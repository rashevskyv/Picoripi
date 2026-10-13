---
status: current
updated: 2026-10-02
owns: decisions and their reasons
tokens: 6.1k
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

## D21. A room join applies its rows on the UI thread in short turns, not in a worker (2026-10-12)

**Context.** A join applies every row of the room to the open project, then refreshes the tree of each block it
touched. Both change state owned by the UI thread (the data store, the unsaved-changes state, the block tree and
the editor). AGENTS rule 5 keeps such work off long blocking calls. The first measurement used the mock-heavy test
window: about 300 us per row, so 5,000 rows took 2.25 s and 20,000 rows 4.9 s in one call. That number is mostly
mock overhead.

**Measured on the real path** (the product classes: `DataStateProcessor`, `AppDataStore`, `FilterQueryAPI`,
`BlockListUpdater` on a real `QTreeWidget`, the room handler, the rules of `plain_text`; a plain-attribute window
with no MagicMock; one problem every 20 rows, written as a project scan leaves them; idle machine; garbage
collector paused; below-normal priority):

| case | total | apply turns | slowest apply turn | refresh turns | slowest refresh turn | per block refresh (median / max) |
|---|---|---|---|---|---|---|
| 25 blocks x 200 rows (5,000) | 0.06 s | 26 | 3.9 ms | 25 | 1.3 ms | 0.31 / 1.30 ms |
| 100 blocks x 200 rows (20,000) | 0.19 s | 101 | 2.8 ms | 100 | 1.0 ms | 0.59 / 0.81 ms |

