"""Расчёт показателей Good Point из трёх Excel-выгрузок.

Использование:
  python3 scripts/compute.py <психологи.xlsx> <стажёры.xlsx> <новые_клиенты.xlsx> > data.json
"""
import sys, re, json, datetime as dt
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs
import openpyxl

def rows(path):
    ws = openpyxl.load_workbook(path, data_only=True).active
    it = ws.iter_rows(values_only=True)
    head = next(it)
    return list(head), [r for r in it if any(v is not None for v in r)]

def pdate(s):
    return dt.datetime.strptime(s.strip(), "%d.%m.%Y %H:%M:%S").date()

# Недели внутри месяца: пн–вс, обрезанные границами данных
def week_key(d):
    monday = d - dt.timedelta(days=d.weekday())
    return monday

# ---------- Психологи ----------
ALIASES = {  # варианты написания одного и того же специалиста
    "настя осипова": "Анастасия Осипова",
    "даша бахтеева": "Дарья Бахтеева",
    "ксюша карпова": "Ксения Карпова",
}
def norm_name(s):
    s = re.sub(r"\s+", " ", s).strip()
    key = s.lower().replace("ё", "е")
    if key in ALIASES: return ALIASES[key]
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))

P_BOOK = re.compile(r"^\s*\d{1,2} \S+ \d{1,2}:\d{2} - \d+x\d+ = \d+\s+(.+?)\s*$")
P_PAY = re.compile(r"^\s*(Оплата .*?консультации(?: онлайн)?)\s+(.+?) - (\d+)x\d+ = \d+\s*$")
P_PACK = re.compile(r"^\s*Пакет (\d+) .*?консультаций - (\d+)x\d+ = \d+\s+(.+?)\s*$")

def parse_psy(text):
    m = P_BOOK.match(text)
    if m: return norm_name(m.group(1)), "Запись на время", 1
    m = P_PACK.match(text)
    if m: return norm_name(m.group(3)), "Пакет консультаций", int(m.group(2))
    m = P_PAY.match(text)
    if m:
        kind = m.group(1)
        k = ("Семейная" if "семейн" in kind else "Детская" if "детск" in kind
             else "Очная" if "очн" in kind else "Консультация")
        return norm_name(m.group(2)), "Оплата: " + k, int(m.group(3))
    if not re.search(r"\d", text):
        return norm_name(text), "Только имя специалиста", 1
    raise ValueError("Не распознана строка: " + text)

