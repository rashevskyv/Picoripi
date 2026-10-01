# E. Proxy (gemini-web2api) and Picoripi transport path: robustness audit

Scope: `/home/claude/w2a` (proxy) and `/home/claude/pico` (client). Read-only; nothing was run against Google.

**Blind spots.** `gemini_web2api/accounts.py` and `gemini_web2api/dashboard.html` are NOT in the copy, although both are imported/served (`gemini_web2api.py:47,187`, `gemini.py:20`, `server.py:102`). Pacing, `classify`, cooldown ladders, `AccountManager`, and the "WebTOP" UI could not be read. They are inferred from `test_rotation.py`, README and docstrings. `egress_blocks.json` (20 KB) is also absent. It is gitignored runtime state: per-egress-IP strike/pause/ban records, written next to `config.json` (README:356, `test_rotation.py:774-812`). A 20 KB file means dozens of IPs have accumulated bans.

---
## 1. Proxy architecture

**Two parallel implementations (the main structural problem).**
- Monolith `gemini_web2api.py` (1424 lines) is what `run.bat:17` and Picoripi wiki `5_Gemini_Web2API.md` tell users to run.
- Package `gemini_web2api/` (server.py 779, gemini.py 515, tools.py, multimodal.py, models.py, config.py) is what the Dockerfile runs (`Dockerfile:9`). `COPY gemini_web2api/` omits the monolith. `tests/` and `test_rotation.py` import ONLY the package.
- So the code users actually run via `run.bat` is untested. They have drifted:

| Behaviour | Monolith | Package |
|---|---|---|
| Version | 1.3.1 (`:44`) | 1.3.2 (`__init__.py`); pyproject says 1.3.0; walkthrough says 1.3.3 |
| Body `think` / `think_mode` / `reasoning_effort` | **ignored** (`handle_chat` :1044-1120 never reads them) | honoured (`server.py:339-373`) |
| Unknown model | 400 (`:1033`) | silent fallback to default (`models.py` `resolve_model`) |
| Bad `@think=abc` | `int()` ValueError, then 500 (`:1030`) | 400 |
| Invalid JSON body | `json.loads` raises, 500 (`:1045`) | 400 (`server.py:329-332`) |
| Upstream failure | `send_upstream_error`: 429 + Retry-After, or **infinite recursion** (see below) | always 502 `upstream error: ...`, never 429/Retry-After |
| `extract_response_text` | LAST non-empty text (`:631-658`) | LONGEST text (`gemini.py:358-365`) |
| Payload slots / images / tool_choice | 80 slots, no images | 102 slots, multimodal |
| Probe | 60 s, think from model | 15 s, think 0 (`gemini.py:377`) |

- Picoripi's `think` (see `_prepare_body`, providers.py:162-165) is therefore a **silent no-op** against the monolith. The walkthrough's "think levels per task" only works with `python -m gemini_web2api`.

**Bug (monolith).** `send_upstream_error` (`gemini_web2api.py:769-783`): when `wait` is falsy (timeout, 5xx, BardErrorInfo, anything without Retry-After) the `else` branch calls `self.send_upstream_error(e)` again. That is unbounded recursion, then `RecursionError`, then the generic `except` (`:1018-1023`) returns **HTTP 500 "maximum recursion depth exceeded"**. The real error text never reaches Picoripi. README:408 promises 429-or-502; reality is 429-or-500.

**Entry points.** `main()` (`gemini_web2api.py:1351`) and `gemini_web2api/__main__.py:main`. Config loads `--config`, `$GEMINI_WEB2API_CONFIG`, `./config.json`, then `~/.config/gemini-web2api/config.json`. Defaults are in `DEFAULT_CONFIG` (`:56-90`), duplicated in `config.py`. `config.example.json` has 28 keys:
- Network: `port 8081`, `host 0.0.0.0`, `proxy`, `proxy_pool`, `webshare_api_key(s)`, `webshare_refresh_sec`, `webshare_retry_sec`.
- Retry/timeouts: `retry_attempts 3`, `retry_delay_sec 2`, `request_timeout_sec 180`.
- Upstream identity: `gemini_bl`, `auth_user`, `xsrf_token`, `cookie_file`.
- Behaviour: `default_model`, `api_keys ["sk-gemini"]`, `log_requests`, `temporary_chats false`.
- Pacing: `min/max_request_gap_sec 3/20` (per egress IP), `min/max_account_gap_sec 3/20` (per account).
- Captcha: `captcha_open_browser`, `chrome_path`, `captcha_poll_sec`, `captcha_poll_attempts`.
- Egress health: `egress_timeout_pause_sec 300`, `slow_egress_sec 120`, `xsrf_refresh_gap_sec 300`, `startup_check`.
- `requests_per_account` and `ip_block_cooldown_sec` exist only in code defaults.

