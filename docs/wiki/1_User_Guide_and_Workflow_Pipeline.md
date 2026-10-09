---
status: current
updated: 2026-10-07
owns: ui/, components/, dialogs/
tokens: 18.4k
purpose: Main window, menus, filters, settings tabs, shortcuts
---
# User Guide: Interface

**Language:** English · [Українська](uk/1_User_Guide_and_Workflow_Pipeline.md)

This page is the map of the main window as built in `ui/builders/menu_builder.py`, `toolbar_builder.py`, and `layout_builder.py`. Labels below match the English UI.

Recommended order of work: [8. Localization Pipeline](8_Localization_Pipeline.md). Virtual folders and the in-game preview: [6. Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md). AI buttons: [11. AI Translation](11_AI_Translation.md). Every feature in one list: [docs/FEATURES.md](../FEATURES.md).

---

## 1. Layout

```
+---------------------------------------------------------------------------------+
| File  Edit  View  Tools  Navigation  Bookmarks                         Help     |
+---------------------------------------------------------------------------------+
| Toolbar: Save  Undo Redo  Find  Preview  AI Chat  BFN  Rescan All  Settings  >_  F1 |
+---------------------------------------------------------------------------------+
| Blocks (tree)        | Strings in block (click a line to select)                |
| folders + files      | Hide empty / translated / unsaved / overrides / warnings |
| Speakers, Story, …   +----------------------------------------------------------+
| + − ✎ ↑ ↓ ⟳         | Original (read-only) | tools | Editable translation      |
| Glossary…            | Max-width, Hide tags |      | Window / Chapter / Speaker |
+---------------------------------------------------------------------------------+
```

| Region | What it is |
|--------|------------|
| Left | Project tree: physical files plus derived virtual roots. Header: **Blocks:** (double-click hint in tooltip). |
| Top right | **Strings in block (click line to select):** read-only list. Click a line to bind the editors. |
| Bottom left | **Original** — source text, read-only. |
| Bottom right | **Editable** — the only pane that writes translations. |
| Narrow column between Original and Editable | Revert string, Restore translation, Inspect story context, jump to Script Markup Studio. |
| Above Editable | **Window:**, **Chapter:**, **Speaker:**, then **AI Translate**, **AI Variation**, **Auto-fix**, **Font:**, **Max-width:**, **Apply**. |
| Under Editable | Visual preview (toggle with **View → Preview**). |

Do **not** type in Original. Do **not** treat the Strings list as an editor.

---

## 2. First launch

1. `File → New Project…` (`Ctrl+N`) or `Open Project…` (`Ctrl+O`).
2. New Project (**Create New Project**) asks for:
   - **Project Name**
   - **Project Location** (folder that will hold `project.uiproj`)
   - **Source Type:** **Folders** or **Files**
   - **Source:** original files (or an extracted ISO `root`)
   - **Translation:** writable copy
   - **Auto-create translation files**
   - **Game Plugin:** folder under `plugins/` that has `config.json`
   - **Description** (optional)
