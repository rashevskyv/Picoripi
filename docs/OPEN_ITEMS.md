---
status: current
updated: 2026-10-04
owns: unfinished work
tokens: 10.7k
purpose: Everything left open, one line each, by work package
---
# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

## Tingle Tuner (`plugins/zelda_tingle`, 2026-10-04)

- The GBA keeps 67,584 bytes for the unpacked USA text, only ~1,800 more than the English needs; a longer translation needs the client's buffers moved (the 0x02010800 literals in `client_u.bin`, see `WW_UA\reports\tingle_tuner_report.md`).
- Text drawn as graphics on the GBA is not translated: the help screen (tiles 0xA0-0xEF of the font block, editable as glyph cells in the Font Editor), "Call", "Please wait...", N/E/S/W on the main screen (OBJ/BG tiles).
- The Ukrainian glyphs in `WW_UA\translation\files\res\Gba\client_u.bin` are a rough render (Press Start 2P squeezed to 5 px); Б Ґ Ї Й і й need hand drawing.
- European clients (`client_0`..`4.bin`) have other addresses: no font source or program strings for them yet; their accent codes show as `{xNN}`.

## Textures window (`core/texture_formats`, 2026-10-04)

- Not encoded yet: ASTC (TotK logo colour/outline layers: 5 textures), BC6H. Textures inside models (TP title logo in `titlelogo_r.bmd`, WW subtitle in two BDLs, WW HD `Tlogo.bfres`), the Wii channel banner (`opening.bnr`: IMET > U8 > LZ77 > U8 > TPL, LZ77 not handled).
- No container yet: Koei RDB (Age of Calamity: 4 groups of BC3/BC1 sprites), TPHD TMPK/GTX (needs a decrypted dump), MGS `stage.dat` (zlib folders > tex13 packs > TPL: 449 textures; the TPL itself is handled — needs the stage.dat container or loose packs from the workspace unpack), 3DS BCH and SPBD particles (TFH boss cards). Drafts: `E:\Emulators\RomHacking\ZELDA\_textures\drafts`.
- 3DS games have no plugin: their textures open with File → Open (BFLIM, CTPK, CTXB; SARC/SZS, ZAR/GAR, LzS archives) and are edited in place; a plugin with `texture_sources.json` (drafts `zelda_albw`, `zelda_tfh`, `zelda_oot3d`, `zelda_mm3d`) would list them. OoT3D title logo letters are in a CMB model (not handled).
- Majora's Mask `yar` archives have no room to grow in the ROM: an edit that compresses worse than the original is fitted by recompressing every block of the archive optimally; if even that does not fit, the save is refused with the file's size.
- An archive around an edited texture is laid out anew by its container code (SARC, RARC); Revert restores the texture file byte for byte, not necessarily the archive.
- Helper to erase the English and render Ukrainian with the game font (later).

## Startup speed (2026-10-04)

Measured offscreen from process start to "open sequence complete"; Twilight Princess 5 s, Minish Cap 1.7 s,
The Wind Waker (GameCube) 1.2 s, Ocarina of Time / Majora's Mask 0.5 s.

- **Reference languages are parsed on the UI thread at every open** (Twilight Princess: 5 languages, ~3 s of
  the 5 s). Parse in a worker, or keep the parsed result on disk keyed by the archives' time and size and the
  alias table. The parser writes aliases into `mw.default_tag_mappings`, so a worker needs that split first.
- **The block tree is built on the UI thread** (`populate_blocks`, Twilight Princess ~1.3 s): the speaker pool
  walks every message flow (`build_speaker_pool` → `get_speaker_for_string`).
- **The issue scan runs one whole block per UI-thread step** (`issue_scan_handler._scan_next_batch`): a game
  whose text is one block (N64: 4589 strings) freezes the window for ~2 s at the first open.
- **An enabled spellchecker parses its dictionary in a Python thread** (pure-Python `spylls`, 2–3 s of CPU
  that the UI thread shares). Keep the parsed dictionary on disk, or parse in a process.
- **A project without its own MemPalace database gets one in the working directory**
  (`mempalace_local.db` next to where the application was started), not in the project folder.
- **`SettingsManager.load_unsaved_session` uses `eval` on keys read from `settings.json`**
  (`core/settings_manager.py`); `ast.literal_eval` is enough.

## Twilight Princess Wii / HD (2026-10-04)

- **No clean English TP HD dump on this PC.** `TPHD_UA\source` is a stand-in: the UK English archives of the
  Kruptar project (compressed again) with the Russian patch's fonts and size tables, matching the installed
  Russian build Cemu runs. A decrypted USA/EUR folder (`tphd_game` in `_tools\zelda_env.ini`) gives the real
  `Msgus`/`Msguk`, `Fontus`/`Fonteu` and size tables.
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

