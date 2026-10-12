---
status: current
updated: 2026-10-12
owns: decisions and their reasons
tokens: 7.9k
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
  in-app host keeps its token in `collab.json` per name. When that token is not the room's host, the app issues a new
  creation token and the previous host becomes a moderator, so the room stays manageable.
- **Claims.** A scope is a project, folder, file, block, row or virtual folder. The client sends the row keys under
  the scope; a claim on a folder covers every row inside it. The server keeps a row-to-claim index and the smallest
  claim wins. A free area is granted at once. An area that another member holds becomes a request to the host and
  moderators; approving a request takes the area from its owner. Claims persist when the owner leaves; the owner, a
  host or a moderator releases them.
- **Edits.** Translators, moderators and the host edit. A claimed row is edited only by its owner. A refused edit comes
  back with the room's text and the reason, and the window puts the room's text back in place.
- **Comments.** A thread per scope (row, file, block, folder, virtual folder, project) with author, time, text and a
  resolved flag (who, when; can be reopened). The author deletes its own comment; a host or moderator deletes any.
  Comments are kept in the room journal and in `comments.json` next to it, both written atomically on the journal timer.
- **Approval.** Reviewers, moderators and the host mark a row approved. A text change clears the mark. Approval is not
  a claim.
- **Presence.** Entering a row that someone else works on shows a soft warning. Nothing is locked.
- **Removal.** A kick is a ban until a host or moderator allows the participant back. Host and moderators cannot be
  removed. Moderator actions go to a log that only the host sees.
- **Operations.** Each change is an operation with an `op_id`, a `kind`, its payload and an optional `seq`. `seq` counts
  per member from 1. The server applies a `seq` above the member's high-water mark only; a repeat answers
  `duplicate` and changes nothing. `POST /ops` takes up to 500 operations with the room id; `GET /ops?since=` is the
  same feed as `GET /events`. The legacy `POST /edits` and `GET /events` remain. A poll that is further behind than the
  kept events gets every row plus a `snapshot` of members, claims, requests and comments.
- **Journal (one deliberate change).** The room journal (`collab_room.json`, protocol 2) stores the current state, the
  sequence number, each member's high-water mark and the last 500 log entries. It does not store the full operation
  list: that list grows without limit and the journal is written every two seconds while the room changes. The event
  window (`EVENT_LIMIT`) lives in memory. A protocol 1 journal still loads.
- **Headless room.** `python -m core.collab.server --headless --port N --password-file F --project-dir D`, with
  optional `--host`, `--owner-name` and `--owner-token-file`. The module imports no Qt. The fingerprint comes from the
  journal in D; without a journal, the first join with the creation token sets it and other joins wait. The process
  prints one JSON line (`port`, `room_id`, and `owner_token` when it is issued and not written to the token file).
  The journal is written on close and within two seconds of each change; a `terminate()` on Windows skips the close,
  so the last two seconds can be lost.
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
  a worker and merges it by comment id, but only when the file came from another room: a file of this room is the
  room's own copy, so a deleted comment stays deleted. A resolution takes the later time.
- **Saved rooms.** The user may tick "Remember this room": the address, the name and the password go to the computer's
  settings (`collab.json`, next to the AI keys in `settings.json`). The list is empty on a fresh profile; a saved room
  connects only when the user presses Connect. A test checks that a fresh profile makes no network call and that the
  password never reaches the project folder.
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
