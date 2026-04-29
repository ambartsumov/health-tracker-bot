# Deploy script for Health Telegram Bot
# For Linux server deployment

#!/bin/bash

set -e

# Configuration
APP_NAME="health-bot"
APP_DIR="/opt/${APP_NAME}"
USER_NAME="${APP_NAME}"
GROUP_NAME="${APP_NAME}"
PYTHON_VERSION="3.11"

echo "[>>] Starting deployment of ${APP_NAME}..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[!!] Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Install system dependencies
echo "[*] Installing system dependencies..."
apt-get update
apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    git \
    curl \
    gcc \
    libffi-dev

# Create user and group
echo "[>] Creating user and group..."
if ! getent group "${GROUP_NAME}" > /dev/null 2>&1; then
    groupadd "${GROUP_NAME}"
fi
if ! id "${USER_NAME}" > /dev/null 2>&1; then
    useradd -r -g "${GROUP_NAME}" -d "${APP_DIR}" -s /bin/bash "${USER_NAME}"
fi

# Create application directory
echo "[>] Creating application directory..."
mkdir -p "${APP_DIR}"
chown "${USER_NAME}:${GROUP_NAME}" "${APP_DIR}"

# Clone or copy repository
echo "[>] Copying application files..."
# If using git:
# git clone <repository-url> "${APP_DIR}"
# Otherwise, copy files manually
cp -r ./* "${APP_DIR}/"
chown -R "${USER_NAME}:${GROUP_NAME}" "${APP_DIR}"

# Create virtual environment
echo "[>] Creating virtual environment..."
cd "${APP_DIR}"
su - "${USER_NAME}" -c "python${PYTHON_VERSION} -m venv venv"

# Install dependencies
echo "[*] Installing Python dependencies..."
su - "${USER_NAME}" -c "${APP_DIR}/venv/bin/pip install --upgrade pip"
su - "${USER_NAME}" -c "${APP_DIR}/venv/bin/pip install -r ${APP_DIR}/requirements.txt"

# Create .env file
echo "[>] Creating environment file..."
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    echo "[!]  Remember to edit ${APP_DIR}/.env with your API keys!"
fi

# Create data directories
echo "[>] Creating data directories..."
mkdir -p "${APP_DIR}/data/users"
mkdir -p "${APP_DIR}/data/reports"
mkdir -p "${APP_DIR}/data/backups"
mkdir -p "${APP_DIR}/data/uploads"
chown -R "${USER_NAME}:${GROUP_NAME}" "${APP_DIR}/data"

# Initialize database
echo "[>] Initializing database..."
su - "${USER_NAME}" -c "${APP_DIR}/venv/bin/python ${APP_DIR}/database/migrations.py"

# Install systemd service
echo "[>] Installing systemd service..."
cp "${APP_DIR}/health-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "${APP_NAME}"

# Configure firewall (if ufw is available)
if command -v ufw &> /dev/null; then
    echo "[>] Configuring firewall..."
    ufw allow out 443/tcp  # HTTPS for API calls
    ufw allow out 80/tcp   # HTTP for API calls
fi

# Set up log rotation
echo "[>] Setting up log rotation..."
cat > /etc/logrotate.d/${APP_NAME} << EOF
/var/log/journal/*/${APP_NAME}*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ${USER_NAME} ${GROUP_NAME}
}
EOF

# Start service
echo "[>>] Starting service..."
systemctl start "${APP_NAME}"

# Check status
echo "[>] Service status:"
systemctl status "${APP_NAME}" --no-pager

# Show logs
echo ""
echo "[>] Recent logs:"
journalctl -u "${APP_NAME}" -n 20 --no-pager

echo ""
echo "[OK] Deployment complete!"
echo ""
echo "[>] Next steps:"
echo "   1. Edit ${APP_DIR}/.env with your API keys"
echo "   2. Restart service: sudo systemctl restart ${APP_NAME}"
echo "   3. Check logs: sudo journalctl -u ${APP_NAME} -f"
echo ""
echo "[>] Useful commands:"
echo "   Start:   sudo systemctl start ${APP_NAME}"
echo "   Stop:    sudo systemctl stop ${APP_NAME}"
echo "   Restart: sudo systemctl restart ${APP_NAME}"
echo "   Status:  sudo systemctl status ${APP_NAME}"
echo "   Logs:    sudo journalctl -u ${APP_NAME} -f"
