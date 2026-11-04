"""Собирает HTML-отчёт: подставляет data.json в report/template.html.

  python3 scripts/build.py data.json report/goodpoint_2026-10.html [--fragment]
--fragment: без <!doctype>/<head> (для публикации как Artifact).
"""
import sys, json, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
data = json.load(open(sys.argv[1], encoding="utf-8"))
tpl = (root / "report" / "template.html").read_text(encoding="utf-8")
html = tpl.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
if "--fragment" not in sys.argv:
    html = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + html.replace("<div class=\"wrap\">", "</head>\n<body>\n<div class=\"wrap\">", 1)
            + "\n</body>\n</html>\n")
pathlib.Path(sys.argv[2]).write_text(html, encoding="utf-8")