**Request mapping.**
- `/v1/chat/completions` (`handle_chat`), `/v1/responses` (Codex), `/v1beta/models/*:generateContent`, `/v1/models`.
- `messages_to_prompt` flattens the whole conversation into ONE prompt string with `[System instruction]:` prefixes. Every call is a fresh single-turn Gemini web chat via `StreamGenerate`, with the model chosen by `MODE_CATEGORY` in payload slot 79 and thinking in slot 17.
- No session reuse, so `session_mode`, `conversation_id` and `start_new_chat_session()` in Picoripi (providers.py:441-462, hits non-existent `/api/new-chat`, errors swallowed) do nothing here.
- `temporary_chats` defaults **false**, so every request creates a persistent chat in the Google account's history (`apply_chat_persistence_flags`, `:202-208`). A bulk run leaves thousands of chats. Recommend `true` for batch use (needs a test).

**Account/cookie rotation.**
- `AccountManager` (missing) holds accounts with `status` (active/rate-limited/invalid), cooldown, `strikes`, `proxy`/`proxy_auto`.
- `_next_account` (`:352-364`) calls `pick_account()` round-robin (`requests_per_account=1`). If none is usable it raises `UpstreamError(429, "no usable account: ...; retry in {eta}s", retry_after=eta)`.
- `_penalize` (`:389-448`) classifies each failure:
  - **timeout:** pause the egress for 300 s.
  - **BardErrorInfo 1060:** permanent egress ban.
  - **ip_block** (captcha, 403 robot page): pause the IP and rebind the account to a pool proxy.
  - **blocked** (429/405/400/BardErrorInfo): first try an XSRF refresh, otherwise bench the account.
  - **auth** (login redirect): mark INVALID.
  - **other:** plain retry on the same account.
- 405 triggers an automatic `gemini_bl` refetch.

**`test_rotation.py` is a script of plain-assert functions, not a real test suite.** It has 33 `test_*` functions and a hand-maintained `__main__` runner (`:1280-1323`), and prints "ok ...". It is pytest-collectable but breaks under pytest or on a clean checkout:
- `test_error_summary` reads `failed_generation.html` (`:57`), which is gitignored.
- `test_live` (`:1261`) reads `accounts.json`.
- It monkey-patches module globals (`g.AccountManager = ...`).
- It exercises only the package.

It is, however, good behavioural coverage of rotation/pacing/bench/ban logic. `tests/test_modular_sync.py` has about 26 cases (payload flags, prompt parsing, SSE).

**Rate-limit handling, retries, streaming.**
- `gemini_stream_generate` (`:473-519`) makes `attempts = max(retry_attempts, n_accounts)` tries, each with its own account/egress, `retry_delay_sec` between, up to `request_timeout_sec` (180 s) each. Worst case for one client request with 6 accounts is about 6x(180+pace 20+2) ≈ **20 minutes**.
- **The proxy never detects client disconnect** on the non-stream path. After Picoripi times out and retries, the proxy keeps burning accounts on the abandoned call ("zombie requests"). `_bench_if_slow` (`:367-381`) admits this: "the answer was generated and thrown away".
- Streaming path (`:522-603`) uses httpx when installed. A BardErrorInfo before the first text means retry, after text it is treated as a trailer, and a mid-stream failure after text re-raises with no retry.
- Monolith SSE errors after headers are logged only (`:1085`), so the client sees 200 + truncated stream. In the package, `_handle_chat` (`server.py:391-414`) catches only BrokenPipe, so `do_POST` then writes a 500 JSON into an open SSE stream.