## Metal Gear Solid: The Twin Snakes (2026-10-04)

- Which strings of a GCX table are English is detected (voice clips settle ~92 % of codec lines, the rest by
  stopwords and run lengths): a few unvoiced menu/briefing strings may be misfiled; check `stage/n_title.gcx`
  and `stage/r_cmmn.gcx` in the editor.
- Text drawn into textures is not handled by the plugin: about 450 images (credits, titles, place-name cards,
  HUD plates, menus, results), listed in `TWIN_SNAKES\reports\visible_text_inventory.md` and the texture
  draft `ZELDA\_textures\drafts\mgs_ts.json`. The HUD words of `shared/mgso.rel` are a text block now, but
  the HUD atlas has only ASCII cells: Cyrillic there needs new atlas cells and a code change.
- Five speaker hashes are unnamed (`0x663ee3`, `0x28dce6`, `0x1932cc`, and two guessed in
  `plugins/mgs_ts/speakers.json`: `#9331f5` Snake, `#388785` Psycho Mantis).
- The clean ISOs are NKit (DolphinTool cannot undo NKit); patches made against them need the same NKit images.
- Seen in Dolphin 2026-10-04 (input movies, no keyboard): the options help, the first codec call after the
  intro, the codec opened in play (Start + A). Measured: codec rows wrap above 509 font units (509 fits, 514
  wraps), the options help row at the screen edge (711 fits, 725 wraps). The item-description, memory-card,
  briefing and photo windows were not measured: their limit is the widest English row of the neighbouring
  strings (`get_string_layout`), a guess from the English layout. Subtitles keep the block's widest row + 5 %.
- The codec box shows four rows; a fifth row (a long line the game wrapped) is not shown.

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
- TotK's fonts are scalable OpenType (`bfotf`): the editor shows them, outlines are edited outside (FontForge on
  the unscrambled OTF) or by `plugins/zelda_totk/font_glyphs.py`. Opening needs the TotK plugin's SARC container.
- BFFNT (Switch): new characters get a CMAP block and new sheets a texture layer (`min_sheets`); the kerning table
  (KRNG) is kept as it is, and a removed character outside the changed code range still resolves.
- HWDE: the `../romfs/...` candidate assumes the workspace layout `source/` next to `romfs/` and a translation
  folder named `romfs`.
- Opening a font and listing archive members still reads the archive on the UI thread (small files);
  the old BFN paths (`load_bfn`, saving a BFN) are synchronous as before.
- Next formats: Tingle Tuner (GBA), Wii U BFFNT (big endian, GX2 tiling). Cadence of Hyrule's BFFNT already
  opens; the 3DS fonts are done.

## Cadence of Hyrule plugin (`plugins/zelda_coh`, 2026-10-04)

- Owner decision: the Ukrainian glyphs of `LoveBug.bffnt` (the menu and text font, no Cyrillic; the second
  sheet is free for them) and the four missing letters Є є Ґ ґ of `ZeldaGlyph`/`ZeldaGlyphSmall` must be drawn
  in the Font Editor. Which screens use ZeldaGlyph and the Asian fonts in English mode was not mapped.
- Text in images is not covered: `textures_bin/texture_pack.bin` (zlib of BNTX textures) holds the title logo and
  the four menu tab names (`UI_BorderNames_English_*`); the Russian mod redrew exactly those five.
- Speakers come from string keys; 20 keys (`mellan`, `gerudo_leader`, `zora_leader`...) stay `npc:<key>` until
  someone names them. Dialogue box limits (lines per page, wrap width) are not known; only short labels get a
  width limit (1.3x / 1.6x the English).
- `credits.xml` (names and some English headings) is not opened; the translated credits headings live in
  `localization.xml` (ids 8000+).

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
- Not covered: text in textures (logos, UI art), the executable, movies.
- Watch: `tests/test_ui/test_font_editor_formats.py::test_font_jobs_run_in_a_worker_thread_one_after_another`
  crashed its xdist worker (access violation) every time it ran first in a worker while that module had a
  fourth test; the G1N editor test therefore lives in `test_font_editor_g1n.py`. Cause not found.

## Hyrule Warriors DE plugin (`plugins/zelda_hwde`, 2026-10-03)

- Owner decision: also write the translation into the English-EU section (default, `MIRROR_SECTIONS`)?
  Other languages stay as they are.
- Ran in Eden 2026-10-04 (text, redrawn `font_eu*.g1t` and the patched width tables show Ukrainian without
  overlaps); not on a Switch.