3. Plugins currently discovered that way (folder name → **display_name** in `config.json`):
   - `zelda_bmg` — Zelda: Twilight Princess BMG. GameCube, Wii and Wii U (HD) alike: **Source** is the folder with
     `bmgres*.arc` (`res/Msgus` on GameCube and in the Wii disc's DATA partition, `content/res/Msguk` or `Msgus` in
     HD); the three share message ids, so speakers, scenes and conversations work the same. HD text adds Wii U
     control icons (`{U:ZL}`, `{U:L stick}`, `{U:+}`…). Point **Fonts folder** at `res/Fontus` (HD: `res/Fonteu`).
     HD draws its letters from the textures in `*.pack.gz`, not from the BFN: the workspace build
     (`TPHD_UA\2_build.bat`) redraws them from the edited BFN sheets
   - `zelda_mc` — The Legend of Zelda: The Minish Cap
   - `zelda_ww` — Zelda: The Wind Waker HD (Wii U): the `Message/*.msbt` and `Font/*.bffnt` taken out of `content/Common/Pack/permanent_2d_UsEnglish.pack` (one block per MSBT). Tags come from the game's `CKing.msbp` (`[Red]…[/C]`, `[Name]`, `[Wait:10]`, `[A]`); speakers, box width (875 font units in a talk box, 812 in signs and item boxes, 4 lines a page), conversations and glossary terms come from each message's attributes. An unedited file saves byte for byte. Load Reference Patch with a folder of `permanent_2d_<Region><Language>.pack` files (the workspace's `reference\`: the game's French and Spanish packs and the Russian patch's pack named `permanent_2d_RuRussian.pack`) shows those languages, Russian first, matched by file and label. Font Editor: all six fonts (CKingMsg, CKingMain, CKingMainL, the RGBA8 button pictures CKingPic, CKingRuby, CKingZelda). Textures window: the BFLIM images of the title logo, boot screen, button and controller screens (`source\Layout\*.szs`, the game's `content/Common/Layout`) and the map titles and button pictures in the pack. Older projects of Kruptar `.txt` dumps still open
   - `paper_mario_cs` — Paper Mario: Color Splash (Wii U, Europe): **Source** is the workspace's `source\content` (`1_unpack.bat` decompresses the game's `.lz` files there), one block per `messages/EU_English/*.msbt` (48 files, 6,940 messages). Tags are named from the game's `gojika.msbp` (`{PageBreak}`, `{wait:30}`, `{select:0:1:0:300:yesno}`, `{ItemName:item}`). The Font Editor lists the five `fonts/*.bffnt`; the Textures window the English UI pictures `Graphics/UI/**/*.EUR_en.bfres` (title logo, battle words, chapter cards). `2_build.bat` compresses the changed files again and writes their sizes into `fs.table`
   - `zelda_sshd` — Zelda: Skyward Sword HD (Switch) and the Wii original (one plugin; the version is told by the source folder): the English `*.msbt` that `1_unpack.bat` takes out of the `.arc` archives (`US/Object/en_US/<area>/`, interface text `Layout/<name>/text/`), one block per file. Tags are named from the text (`{heroName}`, `{color:Red}`, `{item:11}`, `{icon:41}`, `{wait:15}`, `{choice1:65535}`); an unedited file saves byte for byte and `2_build.bat` packs the files back into the archives. Speakers (the HD's speaker byte, Fi's window, one-character files), conversations (the MSBF flows), line limits per window kind (the game breaks an over-long line mid-word, so keep within them; 4 lines a page) and glossary terms come from the game data. Load Reference Patch with the HD `romfs` folder shows the official Russian first and 12 more languages — also for a Wii project, matched by label. Wii: the HOME Menu messages (`HomeButton2/home.csv`, the English column) are a block too. Tools → Textures lists the English text textures (title and ending logos, opening captions, Game Over, The End; Wii: save banner, wrist-strap notice, HOME Menu labels, the disc channel banner `opening.bnr`) and the Font Editor every font (also the icon font, the HD options-menu fonts, the Wii HOME Menu and MotionPlus video fonts) once the workspace tool `tools\ss_extra_sources.py` (in the HD workspace) has put them into `source`
   - `zelda_mm64` — Zelda: Majora's Mask (N64): the US ROM itself (`.z64`, `.n64`, `.v64`) is the source file and the translated ROM the translation file. The ROM opens into four blocks: the 4,589 messages, the 45 credits messages (Ocarina of Time's codes), "Interface strings" the game's code prints itself (owl-warp places, "Rupee(s)", time speed, mask-code colours; each has a fixed room) and the title screen's "PRESS START" (two words of up to 5 cells of the title font: digits, Latin letters, a few accented cells); control codes as `{tags}` (zeldaret/mm); line width per textbox type, from the Font Editor's map of the game font once it is saved in the project, else from the game's own width table. Saving rebuilds the text files and the message tables from the source ROM, keeps the textures, glyphs and widths edited in the translated ROM (Tools → Textures, Font Editor) and fixes the header checksum. Speakers (one actor per line when the decompilation shows exactly one), scenes and seed glossary terms come from `context.json`, generated offline from zeldaret/mm and the ROM by `python -m plugins.common.zelda64_context`. Ukrainian letters are saved into the font slots of `translation_map.json` (the project's, else the plugin's): look-alike letters share the Latin glyph (А = A, і = i, Ї = Ï…), the rest take accented and unused punctuation slots chosen by width, so English stays readable; Ocarina of Time uses the same map. Load Reference Patch with the folder that holds `mm3d_seed.json` (Ukrainian carried over from Majora's Mask 3D, keyed by N64 message id) shows it as the "Ukrainian (MM3D)" reference
   - `zelda_mm3d` — Zelda: Majora's Mask 3D (3DS, Europe, with or without the v1040 update). **Source:** the workspace's `source` folder (`1_unpack.bat` copies `romfs\message\eu\eue.gmsg`, the font `ltn16.gzf` and the text textures there); **Translation:** `translation` (whole files at their romfs paths; `2_build.bat` makes the LayeredFS mod, which the base game and the update both read). All 6,152 messages of `eue.gmsg` (dialogue, items, signs, Bombers' Notebook, place names, credits, file select, fishing, Sheikah Stone, objectives), one block per id range; an unedited file stays byte for byte. Control codes are tags named as in the N64 plugin where the code is the same: `{color:red}`, `{box-break}` (followed by a line break), `{quicktext-on}`, `{name}`, `{btn:A}`, `{delay:10}`, `{flow:wait}`, `{event:1}`, `{choices:2}`, `{center}`, `{sfx:0x01006858}`, `{plural:0x0007}…{plural-else}…{plural-end}`. **Load Reference Patch** with the Russian build's `eue.gmsg` (or its folder) shows its Russian; the game's `romfs\message\eu` folder shows French, German, Spanish and Italian. The Font Editor opens `ltn16.gzf`; the Textures window lists 129 text textures: menus and HUD (`layout\EU_English\*.gar`), area, day and boss title cards, the title logo and copyright (textures inside a `.cmb` model and a `.cmab` animation), the save notice and the version labels
   - `zelda_oot64` — Zelda: Ocarina of Time (N64): the US 1.0 ROM, the same way as `zelda_mm64`: the ROM opens into three blocks — 2,115 messages, the 48 credits messages and the title screen's two strings ("PRESS START", "NO CONTROLLER": two words each, each word fits the cells the game draws, letters and digits of the title font only); codes from zeldaret/oot. The Font Editor lists the message font and the title and file-select font (the kanji glyphs the game picks by message 0xFFFC; it has no widths). Tools → Textures lists the 335 text textures (item, map and area names, pause and file-select labels, title cards); a text save keeps the textures and fonts edited in the translated ROM
   - `zelda_tww` — Zelda: The Wind Waker (GameCube BMG): `res/Msg/bmgres.arc` of the US or a European disc (`data0`–`data4` are English, German, French, Spanish, Italian). Shares the Twilight Princess machinery; tags, colours and line widths come from the zeldaret/tww decompilation, line width and lines per page follow each message's box type. With the disc's whole `source` folder the project also has the Hylian lines (`bmgresh.arc/zel_01.bmg`, Shift-JIS), the disc-error messages inside `sys/main.dol` and the disc banner (`opening.bnr`, Latin letters only); the Font Editor lists six fonts (message, Hylian, name entry and its copy in the file-select archive, the disc-error font in `main.dol`, the debug-menu font) and the Textures window 154 text textures (BTI, the title subtitle inside two BDL models, the banner). No speakers or window frames yet
   - `zelda_tingle` — Zelda: The Wind Waker, Tingle Tuner (the text a linked Game Boy Advance shows). **Source:** the disc's `files\res\Gba` folder (`msg_LZ.bin`, USA; `msg_LZ0`–`4` of a European disc: English, German, French, Spanish, Italian); **Translation:** the same folder under `translation`. One block of 1,086 messages with readable codes (`{color:2}`, `{wait:30}`, `{icon:1}`, `{choice2:0}`, `{anim:13}`…); the GBA draws every letter 6 px wide and breaks a line itself after 16 letters, 6 lines a page, so the width check is 96 px. Saving packs the file again (GBA LZ77) and refuses a text bigger than the GBA keeps room for (USA: 67,584 bytes unpacked, about 3 % more than the English); an unchanged file stays byte for byte. `client_u.bin` opens as a second block with the GBA program's own two lines ("Calling...", the no-link screen), changed in place. The Font Editor opens the GBA font inside `client_u.bin` (format `gba_tiles`): Ukrainian letters have their own codes (look-alikes share the Latin glyphs). The Textures window lists the client's sprites ("Please wait..."), screen tiles and help-screen text (format `gba`; an edit that no longer packs into the program's room is refused). Checked in Dolphin with its built-in GBA (`WW_UA\3_run_tingle.bat`)
   - `lunar_ssh` — Lunar: Silver Star Harmony (PSP, USA ULUS-10482). **Source:** the workspace's `source`
     folder, filled by `1_unpack.bat` from the UMD image: `ScriptPack\TEXT*.dat` (62 event scripts, unzipped
     from `ScriptPack.dat`: 11,837 messages and 164 choice lines), `TEXT_US\*.TXT` (8 UTF-16 tables: abilities,
     item names and descriptions, places, monsters, menus, credits; the string is the part before `;`, the
     comment stays) and `StationedPack\*` (interface pictures); **Translation:** `translation`. Tags are
     readable: `{speaker:41}`, `{wait}`, `{page}`, `{pause:30}`; a line break is a new line. A script string
     may grow; the labels of the script are counted again on save, and an unedited file stays byte for byte.
     The retail game draws text with the PSP's built-in font; the build gives it a font on the disc:
     `source\MODULE\font.pgf` (Font Editor format `pgf`: PPSSPP's open Liberation Sans Bold, Latin and
     Cyrillic) and the decrypted program (`source\SYSDIR\EBOOT.ELF`, dumped by PPSSPP during `1_unpack.bat`)
     patched to open it. Ukrainian letters are stored with their cp1251 codes (the script's U+0400–04FF range
     holds its control codes; `translation_map.json`), which the disc font maps to the Cyrillic glyphs; the
     editor shows the letters. The Textures window opens the title screen, menu and message-window pictures (`gim`: GIM in FCHN
     packs, 8-bit index and RGBA8888). `2_build.bat` zips changed files back into their packs and writes a
     copy of the image with them (`build\Lunar - Silver Star Harmony (UA).iso`); `3_run.bat` starts PPSSPP.
   - `metroid_prime4` — Metroid Prime 4: Beyond (Switch, update 1.1.0). **Source:** the workspace's `source`
     made by `1_unpack.bat` from the game's Retro packages (`text\*.msbt`: the English USEN messages of every
     MSBT table, 98 tables, 5,792 messages; `font\FONT_*.rfont`; `texture\<package>\*.txtr`, decompressed);
     **Translation:** `translation`. Every table is a block; tags read `{icon:123}`, `{color:255:197:41:255}`,
     `{size:150}`, `{pageBreak}`, `{column}`; `{0}` placeholders are plain text. The Font Editor opens the three
     fonts (`retro_font`: distance-field atlases, one language set per page; glyphs are edited in place, none
     added). The Textures window opens the interface textures (`txtr`: R8, RGBA8, BC1–BC5, BC7 written in place;
     ASTC read, an edited ASTC texture is stored as RGBA8). `2_build.bat` puts changed text into USEN and EUEN of
     every package that holds the table (the update's `Patch\Z_198_NXPatch.pak.patch` wins in the game) and
     changed fonts and textures with their metadata into a LayeredFS mod. The workspace starts from BakAI's
     Ukrainian translation (text and fonts with Ukrainian letters).
   - `metroid_other_m` — Metroid: Other M (Wii, USA). **Source:** the workspace's `source` (`1_unpack.bat` puts
     there, at the disc paths, `message\message_all.dat`, the fonts `font\*.brfnt`, the Wii HOME Menu messages
     `hbm\HomeButton2\home*.csv` and every 2D layout as a folder `<number>\<layout>\timg\*.tpl`);
     **Translation:** `translation`. `message_all.dat` holds every message of the game in eight languages; the
     project shows the US English one in groups (menus, chapter summaries, system messages, area names, tutorials,
     item and personnel files, 1,393 voice and cutscene subtitles) and keeps the other seven on save. Control
     codes read `{FONT_SYSTEM}`, `{COLOR_GREEN}`, `{ICON_A}`, `{IMG_ADAM}`; a line break is `^` in the file. The
     Font Editor opens the four game fonts and the HOME Menu font; the Textures window lists every layout
     (each exists once per language: the second of eight copies is English). `2_build.bat` packs the changes
     back into the disc image.
   - `zelda_lttp` — Zelda: A Link to the Past (SNES) through its PC port snesrev/zelda3. **Source:** the workspace's `source` (`1_unpack.bat` runs the port's own `restool.py` on the USA ROM): `dialogue.txt` (397 messages, the port's `[Name]`, `[Waitkey]`, `[Color 02]` codes; a line break shows before `[2]`, `[3]` and `[Scroll]`, and a break typed without one gets the code of its line), `font.png` (the Ukrainian dialogue font, format `zelda3` in the Font Editor: the English glyphs plus empty cells 95–119 for б–я and 128–148 for Б–Я, 114 cells more free; look-alikes use the Latin glyphs) and `gfx\*.bin` (8 graphics sheets with text — menu labels, item names, GAME OVER, title logo — in Tools → Textures as `snes:2bpp`/`snes:3bpp`); **Translation:** the same files under `translation`. Speakers, conversations and source lines come from the port's C code (`context.json`). `2_build.bat` compiles the translation as the port language `uk` of `build\zelda3\zelda3_assets.dat` with the port's own compiler (English stays as it is; `zelda3.ini` gets `Language = uk`) and builds `zelda3.exe` with Visual Studio Build Tools and SDL2 (one 2-line change to a copy of `messaging.c`: glyphs 128–255 through the escape code 0x86). Seen in the game: an edited intro line, font cells and the title logo.
   - `super_metroid` — Super Metroid (SNES) through its PC port sm_rewrite. **Source:** the workspace's `source` (`1_unpack.bat` reads the USA ROM): `text.json` — every text the game draws from tilemaps in six blocks (message boxes, file select and game over, options, pause map area names, intro, credits; 180 strings). The game has capital letters only and one 8-pixel cell per letter: a string is as wide as its `width`; tiles that are not letters are tags (`[press1]`, `[#304B]`) and stay in place. Ukrainian look-alikes (А, В, Е, І …) use the Latin tile; the other Ukrainian letters have cells only in the message-box font. Fonts (Font Editor, `texture_grid` over the raw tile sheets) and 13 text sheets (Textures, `snes:2bpp`/`4bpp`) are in `source\gfx`. `2_build.bat` writes a translated ROM (`build\sm\sm.smc`) and builds `sm.exe`. Context: the source line and function of each item in the port's C code; the intro is Samus's narration.
   - `metroid_prime_remastered` — Metroid Prime Remastered (Switch, base game). The same formats and rules as
     `metroid_prime4`. **Source:** the workspace's `source` (`text\TEXT_*.msbt`: 27 tables, 3,132 messages,
     named as in Metroid Prime 1, e.g. `TEXT_ScansChozoRuins`; `font\FONT_*.rfont`: Geneva, Deface and the
     title-screen Deface; `texture\<package>\*.txtr`: 771 textures); **Translation:** `translation`. Extra tag
     `{image:TXTR_RStickIdle:1}` (a picture by texture name). `2_build.bat` writes USEN and EUEN and every
     package that holds a changed asset into a LayeredFS mod.
   - `zelda_totk` — Zelda: Tears of the Kingdom (Switch, checked on 1.4.0). **Source:** the game's dumped `romfs`
     with only the language you replace in `Mals` (`USen.Product.140.sarc.zs`), plus `Pack`; **Translation:** the
     mod's `romfs`, e.g. `atmosphere/contents/0100F2C0115B6000/romfs`. Every MSBT in the archive is a block (1,511
     files, 47,799 messages); saving writes the archive back, compressed with the game's own zstd dictionary; an
     unedited project writes nothing. Needs Python 3.14+ and `Pack/ZsDic.pack.zs` from the same romfs (or a copy
     in `~/.picoripi/plugins/zelda_totk`). Tags read `{color:2}`, `{icon:AButton0}`, `{pause:30}`,
     `{textSpeed:0.5}`, `{autoAdvance:90}`; a tag it does not know reads `{tag:group:type:hex}`. **Speaker** comes
     from the game's event flows (about 69% of the event lines; English names from the game's character list);
     the AI context names the message file, label, event flow and speaker. Line width: the dialogue font (Rodin B
     at 45 px, `fonts/RodinNTLG-B_45.json`) with a 1000 px talk window and 1290 px for cutscene subtitles
     (`Dm*` files), 3 lines per page. **Load Reference Patch** with the romfs (or its `Mals` folder) shows the
     game's other languages as references, Russian first. The fonts (`Font/*.bfarc.zs`) are scalable OpenType
     fonts: in the Font Editor a changed width becomes the glyph's advance and a redrawn cell replaces the glyph's
     outline with its pixels traced as squares (a blocky draft or a test mark; polish real letters in a font editor);
     `python -m plugins.zelda_totk.font_glyphs <archive> <output>` adds І і Ї ї Є є Ґ ґ to the fonts that lack them
     (drawn from the font's own I i Ï ï, mirrored Э э and Г г with an upturn). The workspace's `2_build.bat`
     raises the resource size table for a grown text or font archive (`python -m plugins.zelda_totk.restbl
     <game romfs> <mod romfs>` does the same: the game's own rule, size rounded to 32 bytes plus 0x180 for text,
     0x100 for fonts).
   - `zelda_hwde` — Zelda: Hyrule Warriors Definitive Edition
   - `zelda_coh` — Zelda: Cadence of Hyrule (Switch). **Source:** a folder with the game's `localization.xml`
     (base + update romfs) and `fonts_bin`; **Translation:** the mod's `romfs`
     (`atmosphere/contents/01000B900D8B0000/romfs`, the base game's Title ID). All 1,809 strings, one block per id
     range (menus, dialogue, tutorials, items, enemies, places, cutscenes, credits, achievements); only the English
     strings are shown and saved, an unedited file stays byte for byte. Tags are the game's own (`[c:b]`, `[/c]`,
     `[i:button_a]`, `[s:9]`); `[n]` shows as a line break, `[p]` (next page) as `[p]` plus a line break. Speakers
     come from the string keys (`zora4_1` → Zora). The Font Editor opens the six `.bffnt` fonts; the text font
     `LoveBug` has no Cyrillic, so it opens with a spare sheet for the Ukrainian letters. `credits.xml` (the credits
     roll: headings, companies and names, the same in every language) opens as one more block, "Credits roll".
     Tools → Textures lists the five text pictures of `textures_bin/texture_pack.bin` (the title logo and the four
     pause-menu tab names; BNTX RGBA8 inside one zlib stream, written back into the pack)
   - `zelda_fsae` — Zelda: Four Swords Anniversary Edition (DSiWare, Europe). **Source:** the workspace's `source`
     folder (`1_unpack.bat` takes it from the clean European dump: `eu.kmsg`, `font_ltn.nftr`, the manual
     `manpages_narc_eu.blz` and the graphics); **Translation:** `translation` (whole files; the workspace's
     `2_build.bat` rebuilds the DSi SRL and a CIA). The manual opens one block per page (`Manual: page_01_00`…;
     a line break is the page's own line break, `[pic:N]` a picture, `[color:N]` a colour; the manual is drawn
     with the console's font). All 220 messages, one block per id range (prologue,
     Chambers of Insight, items, Great Fairies, Vaati and the ending, in-game messages, system, credits); only the
     English (EU) slot is shown and saved, an unedited file stays byte for byte. The game's control codes are tags:
     `[speaker:1]`, `[wait:120]`, `[next:90]`, `[close]`, `[choice]`, `[center]`, `[icon:N]`, `[button:N]`, `[num:N]`,
     `[space:N]`, `[color:N]`; a line break is a real line break (the game does not wrap). Speakers come from
     `[speaker:N]` (Zelda, Vaati) and the Great Fairy messages; widths from the font (225 px in dialogue, 168 px in
     in-game messages, 240 px in menus). **Load Reference Patch** with the Russian build's `nitrofs` folder shows
     its Russian and the game's other languages. The Font Editor opens `font_ltn.nftr` with spare cells: a letter
     typed into one becomes a new character. The Textures window lists the menus and buttons
     (`subtask_eu_en.cmp`), the stage-select plates, GAME OVER letters, copyright line (`zeldat_eu_en.bin`) and
     the title logo (`zeldat.bin`) in the game's colours; an imported colour that is not in the picture's
     palette becomes the nearest one. The block `game_over` (`main.arm9`) holds the GAME OVER word, one line per
     letter (`<character> <first tile> <W>x<H>`, tiles of the GAME OVER letters picture) and the x of each
     letter; the letters picture also shows as 16 slots of 16x32 for narrow letters
   - `zelda_albw` — Zelda: A Link Between Worlds (3DS, Europe). **Source:** the workspace's `source` folder;
     **Translation:** `translation`. `1_unpack.bat` writes each Yaz0 SARC archive as a folder of its members
     (`romfs\EU_English\FieldLight.szs\EU_English\Field.msbt`), the path a translated member is saved to;
     `2_build.bat` repacks the archives into the LayeredFS mod. All 190 English MSBT files (4,956 messages:
     dialogue, items, places, characters, menus, HUD, credits), one block per file. A file that several archives hold
     with the same bytes (`Field.msbt` is in 7) appears once and the build writes it into each of them. Tags are named
     by the game's own message project `CTRJack.msbp`: `{PlayerName}`, `{Color:Name}…{Color:Reset}`, `{Wait:30}`,
     `{ChoiceN:2}`, `{IntNumberN:2:0:-1:None}`, `{ItemName:hammer:Yes:No}`; an unedited file saves byte for byte.
     Menu and HUD texts (`Gm_*`, `Mn_*`, `Cm_*`, `Ed_*`) take the width and line count of their text box from the
     message project; dialogue keeps to 344 px, 3 lines a page. The Font Editor opens `MessageFont.bffnt` and
     `HyliaFont.bffnt`; the Textures window lists the 10 minigame and ending banners and the title logo
   - `zelda_tfh` — Zelda: Tri Force Heroes (3DS, Europe; the A Link Between Worlds plugin with this game's tags).
     **Source:** `source`; **Translation:** `translation`, archive members as folders the same way
     (`romfs\Archive\EU\EUen\LanguageGame.szs\EU\Message\EUen\NpcKing.msbt`). All 100 English MSBT files
     (3,382 messages: dialogue, signs, credits in `LanguageGame.szs`; menus, items, outfits, system in
     `RegionBoot.szs`), tags named by the game's `Alice.msbp` (`{CostumeName:EightBit:No}`, `{InsertMark:0}`,
     `{Size:90}`). Dialogue keeps to 344 px, 3 lines a page, `{Size:90}` text measured at 90 %; layout texts
     (`Layout*`), the opening story, credits, error and news screens have no width limit. The Font Editor opens
     `MessageFont.bffnt` and `HyliaFont.bffnt`; the Textures window lists 63 images with text: timers, chat stickers
     and billboards (CTPK), layout banners (BFLIM), the boss title cards in `Telop.ptcl` and the title logo in
     `PictureStory_EU.bch` (PICA textures at fixed offsets, format `raw`)
   - `zelda_oot3d` — Zelda: Ocarina of Time 3D (3DS, Europe). **Source:** the workspace's `source` folder
     (`1_unpack.bat` copies `romfs\message\eu\eu.qm`, the fonts, the name-entry keyboards
     `romfs\menu\ltn16_*.list`, the text textures and `exefs\code.bin` there); **Translation:** `translation`
     (whole files at their romfs paths; `2_build.bat` makes the LayeredFS mod). All 2,510 messages of `eu.qm`
     (dialogue, items, signs, Navi, menus, file select, credits, Sheikah Stone visions, area names), one block per
     id range; only the English slot is shown and saved, an unedited file stays byte for byte. The control codes
     are tags named as in the N64 plugin: `{color:red}`, `{box-break}` (followed by a line break), `{item-icon:45}`,
     `{button:A}`, `{name}`, `{two-choice}`, `{center}`, `{textid:0x0205}`, `{mq}…{mq-else}…{mq-end}` (normal and
     Master Quest text), `{plural:1}…{plural-else}…{plural-end}`. The four keyboard pages are one string each (keep
     the number of keys); the default player name `Link` (`code.bin`) holds at most 4 letters. **Load Reference
     Patch** with the Russian build's `eu.qm` (or its folder) shows its Russian and the game's German, French,
     Spanish and Italian. The Font Editor opens `ltn16.qbf` (dialogue) and `sys8.qbf`; the Textures window lists
     137 text textures: menus, title, Boss Challenge, logo, area and boss title cards inside the scene and actor
     `.zar` archives, and the SOLD OUT sign and title models (textures inside `.cmb` models)
   - `zelda_aoc` — Zelda: Hyrule Warriors Age of Calamity. Source is the workspace's `source` folder
     (`text\*.bin`, `battle\*.bin`: the game's text cut out of `data/LinkData2.bin`, one file per table
     with all its languages); the English table is shown and saved, and the workspace's `2_build.bat` packs
     the changed files into the LayeredFS mod. The Font Editor opens every game font (`font\latin.g1n`, 11
     sizes; the Japanese, Korean and both Chinese fonts); Tools → Textures lists the 33 pictures with English
     words (`texture\0x<id>.g1t`: logos, Victory/Defeat/Complete pop-ups, tutorial screenshots, language
     names). `2_build.bat` writes edited fonts and pictures into the mod as well.
   - `yokai_watch` — Yo-kai Watch (3DS, USA). **Source:** the workspace's `source` folder (every English text
     table `*_en.cfg.bin` at its path inside the game archive `yw1_a.fa`, the fonts `fnt\*.xf`, the English menu
     textures); **Translation:** `translation`. The game's codes show in curly brackets (`{PAGE}` — next page of
     the 2-line message window, `{PNAME01}` — the hero's name, `{CG}…{/C}` — colour); story files exist twice,
     `_m` (Nate) and `_f` (Katie). Japanese leftovers and passwords are not shown; an unedited file stays byte for
     byte. Speakers come from the game's speaker tables in the workspace's `meta` folder. The Font Editor opens
     `ft_nrm` and `ft_sml` (format `xf`, real Ukrainian letters); the Textures window lists 594 English textures
     (`imgc`). The workspace's `2_build.bat` rebuilds `yw1_a.fa` into the LayeredFS mod. Yo-kai Watch 3 (EUR, workspace
     `YOKAI_WATCH_3`) opens with the same plugin: its English text is in `data/txt/ev/en` and the archive
     `yw_lg_en.fa`; the hero of a line comes from its voice clip (`{PV#pv_c001000_23}`: Nate). Its Textures window lists all 5,817
     English textures (title logo, menus, telops, help, captions, signs; loading them takes several minutes).
     Yo-kai Watch 1 for Switch (Japanese game, workspace `YO_KAI_WATCH_SWITCH`) opens with the same plugin: the
     source text is the English fan mod written into the Japanese tables (`*_ja.cfg.bin`, 2,014 files, about
     48,000 lines, and the 13,800 lines the mod left Japanese, to translate from Japanese: each block that has
     them lists them under its category "Japanese source"; a Shift-JIS table that gets Ukrainian text is saved
     as UTF-8); the Font Editor opens
     `ft_nrm`, `ft_lrg`, `ft_sml` and `dbg` (Switch XF: A8 texture); the Textures window lists the menu,
     title, telop, help and caption images (IMGN, the Switch IMGC: RGBA8, RGBA4, LA8, A8, BC3).
     Yo-kai Watch 4++ and Yo-kai Academy Y for Switch (Japanese games, workspaces `YO_KAI_WATCH_4_SWITCH`,
     `YO_KAI_ACADEMY_Y_SWITCH`) open with the same plugin: the source text is each game's English fan mod in
     the Japanese tables `data/common/text/ja` (2,316 tables, about 38,500 lines; 1,672 tables, about 19,600
     lines — the lines the mods left Japanese, about 550 and 12,300, are shown too, under each block's category
     "Japanese source"); colour codes `[CR1]`…`[C]`
     and pictures `[$gaiji_…]` are tags; the Font Editor opens the G4 fonts (`font_ja`, `font_def`, Academy Y
     also `font_ja2` and a second style; each with its furigana font); the Textures window lists the menu,
     title, telop, help, caption and button pictures (G4TX: RGBA8, BC1, BC3, BC7).
   - `mgs_ts` — Metal Gear Solid: The Twin Snakes (GameCube, USA). **Source:** the workspace's `source\text`
     folder (`common\codec.dat` — every codec call; `stage\*.gcx` — menus, briefing files, item descriptions,
     memory-card messages, credits; `*\demo.subs`, `common\vox.subs`, `common\movie.subs` — subtitles of
     cutscenes, in-game voices and movies, taken out of the disc's stream files); **Translation:**
     `translation\text`. Every string is stored in six languages; only the English ones are shown (found by
     the voice clip a codec line plays, else by language detection), identical codec tables are one block and
     a save writes all their copies. Longer text takes the room of the French–Spanish strings the US game never
     shows; an unedited file stays byte for byte. Speakers come from the game data (codec `talk` commands and
     subtitle records name the character). The Font Editor opens the text font (`font\*.fnt`, format `mgs`);
     Ukrainian letters live in its upper half through the plugin's `translation_map.json`. The workspace's
     `2_build.bat` puts the pieces back into `stage.dat`, `demo.dat`, `vox.dat`, `movie.dat`, `codec.dat`.
     The game breaks a row that is too wide by itself, in the middle of a word, so the width check has no
     slack: a codec row may be 509 font units wide (measured in the game's codec box), a menu or item text row
     as wide as the widest English row of the neighbouring strings (one script mixes option help, item
     descriptions and memory-card dialogs, each in its own window). Credits, titles, HUD plates and menu words
     are pictures, not text (`TWIN_SNAKES\reports\visible_text_inventory.md`): **Tools → Textures…** lists
     them from `texture\<stage>.stage` (stages of `stage.dat` the workspace copies out; the texture packs read
     as TPL) and writes the translation copy; the build puts each changed pack into every stage of both discs
     that has it. `common\mgso.rel` (the game module) gives one block of HUD words — LIFE, O2, the item and
     weapon box labels, boss names: capital letters only, one byte each and never longer than the word's slot.
     Ukrainian letters shaped like Latin ones use those; the others use ASCII cells no HUD word uses, which the
     workspace redraws as Ukrainian letters in the HUD font (`tools\hud_font.py`). The Font Editor also opens
     the glyph grids the game draws HUD words, menu values, results and codec digits from (HUD font in three
     sizes, menu and results fonts, digit strips; format `texture_grid`, saved into their texture packs).
     `disc1\opening.bnr`, `disc2\opening.bnr` give the disc banner texts (the name in the GameCube menu and
     Dolphin: Latin letters only) and the banner picture in the Textures window.
   - `paper_mario_gc` — Paper Mario: The Thousand-Year Door (GameCube, USA). **Source:** the workspace's
     `source\files\msg\US` (one `.txt` per area, `global.txt` for menus, items, badges, battle text and
     tattles); **Translation:** `translation\files\msg\US`. Tags show in braces (`{k}`, `{p}`,
     `{wait 250}`, `{col c00000ff}`); `global.txt` opens as blocks by kind (item and badge names, enemy
     names, battle tattles, descriptions, menus); Japanese leftovers in the US files are left out and saved
     unchanged; an unedited file stays byte for byte. Speakers come from the game's event scripts (the NPC
     each `evt_msg_print` points at, plugin `context.json`), tattles are Goombella's; width limits per window
     kind are the widest English line of that kind in font units. The Font Editor opens the text font
     `f\papermarioset_US.bfn` (and the disc's other two, `_EU` and `_JPN`); Ukrainian letters use Latin-1 slots no English text draws
     (`translation_map.json`, `translation_map.md`). The Textures window lists the title, file-select,
     pause-menu, battle and sign textures with English text.
   - `paper_mario_nx` — Paper Mario: The Thousand-Year Door (Switch, 2024). **Source:** the workspace's `source`
     (`1_unpack.bat`: base + update): `msg\EU_English\*.msbt` (all text, 46 files, ~14,900 messages), the fonts
     `font\*.bffnt` / `*.bfotf` and the UI textures `ui\<folder>\*.bntx` (taken out of the game's `.bfres.zst`);
     **Translation:** `translation`. Tags are named from the game's `msg.msbp` (`{wait:250}`, `{key_wait}`,
     `{PageBreak}`, `{Color:255:255:255:204}`, `{center}`…`{/center}`); an unedited file stays byte for byte.
     The Font Editor opens the eight fonts (the outlined MARIO fonts are BC5: red is the fill, green the
     silhouette); the Textures window lists the title logos and every UI texture (BC1, BC3, BC4, BC5, BC7,
     ASTC 8x8). `2_build.bat` puts edited text into both English folders (EU and US) of the LayeredFS mod and
     compresses fonts and textures back.
   - `twewy` — The World Ends with You (Nintendo DS, Europe AWLP). **Source:** the workspace's `source` folder,
     filled by `1_unpack.bat` with every game file but the sound under its NitroFS path; the text is
     `Apl_Fuk/mestxt.mes` (the game's `mestxt.bin`: all 25,233 messages, 500 a block); **Translation:**
     `translation`. Codes are glyphs of the text font (ASCII, accented Latin and symbols show as characters,
     other glyphs as `[g:XXX]`); tags `[color:1]`…`[color:4]`, `[/color]`, `[num]`, `[value]`, `[name]`; an
     unedited file stays byte for byte. The Font Editor lists the four fonts of `Apl_Fuk/Grp_Font.bin` (format
     `twewy`: 10x10 text font, 10x12, two 16x16); the Textures window lists ~300 tile sheets of menus, titles,
     credits, location titles and copyright screens in the game's `pack` archives (sprites shown as a plain tile
     sheet). `2_build.bat` makes the message index `mestable.bin` again and rebuilds the ROM.
   - `policenauts` — Policenauts (PlayStation, Japanese discs SLPS-00215/00216 with the English fan patch, as the
     PSP PS1-Classic `EBOOT.PBP` files; disc 3 is not in the release). **Source:** the workspace's `source` folder
     (`1_unpack.bat` reads the PSISOIMG disc of each EBOOT): `PN_VOX1.PNV` / `PN_VOX2.PNV` (the dialogue of discs
     1 and 2: the subtitle text the patch keeps in each voice chunk, one group per chunk; lines of spaces are
     hidden), `FONT\*` and `SHOTPAC\KANJIFNT.*` (Font Editor, format `policenauts`), `PAK\*` (Textures: title,
     menu, act cards, story pages, staff roll; formats `policenauts_pak` and `tim`). Tags: `{dash}`, `{xHH}`.
     A chunk's text must fit its header sector; `2_build.bat` writes `build\CD1\EBOOT.PBP` and
     `build\CD2\EBOOT.PBP` (only the changed 16-sector blocks are compressed again).
   - `super_paper_mario` — Super Paper Mario (Wii, PAL, English UK). **Source:** the workspace's `source`
     (`1_unpack.bat` puts there the text `msg\UK\*.txt`, the fonts, the text textures and the Wii HOME Menu
     messages `hbm\HomeButton2_en.bin\home.csv`; an archive is a folder named like the archive file);
     **Translation:** `translation`. The message files have the Thousand-Year Door format and tags;
     `global.txt` opens as blocks (places, chapter titles, items, enemies, Catch Cards, Tippi's tattles,
     descriptions, menus); an unedited file stays byte for byte. The Font Editor opens `font\papermarioset_EU`,
     `_US`, `_JPN.bfn` and the HOME Menu font; the Textures window lists the title, pause, file-select,
     name-entry, chapter captions, HOME Menu and channel banner textures. `2_build.bat` packs every changed file
     back into its archive and the disc image.
   - `lunar_sssc` — Lunar: Silver Star Story Complete (PlayStation, USA, 2 discs). **Source:** the workspace's
     `source` folder (`1_unpack.bat`): `LUNADATA\TEXT*.DAT` (event scripts: messages and yes/no answers),
     `LUNADATA\SYSTEM.DAT\00_0001.bin` (items, spells, monsters, places, menus; fixed room), the unpacked program
     `SLUS_006.28` (Font Editor: text font and symbol font) and 15 TIM pictures (Textures: title menu, logos,
     insert-disc screens). Tags: `{wait}`, `{page}`, `{clear}`, `{close}`, `{end}`, `{FA:39}`-style codes.
     A longer message moves the script code after it; `2_build.bat` rebuilds both discs.
   - `lunar_ebc` — Lunar 2: Eternal Blue Complete (PlayStation, USA, 3 discs). **Source:** the workspace's
     `source` folder (`1_unpack.bat`, files of `DATA.PAK`): `DATA\EVENT` (event scripts), `DATA\PEOPLE` (what
     people on a map say), `DATA\SYSTEM\2499\05-12.bin` (items, spells, menus, memory-card messages),
     `DATA\BATTLE` (monster names, 21 letters), `DATA\MAP` (place names, fixed length),
     `DATA\SYSTEM\0003.bin`. Font Editor: the text font `DATA\SYSTEM\2499\18_font.bin` (94 glyphs and their
     widths). Textures: title screen and logos, battle status page, card game words, 50 full-screen pictures.
     Tags: `\n` next line, `{2000}` new page, `{3007}` the 'more' arrow, `{B2C9}` speaker, `{XXXX}` other codes.
     A longer text moves the messages; a file that outgrows its place goes to the end of the disc.
   - `paper_mario_ok` — Paper Mario: The Origami King (Switch, 2020), the same formats. **Source:** the
     workspace's `source` (`1_unpack.bat`: base + update): `msg\EU_English\*.msbt` (59 files, 9,708 messages),
     `font\*.bffnt` (12 fonts) and `ui\...\*.bntx`; a picture the game keeps once per language opens as its
     English copy `*.bfres.en.bntx` and `2_build.bat` writes it into both English versions (en-GB, en-US).
     Tags come from this game's `msg.msbp` (`{Font:4}`…`{Font:-1}` switches the font).
   - `animal_crossing_nh` — Animal Crossing: New Horizons (Switch, 2020). **Source:** the workspace's `source`
     (`1_unpack.bat`: the repack's base + update + DLC): `Message\*_USen.sarc.zs` (11 archives, 3,086 MSBT
     files, 120,498 messages; each MSBT is one block), `Swkbd\message\USen\*.msbt.szs` (the game's keyboard),
     `Font\ScalableFont.sarc.zs` (OpenType CFF `.bfotf` and TrueType `.bfttf` fonts — a drawn glyph is saved
     into either), `Font\BmpFont_US.sarc.zs` (number fonts), `Layout\*.zs` and `Model\*_USen.*.zs` (BNTX
     textures, also inside a model's BFRES; every ASTC block size). Tags are named from the text itself:
     `{Color:Npc}`, `{Item7:He:She}`, `{Item8:512:years:year:years}` (an item's gender and plural forms).
   - `vagrant_story` — Vagrant Story (PlayStation, USA SLUS-01040). **Source:** the workspace's `source`
     folder, filled by `1_unpack.bat` with the disc's text files under their disc paths: `EVENT\*.EVT`
     (cutscenes), `MAP\*.MPD` (room events), `MENU\ITEMNAME.BIN`, `ITEMHELP.BIN`, `MCMAN.BIN`, `MENU12.BIN`,
     `MENU\*.PRG` (menus), `SMALL\HELP*.HF0` (Quick Manual), `SMALL\MON.BIN` (Monster Book), `SMALL\SCEN*.ARM`
     (room names), `MAP\ZONE*.ZND`, `BATTLE\*.PRG`, `TITLE\TITLE.PRG`, `SLUS_010.40` (names in program and zone
     data: spells, arts, enemies, their equipment; ASCII HUD words such as `#WEAPON`, kept ASCII) and the
     font `FONT\VSFONT.FNT`; a room also shows its door messages and the weapon in its chest; the staff roll
     `ENDING\ENDING.PRG` (ASCII, edited in place) and the picture files of Tools → Textures (`GIM\`,
     `SMALL\*.DIS`, `SMALL\HELP*.HF1`, `BATTLE\SYSTEM.DAT`, `MENU` pictures) are unpacked too; **Translation:**
     `translation`. Tags are readable: `{down 13}` / `{>12}` place the text in the balloon, `{color 1}`,
     `{num 0}`, `{wait}`, `{page}`; Japanese leftovers and empty strings are not shown; an unedited file stays
     byte for byte. A dialog line's width limit is its balloon (`chars_per_line` × 12 px of the italic font,
     read from the script's DialogShow), other text the widest English line of its table. Text grows inside
     its table or script: an event keeps its 6144 bytes, a room may grow to the end of its last CD sector,
     every other file keeps its size, and names in program data are edited in place (never longer); a save
     that does not fit says which file and table. Ukrainian letters go through the plugin's
     `translation_map.json` (look-alike letters share the Latin codes, the others take accented cells the
     English text never uses; `translation_map.md`). The Font Editor opens the font twice (format `vagrant`):
     **Dialog font (italic)** and **Menu font (regular)**, with the advances of `BATTLE.PRG`. The Russian fan
     translation (Reborn 1.5f, `reference\RU`) is the reference language, matched by file, table and place.
     Scene context names the area and room of a room file (`vs_index.json`); the game data names no
     speakers. `2_build.bat` writes the changed files over their own sectors of the disc image (EDC/ECC
     recomputed) and splits the font back into `SYSTEM.DAT` and `BATTLE.PRG`.
   - `metroid_prime_trilogy` — Metroid Prime Trilogy (Wii, USA R3ME01): Prime 1, 2, 3 and the Trilogy menu.
     **Source:** the workspace's `source` made by `1_unpack.bat` from the game's Retro packages, one folder per
     game (`MP1`, `MP2`, `MP3`, `Menu`): `text\<package>\<name>.<id>.strg` (every string table once per game,
     5,473 tables, 16,211 strings), `font\*.font` (59 fonts), `texture\<package>\*.txtr` (2,088 interface
     textures); **Translation:** `translation`. Every table is a block of its English strings; the game's
     `&push;` / `&main-color=#…;` / `&image=…;` tags read `{push}`, `{main-color=#…}`, `{image=…}`. A saved table
     carries the edited text as every language of the table (the game shows it whatever the console language);
     an unedited table stays byte for byte. The Font Editor opens every font (`retro_font_gx`: glyphs are edited
     in place, none added; no font has Ukrainian letters); the Textures window opens the interface textures
     (`txtr_gx`: every GX format). `2_build.bat` writes changed files into every package of that game that holds
     them and the packages into a copy of the ISO
   - `metal_gear_solid_ps1` — Metal Gear Solid (PlayStation, USA, both discs). **Source:** the workspace's `source`
     folder, filled by `1_unpack.bat`: `RADIO.DAT` (every codec call), `SLUS_005.94` (item names and descriptions,
     menus, memory card messages; edited in place), `stage\<stage>\*.gcx` and `*.bin` (scripts and overlays of
     `STAGE.DIR`: pick-up labels, mission log, VR and difficulty menus), `subs\demo.subs`, `vox.subs`, `movie.subs`
     (subtitles of cutscenes, voices and movies of both discs, each distinct block once), the font `fontont.res`
     and the PCX textures of the title, menu, briefing and result stages; **Translation:** `translation`. Line breaks
     are `#N` in codec calls and `|` in subtitles (shown as new lines); other game codes read `{901B}`. A codec call
     or script line may grow; a subtitle block may grow up to the end of its stream sector, a program string only
     inside its slot. `2_build.bat` builds both discs (`STAGE.DIR`, codec call offsets, subtitles, program).
   - `metal_gear_solid_mc` — Metal Gear Solid, Master Collection Version (PC Steam and Switch; the USA game in
     M2's emulator). **Source:** the workspace's `source` folder (`1_unpack.bat`): the same PlayStation files as
     `metal_gear_solid_ps1` (`SLUS_005.94` is the program from M2's RAM image) plus M2's own text in
     `m2\text\**\*.psb` (menus, messages, credits, Master Book; English lines, saved as UTF-8), M2's fonts
     (`m2\font`, Font Editor formats `m2` and `mgs1_hd`) and pictures (`m2\texture\*.pcx`, `m2\image\*.m2tex`,
     Textures format `m2`). `2_build.bat` writes M2's patch archive `patchdata.psb.m` + `patchdata.bin`
     (PC: `build\windata`; Switch: a LayeredFS mod) and drops M2's own small fixes where the translation changed
     their bytes.
   - `plain_text` — Plain Text
   - `pokemon_fr` — Pokemon FireRed/LeafGreen
   - `default_plugin` — Default Plugin Template
4. After open, the last session is restored (block, string, undo stack, most filters). **Show Unsaved Only** (tree and strings list) is always off after a restart (`core/data_store.py`).
5. `File → Close Project` unloads the workspace. It does not quit Picoripi.

**Do not** point Source and Translation at the same writable tree if you still need a clean original. **Do not** bundle copyrighted dumps in this repo.

---

## 3. File menu

| Command | Shortcut | What it does |
|---------|----------|----------------|
| New Project… | Ctrl+N | Wizard above |
| Open Project… | Ctrl+O | Load a `project.uiproj` |
| Recent Projects | | Last workspaces |
| Close Project | | Unload. Disabled until a project is open |
| Import Block… | | Add one file. **Project mode only** (tooltip: “only available in Project mode”) |
| Import Directory… | | Add a folder of files. Same restriction |
| Save Changes | Ctrl+S | Write **every** unsaved string. No confirm dialog |
| Save Changes As… | | Copy translations to a new location |
| Reload Original | | Re-read source files from disk |
| Revert Changes File to Original… | | Throw away the translation file and start from source |
| Export Translations to JSON… | | Round-trip translations. Disabled with no project |
| Export Original to JSON… | | Dump source strings |
| Import Translations from JSON… | | Load a previous export |
| Reload Tag Mappings from Settings | | Re-apply aliases after you edited plugin settings |
| Settings… | Ctrl+P | Preferences |
| Exit | | Quit; session checkpoint is written |

Partial save: right-click a block → save that block only. **Do not** use Revert unless you mean to discard the translation file.

---

## 4. Edit menu

| Command | Shortcut | Notes |
|---------|----------|--------|
| Undo Typing | Ctrl+Z | Editor and Speaker field |
| Redo Typing | Ctrl+Y or Ctrl+Shift+Z | |
| Save Translated | Ctrl+T | Snapshot of the current translation (local backup). Disabled until a string is selected |
| Restore Translated | Ctrl+Shift+T | Bring that snapshot back |
| Undo Paste Block | | Enabled after a block paste |
| Paste Block Text | Ctrl+Shift+V | Paste a whole block’s worth of lines |
| Find… | Ctrl+F | Toggle the inline search panel. F3 next, Shift+F3 previous |
| Advanced Search… | Ctrl+H | Project-wide search/replace |
| Auto-fix Current String | Ctrl+Shift+A | Current string. Ctrl-click the **Auto-fix** button to pick rules. The shortcut always runs the plain fix |
| Rescan All | Ctrl+Shift+R | Force widths, every warning, the Blocks tree, editors and preview. Use when the tree looks stale or after font/tag/width changes. Same control as the toolbar button. Right-click one block for that block only |

---

## 5. View menu

| Command | Shortcut | Notes |
|---------|----------|--------|
| Preview | Ctrl+Shift+P | Checkable. Shows or hides the visual preview under Editable |
| Hide Tags | Ctrl+Q | Hide control codes in Original and translation panels |

Same hide-tags toggle exists as the **Hide tags** checkbox above Original.

---

## 6. Tools menu

This is the localization pipeline plus utilities. Prefer **Localization Pipeline…** over clicking items at random. Same actions live in the wizard.

| Command | Shortcut | Role |
|---------|----------|------|
| Localization Pipeline… | | Ordered steps + status. Thin: every button runs the same action as the menu |
| Font Editor… | | Bitmap fonts in a separate window; the project stays open. Opens Nintendo `.bfn` (Twilight Princess, Wind Waker), the message font inside an N64 Zelda ROM (OoT, MM), Hyrule Warriors `.g1t` atlases, Age of Calamity `.g1n` fonts, Switch and Wii U `.bffnt` (The Wind Waker HD: big-endian, GX2-tiled sheets; Paper Mario: Color Splash: two-tone BC5 sheets, shown as the letter in grey over its shape in alpha), Wii `.brfnt` (Skyward Sword HD and Wii: GX I4 sheets) and the 3DS fonts: `.bcfnt` / 3DS `.bffnt` (A Link Between Worlds, Tri Force Heroes), Grezzo `.qbf` (Ocarina of Time 3D) and `.gzf` (Majora's Mask 3D), and the Switch scalable fonts `.bfotf` / `.bfttf` (Tears of the Kingdom, Animal Crossing: widths are saved as the glyph advances, a redrawn glyph is saved as an outline traced from its pixels, CFF or TrueType), 2bpp text fonts of Metal Gear Solid: The Twin Snakes and of Metal Gear Solid (PlayStation, `font.res`) and the 12x12 text font of Vagrant Story (regular and italic, with the advances of `BATTLE.PRG`; the two staff-roll fonts of `ENDING.PRG`) and the Tingle Tuner's GBA tile font inside `client_u.bin` of The Wind Waker (each from its project only), Nintendo DS `.nftr` (Four Swords Anniversary Edition) — open them with **Open** (no project needed; Save writes the file back). In a font that maps Unicode characters (`.bffnt`, `.g1n` and the 3DS fonts), typing a letter into an empty cell's character column adds that real character to the font (no translation slot; a character the font already has is refused): draw the glyph in a free cell and give it its letter. The game's own fonts, named by its plugin, are listed in the font tree and open from the project (the translation copy once there is one); Save writes the translation copy and the font's widths with the translation map to `<project>/font_maps/`, which the width checks read. Hyrule Warriors DE takes its advances from a table in the game's executable, not from the atlas: the editor shows that table (in atlas pixels) and Save also writes it as executable patches `exefs/<build id>.ips` in the translation folder, one per game version (the workspace's `2_build.bat` puts them into the mod). Wind Waker also lists its name-entry and system fonts; Twilight Princess lists its text and ruby fonts (the archives in `res/Fontus`). **Render System Font to Glyphs** takes a TTF/OTF through **Font File...** (no install needed) and can **Thicken** strokes for small heavy fonts; with baseline alignment each rendered letter is moved to stand on the font's own Latin baseline (р у ф hang like p, д ц щ line up by their top); **Move glyph** (◀ ▲ ▼ ▶ or Ctrl+Arrow keys) shifts the selected glyphs' pixels 1 px inside their cells, with undo, in every format. Uses the same **Language** as the rest of the app |
| Textures… | Ctrl+E export, Ctrl+I import, Ctrl+O open, F5 reload | Text baked into game textures (title cards, menu labels, logos) in a separate window; the project stays open. The textures the game's plugin names are listed with a thumbnail, the game file, the pixel format, the size and a status (Not started / Redrawn / Checked in game, kept in `<project>/textures/status.json`); the selected one is shown original next to translated. **Export PNG…** / **Export All…** save PNGs into a folder (default `<project>/textures/png`) under stable names made from the game file and member; redraw them in any image editor, then **Import PNG…** (one texture; another size is resized after a question) or **Import Folder…** (every PNG whose name matches). Picoripi encodes the image in the game's own format (GameCube/Wii BTI, TPL and BMD/BDL model textures, GBA tiles inside a packed multiboot program, 3DS BFLIM/BCLIM, CTPK and Grezzo CTXB (also the textures inside CMB models and CMAB animations) in ZAR/GAR/LzS archives, Wii U BFLIM and GX2 (GTX, TMPK packs), Switch BNTX (BC1-BC5, BC7, every ASTC block size; also the BNTX inside a model's BFRES), Koei Tecmo G1T, Retro TXTR (Metroid Prime 4), GBA / DS character tiles, N64 textures in the ROM, PlayStation TIM and headerless 4/8/16-bit pictures, Vagrant Story GIM screens, help sprites and the compressed title screen, Retro TXTR of the Wii Metroid Prime games, PSP GIM, Policenauts picture packs, Metal Gear Solid PCX and M2 PSB pictures, Level-5 IMGC and G4TX, Wii U BFRES textures) and writes the translation copy, repacking the archives around it, so the workspace's `2_build.bat` puts it into the mod; only the changed blocks are encoded again. **Revert** puts the original back. **File → Open Texture File…** opens a texture or an archive of them directly (games without a plugin, such as the 3DS ones); that file is then edited in place. Not yet: BRRES model textures (Wii) |
| Script Markup Studio… | | Mark a walkthrough (Phase 0 for MemePalace). See [9](9_Script_Markup.md) |
| MemePalace Context Builder… | Ctrl+M | Weave the marked script into story memory |
| Prepare Glossary… | | One automatic glossary pass |
| Merge Speakers from Script… | | Match script names to game voice codes. Needs plugin capability `speaker_attribution` |
| AI Batch Translation ➔ | | Submenu: Translate Story First, Translate Remaining Blocks, Translate All (Story ➔ Semantic) |
| Inspect Story Context… | Ctrl+I | Timeline, speaker, visual context for the **selected** row |
| MemePalace Database Viewer… | Ctrl+Shift+I | Rooms, visual contexts, character graph |
| Fix All Strings… | | Project-wide Auto-Fix with a rule checklist |
| Export Current BMG to JSON… | | Selected BMG only. Disabled until a BMG block is selected |
| Import Current BMG from JSON… | | Into the selected block |

---

## 7. Navigation menu

| Command | Shortcut |
|---------|----------|
| Next Block Nav | Alt+Shift+Down |
| Previous Block Nav | Alt+Shift+Up |
| Next Folder Nav | Alt+Shift+Right |
| Previous Folder Nav | Alt+Shift+Left |

Shortcuts are window-wide. **Ctrl+PageUp / Ctrl+PageDown** also move to the previous/next block (`ui_event_filters.py`). The up/down arrows next to **AI Translate** jump **problem** strings (Ctrl+Down / Ctrl+Up). Alt+Down / Alt+Up (and Up/Down in the Strings list) move one string regardless of warnings.

---

## 8. Bookmarks menu

| Command | Shortcut | Notes |
|---------|----------|--------|
| Add Bookmark… | Ctrl+B | Current line of the active block. Needs an open project. |
| Clear All Bookmarks | | Permanent delete from this project |

The menu lists only bookmarks for the **open project**. They are stored in that project's `.uiproj` (`metadata.settings.bookmarks`), not in `settings.json`. Closing the project clears the menu. If a project has no bookmark list yet, leftover entries for its name in the old global `settings.json` are copied into the project once.

---

## 8a. Language menu

**Language** lists every `locales/<code>.json` that already has UI translations. The label is `@language_name` inside that file (English, Українська, …). Changing it writes `ui_language` and asks for a restart.

A missing string in the chosen catalog is shown in English. Russian is never listed. Fill more catalogs with `tools/i18n-translate/run.bat`; they appear in the menu after a restart. **Font Editor** uses this language too.

---

## 9. Help

**Help** sits as a corner button on the menu bar (not a normal left-to-right menu).

| Command | Shortcut |
|---------|----------|
| Shortcuts Help | F1 |

Opens **Keyboard Shortcuts Reference**. Mouse modifiers (Ctrl-click, Shift-click) are documented on each button’s tooltip, not in that table.

Shortcuts listed in F1:

| Action | Shortcut |
|--------|----------|
| Save Project/File | Ctrl+S |
| Hide/Show Tags in Editor | Ctrl+Q |
| AI Chat Window | Ctrl+Shift+C |
| Open Glossary | Ctrl+G |
| Shortcuts Help | F1 |
| Settings | Ctrl+P |
| Undo | Ctrl+Z |
| Redo | Ctrl+Y / Ctrl+Shift+Z |
| Find Text | Ctrl+F |
| Advanced Search | Ctrl+H |
| Find Next | F3 |
| Find Previous | Shift+F3 |
| Paste Block Text | Ctrl+Shift+V |
| Auto-fix Current String | Ctrl+Shift+A |
| Navigate to Next Problem | Ctrl+Down |
| Navigate to Previous Problem | Ctrl+Up |
| Select Next String | Alt+Down / Down (in Preview) |
| Select Previous String | Alt+Up / Up (in Preview) |
| Next Block | Alt+Shift+Down |
| Previous Block | Alt+Shift+Up |
| Next Folder/Category | Alt+Shift+Right |
| Previous Folder/Category | Alt+Shift+Left |
| Next / previous block (extra) | Ctrl+PageDown / Ctrl+PageUp |

---

## 10. Toolbar

Left to right (`toolbar_builder.py`):

Save · Undo · Redo · Find · Preview · **AI Batch Translation** (opens pipeline mode chooser) · **Open AI Chat** (`Ctrl+Shift+C`) · Font Editor · **Rescan All** (`Ctrl+Shift+R`) · Settings · (spacer) · **Run External Script** (`>_`) · Shortcuts Help.

**AI Translate** and **AI Variation** are **not** on this toolbar. They sit above Editable.

**Run External Script** runs the path in **Settings → Global → External Tool/Script Path**. Save (`Ctrl+S`) before you run a ROM build; the tool reads files on disk.

**AI Chat:** in the chat input, Ctrl+Enter sends; Enter adds a new line.

---

## 11. Blocks tree (left)

Header buttons: add folder (disabled until a project is open), expand all, collapse all. Ctrl+wheel over the tree zooms the tree font.

**Show Unsaved Only** (above the tree): only blocks and folders with unsaved changes. Session-only; always off after restart.

Tree toolbar (bottom of the panel; buttons start disabled):

| Button | Action |
|--------|--------|
| + | Add / import a block |
| − | Delete the selected block |
| ✎ | Rename |
| ↑ / ↓ | Reorder. Drag-and-drop also moves. Alt+Shift+Up/Down **navigates**, it does not move |
| ⟳ | Rebuild Speakers, Chapters and Items from current story data. Does not touch translation files |

**Glossary…** under the tree opens the project glossary (`Ctrl+G`). Ctrl-click a glossary term in Original to open that entry.

**Glossary Dialog Layout & Controls**:
- **Left Panel (Terms & Categories)**:
  - Top: Search bar for filtering terms in real time.
  - Middle: Category tabs (`_tab_widget`) organizing entries into semantic domains ("Characters", "Items", "Locations", etc.).
  - Bottom: Dedicated bottom bar with the **Needs review** (`_unconfirmed_only_checkbox`) filter checkbox, filtering the table to unconfirmed terms without taking up horizontal search bar or vertical detail space.
- **Right Panel (Term Details)**:
  - **Side-by-Side Term & Translation**: Synchronized `QGridLayout` with uniform 26px height. The original term is read-only, selectable, constrained to 280px max width, and features an interactive **Wiki ↗** button linking directly to game lore search (via `BaseGameRules.get_external_reference_url`). The editable translation is paired with a compact **Confirm** button.
  - **Dedicated Action Row**: Positioned directly below the translation input field to allow the input unobstructed full width (up to 400–550px+). Contains a prominent **Save** button (`Ctrl+S`, which lights up in blue `#2563eb` when uncommitted edits exist), **Confirm translation** (advances to next unreviewed term), and **Discuss with AI…** (opens chat with full term context).
  - **Unsaved Changes Navigation Protection**: A confirmation dialog (`Save` / `Discard` / `Cancel`) appears when selecting another row, switching tabs, or closing the dialog with uncommitted edits.
  - **Description & Notes**: Includes the **Profiled via AI** checkbox in the section header with a descriptive tooltip indicating character speech profiling status.
  - **Collapsible Sections**: Description, AI Notes, and Occurrences panels feature collapse/expand toggle buttons (`[▼]/[▶]`) to optimize vertical space.
  - **Granular Occurrence Filtering**: Independent checkboxes for **Mentions** (text references) and **Spoken** (lines spoken by this character).
  - **Reference Line Preview & Occurrence Alignment**: For each dialogue occurrence, the preview shows the complete original message and the full corresponding reference record for that (block, string) without trimming surrounding lines. Long previews scroll vertically, even when there is only one occurrence. The occurrence is highlighted within the full original text, and matching reference terms are highlighted within the reference lines while preserving all line breaks. The `RU:` block is displayed only when the reference is explicitly identified as Russian; other reference languages provide evidence to the AI translator without displaying an `RU:` badge in occurrences.
  - **In-Place Variant Application & Double-Click**: Double-clicking any proposed variant or clicking **Apply selected variant** inserts the candidate translation and updates notes in place without advancing to the next row. Confirmation and progression to the next term are strictly decoupled and triggered by clicking **Confirm translation**. Reference variants from external patches are styled distinctly (cyan/italic) and protected from double-click application.
- **Bottom Toolbar**: Contains **Force Retranslate...** (highlighted in orange `#ea580c`, creates automatic `glossary.json.bak` backup before AI re-translates entries) and **`[☁ Companion Sync...]`** for 1-click push and pull synchronization with [Picoripi Companion](12_Picoripi_Companion.md).

Right-click (empty space): **Create Folder**, **AI: Translate All Blocks (UA Chronological)**, **Revert All Blocks to Original**, **Restore All Translations**.

Right-click a file: import, save this block, rescan, widths, markers, restore. **Chapters** root and Act folders have no context menu (read-only structure).

Status bar (bottom of the window): Original path, Changes path, Plugin name, `Strings: N | Unbound: N`, then cursor Pos / Line / Width.

---

## 12. Strings in block (top right)

Click a line to bind Original + Editable immediately. The BFN preview follows about a frame later. Glossary, spellcheck, tags, and warnings catch up after you stop typing (~1.5s). The list itself is read-only.

| Checkbox | Effect |
|----------|--------|
| Highlight moved | Highlight strings already in a virtual category. Hidden unless categories apply |
| Hide moved | Hide those strings from the parent view. Hidden unless categories apply |
| Hide empty strings | Collapse consecutive empty strings into a placeholder |
| Hide translated | Hide already translated strings |
| Show Overrides Only | Only strings with custom font or width |
| Show Unsaved Only | Only strings with unsaved changes. **Always off after restart** |
| Show Warnings Only | Only strings with selected warning types |
| **Warnings: X / Y** | Choose which warning types the filter uses. X = selected types, Y = types enabled in Detection |

Several filters can combine. **Do not** leave **Show Unsaved Only** on and assume the file is empty — uncheck it.

---

## 13. Original, Reference Tabs, and Editable

**Source Panel (Left)**

- **Dynamic Reference Tabs**: When a reference patch or multi-language ROM / ISO is configured in project settings (**Settings → Project → File Paths → Reference Translation / ROM Path**), the panel dynamically generates comparison tabs (`Original (EN)`, `Russian (RU)`, `German (DE)`, `French (FR)`, `Italian (IT)`, `Spanish (ES)`).
- Read-only, selectable, with synchronized line scrolling and cursor movement across all language views.
- **Max-width:** click the value to copy it into the translation Max-width field, then press **Apply** on the right.
- **Hide tags** (`Ctrl+Q`): toggles control code visibility across all source and translation tabs.

**Column of icon buttons** (between the panes)

| Button | Action |
|--------|--------|
| Arrow (`→`) | **Copy active source string** — copies text from whichever tab is currently active (Original or reference translation) into the target translation editor |
| Document+arrow | **Restore translation** — last backup (`Ctrl+Shift+T`) |
| S | **Inspect story context** (`Ctrl+I`) |
| R | **Open in Script Markup Studio** — jump to the marked-script place for this string |

**Editable (Right)**

- This is where you type.
- **Vertical Level Synchronization**: An event filter (`HeaderSyncFilter`) dynamically calculates `left_header.height = right_header.height - tab_bar.height`, ensuring the top line of text editors on both sides starts at the exact same vertical Y level across all screen resolutions and DPI scaling.
- Under it: visual BFN preview (if Preview is on) with a window-kind bar when the plugin supports it.

**Do not** apply Font / Max-width without **Apply**. **Apply** is enabled only while there is an unapplied change.

---

## 14. Story Context & Controls (above Editable)

Organized into a compact 2-row header above the editable pane:
- **Row 0**: `Window:` and `Chapter:` on the left; Navigation (`[↓][↑]`), `AI Translate`, `AI Variation`, and `Auto-fix` on the right.
- **Row 1**: `Speaker:` on the left; `Font:`, `Max-width:`, and `Apply` on the right.

| Field | Behaviour |
|-------|-----------|
| **Window:** | Message window type from game data. Double-click the label to open the physical block |
| **Chapter:** | Assign this row to a Story chapter or scene, including rows without a script link. Double-click the label to open the virtual Chapter |
| **Speaker:** | Editable combo with autocomplete. **Enter** commits the name (`save_speaker_for_current_string`). Clicking a drop-down item alone does not save. Double-click the label to open virtual Speaker or Item |
| **Font:** | Per-string font override |
| **Max-width:** | 0 = plugin default. Right-click: **Reset to Plugin Default**, **Set Width from Original** |
| **Apply** | Save Font and Max-width for this string |

`None` in Speaker clears the assignment. Empty BMG padding is not stuffed into Speakers; do not invent a speaker for those slots.

---

## 15. Action buttons above Editable

| Button | Click | Modifiers |
|--------|-------|-----------|
| Down / Up arrows | Next / previous **problem** string (Ctrl+Down / Ctrl+Up) | Alt+Down/Up = next string anyway; Alt+Shift+Down/Up = next block |
| **AI Translate** | Translate the current string. Reuses a backup if one exists | Ctrl-click: prompt editor + always re-translate. Multi-string: select lines in Strings, right-click |
| **AI Variation** | Alternative wording of the current translation | Select a fragment in Editable first to rewrite only that. Ctrl-click: prompt editor |
| **Auto-fix** | Fix issues with every enabled rule (`Ctrl+Shift+A`) | Ctrl-click: pick rules. Shift-click: page-local (text never flows across a page). Ctrl+Shift-click: both. The keyboard shortcut is always the plain fix |

If an AI task is already running, Translate shows **AI Busy**.

---

## 16. Settings (`Ctrl+P`)

Window title **Settings**. Tabs:

| Tab | Contents |
|-----|----------|
| **Global** | Theme (restart), Active Game Plugin (restart), font sizes, external script path, Wiimms ISO Tool (`wit.exe`) path, space dots, restore session, prompt editor before AI, live preview, real-time warning scan, glossary system, archive size warnings, auto-sleep idle delay |
| **Project** | Only with a project open. Subtabs: File Paths (Directory Mode, Auto-generate translation path, original/changes/fonts paths, Reference Translation / ROM Path with popup selector for folder or `.iso`), Display, Rules, Context Tags, Tag Aliases, Font Map, Detection, Auto-fix (**Align sentences to original page layout**, **Prevent adding empty padding lines during pagination**, plus per-problem toggles) |
| **Spelling** | Enable spell checking, dictionary language, Manage Dictionaries… |
| **AI Translation** | See [11](11_AI_Translation.md) |
| **AI Glossary** | Provider, key, Use API key from AI Translation, model, chunk size, Parallel Requests, Retry Delay |
| **Companion** | Server URL, API token, Test Connection, automatically sync on project open/close (see [12](12_Picoripi_Companion.md)) |
| **Logging** | Console / file / `ai_traffic.log`, log path, event categories |

Theme change and plugin change each show a restart required dialog.

---

## 17. What not to do in the main window

- Do not edit Original.
- Do not treat an empty Strings list as a bug before unchecking **Show Unsaved Only** and **Hide empty strings**.
- Do not Revert the changes file unless you intend to wipe translations.
- Do not skip Save before `>_`.
- Do not set Parallel Requests higher than Active accounts on the local proxy dashboard.
- Do not run glossary / merge / bulk translate with no provider configured.
- Do not treat empty BMG slots as unbound dialogue — they stay in the physical file only.
