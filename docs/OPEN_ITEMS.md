---
status: current
updated: 2026-10-03
owns: unfinished work
tokens: 8.1k
purpose: Everything left open, one line each, by work package
---
# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Font editor formats (branch `feat/font-formats`, 2026-10-03)

- **Merge order:** the `font_sources.json` files of `zelda_oot64`, `zelda_mm64`, `zelda_hwde`, `zelda_totk` and
  `zelda_tww` (and `zelda_hwde/translation_map.json`) sit in folders that only the other branches fill;
  `plugins/common/n64_rom.py` is a byte-identical copy of the `feat/zelda64` file.
- **N64 widths do not reach the checks yet:** `Zelda64Rules.calculate_string_width_override` reads its own
  `FONT_WIDTHS`; after the merge it should take `font_map` widths when given (the editor writes
  `oot_font.json` / `mm_font.json`). Ukrainian on N64 still needs the user's slot decision and an encoder map.
- Nothing edited has run in a game or emulator: an N64 ROM with a redrawn glyph, a HWDE `font_eu.g1t` in the
  LayeredFS mod, a TotK font.
- TotK: no real font on disk; BFFNT was verified on Cadence of Hyrule and Pokémon SV (Switch, BC4). Its
  `Font/*.bfarc.zs` needs the TotK plugin's SARC container (registered when that plugin is active) and the
  project pointing at the romfs (or `Mals`). Texture formats other than BC4 open empty (widths only).
- BFFNT: the character map (CMAP) and the kerning table are kept, not edited; a glyph with no character
  cannot get one (the translation map assigns letters to existing glyphs).
- HWDE: widths are measured from the ink (+4 px) — whether the game has its own table is unknown; edited
  widths live in the project's `font_maps/hwde_eu.json`. The `../romfs/...` candidate assumes the
  workspace layout `source/` next to `romfs/` and a translation folder named `romfs`.
- Opening a font and listing archive members still reads the archive on the UI thread (small files);
  the old BFN paths (`load_bfn`, saving a BFN) are synchronous as before.
- Next formats: 3DS BCFNT (CIAs still encrypted), Tingle Tuner (GBA), Cadence of Hyrule (its BFFNT already
  opens), Wii U BFFNT (big endian, GX2 tiling).

## Review-queue test gaps (agent work; `docs/REVIEW_QUEUE.md` keeps only owner items)

- Real-window tests for single-string translation, variation and the legacy build (the attempt hung on
  teardown); the same for global hotkeys (Alt+Shift+…).
- WP5: a test that reads `settings/effective.json`; selecting a generated plugin (`tools/new_plugin.py`) in the
  real window (5.4).
- `run.bat` itself and `test_all.ps1` (WP7); `tasks.py run` is covered by `test_rq_wp078_app_start.py`.

## Found by the review tests (2026-10-03, not fixed)

- Watch: `tests/test_review/test_rq_wp2_4_run.py::test_a_single_string_request_shows_the_translation_memory_and_a_variation_request_does_not`
  crashed its xdist worker once under `-n 8` (2026-10-03); passed alone and in four parallel reruns.
- `zelda_mc` and `zelda_ww` ship a `glossary.md` that nothing reads.
- ChatMock on loopback is taken for the `web2api` profile (sends `think`, 180 s timeout); there is no UI for
  the profile.
- A settings file saved from the Ukrainian interface may hold `"provider": "вимкнено"` (the provider ids went
  through `tr()` until 2026-10-03); it loads as an unknown provider.

## Hyrule Warriors DE plugin (`plugins/zelda_hwde`, 2026-10-03)

- Owner decision: the font. `font_eu.g1t` / `font_eu_p.g1t` are cp1252 glyph grids without Cyrillic; the
  plugin writes Ukrainian into the cp1251 slots, so the atlas must be redrawn there (no font builder yet).
- Owner decision: also write the translation into the English-EU section (default, `MIRROR_SECTIONS`)?
  Other languages stay as they are.
- Not verified in the game: the mod has not run on a Switch or an emulator; the glyph advance widths
  (`fonts/hwde_eu.json` is measured ink + 4 px) and where the game keeps them are unknown.
- Voice-line speakers for character ids 18-99 are `chara_NNN` (the names table disagrees there); event and
  movie scene ids are not tied to story chapters; text inside textures (`ui/caption`, `still_*`) and the
  executable is not covered.

