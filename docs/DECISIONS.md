---
status: current
updated: 2026-10-02
owns: decisions and their reasons
tokens: 2.1k
purpose: Why the code is the way it is: one short record per decision
---
# Decisions

One record per decision that shapes the code: what was decided, why, and what it costs. Add a record when a
choice would otherwise have to be re-argued; never rewrite an old one — add a new record that supersedes it.
Sources: `docs/history/AUDIT-2026-H1.md` (2026 H1) and `docs/audit/2026-10-01/` (the October audit).

## D1. One writer of project data (2026-06)

**Context.** Handlers and widgets changed `data`, `edited_data` and unsaved flags directly; undo, autosave and
the block tree drifted apart.
**Decision.** Every change of text goes through `DataStateProcessor`, which writes `AppDataStore`, records undo,
marks the block unsaved and schedules the session save. Updaters only read.
**Cost.** One more hop for a trivial edit; a handler that needs a new kind of mutation adds a processor method.

## D2. The engine knows no game (2026-07, enforced 2026-10)

**Context.** Twilight Princess vocabulary (`BossName`, BMG section names, the Zelda Wiki lookup) had leaked into
the prompt composer and the core.
**Decision.** Game knowledge lives in `plugins/<game>/` behind opt-in `BaseGameRules` hooks. The engine
publishes empty slots (`window_type`, `content_role`, `role_instruction`, …) and never compares them with a
value. A missing hook means the feature is absent, not an error. `plugins/spec.py` is the list of hooks;
`docs/PLUGIN_CONTRACT.md` is generated from it.
**Cost.** A new capability needs a hook, a spec entry and documentation in four places (AGENTS.md checklist).

## D3. Big modules were split; the old module names stay as re-exports (2026-06)

**Context.** `translation_handler.py`, `ai_worker.py`, `project_action_handler.py` and others had grown past
1000 lines; plugins, tests and saved habits import the old names.
**Decision.** The code moved into packages of mixins; the fourteen old modules only re-export
(`docs/ARCHITECTURE.md` lists them). Tests patch a name in the module that uses it.
**Cost.** Opening an old module shows nothing; the table in ARCHITECTURE is the map.

## D4. Session: a fast binary snapshot plus a durable JSON checkpoint (2026-06)

**Context.** JSON alone made autosave lag on large projects; a binary snapshot alone could not be validated or
read by a person, and an incomplete one once lost an open project.
**Decision.** Debounced autosave writes a Pickle snapshot; a schema-validated JSON checkpoint is written at
shutdown, every five minutes and before long operations. Startup loads JSON first and falls back to Pickle.
**Cost.** Two formats to keep compatible. Pickle is only ever read from the project's own folder.

## D5. Tests run in parallel; timing tests have their own lane (2026-06)

**Context.** A serial run takes hours. Performance tests are meaningless under load from other workers.
**Decision.** `pytest -n auto` is the only supported way to run the suite; tests marked `performance` are
excluded by default and run separately; heavy real-thread tests are marked `serial`.
**Cost.** Every test must be safe beside others: no shared files outside `tmp_path`, no leftover threads.

## D6. The glossary belongs to the project, as JSON with stable ids (2026; ids and tombstones 2026-10, WP3)

**Context.** A glossary beside the plugin was shared by every project of that game; the Markdown table could not
hold variants, evidence or sync state.
**Decision.** The glossary is `<project>/glossary.json` and is looked up only there. Every entry has a stable
`id`; a deleted or merged entry leaves a tombstone so that Companion sync does not resurrect it. An old `.md`
glossary is migrated with a backup.
**Cost.** A new project starts with an empty glossary; plugin-side term lists are seeds, not the glossary.

## D7. One automatic glossary pass (2026-08)

**Context.** Seed, sweep, describe and translate were separate modes that had to be run in the right order.
**Decision.** One pass runs them in sequence without stopping for questions; doubts go to a review backlog and
never block translating text. The pass is incremental by block fingerprint.
**Cost.** The report after a pass shows a remainder, not "done"; review is a separate, human step.

## D8. Fixed prompt rules are code and stay byte-stable (2026-10, WP2)

**Context.** Request rules lived in editable prompt files, drifted between plugins and changed per request,
which defeated provider-side caching.
**Decision.** The rules that make a request work (output format, layout, tags, glossary use) are constants in
`handlers/translation/prompt_composer/instructions.py`, appended after the editable prompt.
**Cost.** A rule change is a code change with a test; users edit style and voice, not mechanics.

## D9. A worker is never terminated; a stuck one is parked (2026-10, WP6)

**Context.** `terminate()` and destroying a running `QThread` crashed the process; so did a result slot that
dropped the last reference before `run()` returned.
**Decision.** Workers derive from `WorkerThread`, which keeps itself alive until Qt reports it finished.
`safe_shutdown_thread` cancels, waits a bounded time and parks a thread that did not stop; the application
waits for parked threads at exit.
**Cost.** A worker must check for cancellation itself; a custom `finished` signal is named `finished_with_result`.

## D10. Product code never detects the test runner (2026-06, completed 2026-10)

**Context.** Branches such as `'pytest' in sys.modules` and mock checks made tests pass on code paths users never run.
**Decision.** The only switch is `utils.app_mode.headless` ("no event loop, nobody at the screen"), set by
`tests/conftest.py`. A guard test fails on any other detection.
**Cost.** Code that must run inline without an event loop states so explicitly through that flag.

## D11. User data is written atomically and never into `plugins/` (2026-10, WP1 and WP5)

**Context.** A crash during a save left truncated project and glossary files; aliases and font maps written into
the plugin folder were lost on update and changed tracked files.
**Decision.** User data is written to a temporary file in the same directory and renamed (`utils/atomic_io.py`).
Run-time data goes to `SETTINGS_DIR` or the project folder; `plugins/` is read-only at run time.
**Cost.** Bundled defaults and the user's overrides are two files that are merged at load.

## D12. Identical source strings are translated once per run (2026-10, WP4)

**Context.** Games repeat lines; each copy cost a request and could come back worded differently.
**Decision.** A run folds strings with the same normalized source and the same context key into one request and
copies the result to the followers; a project translation memory offers earlier translations of the same or a
similar source. The fold is saved with the run so that a resume applies it again.
**Cost.** Two identical lines that should differ need different context, or a manual edit afterwards.

## D13. Interface text: English source, Ukrainian in the same change, no Russian (2026)

**Context.** Half-translated controls and three places to edit a string.
**Decision.** UI text is `tr("English source")`; the key is added to `locales/uk.json` in the same change. Other
catalogs are filled by `tools/i18n-translate/`. There is no Russian locale, string or comment.
**Cost.** A missing key shows English; nothing but review catches a key that was forgotten.

## D14. One home per fact in the documentation (2026-10, WP0 and WP7)

**Context.** The same feature was described in the README, a feature reference, the wiki and two manifestos, and
they disagreed; an agent read 60k tokens before starting.
**Decision.** `AGENTS.md` is the only place for agent rules. Every document under `docs/` has a header (status,
owner, size); `docs/INDEX.md` is generated from them; `tests/test_docs/` checks paths, links, EN/UK structure
and size budgets. Process logs live in `docs/history/` and are not read, only searched.
**Cost.** A document change ends with `python tasks.py docs-index`.
