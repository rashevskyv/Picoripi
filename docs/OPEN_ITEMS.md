# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Carried over from the 2026 H1 audit (`docs/history/AUDIT-2026-H1.md`)

- **DOC03** — feature docs as a release requirement: a changed feature updates its owning doc in the same
  change. Superseded by the `AGENTS.md` checklist once WP7.4 merges `docs/FEATURE_REFERENCE.md` into wiki 1.
- Keep `docs/FEATURE_REFERENCE.md` current for large features until WP7.4 removes it.
- UI command "Create plugin from template" (copy `plugins/default_plugin`, rename, open the prompt file).
  WP5.4 delivers the generator (`tools/new_plugin.py`); the menu entry is still unplanned.

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
- **`max_reference_languages` has no settings-dialog control** (translation config key, default 1).
- **Holding folder to delete**: `D:\git\dev\Picoripi_local_cleanup_2026-10-01` (562 MB: `gemini/`, `.grok/`,
  `.tmp_audit/`, 35 `graphify-out` snapshots, `stderr_output.log`, `image.png`, `settings.json.migrated`).
  Task 0.9 moved these out of the workspace instead of deleting them.
- `scripts/deploy.py::bump_version` does not handle the `-dev` suffix (`0.3.141-dev` comes back unchanged)
  and `update_changelog` expects a `# Changelog` heading the file no longer has. Releases are done by hand
  through the deploy skill, so the script is effectively unused — fix it or delete it in WP7.5.
- `AGENTS.md` "Read next" should point at `docs/INDEX.md` once WP7.1 creates it.
- `docs/AI_DEVELOPMENT_MANIFESTO.md`, `docs/FEATURE_REFERENCE.md` and `docs/TESTING_STRATEGY_AND_AUDIT.md`
  still tell agents to update `GEMINI.md` / `AUDIT.md`; both are gone as working files (WP7.4 merges these
  docs).
- Root `CHANGELOG.md` is ~38 KB after archiving: the last 14 days hold 17 verbose release entries. New
  entries are one line each; consider cutting the window to the current minor at the next release.
