#!/usr/bin/env bash
# Picoripi Companion Server - Ubuntu Systemd Installer
set -e

echo "=== Installing Picoripi Companion Server ==="

INSTALL_DIR="/opt/picoripi-companion"
SERVICE_NAME="picoripi-companion"
TOKEN="${1:-picoripi}"
PORT="${2:-8000}"

echo "Creating installation directory at $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r . "$INSTALL_DIR"

cd "$INSTALL_DIR"

echo "Setting up Python virtual environment..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

if [ ! -d "venv" ]; then
    sudo python3 -m venv venv
fi

sudo "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install -r companion/server/requirements.txt

echo "Configuring systemd service..."
sudo bash -c "cat > /etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Picoripi Companion Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PICORIPI_COMPANION_TOKEN=${TOKEN}"
Environment="COMPANION_PORT=${PORT}"
Environment="COMPANION_HOST=0.0.0.0"
Environment="PYTHONPATH=$INSTALL_DIR"
ExecStart=$INSTALL_DIR/venv/bin/python -m uvicorn companion.server.main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo "=== Installation Complete! ==="
echo "Service is running on port ${PORT} with auth token: ${TOKEN}"
echo "Check status: sudo systemctl status ${SERVICE_NAME}"
echo "View logs: sudo journalctl -u ${SERVICE_NAME} -f"
