"""Шифрует готовый HTML-отчёт паролем (AES-256-GCM, ключ из пароля через PBKDF2-SHA256)
и собирает страницу-замок, которая расшифровывает отчёт в браузере.

  GP_PASSWORD='...' python3 scripts/encrypt.py report/goodpoint_2026-10.html docs/index.html

Без пароля содержимое страницы прочитать нельзя: в файле только шифротекст.
"""
import os, sys, base64, json, pathlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 600_000
pw = os.environ.get("GP_PASSWORD") or sys.exit("Задайте пароль в переменной GP_PASSWORD")
src, dst = sys.argv[1], sys.argv[2]
plain = pathlib.Path(src).read_bytes()
salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())
ct = AESGCM(key).encrypt(iv, plain, None)
b64 = lambda b: base64.b64encode(b).decode()
payload = json.dumps({"s": b64(salt), "i": b64(iv), "n": ITER, "c": b64(ct)})
lock = pathlib.Path(__file__).with_name("lock.html").read_text(encoding="utf-8")
out = lock.replace("/*PAYLOAD*/null", payload)
pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(dst).write_text(out, encoding="utf-8")
print(f"{dst}: {len(out)//1024} КБ")