- Apply: 7 to 10 us per row (median 8 us; p99 18 to 50 us); the slowest single row 0.23 to 0.45 ms.
- Refresh of one block, first call after its rows changed (the block's warning index is rebuilt): median 1.8 ms,
  max 4.5 ms for 100 blocks of 600 rows with 60,000 problem entries (1 per row), and 3.2 ms with 2,100 extra
  tree items (the tree iterator is O(tree) per call). Repeat call with the index built: 0.1 ms (0.9 ms with the
  extra tree items).
- Remote batches (the same real window, 100 blocks, one batch of edits, before this round one event):
  20,000 edits in 0.26 s (200 turns; slowest apply turn 5.2 ms, slowest refresh turn 1.1 ms; 6 us per row median,
  0.36 ms max); 60,000 edits in 0.77 s (400 turns; slowest apply turn 5.1 ms, slowest refresh turn 2.2 ms; 6 us per
  row median, 0.9 ms max). Before the turns, one event took 0.23 s and 0.64 s for the same batches.
- Not measured: the editor's text views (`update_text_views`), which need a real editor. A join or a remote batch
  calls them at most once, in a turn of their own.

**Decision.** The join is a generator that runs in turns, one turn per event-loop pass (`single_shot` owned by the
handler; `leave()` drops the generator, so a left room stops the join). An apply turn ends after 200 rows, or after
about 50 ms; the clock is read every 8 rows. After the last row, each touched block is refreshed in its own turn
(one tree refresh per turn, in block order). The editor's text views, when the displayed block was touched, get a
turn of their own. Each row is checked when it is reached (conflicts, keys superseded by a remote edit, a left
room). The apply and the refresh stay on the UI thread: they mutate the store, the tree and the editor. A worker
would need a snapshot of the store (as costly as the reads) and would race with the user's typing.

**Remote batches** use the same turn queue (`_turns`, run one turn per event-loop pass). The join is the first
item in the queue; each remote batch is one generator that drains `_remote_pending`, so a batch that is still
running is never started again and later edits join it in arrival order. Within a turn, edits are applied in order,
JOIN_SLICE_ROWS per turn. An edit is written only if its revision is newer than the newest one this participant has
applied or sent (`_applied_rev`): an older edit cannot overwrite a newer one, and the same edit is never written
twice. A row with an unsent local edit is left alone (the server decides that conflict, as before). `leave()` drops
the queue, the pending edits and the running batch, and starts a new room generation: events from an older
generation, or any event while not joined, are dropped before they are queued, so nothing from an old room is
written into the project. One edit that raises is logged once per batch with its key; the rest of the batch goes
on. A turn that raises is logged and dropped, and the queue goes on.

**Queue limit (documented).** The remote queue has no size limit: nothing is dropped. One poll returns at most
5,000 events, so a backlog exists only while the window stalls; a stall of several seconds with a busy room can hold
tens of thousands of events in memory until the window runs again. A client-side pause would be the next step.

**Cost and limits.** A join of 20,000 rows takes about 0.2 s of apply and refresh work, spread over about 200
event-loop passes; the tree and the editor show the old state until their turn comes. A single row or a single
block refresh can hold the window for its own cost (under 1 ms and under 3 ms measured). A remote batch that
arrives while a join runs waits behind it. Remote edits are queued without a size limit: nothing is dropped; a poll
returns at most 5,000 events (`EVENT_LIMIT`), and at the measured turn rate a backlog clears in a few event-loop
passes, so the queue does not grow unless the window stops for a long time.

**Test.** `tests/test_performance.py` runs the real-path join (with the real tree refresh) and requires every turn
under 0.15 s, about 30 times the measured slowest turn; it also runs a batch of 60,000 remote edits over 100 blocks
with the same bound, and checks that each row is written once. The mock-window join test is a smoke test with no
time bound. `tests/test_core/test_collab.py` checks that a join touching 100 blocks runs at most one block refresh per
turn and refreshes each block once, and that overlapping remote batches apply in arrival order and a stale or
repeated revision is not applied.

## D23. Project Manager phase 2: plugin hooks for roles, unpacking and builds; counts in a worker (2026-10-12)

**Context.** Phase 1 listed the projects and showed counts only after a project was opened. The new-project wizard,
Build, Export and Run need facts only a game's plugin knows: which files a game has, how to recognise them, how to
unpack them and what it can build.
**Decision.** Six optional `BaseGameRules` hooks: `get_source_roles`, `identify_source`, `get_platforms`,
`unpack_sources`, `get_build_targets`, `build_target`. The defaults do nothing, so every plugin stays valid, and
the buttons stay off for a game that declares no target. Each hook runs on a worker and receives its progress and
cancel callables; a hook never touches widgets. The wizard creates the project through the same path as the old
dialog (`LifecycleMixin.finish_new_project`). Unpacking and building write into a temporary folder beside the
result and rename it into place only when complete; a cancel removes that folder and nothing else. Export copies a
built folder into a folder the user chooses, which must be empty. The emulator command is a Project Manager setting
kept in `project_manager.json` (`settings`), written through the registry's lock and atomic write. It is split into
arguments before `{path}` is replaced, and the program starts detached without a shell. Counts for projects never
opened come from `count_project`, which loads the plugin with `GameRules(None)` on a worker and counts the blocks the
project file lists, resolved against the source and translation paths. The result is cached in `project_index.json`
with the project file's modification time (`counted_mtime`). The plugin loader is passed in, so tests use an explicit
fake. The flags "built" and "verified in game" live in `metadata.flags` and change only when the user ticks them.
An open project saves them through its own manager, so no second writer touches its file.
**Thread safety.** `BaseGameRules(None)` creates `QTextCharFormat`, `QColor` and `QFont` values in
`plugins/common/tag_manager.py` and `config_factory.py`. They are value types and are created on the worker. A plugin
that creates a widget or a QObject in its constructor would break this; the rule for plugin authors is in the hook
docstrings. `load_game_plugin` clears plugin modules, so a count and a load of one plugin can race. One count job
runs at a time, which limits the race to a load in the middle of a count.
**Cost.** Counts skip archive members and report them. A count reads the files of each project again when the
project file changes. Only `plugins/plain_text` declares a build target in this change; it copies the translation
files.

**Addendum (2026-10-12).** Every import of a game plugin takes the `PLUGIN_IMPORT_LOCK` of `utils/plugin_import.py`: the
Project Manager's `default_load_rules` and the main window's `load_game_plugin` (forget and import). The count
worker and the main window no longer see each other's half-dropped modules; a test checks that a worker waits while
the lock is held. The cost is that a plugin load waits on the UI thread for a count that is importing the same
plugin. Ctrl+N and every New Project entry open the wizard; `NewProjectDialog` is no longer opened.
