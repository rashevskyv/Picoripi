---
status: current
updated: 2026-10-02
owns: core/companion_sync.py, companion/
tokens: 1.8k
purpose: Companion server and glossary sync
---
# Picoripi Companion (Mobile PWA & Sync)

**Language:** English · [Українська](uk/12_Picoripi_Companion.md)

Picoripi Companion lets translators review, edit, and approve glossary entries on a mobile phone (iOS Safari or Android Chrome) or tablet. It consists of a mobile Progressive Web App (PWA), a lightweight FastAPI backend server, and an automatic background synchronization client embedded in Picoripi desktop.

Desktop implementation: `core/companion_sync.py`, `ui/settings/companion_mixin.py`. Server & web app: `companion/server/`, `companion/web/`. Deployment guide: `companion/README.md`.

---

## 1. Desktop Configuration

Configure the companion server endpoint in **Settings → Companion** (`Ctrl+P`):

| Setting | Notes |
|---------|-------|
| Companion Server URL | Endpoint of your Companion instance, e.g. `http://127.0.0.1:8000` or `http://<server-ip>:8000`. Persisted in `settings.json` (`companion_server_url`). |
| API Token / PIN | Bearer security token (default: `picoripi`). Persisted in `settings.json` (`companion_api_token`). |
| Automatically sync on project open and close | Checkbox (`companion_auto_sync`, default on). Automatically keeps local and server glossaries in sync. |
| Test Connection | Tests connectivity and credentials against the server. |

### Background Auto-Sync Workflow

When **Automatically sync on project open and close** is enabled:
- **Startup Auto-Pull**: 600 ms after UI initialization or whenever a project is opened, Picoripi launches a non-blocking `CompanionPullWorker` thread. If remote terms were confirmed or edited on mobile, local `glossary.json` is safely updated (after creating a durable `glossary.json.bak` backup), in-memory data structures are hot-reloaded (`glossary_mgr.refresh_from_disk()`), editor syntax highlighting is refreshed, and open review dialogs reload automatically.
- **Diff Check**: If local and remote glossaries are already identical, `changed_count = 0` and disk writes are completely skipped, reporting a calm status: `Companion: glossary is in sync with server.`.
- **Auto-Push Fallback**: If the server has no terms for the current project while the local project has terms, Picoripi automatically pushes the initial glossary so terms become immediately available on mobile.
- **Save & Exit Auto-Push**: Saving changes (`Ctrl+S`), closing a project, closing the glossary dialog, or exiting the application automatically launches a background `CompanionPushWorker` to send updated terms, context occurrences, and reference translations to the server.
- **Debouncing & Safety**: All network sync requests use a 3-second debounce window and detect active workers (`existing_worker.isRunning()`) to prevent race conditions or duplicate requests. Network timeouts or offline servers never freeze the UI or show blocking modal errors.
- **Manual actions run in the background too**: *Push*, *Pull* and *Test Server Connection* (glossary window and Settings) show a small progress window with **Cancel**; cancelling returns at once and a cancelled pull does not touch the local glossary. After you resolve conflicts, the merge is committed by the same background worker.
- **Exit never waits for a silent server**: the sync window shown on exit gives up after 6 seconds without an answer and closes; **Skip** closes it immediately.

---

## 2. Desktop Manual Synchronization

Translators can also manually trigger synchronization at any time:
1. Open the Glossary dialog (**Glossary…** / `Ctrl+G`).
2. Click the **`[☁ Companion Sync...]`** button in the bottom toolbar.
3. Choose the action:
   - **⬆ Push Glossary & Context to Mobile Companion**: Uploads current terms, AI proposed variants, in-game quotes, and reference translations to the server.
   - **⬇ Pull Reviewed Glossary from Mobile Companion**: Downloads terms reviewed on mobile, creates a local `.bak` backup, updates `glossary.json`, and reloads active views.

---

## 3. Mobile PWA Interface & Workflow

Open `http://<your-server-ip>:8000` on your smartphone browser.

### Installing as a Standalone App (PWA)
- **iOS (Safari)**: Tap **Share ➔ Add to Home Screen**.
- **Android (Chrome)**: Tap **Menu (⋮) ➔ Install app** or **Add to Home Screen**.

The companion opens in full-screen standalone mode without browser URL bars or navigation clutter.

### Key Mobile Features
- **Header**: Compact glowing green status dot (`.status-dot`), streamlined project selector dropdown, and manual sync action.
- **Category Tabs**: Horizontally scrolling category pills (`All`, `Characters`, `Locations`, `Items`, etc.) with real-time term counts.
- **Search & Filters**: Debounced live text search and a **Needs review** filter toggle that isolates unconfirmed terms (confirmed terms are strictly excluded even if they retain historical AI variants).
- **Term Review Screen**:
  - Touch navigation: Previous/Next buttons (`[◀]` and `[▶]`) with 44×38px touch targets, tap animations, and term counter (`X / Y`).
  - Source Card (`О:`): Displays original term with 1-tap clipboard copy.
  - Translation Editor (`П:`): Large touch-friendly input field.
  - **"✓ Confirm & Next"** primary button: Confirms the translation, saves the record, and automatically advances to the next unreviewed entry.
  - **Proposed AI Variants**: Interactive cards displaying candidate translations and rationales; tapping any variant immediately fills the translation field.
  - **Lore & Context Accordions**: Collapsible cards for dynamic lore descriptions (with real-time `{{TERM}}` substitution), user notes, and dialogue occurrences with English script quotes and reference translations.
  - **Layout Ergonomics**: Protected by `flex-shrink: 0` so bottom accordions never get squashed, native momentum scrolling (`-webkit-overflow-scrolling: touch`), and safe-area inset padding.

---

## 4. Server Deployment

The companion backend runs on Python 3.10+ (FastAPI + Uvicorn) and stores project glossaries under `companion/server/projects/` with automatic `.bak` backups before every modification.

### Option A: Docker Compose (Recommended)

1. On your Linux server:
   ```bash
   git clone https://github.com/rashevskyv/Picoripi.git
   cd Picoripi/companion/server
   docker compose up -d --build
   ```
2. The web service starts on port `8000`.

### Option B: Native Ubuntu systemd Service

1. Run the included installer script:
   ```bash
   cd Picoripi
   sudo ./companion/server/install_ubuntu.sh <SECRET_TOKEN> 8000
   ```
2. Manage service:
   ```bash
   sudo systemctl status picoripi-companion
   sudo systemctl restart picoripi-companion
   ```

---

## 5. What not to do

- Do not expose the Companion server to the public internet with the default token `picoripi`. Set a custom `PICORIPI_COMPANION_TOKEN`.
- Do not edit the same term simultaneously on desktop and mobile without syncing first.
- Do not disable `companion_auto_sync` if you frequently review terms on your phone while keeping Picoripi open on desktop.
