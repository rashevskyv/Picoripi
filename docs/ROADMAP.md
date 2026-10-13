---
status: current
updated: 2026-10-12
owns: work packages, order of work
tokens: 1.1k
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
| A6 | Work Together, v2: claims, roles, comments, host transfer, headless room server, op API | doing | branch `feat/collab-claims` | D22 (to come) |
| A7 | Work Together, v3: the log is the truth, local files are a replica; offline-first journal (exchange file, shared folder, any reachable room); build stamp (hash of the translation state and the unsynced edits in every build manifest); block-hash check at start | next | after A6; owner decided 2026-10-12 | D22 |
| A16 | Thin client: observers get a read-only web page from the room server; a full web editor later (the server must run all the time, e.g. a VPS) | idea | needs the A6 op API and A7 | D22 |
| A17 | AI through the room: the server holds the key and ticks "AI for participants", a user ticks "send AI requests through the server" and may enter an own key (own key wins); limits per participant, spend counters per participant (no texts, no key), access by role | next | after A6; owner decided 2026-10-12 | D22 |
| A8 | Family projects: one project per game family, plugin decides what is shared, "<version> only" folders | branch | TP, WW, DX; `feat/family-projects-ui`, `feat/family-ww`, `feat/ladx-family` | D25, D26, D27 |
| A9 | Family UI: several folders or images per project, roles of files recognised by the plugin | next | needs A2 and A8 merged | `docs/PROJECT_MANAGER_PHASE2.md` |
| A10 | Project Manager, phase 2 (wizard, unpack recipes, build, export, run, flags) | next | | `docs/PROJECT_MANAGER_PHASE2.md` |
| A11 | Font Editor: advance width from drawn pixels (menu action done), automatic on save | next | the editor must align the letters itself | wiki 1 |
| A12 | Font formats: NFTR 3-bit and LZ10, SpriteFont XNB, XNB texture | branch | `feat/zelda-ds`, `feat/ladx-hd` | `docs/OPEN_ITEMS.md` |
| A13 | Reference files under `source/reference` must not become blocks | doing | separate session | |
| A14 | Hygiene: personal paths in tracked files, provenance of widths tables, slow test on `origin/main` | next | | `docs/REVIEW_QUEUE.md` |
| A15 | macOS and Linux checks (no `.exe` or `.bat` assumptions in app code) | idea | | |

## Games (readiness: opens, saves, builds, boots with a visible edit)

The per-game table is the status page generated from `_shared/status/*.json`. In short:

| Group | State |
|---|---|
| Zelda: TP (GC, Wii, HD), WW (GC, HD), SS (Wii, HD), OoT 3D, N64 ports, DS (PH, ST), Oracles, Awakening (DX, DX HD), 3DS | most open, save, build and have a visible edit; letters are drawn by a person |
| Pokémon, Castlevania, Metroid, DKC, Metal Gear, Layton, Dragon Quest, Bravely, others | plugins registered; proofs per game in the status page |
| Silent Hill 1, 2 | Ukrainian builds exist; Switch packages in progress |
| Monster Hunter Portable 3rd HD | project and build done; needs a Yakumo build with the translation loader |
| Wii U (52 titles) | blocked on a console key file |

## Order of work

1. A6 (claims, roles, comments) and its audit.
2. Integration round 9: A8, A12 and the new plugins from branches.
3. A9 and A10 (needs the Project Manager on `origin/main`).
4. A7 (offline-first journal).
5. A11, A13, A14 in between rounds.

## How a package moves

`doing` -> `branch` (tests green, wiki and CHANGELOG written) -> audit -> `done` (fast-forward to `origin/main`).