def main(psy_path, tr_path, new_path):
    out = {}
    # ---- психологи
    h, data = rows(psy_path)
    assert h[:3] == ["Дата создания", "Дата записи 1", "PROMOCODE"], h
    psy = []
    for r in data:
        name, kind, qty = parse_psy(r[1])
        psy.append(dict(d=pdate(r[0]), name=name, kind=kind, qty=qty,
                        promo=(r[2] or "").strip() or None, pack=kind == "Пакет консультаций"))
    # ---- стажёры
    h, data = rows(tr_path)
    assert h[0] == "Этап сделки" and h[1] == "Дата создания", h
    hi = {k: i for i, k in enumerate(h)}
    tr = []
    for r in data:
        tr.append(dict(d=pdate(r[1]), name=norm_name(r[0]),
                       promo=(r[hi["PROMOCODE"]] or "").strip() or None,
                       utm_source=(r[hi["utm_source"]] or "").strip() or None,
                       utm_medium=(r[hi["utm_medium"]] or "").strip() or None,
                       utm_campaign=(r[hi["utm_campaign"]] or "").strip() or None))
    # ---- новые клиенты
    h, data = rows(new_path)
    assert h == ["Сделки"], h
    deals = []
    for r in data:
        urls = re.findall(r"https?://[^\s,]+", r[0])
        deals.append(urls)

    all_days = sorted({x["d"] for x in psy} | {x["d"] for x in tr})
    d0, d1 = all_days[0], all_days[-1]
    out["period"] = dict(start=d0.isoformat(), end=d1.isoformat(),
                         months=sorted({d.strftime("%Y-%m") for d in all_days}))

    # недели
    weeks = []
    w = week_key(d0)
    while w <= d1:
        a, b = max(w, d0), min(w + dt.timedelta(days=6), d1)
        weeks.append(dict(key=w.isoformat(), start=a.isoformat(), end=b.isoformat(),
                          days=(b - a).days + 1))
        w += dt.timedelta(days=7)
    out["weeks"] = weeks
    def wk(d): return week_key(d).isoformat()

    def series_by_week(items, keyf=None):
        res = defaultdict(lambda: Counter())
        for x in items:
            res[keyf(x) if keyf else "all"][wk(x["d"])] += 1
        return {k: [v.get(w["key"], 0) for w in weeks] for k, v in res.items()}

    def days(items):
        c = Counter(x["d"].isoformat() for x in items)
        days_ = [(d0 + dt.timedelta(days=i)) for i in range((d1 - d0).days + 1)]
        return [c.get(d.isoformat(), 0) for d in days_]

    out["days"] = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]

    # психологи
    pc = Counter(x["name"] for x in psy)
    out["psy"] = dict(
        total=len(psy),
        by_name=pc.most_common(),
        weekly_total=series_by_week(psy)["all"],
        weekly_by_name=series_by_week(psy, lambda x: x["name"]),
        daily=days(psy),
        kinds=Counter(x["kind"] for x in psy).most_common(),
        pack_rows=sum(x["pack"] for x in psy),
        multi_qty_rows=sum(1 for x in psy if x["qty"] > 1 and not x["pack"]),
        qty_sum_nonpack=sum(x["qty"] for x in psy if not x["pack"]),
    )
    # стажёры
    tc = Counter(x["name"] for x in tr)
    out["tr"] = dict(total=len(tr), by_name=tc.most_common(),
                     weekly_total=series_by_week(tr)["all"],
                     weekly_by_name=series_by_week(tr, lambda x: x["name"]),
                     daily=days(tr))
    # UTM в записях к стажёрам (сырые значения)
    out["tr_utm_source"] = Counter(x["utm_source"] or "Не указан" for x in tr).most_common()
    out["tr_utm_combo"] = Counter(
        " / ".join(v or "—" for v in (x["utm_source"], x["utm_medium"], x["utm_campaign"]))
        for x in tr if x["utm_source"] or x["utm_medium"] or x["utm_campaign"]).most_common()

    # промокоды
    promo = defaultdict(lambda: dict(psy=0, tr=0))
    for x in psy:
        if x["promo"]: promo[x["promo"]]["psy"] += 1
    for x in tr:
        if x["promo"]: promo[x["promo"]]["tr"] += 1
    out["promo"] = dict(
        psy_rows=sum(1 for x in psy if x["promo"]), tr_rows=sum(1 for x in tr if x["promo"]),
        codes=sorted(([k, v["psy"], v["tr"]] for k, v in promo.items()), key=lambda r: -(r[1] + r[2])),
        weekly_psy=series_by_week([x for x in psy if x["promo"]]).get("all", [0]*len(weeks)),
        weekly_tr=series_by_week([x for x in tr if x["promo"]]).get("all", [0]*len(weeks)),
    )

    # новые клиенты: тип страницы
    def page_type(u):
        p = urlparse(u)
        path = p.path.strip("/").lower()
        if path == "trainee1": return "Запись к стажёрам (/trainee1)"
        if path == "interns-program": return "Программа стажёров (/interns-program)"
        if path == "pay": return "Страница оплаты (/pay)"
        if path in ("specialists", "depression"): return "Каталог и подборки специалистов"
        if path in ("", "contacts", "user_agreement"): return "Главная и служебные страницы"
        return "Личная страница психолога"
    def utm_src(u):
        q = parse_qs(urlparse(u.split("#")[0]).query)
        return q.get("utm_source", [None])[0]
    deal_type = Counter(); touch = Counter(); src = Counter(); leads_per = Counter()
    for urls in deals:
        types = {page_type(u) for u in urls}
        deal_type[types.pop() if len(types) == 1 else "Несколько типов страниц"] += 1
        for t in {page_type(u) for u in urls}: touch[t] += 1
        s = sorted({utm_src(u) for u in urls} - {None})
        src[" + ".join(s) if s else "Не указан"] += 1
        leads_per[len(urls)] += 1
    out["new"] = dict(total=len(deals), leads_total=sum(len(u) for u in deals),
                      by_type=deal_type.most_common(), touch=touch.most_common(),
                      utm_source=src.most_common(), leads_per_deal=sorted(leads_per.items()))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main(*sys.argv[1:4])
