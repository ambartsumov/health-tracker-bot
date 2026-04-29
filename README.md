# Health Tracker Bot

Telegram-бот для отслеживания питания, тренировок и показателей здоровья.
инальный проект по курсу Python.

##  проекте

от помогает вести дневник здоровья прямо в Telegram: считает калории, фиксирует тренировки, отслеживает метрики (вес, давление, анализы крови). ожно сфотографировать еду — бот распознает блюдо и посчитает .  конце недели/месяца генерируется Excel-отчёт с графиками.

исал этот проект после прохождения курса Python, чтобы применить всё изученное на практике: работа с API, база данных, асинхронный код, Docker.

## озможности

- **итание** — фото-распознавание еды через Gemini Vision, ручной ввод, подсчёт 
- **Тренировки** — лог тренировок, ежедневный опрос, анализ прогресса
- **доровье** — метрики (вес, давление, пульс), импорт анализов крови по фото
- **апоминания** — приём пищи, ы, тренировки, вечерний итог дня
- **тчёты** — еженедельные и ежемесячные Excel-таблицы с диаграммами
- **нбординг** — первичная настройка профиля, расчёт нормы калорий (формула иффлина-Сан еора)

## Стек

- Python 3.9+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API
- SQLAlchemy + SQLite — хранение данных
- Alembic — миграции 
- Gemini Vision API — распознавание еды и анализов
- DeepSeek API — персональные рекомендации (опционально)
- openpyxl — генерация Excel-отчётов
- Docker — контейнеризация

## ыстрый старт

### Требования
- Python 3.9+
- Токен Telegram-бота (создать у @BotFather)
- API-ключ Gemini (Google AI Studio — бесплатно)

### становка

```bash
git clone https://github.com/your-username/health-tracker-bot.git
cd health-tracker-bot

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### астройка

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

ткрыть `.env` и заполнить:

```env
TELEGRAM_BOT_TOKEN=ваш_токен
GEMINI_API_KEY=ваш_ключ
```

### апуск

```bash
# нициализация 
python database/migrations.py

# апуск бота
python bot.py
```

### Docker

```bash
docker-compose up -d
```

## Структура проекта

```
health-tracker-bot/
├── bot.py                  # Точка входа, хендлеры Telegram
├── config.py               # онфигурация из .env
├── requirements.txt
├── database/
│   ├── models.py           # ORM-модели (SQLAlchemy)
│   ├── manager.py          # CRUD операции
│   └── migrations.py       # Скрипт миграций
├── modules/
│   ├── onboarding.py       # нбординг нового пользователя
│   ├── profile.py          # рофиль пользователя
│   ├── nutrition/          # чёт питания
│   ├── training/           # Тренировки
│   ├── health/             # етрики здоровья
│   ├── reminders/          # апоминания
│   ├── analytics/          # Excel-отчёты
│   └── integrations/       # нешние API
├── utils/
│   ├── image_processor.py  # бработка фото
│   ├── security.py         # Шифрование данных
│   ├── rate_limiter.py     # граничение запросов
│   └── logger.py
├── tests/
└── data/                   # анные пользователей, отчёты
```

## оманды бота

| оманда | писание |
|---------|----------|
| `/start` | ачало работы / приветствие |
| `/help` | омощь |
| `/profile` | рофиль и статистика |
| `/settings` | астройки |
| `/today` | тог дня |
| `/week` | тог недели |
| `/report` | Сгенерировать Excel-отчёт |
| `/health` | вести показатели здоровья |
| `/cancel` | тмена текущего действия |

## еременные окружения

| еременная | бязательная | писание |
|-----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | а | Токен бота |
| `GEMINI_API_KEY` | а | люч Gemini (распознавание фото) |
| `DEEPSEEK_API_KEY` | ет | люч DeepSeek (рекомендации) |
| `DATABASE_URL` | ет | URL  (по умолчанию SQLite) |
| `TIMEZONE` | ет | асовой пояс (по умолчанию Europe/Moscow) |
| `ENCRYPTION_PASSWORD` | ет | ароль шифрования данных |

## Тестирование

```bash
pytest
pytest --cov=.
```

## езопасность

- Шифрование чувствительных данных (Fernet, PBKDF2)
- Санитизация входных данных
- Rate limiting
- удит-лог действий

## еплой

одробнее в [DEPLOYMENT.md](DEPLOYMENT.md) — инструкция для деплоя на Linux-сервер (systemd) и Docker.

## ицензия

MIT — подробнее в [LICENSE](LICENSE).