## Carried over from the 2026 H1 audit (`docs/history/AUDIT-2026-H1.md`)

- UI command "Create plugin from template" (copy `plugins/default_plugin`, rename, open the prompt file).
  WP5.4 delivers the generator (`tools/new_plugin.py`); the menu entry is still unplanned.

## Found during WP8 (the proxy, `D:\git\dev\gemini-web2api`)

- **Nothing in proxy 1.4.0 has met Google.** Tests stub Gemini. Unverified against the real service: the
  `f.req` body with raw UTF-8 instead of escaped text (it is what a browser sends, but it was not tried),
  temporary chats as the default, the 170 s deadline and the gate under real load.
- **`/api/proxy/status` returns the Webshare keys in clear text** (`key` next to `masked`). It is behind the
  API key now; the dashboard only needs the masked form.
- **`README_CN.md` of the proxy is not updated** for 1.4.0.
- **Monolith behaviour that was not ported (8.1):** an unknown model name was a `400` (the package falls back
  to the default model and logs it); the answer was the LAST non-empty text of the reply (the package takes
  the LONGEST). The package's behaviour is what the Docker image always ran.
- **`/v1/responses` still reports `status: "completed"`** for an answer cut at the output ceiling; only
  `/v1/chat/completions` and the Google endpoints tell (`finish_reason: length` / `MAX_TOKENS`).
- **The client-disconnect check runs between attempts**, not during one: an attempt already waiting on Gemini
  (up to `request_timeout_sec`, or what is left of the deadline) finishes before the request is dropped.
- **Three anonymous POSTs went to `gemini.google.com/u/0/app` during WP8**: the old `test_rotation.py` had a
  redirect check that used the real host, and it ran in the baseline runs before the suite was isolated.

- **WP8 is NOT in the proxy's working directory.** That directory had 16 modified, uncommitted files (the
  v1.3.1-1.3.3 work) and the proxy is a live service, so nothing there was touched. WP8 lives on the branch
  `audit/wp8`, checked out as a separate git worktree in `D:\git\dev\gemini-web2api-wp8`. Its first commit is a
  snapshot of the uncommitted work (so that WP8 commits can be told apart); the rest are the WP8 tasks.
  Nothing is pushed. To use it: commit your own work on `main`, then `git merge audit/wp8` (the snapshot commit
  holds the same content, so the merge is clean) and delete the worktree with
  `git worktree remove ../gemini-web2api-wp8`. To discard it: remove the worktree and `git branch -D audit/wp8`.
- **A token-like string sits in the uncommitted `gemini_web2api/dashboard.html` of the proxy**: the placeholder
  of the "Proxy API Key(s)" field is a 40-character lowercase string that looks like a real Webshare token,
  not like a dummy. It was replaced with a dummy in the snapshot commit. Check it before that file is committed
  or pushed from `main`; if it is a real token, rotate it.
- **`run.bat` pulls from `upstream main` on every start.** The files WP8 rewrote are all listed in
  `.gitattributes` as `merge=ours`, so upstream changes to them are never merged in — including upstream fixes
  to `gemini_web2api.py`, which is now a shim.

## Found during WP4

- **"Fixed output" is a property of the glossary section, not of an entry (4.4).** The plan spoke of
  `fixed_output: true`; there is no such field. An entry is fixed when its section is listed in
  `fixed_output_sections` (default `UI`). A per-entry switch would need a model field, its serialisation and a
  checkbox in the glossary editor.
- **Nothing in the application puts a term into the `UI` section by itself (4.4).** The user types the section
  name in the glossary editor; the glossary build does not classify interface words into it.
- **Fixed outputs are filled even on Ctrl+click "translate anew" (4.4)** — the glossary is the decision. They
  are not written to the saved translations.
- **WP4 was verified by tests only.** No request was sent to a live model: duplicate folding, the run memory
  section, conversation packing and the new rule sentences have not been seen by a model yet.

- **A message reached by several flow entries is packed with the first one (4.3).** Shared greeting or farewell
  lines therefore travel with the lowest-numbered conversation that uses them; the others get them only as
  `dialogue_flow` context. Entries are deliberately not merged through shared messages (that produced
  hundred-line "conversations").
