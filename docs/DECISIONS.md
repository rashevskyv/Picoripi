---
status: current
updated: 2026-10-12
owns: decisions and their reasons
tokens: 15.3k
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
## D22. Work together: roles, claims, comments, operations and a headless room (2026-10-12, owner)

**Context.** A room (D18) shares rows. Translators need to reserve parts of the game text, the host and moderators
need to assign and review, comments must outlive the room, and the room must run on a neutral machine as well as on
the host's own computer.

**Decision.**
- **Roles** belong to a participant token: host (one; the host transfers the role with a confirmation, and the old
  host becomes a moderator), moderator (any number, set by the host), reviewer (approves rows, does not change text),
  translator (the default at join), observer (reads and comments). `core/collab/roles.py` is the one permission table;
  the server asks `allowed(role, action, target, new)` before every operation, and the UI only hides what it refuses.
- **Identity.** A token is issued at join and kept by the server only as its SHA-256 hash. A join with a known token
  gets the same member back, with its role, claims and operation high-water mark. The same name with another token is
  refused while the first is online. A removed token is refused at join, not only at the next poll.
- **Creation token.** A room starts with a creation token; the first joiner that presents it becomes the host. The
  in-app host keeps its token in `collab.json` per room address and name (a host restarted on another port starts
  with a new token). A token is sent only to the address it was kept for; a new room at an address starts its names
  over; tokens kept by name by an earlier version are dropped. When that token is not the room's host, the app issues a new
  creation token and the previous host becomes a moderator, so the room stays manageable.
- **Claims.** A scope is a project, folder, file, block, row or virtual folder. The client sends the row keys under
  the scope; a claim on a folder covers every row inside it. The server keeps a row-to-claim index and the smallest
  claim wins. A free area is granted at once. An area that another member holds becomes a request to the host and
  moderators; approving a request takes the area from its owner. Claims persist when the owner leaves; the owner, a
  host or a moderator releases them.
- **Edits.** Translators, moderators and the host edit. A claimed row is edited only by its owner. A refused edit comes
  back with the room's text and the reason, and the window puts the room's text back in place.
- **Comments.** A thread per scope (row, file, block, folder, virtual folder, project) with author, time, text and a
  resolved flag (who, when). Observers cannot resolve. Anyone who may resolve can reopen; reopening a comment that
  another member resolved needs its author, a host or a moderator. The author deletes its own comment; a host or
  moderator deletes any. Comments are kept in the room journal and in `comments.json` next to it, both written
  atomically on the journal timer.
- **Approval.** Reviewers, moderators and the host mark a row approved. A text change clears the mark. Approval is not
  a claim.
- **Presence.** Entering a row that someone else works on shows a soft warning. Nothing is locked.
- **Removal.** Removing a participant blocks its token and its name (compared without case) until a host or moderator
  presses Allow back. A host cannot be removed; a moderator cannot be removed by a moderator, nor by the host until its
  role is changed. A removal is not an access control: anyone with the room password can join under a new name with a
  new token. To keep someone out, the host changes the room password. The ban is held in the journal (`banned_names`).
  Moderator actions go to a log that only the host sees.
- **Operations.** Each change is an operation with an `op_id`, a `kind`, its payload and an optional `seq`. `seq` counts
  per member from 1. The server applies a `seq` above the member's high-water mark only; a repeat answers
  `duplicate` and changes nothing. An operation without `seq` is applied once per member and `op_id`: the last 20,000
  ids are kept in memory, so a restart forgets them. A field of the wrong type fails that operation with `bad
  operation`; the batch goes on. `POST /ops` takes up to 500 operations with the room id; `GET /ops?since=` is the
  same feed as `GET /events`. The legacy `POST /edits` and `GET /events` remain. A poll that is further behind than the
  kept events gets every row plus a `snapshot` of members, claims, requests and comments.
- **Journal (one deliberate change).** The room journal (`collab_room.json`, protocol 2) stores the current state, the
  sequence number, each member's high-water mark and the last 500 log entries. It does not store the full operation
  list: that list grows without limit and the journal is written every two seconds while the room changes. The event
  window (`EVENT_LIMIT`) lives in memory. A protocol 1 journal still loads.
- **Headless room.** `python -m core.collab.server --headless --port N --password-file F --project-dir D`, with
  optional `--host`, `--owner-name` and `--owner-token-file`. The module imports no Qt. The fingerprint comes from the
  journal in D; without a journal, the first join with the creation token sets it and other joins wait. The process
  prints one JSON line (`port`, `room_id`). A new creation token goes to the token file; without a token file it is
  printed on stdout only with `--print-token` (stdout is a log), and without either the room does not start. A
  headless room started again with the same token file lets whoever holds that file take the host role back: that is
  the design, the file holder is the owner. The creation token file is written atomically; its access rights are those
  of the folder it sits in, so keep it out of shared folders.
  The journal is written on close and within two seconds of each change; a `terminate()` on Windows skips the close,
  so the last two seconds can be lost. Journal writes run one at a time, and each snapshot is taken just before its own
  write: an older copy cannot land after a newer one, so a deleted comment stays deleted in `comments.json`.
- **No open endpoints.** `/hello` was removed. Joining needs the room password; every other endpoint needs the room
  token. No remote endpoint is contacted by default: joining is an explicit action in the window.