- Voice-line speakers for character ids 18-99 are `chara_NNN` (the names table disagrees there); event and
  movie scene ids are not tied to story chapters; text inside textures (`ui/caption`, `still_*`) and the
  executable is not covered.

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
  script at `e:\Emulators\RomHacking\ZELDA\TP_UA\zelda_tp_script.txt` and queries MemPalace (the file takes
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
- **Credits** (`staff_message_data_static`) are not in the project.
- **Exports**: a 2Ship2Harkinian `.o2r` (TextMM file) and a Zelda64Recomp `.nrm` (EZ Text Replacer code)
  from the same project; the Ukrainian MM3D table (`translation_majora.csv`) as a seed for the N64 ids.
- **Width of runtime values** (`{rupees-total}`, timers) counts as zero.

## Ocarina of Time N64 plugin (`plugins/zelda_oot64`)

- Same open items as Majora's Mask (exports, credits, characters per box). Relocated text
  rewrites the single `lui`/`addiu` pair that loads the English text on NTSC; untested in a running game
  (`OOT64_UA\rom\test_edit_green_rupee.z64`, `test_text_grown_40pct.z64`).
- Only NTSC-U 1.0 is supported; Europe 1.0 (English/German/French) could serve as reference languages.

## Context mined from the N64 decompilations (`plugins/common/zelda64_context.py`)

- Speaker names are decomp descriptions ("Clock Town - Gate-Blocking Soldier", OoT actor names like `En_Go2`
  where no description exists); a curated name table would read better. Cutscene-only lines, ids computed at
  run time and Bombers' Notebook entries without a placed actor get no speaker. Report:
  `E:\Emulators\RomHacking\ZELDA\MM64_UA\reports\context_report.md`.

## The Wind Waker HD plugin (`plugins/zelda_ww`, Wii U)

- **Text in textures** is not handled: the title logo, the sea-chart island names (`MapIsland_*`, the 116
  `MapScreen` messages are empty), quadrant titles and the boot screen (`Boot_00.szs`) are BFLIM images; there is
  no BFLIM backend. List: `E:\Emulators\RomHacking\ZELDA\WWHD_UA\reports\format_report.md`.
- **Box widths by BalloonType** come from two layouts (700 px / 650 px panes) and the English 99th percentile; which
  layout each balloon type uses was not traced in `cking.rpx`.
- **Ukrainian letters in CKingMain / CKingMainL** are rough Rubik Black shapes on a new sheet each (+512 KB of
  texture per font in memory); they showed in Cemu on the title screen, but were not checked in every menu or on a
  console. CKingPic (RGBA8 button pictures) opens for viewing only.
- **The entered player name** is typed on a Latin keyboard; `[Name]` shows it undeclined. The Russian translation
  replaced `[Name]` with a fixed «Линк».

## The Wind Waker GameCube plugin (`plugins/zelda_tww`)

- **Runtime suffixes are in the executable**, not in BMG: " Rupee(s)", " bomb(s)", " yard(s)", timers
  (`tag_*` in `f_op_msg_mng.cpp`). A Ukrainian build needs them patched in `main.dol`, or the text rewritten
  around a bare number.
- **No speakers yet**: NPCs pick message ids in code (`getMsg` / `next_msgStatus` per actor), cutscenes through
  `event_list.dat` `msgNo`. TP's flow-based attribution does not apply.
- **No window frames** in the preview (`hukidashi_*.blo` in `res/Msg/msgres.arc`) and no `message_window_preview`.
- **`bmgresh.arc/zel_01.bmg`** (15 Hylian-language messages, Shift-JIS) does not load: the BMG reader maps
  Shift-JIS to cp1252 for Twilight Princess.
- **Rebuilding the disc**: the images were extracted with DolphinTool (`files/` + `sys/`); `gcr` packs a
  `root/` tree, so the pack script in the user's workspace does not work yet.

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
  language, ~8 s for TotK's 14.
- **Added glyphs are unproven in game:** the title menu shown in Eden uses Rodin, which already had Ukrainian;
  the glyphs drawn into RaglanPunch, NTLG-DB and ZeldaGlyphs (titles, small text, location banners) still need a
  screen that uses those fonts, and a hand touch-up.
- **RESTBL** follows the game's own rule (measured on every text and font archive); a translation far longer than
  English has not been played.

## Found during the series glossary feature

- The series tab shows no occurrences (Count 0): its occurrence index is not built over the open project.
- Glossary builds do not consult the series glossary: a term the series already decided is seeded and
  translated again in the project (the series file itself is never written by a build).
- Series and project glossary files are read and written on the UI thread, as the project glossary is today.
- Two programs (or two projects open at once) editing the same series file: the last write wins.
