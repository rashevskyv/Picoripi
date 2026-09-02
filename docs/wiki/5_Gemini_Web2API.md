# Gemini Web2API (WebTOP)

**Language:** English · [Українська](uk/5_Gemini_Web2API.md)

Gemini Web2API is the **local proxy** Picoripi uses for glossary builds and bulk translation. It turns a signed-in [Gemini](https://gemini.google.com) browser session into an OpenAI-compatible HTTP API. Picoripi never talks to Google’s billed Gemini API unless you deliberately leave the Base URL empty and paste a Google API key.

The proxy’s browser dashboard (account list, rotation, cooldowns) is the **WebTOP**. Open it at `http://127.0.0.1:8081/` while the proxy is running.

The proxy lives in a **separate repository** (`gemini-web2api`). Picoripi only consumes `http://127.0.0.1:8081/v1`.

---

## Why it sits in the pipeline

Glossary sweep, describe, translate-variants, and block translation send **many** LLM calls. A single Google API key rate-limits quickly. Web2API rotates **several Gemini web accounts** (and optional per-account proxies) so Parallel Requests in Picoripi can stay above 1 without dying on HTTP 429.

If the proxy is down, Picoripi’s Test Provider / glossary / translate will fail with a connection error. Start Web2API **before** a long glossary or translation run.

---

## Start the proxy

From the `gemini-web2api` checkout:

```bat
run.bat
```

or:

```powershell
python gemini_web2api.py
```

Default listen address: `http://127.0.0.1:8081`. OpenAI-style routes live under `/v1`.

Confirm:

```powershell
curl.exe http://127.0.0.1:8081/v1/models
```

Then open **WebTOP**: [http://127.0.0.1:8081/](http://127.0.0.1:8081/) (or `/dashboard`).

On WebTOP you can:

- See each account as Active / Rate Limited / Invalid, with cooldown timers
- Switch the live account by hand
- Test a connection
- Turn auto-rotation on 429 on or off
- Add accounts: **Launch Browser for Login**, bookmarklet, or paste a session

Keep at least one **Active** account before starting a Picoripi batch.

---

## Turn it on inside Picoripi

**Settings → AI Translation** (`File → Settings…` / `Ctrl+P`, AI Translation tab).

Recommended preset for Web2API:

| Field | Value |
|-------|--------|
| Active Provider | **OpenAI Compatible** (or **Gemini** with Base URL set) |
| Endpoint / Base URL | `http://127.0.0.1:8081/v1` |
| API Key | any dummy string if the proxy has no `api_keys`; otherwise a key from the proxy `config.json` |
| Model | `gemini-3.7-flash` (or `gemini-3.5-flash-thinking` when you need long output) |
| Temperature | `0.0`–`0.3` for glossary and in-game text |
| Request Timeout | **180 s** (the proxy retries across accounts; 60 s is too short) |
| Parallel Requests | **4–8** if several Active accounts; **1** if you only have one account |

Save it as a named preset (e.g. `Gemini Web2API`).

**Glossary** uses the same credentials when “use the AI Translation key” is on (Settings → AI Glossary). The glossary pipeline already raises timeout to at least 180 s when the translation timeout is smaller.

**Test Provider** on the AI Translation tab sends one tiny request. Green means Picoripi can reach Web2API.

---

## Recommendations

1. **Start Web2API first**, then Picoripi. The dashboard must show at least one Active account.
2. **Do not point Parallel Requests higher than the number of healthy accounts.** Extra workers only stack 429s.
3. Prefer **OpenAI Compatible + `/v1`** over native Google Gemini unless you really want Google’s paid API.
4. For glossary / bulk translation use **Flash**. Use thinking models only when a single string needs a long reasoned pass.
5. If Test Provider fails: confirm `run.bat` is still running, the port is 8081, and WebTOP shows Active — not Rate Limited.
6. After a 429 wave, wait for cooldowns on WebTOP; Picoripi honors `Retry-After` from the proxy.
7. Cookie / XSRF refresh belongs in Web2API (dashboard login or cookie-sync extension), not in Picoripi settings.

---

## What Picoripi does not do

- It does not start or update `gemini-web2api` for you.
- It does not store Google cookies. Those stay in the proxy’s `accounts.json` / browser profiles.
- It does not replace ChatMock. ChatMock is the ChatGPT-web equivalent; see `docs/chatmock_setup.md`. Web2API is the Gemini-web equivalent.

---

## Related code (for maintainers)

- Settings UI: `ui/settings/ai_mixin.py` (`Parallel Requests`, Gemini Base URL placeholder `http://127.0.0.1:8081/v1`)
- HTTP client: `core/translation/providers.py` (Retry-After, local-proxy connect timeout)
- Glossary timeout floor: `handlers/translation/glossary_pipeline_handler.py`
