---
status: current
updated: 2026-10-02
owns: decisions and their reasons
tokens: 3.7k
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

## D15. Twilight Princess: the hero is «Лінк» and the horse «Епона», fixed and declined (2026-10-03, owner)

**Context.** The game fills in the names the player typed (`{escape:0:0000}` hero, `{escape:0:0022}` horse), and a
tag cannot take a Ukrainian case ending. A live run showed «Лінку» in the vocative.
**Decision.** Both tags are force aliases (`{F:Link}`, `{F:Epona}`): the model sees the name, declines it, and the
translation keeps «Лінк» / «Епона» in the right case as plain text. The names are fixed: the translation does not
support renaming (the glossary says so for Link). A nominative-only `{Epona}` tag was tried and rejected.
**Cost.** A hero or horse renamed by the player keeps the Ukrainian default name.

## D18. Working together: a room hosted inside one participant's Picoripi (2026-10-10, owner)

**Context.** Several translators work on one game. The Companion server (FastAPI, Docker) syncs only the glossary and
needs a machine to run it; peer-to-peer needs NAT traversal and a replicated data model.
**Decision.** The owner chose a server that one of the participants runs: Tools → Work Together starts a stdlib HTTP
room inside that Picoripi (`core/collab/server.py`), the host sets port and password, everyone (the host too, over
127.0.0.1) joins with the same client. Rows are keyed like saved translations; a fingerprint of the source rows
refuses another project; an edit on an old revision is refused and shown as a conflict, never overwritten silently.
The room also serves the progress page and the team board (`/stats`).
**Cost.** Plain HTTP (LAN or a VPN); the room lives only while the host's Picoripi runs; every participant needs the
same game files; Import BMG and Undo Paste bypass the room.

## D17. Text textures: one window, the game's own format, only changed blocks re-encoded (2026-10)

**Context.** Every game bakes some words into textures (title cards, menu labels, logos), in a dozen formats inside nested archives. The translator redraws them in an image editor of their choice.
**Decision.** `core/texture_formats/` reads a texture file into RGBA images and writes images of the same size back in place: a pixel format is a `Codec` over elements (a GX/PICA tile, a 4x4 block or a pixel), the console tilings give the element offsets, and only elements whose pixels changed are encoded again, so an unedited texture writes byte-exact and an edit costs no quality elsewhere. A plugin names its textures in `texture_sources.json`; containers and compression are found by their bytes, the rest are descriptor params. No PNG round trip through Picoripi's own drawing: the user's image editor does the redraw.
**Cost.** A texture cannot change size or format; formats without an encoder here (ASTC) or inside models (BMD/BDL/BFRES) are listed as next work. Pure-Python ETC1/BC7 encoding takes seconds for a large texture (in a worker).

## D16. One font editor; every font format becomes the BFN-shaped model (2026-10)

**Context.** Each new game came with its own font file (N64 ROM font, G1T atlas, BFFNT), and a tool per game
would have repeated the glyph grid, the width table and the translation map that the BFN editor already has.
**Decision.** `core/font_formats/` turns each format into the editor's existing model (`data.json` with the BFN
section names + sheet images) and packs it back into the original bytes; only edited glyphs are encoded again,
so an unedited font saves byte-exact. A plugin names its fonts with `get_font_sources()` / `font_sources.json`;
game constants stay in that file. Widths reach the checks through `<project>/font_maps/*.json`.
**Cost.** The model keeps BFN names (`GLY1`, `MAP1`, `WID1`) for formats that are not BFN; a format whose
character map is fixed by the game cannot give a new glyph a character (the translation map does that).

## D20. The Project Manager lists the projects the user added; counts come from memory (2026-10)

**Context.** Picoripi had only Recent Projects. Scanning all project files at start would read hundreds of
folders and make the list depend on the disk. The line and translation counts need the plugin's parser, and
a plugin loaded on a worker thread is a risk.
**Decision.** `~/.picoripi/project_manager.json` holds only what the user added: paths, folders, names, the
view choices. Every change is a read-modify-write on a worker under one lock. The window reads a cache,
`project_index.json`, and refreshes each card from a worker. Lines and translated % are counted from the data
already in memory when a project opens or saves, on a worker. Only `picoripi/project.uiproj` folders are imported,
and folders named `_…` or `.…` are skipped.
**Cost.** A project never opened in Picoripi shows "—" for lines. Counts copy the lists on the UI thread once
(pointer copies). Recent Projects stays as before and is not replaced.

## D19. The user chooses the data folder; no silent default, no home folder by default (2026-10)

**Context.** Picoripi wrote everything to `~/.picoripi`, spread over the computer. The user wants a portable
program whose data sits in one folder that he chooses, and no data written before he has chosen.
**Decision.** `utils/data_location.py` resolves the folder from explicit choices only: the env variable
`PICORIPI_HOME`, then `picoripi_home.json` next to the program (a path inside the program folder is stored
relative). Without either, the first-start chooser (`dialogs/data_location_dialog.py`) must run; its suggestion
(`data` next to the program) is pre-filled and still needs a confirm click. The model (`core/data_location_choice.py`)
checks writability, free space and the old profile; the copy of an old folder never overwrites, never deletes,
and writes the pointer only after success. `utils.constants.SETTINGS_DIR` keeps its name and is frozen at import, so
the chooser runs in `main.py` before any module reads it. Headless runs and the test suite set `PICORIPI_HOME`
to a temp folder; a headless run without an explicit folder raises instead of asking or guessing.
**Cost.** The chooser appears on each new worktree or checkout (each has its own `data/`). A "change folder"
takes effect after restart, because modules hold the path they read at import. Logs stay next to the program.
