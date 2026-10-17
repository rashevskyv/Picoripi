---
status: current
updated: 2026-10-15
owns: unfinished work
tokens: 37.9k
purpose: Everything left open, one line each, by work package
---
# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Grandia PS1, PC HD Remaster and Grandia II HD (`plugins/grandia`, 2026-10-17)

- Grandia PS1: the plugin lists the PlayStation 1 platform; the wizard unpacks the disc (`core/containers/psx_disc.py`,
  `images.identify`). The input is two RAR archives: Picoripi has no RAR reader, so one extract step runs outside it
  until the owner decides otherwise.
- Grandia PS1 text: field dialogue (`FIELD/*.MDP`) and battle strings (`BATLE/B*.BBG`, `FIELD/WINDT.BIN`) open as
  editor text (`plugins/grandia/psx_text.py`). The writer is bounded: a text keeps its original byte count, and a longer
  text is refused. Growing a text needs the command stream's jumps fixed; not done.
- Grandia PS1 emulator proof: DuckStation has no BIOS on the owner's PC; try PCSX-Redux with its own OpenBIOS.
- Grandia HD Remaster (PC, scene release): the game data is inside `skidrow.bin`, an installer payload with no known
  format. Owner question: a copy of the installed game folder.
- Grandia II HD Remaster (PC, scene release): the image is UDF, not ISO 9660; Picoripi has no UDF reader.

## Super Mario Galaxy 1 and 2 (`plugins/super_mario_galaxy`, 2026-10-15, D39)

- The Wii fonts get the Ukrainian mod's Cyrillic glyphs, scaled from the Switch fonts (`font_port.py`); the mod has
  no ґ, so the builds write г for it. The scaled glyphs are not reviewed letter by letter yet. The Switch fonts
  (little-endian `TNFR`) do not open in the Font Editor.
- Picoripi cannot read a Switch update's RomFS (BKTR). The Switch build takes the update's archives from the imported
  mod; a project without a mod builds on the base game's archives, which lack the update's labels (SMG1 v0 has 2246,
  the mods 2247). The update the Ukrainian SMG1 mod was made for is unknown (its labels are those of the Russian mod,
  which needs v1.3.0 = v196608).
- Switch build not run in an emulator (skipped for now): Eden cannot open the `.nsz` packages (NCZ inside); an NSP is
  needed.
- 73 SMG1 labels (110 in SMG2) are worded differently on the Wii and the Switch, so each has a Wii row and a Switch
  row (warning "Switch translation; Wii English differs"). The SMG1 Wii rows have no Ukrainian yet and build as the
  Wii English; the Wii title prompt ("Press both A and B") is one of them.
- Nebula: the build's `sys/fst.bin` must also replace Nebula's `content\sys\fst.bin` (the runtime loads that copy at
  boot). Setup or repair of Nebula writes it back.
- 132 imported SMG1 messages have other tags than the English (colour and timing tags the translator moved);
  every button picture in a Wii row is now a Wii picture.
- The 22 SMG1 Wii-only labels with text have no Ukrainian yet (the Switch mod does not have them); the Switch
  `System.arc` (6 messages) is not in the mod either.

## Write hardening (audit r28, 2026-10-15)

- Rule 5 (pre-existing): the Font Editor saves a font on the UI thread — `save_changes` repacks the BFN and
  `window_tree_mixin.save_disk_font` reads, rebuilds and writes the archive synchronously. Not moved into a font
  job: `switch_active_bfn_new` loads the next disk font at once, so it must first wait for the save job.
- Rule 9: `io_save_mixin.save_changes` writes `data.json` and `sheet_*.png` with plain `open`/`QImage.save`; in
  extracted-folder mode (no BFN path) these are the user's files, so a crash mid-save can leave them torn.
- `WiaStream.read()` with no size allocates the header-declared disc size at once; only tests call it so.
- `bfn_actions.save_callback` puts the font into the project's in-memory archive before the disk write; after a
  failed write the in-memory archive is ahead of the file until the next save.
- A plugin BFN font's width map, translation map and main-window preview cache are updated before its file is written (unchanged); a failed font
  write leaves them ahead of the file.

## 3DS system menus (`plugins/system_3ds`, 2026-10-15)

- Live preview, phase 2 (`plugins/system_3ds/box.py`, `preview_panel.py`): every string is drawn as a budget box with the console system font, with the real width and line budgets; the status line marks overflow and missing glyphs. Not done: the string drawn in its own layout pane. Layout coverage, measured on the owner's repo_manual folder:
  - (a) layout spec: 1 string (`up_LZ.bin` / `StartTopEU_U_00.bclyt` / `TextBoxTitle_00`, system_settings), rendered in place from a scratch copy of the decrypted romfs. `work\0004001000022000\` has no `romfs`; the owner's folder was not written.
  - (b) user-data labels: a `usd1` section follows the text pane it belongs to, and its entry name is the label. 0 panes are named after a label. 0 text panes hold a label's English as their own default text (the matches are generic words such as "Back"). The builder links 33 unique labels in 48 part-and-label pairs (browser 16, miiverse 16, miiverse_post 9, game_notes 7). 29 labels have Ukrainian text and draw in place. 4 have empty text (`STR_DATE_TIME`, `STR_SAVE_CONF_00`, `STR_SAVE_CONF_01`, `SaveImage_Lower`). `PageNum` is a group pane without text, so it is not linked.
  - The preview panel draws (a) and (b) in place from `plugins/system_3ds/layout_links.json` (built by `scripts/build_system_3ds_layouts.py`). The backdrop is a placeholder dark colour. Candidate `base_LZ.bin` / `Bg_U_00.bclyt` is pale yellow and makes the white text unreadable, so it is not used. The real backdrop is not found. Limits: the text colour is the layout's own, so white text on a white field stays hidden; the console may set colours at run time.
  - (c) box preview: all 35 parts. Labels with a width budget: 10,508 in 30 titles; the rest show the width only.
  - Owner's rule on the Ukrainian text: 0 labels wider than their budget and 0 with more lines than their line budget (`scan_fit`, rounded widths as validate.py).
- Width budgets (`budgets.json`, built by `scripts/build_system_3ds_budgets.py` from the decrypted NAND titles and the owner's validate.py): 10,533 of 16,235 strings have one (10,508 label budgets in 30 titles and 1 pane). On the owner's text with a wide word added to every string, the plugin and the owner's gate flag the same 5,640 strings. Still without a budget: the New 3DS titles `browser_n3ds` and `health_safety_n3ds` (no decrypted dump), `area`, `plaza_map` and `nnid` (the owner checks them with their own functions: `validate_area`, `validate_plaza_map`, `validate_nnid`), labels no official localisation has, and the `_smdh.json` files. Rebuild the file when the owner's layouts, `budget_groups` or `budget_px` change.
- The host reads the reference column while a project's files are still loading. `system_3ds` matched files by the blocks parsed so far and showed 792 of 2,317 Russian strings on a fresh open; it now reads each project block's own file. `manual_3ds` matches its reference the same way (fingerprints of the manuals parsed so far): not checked whether it loses part of its reference too.
- A save writes every `ua` the editor holds that differs from the file on disk, so a `ua` changed outside Picoripi in a file that is open is written back with the editor's text. The reference read (0.15 s for 138 files) runs on the UI thread, as for every plugin; the session keeps the string ids (about 310 KB).

## Link's Awakening Switch for LAS Recomp (`plugins/zelda_las`, 2026-10-14)

- Run in LAS Recomp beta_4 (2026-10-15) with the owner's v1.0.0 dump, the SWUK import and DejaVu Sans 2.37: the Ukrainian title screen, file select, difficulty choice and name entry show. Not reached yet: the first dialogue (the scripted run did not get past the name entry). Noto Sans 2.015 crashed the game at start (no U+25A1); the build now refuses such a font. The font is not in the repo. Not checked yet: the font's size and line height in long dialogue against the Standard font.
- Button icons come from the NintendoExt font (`runtime/hle/pl.c`, type 5). Without the owner's dump of `nintendo_ext_003` the title screen still showed the L and R icons; other icons in text are not checked.
- The SWUK import copies `region_common/ui/StartUp.arc` and `jpn_heading.bffnt`, made for v1.1.0, over the 1.0.0 files. On 1.0.0 in LAS Recomp the Ukrainian title logo shows and nothing crashed up to the title screen; later screens are not checked.
- A killed process or a power loss during an unpack leaves `.unpack-<id>` in the project folder (a cancel or an error removes it), now with the NCZ cache inside; nothing removes it later.
- An `.nsz` needs Python 3.14: `core/containers/switch_nsz.py` takes the streaming decoder from `core/zstd_frame.stdlib()` (no `zstandard` fallback). NCZBLOCK blocks above 16 MiB (`MAX_BLOCK_EXP` 24) are refused; nsz writes 1 MiB by default.

## 3DS manual simulator (`plugins/manual_3ds`, 2026-10-14)

- Done: `core/texture_formats/flim.py` reads 3DS CLIM / flag 0 BFLIM pictures as stored (top row first, picture top-left; `fix/flim-orientation`), and `console_render.decode_bclim` is `flim.read`; the merged render still matches the console on the pages with pictures (home_menu_manual page 7: text difference 0.86).
- The viewer's line wrap (2026-10-15, D40): it breaks a stored line only when the line is wider than its pane by more than `SUB_PIXEL` (`WRAP_SLACK` is −0.5). The New 3DS pairs of the card build `nd000_card_1653` draw lines whole at 0.17, 0.33, 0.50, 0.83 and 1.71 px short of the pane and at 0.09 px past it (home_menu_manual pages 8, 21, 22, 3; crops in the report folder `wrapcrops`). The earlier 2 px (a break at 0.8 px on shots_r17b, round-8 health document) came from the older font's widths. Open: how far past its pane a line may go before the viewer breaks it; no pair shows a line wider than its pane by more than 0.09 px (the build widens every pane to its text).
- The scroll bar's length and position are modelled (190 px track, length by the visible share), not fitted per shot; the bar rows of every shots_r17b pair are in the chrome notes of the simulator report.
- The real-data screenshot test (`tests/test_plugins/test_manual_3ds/test_simulator.py`) needs `PICORIPI_3DS_CALIB` (the folder that holds `shots_r17b`) besides `PICORIPI_ROMHACKING`; the chrome crops come from `<data>/plugins/manual_3ds/chrome` (git-ignored, cut from console screenshots).
- One layout truth (chosen 2026-10-14): the plugin's problems take the lines from the owner's model (that is where the build puts them: `layout.layout_for`, since round 19 the console's own measure: `fontSize / 25`, each pane's charSpace, the card edge, the ink overhangs) and judge each stored line with the console's measure (`layout.console_problems`: `console_render.FONT_WIDTH`, `WRAP_SLACK`, `COLUMN_WIDTH`, `FRAME_INNER`, `SUB_PIXEL`): WRAP (the viewer breaks the line inside its pane), WIDTH (ink past the card edge), BESIDE (past a picture's edge or a box frame's inner edge; the clearance before a picture is the owner layout's job, so Nintendo's own "/" panes are no defect). The preview runs the real render (`simulator.defects_of`) on the worker; the scan does not render (the per-line measure is the same arithmetic). The owner's column-budget WIDTH rule is gone from the plugin; the gate-comparison test compares the gate's text and pane failures only.
- Done (owner round 19, 848d04b): the owner's model measures as the console draws (`fontSize / 25`, `charSpace`, ink overhangs, frame widths from the textures), so the 329 cand_r18 lines past the card edge belong to the past builds; the next build's render decides.
- New 3DS screenshots (2026-10-15, D40): `shots_r19` holds 150 pairs; 36 are the old `shots_r17b` and `shots_new` pairs (byte-identical), 114 are new (console clock 2011-01-01), 113 of them viewer pairs. Classified by machine (`E:\Emulators\RomHacking\_shared\reports\manual_sim_fidelity_2026-10-15\shots_r19_0101.json`). The 9 pairs of the 21:00 batch are cand_r19; the 103 pairs of the 03:06–04:24 batch were shot with the card copy `nd000_card_1653.bin` (`calib\nd000`), a build no tmp folder holds; one pair matches `nd000_card_1621.bin`. The report folder has the per-pair sheets and the categorised list. `shots_r19_new` (36 pairs) is `shots_r17b` plus `shots_new`, byte-identical, not a new batch.
- Done (2026-10-15): the editor scan reports the render-only defects (`M3D_CELL`, `M3D_OVERLAP`, `M3D_COVERED`) by building and drawing the string's page with the owner's tools (`page_build.page_kinds`), and `geometry.json` carries the painted frame widths, so BESIDE agrees with the render. Open: the whole-project scan runs on the UI thread (`IssueScanHandler._perform_issues_scan_for_block`), so there the page render goes to one background `WorkerThread` at a time (texts read on the UI thread, interrupted between pages by the preview panel's shutdown on window close or plugin switch, results of a replaced manual dropped) and the block is rescanned when it is done (`rules._ScanRender` -> `_render_done` -> `rescan_issues_for_single_block`; audit r33); a project of 18 manuals renders 352 pages once after load (about 0.5 s a page, in the background). Without the owner's folder (`<data>/plugins/manual_3ds/preview.json`) the three kinds are not reported; the layout kinds are.
- Chrome from the viewer's own romfs (title 0004003000009B02, 87 files: `layout/*.arc` LZ10 darc with BCLYT, BCLAN and BCLIM; `message/*/ebird.msbt`): the header, badge, scroll indicator, arrows and bottom-bar textures are there (`BtnHeadLineTxt`, `PageNum`, `ScrollIndicator`, `SideScrollArw`, `BtnBack00`, `BtnClose00`, `BtnTextSize00`, `PageShdw00`), but their stored positions are moved by the applet's code and animations (the badge sits at x −120 in the layout and at canvas x 54 on the console), so the screenshot crops stay. No New 3DS variant of the viewer exists in the NAND dump (`00040030` has no `2000xxxx` title). A page's own structure needs no code: `__AREA__` blocks of 480 px, `HorizonG` rows, `wnd1` cells, `txt1` lines of one stored line each (Nintendo ends a continued line with `\n`).
- Done (2026-10-15, `fix/manual-preview-pm-search`): a project of many manual files keeps one manual per block (`rules._Manual`; before, only the file parsed last, and nothing after a restored session, so every string was looked up in the wrong manual and the preview said "The index is not drawn here"). The session carries the manuals without `ua` (`export_runtime_state`, about 1.4 MB for the 18 manuals, exported at each autosave); a session written before (the owner's has no plugin state) is completed once by a state-only read of the project files on a worker (`SessionMixin._read_missing_plugin_state`), then the issues are scanned again. While that read runs, the plugin may be asked from both threads; the geometry of a block is resolved on the thread that asks first. Checked offscreen on a copy of the owner's project: one page paragraph of each of the 18 blocks draws its Ukrainian text, except `browser` (no `Manual.bcma` on the owner's disk: the panel says so).
- Audit r30 on the state-only read: it now reads the source files only (before: the translation files too). The worker only appends to `rules._manuals`; the readers take the list once (`_manual`, `_keys_of`), so a list the UI thread replaces never gives an IndexError. Open, small: (1) Picoripi closed or killed while that read runs saves a session with part of the manuals, and the next open does not read the files again; the blocks without a manual say "This manual is not read yet" until a session predates the plugin code. Fix: write no plugin state while the read runs. (2) After a restored session the first issue scan resolves the geometry on the UI thread (`geometry.json`, 3.8 MB, once per process: about 0.25 s measured). Fix: resolve it on a worker after the restore. (3) The autosave (pickle on the UI thread, as before) now also copies the manuals (about 1.4 MB).
- Open: `face_raiders` and `face_raiders_n3ds` have the same key list, so `geometry.json` (keyed by the key-list fingerprint) holds one of them (`face_raiders`, the later in `manual.MANUALS`). The preview picks the archive by the block's name; the problems of `face_raiders_n3ds` use the `face_raiders` geometry. Fix when the two layouts differ: key `geometry.json` by manual name and match a file by its block name.
- Not ported from the owner's `beside_overruns`: the icon bands of other lines (an icon whose origin is at the bottom reaches up into the line above). The plugin's BESIDE sees pictures and frames only; the preview's render (`simulator.defects_of`) sees every icon as a picture. The parity test does not compare BESIDE.
- Open (2026-10-16): `geometry.json` is stamped with the owner commit it was built from, so any change to the owner's `src/manuals` breaks the gated real-data tests until `scripts/build_manual_geometry.py` is run again (r35 rebuilt it for 1e25146). Either rebuild the stamp with every owner change, or let the gate compare against the commit the file names.
- Done (2026-10-16): the simulator was checked against Azahar screenshots of our own build (Camera, Face Raiders, System Settings; small and large text, tables): 698 lines, 0 wrap or line-position mismatches; small text in Azahar is within the console band (median 0.66 vs 1.13). Report: `_shared/reports/azahar_large_2026-10-16/index.html` (owner workspace, not in git).

## Slop baseline: reduce the count (deslop, 2026-10-14)

- Reduce `tools/deslop/baseline.json` (default-on rules, counts per file): `call-only-assertions` in tests 321 -> 165 (2026-10-14). The 165 left check specific argument values of a collaborator call (for example an exact window title or exact call arguments); they stay as specific checks, not result checks. Remaining work: a test that checks only "was called" (no argument value, no result) needs a result or state check, not a suppression. Largest left: `tests/test_ui/test_ui_updater.py` 17, `tests/test_ui/test_updaters/test_small_updaters.py` 17, `tests/test_handlers/test_translation/test_glossary_handler.py` 14.
- Test gap found by the rewrite: `AIStatusDialog` teardown can hang a run if a test leaves the dialog open (its closeEvent calls the real `QMessageBox.question`).
- Product `getattr-literal` (20, e.g. `components/ai_status_dialog.py`): plain attribute assignment or access where the attribute always exists. `hasattr` probes are not checked on purpose.
- `poor-substring-tests` (62 -> 0 in tests, 2026-10-14): fixed with exact assertions; single glyph markers, dict-key checks and exact collection elements carry `# deslop: ignore[poor-substring-tests] <reason>`.
- Opt-in rules were measured but are not in the baseline: `any-params-returns` 1153 in product code, `shape-in-names` 424, `renamed-imports` 228, `duplicate-consts` 400. Decide per rule before enabling it in `[tool.deslop]`.
- Ruff candidates on this repo (not selected in `pyproject.toml`): `UP035 deprecated-import` 2126 hits; `RUF006 asyncio-dangling-task` 0; ruff 0.15.15 has no rule for unreachable code or unawaited coroutines.
- After each reduction run `python -m tools.deslop --update-baseline` and commit the lower count.
- Merge check (audit r16, 2026-10-14): no count rose. The baseline lost one entry (`repeated-assert-call`, `tests/test_core/test_translation/test_providers.py`, now suppressed with a reason). Two `module-mocking` findings in `tests/test_plugins/test_manual_3ds/` are suppressed with a reason: they test that sys.modules is restored.
- Audit r19 (2026-10-14): the merge of `fix/deslop-tests` raised no count; `tools/deslop/baseline.json` regenerated and unchanged. Ten behaviour mutations (run on a scratch copy of HEAD) each made their named tests fail, 15+ rewritten tests among them. The companion sync dialog test checks the exact status text, not the check mark alone; a stale "FAILURE EXPECTED HERE" comment in `tests/test_ui/test_glossary_ui_logic.py` was removed.
- Decided (2026-10-14): `call-only-assertions` counts `assert_called_with(...)` checks with real argument values as mock-only. They stay in the count as specific checks, not results. Only "was called" checks without an argument value need a result or state check. `poor-substring-tests` flags a single non-ASCII glyph (e.g. `'Ї'` in font tests), which is a deliberate marker; decide per case. `module-mocking` cannot tell a restore snapshot from a fake module; suppress with a reason.