**Size/concurrency limits.**
- No input-size check (`handle_chat` accepts any prompt), no body cap (`_read_request_body` `:855-878`, trusts Content-Length / chunked unbounded).
- Documented OUTPUT ceilings are only in the README model table (~12k chars Flash, ~20k Thinking, ~10k Lite). No input limit is documented anywhere.
- `finish_reason` is always `"stop"` and `usage` is `len//4` (fake, wrong for Cyrillic), so truncation is undetectable by the client.
- Concurrency: `ThreadingMixIn` with unbounded daemon threads (`:1379`). The real cap is implicit pacing: each thread sleeps in `_pace()` 3-20 s per account/IP. N accounts therefore give about N/11 requests/s at best (README measured 6 requests in 6.9 s on 6 accounts). A 7th concurrent request queues server-side while the client's read timeout runs.
- The f.req body is `json.dumps` (ensure_ascii default) applied twice (`gemini.py:286-287`, monolith `:301-302`), so each Cyrillic char costs about 11 bytes on the wire. Inflates bodies about 2x versus raw UTF-8; test `ensure_ascii=False` (P2).

**WebTOP dashboard.** Served at `/` (when `Accept: text/html`) and `/dashboard`; UI over `/api/accounts/*` and `/api/proxy/*` (add/delete/test/set_proxy/import_local/toggle_rotate, pool status, Webshare key rotate). **`/api/*` is unauthenticated** (auth only for `/v1*`, `:813,882`), with CORS `*`, default `host 0.0.0.0`, and `/api/debug_headers` echoing headers: any LAN host or web page can list/add/delete accounts.

**HTTP status matrix (monolith vs package).**

| Status | When |
|---|---|
| 200 | success; also truncated SSE (see above) |
| 204 | OPTIONS |
| 400 | bad chunked body; unknown model (monolith only); empty prompt; missing cookie/id; package: bad JSON, bad `@think` |
| 401 | `/v1*` with wrong key |
| 404 | unknown path; account not found |
| 429 + Retry-After | monolith only: no usable egress / captcha. Header only when wait > 0 |
| 500 | monolith: invalid JSON body, `@think=x`, recursion bug above, any unhandled exception |
| 502 | package: ALL upstream failures incl. "no usable account" (429 semantics lost); image upload failure |

**Logging.** stderr only, unstructured, gated by `log_requests`; lines carry account/egress/model/chars/timing. No request id, no metrics, **no health endpoint** (`GET /` returns static `{"status":"ok"}`).

**Code quality.** Monolith duplicates ~70% of the package; `merge=ours` in `.gitattributes` blocks upstream fixes; duplicated `_serve_dashboard`/`load_cookie`/`probe_account`, bare `except:` (`:894,914,1022`), `AccountManager()` built per request. No tests for SSE, status mapping, auth, or the monolith.

---
## 2. Picoripi client side

**Provider layer (`core/translation/providers.py`).**
- `OpenAIProvider.translate` (:177-286): `requests.post(..., timeout=_split_timeout(...))`. For `localhost`/`127.0.0.1` only, connect timeout is min(10, read) (:104-110), so a dead proxy fails in 10 s. A LAN or hostname proxy gets the full read timeout as connect timeout.
- Default timeout is **60 s** (`_extract_timeout` default :113, config.py:13, UI spin `ai_mixin.py:101-103`). Gemini/Ollama default 120.
- No `Session`, no retry, no backoff inside the provider.
- On `Timeout` it raises with `retry_after = 15.0` (:206-209), which nothing consumes.
- `RequestException` becomes `provider_error("API request failed: {e} - {body[:200]}")` carrying Retry-After (header, or regex `retry after Ns` in message/body, :16-54). This only matches the monolith's captcha message; the package's "retry in 30s" does not match.
- Empty `choices` returns `ProviderResponse(text=None)` (:266), a **silent empty success**. Non-JSON 200 raises `TranslationProviderError` (:263).
- `_prepare_body` sends **`think`/`think_mode` to every OpenAI-style endpoint** (:162-165; the worker injects `think` in nearly every task, e.g. run_mixin.py:192, 279, 563, 721-725). Real OpenAI/Perplexity reject unknown top-level params with 400 (I believe; verify). It should be sent only to a Web2API-flagged provider.
- `GeminiProvider` compat path (:533-577): calls `response.json()` and `raise_for_status()` with no wrapping (:552-553), so a non-JSON body is a raw `ValueError`. It does not send `think`, so `think` is dropped on this documented Web2API route (wiki says "OpenAI Compatible or Gemini with Base URL"). Native path puts `?key=` in the URL (:581) and `API request failed: {e}` embeds the URL, **leaking the API key into logs/UI** (:490, 524). The native stream parser matches lines starting `"text":` (:631), which is brittle.
- `_active_stream_response` is a single slot per provider instance (:72, 85-87), only safe because a provider is used by one stream at a time. A provider is **shared across the ThreadPool threads** in chunked translation, but only for non-stream `translate()`, which keeps no mutable state. OK today, fragile if streaming is ever parallelised.
- `gemini/` (top-level, 540-line `providers.py` etc.) is a stale full copy of the app with no Retry-After and no timeout split. Nothing outside it imports it, but `plan.md` lists it as maintained.

