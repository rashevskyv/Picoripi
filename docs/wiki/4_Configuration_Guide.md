# Configuration

**Language:** English · [Українська](uk/4_Configuration_Guide.md)

User-facing settings live in **Settings…** (`Ctrl+P`), `ui/settings_dialog.py`. On-disk: `settings.json` in the working directory (do not commit it). Optional `.env` is loaded at startup (`core/settings_manager.py` + `python-dotenv`) for API key env vars.

This page lists **controls as the UI shows them**, then the files they persist to.

---

## Settings tabs

### Global

| Control | Notes |
|---------|--------|
| Theme (requires restart) | Auto, Light, Dark. Changing it shows “A restart is required to apply the new theme.” |
| Active Game Plugin | Discovered from `plugins/*/config.json`. Changing it requires restart |
| Application Font Size | 6–24, default 10 |
| Tooltip Font Size | 6–32, default 11 |
| External Tool/Script Path | `.bat` / `.cmd` / `.exe` — the toolbar `>_` button |
| Show special spaces as dots | |
| Space Dot Color | |
| Restore unsaved session on startup | If unchecked, unsaved changes are discarded on close |
| Show prompt editor before AI requests | |
| Enable Live Preview (turn off to reduce lag) | Also **View → Preview** |
| Enable Real-Time Warning Scan (turn off to reduce lag) | |
| Enable Glossary System (turn off to reduce lag) | |
| Show archive size warnings | Packed archive larger than original |
| Auto-Sleep Idle Delay (minutes) | 1–60, default 5. Idle after a finished task before sleep |

### Project (only with a project open)

Subtabs:

| Subtab | Role |
|--------|------|
| File Paths | **Directory Mode (Load from folder)**, **Auto-generate translation path**, Original / Changes paths, Original Fonts Directory Path, Fonts Directory Path |
| Display | Default Font for Project, wrap preview, wrap editors, Newline Symbol + style, Tag Style |
| Rules | Game Dialog Max Width (px), Editor Line Width Warning (px), Show guideline, Lines Per Page. For `zelda_bmg`: **Window limit mode** — Shared for all windows vs Separate by window type (`window_layouts.json`) |
| Context Tags | Custom insert/wrap tags for the editor menu |
| Tag Aliases | alias ↔ original tag; **File → Reload Tag Mappings from Settings** |
| Font Map | Glyph widths |
| Detection | Per-problem-id checkboxes from `get_problem_definitions()` |
| Auto-fix | Which of those ids Auto-fix may apply |

Changing Rules marks a rescan.

### Spelling

Enable spell checking · Dictionary Language · **Manage Dictionaries…** (download/remove Hunspell dicts; words added via Spellcheck → Add to Dictionary).

### AI Translation / AI Glossary

See [11. AI Translation](11_AI_Translation.md). Keys belong in Settings or `.env`, never in git.

Default translation config (`build_default_translation_config`): provider `disabled`, workers `6`, OpenAI env `OPENAI_API_KEY`, Gemini env `GEMINI_API_KEY`, OpenAI timeout 60 s, Gemini timeout 120 s.

### Logging

| Control | |
|---------|--|
| Enable Console Logging | |
| Enable File Logging | |
| Log AI Traffic to File (`ai_traffic.log`) | |
| Log File Path | empty → `app_debug.txt` |

Categories: general, lifecycle, file_ops, settings, ui_action, ai, scanner, plugins.

---

## Files next to the app

| File | Role |
|------|------|
| `settings.json` | Global + last plugin + AI presets + `ui_language` (`en` / `uk`). Local; untracked |
| `locales/en.json` | English UI catalog (keys = English source strings) |
| `locales/uk.json` | Ukrainian UI catalog. Add a key here whenever you add `tr("...")` in code |
| `.env` | Optional `OPENAI_API_KEY`, `GEMINI_API_KEY`, … |
| `session` / `.picoripi_session.json` | UI filters, navigation, unsaved edits, undo. **Show Unsaved Only** is forced off on restore |
| `project.uiproj` | Project record: name, plugin folder, source/translation paths |
| plugin `config.json` | Defaults for that game |
| plugin `aliases.json` | Extra tag aliases |
| `translation_prompts/` | Prompt JSON used by Edit Prompts JSON / glossary pipeline |

---

## What not to do

- Do not commit `settings.json`, `.env`, session files, or API keys.
- Do not switch **Active Game Plugin** and expect BMG load without restart.
- Do not point External Tool at a build that reads unsaved buffers — Save first.
- Do not put machine-absolute paths in wiki or README examples.

To fill extra interface languages (or to complete Ukrainian): start Gemini Web2API, then run `tools/i18n-translate/run.bat`. The window selects target languages; **Ukrainian is on by default**. Other languages stay off until a deploy pass. The in-app **Language** menu still shows only English and Ukrainian until `SHIPPED_UI_LANGUAGES` is extended.
