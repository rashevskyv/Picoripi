# Picoripi Companion

Picoripi Companion is a mobile web companion (PWA) and lightweight synchronization server for [Picoripi](https://github.com/rashevskyv/Picoripi). It allows you to open your translation glossary on your mobile phone, review candidate translation variants, approve terms ("Confirm & Next"), inspect game lore with dynamic `{{TERM}}` substitution, and read in-game line occurrences (with English quotes and Russian reference translations) wherever you are.

---

## Architecture

- **Backend**: FastAPI + Uvicorn (Python 3.10+). Handles project storage, automatic `.bak` backups, occurrences context caching, and REST API.
- **Frontend**: Responsive Mobile Single Page Application (PWA). Works on iOS Safari, Android Chrome, and desktop browsers. Supports "Add to Home Screen" for standalone app experience.
- **Desktop Integration**: Picoripi desktop app syncs glossary and occurrence data directly to the Companion server via `[☁ Companion Sync...]` button in the Glossary window.

---

## Deployment on Ubuntu Server

### Option A: Docker Compose (Recommended)

1. Clone or copy the repository onto your Ubuntu server:
   ```bash
   git clone https://github.com/rashevskyv/Picoripi.git
   cd Picoripi
   ```

2. (Optional) Set your secret token in `companion/server/docker-compose.yml`:
   ```yaml
   environment:
     - PICORIPI_COMPANION_TOKEN=my_secret_token
     - COMPANION_PORT=8000
   ```

3. Launch the container:
   ```bash
   cd companion/server
   docker compose up -d --build
   ```

4. The companion web app is now live at `http://<your-server-ip>:8000`!

---

### Option B: Native systemd Service

1. On your Ubuntu server, run the automated installation script:
   ```bash
   cd Picoripi
   chmod +x companion/server/install_ubuntu.sh
   sudo ./companion/server/install_ubuntu.sh my_secret_token 8000
   ```

2. Check service status:
   ```bash
   sudo systemctl status picoripi-companion
   ```

---

## Connecting from Mobile Phone

1. Open `http://<your-server-ip>:8000` in Safari (iOS) or Chrome (Android).
2. Enter your **Access Token / PIN** (default: `picoripi`).
3. Tap **"Share" ➔ "Add to Home Screen"** (iOS) or **"Install app"** (Android) to install Picoripi Companion as a native-feeling fullscreen PWA.
4. Browse your terms, filter by **"Needs review"**, select proposed AI variants with a single tap, and tap **"✓ Confirm & Next"** to quickly review terms!

---

## Connecting from Picoripi Desktop

1. In Picoripi desktop, go to **Settings ➔ Companion** tab:
   - **Server URL**: `http://<your-server-ip>:8000` (or your domain)
   - **API Token / PIN**: `my_secret_token`
   - Click **"Test Connection"** to verify reachability.
2. In the Glossary Dialog (`Ctrl+G`), click the **`[☁ Companion Sync...]`** button:
   - **⬆ Push Glossary & Context to Mobile Companion**: uploads terms, AI proposed variants, and occurrence quotes to the server.
   - **⬇ Pull Reviewed Glossary from Mobile Companion**: downloads approved terms back to your PC, creates a local `.bak` backup, and updates your project in real-time.