**Three retry regimes (no single policy).**
1. **Block/batch translation** (`translate_block_chunked`, `run_mixin.py:224-544`, `ai_lifecycle_manager.py:216-317`). The worker has **no retry**. On ANY failure it emits `error`, then `_handle_task_error` shows a modal: timeout asks "wait longer and retry?", anything else shows a "(Debug)" dialog with "Retry (Wait 3s)" / "Stop". `max_retries` is 4 (translate_mixin), a fixed 3 s delay, a human click each time. `Retry-After` is **never read** here (grep: only `core/glossary_build/parallel.py` consumes it). The wiki's recommendation 6 ("Picoripi honors Retry-After") holds only for glossary builds. Retrying a captcha-blocked proxy every 3 s is exactly what the proxy docs warn extends the block.
2. **Glossary pipeline** (`core/glossary_build/parallel.py`, `glossary_pipeline_worker.py`). Good design: rolling window of N workers, failure-as-data, no per-unit retry loop, one retry pass on 2 workers after `Retry-After` or 60 s, `max_consecutive_failures` stops a dead backend (worker default 3, handler default 5, inconsistent). Timeout floor is 180 s (`glossary_pipeline_worker.py:76`, `glossary_pipeline_handler.py:190-199`).
3. **Single-string / variations / manual glossary**: `max_retries 1` for most, or via the modal above.
- **Dead code:** `core/glossary_build/retry.py` (`is_transient`, `call_with_retry`, text-based classification) and `concurrency.py` (`AIMDWindow`) are referenced only by their own tests. The classification work in `retry.py` is reusable for P0.

**Parallelism vs proxy capacity.** Default `workers = 6` everywhere (config.py:26, global_settings.py:71, ai_mixin.py:66, `batch_translator.py:275`), range 1-16, regardless of provider. The wiki says "4-8 if several accounts; 1 if one". Proxy real capacity = number of ACTIVE accounts, with pace 3-20 s each, so 6 workers on 1-2 accounts queue inside the proxy: the k-th request waits about k×11 s plus generation (3-25 s), already near 60-90 s. Block translation hard-codes `block_timeout = 180` in 7 places (translate_mixin.py:85,275,326,378,473,556,755) and always overrides a larger user setting. Single-string tasks use the 60 s default.
- **Verdict on 60 vs 180:** 60 is NOT sane for Web2API (pace + up to 3 internal retries), and the wiki already says so. But 180 is also marginal given the proxy's own `request_timeout_sec 180` per attempt: Picoripi gives up exactly when the proxy's first attempt would time out, never seeing the rotation result. Better default: provider-aware 120-180 client timeout with a **total** deadline, plus a proxy that fails fast.
- Parallel path bug (`run_mixin.py:416-436`): on the first chunk failure it does `error.emit(...)` and `return` inside `with ThreadPoolExecutor`. `__exit__` waits for ALL queued futures, so remaining chunks keep calling the proxy (quota burn), their results are discarded, and `finished` fires late. Cancellation has the same shape (`break` inside `with`). In-flight non-stream requests are not abortable.
- Cancellation: `AIWorker.cancel()` (control_mixin.py) only closes an active **stream** (`cancel_active_stream`). Non-stream `requests.post` runs until completion/timeout (up to 180 s). `AIStatusDialog` honestly says "will stop after the active network step". `safe_shutdown_thread` waits 1000 ms, and `allow_terminate` is false, so on dialog close a still-running thread is left with `deleteLater()` (risk of "QThread destroyed while running"). The proxy meanwhile keeps working on the abandoned request.
- Thread-safety otherwise: `provider_override` dict and `task_details` shared read-only across threads (fine); `self._last_messages` raced (benign); **`ai_traffic.log` has no lock** (`logging_utils.py:214-267`), so parallel entries interleave, with no request id/chunk id/timing to correlate request and response. It also truncates the file at task start in cwd (`run_mixin.py:27-37`), which wipes a previous run's evidence, and double-writes full prompts into `app_debug.txt`.

