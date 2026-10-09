---
status: current
updated: 2026-10-07
owns: unfinished work
tokens: 16.4k
purpose: Everything left open, one line each, by work package
---
# Open items

Every unchecked item that is not already a task in `docs/audit/2026-10-01/TASKS.md`. One line each; delete
the line when it is done or moved into a plan.

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