**Cost and limits.**
- Plain HTTP; the password is a shared secret, not encryption (as D18).
- A room lives while its process runs. A headless room needs a machine that stays on.
- An offline participant's changes reach the room only when it reconnects. The offline-first package below is the fix.
- Leaf rows of the block tree get no marker; the row bar shows the row's claim, presence and comments. Resolved comments
  are not dimmed on the tree.
- The row's menu is on the row bar; the editor itself has no menu of its own.
- A host that lost its token and runs a headless room needs the creation token file (`--owner-token-file`); otherwise
  nobody can take the host role back.

**Second round (2026-10-12, same work package).**
- **Markers.** A block item shows a disc with the initial of the first participant who works there (`+n` for more), a
  lock with the initial of the claim's owner (grey when the owner is offline) and a bubble with the open-comment count.
  The tooltip gives the names, the minutes since each one moved there, and the claim and comment lines.
  `ui/collab_markers.py` draws; the handler decides what each block shows.
- **Read-only.** The editor is read-only for a row the participant may not change (another claim, or a role without
  text rights). The row bar sets and clears that flag only; a read-only editor for another reason is left alone. The
  refusal path still puts the room's text back, as the safety net.
- **Menus.** One scope menu (`ui/collab_menu.py`) for the block tree and for the row bar: Claim for me, Release my claim
  here, Assign to, Comment, Resolve comments here.
- **comments.json everywhere.** Every participant's Picoripi writes the room's comments to the project's `comments.json`
  when they change, atomically, in a worker thread (`core/collab/comments_file.py`). On join the window reads the file in
  a worker. A file of another room is not merged into the window: the host or a moderator adopts its comments into the
  room (`comment_import`), and the room skips a comment it already holds or deleted (its deleted ids are kept in the
  journal). A file of this room is never read back. Guests show a foreign file's comments only after the room has them.
- **Saved rooms.** The user may tick "Remember this room": the address, the name and the password go to the computer's
  settings (`collab.json`, next to the AI keys in `settings.json`). The list is empty on a fresh profile; a saved room
  connects only when the user presses Connect. A test checks that a fresh profile makes no network call and that the
  password never reaches the project folder. Settings are kept as a copy in memory: a save changes the copy at once,
  and `SettingsFile` (a worker) writes the file, so no save waits for the disk on the UI thread. Reading the file
  happens once per process, on first use.
- **Error texts.** The room sends English on the wire. The window shows `tr(text)` of each text; every text the room can
  send is a catalog key (a test reads `core/collab/server.py` and checks the keys).

**Test.** `tests/test_core/test_collab_server.py`: the permission matrix, enforcement in `edit`, claims and requests,
approval, comments, identity, removal and unban, host transfer, idempotent operations, the journal and `comments.json`,
the headless start, and that the process imports no Qt. `tests/test_core/test_collab_client.py`: a real server with
real clients (answers, refusals, a token kept across reconnects, removal). `tests/test_core/test_collab_room_state.py`
and `tests/test_ui/test_collab_panels.py`: two windows in one room (mirror, actions, panel gating, tree menu, row bar).
`tests/test_performance.py`: the join and remote-batch bounds of D21 still hold.

**Next package: offline-first sync (design only, not built).** A participant edits offline; the work merges later
through any of three transports.
1. **Operation log per participant.** `collab_sync/journal-<member id>.ops`: JSON lines, append-only. Each line is one
   operation with `op_id` (random), `member`, `seq` (the member's own counter), `lamport` (a new field: the largest
   value seen plus one), `base_rev` for an edit, and the payload. A line applied twice changes nothing, because the
   `op_id` is already known.
2. **Transports.** (a) Any reachable room: `POST /ops` with the local lines above the room's high-water mark for the
   member (the endpoint exists now). (b) An exchange file `.picoripi-sync`: Export writes the lines after a cursor,
   Import reads them. (c) A shared folder (Syncthing, a cloud drive): each participant reads the others'
   `collab_sync/*.ops` files and merges them by `op_id`.
3. **Conflict rules.**
   - Two edits of one row from the same base revision: both stay in the history. The current text is the edit with the
     greater `lamport` (ties: the member id). The row is flagged as a conflict with the same Take theirs and Keep mine
     actions as now.
   - An edit made offline to a row claimed by someone else becomes a **proposal**: it is not applied, and the claim
     owner sees it and accepts or drops it.
   - Comments merge as a set by `id`; the resolved flag takes the last writer by `lamport`.
   - Roles and claims: operations by host or moderator tokens merge by `lamport`; of two claims on the same rows the
     earlier claim wins; a request stays a request.
4. **Interfaces** (a new module beside the server, to create): `Op` (the fields above), `OpLog.append` and `read_since(cursor)`,
   `merge(ops)` returning the changes. `Room._apply_op` stays the only authority path; sync feeds it operations.
5. **Not in this package:** the client writing its log, the exchange file, and the shared-folder reader.
## D24. Family projects: one translation for the strings several consoles share (2026-10-12)

> Superseded in part by D25: the plugin, not core, decides the members and the match key.

