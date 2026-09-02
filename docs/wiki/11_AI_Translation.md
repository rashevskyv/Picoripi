# AI Translation

**Language:** English · [Українська](uk/11_AI_Translation.md)

Picoripi talks to LLMs through **Settings → AI Translation**. Glossary builds use **Settings → AI Glossary** (optionally the same key). Recommended local proxy: [5. Gemini Web2API](5_Gemini_Web2API.md).

Handlers: `handlers/translation_handler.py`, `handlers/translation/`. Providers: `core/translation/providers.py`. Defaults: `core/translation/config.py`. Prompts: **Edit Prompts JSON** and plugin `translation_prompts/prompts.json`.

---

## Turn a provider on

**Settings → AI Translation**

| Field | Values |
|-------|--------|
| Target Language | e.g. Ukrainian, Spanish, German |
| Active Provider | Disabled · OpenAI Compatible · Ollama Chat · Gemini · Perplexity |
| Preset | Save Preset / Delete Preset (saving an existing name overwrites it) |
| Parallel Requests | 1–16, default 6. Concurrent requests during batch/chunked translation |
| Test Provider | One tiny request. Disabled while provider is Disabled |

**OpenAI Compatible** (use this for Web2API):

| Field | Notes |
|-------|--------|
| API Key | Bearer token (password field) |
| API Key Env Var | default name `OPENAI_API_KEY` (also loaded from `.env` via `settings_manager`) |
| Endpoint | placeholder includes `https://api.openai.com/v1` or `http://127.0.0.1:8081/v1` |
| Model | placeholder `gpt-4o-mini` or `gemini-3.7-flash` |
| Temperature | 0.0–2.0, default 0.0 |
| Max Output Tokens | 0 = Provider default |
| Request Timeout | 1–600 s, default 60. Use **180 s** with Web2API |

**Ollama Chat API:** Base URL `http://localhost:11434`, Model `llama3`, timeout default 120 s, Keep Alive.

**Google Gemini API:** Base URL optional (`http://127.0.0.1:8081/v1` or empty for Google API), API Key optional for a local proxy, Model `gemini-3.7-flash`.

**Perplexity API:** Bearer token, Base URL `https://api.perplexity.ai`, model placeholder `sonar-medium-8x7b-chat`.

**Edit Prompts JSON** edits the stored templates. For a one-off tweak, Ctrl-click **AI Translate** or **AI Variation** instead.

**Global → Show prompt editor before AI requests** opens the editor on every request.

Default config `provider` is `"disabled"` until you pick one.

---

## Translate in the editor

**AI Translate** (above Editable):

- Click: translate the current string. If a translation already exists in the backup database, that one is reused (no new request).
- Ctrl-click: prompt editor, and **ignore** the stored translation (always re-translate).
- Several strings: select lines in **Strings in block**, right-click (Ctrl-click there too for the prompt editor).
- More than 12 items in one job uses **chunked** translation (`translate_specific_strings`).

If a job is already running: dialog **AI Busy**.

Nothing selected (`physical_block_idx == -1`): the button does nothing.

**AI Variation**:

- Click: alternative wording of the **current translation** (`request_type='variation_list'`; temperature override 0.7).
- Select a fragment in Editable first — only that fragment is rewritten.
- Ctrl-click: prompt editor.
- Pick from **AI Translation Variations**; Refresh / Ctrl-click ignores the in-memory cache.

**AI Chat** (toolbar, `Ctrl+Shift+C`): window **AI Chat**. Discuss translations. Ctrl+Enter / Send sends; Enter is a newline. Optional **Web Search**. Chat does **not** write the Editable pane; copy a suggestion yourself or use **AI Translate**.

Tree empty-space menu: **AI: Translate All Blocks (UA Chronological)** — `translate_all_blocks_chronologically()`.

---

## What goes into the prompt

The engine does **not** hard-code game vocabulary. The plugin may attach (`get_translation_context_for_string`):

| Key | Prompt effect |
|-----|----------------|
| `window_type` | `Window Type: <value>` |
| `content_role` | `Content Role: <value>` |
| `role_instruction` | inserted verbatim (plugin teaches the model its own roles) |
| `has_speaker` | `False` skips speaker lookup |
| `glossary_section` | section for a new term from this line |
| `force_glossary` | line must produce a glossary entry |

Plus speaker (after Merge Speakers), glossary hits, MemePalace scene if built, optional `get_ai_flow_context_for_string` / `get_ai_flow_overview`.

---

## Glossary AI

**Settings → AI Glossary**

| Field | Notes |
|-------|--------|
| Provider | OpenAI Compatible · Ollama · Gemini |
| API Key | |
| Use API key from AI Translation | |
| Model | |
| Text Chunk Size | 1000–32000 characters |
| Parallel Requests | 1–16. Wider than the number of proxy accounts only queues on cooldown |
| Retry Delay | 0–600 s. Server `Retry-After` wins |

Pipeline launch: **Tools → Prepare Glossary…** or wizard step **Prepare and enrich the glossary**. See [8](8_Localization_Pipeline.md).

---

## Parallel Requests

`translation_workers_spin` / `glossary_workers_spin`. Proxies that rotate several accounts (Web2API) can use 4–8. One account: set **1**.

---

## What not to do

- Do not click Translate with Active Provider **Disabled**.
- Do not leave Request Timeout at 60 s on Web2API (proxy retries across accounts).
- Do not assume a reused backup is a fresh model output — Ctrl-click to force.
- Do not start a second Translate while **AI Busy**.
- Do not put API keys or cookies in the wiki, README, or commits. Use Settings or `.env`.
- Do not set Parallel Requests far above Active accounts; extra workers wait on cooldown.