- **Packing reorders strings inside a scene (4.3):** the members of a conversation are gathered at its first
  member. Rows are applied by id, so nothing depends on the order, but the request no longer lists a block's
  strings strictly by index.
- **How many conversations in Twilight Princess are longer than 12 lines — and are therefore still cut — is not
  measured (4.3).**

- **A restore from the translation memory ignores who speaks (4.2).** The duplicate fold of 4.1 compares
  speaker, addressee and window; the cross-run memory has only the source text, so "I'm ready" saved for a
  woman is offered for a man's identical line. The user sees every such row in the Cached Translation window
  (marked "same text elsewhere") and can choose Translate Anew — but only for all rows at once. Storing the
  fold key with each memory row would let the restore be as strict as the fold.
- **Translations saved through `save_all_saved_translations` do not reach the memory (4.2)** — import of saved
  translations and the delete actions write the positions file directly. The memory is rebuilt from scratch
  only when its file is missing; an "update memory" pass after an import is not there.
- **Deleting a saved translation leaves its memory row (4.2).**

- **How much duplicate folding saves on the real project is not measured (4.1).** The audit estimated 10–30 %
  exact duplicates; the count depends on speakers and windows (a fold needs them equal). Measure on a copy:
  log line `BatchTranslator: N duplicate strings will take the translation of M others` at the start of a run.
- **The fold key costs a speaker lookup per repeated string (4.1)**, on the interface thread before the run
  starts. Only texts that occur more than once are looked up; if a project-wide run starts noticeably slower,
  cache the speaker pool for the fold (`BlockListUpdater._speaker_pool_cache` already has it).
- **A translation in progress saved before 4.1 resumes without folding (4.1)** — its chunk numbers belong to
  the unfolded plan. Nothing to do; noted so that nobody "fixes" the resume path to fold again.
- **The prompt preview shows the first folded chunk (4.1)**: with the prompt editor on, the JSON lists the
  strings that are really sent, not the duplicates.

## Found during WP6

- **Five places still use a plain `QThread` with a worker object moved into it** (`handlers/ai_chat_handler.py`,
  `handlers/translation/ai_lifecycle_manager.py`, `glossary_builder_handler.py`, two in
  `ui/script_markup/mixins/hierarchy_ai_mixin.py`). Their threads are held by an attribute and stopped through
  `safe_shutdown_thread`, so the "destroyed while running" race of `WorkerThread` does not apply as long as
  nobody sets the attribute to `None` from a result slot; `ai_lifecycle_manager.py:158` does set `self.worker`
  (the object, not the thread). Worth one look.
- **One full run crashed a pytest worker once (2026-10-02)** in `test_search_worker_global_success`, right after
  the conftest heap walk was removed. Cause found and fixed (`WorkerThread`); if a "worker crashed" line shows
  up again, it is a new case, not noise — the test that was running names the thread.

- **Results that were computed and never used (6.5, found by F841).** Removed as dead code, not wired in — each
  may be a feature that was meant to work:
  `core/translation/script_speaker_finder.py` computed whether the previous script line matches the previous
  game string and the word-count difference, and used neither when choosing the speaker;
  `components/editor/paint_event_logic.py` and `handlers/text_operation/edit_mixin.py` computed a
  `max_allowed_width` (the per-string custom width) that nothing read;
  `components/list_item_delegate/paint_mixin.py` fetched the block's colour markers and did not paint them;
  `plugins/common/text_fixer.py` and `problem_rules/registry.py` tracked "changed" flags and returned a
  comparison of the texts instead.
- **`AIWorker` has a dead branch no more (6.5):** the one-request path had a
  `glossary_occurrence_batch_update` case that the chunked path above always handled first; removed.
- **A sequential block translation cancelled during a request ends without `translation_cancelled` (6.5).**
  `_run_chunks_sequential` breaks out of the loop and only `finished` is emitted. Kept as it was; check whether
  the status window relies on it.
- **S110/S112 are gating, not a warning step (6.5).** The plan asked for a warning; with zero findings left in
  product code the rule is in `select`, so `ruff check .` (and `tests/test_static_analysis.py`) fails on a new
  silent broad `except`. Tests, `scripts/` and `tools/i18n-translate/` are exempt.

