# Health Tracker Bot

Telegram-бот для отслеживания питания, тренировок и показателей здоровья.
Финальный проект по курсу Python.

## О проекте

Бот помогает вести дневник здоровья прямо в Telegram: считает калории, фиксирует тренировки, отслеживает метрики (вес, давление, анализы крови). Можно сфотографировать еду — бот распознает блюдо и посчитает КБЖУ. В конце недели/месяца генерируется Excel-отчёт с графиками.

Писал этот проект после прохождения курса Python, чтобы применить всё изученное на практике: работа с API, база данных, асинхронный код, Docker.

## Возможности

- **Питание** — фото-распознавание еды через Gemini Vision, ручной ввод, подсчёт КБЖУ
- **Тренировки** — лог тренировок, ежедневный опрос, анализ прогресса
- **Здоровье** — метрики (вес, давление, пульс), импорт анализов крови по фото
- **Напоминания** — приём пищи, БАДы, тренировки, вечерний итог дня
- **Отчёты** — еженедельные и ежемесячные Excel-таблицы с диаграммами
- **Онбординг** — первичная настройка профиля, расчёт нормы калорий (формула Миффлина-Сан Жеора)

## Стек

- Python 3.9+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API
- SQLAlchemy + SQLite — хранение данных
- Alembic — миграции БД
- Gemini Vision API — распознавание еды и анализов
- DeepSeek API — персональные рекомендации (опционально)
- openpyxl — генерация Excel-отчётов
- Docker — контейнеризация

## Быстрый старт

### Требования
- Python 3.9+
- Токен Telegram-бота (создать у @BotFather)
- API-ключ Gemini (Google AI Studio — бесплатно)

### Установка

```bash
git clone https://github.com/qwert2009/health-tracker-bot.git
cd health-tracker-bot

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### Настройка

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Открыть `.env` и заполнить:

```env
TELEGRAM_BOT_TOKEN=ваш_токен
GEMINI_API_KEY=ваш_ключ
```

### Запуск

```bash
# Инициализация БД
python database/migrations.py

# Запуск бота
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
├── config.py               # Конфигурация из .env
├── requirements.txt
├── database/
│   ├── models.py           # ORM-модели (SQLAlchemy)
│   ├── manager.py          # CRUD операции
│   └── migrations.py       # Скрипт миграций
├── modules/
│   ├── onboarding.py       # Онбординг нового пользователя
│   ├── profile.py          # Профиль пользователя
│   ├── nutrition/          # Учёт питания
│   ├── training/           # Тренировки
│   ├── health/             # Метрики здоровья
│   ├── reminders/          # Напоминания
│   ├── analytics/          # Excel-отчёты
│   └── integrations/       # Внешние API
├── utils/
│   ├── image_processor.py  # Обработка фото
│   ├── security.py         # Шифрование данных
│   ├── rate_limiter.py     # Ограничение запросов
│   └── logger.py
├── tests/
└── data/                   # Данные пользователей, отчёты
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начало работы / приветствие |
| `/help` | Помощь |
| `/profile` | Профиль и статистика |
| `/settings` | Настройки |
| `/today` | Итог дня |
| `/week` | Итог недели |
| `/report` | Сгенерировать Excel-отчёт |
| `/health` | Ввести показатели здоровья |
| `/cancel` | Отмена текущего действия |

## Переменные окружения

| Переменная | Обязательная | Описание |
|-----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Да | Токен бота |
| `GEMINI_API_KEY` | Да | Ключ Gemini (распознавание фото) |
| `DEEPSEEK_API_KEY` | Нет | Ключ DeepSeek (рекомендации) |
| `DATABASE_URL` | Нет | URL БД (по умолчанию SQLite) |
| `TIMEZONE` | Нет | Часовой пояс (по умолчанию Europe/Moscow) |
| `ENCRYPTION_PASSWORD` | Нет | Пароль шифрования данных |

## Тестирование

```bash
pytest
pytest --cov=.
```

## Безопасность

- Шифрование чувствительных данных (Fernet, PBKDF2)
- Санитизация входных данных
- Rate limiting
- Аудит-лог действий

## Деплой

Подробнее в [DEPLOYMENT.md](DEPLOYMENT.md) — инструкция для деплоя на Linux-сервер (systemd) и Docker.

## Лицензия

MIT — см. [LICENSE](LICENSE).
