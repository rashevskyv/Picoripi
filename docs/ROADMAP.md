---
status: current
updated: 2026-10-13
owns: work packages, order of work
tokens: 1.2k
purpose: Master plan: the work packages of Picoripi, their state and the order
---
# Road map

One page for "where are we". Details live in the page named in the last column. Update the state when a package
changes; the integration rounds in `docs/OPEN_ITEMS.md` carry the per-change record.

State: `done` is on `origin/main`; `branch` is finished on a branch and waits for an integration round;
`doing` is in progress; `next` is decided and not started; `idea` is not decided.

## The application

| # | Package | State | Notes | Home |
|---|---|---|---|---|
| A1 | Audit plan 2026-10 (rules, tests, review queue) | done | 0.3.150 | `docs/audit/2026-10-01/` |
| A2 | Project Manager, phase 1 (groups, tree, import from folder, startup) | done | `origin/main` 670e8b63 | `docs/DECISIONS.md` D20 |
| A3 | Portable data folder, never a silent default, import script | done | | `docs/DECISIONS.md` |
| A4 | Work Together, v1 (rooms, presence, revisions, conflicts, journal, bounded join and remote turns) | done | | `docs/wiki/13_Working_Together.md`, D18, D21 |
| A5 | Series memory, forms of address, glossary chain, progress page | done | | wiki 1, 13 |
| A6 | Work Together, v2: claims, roles, comments, host transfer, headless room server, op API | done | `origin/main` 1541b1a1; open: quotas, ops dedupe without seq is in memory only | D22 |
| A7 | Work Together, v3: the log is the truth, local files are a replica; offline-first journal (exchange file, shared folder, any reachable room); build stamp (hash of the translation state and the unsynced edits in every build manifest); block-hash check at start | next | after A6; owner decided 2026-10-12 | D22 |
| A16 | Thin client: observers get a read-only web page from the room server; a full web editor later (the server must run all the time, e.g. a VPS) | idea | needs the A6 op API and A7 | D22 |
| A17 | AI through the room: the server holds the key and ticks "AI for participants", a user ticks "send AI requests through the server" and may enter an own key (own key wins); limits per participant, spend counters per participant (no texts, no key), access by role | next | after A6; owner decided 2026-10-12 | D22 |
| A18 | Unpack in Picoripi: phase 1 (GameCube and Nintendo DS images unpacked by the wizard, no keys); phase 2 (console key file per console, Wii and 3DS and Switch images) | doing | phase 1 in integration round 11; phase 2a on `feat/unpack-2a` (the zt steps that do more than copy: Gen 4, Gen 5, Layton DS, Castlevania DS, Tactics A2, DQ9, Eternal Darkness, Metroid Prime GC, Twin Snakes, Twilight Princess GC, source-root hook, free-space check, NKit GC); phase 2b (console keys, Wii, 3DS, Switch) not started | `docs/DECISIONS.md` D30 addendum, `docs/OPEN_ITEMS.md` |
| A8 | Family projects: one project per game family, plugin decides what is shared, "<version> only" folders | done | TP, WW, DX; the family engine has a command line, the interface is A9 | D25, D26, D27 |
| A9 | Family UI: several folders or images per project, roles of files recognised by the plugin | next | needs A2 and A8 merged | `docs/PROJECT_MANAGER_PHASE2.md` |
| A10 | Project Manager, phase 2 (wizard, unpack recipes, build, export, run, flags) | done | on `origin/main`; integration round 10 (`origin/main` 0e1cf802): Dolphin view and scan process, game icons, Super Metroid, Silent Hill menu language, Oracles, Donkey Kong x3; real plugin hooks per game come with each plugin | `docs/PROJECT_MANAGER_PHASE2.md` |
| A11 | Font Editor: advance width from drawn pixels (menu action done), automatic on save | next | the editor must align the letters itself | wiki 1 |
| A12 | Font formats: NFTR 3-bit and LZ10, SpriteFont XNB, XNB texture | done | Zelda DS, LADX HD; on `origin/main` | `docs/OPEN_ITEMS.md` |
| A13 | Reference files under `source/reference` must not become blocks | doing | separate session | |
| A14 | Hygiene: personal paths in tracked files, provenance of widths tables, slow test on `origin/main` | doing | tests done (guard test, `romhacking_root`); left: personal paths in non-test tracked files, widths provenance | `docs/REVIEW_QUEUE.md` |
| A15 | macOS and Linux checks (no `.exe` or `.bat` assumptions in app code) | idea | | |

## Games (readiness: opens, saves, builds, boots with a visible edit)

The per-game table is the status page generated from `_shared/status/*.json`. In short:

| Group | State |
|---|---|
| Zelda: TP (GC, Wii, HD), WW (GC, HD), SS (Wii, HD), OoT 3D, N64 ports, DS (PH, ST), Oracles, Awakening (DX, DX HD), 3DS | most open, save, build and have a visible edit; letters are drawn by a person |
| Pokémon, Castlevania, Metroid, DKC, Metal Gear, Layton, Dragon Quest, Bravely, others | plugins registered; proofs per game in the status page |
| Silent Hill 1, 2 | Ukrainian builds exist; Switch packages in progress |
| Monster Hunter Portable 3rd HD | project and build done; Yakumo built from source with the translation loader; Cyrillic seen on screen (Character Creation) |
| Wii U (52 titles) | blocked on a console key file |

## Order of work

1. A9 (family UI) on the Project Manager now on `origin/main`.
2. A7 (offline-first journal, build stamp), then A17 (AI through the room).
3. A11, A13, A14 in between rounds.
4. Integration round 10 is done (`origin/main` 0e1cf802; see A10).
5. `feat/manual-3ds-plugin` waits for the owner.
6. A18 (unpack in Picoripi): phase 1 in integration round 11; phase 2a on `feat/unpack-2a` (pending the lead's commit); then phase 2b (console keys).

## How a package moves

`doing` -> `branch` (tests green, wiki and CHANGELOG written) -> audit -> `done` (fast-forward to `origin/main`).