**JSON handling: three divergent cleaners.**
- `AIWorkerJsonMixin._clean_json_response` (json_mixin.py:49-77), `AILifecycleManager._clean_model_output` (:334+), `glossary_build/ai_adapters.parse_json_array/object` (:24-81). I reproduced the first against test inputs:
  - `[{"a":1},{"b":2}]` (unfenced array) becomes `{"a":1},{"b":2}` (brackets stripped, invalid, `JSONDecodeError`). `[{"a":1}]` becomes the bare object.
  - Trailing prose containing `{note}` is swallowed into the slice, invalid.
  - Fenced JSON with ``` inside a string is cut at the inner fence (non-greedy regex).
  - Trailing comma is handled and string-aware. Good.
- In the legacy `build_glossary` task (`run_mixin.py:194-199`) a non-list result is only `log_debug`'d and the chunk **silently dropped**. `ai_adapters.parse_json_array` returns `[]` on any garbage (silent drop of a chunk's terms) and never repairs trailing commas. `_description_from_reply` falls back to raw reply text, so chatter becomes a glossary description.

---
## 3. Failure matrix (what Picoripi does today)

| Failure | Block translation | Glossary pipeline | Single/chat |
|---|---|---|---|
| Proxy down (ConnectionError) | `provider_error` "API request failed..." (providers.py:210-213), `worker.error`, debug modal, user retries every 3 s | unit failure; after 3-5 in a row run stops "AI backend not responding" (`pipeline_coordinator.py:192`); then 60 s retry pass | error text; chat adds "Diagnosis" (`ai_chat_handler.py:493-499`, string match) |
| Cookie expired / account INVALID | proxy rotates; if all dead monolith emits 429 "out of quota" (misleading) or 500; same modal | same | same |
| 429 / quota / captcha | Retry-After parsed but **ignored**; modal 3 s retry | honoured: waits Retry-After, 2-worker retry pass | surfaced |
| Slow > timeout | `Timeout` becomes `TranslationProviderError`, `is_timeout` string-match `'timed out'` (lifecycle:259), "wait longer?" modal; proxy still working (zombie) | unit failure, retry pass | same |
| Truncated output | invalid JSON, `JSONDecodeError`, modal retry whole chunk; no smaller chunk | brace-balancer fails, `[]`, **silent drop** | shown as is |
| Markdown fences | stripped by regex | stripped | n/a |
| Non-JSON chatter | brace slice; works for objects, breaks on arrays/extra braces | `_first_json` balanced, OK | n/a |
| Empty response | provider returns `text=None`; `json.loads('')` raises, error (translate); glossary: `""` becomes `[]` silent | silent empty | `ProviderResponse(None)` |
| Item count mismatch | `ValueError` for whole 12-item chunk, retry whole chunk | n/a | n/a |
| Reordered ids | **positional mapping wins; model `id` only a fallback** (`batch_translator.py:429-458`), so a reordered reply silently mis-assigns translations | n/a | n/a |
| Unicode | `ensure_ascii=False` on client side (OK); proxy over-escapes; no known issue | same | same |

Partial-success loss: one bad line (layout contract, `validate_translation_layout`) rejects the whole 12-item chunk (`_validate_chunk_result`, run_mixin.py:306-350); no per-item salvage or bisect.

---
## 4. Token/length discipline

- Picoripi has **no knowledge of the proxy's context or output limit**. Glossary chunk presets are 2000/4000/8000 chars (`text_sweep.py:23`); legacy build is 8000 (range 1000-32000, `ai_mixin.py:170-176`). Block chunks are a fixed 12 items (`run_mixin.py:266`). Nothing relates these to the ~10-20k char output ceiling, and there is no input estimate.
- No adaptation on failure (no halving of chunk on JSON/truncation errors). `AIMDWindow` adapts concurrency but is unused.
- No request-size or latency metrics: `log_info` records only endpoint/timeout/status code (providers.py:202-204). `ai_traffic.log` has full text but no sizes/durations. `max_output_tokens` is optional and meaningless for Web2API.

---
## 5. Proposals

### P0-1 `TransportPolicy` (one retry/timeout/classification module)
- **Files:** new `core/translation/transport.py`; use from `providers.py`, `run_mixin.py`, `ai_lifecycle_manager.py`, `glossary_build/parallel.py`; delete the unused `retry.py`/`concurrency.py` after moving `is_transient` logic.
- **Sketch:**
  - `class ErrorKind(Enum): CONNECT, TIMEOUT, RATE_LIMIT, SERVER, AUTH, BAD_REQUEST, PARSE, EMPTY, CANCELLED`.
  - `class TransportError(TranslationProviderError)` with `kind`, `status`, `retry_after`, `retryable`, `raw_text`.
  - `classify(exc|response) -> TransportError`: map `requests` exceptions and status (400/401/403/404/405/422 fatal; 408/425/429/5xx and Timeout/ConnectionError retryable), parse Retry-After header plus both "Retry after Ns"/"retry in Ns" regexes.
  - `@dataclass TransportPolicy(timeout, connect_timeout=10, max_attempts=3, base=2, cap=60, jitter=0.5, total_deadline=...)` with `run(fn, is_cancelled)` doing exponential backoff + full jitter, always honouring `retry_after`.
  - Per-provider concurrency cap (semaphore) and a **circuit breaker**: after K consecutive retryable failures, open for `retry_after or cooldown`, fail fast with `kind=RATE_LIMIT`.
- **Wire-up:** `OpenAIProvider.translate` wraps the post in `policy.run`. Block translation stops showing the "Debug" modal for retryable kinds and shows it only after policy exhaustion. Fix `GeminiProvider._translate_via_openai_compat` to use the same path (wrap `response.json()`, pass `think`). Strip `?key=` from error strings.
- **Risk:** medium: changes user-visible retry flow; keep the modal on exhaustion. Retry count × the proxy's internal retries multiplies load, so default `max_attempts=2` for Web2API (the proxy already rotates).
- **Tests:** table-driven `classify` (statuses, Retry-After header, regex messages), fake-clock backoff, breaker open/close; reuse the cases in `tests/test_core/test_glossary_retry.py`.

### P0-2 Robust JSON extraction utility
- **Files:** new `utils/json_extract.py` (`extract_json(text, expect="object"|"array"|"any") -> (value, repair_notes)`); replace `_clean_json_response`, `_clean_model_output`, `ai_adapters.parse_json_*`.
- **Sketch:**
  - Strip BOM/zero-width chars.
  - Try the whole text.
  - Try each fenced block (greedy to the LAST closing fence, not first).
  - Else scan with a string-aware balanced matcher for the first complete `{...}` or `[...]` of the requested type.
  - Repair: trailing commas, smart quotes only outside strings, unescaped raw newlines inside strings, truncated tail (close open string/brackets, flagged `truncated=True`).
  - Raise `ParseError(kind=PARSE, raw_text)` instead of returning `[]`/`""`.
  - Callers must handle `truncated`/`ParseError` explicitly: no silent drop.
- **Tests:** property-style table including every case reproduced above (unfenced array, array of 1, trailing `{note}`, ``` inside string, trailing comma in string "привіт, }", truncated output, BOM, empty).
- **Risk:** low-medium: behaviour change where `[]` used to be silently accepted. Gate: log + count `parse_failures` per run.