**Context.** Twilight Princess (GameCube, Wii, Wii U HD) and Wind Waker (GameCube, Wii U HD) have the same
message ids and mostly the same text. Translating each console separately repeats the work and lets the copies drift.
**Decision.** `core/family_projects/` aligns each console's messages with the family base by their editor text
(translator-visible text, escapes included), with `difflib` on hashes. An aligned message is a unit: translated once in
the family store (`family_translations.json`), written into every console that has the unit. A message only one
console has is that console's override. An override wins for its console only. A console translation that differs
from the unit is kept as that console's override with a warning. Byte-level details (message ids, INF1 attributes)
stay with each console's own writer (`plugins/zelda_bmg/family.py`), and only changed archives are written.
Message ids are not used as the key: the HD BMGs reuse ids (2707 distinct ids in 5000 messages).
**Cost.** Alignment by text can pair a repeated short line with the wrong copy (ponytail: an id key when both sides have
unique ids). Escape differences between consoles make a text unit; they are not warned yet. The Picoripi project with
virtual folders per console is not built yet; the store is fed by the CLI (`python -m plugins.zelda_bmg.family`).

## D25. The plugin declares the family; core is a generic engine (2026-10-12)

**Context.** D24 let core decide what is shared (equal editor text) and read the family from a JSON file given to
a CLI. A Wind Waker or Twilight Princess match needs game knowledge: which sources are which console, which files
are shared bytes (font archives), and what counts as the same message across formats.
**Decision.** Supersedes the "core decides" part of D24. `BaseGameRules.family_plan(sources, project_dir)` returns a
`FamilyPlan` (core/family_projects/model.py): its members (key, label, source, base, parents) and a reader that lists
each member's units as (unit id, text). The plugin recognises each source by its content. Core
(`core/family_projects/`) only aligns units by their match key, stores one text per shared unit, keeps per-member
overrides, and fans texts out. Members link to parents in order (for example HD Msgus links to HD Msguk first, then to
the base), so a unit shared by three consoles is stored once. The user supplies sources only; fewer sources than
members is valid. The CLI (`python -m plugins.zelda_bmg.family`) is a thin wrapper over the same plan.
**Cost.** Each plugin implements its own recognition and reading. Recognition by message-count fingerprint is
exact for the sources on disk, and a new revision of a game needs a new fingerprint. The match key is the editor text
by default; a plugin with different tag syntax per console must normalise it first (Wind Waker: solved in D27).

## D26. Family project folders: "Shared" and "<version> only", for every version alike (2026-10-12)

**Context.** The first Twilight Princess project kept the GameCube messages in the main tree and put only the other
versions' own messages in folders. That made the base special, and the "HD Msguk only" folder held messages that the
Msgus slot also has.
**Decision.** A unit tree (one message plus its linked copies, `core/family_projects/store.py` `trees`) is one project
message. A tree of more than one version is in "Shared" (rooted in the base) or "Shared <label>" (rooted in another
version). A tree of one version is in "<label> only", the GameCube included ("GC only"). The store is unchanged.
`normalize` moves a tree's text onto its root; a text below the root that differs is an override, and the project
build refuses it until a family has such texts. Files a member takes from the base byte for byte are declared in
`FamilyPlan.shared_files` (file -> members); `family.py shared` copies them.
**Cost.** A text that differs below the root cannot be shown in the project yet (none for Twilight Princess).
**Naming (documented, not renamed).** The Wind Waker base tree is in a folder named `.extracted`, not "Shared".
`.extracted/` is the project's folder for extracted archive sources (`core/project/blocks_mixin.py`).
`plugins/zelda_ww/family.py` `count_project` and `tests/test_plugins/test_zelda_ww/test_family_real.py` rely on the name.
It is kept: a rename would change existing project folders. Twilight Princess uses "Shared".

## D27. Wind Waker: one syntax-free match key, the tag table derived from the files (2026-10-12)

**Context.** Wind Waker GameCube (BMG) writes a control tag as `{escape:TYPE:HEX}`; Wind Waker HD (MSBT) writes it as
`[Size:150]`, `[Wait:10]`, `[/C]`. Equal editor text matched 23 % of the GameCube messages. D25 left the tag syntax open.
**Decision.** `plugins/zelda_ww/family_tags.py` maps the two syntaxes. `plugins/zelda_ww/family_tag_map.json` is derived
from the decoded files (`python -m plugins.zelda_ww.family_tags derive <bmg> <msbt>`): messages with the same id in
both versions, compared with tags and icons removed; each tag pairs with the HD tag it co-occurs with at the same text
offset (Jaccard score at least 0.5; each HD tag used once). Colour (escape 255, type 0) and scale (type 1) follow a rule
the catalogue names and the data confirm. The match key converts GameCube to HD syntax, folds curly quotes (the
GameCube editor shows them, HD does not) and drops colour. Shared text is stored in GameCube syntax and converted to
HD syntax on write; HD-only messages keep HD syntax in their own folder. The engine pairs equal keys with
`align_by_key` when a family sets `exact_keys` (D24 alignment stays for Twilight Princess).
**Cost.** The table is a snapshot of one game revision; a test re-derives it. Three HD tags have a conflicting partner
and stay per-version. Colour 0 is written as `[/C]` (box default); `[White]` reads back as the same colour.
Messages with an unmapped tag never match. Only the GameCube plugin (`zelda_tww`) opens the family project; it reads
MSBT blocks by their magic, but its editor tag highlighting and checks still use GameCube syntax (open).

## D28. The Project Manager scans in a child process, keeps a signature cache and updates rows in place (2026-10-13)

