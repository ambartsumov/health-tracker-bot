# Health Tracker Bot

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/telegram-bot-2CA5E0?logo=telegram">
  <img src="https://img.shields.io/badge/AI-Gemini_Vision-4285F4?logo=google">
  <img src="https://img.shields.io/badge/database-SQLite-003B57?logo=sqlite">
  <img src="https://img.shields.io/badge/deploy-Docker-2496ED?logo=docker">
  <img src="https://img.shields.io/badge/license-MIT-green">
</p>

<p align="center">
  <a href="#english">English</a> · <a href="#russian">Русский</a>
</p>

---

<a name="english"></a>

## Overview

**Health Tracker Bot** is a Telegram bot for tracking nutrition, workouts, and health metrics.
A personal project for health, nutrition and fitness tracking.

The bot lets you keep a health diary right in Telegram: counts calories, logs workouts, and tracks metrics (weight, blood pressure, lab results).
Photograph your meal — the bot recognizes the dish and calculates CJPF (calories, proteins, fats, carbs).
Weekly and monthly Excel reports with charts are generated automatically.

## Features

- **Nutrition** — photo recognition via Gemini Vision, manual entry, CJPF calculation
- **Workouts** — workout log, daily check-in, progress analysis
- **Health** — metrics tracking (weight, blood pressure, heart rate), blood test import via photo
- **Reminders** — meals, supplements, workouts, end-of-day summary
- **Reports** — weekly and monthly Excel spreadsheets with charts
- **Onboarding** — profile setup, calorie target calculation (Mifflin-St Jeor formula)

## Tech Stack

- **Python 3.9+**
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API
- **SQLAlchemy + SQLite** — data storage
- **Alembic** — database migrations
- **Gemini Vision API** — food and lab result recognition
- **DeepSeek API** — personalized recommendations (optional)
- **openpyxl** — Excel report generation
- **Docker** — containerization

## Quick Start

### Requirements
- Python 3.9+
- Telegram bot token (create via @BotFather)
- Gemini API key (Google AI Studio — free tier available)

### Installation

```bash
git clone https://github.com/ambartsumov/health-tracker-bot.git
cd health-tracker-bot

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### Configuration

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Edit `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=your_token
GEMINI_API_KEY=your_key
```

### Run

```bash
# Initialize database
python database/migrations.py

# Start the bot
python bot.py
```

### Docker

```bash
docker-compose up -d
```

## Project Structure

```
health-tracker-bot/
├── bot.py                  # Entry point, Telegram handlers
├── config.py               # Configuration from .env
├── requirements.txt
├── database/
│   ├── models.py           # ORM models (SQLAlchemy)
│   ├── manager.py          # CRUD operations
│   └── migrations.py       # Migration script
├── modules/
│   ├── onboarding.py       # New user onboarding
│   ├── profile.py          # User profile
│   ├── nutrition/          # Nutrition tracking
│   ├── training/           # Workout tracking
│   ├── health/             # Health metrics
│   ├── reminders/          # Reminders
│   ├── analytics/          # Excel reports
│   └── integrations/       # External APIs
├── utils/
│   ├── image_processor.py  # Photo processing
│   ├── security.py         # Data encryption
│   ├── rate_limiter.py     # Request limiting
│   └── logger.py
├── tests/
└── data/                   # User data, reports
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start / welcome message |
| `/help` | Help |
| `/profile` | Profile and statistics |
| `/settings` | Settings |
| `/today` | Today's summary |
| `/week` | Weekly summary |
| `/report` | Generate Excel report |
| `/health` | Enter health metrics |
| `/cancel` | Cancel current action |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token |
| `GEMINI_API_KEY` | Yes | Gemini key (photo recognition) |
| `DEEPSEEK_API_KEY` | No | DeepSeek key (recommendations) |
| `DATABASE_URL` | No | DB URL (default: SQLite) |
| `TIMEZONE` | No | Timezone (default: Europe/Moscow) |
| `ENCRYPTION_PASSWORD` | No | Data encryption password |

## Testing

```bash
pytest
pytest --cov=.
```

## Security

- Sensitive data encryption (Fernet, PBKDF2)
- Input sanitization
- Rate limiting
- Action audit log

## License

MIT License — see [LICENSE](LICENSE)

## Author

Ambartsumov Vyacheslav — [GitHub](https://github.com/ambartsumov)

---
---

<a name="russian"></a>

## Описание

**Health Tracker Bot** — Telegram-бот для отслеживания питания, тренировок и показателей здоровья.
ФСамостоятельный проект: полноценный инструмент для трекинга здоровья.

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

- **Python 3.9+**
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API
- **SQLAlchemy + SQLite** — хранение данных
- **Alembic** — миграции БД
- **Gemini Vision API** — распознавание еды и анализов
- **DeepSeek API** — персональные рекомендации (опционально)
- **openpyxl** — генерация Excel-отчётов
- **Docker** — контейнеризация

## Быстрый старт

### Требования
- Python 3.9+
- Токен Telegram-бота (создать у @BotFather)
- API-ключ Gemini (Google AI Studio — бесплатно)

### Установка

```bash
git clone https://github.com/ambartsumov/health-tracker-bot.git
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

## Лицензия

MIT License — см. [LICENSE](LICENSE)

## Автор

Амбарцумов Вячеслав — [GitHub](https://github.com/ambartsumov)
