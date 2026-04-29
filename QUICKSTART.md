# ыстрый старт

## 1. олучить токены

- **Telegram**: написать @BotFather → `/newbot` → скопировать токен
- **Gemini**: зарегистрироваться на [aistudio.google.com](https://aistudio.google.com) → создать API-ключ (бесплатно)

## 2. становка

```bash
git clone https://github.com/your-username/health-tracker-bot.git
cd health-tracker-bot
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## 3. астройка

```bash
copy .env.example .env
```

ткрыть `.env` в любом текстовом редакторе и вставить токены:

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
GEMINI_API_KEY=AIzaSy...
```

## 4. апуск

```bash
python database/migrations.py
python bot.py
```

от готов к работе. ткрыть Telegram и написать `/start`.