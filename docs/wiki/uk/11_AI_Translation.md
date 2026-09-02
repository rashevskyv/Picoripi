# AI-переклад

**Мова:** [English](../11_AI_Translation.md) · Українська

Picoripi розмовляє з LLM через **Settings → AI Translation**. Збірка глосарія — **Settings → AI Glossary** (опційно той самий ключ). Рекомендований локальний проксі: [5. Gemini Web2API](5_Gemini_Web2API.md).

Обробники: `handlers/translation_handler.py`, `handlers/translation/`. Провайдери: `core/translation/providers.py`. Типові значення: `core/translation/config.py`. Промпти: **Edit Prompts JSON** і `translation_prompts/prompts.json` плагіна.

---

## Увімкнути провайдера

**Settings → AI Translation**

| Поле | Значення |
|------|----------|
| Target Language | напр. Ukrainian, Spanish, German |
| Active Provider | Disabled · OpenAI Compatible · Ollama Chat · Gemini · Perplexity |
| Preset | Save Preset / Delete Preset (збереження з наявним ім’ям перезаписує) |
| Parallel Requests | 1–16, типово 6. Паралельні запити під час пакетного/чанкованого перекладу |
| Test Provider | Один крихітний запит. Неактивне, поки провайдер Disabled |

**OpenAI Compatible** (для Web2API):

| Поле | Нотатки |
|------|---------|
| API Key | Bearer-токен (поле пароля) |
| API Key Env Var | типове ім’я `OPENAI_API_KEY` (також з `.env` через `settings_manager`) |
| Endpoint | плейсхолдер містить `https://api.openai.com/v1` або `http://127.0.0.1:8081/v1` |
| Model | плейсхолдер `gpt-4o-mini` або `gemini-3.7-flash` |
| Temperature | 0.0–2.0, типово 0.0 |
| Max Output Tokens | 0 = Provider default |
| Request Timeout | 1–600 с, типово 60. З Web2API ставте **180 s** |

**Ollama Chat API:** Base URL `http://localhost:11434`, Model `llama3`, таймаут типово 120 с, Keep Alive.

**Google Gemini API:** Base URL необов’язковий (`http://127.0.0.1:8081/v1` або порожньо для API Google), API Key необов’язковий для локального проксі, Model `gemini-3.7-flash`.

**Perplexity API:** Bearer-токен, Base URL `https://api.perplexity.ai`, плейсхолдер моделі `sonar-medium-8x7b-chat`.

**Edit Prompts JSON** редагує збережені шаблони. Для разової правки Ctrl-клік **AI Translate** або **AI Variation**.

**Global → Show prompt editor before AI requests** відкриває редактор на кожному запиті.

Типовий конфіг `provider` — `"disabled"`, поки не виберете.

---

## Переклад у редакторі

**AI Translate** (над Editable):

- Клік: перекласти поточний рядок. Якщо переклад уже є в базі бекапів — бере його (без нового запиту).
- Ctrl-клік: редактор промпта і **ігнор** збереженого перекладу (завжди новий запит).
- Кілька рядків: виділіть у **Strings in block**, правий клік (там теж Ctrl-клік для редактора промпта).
- Понад 12 елементів в одній задачі йде **чанкованим** перекладом (`translate_specific_strings`).

Якщо вже йде задача: діалог **AI Busy**.

Нічого не вибрано (`physical_block_idx == -1`): кнопка нічого не робить.

**AI Variation**:

- Клік: інше формулювання **поточного перекладу** (`request_type='variation_list'`; температура 0.7).
- Спочатку виділіть фрагмент в Editable — перепише лише його.
- Ctrl-клік: редактор промпта.
- Вибір з **AI Translation Variations**; Refresh / Ctrl-клік ігнорує кеш у пам’яті.

**AI Chat** (тулбар, `Ctrl+Shift+C`): вікно **AI Chat**. Обговорити переклади. Ctrl+Enter / Send надсилає; Enter — новий рядок. Опційно **Web Search**. Чат **не** пише в Editable; скопіюйте пропозицію самі або скористайтесь **AI Translate**.

Меню порожнього місця в дереві: **AI: Translate All Blocks (UA Chronological)** — `translate_all_blocks_chronologically()`.

---

## Що потрапляє в промпт

Рушій **не** хардкодить словник гри. Плагін може додати (`get_translation_context_for_string`):

| Ключ | Ефект у промпті |
|------|-----------------|
| `window_type` | `Window Type: <value>` |
| `content_role` | `Content Role: <value>` |
| `role_instruction` | вставляється дослівно (плагін сам учить модель свої ролі) |
| `has_speaker` | `False` пропускає пошук спікера |
| `glossary_section` | секція для нового терміна з цього рядка |
| `force_glossary` | рядок мусить дати запис глосарія |

Плюс спікер (після Merge Speakers), входження глосарія, сцена MemePalace якщо зібрана, опційно `get_ai_flow_context_for_string` / `get_ai_flow_overview`.

---

## AI глосарія

**Settings → AI Glossary**

| Поле | Нотатки |
|------|---------|
| Provider | OpenAI Compatible · Ollama · Gemini |
| API Key | |
| Use API key from AI Translation | |
| Model | |
| Text Chunk Size | 1000–32000 символів |
| Parallel Requests | 1–16. Ширше за кількість акаунтів проксі лише ставить зайве в чергу на кулдаун |
| Retry Delay | 0–600 с. Серверний `Retry-After` перемагає |

Запуск пайплайну: **Tools → Prepare Glossary…** або крок майстра **Prepare and enrich the glossary**. Див. [8](8_Localization_Pipeline.md).

---

## Parallel Requests

`translation_workers_spin` / `glossary_workers_spin`. Проксі з ротацією кількох акаунтів (Web2API) можуть 4–8. Один акаунт: ставте **1**.

---

## Чого не робити

- Не тисніть Translate з Active Provider **Disabled**.
- Не лишайте Request Timeout 60 с на Web2API (проксі ретраїть по акаунтах).
- Не вважайте повторно використаний бекап свіжим виводом моделі — Ctrl-клік, щоб форсувати.
- Не запускайте другий Translate, поки **AI Busy**.
- Не кладіть ключі API чи cookies у вікі, README чи коміти. Settings або `.env`.
- Не ставте Parallel Requests набагато вище за Active-акаунти; зайві воркери чекають кулдаун.
