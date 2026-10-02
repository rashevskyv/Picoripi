# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Carried over from the 2026 H1 audit (`docs/history/AUDIT-2026-H1.md`)

- **DOC03** — feature docs as a release requirement: a changed feature updates its owning doc in the same
  change. Superseded by the `AGENTS.md` checklist once WP7.4 merges `docs/FEATURE_REFERENCE.md` into wiki 1.
- Keep `docs/FEATURE_REFERENCE.md` current for large features until WP7.4 removes it.
- UI command "Create plugin from template" (copy `plugins/default_plugin`, rename, open the prompt file).
  WP5.4 delivers the generator (`tools/new_plugin.py`); the menu entry is still unplanned.

## Found during WP5

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
- **`CompanionSyncClient.commit_merge` and `pull_project` still write the glossary non-atomically**
  (`write_text`); the manager's own writes are atomic since WP3.6. WP6 covers user-data writes.

## Found during WP0

- **WP0 exit is not ticked**: the suite is green on Windows only; the Linux run has not been done.
- **Watch: the intermittent UI-lane hang of 2026-10-01** (one `-n 2` run printed an `F` at ~88 % and stalled
  with idle workers). Most likely the same cause as the click/focus failures fixed on 2026-10-02:
  `tests/conftest.py::_stop_lingering_qthreads` called `quit()` on the GUI thread, after which every
  `QEventLoop.exec()` on that xdist worker returned at once. Not proven for the hang itself; delete this line
  if it does not come back. WP6.4 removes that heap walk altogether.
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
