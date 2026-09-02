# Налаштування

**Мова:** [English](../4_Configuration_Guide.md) · Українська

Налаштування для користувача живуть у **Settings…** (`Ctrl+P`), `ui/settings_dialog.py`. На диску: `settings.json` у робочій теці (не комітити). Необов’язковий `.env` читається на старті (`core/settings_manager.py` + `python-dotenv`) для змінних ключів API.

Тут — **контролі, як їх показує UI**, потім файли, куди вони зберігаються.

---

## Вкладки Settings

### Global

| Контроль | Нотатки |
|----------|---------|
| Theme (requires restart) | Auto, Light, Dark. Зміна показує “A restart is required to apply the new theme.” |
| Active Game Plugin | Знаходиться з `plugins/*/config.json`. Зміна потребує перезапуску |
| Application Font Size | 6–24, типово 10 |
| Tooltip Font Size | 6–32, типово 11 |
| External Tool/Script Path | `.bat` / `.cmd` / `.exe` — кнопка тулбара `>_` |
| Show special spaces as dots | |
| Space Dot Color | |
| Restore unsaved session on startup | Якщо знято — незбережені зміни викидаються при закритті |
| Show prompt editor before AI requests | |
| Enable Live Preview (turn off to reduce lag) | Також **View → Preview** |
| Enable Real-Time Warning Scan (turn off to reduce lag) | |
| Enable Glossary System (turn off to reduce lag) | |
| Show archive size warnings | Запакований архів більший за оригінал |
| Auto-Sleep Idle Delay (minutes) | 1–60, типово 5. Простій після завершеної задачі перед сном |

### Project (лише з відкритим проєктом)

Підвкладки:

| Підвкладка | Роль |
|------------|------|
| File Paths | **Directory Mode (Load from folder)**, **Auto-generate translation path**, шляхи Original / Changes, Original Fonts Directory Path, Fonts Directory Path |
| Display | Default Font for Project, wrap preview, wrap editors, Newline Symbol + стиль, Tag Style |
| Rules | Game Dialog Max Width (px), Editor Line Width Warning (px), Show guideline, Lines Per Page. Для `zelda_bmg`: **Window limit mode** — Shared for all windows vs Separate by window type (`window_layouts.json`) |
| Context Tags | Власні insert/wrap-теги для меню редактора |
| Tag Aliases | аліас ↔ оригінальний тег; **File → Reload Tag Mappings from Settings** |
| Font Map | Ширини гліфів |
| Detection | Чекбокси по id проблем з `get_problem_definitions()` |
| Auto-fix | Які з цих id може застосовувати Auto-fix |

Зміна Rules позначає rescan.

### Spelling

Enable spell checking · Dictionary Language · **Manage Dictionaries…** (завантажити/прибрати словники Hunspell; слова з Spellcheck → Add to Dictionary).

### AI Translation / AI Glossary

Див. [11. AI-переклад](11_AI_Translation.md). Ключі — у Settings або `.env`, ніколи в git.

Типовий конфіг (`build_default_translation_config`): provider `disabled`, workers `6`, OpenAI env `OPENAI_API_KEY`, Gemini env `GEMINI_API_KEY`, таймаут OpenAI 60 с, Gemini 120 с.

### Logging

| Контроль | |
|----------|--|
| Enable Console Logging | |
| Enable File Logging | |
| Log AI Traffic to File (`ai_traffic.log`) | |
| Log File Path | порожньо → `app_debug.txt` |

Категорії: general, lifecycle, file_ops, settings, ui_action, ai, scanner, plugins.

---

## Файли поруч із програмою

| Файл | Роль |
|------|------|
| `settings.json` | Глобальні + останній плагін + пресети AI + `ui_language` (`en` / `uk`). Локальний; не в git |
| `locales/en.json` | Англійський каталог UI (ключ = англійське джерело) |
| `locales/uk.json` | Український каталог UI. Новий `tr("...")` у коді одразу додає сюди той самий ключ |
| `.env` | Необов’язково `OPENAI_API_KEY`, `GEMINI_API_KEY`, … |
| `session` / `.picoripi_session.json` | Фільтри UI, навігація, незбережені правки, undo. **Show Unsaved Only** при відновленні примусово вимикається |
| `project.uiproj` | Запис проєкту: ім’я, тека плагіна, шляхи source/translation |
| `config.json` плагіна | Типові значення для цієї гри |
| `aliases.json` плагіна | Додаткові аліаси тегів |
| `translation_prompts/` | JSON промптів для Edit Prompts JSON / пайплайну глосарія |

---

## Чого не робити

- Не комітьте `settings.json`, `.env`, файли сесії чи ключі API.
- Не змінюйте **Active Game Plugin** і не чекайте завантаження BMG без перезапуску.
- Не спрямовуйте External Tool на збірку, яка читає незбережені буфери — спочатку Save.
- Не ставте в прикладах вікі чи README абсолютні шляхи машини.

Щоб заповнити український каталог (або пізніше інші мови): запустіть Gemini Web2API, потім `tools/i18n-translate/run.bat`. У вікні оберіть мови; **Ukrainian увімкнений типово**. Коли в каталозі вже є переклад, мова з’являється в **Language**; назва — з `@language_name` у тому JSON. Відсутні рядки лишаються англійськими.