- **Two more test switches remain in product code (6.4):** `_is_test_mode` on the parent window (17 mentions:
  search and spellcheck dialogs, tag aliases, preview cache, block list, report dialog) and `mw.is_testing`
  (close handler, issue scan, Companion on close). Both are attributes somebody sets, not detection, but they
  duplicate `utils.app_mode.headless`; fold them into it.
- **`headless` is one switch for two things (6.4):** "run background work inline" and "show nothing modal".
  A test of a threaded path switches it off for itself. Split it only if a caller needs one without the other.
- **Mock tolerance in product code (6.4):** `ui/updaters/preview_renderer.py` and
  `handlers/text_operation/preview_mixin.py` wrap `QTextCursor(...)` in `try/except TypeError` and probe with
  `hasattr(cursor, 'beginEditBlock')` only because tests hand them mocks.
- **The compatibility modules still re-export names nobody imports from them** (`Path`, `QMessageBox`, ... in
  `handlers/project_action_handler.py`, `core/project_manager.py` and ten more). Tests patch class attributes
  through some of those paths (`...project_action_handler.QFileDialog.getOpenFileName`). Remove with the shims
  themselves once callers import from the real packages.
- **`plugins/zelda_bmg/window_frame_loader.py::_KNOWN_DUMP` is a path on the author's machine** (`E:\Emulators\...`).
  It should come from the project or the plugin settings.

- **`sync_push_on_close` still syncs on the calling thread when there is no window (6.3)** — headless callers
  and `mw.is_testing` (a test switch in product code; 6.4 removes the `pytest` checks, this attribute stays
  until the close path gets an injected "show dialog" decision).
- **Project close calls `sync_push_on_close` too** (`handlers/project_action/lifecycle_mixin.py`): the sync
  window there is titled "Closing Picoripi" although only the project closes.

- **A parked thread still finishes its network request (6.2).** `requests` cannot be interrupted from another
  thread, so a skipped Companion sync runs until the client's timeout (15 s, 6 s on close) and the process waits
  up to 8 s for it at exit (`utils.thread_utils.wait_for_parked_threads`). Closing the `requests.Session` from
  `cancel()` (as `AIWorker` does since 1.8) would end it at once.
- **`safe_shutdown_thread` has no `allow_terminate` any more (6.2).** No product code used it. The plan kept the
  flag; it is gone because a terminated thread leaves locks held and files half-written.