**Context.** The first scan of 191 projects froze the window for minutes. Measured on the unchanged code: heartbeat
gaps up to 2.2 s (117 gaps over 250 ms), 54 tracebacks from binary fonts read as text, and the list rebuilt about 150
times during the scan. The rebuild (`tree.clear()` and 191 new rows) took 42 s of UI-thread time and reset the
scroll position. Counts for a project were recomputed on every start, and a count for an open project carried no
signature, so it was recounted too.
**Decision.**
- The scan runs in a child process: `python -m core.project_library.scan_child`, started with `QProcess` from the
  window. The job arrives on stdin as JSON; the child writes one JSON line per event (`card`, `icon`, `plan`,
  `progress`, `counts`, `done`) on stdout, and plugin `print()` goes to stderr. The child runs at below-normal
  priority and sets `PICORIPI_SCAN_CHILD=1`, which keeps `utils.logging_utils` from truncating `app_debug.txt`.
  The window closes the child at once on close and on a new scan. Cancel writes the line `cancel` to the child's
  stdin: the child stops between projects (and between blocks inside a count), ends with `done` (`cancelled: true`),
  and exits 0. A child still running after `CANCEL_GRACE_MS` (2 s) is killed; what it already wrote stays.
  The child's stderr lines go to the app log as warnings (`Project scan: ...`); the child's own warnings and plugin
  `print()` lines are the same channel.
- The scan has two phases. Phase 1 reads each card, works out the icon, and computes each project's input signature
  (the project file, the plugin's `config.json`, the stat of every Python file of the plugin and of the shared
  `plugins/common` folder, the Picoripi version `APP_VERSION`, and the stat of every source and translation file its
  blocks name). Phase 2 counts only the projects whose signature changed. A second start with nothing changed parses
  no string content.
- The version and the Python files make a parser update recount the affected projects, without a manual cache reset.
  Ceiling: the core parsers (`core/formats.py`, the format modules outside the plugin folders) are covered only by the
  version. A dev build that changes them without a version bump keeps stale counts. Upgrade: add a stat stamp of the
  core parser modules when that happens in practice. Only `stat` is called; no file content is read.
- The cache lives in `project_index.json` (card by mtime and size, counts by signature) and `pm_icons/` (PNG per
  project). Folder modification times are not used: on NTFS they do not change when a file inside is edited.
  `record_counts` stores the signature of the files on disk when a project is saved, so an open project is not
  recounted on the next start.
- Counting skips a file that no format of the plugin claims. It never reads it as text. A project whose plugin is
  not installed gets `count_error = plugin_missing` (shown as a flag) and is not counted. One summary line ends a
  scan.
- Rows update in place: when only cells, icons or counts change, the same `QTreeWidgetItem` objects get new text
  and data. The order does not change while a scan runs; a regroup or re-sort happens when the scan ends or the
  view changes. A rebuild (a project added or removed, a view change) keeps the scroll value, the selection and the
  open details.
- The list has two views: a list (`QTreeWidget`, the default, with groups) and a grid (`QListWidget` in icon mode,
  flat). The progress strip shows "Scanning N of M — name — about X left"; the time left is a moving average of the
  time each counted project takes.
- Icons: `icon.png` beside `project.uiproj` wins; a plugin may return PNG or JPEG bytes from the optional hook
  `project_icon(project_dir)`; otherwise a generated tile. The image is decoded with `QImage` on a worker, never on
  the window's thread at paint time.
**Thread safety.** The child has its own `sys.modules`, so the plugin import lock of D23 no longer guards the scan
against the window's plugin load. The window's own loads still use `PLUGIN_IMPORT_LOCK`.
**Cost.** The first scan of 191 projects takes about 4 minutes in the child (plugin parsing is CPU work), but the
window stays responsive: heartbeat max gap 202 ms (was 2154 ms), 0 gaps over 250 ms (was 117). The render time falls
from 42 s to 2 s. A frozen (PyInstaller) build would need a scan entry point; no frozen build exists. Icons changed
while the window is open appear at the next scan (open or Reload); there is no file watcher.

## D29. Game icons: an offline harvester writes icon.png; the app reads only icon.png (2026-10-13)

**Context.** Two branches each added project icons. The Project Manager reads `picoripi/icon.png` and the optional
`project_icon` plugin hook (D28). `core/game_icons` reads a picture from a game's own files (3DS, DS, GameCube, Wii,
Switch, PE, PSP).

**Decision.**
- One mechanism. `scripts/harvest_project_icons.py` extracts a picture and writes `icon.png` beside
  `project.uiproj`. It uses the Project Manager's atomic PNG writer (`core/project_library/icons.py`) and keeps the
  native size.
- The app does not extract game icons. A plugin that wants its own picture returns it from `project_icon`.
- A harvested icon never replaces an existing `icon.png`. The script is a dry run unless `--apply` is given.
- Game art is never committed to the repository.

**Consequences.** The harvester has one write path. A harvested icon shows at the next scan, because the scan reads
the file's size and time. A second extraction path inside the app would need a new record.

## D30. Unpack in Picoripi: Picoripi reads GameCube and Nintendo DS images itself (2026-10-13)

**Context.** The zt scripts unpack game images outside Picoripi (DolphinTool, ndstool, Python). D23 gave the
new-project wizard a `unpack_sources` hook, but no plugin implemented it, so a project could not start from a disc
or a cartridge in the app.