## Test path hygiene (A14, 2026-10-13)

- Done: real-data tests reach the RomHacking workspace through `romhacking_root.under()` (env `PICORIPI_ROMHACKING`); without it they skip. `tests/test_personal_paths.py` fails on a new hard-coded drive path in `tests/`.
- Not checked any more on the owner's PC: the PPSSPP flash0 font comparison (`test_lunar_ssh`, always skipped); the owner's download-folder NSP checks and the `MG1-2 MC` raw check (relative placeholders, skip); the WP8 proxy tests (set `RQ_WP8_PROXY_ROOT` to run them).
- Jak 2 `atoll.fr3` check reads `PICORIPI_SCRATCH` (default `scratch`), not the owner's scratch folder.
- Guard run (deny-mode audit hook over the owner's emulator, download, game and scratch folders): 601 of 769 write-candidate test items ran, no write denied. The other 104 files (no write site outside tmp by AST triage) were not run under the hook. Owner action: run `python tasks.py test` with `PICORIPI_ROMHACKING` set and confirm the real-data count once.
- Before/after listing (path, size, mtime): the whole owner's workspace tree, 1,821,846 entries, is identical; the download, emulator, game and scratch folders are identical to two levels only.

## Work Together: roles, claims, comments (2026-10-12, D22)
- Tree markers on leaf rows: block items carry presence, claim and comment markers; the row items under a virtual folder do not yet. Resolved comments are not dimmed.
- Offline-first sync: operation log per participant, exchange file and shared-folder reader, with the conflict rules in D22 (next package; the interfaces are named there).
- Folder-level aggregation on virtual and real folder items: only block items get markers so far.
- Journal keeps state, not the operation list (D22 "one deliberate change"); a client that falls behind a window of 5,000 events gets a snapshot.
- Operations made while the room is unreachable wait in memory for the running session only; if Picoripi closes first, they are lost (the offline-first item keeps them on disk).
- Work Together, audit of `feat/collab-claims` (2026-10-12, not built): no quotas per member (comments, claims, requests, keys per scope); a member can fill memory and the journal. Add caps or document them.
- Work Together: the `op_id` dedupe for operations without `seq` is in memory (20,000 ids); a restart forgets them. The client always sends `seq`, so only old or test clients rely on it.
- Work Together: `deleted_comments` and `banned_names` in the journal grow without limit (one entry per delete or removal).
- Work Together: a host restarted on another port gets a new identity (its token is kept per address). The creation-token file restores the host role only on the same token.
- Work Together: a foreign `comments.json` is adopted only when the host or a moderator joins with it; with no host online its comments stay hidden.
- Work Together: the join snapshot (`_apply_state`) is not measured with 5,000 comments; the first read of `collab.json` per process is synchronous (a small file).

## Integration round 10 (2026-10-13)
- Integrated on `integrate/r10` from origin/main 54cc4479 and approved by the audit. `origin/main` is now 0e1cf802 (the round's fixes are on it). Contents: Project Manager Dolphin view and scan process, game icons, Super Metroid, Silent Hill menu language, Oracles, Donkey Kong x3.
- Audit fixes in 0e1cf802: "Built" and "Verified in game" have Ukrainian labels; the icon harvester reports a folder it cannot write and goes on; the story wing test stubs the MemPalace client (a `mempalace_local.db` in a parent folder changed its result; it reproduces on origin/main).
- Follow-up on `fix/pm-followups` (merged in integration round 11): the scan child stops between projects on a `cancel` line, and its stderr goes to the app log; the count signature includes the plugin's Python files, the shared `plugins/common` files and the Picoripi version (D28).
- Open from the audit: `core/project_library/index.py` `merge` locks per process only. The scan child and the window can write `project_index.json` at once; a lost update keeps an old count with a new signature until the next change. A file lock closes it.
- Open: `ScanProcess.shutdown()` waits up to 1.5 s on the UI thread when a rescan replaces a running scan (`ui/project_manager/window.py` `_start_scan`). Kill is fast in practice.
- Open: one `BackgroundJob` (a QThread) per changed icon (`_on_scan_event`, "icon"); a single decode worker would be cleaner.
- Open: PNGs in `pm_icons/` of removed projects are never deleted.
- Open: no test that closing the Project Manager window leaves no child process; no test that a `record_counts` save is followed by a correct scan.
- Open: a change to the core parsers (`core/formats.py`) without a version bump does not recount; the signature covers the plugin folders and the version only (D28).
- Owner to confirm: `plugins/mario_vs_donkey_kong_switch/msbp.json` (4428 lines) is the game's own message project converted to JSON; it may ship publicly only if the owner agrees (D29: game art is never committed).
- Owner: `feat/manual-3ds-plugin` waits for the owner.
- A18 (unpack in Picoripi): phase 1 is in integration round 11; phase 2a runs on `feat/unpack-2a`; phase 2b runs on `feat/unpack-2b`; phase 2c (decryption for 3DS, Switch and Wii) runs on `feat/unpack-2c`, not merged. The open items for 2c are at the end of this file. The owner's run of 2026-10-14 verified 3DS and Switch decryption on real images; Wii is not run yet (no `keys.bin` on the PC).

## Integration round 9 (2026-10-13)
- Merged on `integrate/ready-2026-10-13` from origin/main 670e8b63: `feat/pm-phase2`, `feat/data-folder-guard`, `feat/collab-claims`, `feat/family-projects`, `feat/family-projects-ui`, `feat/family-ww`, `feat/zelda-ladx-dx`, `feat/ladx-family`, `feat/ladx-hd`, `feat/zelda-ds`, `feat/mhp3rd-lang`, `feat/sly-cooper`, `feat/ss-shared`, `docs/roadmap`. Not pushed.
- Skipped: `feat/oot3d-ua` (no commits beyond main), `feat/sh-menu-lang` (its worktree has uncommitted changes), `feat/sm-sh-ua-variants` (an agent still works on it).
- Decision numbers: the family branches used D18 to D20, which main already had. They are now D24 (family projects), D25 (plugin declares the family), D26 (family folders) and D27 (Wind Waker).
- Personal paths in the new real-data tests now come from `PICORIPI_ROMHACKING` and `PICORIPI_SCRATCH`; the defaults are relative paths, so those tests skip until the owner sets the variables.
- `feat/ss-shared` adds only one CHANGELOG line about workspace scripts that are not in this repository. Owner decides whether to keep it.
- Sly Cooper: the option table (1179 entries, from ProjectCane `spaprops.cpp`) left `plugins/sly_cooper/tables.py`; `load_option_schema()` reads it from a local file given by the caller, e.g. `<workspace>\tools\option_schema.json`, outside the repository. The licence of ProjectCane is free (owner confirmed 2026-10-13), so the copy in history is accepted and the table may return to the repository when a reason appears.
- Wind Waker family project: base archive messages count under the `.extracted` folder, not `base` (test adapted).
- Sly Cooper option table (ProjectCane) remains in history at 76d8c5a1; the owner confirmed on 2026-10-13 that its licence is fully free. Closed.

## Integration round 8 (2026-10-12)
- Merged on `integrate/ready-2026-10-12` from origin/main 2eeafa1c: the user's WIP branch (7 commits), `feat/project-manager`, `feat/portable-home`, `feat/ready-wiiu-system`, `feat/ready-mgs23-pc`, `feat/ready-dk`, `feat/oot3d-ua`. Not pushed.
- Test failures seen in the full parallel run, and their classes: a stale `docs/INDEX.md` after the merge (integration, fixed by `docs-index`); the review-pass test expected a kept line break where the user's `layout_class` now typesets a prose string (intentional change, test updated, see its comment). A run that shared the machine with a second pytest run ended with `node down: Not properly terminated` workers (load, not reproduced in a quiet run).
- Final full parallel run on this branch (before the last heuristic fix): 9548 passed, 14 skipped, 2 xfailed, 4 failed. One failure was ours: `test_validate_all` read `plugin.encode` in `handlers/collab_handler.py`; fixed (now `str(plugin).encode`), `test_validate_all` and `test_collab` pass (162).
- OPEN, owner decision: three Super Metroid real-data tests (`tests/test_plugins/test_super_metroid/test_rules.py`, `test_real_text_saves_back_unchanged`, `test_real_intro_fonts_show_every_letter_the_text_uses_as_a_whole_glyph`, `test_an_edited_intro_glyph_lands_in_the_built_rom_and_the_other_intro_font_keeps_its_edit`) read the live workspace `<RomHacking>\Metroid\Super Metroid\source\text.json`, which was rewritten at 14:14:38 on 2026-10-12 by a process outside this repo (block counts now 27,27,29,7,7,77 against 27,27,36,7,7,77). Two fail serially too; the third failed only in parallel. Not weakened: decide whether the expected values follow the workspace or the workspace is pinned.
- `plugins/plain_text/fonts/` (FFNT dumps of a Nintendo game) is not tracked: no free licence. No test reads it; smoke passes without it.
- Collab residual risk: the first fingerprint pass of a project runs on the UI thread at Start or Join (one pass, then cached per project). Measured with plain attribute access: 29 ms for 20,000 rows, 93 ms for 60,000. Move it to a worker if a project grows past about 200,000 rows.
- Collab residual risk: `lan_addresses()` looks up the host name once per process, only after the host allows other computers, and in a background thread (`LanLookup`); a slow DNS shows the invitation a moment later.
- Collab residual risk: the room is plain HTTP with a shared password; the window says so.

## Project Manager phase 3 (2026-10-17, branch `feat/pm-phase3`)

Audit against the owner design of 2026-10-11 and the goal of 2026-10-16. Checked in code (plugin hook table of
every `plugins/*/rules.py`, scratch script outside the repo) and by the 147 Project Manager tests that pass on
`origin/main` 8cfc53e0.

Exists:
- Manager opens with no project open. Only added projects are listed. Folders, group and sort choices are kept.
- Row details: path, lines, translated %, blocks, dates, folder tree (blocks and lines per source folder), needs
  attention (issue codes, count errors, blocks not counted yet), flags Built and Verified in game.
- Build mod, Export mod and Run in emulator are on for the 16 plugins that override `get_build_targets`:
  ffta_gba, plain_text, pokemon_bdsp, pokemon_fr, pokemon_gen1, pokemon_gen4, pokemon_gen5, pokemon_gen6,
  pokemon_gen7, pokemon_gsc, pokemon_md_3ds, pokemon_nx, pokemon_trinity, super_mario_galaxy,
  super_mario_sunshine, zelda_las. The other plugins show the buttons off. Only the dispatch is tested here;
  a real build of each target needs the owner's data.
- Wizard: roles and platforms come from the plugin (`get_source_roles`: 9 plugins; `get_platforms`: 27 plugins)
  and file identity from `identify_source` (30 plugins). Several files; unpack on create with cancel; key files
  asked per console (`unpack_key_consoles`: 8 plugins).

Done on `feat/pm-phase3` (2026-10-17):
- (a) One emulator command per platform: `emulator_command.<platform>` in the registry; Run uses the command of the
  target's platform; the old shared `emulator_command` still applies to platforms with no line of their own. A
  project with no platform (plain text) uses the shared one. Run is off for a target with no command. Test:
  `test_run_starts_the_emulator_of_the_platform_the_build_is_for` (no real emulator starts).
- (b) Row details: the source folder's files by kind (text, font, texture, other), counted on a worker when the row
  opens (`ResourceJob`, cancellable; cached for the window's life, so a file added later shows after a reopen). Needs
  attention lists blocks with no translation file yet (`missing_translations`, counted in the scan). Kinds come from
  the file extension (`core/project_library/resources.py`).
- (c) Wizard: "Use an existing translation folder" (folder projects only; refused for a one-file project). The
  source files and their roles are listed in the row details. The roles still reach `unpack_sources` as before.
- (d) `NewProjectDialog` is removed. The Import block and settings file pickers use `formats.dialog_filter`. The
  wizard and the icon dialogs list all files, as before.
- (e) GameCube reader, shared image helpers and identify layer: `ImageError` texts through `tr()`. See the
  "Audit r17" line in the phase 2c section for the readers still in English.

Found while doing it (not fixed):
- Fixed in phase 3b: `pokemon_bdsp`, `pokemon_nx` and `pokemon_trinity` declare `switch` in `get_platforms()`. `test_plugin_platforms.py` checks that every build target names only declared platforms.
- `super_mario_sunshine`'s `port_pack` target names no platform. It uses the project's platform (`gc`).
- Fixed in phase 3b: `UnpackJob` makes `translation` only when the project keeps its own folder, so a refused one-file create leaves none.
- Real builds of each of the 16 targets are not run here (they need the owner's data). Tests cover the dispatch
  with a fake target. Check each target once on the owner's machine.
- The resource counts are kept for the window's life. A file added to a source folder shows after the window
  reopens.

Missing, outside phase 3 (for the owner's decision):
- Done in phase 3b: the Console keys tab in Settings holds the key file path of each console (paths only). The wizard still asks for a missing key and stores it there.
- Decided 2026-10-17: no opens counter. The design's "opens" is the project-opens flag (last opened time), which the registry already keeps.
- Done in phase 3b: the grid shows the selected project's details under the grid (the list's detail widget, the same code).
- No zip export. Single-file export works (`build.export_build` copies a file).
- macOS `.app` bundles: the emulator command needs the path of the program inside the bundle (no helper yet).
- `metroid_prime_trilogy` has no `identify_source`, so its wizard takes the role from the user.
- Icons changed while the window is open show at the next scan (no file watcher).
- Resource kinds: the plugin hook `classify_resource(path)` names a kind first (done in phase 3b); the extension rule is the default. No plugin overrides it yet, so a font or texture in an unknown format still counts as other for every game.

## Project Manager phase 3b (2026-10-17, branch `feat/pm-phase3`)

Done in this round: the Switch platform of three Pokémon games, the refused one-file create, the emulator lines, the grid
details, the Console keys tab, the `classify_resource` hook, and the `ImageError` texts listed under "ImageError texts" below.
Decisions of the coordinator (2026-10-17): keys live on one settings page per console, paths only; no opens counter.

Open after phase 3b:
- The Console keys tab lists the slots in `core/project_library/console_keys.py` (`CONSOLES`), not the consoles found by
  loading every plugin (that would import all plugins on the UI thread). `test_every_console_a_plugin_names_has_a_slot`
  fails when a plugin names a console without a slot; a new console needs a slot first.
- `classify_resource` is optional. No plugin overrides it yet.
- Real builds of each target are not run here (owner's data), as before.
- Done in phase 3b: every `ImageError` text of `core/containers/` and `plugins/*/unpack.py` goes through `tr()`; `tests/test_core/test_image_error_text.py` keeps it so.
- Done in phase 3b: the unpack and container error texts (`ValueError`, `RuntimeError`, `OSError`) of `core/containers/` and `plugins/*/unpack.py` go through `tr()` (87 messages), with Ukrainian entries.
- Still English: the `OodleError` texts of `core/unreal/oodle.py` (4 f-strings: library not loaded, no `OodleLZ_Decompress`, no `OodleLZ_Compress`, nothing compressed). The Pokémon Switch unpack wraps them as "the Oodle library cannot be used: {0}" (`tr()`), so the English detail still shows inside the Ukrainian line.
- Still English: 9 developer messages that reach the log, not the wizard: `core/containers/wia.py` (2, seek on a closed stream) and `core/project_library/` (7: project file not an object, unknown console, unknown flags, missing entries object). Count with `grep -rn 'raise \(ValueError\|RuntimeError\)(' core/containers core/project_library`.

## Project Manager phase 2 (2026-10-12)

- Owner screenshot of 2026-10-14 showed the Project Manager in English while the menus were Ukrainian. Not reproduced on HEAD: every Project Manager literal has a `locales/uk.json` key (keys dated 2026-10-11 and 2026-10-13), and a freshly built dialog renders in Ukrainian. Check whether the owner's running build predates these keys. The walk test `tests/test_ui/test_project_manager/test_translation_walk.py` guards against regressions.
- Qt's own dialog text ("OK", "Yes", "No") follows the language only where Qt ships the translation (`qtbase_uk.qm` has Cancel and Yes but not OK). Other Qt text stays English.
- Stale (2026-10-17): the 16 build-target plugins and the wizard hooks are in place; see "Project Manager phase 3" above. The Build, Export and Run buttons stay off only for plugins with no target.
- Counts skip archive members (blocks inside containers) and report them as "not counted yet". Counting them needs the load worker's archive path (`handlers/project_action/load_worker.py`).
- Closed in D28: a count is kept while its input signature (project file, plugin config, source and translation files) is unchanged. An edit to a translation file made outside Picoripi is seen at the next scan.
- Closed in D28 for the scan: the scan runs in its own process with its own modules, so a plugin load of the window cannot wait for it. The window's own plugin loads still share `PLUGIN_IMPORT_LOCK` on the UI thread.
- The wizard, with no unpacking and several files, uses the base file as the source. The other files are recorded in the project metadata only.
- One emulator command serves every platform. MacOS `.app` bundles need the path of the program inside the bundle.
- Export copies a folder. A zip or a single-file export is not built.
- ROADMAP entries A9 and A10 are not updated: `docs/ROADMAP.md` is not on `main`. Their state is in the phase 2 commit messages and D23.
- The first scan of 191 projects takes about 4 minutes in the scan process (plugin parsing is CPU work). The window stays responsive; a faster parse would need a plugin-level change.
- Measured 2026-10-15 on the owner's 194 projects (read-only, temp data folder): the cards take 0.5 s, the input signatures 18 to 29 s (a `stat` of every block file on the E: drive; the largest are Yo-kai Watch 2 and 3, about 1 s each), the icons 1.5 s. The scan now sends every card first, so the names and the search are complete after 0.5 s (before: 20 to 32 s). The signatures still come before the counts; making them cheaper needs a per-folder stamp, which NTFS does not give (see `plugin_facts.input_signature`).
- Five projects showed `Plugin missing` before round 10 (`zelda_oracles`, `donkey_kong_tropical_freeze`, `mario_vs_donkey_kong_gba`, `mario_vs_donkey_kong_switch`). Round 10 merges those plugins. Not yet checked in the app.
- Icons changed while the window is open appear at the next scan (open or Reload). There is no file watcher.
- Game icons: `scripts/harvest_project_icons.py` writes `picoripi/icon.png` (dry run by default; `--apply` writes). It is run by hand; the app does not extract icons (D29).
- A scan child needs `sys.executable -m core.project_library.scan_child`. A frozen (PyInstaller) build would need a scan entry point; no frozen build exists.
- A save of an open project writes its counts to the index from the window's process while a scan may be writing the same file from the child. A lost entry only means one recount at the next scan.

## Project Manager phase 1 (2026-10-11)

- Closed in phase 2 (D23): lines and translated % are counted in a worker for a project never opened.
- Closed in phase 2 (D23): the Built and Verified in game flags are stored in `metadata.flags`, set only by the user.
- The platform of an imported project comes from a folder name (3DS, Switch, …). It is a guess; the user can review it in the import checklist. Check it on the real set once.
- The shortcut Ctrl+Shift+M is free; Ctrl+Shift+P is taken by Preview. Confirm the shortcut.
- Opening a project from the manager has the same unsaved-edits behaviour as the Recent Projects menu. No guard was added. Check it with unsaved edits.
- Move to folder is the only way to change a folder. Drag and drop is not built.
- The import of the RomHacking set (`<RomHacking>`) into the owner's real registry is not done. Run Import once from the window.
## Family projects (2026-10-12, branch feat/family-projects-ui)

- [ ] Project and wizard accept several folders or game images per project, each assigned to a member by the plugin (the engine and the TP recognition exist; the UI and image files do not).
- [ ] Wind Waker family: plugin reads both GC BMG (`zelda_tww`) and HD MSBT (`zelda_ww`). Measured 2026-10-17 on the owner's unpacked folders: 3,432 of 5,040 HD messages link (68.1 %). The tag map (`family_tag_map.json`) was already derived, so the old 23 % figure was stale. Of the 4,262 messages paired by id, 3,306 have the same match key, 222 differ only in tags the match key sees, and 734 have different text. Open: the 222 tag gaps are `[Capital]` and `[Size]` the HD text writes and GameCube does not. Leaving them out of the key would link them, but family output takes the GameCube text, which drops those HD tags from the linked HD message (checked in `write_hd_output`). So they stay out of the key until the output re-applies HD-only styling. A rule for the 734 text differences is a scope decision.
- [x] Shared files: `python -m plugins.zelda_bmg.family shared` copied the English GameCube `fontres.arc` (the family's base source), not the translated one the disc ships. Fixed: the family file's `translations` entry for the base is used (`ISO\UA\root\res\Fontus\fontres.arc`, SHA-1 `d01c5de…`, checked with the owner's `_family\family.json` through a scratch copy). The Wii patcher (`GC + Wii\Patcher\patcher.py`, outside the repo, line 406) still copies its own `Patcher\files\Fontus\fontres.arc` (SHA-1 `bbeafe…`), a third file. Open for the owner: point the patcher at `family_out\wii\Fontus\fontres.arc` after `family shared` (a change to the Wii font), or keep its file.
- [x] Wind Waker font sync (checked 2026-10-18): the two copies are byte-equal (148064 bytes, SHA-1 `36d088df…`); the "28335" size was wrong. Glyph sync by character code is written (`core/font_formats/glyph_sync.py`, linked in `plugins/zelda_tww/font_sources.json`). It is opt-in per pair: the Font Editor asks once, and the "Copy changes to" box turns the pair on. Tests: 18 pass, including the real-data pair (`tests/test_core/test_glyph_sync_real.py`).
- [ ] Family store v1 to v2 migration: the old `_family/family_translations.json` is kept as `.bak_v1_20261012`; the new store is seeded from the translation folders.
- [ ] TP Wii only folder reads the Wii source from `<RomHacking_tmp>`; the family file must point elsewhere once that folder is removed.
## Zelda DS (`plugins/zelda_ds`, 2026-10-12)

- Zelda DS: the fonts and picture files are in `source\`, but the Textures window and the Font Editor have not been checked in the GUI for them. `texture_sources.json` is not written yet.
- Zelda DS 3D textures (`ntfp` / `ntft` / `ntfi` members of `*.bin` NARCs, NSBTX inside BMD0 models) are not opened. One LZ10 stream (`dwc/utility.bin`) gives a back-reference error.
- Zelda DS Download Play children: no BMG, NFTR or readable strings in the child programs (PH `child.srl` has no NitroFS files; the ST child ARM9 has no plain text). Their text format is not identified yet.
- Zelda DS picture edits: the picture module writes top-level NCGR members only; a picture nested one archive down (in the ST child) is rebuilt as a whole file, not edited sheet by sheet.

## Integration round 7 (2026-10-11)

- BIOS Huffman exists twice: `core/containers/level5.py` `_huffman` (Kuriimu tree layout) and `core/containers/layton_ds.py` `_huffman` (BIOS tree layout, Layton DS). Both read MSB-first 32-bit words, but the tree indexing differs. A random-tree comparison proved too little (25 comparable cases of 3000), so both stay. Merge them after a Layton DS stream with a Huffman body is checked on disk, or after a BIOS Huffman encoder test exists.
- Duplicate LZ10 (round 6 item) is still open: `core/containers/level5.py` `_lz10` next to `core/containers/lz10.py`.
- `plugins/pokemon_gen7/rules.py` is a copy of `plugins/pokemon_gen6/rules.py` (33 changed lines: tables, GARC ids, names). Both use `plugins/common/gfmsg`. A shared base for the Game Freak `.dat` plugins is a later refactor.
- Licence notices: `core/texture_formats/xenos.py` carries the full Xenia BSD-3 text (Ben Vanik, 2015); `core/containers/layton_ds.py` carries the full MIT text of bullbin's madhatter (2024), which its pack codec is ported from; `core/containers/romfs_write.py` carries the full MIT text of Peiikai's LAS Recomp (2026), which it is ported from (`runtime/romfs_build.c`); `core/containers/switch_nsz.py` cites nsz (MIT) for format facts only. Jak (`fr3`) cites the OpenGOAL port for format facts only; no OpenGOAL source is copied. The OpenGOAL licence was not checked.
- Zstd: `core/zstd_frame.py` is the one zstd helper (`compression.zstd` or `zstandard`, imported inside the calls). `fr3`, `core/unreal/pak.py`, the RVZ reader (`core/containers/wia.py`) and the NCZ reader (`stdlib()`) use it; `core/containers/sarc.py` imports `compression.zstd` itself for its dictionaries.
- `feat/ready-dk` does not exist; Donkey Kong is not in round 7.
- Ultra boot proof still open (round 6 item); the Sun/Moon plugin has no boot check either.
- Full suite at 6f5a0d89 (`python tasks.py test`, parallel): 9344 passed, 13 skipped, 2 xfailed, 0 failed (601 s). Round 6's xdist worker crashes did not recur in this run.

## Integration round 6 (2026-10-11)

- `jfnt` (One Piece, `JFNT`) and `asw_jfnt` (Dragon Ball Fusions, `jFNT`) are two font readers for two layouts (different magic). Decide later whether one reader can cover both.
- Duplicate LZ10: `core/containers/level5.py` has its own `_lz10` decode and `lz10_encode`; `core/containers/lz10.py` is the shared one. Merge them into one implementation.
- Pret character tables (H3): the gen4 charmaps hold the encoding facts only; provenance is in `plugins/pokemon_gen4/charmaps/README.md`. Keep that note current when a pret table changes.
- Owner paths in test fixtures: the Donkey Kong, Zelda OoT 3D and Super Metroid real-file tests read the root from `PICORIPI_ROMHACKING` (`tests/romhacking_root.py`) and skip when it is unset. The owner must set it to the RomHacking root folder (the owner's own machine) to keep them running. The MGS3 PC check reads `MGS3_PC_LAUNCHER_DATA` the same way. Other older test modules still name the owner's RomHacking folder directly (about 200 lines in the tracked tree, pre-existing): not yet moved to the helper.
- TP preview goldens (`tests/fixtures/review_queue/wp5`) were made with no fonts installed; the pixel check depends on the machine's fonts (`QT_QPA_FONTDIR`).
- Intermittent worker crashes under heavy load (xdist): `test_wwhd_real`, `test_kid_icarus_real`, `test_kingdom_hearts_ddd`. Each passes alone; rerun them with `-p no:xdist`.
- Ultra boot proof open: no emulator boot check is recorded for the Ultra game in round 6.
- `fantasy_life`: a longer text is cut, not moved (moving hung the game after the title screen; `allow_growth` in `plugins/fantasy_life/l5text.py` stays off). 26 `.l5ui` containers (`ui000_*`) gave a black screen at start in Azahar; the breaking one is not found.

## Integration round 5 (2026-10-10)

- `core/unreal/pak.py` (Unreal pak v8) has no plugin user yet; its zstd path needs Python 3.14+ (`compression.zstd`) or the `zstandard` package; otherwise it raises `PakError`. MGS2/3 Master Collection PC text is not read yet (only the PC `.ctxr` pictures).
- `core/texture_formats/sources.resolve()` decodes every picture it lists: Bravely Second's 5,073 ETC1 pictures take about 100 s (its real-data test has a 600 s timeout).

## Pokémon generation III-V (`plugins/pokemon_fr`, `pokemon_gen4`, `pokemon_gen5`, 2026-10-10)

- Game text in older tests (before r37, not changed by r43): `test_pokemon_gen1/test_rules.py`, `test_pokemon_gen4/test_gen4_rom.py`, `test_pokemon_gen4/test_rules.py` and `test_pokemon_gen5/test_rules.py` quote full game lines. Use synthetic text, or a facts file under `PICORIPI_ROMHACKING` as the r43 tests do. The lines already exist in git history (for example commits `b1188479`, `e9d9ae0d`); a history rewrite needs the owner's decision.
- Gen 3 (Ruby / Sapphire, FireRed / LeafGreen, Emerald): the WSL build in `zt/pret_gen3.py` (agbcc, libpng built from the cloned sources) was written but not run; `2_build.bat` must be run once to prove it.
- Gen 3: the Ukrainian letters that are not look-alikes sit on the cells of accented Latin letters; their glyphs are not drawn. Width checks use the old JSON font map, not the game's font widths.
- Gen 4 decompilations: no build (Metrowerks mwccarm, Nitro SDK and the ROMs are not on disk); the fonts and pictures are PNG + JSON descriptors the decompilation's tools turn into NFTR/NCGR, not opened yet.
- Gen 5: seen in melonDS 1.1 (private copy, hidden desktop): the edited menu text, a filled `S` glyph and changed pictures (all NCGR, not one chosen picture); NO$GBA stops Pokémon B/W at its save check. `gfl_font.dat` (2,320 bytes) and the NCER / NSCR / NSBTX / NSBMD files are not opened. White and White 2 are not on disk.
- Sun / Moon / Ultra Sun / Ultra Moon: no complete image on disk (the CIA downloads are partial).

## Ikenie no Yoru (`plugins/ikenie_no_yoru`, 2026-10-08)

- Not opened: the channel title in the `opening.bnr` IMET header, TEX0 textures of the BRRES models, text in the
  THP movies. No speakers or window widths yet; `{U0008}`-style codes (debug text) have no names.
- No font has Cyrillic; the Japanese glyph cells (font_game 968) are where Ukrainian letters would go.
- How much a package (`package\*.bin`) may grow before the game's buffer overflows is not measured (a 3.4 KB longer
  `ch04_01` builds; only the title screen was booted).
- The workspace's boot fix (a fresh Wii memory without the patch's save) is proved in Dolphin only, not on a
  real Wii.

## Spore Hero (`plugins/spore_hero`, 2026-10-08)

- The three game fonts (`fntg`) have no Cyrillic: Ukrainian letters need glyphs drawn over unused accented letters
  (the Font Editor's translation map; the plugin then writes the letter as that glyph's character) — `fntg` cannot
  add glyphs (no room on the C4 page).
- The game decodes its RefPack packages with a 16 KiB window; the workspace's `zt/spore.py` keeps every command of the
  original stream except around a change. Its own compressor is ~6 % worse than EA's: a package rebuilt in full grows.
- Not opened: the Apt UI files (`.uix`, their text is `~KEY` references to the LOCBIN strings), the credits names
  (`credits.txt`, names only), the disc banner title (`opening.bnr` header), 3D model and effect textures.
- `main.dol` messages are fallbacks before the text loads; each must fit its own bytes (cp1252, no Cyrillic).

## Castlevania: Circle of the Moon (`plugins/castlevania_cotm`, 2026-10-08)

- The 66 Ukrainian cells (0x29A-0x2DB) are empty: nobody has drawn them; the text shows them only when drawn.
- The menu item names are pre-drawn in the font (0x74-0x299, ten cells a name): translated names are redrawn
  there (Tools -> Textures, "Item names in menus"); the text table's names are a second copy (pick-up messages).
- Texture palettes come from the screens' code; sheets whose bank is not known show the first bank or grey.
- No speakers yet: `{1E xx}` in the story looks like the portrait; not mapped to names.

## Pokémon Scarlet/Violet, Legends: Z-A (`plugins/pokemon_trinity`, 2026-10-09)

- The English HUD pictures of Z-A (`ui/tex/hud_spmg/tga_eng/*.bntx`) are not checked in the game; English layouts
  (`*_eng.arc`) are (the build also writes them as the base `X.arc`, which the game reads from the romfs).
- The scalable fonts (FOT-UDKakugo, FOT-Rodin) lack Ґ Є І Ї ґ є і ї and the Font Editor cannot add a character to
  an OpenType font; the bitmap `.bffnt` fonts, UniversNextPro and `or_font` have no Cyrillic.
- Not opened: the `.tbl` line labels (shown nowhere), `message/sort` and `messagegrammarEnglish.dat` (sort and
  article tables), the font settings `.bfcpx` / `TextFontSetting.bin`; the executable was not searched.

## Raving Rabbids: Party Collection (`plugins/rabbids_party`, 2026-10-09)

- TV Party's Flash movies hold no pictures: 0 bitmap tags and 0 bitmap fills in 31,720 shapes; the menus, logos
  and the title logo are vector art (Dolphin uploads no texture for the title logo). Their `DefineExternalImage`
  key pairs match no file on the disc (the per-movie `Flash_<id>.pk` sound packages are the only `Flash_` files).
  A vector logo cannot be replaced by a PNG in the Textures window.
- The TV Party static captions (`gfx` blocks) take only glyphs the movie's own font has (A-Z and a few symbols);
  other letters need the translation map, like every other font of the game.
- The menu prompt ("Press the A Button…") is drawn with a font that is not on the disc (a filled `e` in both
  `wbf1/wbf2.brfna` did not show there in Dolphin; they are the HOME Menu fonts): its Cyrillic needs a user
  decision (Latin letters or leave English).
- Fonts cannot grow: Jade, BRFNA and Flash fonts take new letters only by redrawing unused glyphs (translation map).
- Rabbids 1/2 textures are listed for the menu worlds only (`_main_*`, `Menu_LD`, `RRR2_Boot`, `Compil`); the same
  key in a smaller size elsewhere gets the edit scaled down (nearest neighbour).

## Infinite Space (`plugins/infinite_space`, 2026-10-09)

- The dialogue font (`Obd/T000OBJ.obd`) has 78 glyphs and no room for more: tiles added at its end make the game
  lose the dialogue window (NO$GBA). The text codes allow 50 more glyphs (`0x80 0x9D`..`0x80 0xFF`); Ukrainian
  letters need either redrawn Latin glyphs or a code change that loads a bigger font. Not decided.
- No text file holds ship, weapon or module names (all text is in `SpaceShip.scx`, which has none of them);
  the menus seen so far are pictures (`.obd` / `.bgd`). Where the shipyard names come from is not checked in the game.
- `[x80NN]` codes beyond the font's list draw nothing.

## Dragon Quest IX (`plugins/dq9`, 2026-10-09)

- Not opened: the debug menus (`data/bin/str_dbg*`, `strdbg*`, `str_debug_en.bin`) and the Japanese kanji font
  subsets of `data/pack/font.gp2` and `pack_lv5/font_lv5.gp2` (the English text never uses them).
- Not opened: one line in the code (overlay 3, BLZ-packed): the greeting of a Japanese visitor in tag mode
  ("Hello! I<1>m from Japan! Nice to meet you!"), next to its four other languages.
- Picture formats not listed: the 3D model textures (`.nsbtx` / `.nsbmd` in `pack_lv5/*.gp2`) and the loose `ani/*.spr`
  icons (no text seen).
- `nat` pointer columns are found by rule (tested against all five languages of this game); a table edited by hand
  with a new layout could fool it.

## Metroid: Other M (`plugins/metroid_other_m`, 2026-10-07)

- Not opened: the disc-error messages in `sys/main.dol` (2_build writes only `files/`) and the channel title in
  the `opening.bnr` IMET header. No speakers, scenes or measured window widths yet.
- No font has Ukrainian letters (the global fonts map codes 32–255 only, the game draws `Œ — ’` through
  CP1252 slots); where Ukrainian letters go (free slots or new codes) is not decided.
- The game reads `message_all.dat` into a buffer of its own ("msg buffer size deficiency"); how much longer the
  file may grow is not measured.
- Not in the Textures window: the TEX0 textures inside the 2,234 BRRES model files (3D scenes and effects; a few
  effect letters such as `EFF_tutorial_target_*_word_*`). Same GX formats as TPL.
- The ICON names C..J and TEXT_END come from the game's tables; no English message uses them.

## Super Metroid (`plugins/super_metroid`, 2026-10-08)

- sm_rewrite's HEAD opens a new window every frame (`main_loop()`, commit e55088a); the workspace build fixes its copy of `src/main.c` (`MAIN_PATCH` in `zt\sm.py`) and fails loudly if the port changes. Boot proof: the file select shows a text, a font and a texture edit.
- Ukrainian letters have cells only in the message-box font (21 unused BG3 tiles). The menu, pause, intro and credits fonts have no free cells; the intro font has 4. Japanese-only glyph cells could be reused if the Japanese text option may go (question to the user).
- The big menu and credits letters are built from shared top/bottom tiles: new letters need new tiles and a pair table; the Font Editor shows only the cells whose halves are a whole letter.
- Text pictures (pause item names, button words, title logo, PLANET ZEBES, SEE YOU NEXT MISSION) are tile graphics in the Textures window, not text. Not opened: the Russian fan patch's changes to level data in banks C2/C3 (not text).
- `FONTS` / `UA_BG3` in the workspace's `zt\sm.py` and `font_sources.json` must agree (regenerate both together).
## A Link to the Past (`plugins/zelda_lttp`, 2026-10-07)

- The Ukrainian letters have empty cells in the workspace font (б–я 95–119, Б–Я 128–148); nobody has drawn them yet. The file-select screen, name entry and credits keep the English font and words.
- Not opened: credits and file-select / name-entry text (tilemaps in the port's C code and ROM tables).
- `font_sources.json` `chars` and `UK_LOWER`/`UK_UPPER` in the workspace's `zt\lttp.py` must agree (`test_font_cells_match_the_workspace_build`).
- Switch port (Alek NX, `nx_ui.txt`): its menu font has only A-Z; Ukrainian menu words need Cyrillic cells in sprite sheets 105-107 and a change to `draw_text` in the port's `second_screen_sdl.c`. The port's in-app updater would replace our NRO with the author's (no escape code 0x86).

## Tingle Tuner (`plugins/zelda_tingle`, 2026-10-04)

- The GBA keeps 67,584 bytes for the unpacked USA text, only ~1,800 more than the English needs; a longer translation needs the client's buffers moved (the 0x02010800 literals in `client_u.bin`, see `WW_UA\reports\tingle_tuner_report.md`).
- Text drawn as graphics on the GBA is not translated: the help screen (tiles 0xA0-0xEF of the font block, editable as glyph cells in the Font Editor), "Call", "Please wait...", N/E/S/W on the main screen (OBJ/BG tiles).
- The Ukrainian glyphs in `WW_UA\translation\files\res\Gba\client_u.bin` are a rough render (Press Start 2P squeezed to 5 px); Б Ґ Ї Й і й need hand drawing.
- European clients (`client_0`..`4.bin`) have other addresses: no font source or program strings for them yet; their accent codes show as `{xNN}`.

## Metroid Prime Trilogy (`plugins/metroid_prime_trilogy`, 2026-10-07)

- Not opened: strings in the executables (`rs5*.dol`), the HOME Menu (`rhbm\homeBtn_ENG.arc` per game), the Wii menu banner (`opening.bnr`), videos (`.thp`).
- No font has Ukrainian letters and `retro_font_gx` cannot add glyphs (no room in the C4 texture): letters go over unused accented glyphs (a translation map) or the texture must grow.
- The workspace LZO packs about 3 % worse than Retro's: a package whose edited resources no longer fit gets the English text of unchanged tables as every language, biggest saving first; the disc has only 232 MB free, so a world package of Prime 3 (up to 743 MB) can never move.
- Seen in Dolphin only for the menu (STRG version 3); shared-language tables of Prime 1 (version 0) and Prime 2 (version 1) are checked by machine, not in the game.
- GameCube Metroid Prime (PC port workspace `Metroid\Prime (GC + PC port)`, 2026-10-10): checked on a USA disc of revision 2 (v1.02; the port takes it with `MP_DISC_ANY_VERSION=1`), not on revision 0; the world-name card (`Tallon Overworld`, from the memory-card world list) did not change with a loose STRG, MLVL or whole-PAK mod, while the intro text card did: unexplained, port side.

## Pokémon X/Y + Omega Ruby/Alpha Sapphire (`plugins/pokemon_gen6`, 2026-10-09)

- Not opened: the name sort-order tables (`a/1/9/4` X/Y, `a/1/7/4` ORAS: u16 arrays per language; a translated Pokédex sort needs them regenerated), strings in `code.bin`, the e-manual (CIA content 1).
- The fonts have no Cyrillic at all (free cells: 3 / 0 / 46 / 1, ORAS large font 10): every Ukrainian letter is a new glyph the Font Editor adds (3DS fonts now grow by sheets; a grown font is checked by machine, not yet in the game).
- The English pictures (title logos, battle buttons, gym names, Pokédex) are checked by machine only: the first boot goes straight to the language screen, which shows no text picture; the title screen needs save data.
- The title updates (X/Y 1.5, ORAS 1.4) are not on disk; their text differences, if any, are unknown.
- Alpha Sapphire's CIA is not on disk; the scripts handle it once it is in `ISO\` (title id 000400000011C500).

## Pokémon Sun/Moon + Ultra Sun/Ultra Moon (`plugins/pokemon_gen7`, 2026-10-11)

- Not opened: the `PC` packs of `a/0/9/4` (10,422 members), `a/0/8/7` and `a/0/9/8`; they are not text, fonts or pictures found so far.
- The picture GARCs hold many languages; the English subset is not separated yet, so the project opens every FLIM picture of the eight GARCs.
- Not checked in the game: a boot with a visible edit in Azahar (no run has been made yet for Gen 7).
- The v1.2 update of each Ultra game is read as an overlay; its title version field reads 0 in the CIA header, so the choice rests on the file content.
- Sun and Moon share every English file; Ultra Sun and Ultra Moon share every English file too (checked by machine on the unpacked images).

## Pokémon Sword/Shield + Legends: Arceus (`plugins/pokemon_nx`, 2026-10-09)

- Not opened: the `grammar/*.dat` and `sort_string` tables (binary, not text), strings in `main`.
- The donor glyphs of `translation_map.json` (Э э Ъ ъ for Є є Ґ ґ) are not redrawn yet; the bitmap fonts (`bmp/*.bffnt`) have no Cyrillic at all (free cells: 25-181 per font, `font_fs_150_bold_00` opens with 2 spare sheets).
- The title screen logos are checked by machine only (the "white screen" after the photo select in Eden is the name
  entry: Eden's own software keyboard window, which an emulator run on a hidden desktop does not show).
- The two Legends: Arceus `*_eng.gfpak` packs (battle menu, HUD) are checked by machine only, not in the game.

## Textures window (`core/texture_formats`, 2026-10-04)

- ASTC decoding is pure Python: Origami King's 8640x8640 ASTC 10x10 sea chart (`ui/event/W4G1_Charts`) takes ~2.5 min to
  open and ~1 min to write back; `museum.bntx` (ASTC 8x8 gallery art) several minutes.
- Not encoded yet: BC6H; ASTC block sizes other than 4x4, 8x8, 10x10 and 12x12 (ASTC encoding writes one RGBA line per
  block with a 4x4 weight grid, BC1-like). TotK layout archives are copied into `source/UI/LayoutArchive` by hand: `zt/nx.py`
  `TOTK_PARTS` does not unpack them yet. Textures inside models (TP title logo in `titlelogo_r.bmd`, WW subtitle in two BDLs, WW HD `Tlogo.bfres`), the Wii channel banner (`opening.bnr`: IMET > U8 > LZ77 > U8 > TPL, LZ77 not handled).
- No container yet: TPHD TMPK/GTX (needs a decrypted dump), MGS `stage.dat` (zlib folders > tex13 packs > TPL: 449 textures; the TPL itself is handled — needs the stage.dat container or loose packs from the workspace unpack), 3DS BCH and SPBD particles (TFH boss cards). Drafts: `E:\Emulators\RomHacking\_shared\textures\drafts`.
- 3DS games have no plugin: their textures open with File → Open (BFLIM, CTPK, CTXB; SARC/SZS, ZAR/GAR, LzS archives) and are edited in place; a plugin with `texture_sources.json` (drafts `zelda_albw`, `zelda_tfh`, `zelda_oot3d`, `zelda_mm3d`) would list them. OoT3D title logo letters are in a CMB model (not handled).
- Majora's Mask `yar` archives have no room to grow in the ROM: an edit that compresses worse than the original is fitted by recompressing every block of the archive optimally; if even that does not fit, the save is refused with the file's size.
- An archive around an edited texture is laid out anew by its container code (SARC, RARC); Revert restores the texture file byte for byte, not necessarily the archive.
- Helper to erase the English and render Ukrainian with the game font (later).

## Startup speed (2026-10-04)

Measured offscreen from process start to "open sequence complete"; Twilight Princess 5 s, Minish Cap 1.7 s,
The Wind Waker (GameCube) 1.2 s, Ocarina of Time / Majora's Mask 0.5 s.

- Done (2026-10-17): **Reference languages are parsed on a worker thread** (`ReferenceManager.load_in_background`,
  `plugin_settings.load_reference`). The Twilight Princess plugin gives the worker its own copy of the tag mapping
  (`reference_worker_rules`); the aliases the parse registers are copied back on the window's thread. One parse
  runs at a time and only the latest request is applied. The parser also reads each archive once (on Windows
  `*.arc` and `*.ARC` matched the same files). Measured offscreen on a copy of the owner's project: the parse
  took 2.2 s on the UI thread, now 1.35 s on the worker; the open went from 4.8–6.2 s to 3.1–3.9 s. Output
  identical (same 78,110 strings and aliases; `tests/test_core/test_reference_background.py`).
- **The block tree is built on the UI thread** (`populate_blocks`, Twilight Princess 1.8–2.2 s of the open, measured
  2026-10-17): virtual story and speaker folders (`_add_story_root`, `_add_windows_projection_root`) ~1.7 s, the
  speaker pool (`build_speaker_pool` → `get_speaker_for_string`) 0.6–0.7 s, `_apply_virtual_issue_indicators` and
  `_story_mapping_indices` ~2 s of profiled time, and the MemPalace client import (`core/mempalace/client.py`) ~1.2 s
  the first time a story folder is built. Not moved: each step reads the message flows and the story overrides, so a
  worker needs those as snapshots first.
- **The issue scan runs one whole block per UI-thread step** (`issue_scan_handler._scan_next_batch`): a game
  whose text is one block (N64: 4589 strings) freezes the window for ~2 s at the first open.
- **An enabled spellchecker parses its dictionary in a Python thread** (pure-Python `spylls`, 2–3 s of CPU
  that the UI thread shares). Keep the parsed dictionary on disk, or parse in a process.
- **A project without its own MemPalace database gets one in the working directory**
  (`mempalace_local.db` next to where the application was started), not in the project folder.
- **`SettingsManager.load_unsaved_session` uses `eval` on keys read from `settings.json`**
  (`core/settings_manager.py`); `ast.literal_eval` is enough.

## Twilight Princess Wii / HD (2026-10-04)

- Build status (2026-10-17): **GameCube disc image** and **Dusklight mod** (`gc_iso`, `dusk_mod`) and the **Wii U
  graphic pack** (`wiiu_mod`) are built by Picoripi. Checked on copies of the owner's files: the GameCube archives
  and fonts equal the owner's `UA` folder; the Wii U pack equals the owner's `zt` build byte for byte except the
  description line. Not verified in an emulator or on a console.
- **Wii disc (RZDE01): no build target.** Its partitions are encrypted; a build needs a partition writer (re-encrypt
  each changed cluster and rebuild the hashes). Open; the owner's `GC + Wii\Patcher` still makes the Wii image.
- **Run in emulator for Wii U is not wired.** The host passes the build folder to the emulator command; Cemu needs the
  game file (`-g <game>`). Leave the Wii U command empty; run the pack with the workspace `3_run.bat`.
- **Project unpacked before 2026-10-17 has no disc record** (`.picoripi_disc.json`). Its build is refused with
  "unpack the disc again". Create the project again in the wizard.
- **HD source needs the owner's `source\content`** (`FileSizeList.txt` and `DecompressedSizeList.txt` two folders
  above `res\Msguk`); Picoripi does not unpack the HD game yet (`1_unpack.bat` still does).

- **No clean English TP HD dump on this PC.** `TPHD_UA\source` is a stand-in: the UK English archives of the
  Kruptar project (compressed again) with the Russian patch's fonts and size tables, matching the installed
  Russian build Cemu runs. A decrypted USA/EUR folder (`tphd_game` in `_tools\zelda_env.ini`) gives the real
  `Msgus`/`Msguk`, `Fontus`/`Fonteu` and size tables. The clean USA disc is now on disk
  (`TPHD_UA\iso\…(USA) (En,Fr,Es) (Rev 2).wux`, WUP-P-AZAE; WW HD: `WWHD_UA\iso\…`, WUP-P-BCZE), but it cannot be
  decrypted here: neither the disc keys nor the Wii U common key (`otp.bin`) are on this PC. Needed from the
  user's own console and discs: `otp.bin` (in `%APPDATA%\Cemu\`) and each disc's `game.key` next to its `.wux`
  (or hex lines in Cemu's `keys.txt`).
- **HD glyph textures live in `res/Font*/*.pack.gz`** (GX2 R8, 2D tiled) and the game draws from them. The
  workspace build redraws them from the BFN sheets; the Font Editor itself only writes the BFN.
- **HD width checks use the GameCube font map** (`zelda_bmg/font_map.json`); HD glyph widths are in 54-px cells.
  Confirm the HD box widths against the game, or measure from the HD font.
- **HD Wii U icon textures**: group 7 (`{U:…}`) previews are vector icons; take the real ones from an HD dump.
- **The last glyph's width in a BFN is not editable**: `WID1` holds `last - first + 1` entries, the editor reads
  `last - first` and keeps the last one as padding (TP HD: `щ` of the Ukrainian map sits on glyph 220).
- **Carry the GameCube translation over**: Wii and HD share message ids with GameCube; 8,915 Wii and 8,111 HD
  English lines are word-for-word the GameCube ones. A one-shot copy of the GameCube Ukrainian lines into the Wii
  and HD projects needs the owner to say which GameCube state is current (the session or `TP_UA\ISO\UA`).

## Castlevania: The Dracula X Chronicles (`plugins/castlevania_dxc`, 2026-10-09)

- The disc is the English Asian release ULKS-46155 (named USA in the workspace). The built image's EBOOT is the
  plain BOOT.BIN ELF when the program changes (as fan translations do): checked in PPSSPP only.
- Symphony of the Night strings are found by pattern (some false hits, e.g. code names) and keep their room;
  growing them needs the overlays' pointers (`.rel` relocation data) moved. Its Ukrainian letters need the 8x8
  font's kana cells and a cell map; the description font of the PSP port was not located.
- Not opened: the PC Engine game data (`DRACX_02.DAT`, the Japanese disc; English parts are pictures),
  `PSP_GIM.BIN` (unknown `GDT` format), Japanese-only TIM2 font sheets (`pce/arc/*font*.tm2`), movies.
- Not seen in the emulator: the dialogue text and the dialogue font (stage 1 needs the prologue boss beaten);
  checked by machine in the built image.

## Lunar: Silver Star Harmony (`plugins/lunar_ssh`, 2026-10-07)

- The built image carries a disc font (Liberation Sans Bold from PPSSPP, not the retail FTT-NewRodin) and a
  decrypted, patched EBOOT (plain ELF). Checked in PPSSPP only; a real PSP needs a custom firmware that runs
  plain EBOOTs. Ukrainian letters use cp1251 codes (script words U+0400-04FF are control codes).
- Not opened: the program's own strings (EBOOT is encrypted; the decrypted dump holds only the save-data titles),
  subtitles burned into the `PMF_US` movies (the Russian build re-encoded 30 of them), Japanese-only tables
  (`PLACE`, `PRESS`, `MAKESHIFTSYSTEM`), sprite and map packs (no text).

## Vagrant Story (2026-10-04)

- The USA disc (SLUS-01040) is the base. The European disc (SLES-02754) is LibCrypt-protected (DuckStation
  refuses it without `Vagrant Story (Europe).sbi`) and its executable is compressed: not supported.
- Balloon sizes are fixed by the scripts' DialogShow opcodes (characters per line, lines). The Russian build
  widened or narrowed 530 balloons; the plugin shows the width as the limit but cannot change it yet.
- Files keep their size except events (6144-byte slots) and rooms (to the end of their last CD sector). Help
  pages, item help and menus have no spare room: Ukrainian has to fit the English bytes (a space is one byte,
  `FA 06` indents can go). Growing them needs the file sizes in the executable's load tables.
- Names in program and zone data are found by their shape (`program.py`) and edited in place; a few short
  fragments of record data may still show as lines.
- The Ukrainian letters in `FONT\VSFONT.FNT` are a rough draft (Arimo, both sets): polish them by hand.
- Text in textures (HUD sheet in `SYSTEM.DAT`, title menu, GIM cards, DIS screens, help pictures) is not
  edited by the plugin: catalogued in `ZELDA\_textures\drafts\vagrant_story.json`.
- No speaker data: a balloon points at a character on screen; scene context gives area and room only.
## Metal Gear Solid, PlayStation (2026-10-07)

- The font `font.res` has only the 96 ASCII glyphs (no free cell): no Ukrainian letter yet. The game draws codes
  `80 xx` above 0x80 from the same table, so the table could grow; not tried.
- A subtitle block may grow only into the rest of its stream's last sector (about 1 KB on average): moving
  streams needs the stream codes in the scripts and codec calls. Program and overlay strings keep their slot.
- Textures: the Textures window lists the PCX of 15 menu, title and briefing stages; the build puts any changed PCX
  back into every stage that holds it. Briefing pictures (`BRF.DAT`, `.pll`) and codec faces (`FACE.DAT`) are not opened.
- Codec call speaker names are character codes (`character 21ca`), not names.
## Yo-kai Watch plugin (`plugins/yokai_watch`, 2026-10-04)

- The fonts' new Ukrainian glyphs: seen in Azahar in the main font (ft_nrm); the small font (ft_sml) grew from 405
  to 417 rows to fit them and no small-font line with Є / Ґ was seen in the game yet.
- 32 % of map NPC lines have no speaker: their talk is started from event scripts (`.xq`), not the talk tables.
- Text textures: 594 listed (`texture_sources.json`), none redrawn yet; 15 skill banners still show Japanese.
- The mod is the whole `yw1_a.fa` (~390 MB); a loose-file override was not tried.
- Yo-kai Watch 3 (EUR): the dump has English only (`yw_lg_en.fa`), so no reference languages; its 3,368 English
  textures are not catalogued (the YW1 `texture_sources.json` globs do not match); no script markup yet;
  15 % of event lines and 27 % of NPC lines have no speaker.
- Yo-kai Watch 1 (Switch, 2026-10-07): the 13,820 lines the English fan mod left Japanese (mostly maps t151g00–t156g00)
  are shown since 2026-10-08 (category "Japanese source"); whether the game reads a Shift-JIS table saved as UTF-8
  (footer byte 1) was not seen in the emulator; the game has no width limits measured yet (`layout.json` has no `ywnx`
  section); the L4 texture format (one effect test texture) is not supported.
- Yo-kai Watch 4++ / Yo-kai Academy Y (Switch, 2026-10-07): no speakers, glossary seed or width limits yet (the
  new `data/common` layout); the lines the English mods left Japanese (Academy Y about 12,300, YW4 551) are shown since 2026-10-08;
  the opening staff roll (`gamedata/staffroll/*.cfg.bin`, RDBN format) and the 200_icon pictures are not in
  the editor (the mod's English staff roll is built as it is); the G4 fonts lack Ґ Є І Ї ґ є і ї.

## Metal Gear Solid: The Twin Snakes (2026-10-04)

- Which strings of a GCX table are English is detected (voice clips settle ~92 % of codec lines, the rest by
  stopwords and run lengths): a few unvoiced menu/briefing strings may be misfiled; check `stage/n_title.gcx`
  and `stage/r_cmmn.gcx` in the editor.
- Text textures (Tools → Textures, `texture_sources.json`): the title/menu pictures of `n_title` are drawn in
  Ukrainian (workspace `tools\menu_textures.py`); still English: credits, intro titles, place-name cards, HUD
  plates (ALERT, EVASION…), game over, the mission results of `ending`, the item-window and photo/memory-card
  labels of the `r_*` packs that differ from `n_title`'s, the pause EXIT of the area stages, the briefing's
  Japanese labels. The HUD font has Ukrainian letters in unused ASCII cells (`rel.HUD_LETTERS`, workspace
  `tools\hud_font.py`; not redrawn in the demo14a copy of the sheet); only LIFE is translated.
- Five speaker hashes are unnamed (`0x663ee3`, `0x28dce6`, `0x1932cc`, and two guessed in
  `plugins/mgs_ts/speakers.json`: `#9331f5` Snake, `#388785` Psycho Mantis).
- The clean ISOs are NKit (DolphinTool cannot undo NKit); patches made against them need the same NKit images.
- Seen in Dolphin 2026-10-04 (input movies, no keyboard): the options help, the first codec call after the
  intro, the codec opened in play (Start + A). Measured: codec rows wrap above 509 font units (509 fits, 514
  wraps), the options help row at the screen edge (711 fits, 725 wraps). The item-description, memory-card,
  briefing and photo windows were not measured: their limit is the widest English row of the neighbouring
  strings (`get_string_layout`), a guess from the English layout. Subtitles keep the block's widest row + 5 %.
- The codec box shows four rows; a fifth row (a long line the game wrapped) is not shown.

## Paper Mario: The Thousand-Year Door (`plugins/paper_mario_gc`, 2026-10-04)

- Window limits are the widest English line of each window kind (`LAYOUTS`), not measured in the game; the
  icon advance (`ICON_WIDTH` 36 × scale) and the placeholder widths (`{ITEM}` 130, `{NUM}` 30) are estimates.
- The game skips the line feed after a tag-only line; the editor still counts such a line as a line.
- Speakers: 3,472 of 13,018 messages (event-script `evt_msg_print` calls); messages chosen at run time by
  a variable, `evt_msg_print_party` and the 431 calls of the other message function (0x800d23c4) carry no
  speaker yet. A few NPCs keep their Japanese internal name (`乱`, `キノシチョフ`, `ダミー`).
- Growth: `global.txt` at +40 % (335 KB) boots to the file menu in Dolphin; the big area files (map heap,
  `gor_02.txt` 129 KB) were not grown in the game.
- The Ukrainian glyphs are drawn from Balsamiq Sans Bold: the game's face is Fontworks PopJoy, and no Cyrillic
  PopJoy exists on this machine (Switch TTYD and Origami King PopJoy have none) nor a Russian fan build.
- 188 text textures are listed (`texture_sources.json`, draft `ZELDA\_textures\drafts\paper_mario_gc.json`);
  which of two English pause-tab sets (`icon.tpl` or `w/us/win.tpl`) and which sign variants the US game
  draws is not confirmed.
- Not opened (2026-10-07): the system messages in `sys/main.dol` (progressive scan, disc cover, disc read
  error) are drawn with the console's ROM font, which has no Cyrillic; the disc banner `opening.bnr` is shown
  only by the console menu. Every TPL on the disc (1,263 files, 8 GX formats) reads and writes back byte-exact.

## Super Paper Mario (`plugins/super_paper_mario`, 2026-10-07)

- Not opened: the disc-error messages in `sys/main.dol` (2_build writes only `files/`) and the channel title
  in the `opening.bnr` IMET header. No speakers, glossary seed or measured window widths yet (the
  Thousand-Year Door widths are the default); no `papermarioset_EU.json` width map until the Font Editor saves one.
- No font has Ukrainian letters: `papermarioset_EU`/`_US` and the HOME Menu font have no Cyrillic,
  `papermarioset_JPN` lacks Ґ Є І Ї ґ є і ї. `translation_map.json` is the Thousand-Year Door one (Latin-1
  slots); the PAL disc's French, German, Spanish and Italian text use those slots too.

## Font editor formats (2026-10-03)

- Ukrainian glyphs drawn and shown on screen 2026-10-04 (Dolphin WW, SoH, 2Ship, Eden HWDE, Azahar for the 3DS
  fonts, Eden for Cadence of Hyrule's `LoveBug.bffnt` with a new sheet of Cyrillic; contact sheets and screenshots
  in each workspace's `reports\fonts\`): the letter shapes are rough, a hand touch-up is the owner's. Not shown in
  ares (keyboard input could not reach OoT's name-entry screen); the ROM font bytes equal the SoH/2Ship textures.
  TotK: Eden shows Ukrainian in the title menu (Rodin, already Cyrillic); the glyphs added to its other fonts are
  not yet seen on screen.
- 3DS fonts: the future text plugins (`zelda_oot3d`, `zelda_mm3d`, `zelda_albw`, `zelda_tfh`) should list them in
  `font_sources.json` (formats `qbf`, `gzf`, `bcfnt`; ALBW/TFH: `EU/RegionBoot.szs` / `Archive/EU/RegionBoot.szs`
  member `EU/Font/MessageFont.bffnt`); until then they open with File → Open. A 3DS font cannot change or drop a
  character it has; adding codes to a CMAP scan list that is not the file's last block leaves its old copy as
  dead bytes (a few hundred per save). Outlined fonts (ALBW/TFH) need the outline drawn by hand or by script:
  Render Font draws the letter only.
- HWDE widths are the executable's `f32` tables (`font_eu` / `font_eu_p`, 224 codes each), patched by
  `translation\exefs\<build id>.ips` for 1.0.0 (`0C869F41…`, what Eden runs from the base NSP) and the update
  (`815A2C19…`); shown in Eden 2026-10-04 (`HWDE_UA\reports\fonts\screen_eden_widths.png`, before:
  `screen_eden_widths_before.png`). Not run on a Switch (Atmosphere `exefs_patches`) or in Ryujinx; another game
  version needs its build id and table address in `font_sources.json`. The Cyrillic advances are ink + the Latin
  median gap (rough, like the shapes).
- The N64 slot maps are confirmed (2026-10-04): no English message, credit, code-printed text, name entry or
  SoH/2Ship text uses a cell a Ukrainian letter takes, and every glyph fits its cell
  (`plugins/zelda_oot64|zelda_mm64/translation_map.md`).
- TotK's fonts are scalable OpenType (`bfotf`): the editor saves widths and redrawn glyphs (traced as squares:
  drafts only); finished outlines are made outside (FontForge on the unscrambled OTF) or by
  `plugins/zelda_totk/font_glyphs.py`. TrueType `.bfttf` takes drawn glyphs the same way (simple glyphs in `glyf`; composite glyphs that use an edited glyph change with it).
- Animal Crossing: New Horizons stopped at start in Eden (crash 3-4 s after the mod loaded) when `Font/ScalableFont.sarc.zs` grew; with text and texture edits only it ran. The font rebuild now keeps the archive's size for a glyph edit (test), a boxed 'e' in the dialogue font was seen in Eden, and the workspace's `2_build` stops when that archive grew. Adding glyphs to these fonts would need the game's buffer size (not known).
- BFFNT (Switch): new characters get a CMAP block and new sheets a texture layer (`min_sheets`); the kerning table
  (KRNG) is kept as it is, and a removed character outside the changed code range still resolves.
- HWDE: the `../romfs/...` candidate assumes the workspace layout `source/` next to `romfs/` and a translation
  folder named `romfs`.
- Opening a font and listing archive members still reads the archive on the UI thread (small files);
  the old BFN paths (`load_bfn`, saving a BFN) are synchronous as before.
- Next formats: Tingle Tuner (GBA), Wii U BFFNT (big endian, GX2 tiling). Cadence of Hyrule's BFFNT already
  opens; the 3DS fonts are done.

## Tri Force Heroes plugin (`plugins/zelda_tfh`, 2026-10-07)

- No speakers or scenes: the file names the NPC (`NpcKing`), the MSBF flows (`Common/Message/FlowChart`) are not
  decoded.
- Layout texts (`Layout*`) have no width limit: the message project's styles name layout panes, not messages.
- Boss title cards (`Telop.ptcl`) and the title logo (`PictureStory_EU.bch`) are listed by fixed offsets (format
  `raw`); a game update that moves them needs new offsets (the real-data test reads them).
- Not opened: the Download Play child (not in the workspace), code.bin (only debug and network strings), the other
  BCH textures (models, the storybook pages without text).
- Azahar takes the foreground when it starts, also when started through WMI.

## A Link Between Worlds plugin (`plugins/zelda_albw`, 2026-10-07)

- No speakers or scenes yet: labels name the NPC (`lgt_NpcSahasrahla_Field1B_00`) and the MSBF flows give
  conversations (`reports/flow_refs.tsv` in the workspace); not used.
- Dialogue width (344 px) is the widest retail English line, not a measured box. 96 layout texts have no style in
  the message project and get no width limit.
- No reference languages: the game's French, German, Italian, Spanish and the Russian build (`RU
omfs`) could be
  matched by archive, file and label.
- Not opened: the Home Menu title (`exefs/icon.bin`, a LayeredFS mod cannot replace it), the e-manual
  (`EU/Manual`), code.bin (only debug strings). BCH model textures and CTPK are language-neutral (the same bytes in
  all five languages), so they hold no text to translate.
- Azahar takes the foreground when it starts; the proof run needs Vulkan for PrintWindow.

## Ocarina of Time 3D plugin (`plugins/zelda_oot3d`, 2026-10-07)

- No speakers or scenes yet: the message ids equal N64 Ocarina of Time, so `plugins/zelda_oot64/context.json`
  could give speakers for about 2,000 of the 2,510 messages.
- Box width (285 px) is the widest retail English line, not a measured box; `{mq}…{mq-else}…` lines count both
  branches. Meanings of `{xpos}`, `{record}`, `{credits}`, `{plural:N}` and box types 6-12 are guesses.
- Not opened: the HOME menu title and banner (`exefs/icon.bin`, `banner.bin`; a LayeredFS mod cannot replace
  them), the re-made hint video `misc/hint/movie/hint183.moflex` (video), the name-entry keyboard textures of the
  German, French, Spanish and Italian menus (shared keyboards; only needed when the console runs in those languages).
- Azahar takes the foreground when it starts even with `SW_SHOWMINNOACTIVE`; the proof run needs Vulkan
  (PrintWindow gives black frames with OpenGL).

## Majora's Mask 3D plugin (`plugins/zelda_mm3d`, 2026-10-07)

- No speakers or scenes yet: 4,472 of the 6,152 message ids equal N64 Majora's Mask, so `plugins/zelda_mm64/context.json`
  could give speakers for most of them; the 3DS-only ids need scene or actor analysis.
- Box width (280 px) is the widest retail English line, not a measured box. Meanings of `{chest-flags}`, `{owl-warp}`,
  `{lottery-code:N}`, `{layout}`, `{ordinal}`, `{event:N}`, the 3DS button numbers of `{btn:N}` and bit 15 of
  `{delay}` are guesses; codes 0x1A, 0x1F and 0x30 never occur and are refused (argument size unknown).
- The retail font `ltn16.gzf` has no Ґ Є І Ї ґ є і ї; the draft `translation\romfs\message\ltn16.gzf` has them (476
  glyphs, not polished).
- Not opened: the HOME menu title and banner (`exefs/icon.bin`, `banner.bin`; a LayeredFS mod cannot replace them).
  Checked and left out as they hold no text: the Sheikah Stone hint videos (`hint/movie/*.moflex`) and slides
  (`hint/slide/*.jslide`, stereo screenshots), the language-neutral layouts (story intro, ocarina, ending images), the
  debug `ascii_8x16.ctxb`; the French, German, Spanish and Italian layouts and title cards (other console languages).

## Castlevania GBA plugin (`plugins/castlevania_gba`, 2026-10-08)

- Text pictures show in grey (palette indices): the palettes are set per screen by the game and are not read yet.
- The text pictures listed are the English ones the Russian fan translation also changed, plus the AoS staff roll
  and the HoD title logo; other sprites with text may exist. The AoS ROM's French and German pictures are left out.
- HoD: the second set of narrow letters (`8566`-`858B`) is not used by the text and shows as `[xHHHH]`; the
  width table of the narrow letters is not edited (the Font Editor shows those widths only).
- Control codes are named from how the English text uses them (`[fx:XX]` meaning unknown).

## Castlevania DS plugin (`plugins/castlevania_ds`, 2026-10-09)

- Order of Ecclesia keeps its French text (overlay 1) as it is; the Ukrainian letters take accented-letter cells,
  so a redrawn letter also changes the French text. The `_e` and `_u` picture sets of OoE are both listed (the US
  game was seen using the `_e` title logo).
- Pictures: colours come from DSVEdit's palettes (one bank per sheet; background sheets whose tiles use several
  banks show some tiles in the wrong colours). Pictures DSVEdit keeps in overlay RAM (DoS/PoR info screen, HUD,
  map backgrounds) are not listed; the 3D model textures (`.nsbtx`) are not opened.
- Dawn of Sorrow: the free-space overlay holds 48 KB; if a translation moves more than that out of the old string
  area, the build stops with a message.
- The fonts advance by a fixed step (8 px); the width check uses that step.

## Final Fantasy XII: Revenant Wings plugin (`plugins/ff12rw`, 2026-10-09)

- Seen in NO$GBA (hidden desktop, keys posted to every emulator window): striped title and company logos, and
  the first event line made 40 characters longer with a filled `e`. The opening scroll edit, the menus and the
  airship talks are proven by machine only (`tools\proof_edits.py`: plugin save, build, read back from the ROM).
- A longer mission objective (`Stage.dpk`) moves the stage member's later sections and fixes their offsets;
  nothing else in those members is known to point into them. Event and airship talk records keep their unknown
  fields (box size?) as they are.
- The fonts are Windows-1252 and have no Cyrillic: Ukrainian letters need codes the English text does not use
  (each font has 117+ such codes, `spare` 72 empty cells for new ones); the mapping is not made yet.
- Sprite sheets show in storage order; colours come from the NCLR of the same name (a guess where an archive
  has several). The 3D model textures (`.nsbmd`) and the videos (`.vx`) are not opened.

## Final Fantasy Tactics A2 plugin (`plugins/ffta2`, 2026-10-09)

- Seen in NO$GBA: striped title logo and the first line of the opening made longer with a filled `e`; the
  menu packs grew and moved to the end of `pc.bin` (the game reads them there).
- Not found: the file with the title menu words (New Game, Load, Continue, Trade, Language, Difficulty); 421
  effect files (`EFX0010`) are in `pc.bin` and only three have known names; the battle title pictures
  (`battle/bt_title/us/*.ebn` / `.obn`) are in a format not read yet.
- A glyph added to the font gets a text code from 0xA9 to 0xBF; whether the game draws codes beyond its 168
  glyphs is not tested. The name-entry keyboard (table 20) holds all accented letters.

## The World Ends with You plugin (`plugins/twewy`, 2026-10-07)

- Seen in NO$GBA (hidden desktop) only up to the title screen: input posted to the emulator window does not
  reach the game, so the text (`UA TEST`) and font (filled `e`) edits are proven by machine only
  (`tools\proof_edits.py` of the workspace: plugin save, build, read back from the ROM).
- Sprites (most text pictures) show as a plain tile sheet in storage order, and a pack's palette is guessed
  (first plain member of whole banks); the cell tables that place the tiles are not read yet.
- Not opened: `Static/Font_Funakosi.bin` and `UsrLib/FontData.bin` (Shift-JIS system/debug fonts with their
  own glyph coding, not used by the message text), `Apl_Suy/staff_font.bin` (credits table), `Apl_Mot/*.nsbtx`
  (3D textures, no text seen). No font has Cyrillic letters.
- Control codes `FFB6`-`FFBE` (colours) and `FFD0`-`FFD2` (values the game fills in) are named from how the
  English text uses them.

## Four Swords Anniversary Edition plugin (`plugins/zelda_fsae`, 2026-10-04)

- Not seen in a game: no DSi emulator on the PC (melonDS + DSi BIOS/firmware/NAND needed; no$gba has no BIOS) and
  no console run yet. Proven by machine only: the workspace's `tools\proof_edits.py` saves a text, manual, texture
  and font edit through the plugin, builds the SRL and CIA and reads the edits back (hashes valid).
- Picture widths (`[icon:N]`, `[button:N]`) are guessed 12 px; the code meanings (`[next:N]`, `[event:N]`,
  `[player:N]`, colours) are read from the English text, not from the game code.
- (2026-10-07) Text picture colours: proven from the game files for the subtask sheets #0-#2 (sprite cells +
  NCLR), the title logo and copyright line (BG maps + palette) and CHOOSE A STAGE; the engine sprites (area
  plates, GAME OVER letters, PLEASE WAIT, player marks, Back, script lettering) and subtask #3/#4 take a bank
  chosen by eye from the palette their screen loads: check them in an emulator (`plugins/zelda_fsae/palettes.py`).
- GAME OVER (block `game_over`, `main.arm9`): the English letter table has 16 entries (7 used) and the letter
  sheet 128 tiles (the eighth 32x32 cell empty, narrow letters as 16x32 / 8x32 free more); the sheet cannot grow
  (the next graphics follow it in VRAM). Ukrainian letter sprites are still to be drawn by a person. The
  name-entry keyboard (`main.arm9` 0xDAC1C) is Latin and not opened (no decision yet).
- The manual is drawn with the console's shared font (`nand:/<sharedFont>`), not a game font: whether it has
  Cyrillic is unknown; manual line widths of new lines are estimated (the font is not on disk).
- `eu.kmsg` may have a size limit in the game (the Russian build shares texts to stay under the original size);
  `2_build` warns when the Ukrainian file is larger than the Russian one.

## Cadence of Hyrule plugin (`plugins/zelda_coh`, 2026-10-04)

- Owner decision: the Ukrainian glyphs of `LoveBug.bffnt` (the menu and text font, no Cyrillic; the second
  sheet is free for them) and the four missing letters Є є Ґ ґ of `ZeldaGlyph`/`ZeldaGlyphSmall` must be drawn
  in the Font Editor. Which screens use ZeldaGlyph and the Asian fonts in English mode was not mapped.
- Text in images: the five pictures with English text (title logo, four pause-menu tab names) open in Tools →
  Textures from `textures_bin/texture_pack.bin` (all 8,700 game and DLC textures are BNTX RGBA8; the boss packs and
  DLC packs hold no text). They still have to be redrawn by a person. `bosses/Vaalni_Splash_Anim` (the word
  "Octavo") is not referenced by the game's executable and is left out. The mp4 videos (intro, victory) are not
  opened. A reverted texture leaves the pack recompressed (same content, other zlib bytes).
- Speakers come from string keys; 20 keys (`mellan`, `gerudo_leader`, `zora_leader`...) stay `npc:<key>` until
  someone names them. Dialogue box limits (lines per page, wrap width) are not known; only short labels get a
  width limit (1.3x / 1.6x the English).
- `credits.xml` opens as the "Credits roll" block (lines with `textKey` take their text from `localization.xml`
  and are not shown). Whether names should be transliterated is the translator's choice.

## Skyward Sword plugin (`plugins/zelda_sshd`, HD and Wii, 2026-10-04)

- Owner decision: the Ukrainian glyphs are machine drafts (HD `special_00` from the official Russian font; every
  Wii font scaled from the HD ones, Wii `normal_02` turned into plain fill; Є mirrored from Э, Ґ an upturn on Г)
  — polish them in the Font Editor; the widths and baselines are already set from the fonts' Latin letters.
- Eleven control tags keep neutral names (`{ctl7}` `{ctl10}`…`{ctl19}`): their effect was not identified from the
  text; they round-trip byte for byte.
- Speakers: 49 % of talk/Fi-window lines; the town files (`100-Town`, `115-Town2`, `118-Town3`…) have many NPCs and
  no speaker data (the flow an NPC starts is chosen in the executable, not in `room.bzs`).
- Line limits: HD windows 0, 27, 29, 31 (options, quest log, system) have English lines the HD wraps itself — no limit
  is set there; lines after `{textSize:-1/-2}` are measured at normal size (they may hold more).
- The fonts `normal_01`/`special_01` the layouts name are mapped by the executable to the `_00` files (seen working on
  the title screen); not traced in the code.

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

## Age of Calamity plugin (`plugins/zelda_aoc`, 2026-10-04)

- Font work for the owner: the G1N Latin font (`font/latin.g1n`, sizes 0-6) has no Cyrillic; the glyphs have
  to be drawn (Font Editor adds them). `fonts/aoc_latin.json` holds estimated Cyrillic widths until then.
- Speaker ids not tied to a name show as `chara_NNN` (1 mission voice, 14-17 Great Fairies, 20/21, 48+);
  cutscene subtitles carry no speaker. The id -> actor table was not found.
- Which English table (EN or EN2 of the battle dialogue) and which of the six Latin font ids a console
  language uses is unknown; the build writes both tables and all six fonts.
- Line limits are the widest English line per table; the real box widths are not measured.
- Not covered: movies (`movie/*.webm`). The executable has no player text (checked 2026-10-07: only
  zlib/shader debug strings). Text pictures (33 G1T, BC1/BC3, linear) open and build since 2026-10-07; an
  edited picture was not yet seen in the game (the title logo needs a save past the first battle).
- Watch: `tests/test_ui/test_font_editor_formats.py::test_font_jobs_run_in_a_worker_thread_one_after_another`
  crashed its xdist worker (access violation) every time it ran first in a worker while that module had a
  fourth test; the G1N editor test therefore lives in `test_font_editor_g1n.py`. Cause not found.

## Hyrule Warriors DE plugin (`plugins/zelda_hwde`, 2026-10-03)

- Ran in Eden 2026-10-04 (text, redrawn `font_eu*.g1t` and the patched width tables show Ukrainian without
  overlaps); not on a Switch.
- Voice-line speakers for character ids 18-99 are `chara_NNN` (the names table disagrees there); event and
  movie scene ids are not tied to story chapters. The executable has no game text (only debug and shader
  strings, checked 2026-10-07).
- 2026-10-07: Ч з й с moved to the slots 0xDA 0xFA 0xFB 0xFD (× ç é ñ are used by the English text and the
  language list). The workspace's draft fonts were migrated the same day (cells copied block for block, the
  game's × ç é ñ put back).
- Mirroring into the English-EU section (British English consoles) is kept on purpose (decided 2026-10-07); it
  also fills cells that are empty there (e.g. the language list).

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
- **How many conversations in Twilight Princess are longer than 12 lines — and are therefore still cut — is measured
  (2026-10-17, the owner's GameCube project on a copy):** 15,622 strings in 1,165 conversation groups; 81 groups have
  more than 12 strings (1,776 strings in all); the largest has 77. A group over 12 is cut into runs of 12
  (`handlers/translation/worker/run_mixin.py::pack_groups`). **Stays as it is:** a larger request size is a cost and
  quality choice for the AI requests, and the owner decides it.

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
- Done (2026-10-17): **`plugins/zelda_bmg/window_frame_loader.py::_KNOWN_DUMP` is gone.** The Layout folder is found from
  the project's `source_path` (absolute, or relative to the project folder) and then from its blocks. A project made
  before has the game folder there, so it needs no setting. Test: `tests/test_plugins/test_zelda_bmg_layout_root.py`.

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
- **Tests bypass `mock_open` now.** `utils.atomic_io` does not go through `builtins.open`, so a test that only
  mocks `open` and passes a path outside `tmp_path` writes a real file. A traced full run (2026-10-02) found
  none left; new tests should save into `tmp_path` or patch `atomic_write_*` in the module under test.

## Found during WP5

- **`ui/main_window/bfn_actions.py` still imports the BMG parser** (`from bmg_tool import BMGFile, BMGMessage`,
  through the root shim) for the "Import / Export BMG JSON" actions and calls `msg_to_editor_text`. These are
  Twilight Princess actions living in the main window; they belong in the plugin's `get_plugin_actions()`.
  Open (2026-10-17, why it stays): the two actions are fixed items (`ui/builders/menu_builder.py` 508–528, wired in
  `ui/main_window/main_window_event_handler.py` 112–115 and 413–414, enabled per project in
  `handlers/project_action/handler.py` `_set_project_actions_enabled`). Plugin actions have no enable state per project,
  so moving them needs a rule for the "no project open" case first. Owner decision: show the message, or disable.
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
- **`review_enabled`, `review_model` and `max_reference_languages` have no settings-dialog control** (translation
  config keys). The review pass is on by default; a checkbox in the AI Translation settings tab would let it be
  switched off without editing the config.
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
  script at `E:\Emulators\RomHacking\Zelda\Twilight Princess\GC + Wii\zelda_tp_script.txt` and queries MemPalace (the file takes
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

- **Relocated text is unverified in a running game**: a save whose text outgrows its 0x6A000-byte range moves
  `message_data_static` to free address space and rewrites the four `lui`/`addiu` pairs in `z_message.c`
  (checked statically only). Test ROMs: `MM64_UA\rom\test_edit_blue_rupee.z64`, `test_text_grown_40pct.z64`.
- **Characters per text box**: `Font.charBuf` holds 120 glyphs per box (`include/z64font.h`); longer Ukrainian
  boxes may run out. Not checked by the plugin yet.
- **Credits** (`staff_message_data_static`), the code's own strings and PRESS START open since 2026-10-07. The credits draw with their own width table (`sCreditsFontWidths` in `code`), which the Font Editor does not edit. PRESS START can use only the ordered font's cells (digits, Latin, a few accented cells: no Cyrillic slot of `translation_map.json` except the look-alikes).
- **Exports carry the messages and the message font only**: the 2Ship `.o2r` and the Recomp source leave out credits, interface strings, PRESS START and textures.
- **Exports**: a 2Ship2Harkinian `.o2r` (TextMM file) and a Zelda64Recomp `.nrm` (EZ Text Replacer code)
  from the same project; the Ukrainian MM3D table (`translation_majora.csv`) as a seed for the N64 ids.
- **Width of runtime values** (`{rupees-total}`, timers) counts as zero.

## Ocarina of Time N64 plugin (`plugins/zelda_oot64`)

- Same open items as Majora's Mask (exports, characters per box); the credits and the title screen strings
  open since 2026-10-07. The title / file-select font has no Ukrainian letters (free kana cells could take them),
  and the SoH export carries only the messages and the message font (not credits, title strings, textures).
  Relocated text
  rewrites the single `lui`/`addiu` pair that loads the English text on NTSC; untested in a running game
  (`OOT64_UA\rom\test_edit_green_rupee.z64`, `test_text_grown_40pct.z64`).
- Only NTSC-U 1.0 is supported; Europe 1.0 (English/German/French) could serve as reference languages.

## Context mined from the N64 decompilations (`plugins/common/zelda64_context.py`)

- Speaker names are decomp descriptions ("Clock Town - Gate-Blocking Soldier", OoT actor names like `En_Go2`
  where no description exists); a curated name table would read better. Cutscene-only lines, ids computed at
  run time and Bombers' Notebook entries without a placed actor get no speaker. Report:
  `E:\Emulators\RomHacking\Zelda\Majoras Mask\N64\reports\context_report.md`.

## The Wind Waker HD plugin (`plugins/zelda_ww`, Wii U)

- **Textures**: the Textures window lists ~100 BFLIM images (title logo, boot screen, button and controller
  screens, map / quadrant titles, the sea-chart label). All 1 683 BFLIM of the pack and `Common/Layout` read and
  write back byte for byte, but the other ~1 580 (art, Hylian-only frames) are not listed.
  `Common/Object/Tlogo.szs` (BFRES FTEX: PRESS START, © 2002, ZELDA) has no backend; it is probably the unused
  GameCube 3D title (the HD title is `Layout/Title_00.szs`, proved in Cemu).
- **Box widths by BalloonType** come from two layouts (700 px / 650 px panes) and the English 99th percentile; which
  layout each balloon type uses was not traced in `cking.rpx`.
- **Ukrainian letters in CKingMain / CKingMainL** are rough Rubik Black shapes on a new sheet each (+512 KB of
  texture per font in memory); they showed in Cemu on the title screen, but were not checked in every menu or on a
  console.
- **The entered player name** is typed on a Latin keyboard; `[Name]` shows it undeclined. The Russian translation
  replaced `[Name]` with a fixed «Линк».
- **French/Spanish references come from the user's Cemu `.wua`**, not from the disc: the `.wua`'s English pack has
  the original MD5, so its packs are taken as clean, but the WUX (`WWHD_UA\iso`) stays undecrypted (no keys here).
- **Cemu 2.6 here crashes at boot** (0xc0000409 after "can't initialize tv audio") with Audio API XAudio 2.7, which is
  not installed; Cubeb works. `3_run.bat` leaves Cemu's settings as they are, so the user switches the audio API once.
- **Wizard (2026-10-17)**: a Wind Waker HD project starts from the game folder or from `permanent_2d_UsEnglish.pack`
  (`plugins/zelda_ww/message_pack.py`): `Message/`, `Font/`, `Pack/`, `Layout/`. On the owner's pack: 68 MSBT and 6 BFFNT.
  A `.wua` (Cemu ZArchive, zstd) or `.wux` (Wii U keys) is not read: a ZArchive reader is not in the repo, and the
  `.wux` needs the Wii U key store entry. The wizard refuses them with the pack's error text.
- **Build (2026-10-17)**: the `cemu` target (`plugins/zelda_ww/graphic_pack.py`) repacks each changed message and font into
  the pack and writes `graphicPacks\Picoripi_UA_WWHD\`. The owner's pack with no edits round-trips: 221 members, same
  names and order, same inner data. Not done: the `sdcafiine` and SwitchWakerHD mirrors of the workspace script, and the
  real-game check of an edited pack in Cemu.
- **`glossary.md` (`plugins/zelda_ww/translation_prompts/glossary.md`)**: nothing reads it. Left in place in this
  pass: whether the prompt or the glossary seed should read it is the owner's decision.

## The Wind Waker GameCube plugin (`plugins/zelda_tww`)

- **Runtime suffixes are in the executable**, not in BMG: " Rupee(s)", " bomb(s)", " yard(s)", timers
  (`tag_*` in `f_op_msg_mng.cpp`). A Ukrainian build needs them patched in `main.dol`, or the text rewritten
  around a bare number.
- **No speakers yet**: NPCs pick message ids in code (`getMsg` / `next_msgStatus` per actor), cutscenes through
  `event_list.dat` `msgNo`. TP's flow-based attribution does not apply.
- **No window frames** in the preview (`hukidashi_*.blo` in `res/Msg/msgres.arc`) and no `message_window_preview`.
- **Two copies of the name-entry font**: `nameres.arc` (name entry) and `Stage/Name/Stage.arc` →
  `file_select.arc` (the two player-name panes of the file-select screen keep it; the other 13 panes are switched
  to the message font). The Font Editor lists both; Ukrainian letters drawn in one must be drawn in the other.
- **Tingle Tuner sprites have little room**: the OBJ tile block packs back into 7,468 of its 7,596 bytes, so
  only small redraws fit (a bigger one is refused). More room needs the OBJ palette after it moved.
- **The Tingle Tuner client was checked alone in mGBA** (no-link screen: text, font and sprite edits); inside the
  game with Dolphin's GBA only the text and font were shown (2026-10-04).
- **A session with unsaved edits keeps its old block list** when the folder sync adds project files
  (`SessionMixin._session_misses_project_blocks` falls back to a full load only without unsaved edits).
- **Removed project blocks stay in virtual folders**: `Project.remove_block` (used by the folder sync) leaves the
  block id in its folder, so empty folders remain in the block tree (the WW project was cleaned by hand).
- **Build (2026-10-17)**: `plugins/zelda_tww/disc.py` writes the disc from the unpacked tree (no original image). On the
  owner's data: 2,210 of 2,213 FST files equal the original; the 3 others are the translated files; `main.dol` and the
  apploader are byte-equal; 5.1 s. The `bluewake` target keeps the original `main.dol` (BlueWake checks its SHA-1).
  Boot checked 2026-10-18 in a private muted Dolphin copy (`D:\RomHacking_tmp\zelda-ww-ready\dolphin`, portable, no audio):
  the original and the rebuilt image both boot to the game's own screens; the boot DVD reads are identical (15 lines
  each, no read error). A test copy with two shortened lines of `zel_00.bmg` (units 19 and 24, the save prompts) shows
  its text in game. The rebuilt disc needed no layout change. The card prompt differs between runs even for the
  original image (a card-check timing effect, not the disc).
  Not done: BlueWake texture packs (`Load\Textures\GZLE01`), and the `main.dol` text suffixes.
- **BlueWake (checked 2026-10-18, BlueWake 0.7.0 copied to a scratch folder)**: the built `GZLE01.iso` is accepted: BlueWake
  prepares it (main.dol SHA-1 revision 0, 415 RELs) and runs the game loop for 120 s with no crash; the picture was not
  judged. Refused, each with its own message: a header-only 0x440-byte file (the SHA-1 message: the file has no
  executable), a GZLP01 id, a non-GameCube file. BlueWake does not check the image size. The build refuses a source
  `main.dol` that is not revision 0 (`plugins/zelda_tww/rules.py`).
- **Project Manager walk (2026-10-18, scratch copies, `pm\gc` and `pm\hd`)**: the wizard creates and unpacks both
  projects; the open call takes 0.15 s (GC) and 0.12 s (HD); the longest UI-thread gap during the open is 16 ms (GC)
  and 44 ms (HD); the scan that follows takes about 3 s. Builds: GC ISO 1.15 s, GC BlueWake 1.14 s, HD Cemu pack 11.7 s.
  Not walked: the editor's save, the preview.
- **Outside the plugins, not fixed**: (a) `core/project_library/plugin_facts.py` `count_project` skips archive members (its
  own ponytail note). On the GC project the card shows 5 lines and 0 translated; the message archives hold the game's
  text. (b) `handlers/issue_scan_handler.py` `_scan_next_batch` raises `RuntimeError: QTreeWidgetItem has been deleted`
  when a project is opened again while its background scan runs (seen once in the HD walk, which opened it twice).

## Zelda: Tears of the Kingdom plugin (`plugins/zelda_totk`)

Checked on the real 1.4.0 romfs 2026-10-04 (every MSBT round-trips, an edited title menu shown in Eden).
- **Speakers ~69%** of the event lines (22,926 of 33,263): the rest are lines no flow gives one character
  (system flows started by an unknown `Npc_EventStarter`, shared lines). About 1,570 lines keep an actor id as speaker
  (`Npc_UMiiVillage031`, `Npc_ZoraFencer` = Yona, whose name is a `{yonaName}` tag). No addressee yet.
- **Width limits are measured from the English text**, not from the window layout (talk lines reach 993 px,
  cutscene lines 1279 px at Rodin B 45 px); icons count 45 px. A layout-based limit needs the `UI/LayoutArchive`
  BFLYT text panes.
- **Tag `{tag:1:2}`** (no arguments; at the start of shop prompts and the end of shouted lines) has no name.
- **Reference languages load on the UI thread** (the host's reference loading is synchronous): about 0.6 s per
  language, ~8 s for TotK's 14. Done for plugins that give `reference_worker_rules` (Twilight Princess, 2026-10-17):
  the parse runs on a worker. Other plugins still load synchronously.
- **Added glyphs are unproven in game:** the title menu shown in Eden uses Rodin, which already had Ukrainian;
  the glyphs drawn into RaglanPunch, NTLG-DB and ZeldaGlyphs (titles, small text, location banners) still need a
  screen that uses those fonts, and a hand touch-up.
- **RESTBL** follows the game's own rule (measured on every text and font archive); a translation far longer than
  English has not been played.

## Lunar 2: Eternal Blue Complete plugin (`plugins/lunar_ebc`)

- The font has 94 glyphs and no Ukrainian letters; codes 0x60-0x7F have no glyph yet (the font section can grow).
- Room limits are estimates from the program's buffers: event script + data 0x34000, people file 0x45000,
  system messages 0x80, menu file 2499 its own sectors. Not checked in the game.
- A grown file is written after the end of the disc; the 5,004 free sectors inside DATA.PAK are not reused.
- Not opened: text burned into the FMV movies (`*.STR`), icon glyphs drawn from units 0x3xxx/0x8xxx.
- In-game check of the text and font edits not done (two runs reached the title texture only).

## Found during the series glossary feature

- The series tab shows no occurrences (Count 0): its occurrence index is not built over the open project.
- Glossary builds do not consult the series glossary: a term the series already decided is seeded and
  translated again in the project (the series file itself is never written by a build).
- Series and project glossary files are read and written on the UI thread, as the project glossary is today.
- Two programs (or two projects open at once) editing the same series file: the last write wins.

## Unpack in Picoripi (phase 1, 2026-10-13)
- Phase 2: the console key file (D30 has the owner's rule). Wii, Wii U, 3DS and Switch images need it. Wii discs need a partition reader too.
- Wii WIA and RVZ images, and NKit images of other kinds, are not read; the zt scripts still convert them with DolphinTool or wit. The wizard says so and asks for an ISO. GameCube WIA and RVZ are read natively since D33 (`core/containers/wia.py`). NKit GameCube discs are read as they are (D30 addendum).
- Phase 2a is wired (D30 addendum). Recorded differences, not fixed (the workspaces are not regenerated):
  - Curious Village (Layton DS): the unpack writes 65 more `.gds` scripts than the workspace has (465 text files against 400 blocks). The plugin gives rows for them, and the current zt agrees.
  - SoulSilver (Gen 4): `a/1/3/3` differs from the HeartGold-based workspace. The HeartGold output matches it.
  - Lost Future (Layton DS): two stale workspace files (`lt3/fnt/font_en1.cbin`, `font_en2.cbin`) are not produced; the current zt takes only `.cfnt`.
  - Gen 4 and Gen 5 workspaces keep the old layout (`files/msgdata/msg`, `res/text`, 623 to 828 files) that the current zt does not write.
- Twilight Princess GameCube: the project source is `files/res/Msgus` (10 archives, equal to the workspace, 10 blocks). The whole-disc block count from the earlier note (17) was not measured. PAL and JP discs are not recognised.
- Eternal Darkness: the unpack takes about 330 s on one thread (zt uses a 7-process pool). Only the USA disc (GEDE01) is recognised.
- Metroid Prime GameCube: no `identify_source`, so the wizard takes the role from the user. The PAL disc (GM8P01) is not supported.
- Metal Gear Twin Snakes: the Europe discs (GGSPA4) are not recognised.
- Eternal Darkness and Metroid Prime real-data results come from the helper's full runs; the Eternal Darkness full run was not repeated in phase 2a review.
- Phantom Hourglass workspace `source` is 4 files behind the current `zt/zelda_ds.py` (three `resChild2nd.bin` files for English, French and Spanish, and `Menu/UI_main/opening.bin`). Owner decides whether to rerun its `1_unpack`.
- Revenant Wings workspace project lists 55 blocks; the same source gives 59 with the current scan (four `.dpk` blocks). Owner decides whether to rebuild that project.

## Unpack in Picoripi (phase 2b, 2026-10-13, partial)
- BLOCKED: decryption of 3DS, Switch and Wii content. `pycryptodome==3.23.0` is pinned in `requirements-dev.txt` but not installed in the project venv: the install was denied by the auto-mode permission check, and the brief forbids a pure-Python AES. Every encrypted read raises `encrypted_error` (`core/containers/console_crypto.py`). Owner runs `install_picoripi_crypto.bat` (in the owner's `_shared\scripts` folder; it installs the pin into the project venv), then phase 2c fills the decrypt bodies at that seam: NCCH CTR and keyscrambler (3DS), NCA XTS and CTR with `prod.keys` (Switch), the common key CBC per sector (Wii).
- Owner step after 2c: `scripts\verify_unpack_keys.py` and its `.bat` (not written here; it has nothing to run until the decrypt bodies exist). It takes the key file path as an argument, unpacks the given images to `D:\RomHacking_tmp\unpack_check\`, and prints counts and hash equality per game only.
- Key file formats the store will hold, not read yet: 3DS `aes_keys.txt` (boot9 next to it is used by the workspace tool), Switch `prod.keys`, Wii `keys.bin` (0x400 bytes, common key at 0x158, as `tools/wii_nand` reads it).
- The pin is not in `requirements.txt`. When the decrypt bodies land, decide whether it joins the app's requirements.
- ExeFS `code.bin` is decoded from BLZ when the exheader says so (`nitro.blz_decompress`). Verified against the Update CIA. The base Majora's Mask 3D code differs from the workspace, because the workspace ExeFS is the Update build (D30 addendum). Copy of Princess (text in `code.bin`) is not wired yet.
- No plugin is wired for 3DS, Switch or Wii. Retail `.cia` files are encrypted, and the decrypted dumps are not a plugin input.
- Wii U: not done (no reader, no key).
- Superseded in phase 2c: the wizard asks for a key only when the plugin lists the console in `unpack_key_consoles()` and the file is encrypted (see "Unpack in Picoripi (phase 2c)" at the end of this file).
- 3DS seed crypto (games whose NCCH key comes from a seed: Layton's Mystery Journey (`zt/layton3ds.py`, `seed=True`), Dragon Quest VII/VIII, Corpse Party and others): not in the reader. It needs the seed database too. Professor Layton and the Miracle Mask is not seed crypto: the owner's run of 2026-10-14 decrypted its CIA with the normal keys.

## 3DS manual preview (`manual_3ds`, 2026-10-13)

- Done (phase 3): the page screenshots are drawn from their BCLIM textures (page archive, then `Common_texture.arc`); a texture that cannot be decoded stays a grey box.
- Done (phase 4): window panes (`wnd1`) with a visible fill are drawn as rounded boxes in the average of their four vertex colours (the orange item pills); the page `*_bg` windows are drawn under the page; the title bar shows the page number (file number + 1) in a blue badge and the translated Index entry `index/Index#<page>`; text on a dark fill is white. Checked on one console screenshot (Page 2, Small) only; the badge rule (file number + 1) is taken from that one page.
- Done (phase 5, checks): the check and the preview stop a line before a picture (`pic1`) or a box frame (`wnd1` at least 200 x 40 px) beside it, in the line's vertical band (`BESIDE`, "runs N px into the picture or frame"); the button glyphs of the Russian original must all come back (`ICON`). `geometry.json` holds each line's page position and the pictures and frames of each page; `scripts/build_manual_geometry.py <repo_manual>` rebuilds it from the owner's dumps (the existing fields match the committed file exactly). At owner `702272a` the gate listed two `camera` `PANES` problems; at `a19b98a` it lists none, and the plugin lists none (see the sync note below).
- Sync done (2026-10-14, owner tools at `a19b98a`, branch `feat/manual-3ds-sync`): the plugin follows the owner's current tools. Ported: `pas1` nesting (owner 44be121), the page-reference regex (`\bстр.`, `\bсм.`), the default glyph variant `real` (b31d701, a6a580d; `widths.json` now has the patched letters' donor widths and the `real` substitutions), the pictures and frames attached to every paragraph (a19b98a), and the check exit status. Result: the plugin's problems equal the owner's gate on all 16 dumped manuals (6,034 translated paragraphs); `camera` `PANES` is gone on both sides. The three home-menu screenshot cases are regression tests (`test_home_menu_line_keeps_off_the_picture_or_frame_beside_it`). The preview draws with the owner's live `layout_for`, and `test_the_preview_places_text_and_pictures_where_the_owners_parser_does` pins its pane positions to the owner's parser.
- How to resync: when the owner's tools change, run `python scripts/build_manual_geometry.py <repo_manual folder>` from the repo root. It writes `plugins/manual_3ds/geometry.json` (with `owner_commit`) and `widths.json`, read-only on the owner folder. Then run `pytest tests/test_plugins/test_manual_3ds` with `PICORIPI_ROMHACKING=<romhacking root>`. Until the rebuild, the real-data tests fail with one line: `owner tools at X, geometry built from Y`. Commit both JSON files with the port.
- Open, owner decision: the plugin's own `WORD` rule reports 5 paragraphs the pane model cannot fit (the owner's `OWNER_DECISION` list). The owner's gate does not count them as problems, so the parity test does not compare `WORD`. Keep it as a plugin problem, or drop it to match the gate exactly.
- Not drawn: the window frame textures (the rounded frame edges, the textured frames of the numbered titles), the neighbouring pages at the screen sides (grey strips), and the viewer's own tab text when the heading is not in the selected part (Large or Small). The console shows its title in Russian (the source of that text is not checked); the preview draws the translated Index text in a system font.
- Glyphs come from the system font `cbf_std`, drawn in the console ink (60, 60, 60); the anti-aliasing is the font's own, not the console's.
- Sub-pages K are stacked by their own area heights; checked on one console screenshot (Page 2, Small) only, with a 14 px vertical offset of the viewer's first row. Other pages are not compared.
- Scroll is by pixel steps with no momentum; the Y button is a click target only (no controller input in the panel).
- Untranslated paragraphs (empty `ua`) draw nothing in the preview.

## Unpack in Picoripi (phase 2c, 2026-10-14)
- Real-data results, the owner's run of 2026-10-14 (`verify_unpack_keys_all.bat`, one image per console, unpacked by this branch, compared with the workspace source by sha256):
  - 3DS, Miracle Mask CIA (`00040000000A8600_..._CTR_P_AKKP.cia`) against `Professor Layton\Miracle Mask`: 719 workspace files, 718 equal sha256, 0 missing. Decryption of RomFS and ExeFS is verified. The one difference is `exheader.bin`, 510 bytes: byte `0x0D` (`0x02` SDApplication; the CIA build has it, the cartridge build does not) and `0x400`-`0x5FF` (the RSA-2048 AccessDesc signature and the NCCH public key, which the CIA and cartridge builds sign differently). The workspace came from the decrypted Europe `.cci`, whose exheader equals the workspace copy. Bit `0x01` (CompressExefsCode) is set in both, and the workspace `code.bin` is decoded, as ours is. So our exheader keeps bit `0x01`; no reader change was needed.
  - Switch, Skyward Sword HD base NSP against `Zelda\Skyward Sword\HD - Switch` (`romfs` only): 162 workspace files in `exefs` and `romfs`, 161 equal sha256. The one difference is `romfs\EU\Object\nl_NL\5-CenterField.arc`: workspace 234554 bytes (dated 2026-10-04), ours 234522, which is the size in the RomFS table. The workspace file is most likely edited; not confirmed. The unpack has 720 files the workspace does not hold (the workspace is a subset).
  - Wii: not run; no `keys.bin` on this PC. Wii decryption is unverified on real data.
- Built, synthetic tests only before that run: decryption for 3DS (NCCH sections, CIA title key), Switch (NSP: NCA header, key area, CTR sections, ticket title key) and Wii (data partition, cluster IV). Run `E:\Emulators\RomHacking\_shared\scripts\verify_unpack_keys.bat` per image (`--image`, `--source` = the workspace `source` folder, and the key file argument of its console). It prints counts and equality only and unpacks into `D:\RomHacking_tmp\unpack_check\`.
- Still not verified on real data: the Wii data IV rule (the encrypted hash block at 0x3D0, as wiibrew and Dolphin describe it) and the whole Wii key path (`keys.bin`, the ticket title key, the cluster reads); the NCCH version 1 counter (3dbrew; no owner title checked); the NCCH 0x20 "new keyY generator" flag (the reader tries the signature KeyY and reports a wrong key if the tables do not parse); fixed-key and seed titles (refused). The Switch key-area and titlekek derivation (`switch_crypto.py`, from the spec, not from `nsz`, which is not on this PC) and the 3DS keyscrambler are now verified for the titles of the 2026-10-14 run only.
- Refused with a message: 3DS fixed-key titles (flag 0x01); Wii Korean and vWii common keys (key index 1 and 2); Switch XCI images; Switch NCA0 and NCA2 headers; Switch XTS sections; Switch compressed sections; Switch personalised tickets; several program NCAs in one package; any other 3DS or Switch crypto method.
- Partly read: a Switch update whose RomFS is a patch (BKTR). `SwitchImage.romfs_is_patch` is True and no RomFS entries are returned; the ExeFS is read. Sparse sections are read as plain: not checked (the sparse-info offset is not confirmed).
- Not read: the 3DS seed database (flag 0x20 titles that need it report a wrong key). Wii U is not read.
- Duplicate code: `core/containers/romfs.py` reads the 3DS RomFS only; `switch_images.py` has its own walker for the Switch RomFS (a 0x50-byte header, UTF-8 names). Merge the two when the next RomFS change lands.
- `core/containers/gcm.py` cannot run on a decrypted Wii partition view. `wii_disc.py` has its own copy of the FST walk with the `<< 2` shifts. A refactor of `gcm.py` that takes a reader and a shift would remove the copy.
- Stale (2026-10-17): plugins now unpack 3DS and Switch images (see phase 2c and phase 3). The 3DS zt scripts that run `ctr3ds.main(... "extract" ...)` (for example `zt/aot3ds.py`, `zt/layton3ds.py`, `zt/mii3ds.py`, `zt/pmd3ds.py`) also copy text or build a CXI, or need the seed database; each needs its own wiring and a check against its workspace. `zelda_mm3d` takes its files from texture and font JSON with globs and archive members; not wired. Candidates are listed in the ROADMAP A18 row.
- The wizard asks for a key only when the chosen plugin lists the console in `unpack_key_consoles()` (new hook, D30 addendum) and the file is encrypted. Stale (2026-10-17): 8 plugins list one (pokemon_bdsp, pokemon_gen6, pokemon_gen7, pokemon_md_3ds, pokemon_nx, pokemon_trinity, super_mario_galaxy, zelda_las); the 3DS, Switch and Wii readers are wired through them.
- `pycryptodome==3.23.0` is in `requirements.txt` (decided in D30 addendum 2c). When the package is missing, an encrypted image gives the pycryptodome message, not a crash.
- Wiki EN and UK pages for the key file and the Switch and Wii sentences in the wizard paragraph need a check after the merge; `docs/wiki/3_Plugin_Developer_Guide.md` names the new hook.
- Audit r17 (2026-10-14), fixed: a missing or unreadable 3DS key file or boot9 file no longer chains its OS error, so a logged traceback does not show the key folder (`core/containers/n3ds.py`, two tests in `tests/test_core/test_n3ds_decrypt.py`).
- Audit r17, fixed in audit r18: `tests/test_core/test_unreal_pak.py` no longer opens the real `prod.keys`. Its test that compared the Bravely Default II pak with the extracted files is removed, because the NSP needs the owner's keys. `tests/test_key_file_paths.py` now fails when a test names a real key file or key folder.
- Audit r18, open (owner's choice): the Bravely Default II pak check (NSP, owner's `prod.keys`, extracted English entries) has no test now. Re-add it as a script outside the suite, if wanted.
- Audit r17, reversed in audit r18: the wizard free-space check counts every `images.UNPACK_KINDS` image again, Switch and Wii included. The r17 split `images.SPACE_KINDS` is removed; test `test_switch_and_wii_images_count_toward_the_room_check`.
- Audit r17, open: a packed 3DS code section is decoded whole by the pure-Python BLZ loop (`core/containers/nitro.py`, up to 64 MB). Cancel is checked only between entries, so a cancel waits for that decode.
- Audit r17, partly done (phase 3): the GameCube reader, the shared image helpers and the identify layer use `tr()`. Still English: `core/containers/` `n3ds.py`, `nds.py`, `romfs.py`, `switch_*.py`, `wia.py`, `wii_disc.py`, `gcm_writer.py`, the `console_crypto.py` internal checks and the plugins' `unpack.py` files (about 200 sites). Route them when each reader is next changed.
- Super Mario Sunshine (2026-10-14): the project is registered from the complete RVZ, now at `GameCube\source\Super Mario Sunshine (USA).rvz` in the workspace (same SHA-256 as the older private copy, which is deleted). The project's translation folder is still empty.
- Super Mario Sunshine: Dolphin (private copy) showed a menu string, a subtitle line and the airport0 speech balloon in Latin, and the balloon again with Ukrainian through the code map (D35): every letter one cell, both lines whole, no crash. The cells still hold the Latin-1 letters until the translator draws Cyrillic. The Latin-1 line of airport0 #1 (Toadsworth) did not come up in the 200 s run.
- Super Mario Sunshine: the port overlay matches both ports' loader (`platform/dvd/dvd.cpp` `overlay_dir`, sms-port 9d86575 as pinned by sms-switch b16ef26): `mods/<name>/files`, a folder named after a disc archive replaces members inside it, member paths compared in lower case; on Switch the folder is `sdmc:/switch/sms`.
- Super Mario Sunshine: the executable's English text (11 strings, `dol_text.py`, D32) is editable; the two progressive-scan confirmations with escape codes are not in it yet. Dolphin check of the executable text is still open.
- Super Mario Sunshine: the four `dolpic1.bmg` (Shift-JIS Japanese) save only when every message is replaced (a Japanese character has no code); whether the NA game shows them is unchecked.
- Super Mario Sunshine: the system font and the subtitle font open in the Font Editor (`font_sources.json`); no Cyrillic glyphs are drawn (the translator's job). The two `test_fontex.bfn` (title and common archives) are Shift-JIS fonts (type 2) without the code map's cells and are not listed: which text they draw is not known. No width map (`font_map`) is declared yet, so the width check does not use the game font.
- Super Mario Sunshine: escape tags and the attribute tables are still the Twilight Princess ones; the SMS tag catalogue is not written.
- Super Mario Sunshine reference languages (2026-10-15, D37): the European disc gives English (EU), French, German, Spanish and Italian for 186 of 191 US message files (3193 of 3481 messages, every language). No reference: the four Japanese `dolpic1.bmg`, `title.szs/marisun_stage.bmg` (same file on both discs) and `main_strings.dolstr`. Open: the European English of a few slots says something else (`sys_message` #19 and #21, `pinnaParco5` and `test11/pinnaparco_5` #12, `ricco7` and `test11/ricco_7` #21; `loadmessage` #6 and #22-25 by the text pairing); a reworded slot or a moved message is not told apart.
- Super Mario Sunshine reference, open: the owner's project folder holds `reference_eu`, but `project_settings.json` was not written (the agent's write was blocked); the owner runs the agent's `sms_set_eu_reference.bat` or picks the folder in Settings. A reference path that is still the disc image (Picoripi closed during the unpack) loads nothing at the next open; pick the disc again.

## Final Fantasy Tactics Advance (GBA) plugin (`plugins/ffta_gba`, 2026-10-15)

- Not opened yet: the name-entry keyboard grid (u16 LE codes from about 0xA33F00) and a few text runs outside the known
  tables (0x4B9011, 0x4B658E, 0x4C3006, debug strings near 0x391000 and 0x3C4000).
- The title menu words (New Game, Saved Game, Color Mode) and the intro captions are pictures; texture support is not
  done.
- Single-byte strings of the offset tables are not shown: 5,478 strings, all placeholder codes (5,474 `8D 8A FF` /
  `8A FF` and four short kana strings); the build keeps their bytes.
- The text buffer size is not read from the code (`rom_text.TEXT_LIMIT` = the longest string of the game).
- FFTARecomp: upstream runs a translated ROM "Unpatched" (whole-ROM hash: no widescreen patches). A one-line fork
  (`ffta_rom::eligible` = `verify_hooks`) shows it in 16:9 with the patches on (checked headless, 2026-10-15); the fork
  is local and unpublished, and its installer still checks `KNOWN_SHA1`.

## Skies of Arcadia (GameCube Legends, Dreamcast): script writer (2026-10-17)

- Open: the `*.sct` writer. Text pages sit inside the bytecode, so a longer page moves the bytecode after it.
  The 32-bit words of the script do not point at page starts (4 matches, about 5 by chance on `field/me002a.sct`),
  so relocation needs the bytecode decoder first. The same layout holds on Dreamcast (little endian).
- Open: the GD-ROM image kind is not wired into the Project Manager wizard (`core/containers/gdrom.py` only).
- Open: the other text groups of the GameCube disc (battle, bchara, beff, title, ending) and the AFNT font are not read.
- Skies script analysis (2026-10-17, field/me002a): the Dreamcast and GameCube code streams hold the same 32-bit
  words (GameCube read big endian, Dreamcast little endian). Every `\h(` page starts 4-byte aligned, follows a 0x1d
  byte, and ends with `\c` or `\e` followed by zero bytes. Word 0x0b is followed by 0x98b0 (goto-subscript
  candidate, not yet proven). Instruction boundaries and operand sizes are not yet proven; no re-assembler exists.
- Skies writer proof (2026-10-17, GameCube USA, Dolphin private muted, pad timers): an image with the first 15,000
  marked pages (229 files) boots and reaches dialogue, but no marker line was seen in the sampled dialogue frames.
  Reason: 10,268 of about 25,000 pages have a label inside their text, so the writer refuses them. A label inside a
  text is a second kind of text reference that the writer does not map yet.
- Skies writer blocker: `field/me201a.sct` freezes the game (black screen) once any page grows, while same-length
  edits and growth that keeps every code offset run fine. Literal-only AKLZ and turning off the word relocation did
  not fix it. The cause is a relocation the writer misses in that file (a relative reference or a non-aligned word).
- Skies writer, segments (2026-10-17): `text_segments` splits each page's text at labels inside it; `grow_regions`
  replaces byte regions (padded with spaces to a multiple of 4). All 25,312 pages of 229 files take a marker and pass
  the structural checks. Dolphin run (8 min, pad timers) reaches battles and cutscenes; no marker line was seen in the
  sampled frames yet.
- Skies `field/me201a.sct` (holds the early Aika and Valuan dialogue, excluded from the proof): growth freezes the
  game (black screen, static frames), even when only the last page grows. Control tests with the same file rewritten
  unchanged as literal-only AKLZ, and with 12 bytes appended at the end (decompressed size changed, nothing moved),
  run normally. Relocating only words, or only labels, also freezes. The missed reference is not found.
- Skies plugin (2026-10-17, GameCube USA): `plugins/skies_of_arcadia` identifies GEAE8P, unpacks the disc (field
  scripts decoded), builds a disc copy, and opens field scripts as editor strings (one per text segment). The text
  codec is exact on all 258 field scripts (36,008 segments). Bytes outside printable ASCII show as `{xx}` tokens; most
  are lead bytes 0x81 to 0x83 (punctuation). Their meaning is not mapped yet.
- Skies budget: `me201a.sct` is the only file in `FIXED_SIZE`. Its segments keep their length (in-place saves). Other
  scripts may grow. Growth is not proven in game for any script except the structural checks.
- Skies open: the in-game growth proof. A same-length marker on every script (228 files) ran 7 min in a private muted
  Dolphin. The game reached the title, a cabin and cutscenes. No marker showed in 61 sampled frames. Next: sample every
  frame during a dialogue (slower A presses) to find the first script on screen.
- Skies open: AFNT font `FontData.US` (77,856 bytes). Header: magic, 4 words (0x10 = header size), then 8-byte
  records `(u32 flag|size low16, u32 offset)`, blocks contiguous. Glyph format not decoded. Not opened.
- Skies open: textures `ts*.gvr`, `ea_mc_*.tpl`, `opening.bnr` are AKLZ-compressed on the disc. Not opened.
- Skies open: text groups battle, bchara, beff, title, ending hold no `\h(` pages that match the field format. Weak hits:
  two `battle/*.sml` files and two `field/*.mld` files. Not verified; not opened.

## Skies of Arcadia Dreamcast (USA, MK-51052): status 2026-10-17

- Done: plugin `plugins/skies_of_arcadia_dc` identifies the USA disc (IP.BIN area `U`), unpacks `FIELD/*.SCT`, opens them
  as editor text (LE codec), and builds a GD-ROM set through `core/containers/gdrom_writer.py`.
- Done: text is on the same pages as GameCube. 227 script names exist on both discs; 22,605 of 22,980 pages match the
  GameCube text exactly. The 406 USA scripts (both discs) round trip unchanged.
- Open: in-game proof. Flycast (private copy `D:\RomHacking_tmp\skies\flycast`) runs the marked disc: title, New Game
  (C key), narration and the opening cinematic were reached. No dialogue box was reached yet. The cinematic returns to
  the title; the first gameplay dialogue is not reached by script. Owner shortcut: `Dreamcast\play_to_first_dialogue.bat`.
- Open: growth. Only `FIELD/ME201A.SCT` is fixed (as on GameCube, not tested on Dreamcast). Other scripts may grow but
  no grown script was run in game.
- Open: other text groups (`BATTLE/*.SML`, `FIELD/*.MLD`, `1ST_READ.BIN` with 23 `\h(` pages) are not editor text yet.
- Open: Disc 2 (USA) is identified and extracts the same way; its build is not proven in game.