- **Seven MemPalace workers were renamed too (6.2)**, beyond the four the plan lists: every `QThread` subclass
  that declared its own `finished`. Their `worker.finished.connect(worker.deleteLater)` lines now mean what they
  say (Qt's signal, after the thread ended) instead of deleting a thread that was still inside `run()`.
- **`AliasUpdateWorker` and `SaveWorker` have no caller that cancels them (6.2).** The alias worker checks for
  interruption between blocks; a save is deliberately not cancellable. Nothing asks either to stop on exit.

- **Not atomic on purpose (6.1):** creating a new empty file (`translation_map.json` as `{}`, a new project
  glossary as `[]`), `.bak` copies, the log file, the downloaded dictionary, command-line tools
  (`plugins/zelda_bmg/bmg_tool.py`, `stage_data.py`), MemPalace helper outputs. None overwrites a user's work.
- **Settings → OK writes the font map table into `plugins/<plugin>/font_map.json`** (`ui/settings/load_save_mixin.py`),
  and `tag_alias_mixin` writes font-map overrides there too. User settings inside `plugins/` (audit C, P0-c);
  move them to the per-user plugin folder together with `window_layouts.json`.
- **Tests bypass `mock_open` now.** `utils.atomic_io` does not go through `builtins.open`, so a test that only
  mocks `open` and passes a path outside `tmp_path` writes a real file. A traced full run (2026-10-02) found
  none left; new tests should save into `tmp_path` or patch `atomic_write_*` in the module under test.

## Found during WP5

- **`ui/main_window/bfn_actions.py` still imports the BMG parser** (`from bmg_tool import BMGFile, BMGMessage`,
  through the root shim) for the "Import / Export BMG JSON" actions and calls `msg_to_editor_text`. These are
  Twilight Princess actions living in the main window; they belong in the plugin's `get_plugin_actions()`.
- **The Settings table of per-window limits writes into the plugin folder**
  (`plugins/zelda_bmg/window_layouts.json`). It is the last place where user settings are stored inside
  `plugins/`; move it to the project or user override folder (audit C, P0-c).
- **`get_preview_window_style` and `get_message_attributes` are still looked for with `hasattr`** in four host
  places instead of being base-class hooks.
- **File dialogs of the project wizard and the settings path picker still list fixed extensions**
  (`components/project_dialogs.py:240,260,594,617`, `ui/settings/path_picker_mixin.py:73`,
  `handlers/list_selection/physical_selection_mixin.py:384`). A plugin's own format is reachable through
  "All Files"; the single-file open/save dialogs already use `core.formats.dialog_filter`.
- **Test leftovers under `C:\Temp\project`** (`.extracted/translation/bmgres.arc/zel_unit.bmg`, …): written by
  `tests/test_core/test_data_state_processor_native_packing.py` before WP5.5 (it mocked `Path` but not the
  file writer). The tests no longer write there; the folder can be deleted.
- **Watch: `tests/test_ui/test_bfn_preview_widget.py::test_preview_initial_scale_with_background_fits_viewport_proportionally`**
  failed once under `-n 8` (scale 0.596 vs 0.510) and passed on three reruns alone and in the next full run.
- **`editor_review_enabled` and `max_reference_languages` have no settings-dialog control** (translation
  config keys). Add a checkbox in the AI Translation settings tab if the editor-review pass is to be used.
- **Three scripts in `scratch/` import `plugins.zelda_bmg.text_fixer`** — the reason that module and
  `zelda_bmg/problem_analyzer.py` were kept as named subclasses in WP5.2.

## Found during WP3

- **WP3 exit is not ticked**: no real glossary build was run on a live model (it spends account quota and
  changes the working glossary). The numbers in `walkthrough.md` / `docs/audit/2026-10-01/wp3_glossary_numbers.json`
  are measured on a copy of `translation_prompts/glossary.json` without AI calls. To close: run Prepare
  Glossary with "Reconcile related terms afterwards" on a sample project and record requests, tokens,
  collision groups and diverging families before/after.
- **18 canonical duplicate groups are still in `translation_prompts/glossary.json`** (waiting for a decision,
  see `docs/REVIEW_QUEUE.md`); `KNOWN_CANONICAL_GROUPS` in `tests/test_core/test_glossary_consistency.py`
  goes to 0 after the merge.
- **Deletion records (`deleted_at`) are never pruned** from the glossary file. Drop those older than a few
  months once every device has synced, if the list ever grows.
- **Reconcile does not remember "keep separate" answers**: a pair of spellings the model left apart is asked
  about again on every run. Store the verdict on the entries if the pass is used regularly.
- **Reconcile compares a family only within itself** (`Zora Guard` is in the guards family and is not compared
  with `Zora`). Add the head entries of a member's other words as read-only context if drift shows up there.
## Found during WP0

- **WP0 exit is not ticked**: the suite is green on Windows only; the Linux run has not been done.
- **The intermittent test hang (one `F`, then idle workers) is explained and fixed** (2026-10-02, WP5.8):
  `tests/test_core/test_i18n.py::test_missing_string_stays_english` switched the interface language to
  Ukrainian and left it; later tests on that xdist worker failed on English strings and
  `test_AIStatusDialog_cancel_no_keeps_running` waited on a real message box for ever. `tests/conftest.py`
  now resets the language around every test (`english_interface`). Delete this line after a few clean weeks.
- **JSON fence strippers not yet on `utils.json_extract`** (WP1.3 replaced the three the plan named):
  `core/mempalace/chapter_ai_analyzer.py:102`, `normalized_character_profiler.py:220`,
  `timeline_ai_analyzer.py:176`, `weaver_worker.py:15`, `core/script_markup/hierarchy_ai.py:187`,
  `handlers/translation/translation_ui_handler.py:164`, `handlers/translation/glossary_builder_handler.py:46`.
- **Cancel text in the status dialog is now conservative for translation.** "The current request will stop
  after the active network step" is still true for the glossary pipeline and MemPalace, which share the
  dialog; translation requests stop at once since WP1.8. Give those callers the same cancel hook
  (`provider.enable_retries`/`run_cancellable`), then reword the string (EN + `locales/uk.json`).
- **Streaming and Ollama requests are not retried.** They share timeouts, error classification and the
  breaker with the rest, but `TransportPolicy.run` wraps only non-stream requests — a stream cannot be
  replayed half-way. Retrying the connection phase alone is possible if chat needs it.
- **Provider profile has no settings-dialog control and no `/v1/models` probe** (WP1.5): the host rule plus
  the `"profile"` settings key cover it. Add a combo in `ui/settings/ai_mixin.py` if users need it.
- **A test file depends on this machine's data.** `tests/test_handlers/test_ai_prompt_composer.py` builds
  the composer on a bare `MagicMock` main window; the story-context code then finds and parses the real
  script at `e:\Emulators\RomHacking\ZELDA\TP_UA\zelda_tp_script.txt` and queries MemPalace (the file takes
  ~20 s and its "Story Context" sections come from that script). Stub `composer.story_context` in the fixture.
- **Leftovers of the removed translation-session path.** `AIWorker.run` still has `session_info` /
  `session_state` branches that can no longer be reached for translation tasks, the composers still accept
  `session_state`, `_prepare_glossary_for_prompt` is a pass-through stub and `_record_session_exchange` is a
  no-op for them. Remove when `run()` is split (WP6.5).
- **Runtime-name replacement still runs over the whole user message** (WP2.5 left it): besides the item
  text it also turns `{PLAYER}`-style escapes into names in neighbour rows and reference lines, which is
  useful. Applying it per section instead of to the final string would be the tidy version.
- **`max_reference_languages` has no settings-dialog control** (translation config key; default every language, 0 none).
- **Holding folder to delete**: `D:\git\dev\Picoripi_local_cleanup_2026-10-01` (562 MB: `gemini/`, `.grok/`,
  `.tmp_audit/`, 35 `graphify-out` snapshots, `stderr_output.log`, `image.png`, `settings.json.migrated`).
  Task 0.9 moved these out of the workspace instead of deleting them.
- Root `CHANGELOG.md` is ~38 KB after archiving: the last 14 days hold 17 verbose release entries. New
  entries are one line each; consider cutting the window to the current minor at the next release.

## Found during WP7

- `scripts/deploy.py` still runs `git add .` and offers to push; AGENTS.md forbids the first and releases go
  through the deploy skill. The version bump and the changelog insert were fixed in 7.3; the git part was left alone.
- `docs/FEATURES.md` was moved from the README as written (14k tokens), with only the known stale claims fixed.
  Individual bullets (colours, pixel sizes, widget names) were not re-verified against the code.
- `plugins/zelda_mc/translation_prompts/glossary.md` and `plugins/zelda_ww/translation_prompts/glossary.md` are
  read by no code (the glossary is looked up only in the project folder). They are those games' own term
  lists, so 7.4 left them; the `plain_text` copy of the Wind Waker list was deleted.
- The copies of the `update-wiki` skill outside the repository (`~/.claude/skills/update-wiki/`, `.grok/`) were
  not touched; `.agents/skills/update-wiki/SKILL.md` is the one that was brought up to date.
- `docs/MEMPALACE_CONTEXT_MANIFESTO.md` takes the stage statuses from the archived plan (last entry
  2026-07-16); nobody re-checked stages 3 and 4 against the code.

## Majora's Mask N64 plugin (`plugins/zelda_mm64`)

- **Ukrainian letters**: the codec only knows the N64 font's characters. A translation map (letter -> font
  slot) and redrawn glyph textures (`file 28`, 16x16 I4) plus widths (`sNESFontWidths` in `code`) are needed
  before Cyrillic can be saved. SoH-style ports keep the widths fixed, so slots should be chosen by width.