**Decision.**
- Readers in `core`, pure Python, streamed, with cancel between chunks: `core/containers/gcm.py` (GameCube ISO
  and GCM: header, file system table, `sys/` and `files/` as DolphinTool writes them) and `core/containers/nds.py`
  (Nintendo DS ROM: header, file name table, file spans; `main.arm9` is the ARM9 program). Both share the entry type
  and the copy in `core/containers/image_files.py`. The NitroFS name walk is in core; `plugins/zelda_ds/rom.py` calls it.
- One helper for plugins, `core/project_library/images.py`: `identify` reads the header only and recognises the image
  by content, `base_identity` gives the role and platform for a list of game codes, `open_image` and `extract` write
  the files a plugin selects. `extract` returns None on cancel. Formats it does not read (RVZ, WIA, NKit, Wii) raise
  `ImageError` with the reason. Nothing is converted.
- A plugin chooses its files in its own `unpack.py`. The list is the list its zt script copied, not a new rule.
- Wired in phase 1: The Wind Waker (GameCube, GZLE01), Paper Mario: The Thousand-Year Door (GameCube, G8ME01),
  Phantom Hourglass and Spirit Tracks (AZEE, BKIE), Four Swords Anniversary (KQ9V), Revenant Wings (AXFP), Infinite
  Space (C6CP), The World Ends with You (AWLP).
- Not wired, because the zt step makes more than a copy: Eternal Darkness (decompresses EDASC into `source\game`),
  Twin Snakes (splits text out of two discs), Metroid Prime GameCube (explodes packs), Castlevania DS (writes a string
  bank), Pokemon DS (splits NARC members into blocks), Layton DS (splits GFSA members), Tactics A2 (joins `pc.bin`
  members), Dragon Quest IX (keeps GPC2 archives by their English names: later). Twilight Princess GameCube is a
  family project whose source is `res/Msgus`; a whole-disc project has 17 blocks, the workspace project 10.
  That needs a decision first.
- A game with no unpack step still uses the file as it is (GBA ROMs, for example): no `unpack_sources` result, no reader.
- Owner decision on console keys (2026-10-13), phase 2, not built here: no global key setting. The wizard asks for a
  key file only when an added file needs one (3DS, Switch, Wii, Wii U). Picoripi remembers the key file location per
  console, not per plugin or project, in the data folder, and reuses it for any plugin of that console while the file
  is still there; otherwise it asks again. It stores the path only, never copies or logs key values, and never sends
  the path to a Work Together room.

**Consequences.**
- Verified against the workspace on real images (read only, temp folders): file lists and sha256 equal for Wind Waker
  (2218 files), Paper Mario (3209), Four Swords (8), Revenant Wings (120), Infinite Space (616), TWEWY (731), Spirit
  Tracks (215); Phantom Hourglass equal for all 302 workspace files (the current zt script writes 4 more pictures).
- A new project takes the unpacked folder as its source root. A workspace project that points at a subfolder
  (Paper Mario `files\msg\US`) gets the same block count, with longer block names.
- Platform labels go through `tr()` (`locales/uk.json`). Plugins add no dependency.

