# RC Anallergenic Bot

Telegram-бот для отслеживания цен на Royal Canin Anallergenic на Wildberries.

## Функциональность

- `/prices` — топ-5 минимальных цен прямо сейчас
- Кнопка **🔄 Обновить** — обновить без команды
- `/setalert 1500` — уведомление, когда цена упадёт ниже порога
- `/myalert` — текущий алерт
- `/stopalert` — отключить уведомления
- Автообновление цен каждый час

## Структура проекта

```
rc_anallergenic_bot/
├── main.py              # точка входа, webhook, запуск
├── bot/
│   ├── handlers.py      # команды и кнопки Telegram
│   ├── wb_parser.py     # парсинг цен с Wildberries
│   ├── sheets.py        # чтение/запись Google Sheets
│   └── scheduler.py     # APScheduler, обновление каждый час
├── requirements.txt
├── Procfile             # для Railway
└── .env.example         # шаблон переменных окружения
```

## Деплой на Railway

### 1. Подготовить переменные окружения

В Railway → Settings → Variables добавить:

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather |
| `GOOGLE_CREDS_JSON` | Содержимое credentials.json одной строкой |
| `SPREADSHEET_NAME` | `rc_anallergenic_client` |
| `WEBHOOK_HOST` | Домен Railway (появится после первого деплоя, например `rc-bot.up.railway.app`) |

> **Как получить GOOGLE_CREDS_JSON:** откройте скачанный credentials.json,
> скопируйте всё содержимое и вставьте как значение переменной (без переносов строк).

### 2. Подключить GitHub репозиторий

Railway → New Project → Deploy from GitHub repo → выбрать `rc_anallergenic_bot`.

### 3. Получить домен

После первого деплоя: Railway → Settings → Networking → Generate Domain.
Скопировать домен (без `https://`) в переменную `WEBHOOK_HOST` и передеплоить.

## Локальный запуск (для разработки)

```bash
# Установить зависимости
pip install -r requirements.txt

# Скопировать и заполнить .env
cp .env.example .env

# Для локальной разработки использовать polling вместо webhook:
# Заменить в main.py web.run_app(...) на:
# asyncio.run(dp.start_polling(bot))

python main.py
```

## Google Sheets

Бот создаёт два листа автоматически:

- **prices** — история цен (timestamp, rank, brand, name, price, article, url)
- **subscriptions** — алерты пользователей (user_id, threshold, direction, active, created_at)
