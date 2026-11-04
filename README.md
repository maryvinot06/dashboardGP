# Good Point — визуальная статистика

Отчёт опубликован через GitHub Pages из папки `docs/` и защищён паролем:
`docs/index.html` содержит только зашифрованный отчёт (AES-256-GCM, ключ из пароля через PBKDF2,
600 000 итераций). Расшифровка идёт в браузере после ввода пароля.

Открытые данные (`report/data.json`, `report/goodpoint_*.html`) и Excel-файлы в репозиторий
не попадают — см. `.gitignore`. Репозиторий публичный.

## Обновить отчёт

```bash
python3 scripts/compute.py психологи.xlsx стажёры.xlsx новые_клиенты.xlsx > report/data.json
python3 scripts/build.py report/data.json report/goodpoint_YYYY-MM.html
GP_PASSWORD='пароль' python3 scripts/encrypt.py report/goodpoint_YYYY-MM.html docs/index.html
```

Чтобы сменить пароль, достаточно заново выполнить последнюю команду с новым паролем.
