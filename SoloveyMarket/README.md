# Solovey Market / Соловей Сервис

Локальная площадка заявок на услуги:
- клиентская форма заявок;
- диспетчерская канбан-доска;
- Telegram-бот для исполнителей;
- отклики исполнителей;
- назначение исполнителя с причиной;
- скрытие точного адреса и телефона до назначения;
- рейтинг доверия заказчиков и исполнителей;
- расширение географии через запросы новых населённых пунктов;
- базовая защита админки логином и паролем.

## 1. Быстрый запуск локально

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\activate
```

Установить зависимости:

```bash
pip install -r requirements.txt
```

Скопируй `.env.example` в `.env` и заполни:

```env
BOT_TOKEN=токен_бота
ADMIN_ID=ваш_telegram_id_цифрами
DB_PATH=data/marketplace.db
ADMIN_LOGIN=admin
ADMIN_PASSWORD=ваш_пароль
```

Запуск:

```bash
python main.py
```

Сайт:

```text
http://127.0.0.1:8000
```

Админка:

```text
http://127.0.0.1:8000/admin
```

## 2. Логика работы

Клиент создаёт заявку. Диспетчер получает уведомление, уточняет детали и нажимает “Искать”. Исполнители получают заявку без точного адреса и телефона. После отклика диспетчер назначает исполнителя с указанием причины. Только назначенный исполнитель получает телефон и точный адрес.

## 3. Хостинг / VPS

Проверочный запуск:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Пример systemd:

```ini
[Unit]
Description=Solovey Market FastAPI
After=network.target

[Service]
WorkingDirectory=/var/www/solovey-market
ExecStart=/var/www/solovey-market/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
User=www-data
EnvironmentFile=/var/www/solovey-market/.env

[Install]
WantedBy=multi-user.target
```

Nginx:

```nginx
server {
    listen 80;
    server_name ваш-домен.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Важно

- поменять ADMIN_PASSWORD;
- не публиковать `.env`;
- включить HTTPS;
- регулярно делать копию `data/marketplace.db`;
- при росте заменить SQLite на PostgreSQL.