- **Relocated text is unverified in a running game**: a save whose text outgrows its 0x6A000-byte range moves
  `message_data_static` to free address space and rewrites the four `lui`/`addiu` pairs in `z_message.c`
  (checked statically only). Test ROMs: `MM64_UA\rom\test_edit_blue_rupee.z64`, `test_text_grown_40pct.z64`.
- **Characters per text box**: `Font.charBuf` holds 120 glyphs per box (`include/z64font.h`); longer Ukrainian
  boxes may run out. Not checked by the plugin yet.
- **Credits** (`staff_message_data_static`) are not in the project.
- **Exports**: a 2Ship2Harkinian `.o2r` (TextMM file) and a Zelda64Recomp `.nrm` (EZ Text Replacer code)
  from the same project; the Ukrainian MM3D table (`translation_majora.csv`) as a seed for the N64 ids.
- **Width of runtime values** (`{rupees-total}`, timers) counts as zero.

## Ocarina of Time N64 plugin (`plugins/zelda_oot64`)

- Same open items as Majora's Mask (Ukrainian letters, exports, credits, characters per box). Relocated text
  rewrites the single `lui`/`addiu` pair that loads the English text on NTSC; untested in a running game
  (`OOT64_UA\rom\test_edit_green_rupee.z64`, `test_text_grown_40pct.z64`).