**Addendum (phase 2a, 2026-10-13).** Wires the zt steps that do more than copy files, with readers already in Picoripi
(NARC, GFSA, Retro PAK, Level-5, the plugins' own parsers). Logic is ported, nothing shells out to zt.
- Wired: Pokemon Diamond/Pearl/Platinum/HeartGold/SoulSilver (Gen 4), Black/White and Black 2/White 2 (Gen 5: text
  banks split per NARC member), Professor Layton DS (GFSA members of Spectre's Call, decompressed Level-5 files),
  Castlevania DS (string bank as `strings.cvdstext`), Final Fantasy Tactics A2 (`pc.bin` members, read by a
  PcArchive port), Dragon Quest IX (GPC2 name filter, the same rule as Infinite Space), Eternal Darkness (EDASC decoder
  in `core/containers/edasc.py`; the encoder is not ported), Metroid Prime GameCube (`metroid_prime_trilogy` plugin,
  MP1 package reader in its `unpack.py`; returns None for any other disc), Metal Gear Solid: The Twin Snakes (two
  roles, `disc1` and `disc2`, identified by the disc number in the header; one disc alone also works), and Twilight
  Princess GameCube (whole disc; see the source root below).
- Source root hook: `get_source_subfolder()` on `BaseGameRules` (default None). It names a folder of the unpacked tree
  that is the project source (`files/res/Msgus` for Twilight Princess GC). `run_unpack` returns that folder and
  raises `ValueError` before any folder is left behind when it is missing. `zelda_tww` overrides it to None.
- Free-space check before unpacking: only when a source is a GameCube or DS image (`images.identify`). Room needed is
  the image size plus 10 %, or 256 MB when that is larger. Too little room raises `ValueError` with a `tr()` message
  before a folder is created.
- NKit GameCube discs are read as they are (the GameCube reader handles their layout). RVZ, WIA, Wii and other NKit
  kinds are refused with the reason. The old NKit message never fired for GameCube discs; the guard order is fixed.
- Limits recorded, not fixed: Eternal Darkness takes about 330 s on one thread (zt uses a 7-process pool); Metroid
  Prime has no `identify_source`, so the wizard takes its role from the user; Twilight Princess and Metroid Prime
  PAL and JP discs are not recognised; the Metroid and Eternal Darkness unpacks are checked on one USA disc each.
- Verified on real data (read only, temp folders): Gen 4 ADAE, APAE, CPUE, IPKE equal for every written file
  (IPGE: one file differs, `a/1/3/3`, a version difference); Gen 5 IRBO and IREO equal; Layton Pandora's Box and
  Spectre's Call equal; Lost Future equal (two stale workspace files not produced); Curious Village 65 extra `.gds`
  scripts (kept; recorded in `docs/OPEN_ITEMS.md`); Castlevania dos 74, por 136, ooe 165 files equal; Tactics A2 11 equal;
  DQ9 1751 equal; Twin Snakes 69 files equal with both discs; Eternal Darkness 187 files equal; Metroid Prime 1565
  equal; Twilight Princess `res/Msgus` 10 archives equal, 10 blocks as in the workspace.

**Addendum (phase 2b, 2026-10-13): partial. Decryption is blocked.** The owner's key design is built where it needs no
AES. Encrypted reads stop at the seam; they are not built.
- Blocked: the pinned `pycryptodome==3.23.0` (`requirements-dev.txt`) is not installed in the project venv. The install
  was denied by the auto-mode permission check. The brief allows no pure-Python AES and no install into shared Python,
  so every encrypted 3DS, Switch and Wii read raises `encrypted_error` in `core/containers/console_crypto.py`. The
  message names the missing package when it is missing. The owner runs `install_picoripi_crypto.bat` (in the owner's
  `_shared\scripts` folder, not in the repo; see `docs/OPEN_ITEMS.md`) to install the pin; the decrypt bodies follow in
  phase 2c.
- Built, no key needed: `core/containers/n3ds.py` reads a decrypted (NoCrypto) main program in a card image (`.3ds`,
  `.cci`), a CIA, or a bare NCCH (`.cxi`, `.cfa`). Files: `exheader.bin`, `exefs/<name>.bin` (the workspace name:
  `.code` is `code.bin`) and `romfs/<path>` (IVFC level 3, UTF-16 names, every table pointer bounds-checked, every name
  through `check_name`).
- Built: `core/project_library/console_keys.py`, the key file location per console (`3ds`, `switch`, `wii`). It is
  one JSON file in the data folder, written atomically. It keeps the path only; `path_for` returns a path only while the
  file exists. It is not part of any project and never goes to a Work Together room.
- Built: `console_crypto.key_source`, a job-scoped key lookup. `build.run_unpack(key_provider=...)` sets it around
  `unpack_sources`; `UnpackJob` passes `console_keys.path_for`. No hook signature changed.
- Built: the wizard asks, on Create, for one key file per console that a file with a role needs and that has no live
  stored path (`ui/project_manager/wizard.py`, `_ask_key_files`). The job writes the chosen paths on its worker thread.
  Plugin facts report `key` and `key_ready` per file (`plugin_facts.identify_sources`).
- Built, identify only: a Switch NSP takes its title ID and kind (base, update, dlc) from the plain-text `*.cnmt.xml`,
  or from the rights ID of its ticket (`0x2A0`) when it has no content meta. An XCI is recognised with no title. A Wii disc
  gives its game ID (magic at `0x18`). `images.identify` returns `encrypted`; `images.needs_key` gives the console for an `UNPACK_KINDS` kind only.
- `images.UNPACK_KINDS` (GameCube, Nintendo DS, 3DS, Switch, Wii) decides what the free-space check counts: every game image an unpack step reads needs the room.
- No plugin is wired. No shipped plugin unpacks a file this phase can read: retail `.cia` files are encrypted, and the
  decrypted dumps are not a plugin input.
- Verified (read only, no key): synthetic 3DS images in `tests/test_core/test_n3ds_image.py`. Real data (gated by
  `PICORIPI_ROMHACKING`): the decrypted Majora's Mask 3D CXI has 2139 RomFS files, all equal by sha256; its exheader and
  ExeFS banner are equal; the decrypted Update CIA is read and its `code.bin` and `icon.bin` equal the workspace. Eight Switch NSP filenames carry a title ID, and `identify` returns the same ID for
  each of them (base, update, DLC; the Legends Z-A NSP has no ticket and reads from its content meta).
- ExeFS code: when the exheader flag (byte 0x0D, bit 0) says the code is packed, `exefs/code.bin` is decoded with the
  BLZ decoder in `core/containers/nitro.py` as it is written (`ImageFile.decode`). Verified: the Update CIA's
  `code.bin` decodes to the workspace file byte for byte (5971968 bytes), through the reader.
- Icon and code origin: the workspace `exefs` (code, icon) equals the Update build, not the base game. The base
  CXI's icon differs from byte 12480 on, and the base code decodes to a different binary. The base extraction is
  right; the workspace ExeFS came from the Update. The workspace romfs and banner are the base game's (equal to the
  base CXI). The Update CIA has no `banner.bin`.
- The workspace also holds `romfs/version.ctxb`, which is not in the RomFS.
- Risk: until a Switch plugin exists, the wizard also asks for a key file for an encrypted Switch file that no plugin
  unpacks. The prompt is shown only for a file that has a role.

**Addendum, phase 2c (2026-10-14).** Picoripi decrypts 3DS, Switch and Wii images itself, with the owner's key file. Nothing is verified against a real key yet; the owner runs `verify_unpack_keys` for that.
- Views: `console_crypto.py` gives `PlainView` (a seekable decrypted view), `RangeView` (no crypto), `CtrView` (AES-CTR) and `CbcView` (AES-CBC). An `ImageFile` takes an optional `stream` (a view), so a decrypted entry is read in chunks and never held whole. `images.write_entries` reads through `reader.source(entry)`.
- 3DS (`n3ds.py`): NCCH sections decrypt with the keyscrambler. KeyX comes from the key file (`slotNNKeyX=`); a `*boot9*.bin` in the same folder adds KeyX 0x2C..0x3F. KeyY is the NCCH signature. The exheader, the ExeFS header, the icon and the banner use slot 0x2C; other ExeFS files and the RomFS use the slot of the NCCH crypto method. CIA content uses its title key, from the common key (`commonN=`). Version 1 counters follow 3dbrew. Refused: fixed-key titles (flag 0x01). A flag 0x20 title is tried with the signature KeyY; if the tables do not parse, the key file is reported as wrong.
- The RomFS walker moved to `core/containers/romfs.py` (3DS). The Switch RomFS has its own walker (see OPEN_ITEMS).
- Switch (`switch_crypto.py`, `switch_images.py`): NSP only. Program NCA by content type; header XTS with the header key; key area with the key area key of the generation (`max(0x206, 0x220) - 1`, as `zt/hwde_extract.py`); section CTR; ticket title key with titlekek. Derived keys in the file are used directly; otherwise they come from `master_key_XX` and the source keys. The XTS tweak, the derivation chain and the ticket fields are from the public formats, not verified against a dump.
- Wii (`wii_disc.py`): `keys.bin` (exactly 0x400 bytes, common key at 0x158). The data partition's title key is decrypted from the ticket (common key index 0 only). Cluster data uses the IV at 0x3D0 of the encrypted hash block (wiibrew "Wii Disc" and Dolphin). Hashes are not verified. The GameCube FST walk is copied, with the `<< 2` shifts, because `gcm.py` reads the raw disc only.
- Key files: 3DS `aes_keys.txt` (with boot9 beside it), Switch `prod.keys`, Wii `keys.bin`. Key bytes live in memory for one job. No error text, log line or room message contains a key value or a key file path.
- `images.UNPACK_KINDS` now also covers Switch and Wii, for the key prompt and the free-space check. Audit r18 removed the r17 split (`images.SPACE_KINDS`): a Switch or Wii image counts for room, since these are the largest images.
- Plugin hook `unpack_key_consoles()` (`BaseGameRules`, spec, PLUGIN_CONTRACT, D30 wizard rule): a plugin lists the consoles whose key its unpack reads. The wizard asks for a console's key only for an encrypted file of a listed console (`plugin_facts.identify_sources`). This closes the 2b risk that the wizard asked for Switch or Wii keys that no plugin used. Default: none.
- Requirements: `pycryptodome==3.23.0` moves into `requirements.txt`. The app imports it at run time, when a user unpacks an encrypted image. The dev file keeps the same pin. The reader checks `importlib.util.find_spec("Crypto")` first, so a missing package gives the pycryptodome message and not a raw ImportError.
- No plugin is wired. Plugins whose workspace unpack is a plain extraction are the 3DS zt scripts that run `ctr3ds.main(... "extract" ...)`, but each also copies text, builds a CXI or needs the seed database. The wiring needs a per-game check with the owner's workspace and is left open.
- Departures from the phase 2c brief, recorded: the Wii data IV follows the encrypted hash block (both sources agree), not the decrypted one; the Switch key generation follows `hwde_extract.py` (no ticket field).
- Verification: synthetic tests with generated keys (3DS: `test_n3ds_decrypt.py`; Switch: `test_switch_crypto.py`, `test_switch_image.py`; Wii: `test_wii_image.py`); the real MM3D decrypted CXI and CIA regression (`test_n3ds_real.py`, `PICORIPI_ROMHACKING`) passes after the entry-source change. The owner's `verify_unpack_keys.py` (outside the repo, in the RomHacking `_shared\scripts` folder) runs one real image with its key file and compares it with the workspace.
- Owner run, 2026-10-14 (`verify_unpack_keys_all.bat`): 3DS and Switch decryption verified on real data; Wii not run.
  - 3DS, Miracle Mask CIA against its workspace: 719 workspace files, 718 equal by sha256, 0 missing. RomFS and ExeFS equal. The one difference is `exheader.bin`: byte `0x0D` (bit `0x02`, SDApplication, which the CIA build has and the cartridge build does not) and `0x400`-`0x5FF` (the AccessDesc signature and NCCH public key, which the CIA and cartridge builds sign differently). The reader keeps bit `0x01` (CompressExefsCode), as the workspace does: the workspace exheader equals the decrypted `.cci` exheader, and its `code.bin` is decoded, as ours is. No change to the exheader was needed.
  - Switch, Skyward Sword HD base NSP against its `romfs` workspace folder: 162 workspace files in `exefs` and `romfs`, 161 equal. The one difference, `romfs\EU\Object\nl_NL\5-CenterField.arc` (workspace 234554 bytes, dated 2026-10-04; ours 234522 = the RomFS table size), is most likely an edited workspace file; not confirmed.
  - Wii: unverified. The workspace holds no `keys.bin` on this PC.
  - Miracle Mask is not seed-crypto (the earlier phase 2b note that said it was is wrong; see OPEN_ITEMS).

## D31. Super Mario Sunshine (GameCube GMSE01 Rev 0): BMG encoding 0, an in-place disc writer, a speech-balloon patch (2026-10-14)

**Context.** The disc is the owner's GMSE01 Rev 0 (USA). Its 171 BMG files all carry encoding byte 0, which
`bmg_tool` rejected. Dolphin runs the retail `main.dol`, which reads every byte from 0x80 up as a two-byte lead, so
single-byte Cyrillic breaks in speech balloons. No GameCube writer existed in Picoripi. Facts come from the decomp
(CC0) and the port's notes (MIT); no code was copied.

**Decision.**
- `bmg_tool.ENCODINGS` gains `0: cp1252`. The existing Shift-JIS fallback reads the four `pinnaBeach*.szs`
  `dolpic1.bmg` files. Other games with byte 0 raised "Unknown encoding ID" before; they now load. Keep 1 after 0 in
  the table: `ENCODINGS_REV` maps cp1252 back to 1.
- Four `dolpic1.bmg` (Shift-JIS, `pinnaBeach*.szs`) do not round-trip their INF1. Cause, measured 2026-10-14: their
  DAT1 starts with the first text, not with a NUL byte. The save path writes every INF1 string offset one higher
  (1-based, as in the other files, which start with a NUL). It is a base offset, not the entry size (8 bytes here).
  The build refuses any change to a BMG's INF1 (`plugins/super_mario_sunshine/build.py`). The other 167 round-trip
  byte for byte (`test_real_disc.py`).
- `core/containers/gcm_writer.py` writes a disc: it streams a copy to `<out>.tmp`, overwrites a changed file in
  place, zero-fills a shorter one, moves a grown one to the first free 0x8000-aligned gap, patches its FST entry, and
  replaces `out` at the end. It adds no files, changes only `sys/main.dol` (same size) among the system files, and
  refuses the source as output. Measured on this disc: an unchanged rebuild equals the source byte for byte; the
  DOL patch changes only its four words.
- The speech-balloon fix is four words of the retail `main.dol` (`plugins/super_mario_sunshine/dol_patch.py`): sites
  A, C and D compare with 0x100 instead of 0x80; site B replaces `extsb r3,r3` with `ori r3,r3,0` so the width lookup
  stays unsigned. Each word is checked before it is written, so another executable is refused. `gc_iso` applies it
  when the translation changes any file. Owner decision, 2026-10-14.
- The port pack (`port_pack`) writes each changed archive member under `files/<archive path>/<member>`, the port's
  overlay rule. It never writes `sys/main.dol`: the ports do not read it from the disc.
- `ContainerManager` now registers `.szs` for the project scan. The extension list is global, so other games' `.szs`
  files that are RARC or U8 are opened as archives too. Check those projects after the change.

**Cost and limits.** Cyrillic coverage of the font is not drawn here (the translator's job). Dolphin proof: the disc
on disk is a damaged download: the file ends in an HTML page at 0x4F800000 (1272 MiB) and the file table reaches
0x57058000, so 16 entries (common, title, select, mario, particle and others) are missing. A complete GMSE01 Rev 0
dump is needed before unpack, Dolphin and the Picoripi project can work. Open: the shipped DOL text, the Shift-JIS
display in `dolpic1` on NA, the tag catalogue (Twilight Princess tags are used for now).

## D32. Super Mario Sunshine: no global container registration; archives as folders; the executable's text (2026-10-14)

**Context.** D31 registered `.szs` (and `.dol`) with `ContainerManager`. The registration is global: the project scan
then opens every `.szs` and `.dol` of every game as an archive (`core/project/blocks_mixin.py`, `archive_extensions`),
which changes how other games' projects are read. The four `dolpic1.bmg` files did not round-trip because the BMG save
always writes a leading NUL in DAT1; their DAT1 starts with text.

**Decision.**
- Picoripi registers no container for this plugin. `unpack_sources` turns each RARC `*.szs` under `files/` into a folder
  of its members (`files/data/scene/bianco0.szs/map/message.bmg`), the same layout as the port overlay. The GameCube
  build rebuilds a changed archive from the disc's own copy (`build._archive_bytes`) and keeps Yaz0 when the disc has it.
- The executable's English text is one editable file, `sys/main_strings.dolstr` (JSON), written at unpack. Eleven plain
  strings: the progressive-scan question, Yes, No, the card title, the English save comment and the six disc-error lines.
  Each has its retail room (English length with its NUL). A text that does not fit, or has a character outside one byte
  (cp1252), is refused. The two progressive-scan confirmations with escape codes are not in this version
  (`plugins/super_mario_sunshine/dol_text.py`). A changed text is written into `sys/main.dol` at build, and the speech fix
  follows (`dol_patch.ensure`).
- The BMG save keeps each file's own DAT1 base: a file that starts DAT1 with text (dolpic1) keeps its string offsets.
  Files with a leading NUL are unchanged. The INF1 guard stays: a change to INF1 is refused.
- Measured on the reference `main.dol` copy (SHA-256 13934c86...9955): an unchanged document reproduces the executable
  exactly; a shorter text changes only its own room.

**Supersedes** the `.szs` and `.dol` registration bullets and the "INF1 refused for four files" cost of D31.

**Cost.** The disc on disk is now a new download in progress (`_new\Super Mario Sunshine (USA, Canada).rvz`, 0 bytes and
a `.part` file, 2026-10-14). The original ISO is not at its path, so the four real `dolpic1` round-trips and the real
archive folder test cannot run until a complete image is back. The English executable text has not been tested in
Dolphin.