### P0-3 Fix the parallel-chunk error path and id mapping (`run_mixin.py`, `batch_translator.py`)
- **Sketch:**
  - Replace the `with ThreadPoolExecutor` + `return` pattern with `core/glossary_build/parallel.run_pool` (already handles window/cancel/failure-as-data). On first fatal error or `max_consecutive_failures`, stop submitting and `shutdown(cancel_futures=True)`.
  - Never emit one global error that kills a block when only one chunk failed: report failed chunk indexes and keep the completed chunks (`chunks_to_skip` already supports resume).
  - In `handle_chunk_translated` map by `id` first and verify it equals the positional id; on mismatch, mark the chunk invalid instead of silently trusting position.
- **Tests:** fake provider failing on chunk 3 of 8 asserts 7 results applied and no calls after stop; reordered ids assert rejection.

### P1-1 Provider-aware defaults and `think`
- Add a provider field `profile: "web2api" | "openai" | "ollama"` (auto-detect from `localhost:8081`/`/v1/models` response `owned_by:google`).
- Web2API profile: timeout 180 (single source of truth; replace the 7 hard-coded 180s with `policy.timeout`), workers = `min(user, active_accounts)`, send `think`, `temperature` irrelevant. OpenAI profile: never send `think`.
- Files: providers.py `_prepare_body`, config.py, `translate_mixin.py`. **Risk:** low. **Test:** body-builder unit tests per profile.