- Only NTSC-U 1.0 is supported; Europe 1.0 (English/German/French) could serve as reference languages.

## Context mined from the N64 decompilations (`plugins/common/zelda64_context.py`)

- Speaker names are decomp descriptions ("Clock Town - Gate-Blocking Soldier", OoT actor names like `En_Go2`
  where no description exists); a curated name table would read better. Cutscene-only lines, ids computed at
  run time and Bombers' Notebook entries without a placed actor get no speaker. Report:
  `E:\Emulators\RomHacking\ZELDA\MM64_UA\reports\context_report.md`.

## The Wind Waker GameCube plugin (`plugins/zelda_tww`)

- **Ukrainian letters in the font**: the US game reads bytes 0x80–0x9F as Shift-JIS lead bytes, so a
  translation map must not put letters there (Europe: only Hylian boxes do this). Pick the slots before
  drawing the font.
- **Runtime suffixes are in the executable**, not in BMG: " Rupee(s)", " bomb(s)", " yard(s)", timers
  (`tag_*` in `f_op_msg_mng.cpp`). A Ukrainian build needs them patched in `main.dol`, or the text rewritten
  around a bare number.
- **No speakers yet**: NPCs pick message ids in code (`getMsg` / `next_msgStatus` per actor), cutscenes through
  `event_list.dat` `msgNo`. TP's flow-based attribution does not apply.
- **No window frames** in the preview (`hukidashi_*.blo` in `res/Msg/msgres.arc`) and no `message_window_preview`.
- **`bmgresh.arc/zel_01.bmg`** (15 Hylian-language messages, Shift-JIS) does not load: the BMG reader maps
  Shift-JIS to cp1252 for Twilight Princess.
- **Rebuilding the disc**: the images were extracted with DolphinTool (`files/` + `sys/`); `gcr` packs a
  `root/` tree, so the pack script in the user's workspace does not work yet.

## Zelda: Tears of the Kingdom plugin (`plugins/zelda_totk`, branch `feat/zelda-totk`)

- **Never run on TotK's own files.** No TotK romfs was on disk; the formats were checked on synthetic files and
  on another game's `Mals/USen.Product.100.sarc.zs` (Tomodachi Life, same LMS/SARC/zstd stack: 262 MSBTs and the
  SARC rebuild byte for byte), the font reader on Switch BFFNTs of another game. First real check: open the
  dumped romfs, save one edited line, load the mod in an emulator.
- **No speakers or scenes.** TotK's event flows (`.bfevfl` under `romfs/Event`) name who says each message; an
  offline extractor (like `plugins/zelda_bmg/msg_flow.py` for TP) needs the romfs to be written against. Today a
  line's context is its MSBT file and label only.
- **Width limits are placeholders** (900/880 px, 3 lines per page, icon 36 px, `{playerName}` 64 px). Calibrate
  them against the dialogue font map made by `font_tool` and the game's message window.
- **RESTBL growth rule is a guess**: the entry grows in proportion to the decompressed archive. Check the value
  the game needs (crash or not) with a translation that is much longer than English.
- **Tag catalogue** comes from MSBT Editor's `TotK.gcf`; most group 2 (numbers/strings) and 201 (grammar) tags
  have no confirmed argument meaning. A tag whose bytes do not fit the catalogue shows as `{tag:G:T:hex}`.

## Found during the series glossary feature

- The series tab shows no occurrences (Count 0): its occurrence index is not built over the open project.
- Glossary builds do not consult the series glossary: a term the series already decided is seeded and
  translated again in the project (the series file itself is never written by a build).
- Series and project glossary files are read and written on the UI thread, as the project glossary is today.
- Two programs (or two projects open at once) editing the same series file: the last write wins.
