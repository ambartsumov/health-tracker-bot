# еплой

## окально (для разработки)

```bash
python bot.py
```

## Docker

```bash
# Собрать и запустить
docker-compose up -d

# росмотр логов
docker-compose logs -f

# становить
docker-compose down
```

## Linux-сервер (systemd)

1. становить Python 3.9+ и зависимости:

```bash
sudo apt update && sudo apt install python3 python3-venv python3-pip -y
```

2. лонировать репозиторий и создать окружение:

```bash
git clone https://github.com/your-username/health-tracker-bot.git /opt/health-bot
cd /opt/health-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. астроить `.env`:

```bash
cp .env.example .env
nano .env
```

4. нициализировать :

```bash
python database/migrations.py
```

5. апустить как systemd-сервис:

```bash
sudo cp health-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable health-bot
sudo systemctl start health-bot
```

6. роверить статус:

```bash
sudo systemctl status health-bot
journalctl -u health-bot -f
```

## бновление

```bash
cd /opt/health-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart health-bot
```