#!/usr/bin/env bash
# Picoripi Companion Server - Ubuntu Systemd Installer (No Docker required)
set -e

echo "=== Installing Picoripi Companion Server (Native Systemd) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve REPO_ROOT (where Picoripi repository lives)
if [ -f "${SCRIPT_DIR}/../../main.py" ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
elif [ -f "${SCRIPT_DIR}/../main.py" ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [ -f "${SCRIPT_DIR}/main.py" ]; then
    REPO_ROOT="${SCRIPT_DIR}"
else
    REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi

SERVICE_NAME="picoripi-companion"
TOKEN="${1:-picoripi}"
PORT="${2:-8000}"
RUN_USER="${SUDO_USER:-$(id -un)}"

echo "Repository root: ${REPO_ROOT}"
echo "Running user:    ${RUN_USER}"
echo "Port:            ${PORT}"
echo "Token:           ${TOKEN}"

# Install python3 and venv if not present
echo "Ensuring python3, python3-venv, and python3-pip are installed..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-venv python3-pip
fi

# Create virtual environment inside companion directory
VENV_DIR="${REPO_ROOT}/companion/venv"
echo "Setting up Python virtual environment in ${VENV_DIR}..."
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${REPO_ROOT}/companion/server/requirements.txt" -q

# Create systemd service
echo "Configuring systemd service /etc/systemd/system/${SERVICE_NAME}.service..."
sudo bash -c "cat > /etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Picoripi Companion Server
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${REPO_ROOT}
Environment="PICORIPI_COMPANION_TOKEN=${TOKEN}"
Environment="COMPANION_PORT=${PORT}"
Environment="COMPANION_HOST=0.0.0.0"
Environment="PYTHONPATH=${REPO_ROOT}"
ExecStart=${VENV_DIR}/bin/python -m uvicorn companion.server.main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo ""
echo "=== Picoripi Companion Server Installed & Started Successfully! ==="
echo "Port:       ${PORT}"
echo "Token:      ${TOKEN}"
echo "Status:     systemctl status ${SERVICE_NAME}"
echo "Logs:       journalctl -u ${SERVICE_NAME} -f"
echo "Web URL:    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${PORT}"