### P1-2 Health endpoint + real "Test Provider"
- **Proxy:** add `GET /healthz` returning `{status, version, accounts:{active,rate_limited,invalid}, egress:{usable,paused,banned}, retry_after, inflight}` without calling Google; add `GET /api/health?probe=1` for one real `probe_account`.
- **Picoripi:** `ProviderTestWorker` (provider_worker.py:20-39) first calls `/healthz` when the URL is Web2API, shows accounts/active count, then sends the tiny prompt; use the active-account count to clamp `workers` and display a hint.
- **Risk:** low. **Test:** `http.server` fake with canned health JSON.

### P1-3 Chunk-size adaptation and size/latency metrics
- On `PARSE`(truncated) or `EMPTY` failure, bisect the chunk (12 -> 6 -> 3 -> 1 items; glossary chunk halves down to 1000 chars) before surfacing; per-item salvage for layout errors (accept valid items, retry only invalid ones).
- Log per request: request id (uuid4 short), chunk idx, chars in/out, duration, attempt, kind, status, to `ai_traffic.log` as JSONL (with a lock and size cap), plus a run summary (p50/p95 latency, failures by kind). Cap `ai_traffic.log` rotation instead of truncating.
- **Risk:** medium (more calls on failure; bound by a total attempt budget). **Test:** fake provider returning truncated JSON for n>6 items.

### P1-4 Cancellation of non-stream requests
- Use a per-request `requests.Session` registered on the worker; `cancel()` closes the session/socket (`session.close()` aborts in-flight reads for most adapters) or use `stream=True` with a cancel flag checked while reading. `safe_shutdown_thread`: wait longer for network-bound workers and never `deleteLater` a running QThread.
- **Risk:** medium (Qt lifecycle). **Test:** local `http.server` that sleeps 5 s, cancel at 0.5 s, assert return < 1 s.

### P2 Picoripi misc
Delete stale `gemini/`, `retry.py`, `concurrency.py`; unify `max_consecutive_failures` (3 vs 5); make the wiki's Retry-After claim true via P0-1; test `ensure_ascii=False` in the proxy payload.

### Proxy improvements (ranked)
1. **One implementation.** Make `gemini_web2api.py` a 5-line shim: `from gemini_web2api.__main__ import main`. Update `run.bat` to `python -m gemini_web2api`. Port monolith-only behaviour (429 + Retry-After) into the package: add `send_upstream_error` to `server.py` and map `UpstreamError(429)` to 429 with `Retry-After`, others to 502 with a stable `error.type`/`code` (`rate_limited`, `no_account`, `upstream_timeout`, `upstream_blocked`). Fixes the recursion/500 bug and the think-ignored drift in one move. **Risk:** low-medium. **Test:** extend `tests/test_modular_sync.py` with a stub `generate` raising each `UpstreamError` and assert status/headers.
2. **Detect client disconnect and cap total time.** Pass an `abort` callable (poll `select` on the client socket) to the retry loop; add `total_deadline_sec` (default = client-visible 170 s) so worst-case 20 min zombie retries stop. **Test:** fake slow `post_no_redirect`.
3. **Real concurrency gate.** `threading.BoundedSemaphore(n_active_accounts)` plus a bounded wait queue; answer `429 Retry-After` immediately when the queue wait would exceed X s rather than hanging clients. Expose `inflight`/`queued` in `/healthz`.
4. **Lock down `/api/*` and the bind.** Require `api_keys` on `/api/*`, default `host` to `127.0.0.1`, drop `Access-Control-Allow-Origin: *` on `/api/*`, remove `/api/debug_headers`. Add `Content-Length` cap (e.g. 2 MB). **Risk:** low (dashboard JS needs to send the key). Also: `temporary_chats` default true for bulk runs, and truthful `finish_reason` (`length` if reply hits the documented ceiling).
5. Tests: convert `test_rotation.py` to pytest with tmp_path fixtures (no gitignored files, `test_live` behind a marker), and commit `accounts.py`/`dashboard.html` into the audited tree.
