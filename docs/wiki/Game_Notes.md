---
status: current
updated: 2026-10-21
owns: plugins
tokens: 47.6k
purpose: Per-game technical notes: source folders, file formats, tags, previews, build steps
---
# Game notes

**Language:** English · [Українська](uk/Game_Notes.md)

This page holds the technical notes of each game plugin: which folder is the **Source**, which file formats the plugin reads, which tags the text uses, how the preview works and what the build writes. Read it when you work on one game. The table of all games is on [Supported games](Supported_Games.md).

- `zelda_bmg` — Zelda: Twilight Princess BMG. GameCube, Wii and Wii U (HD) alike: **Source** is the folder with
  `bmgres*.arc` (`res/Msgus` on GameCube and in the Wii disc's DATA partition, `content/res/Msguk` or `Msgus` in
  HD); the three share message ids, so speakers, scenes and conversations work the same. HD text adds Wii U
  control icons (`{U:ZL}`, `{U:L stick}`, `{U:+}`…). Point **Fonts folder** at `res/Fontus` (HD: `res/Fonteu`).
  HD draws its letters from the textures in `*.pack.gz`, not from the BFN: the workspace build
  (`TPHD_UA\2_build.bat`) redraws them from the edited BFN sheets. **Build** (Project Manager): **GameCube disc
  image** writes the translated ISO next to a copy of the disc that the wizard recorded when it unpacked the game
  (a project made before that has no record: create it again); **Dusklight mod** writes `Twilight Princess (UA).dusk`
  and needs your own USA disc; **Wii U graphic pack and SDCafiine folder** writes the Cemu graphic pack and the
  SDCafiine folder for the HD game, with its size tables and redrawn font textures. The Wii disc has no build target
  yet: its partitions are encrypted and Picoripi cannot write them. **New project** wizard: add the USA GameCube
  disc (GZ2E01) or the USA Wii disc (RZDE01; the wizard asks for your Wii key file once) and the wizard unpacks it;
  for Wii U HD, which Picoripi cannot read as a `.wux`, add the unpacked title folder (the one with `code`,
  `content` and `meta`) with **Add folder...**: its source becomes `content/res/Msguk`.
- `zelda_mc` — The Legend of Zelda: The Minish Cap
- `zelda_ww` — Zelda: The Wind Waker HD (Wii U): the `Message/*.msbt` and `Font/*.bffnt` taken out of `content/Common/Pack/permanent_2d_UsEnglish.pack` (one block per MSBT). Tags come from the game's `CKing.msbp` (`[Red]…[/C]`, `[Name]`, `[Wait:10]`, `[A]`); speakers, box width (875 font units in a talk box, 812 in signs and item boxes, 4 lines a page), conversations and glossary terms come from each message's attributes. An unedited file saves byte for byte. Load Reference Patch with a folder of `permanent_2d_<Region><Language>.pack` files (the workspace's `reference\`: the game's French and Spanish packs and the Russian patch's pack named `permanent_2d_RuRussian.pack`) shows those languages, Russian first, matched by file and label. Font Editor: all six fonts (CKingMsg, CKingMain, CKingMainL, the RGBA8 button pictures CKingPic, CKingRuby, CKingZelda). Textures window: the BFLIM images of the title logo, boot screen, button and controller screens (`source\Layout\*.szs`, the game's `content/Common/Layout`) and the map titles and button pictures in the pack. Older projects of Kruptar `.txt` dumps still open. The wizard takes the game folder or `permanent_2d_UsEnglish.pack` and unpacks `Message\`, `Font\`, `Pack\` and `Layout\`; **Build** makes the Cemu graphic pack (`graphicPacks\Picoripi_UA_WWHD\`) from the changed messages and fonts. The Switch homebrew port SwitchWakerHD (centollOS, a fork of ZeldaWWHDRecomp) reads the extracted game from `sdmc:/switch/wwhd/game/` at run time, so the workspace's `2_build.bat` also writes `build\switchwakerhd\switch\wwhd\game\content\` (the translated pack and `Common/Layout` files) to copy over that folder; the same files run in the ZeldaWWHDRecomp Windows build
- `paper_mario_cs` — Paper Mario: Color Splash (Wii U, Europe): **Source** is the workspace's `source\content` (`1_unpack.bat` decompresses the game's `.lz` files there), one block per `messages/EU_English/*.msbt` (48 files, 6,940 messages). Tags are named from the game's `gojika.msbp` (`{PageBreak}`, `{wait:30}`, `{select:0:1:0:300:yesno}`, `{ItemName:item}`). The Font Editor lists the five `fonts/*.bffnt`; the Textures window the English UI pictures `Graphics/UI/**/*.EUR_en.bfres` (title logo, battle words, chapter cards). `2_build.bat` compresses the changed files again and writes their sizes into `fs.table`
- `zelda_sshd` — Zelda: Skyward Sword HD (Switch) and the Wii original (one plugin; the version is told by the source folder): the English `*.msbt` that `1_unpack.bat` takes out of the `.arc` archives (`US/Object/en_US/<area>/`, interface text `Layout/<name>/text/`), one block per file. Tags are named from the text (`{heroName}`, `{color:Red}`, `{item:11}`, `{icon:41}`, `{wait:15}`, `{choice1:65535}`); an unedited file saves byte for byte and `2_build.bat` packs the files back into the archives. The build target `skyrecomp` (Switch, "SkyRecomp (Windows port, mod folder)") writes `mods/Picoripi_UA/romfs/` for the SkyRecomp port: each changed message is packed into its `.arc`, a changed font is copied as it is; it reads the raw `romfs` folder next to `source` and refuses an `exefs/main` that is not v1.0.0. Speakers (the HD's speaker byte, Fi's window, one-character files), conversations (the MSBF flows), line limits per window kind (the game breaks an over-long line mid-word, so keep within them; 4 lines a page) and glossary terms come from the game data. Load Reference Patch with the HD `romfs` folder shows the official Russian first and 12 more languages — also for a Wii project, matched by label. Wii: the HOME Menu messages (`HomeButton2/home.csv`, the English column) are a block too. Tools → Textures lists the English text textures (title and ending logos, opening captions, Game Over, The End; Wii: save banner, wrist-strap notice, HOME Menu labels, the disc channel banner `opening.bnr`) and the Font Editor every font (also the icon font, the HD options-menu fonts, the Wii HOME Menu and MotionPlus video fonts) once the workspace tool `tools\ss_extra_sources.py` (in the HD workspace) has put them into `source`
- `zelda_mm64` — Zelda: Majora's Mask (N64): the US ROM itself (`.z64`, `.n64`, `.v64`) is the source file and the translated ROM the translation file. The ROM opens into four blocks: the 4,589 messages, the 45 credits messages (Ocarina of Time's codes), "Interface strings" the game's code prints itself (owl-warp places, "Rupee(s)", time speed, mask-code colours; each has a fixed room) and the title screen's "PRESS START" (two words of up to 5 cells of the title font: digits, Latin letters, a few accented cells); control codes as `{tags}` (zeldaret/mm); line width per textbox type, from the Font Editor's map of the game font once it is saved in the project, else from the game's own width table. Saving rebuilds the text files and the message tables from the source ROM, keeps the textures, glyphs and widths edited in the translated ROM (Tools → Textures, Font Editor) and fixes the header checksum. Speakers (one actor per line when the decompilation shows exactly one), scenes and seed glossary terms come from `context.json`, generated offline from zeldaret/mm and the ROM by `python -m plugins.common.zelda64_context`. Ukrainian letters are saved into the font slots of `translation_map.json` (the project's, else the plugin's): look-alike letters share the Latin glyph (А = A, і = i, Ї = Ï…), the rest take accented and unused punctuation slots chosen by width, so English stays readable; Ocarina of Time uses the same map. Load Reference Patch with the folder that holds `mm3d_seed.json` (Ukrainian carried over from Majora's Mask 3D, keyed by N64 message id) shows it as the "Ukrainian (MM3D)" reference
- `zelda_mm3d` — Zelda: Majora's Mask 3D (3DS, Europe, with or without the v1040 update). **Source:** the workspace's `source` folder (`1_unpack.bat` copies `romfs\message\eu\eue.gmsg`, the font `ltn16.gzf` and the text textures there); **Translation:** `translation` (whole files at their romfs paths; `2_build.bat` makes the LayeredFS mod, which the base game and the update both read). All 6,152 messages of `eue.gmsg` (dialogue, items, signs, Bombers' Notebook, place names, credits, file select, fishing, Sheikah Stone, objectives), one block per id range; an unedited file stays byte for byte. Control codes are tags named as in the N64 plugin where the code is the same: `{color:red}`, `{box-break}` (followed by a line break), `{quicktext-on}`, `{name}`, `{btn:A}`, `{delay:10}`, `{flow:wait}`, `{event:1}`, `{choices:2}`, `{center}`, `{sfx:0x01006858}`, `{plural:0x0007}…{plural-else}…{plural-end}`. **Load Reference Patch** with the Russian build's `eue.gmsg` (or its folder) shows its Russian; the game's `romfs\message\eu` folder shows French, German, Spanish and Italian. The Font Editor opens `ltn16.gzf`; the Textures window lists 129 text textures: menus and HUD (`layout\EU_English\*.gar`), area, day and boss title cards, the title logo and copyright (textures inside a `.cmb` model and a `.cmab` animation), the save notice and the version labels
- `zelda_oot64` — Zelda: Ocarina of Time (N64): the US 1.0 ROM, the same way as `zelda_mm64`: the ROM opens into three blocks — 2,115 messages, the 48 credits messages and the title screen's two strings ("PRESS START", "NO CONTROLLER": two words each, each word fits the cells the game draws, letters and digits of the title font only); codes from zeldaret/oot. The Font Editor lists the message font and the title and file-select font (the kanji glyphs the game picks by message 0xFFFC; it has no widths). Tools → Textures lists the 335 text textures (item, map and area names, pause and file-select labels, title cards); a text save keeps the textures and fonts edited in the translated ROM
- `jak_and_daxter` — Jak and Daxter (Switch OpenGOAL port; Jak 1 NTSC-U, Jak II NTSC-U, Jak 3 PAL disc, one plugin): **Source** is the English game text (`text/common.json`, 781 ids of Jak II, one block, ids kept) and the English subtitle lines (`subtitle/lines.json`, one block per scene). Saving writes only the changed lines into the port's English overlay; `2_build.bat` runs the port's own compiler, so the game reads the changed `*.TXT` files. The Textures window lists the level textures exported as PNG (`textures/**/*.png`, from the `.fr3` level files; RGBA and BC1/BC3 pixels). Text is an English overlay, so a Ukrainian translation shows in any build without a UI change; the Font Editor has no Jak font yet.
- `black_and_white` — Black & White (Lionhead, 2001) on the openBlack Switch port: **Source** is `Scripts/InfoScript2.txt`, the English ADD_TEXT table (6,974 strings, one block; the key, flag and narrator of each call stay as the game has them). Saving writes the translation into the text literals only, so the rest of the file stays byte for byte; a text with a double quote is refused. The build target `openblack_sd` writes that one file to `switch/openblack/game/Scripts/` for the SD card. The port does not show game text yet (its `RUN_TEXT` plays voice only and `LOAD_LANGUAGE` is not implemented), so a translated line is not visible in the port until a text display exists. Fonts and textures are not opened by this plugin.
- `sly_cooper` — Sly Cooper and the Thievius Raccoonus (ProjectCane port, Switch data folder, read in place): **Source** is the English text of each level file (`text/<world>/<level>.json`, one block per level, all text spans in file order: dialogue, subtitles, Thievius Raccoonus pages). Build replaces each changed line in a copy of the level file (`build\ProjectCane\Worlds\...`) and checks the result. Only ASCII text is written now: a line with other letters stops the build. Fonts and pictures are not opened yet; menu text is compiled into the port. The level-table reader needs a local option schema file, which this release does not ship.
- `manual_3ds` — Electronic manuals of the 3DS system titles (Instruction Manual viewer). **Source** and **Translation** are folders of one JSON file per manual (`src/manuals/*.json` layout: `en` English, `ru` Russian, `ua` translation). Both may be the same folder (the files read in place): the Original column shows `ru` (the keys follow the Russian document), the translation column `ua`, and the **English (EN)** reference tab shows `en` only on pages whose English lines up with the Russian paragraph by paragraph; on any other page it is empty. The editor checks each paragraph the way the console shows it: the lines are placed as the console build places them, then measured as the console draws them (line count, text panes per style, a word wider than its pane box, a line the console breaks inside its pane, a line past the card edge, a line that runs into a picture or a box frame beside it), and, with the repo_manual folder set in the preview panel, the page is also built and drawn from every current text on it, so the editor marks what only the drawn page shows (a line that leaves its filled cell, two paragraphs whose ink meets, a line a later pane paints over), plus markers, glyphs and button glyphs (each one must come back as in the Russian original; a glyph that has a pane of its own stays there and is left out of the translation). The preview panel is a simulator of the console's viewer: the page is built from the current text the way the console build builds it and drawn from the resulting layout files with the console's font, pictures, frames and chrome (header badge with the console page number, scroll track, bottom bar); the status line names the console page number and the defects the render shows (a line past the card edge onto the scroll track, a line the viewer broke inside its pane, a line over a picture or a frame, a line that starts inside a filled cell and leaves it — a white table label runs out of its grey cell onto the white page, as the console shows —, two lines whose ink meets, a line a pane drawn after it paints over, a missing glyph). The preview switches to the selected string's text size (large or small); the selected paragraph is outlined on the page, and the page scrolls to it when it is out of view; a string that draws no text says so in the status line. The same renderer runs headless: `python scripts/manual_3ds_render.py render <manual> <console page> --size small --out page.png`, `all --out <folder>` (every page of a build with its defect list), `validate --shots <classification.json> --calib <screenshot folder> --out <folder>` (matches console screenshot pairs against every build and writes an HTML report), `table` (console page number, `Page_NNN` file, title, category).
  **Preview.** The manual preview, in place of the BFN preview, draws the page of the selected string as the 3DS viewer shows it: the top and bottom screens one below the other, one continuous text column, scrolled with the mouse wheel or by dragging. The Y button (the bar at the bottom of the bottom screen, or the footer button) switches Large and Small text. The text is the current translation; a line the render flags (past the card edge, broken inside its pane, over a picture or a frame) gets a translucent red band. A line stops before a picture or a box frame beside it, as on the console. Set the folder with **Choose folder...** in the preview footer. The folder holds the owner's manual archives: it is read in place and nothing is copied. A project may hold every manual (one file per block): each block draws its own manual. A manual without console files in that folder (for example `browser`) shows one line that says so. Picture areas are drawn from their textures, and window panes (the orange item boxes) with their frame textures; a pane without a texture is filled with its own colour. The top bar shows the console page number in a badge coloured by the page's Index category, and the page's title (its translated Index entry). The neighbouring pages are not drawn in the panel. The viewer's side strip, scroll track and bottom bar use screenshot crops from the git-ignored data folder (`<data>/plugins/manual_3ds/chrome`); without them they are drawn flat.
  **Click and original.** A click on a paragraph in the preview (a press and a release without a drag) selects its string in the editor; a drag scrolls the page. The selector above the preview adds the original beside the translation. **Original: Russian (ru)** draws the page as the console stores it, with its own line breaks. **Original: English (en)** draws the English text in the Russian panes. Both canvases share the scroll, the text size and the selected paragraph. The status line gives the fit of the paragraph: its panes, the pane width, the lines its text needs with their widths, and the longest word. A problem for a word, a line count or a pane count gives the same numbers; a label in a grey cell says how many panes the cell has.
  **Line breaks.** Enter types the hard break `{br}`. A line break typed another way is a space on the console: the problem `NEWLINE` flags it, and its autofix turns it into `{br}`. A hard break takes a spare line on the console; without one the paragraph gets a line problem.
  **Folders.** Under each manual in the block tree: **Small text** and **Large text** (one folder per page, named by the page's section title), **Sections** (per section: its small text, then its large text) and **Contents** (the section titles). A string sits in two places. Section names follow the current translation of the index entry, or the original when it is blank. The names update after the tree rebuilds (after a save). Selecting a folder shows its strings in the list.
  **Same text.** A paragraph whose text is the same in two manuals (for example the Health and Safety section) takes one translation, and the memory bar and the batch fold use it. Each place is checked first: a place whose pane or line count the text does not fit is not written (the status bar says how many). Small and large text share a translation; the check decides for each place (wiki 11, *One source, one translation per run*).
- `system_3ds` — Nintendo 3DS system menus and applets (System Settings, HOME Menu, keyboard, error applet, Friend List, Mii Maker, eShop, browser and the other parts of the 3DS UA mod). **Source** and **Translation** are the same folder: the mod repo's `src`, edited in place (the repo's own build stays the build). Each `src/strings/<part>/*.json` file and each `src/layouts/<part>.json` file is one block. A string is one entry: its id is the MSBT label, or the layout pane path for text inside a layout (`up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0`). The original is `en`, the translation is `ua`, and `ru` is the read-only reference column (the project's reference path is the same `src` folder). `_all_langs.json` is not a block: it holds build overrides per language slot. A save writes into the file on disk only the `ua` values that differ from it; every other byte stays the same, so a file saved without a change is the same file. The width column shows each line in pixels of the 3DS system font, measured as the mod repo's own validator (`validate.py` in its tools folder) measures it (the scale tags `{t:1.0:XXXX}` count). A string is a width problem when it is wider than the mod's own budget: for a message label the widest official localisation of that label, for a layout pane the widest line of the other languages in that pane (the same check as the mod's validator; about two thirds of the strings have a budget). A string without a budget shows its width without a limit. **Preview.** In place of the BFN preview, the selected string is drawn where the console draws it when its text is in a layout: the layout is read from the repo_manual folder, its text pane is set to the string's text, and the pane is outlined in orange. This is done for the layout links built by `scripts/build_system_3ds_layouts.py` (`plugins/system_3ds/layout_links.json`): a label named by the user data of a text pane (the browser, Miiverse, Miiverse posting and game notes parts) and the startup line of System Settings. The status line says the pane is in place and that the backdrop is a placeholder, not the console's; a string that does not draw in its layout says so and shows the box. Other strings are drawn as a budget box: the console's system font, at the font's advances, in a box as wide as the width budget and as many lines high as the line budget (the most lines of any official localisation of the label). A line wider than the budget keeps its full ink, with a red rule over it and a grey edge at the budget; lines past the line budget sit under a red band. The status line gives the widest line against the budget, the line count, and any character the font has no glyph for. The font, widths and layouts come from the repo_manual folder of the manual preview; **Choose folder...** sets it. **Build and export.** Build mod, Export mod and Run in emulator use the mod repo's own Makefile: `build-ru` (the Russian slot, folder `dist`) and `build-en` (the English slot, folder `dist_en`). Picoripi copies the Makefile, `tools`, `assets` and `src` into a temporary folder inside the build's folder, and links `work` to the repo's `work` folder; the repo itself is not written. The build needs GNU make on PATH (`scoop install make`) and a `work` folder with every title the build reads; a title with no dump stops it (the Makefile's `UA_SKIP_TITLES` lists titles to leave out). The make output is in `build.log` beside the result. A save stops with a message that names a file changed on disk since Picoripi read or wrote it: reopen the project, then save. Run in emulator starts the command with the built folder; a Luma folder is not a layout an emulator loads by itself, so that command must perform the install step.
- `hard_corps_uprising` — Hard Corps: Uprising (Xbox 360 XBLA, PC port): a texture-first project with no text blocks. The game pictures (`Gui\Img`, shared and English screens) and the font `Font\ck_font.bin` as a 16 x 16 glyph grid (ASCII 0x20-0x7E).
- `zelda_ladx_hd` — Link's Awakening DX HD (PC fan remake v1.0.0): the English `Data\Languages\eng.lng` and `dialog_eng.lng`, one block per `KEY VALUE` line. An unedited file saves byte for byte. `2_build.bat` writes `ukr.lng` and `dialog_ukr.lng` (the game lists a language for each `.lng` file, so the exe is not changed). The Font Editor opens the eight SpriteFonts in `Content\Fonts\*.xnb` (dialogue font `smallFont`, menu headers `newHeaderFont`); no font has a Ukrainian letter yet. A letter typed into a free cell adds a glyph, and the character map stays sorted. Tools → Textures lists the UI sheet `Data\ui.png` and the four menu pictures `Content\Menu\*.xnb`. A duplicate key or a changed `[TAG]` stops the build; missing glyphs are listed in `build\glyph_report.txt`.
- `zelda_tww` — Zelda: The Wind Waker (GameCube BMG): `res/Msg/bmgres.arc` of the US or a European disc (`data0`–`data4` are English, German, French, Spanish, Italian). Shares the Twilight Princess machinery; tags, colours and line widths come from the zeldaret/tww decompilation, line width and lines per page follow each message's box type. With the disc's whole `source` folder the project also has the Hylian lines (`bmgresh.arc/zel_01.bmg`, Shift-JIS), the disc-error messages inside `sys/main.dol` and the disc banner (`opening.bnr`, Latin letters only); the Font Editor lists six fonts (message, Hylian, name entry and its copy in the file-select archive, the disc-error font in `main.dol`, the debug-menu font) and the Textures window 154 text textures (BTI, the title subtitle inside two BDL models, the banner). No speakers or window frames yet. The Switch homebrew port SwitchWaker (centollOS) reads the whole disc at every start, so the workspace's `2_build.bat` also lays out `build\switchwaker\switch\switchwaker\` (the translated disc as `GZLE01.iso` next to the release's `switchwaker.nro` and caches) for the SD card; the port checks `main.dol` against the decompilation's hash, so only `files\` edits reach it, not the disc-error strings inside `main.dol`. In the Project Manager, **Build** makes the **Disc image (ISO)** (the translated `main.dol` included) or the **BlueWake disc (original main.dol)** from the project's source and translation folders, with no original image needed; **Run in emulator** uses the command set for the GameCube or the BlueWake platform. The Windows static recompilation BlueWake (chrissotraidis/bluewake, release zip, USA `GZLE01` disc) uses the same disc and the same `main.dol` rule: its DLL holds the code translated from the original `main.dol` and modules, and it reads messages, fonts and textures from the disc at run time, so `3_run_bluewake.bat` starts it with that `GZLE01.iso`; `UA TEST` in the title texture and in a message, and an edited message font and name-entry font, showed in its own frame capture. BlueWake checks the disc before it starts: the header id `GZLE01`, the GameCube magic and the `main.dol` SHA-1 of revision 0. Picoripi's BlueWake target builds only from a source `main.dol` that matches that SHA-1 and stops with a message otherwise. For **Run in emulator**, set the BlueWake platform command to `"<BlueWake folder>\BlueWake.exe" --disc {path}` (BlueWake takes the disc from `--disc`); Picoripi starts the program in its own folder, as `3_run_bluewake.bat` does with `pushd`. BlueWake reads HD texture packs from `Load\Textures\GZLE01` in its data folder (the `user` folder beside `BlueWake.exe` when `portable.txt` is there, else `%APPDATA%\BlueWake`); Picoripi does not write that folder yet. The Windows fork WindowWaker (MaskeZenY, a native port compiled from the decompilation, release zip) takes the same disc: it checks only the disc id and version, never `main.dol` or the modules, and reads messages, fonts and textures from the disc, so `3_run_windowwaker.bat` starts it with that `GZLE01.iso`
- `super_mario_galaxy` — Super Mario Galaxy and Super Mario Galaxy 2, one project for every version: Wii (USA, RMGE01 / SB4E01 rev 0, ISO or RVZ), Switch (010099C022B96000 / 0100FD8022DAA000, NSP or NSZ) and, for the first game, the Nebula PC recompilation. Add the Wii disc and the Switch game to the wizard; it unpacks the English message archives and fonts of both into `unpacked\versions` and writes one document per message archive (`MessageData\<archive>.smgmsg`: Galaxy has `Message` and the Switch `System`, Galaxy 2 one per zone). Each row is one message label; the label shows in the context panel, and a row that only one version has is still a row. A label the Wii and the Switch word differently has two rows, one per version, flagged "Switch translation; Wii English differs": translate the Wii row for the Wii and Nebula (until then they show the Wii English). Tags show the Wii bytes on every version (`{escape:3:0000}` in Galaxy, `{tag:3:0:0000}` in Galaxy 2); the build writes each version's own byte order and Switch button pictures. Reference columns: every other language of both versions (set the reference path to the `unpacked` folder; the wizard project has it). Build targets: **Wii: Riivolution patch and Dolphin launcher** (`riivolution\<mod>.xml`, the changed archives, and a Dolphin `<mod>.json` that boots the disc with the patch), **Nebula (PC): disc mod manifest** (Galaxy only; `README.txt` says how: copy `sys\fst.bin` over Nebula's `content\sys\fst.bin` and set `GALAXY_DISC_MOD_MANIFEST`), **Switch: Atmosphere LayeredFS mod** (every English slot). Only translated archives are written. An existing translation mod is read in by label with `python -m plugins.super_mario_galaxy.import_mod <unpacked> <translation> <mod zip or folder>`; its archives become the Switch base (they carry the game update's labels) and its `Font.arc` goes with them. The import also copies the mod's Cyrillic letters from its Switch fonts into the Wii fonts (scaled, nothing drawn) and stores the text as proper Ukrainian (і, ї, є, ґ); each build writes a letter its font lacks the way the mod did. The Wii fonts (`LayoutData\Font.arc`: message, menu, cinema, number and button fonts) open in the Font Editor and save byte for byte (DECISIONS D39).
- `super_mario_sunshine` — Super Mario Sunshine (GameCube, USA, GMSE01 Rev 0): the BMG message files inside the disc's `.szs` archives (`files\data\scene\*.szs/map/message.bmg`, `option.szs`, `guide.szs`), read with the Twilight Princess rules; the source is the whole disc, unpacked from the owner's image. Build targets: **GameCube disc image** writes a new ISO next to the original (the original is never changed; the saved files and the four retail `main.dol` words of the speech-balloon fix are written, the disc size and file layout stay the same) and **PC and Switch port pack** writes `mods\uk\files\...` for the ports (`mod = uk`, a README is inside). A changed message attribute (INF1) is refused; the text may change. The executable's English text (11 strings: the progressive-scan question, Yes, No, the card title, the English save comment, the disc-error lines) is one editable member, `main_strings.dolstr`, each text in its own room; a text that does not fit is refused. Type Ukrainian as it is: the plugin's code map (`translation_map.json`, copied into the project) puts each Ukrainian letter and the apostrophe ʼ on a one-byte code the game's text does not use; a character with no code (a Russian letter, Japanese, or a Latin-1 letter whose code a Ukrainian letter took) stops the save with the character and the message number, and nothing is written as `?`. The system font (balloons, menus; `nintendo.szs/font/standard_fontex.bfn`) and the subtitle font (`subtitle.szs/font/demo_font.bfn`) open in the Font Editor; their cells for the Ukrainian letters still hold the Latin-1 letters until you draw the Cyrillic ones (see DECISIONS D35). Reference languages: in **Settings → Project → File Paths → Reference Translation / ROM Path** pick the European disc (GMSP01, an ISO or RVZ) with **Select Game Disc Image (ISO, RVZ)...**. Picoripi copies its message files into the project folder `reference_eu` in the background (about a minute) and then shows English (EU), French, German, Spanish and Italian next to each US message, read only. You can also pick an existing `reference_eu` folder. Files with no European copy (the four Japanese `dolpic1.bmg`, `title.szs/marisun_stage.bmg`, the executable's text) show no reference. Not done yet: the two progressive-scan confirmations with escape codes.
- `zelda_tingle` — Zelda: The Wind Waker, Tingle Tuner (the text a linked Game Boy Advance shows). **Source:** the disc's `files\res\Gba` folder (`msg_LZ.bin`, USA; `msg_LZ0`–`4` of a European disc: English, German, French, Spanish, Italian); **Translation:** the same folder under `translation`. One block of 1,086 messages with readable codes (`{color:2}`, `{wait:30}`, `{icon:1}`, `{choice2:0}`, `{anim:13}`…); the GBA draws every letter 6 px wide and breaks a line itself after 16 letters, 6 lines a page, so the width check is 96 px. Saving packs the file again (GBA LZ77) and refuses a text bigger than the GBA keeps room for (USA: 67,584 bytes unpacked, about 3 % more than the English); an unchanged file stays byte for byte. `client_u.bin` opens as a second block with the GBA program's own two lines ("Calling...", the no-link screen), changed in place. The Font Editor opens the GBA font inside `client_u.bin` (format `gba_tiles`): Ukrainian letters have their own codes (look-alikes share the Latin glyphs). The Textures window lists the client's sprites ("Please wait..."), screen tiles and help-screen text (format `gba`; an edit that no longer packs into the program's room is refused). Checked in Dolphin with its built-in GBA (`WW_UA\3_run_tingle.bat`)
- `skies_of_arcadia` — Skies of Arcadia Legends (GameCube, USA GEAE8P). **Source:** the wizard's unpacked `field\*.sct` scripts (decoded); each text segment of a script is one editor string. **Budget:** a script's text may not grow in total. A changed line takes its encoded length, padded with spaces in steps of 4 bytes. A script over its budget flags every changed line with "Byte budget exceeded"; the problem tooltip gives the bytes used, the budget and the bytes over. Shorten the line, or shorten another line of the same script. A save keeps the typed text. **Build** refuses such a script and names its lines; no disc is written for it.
- `skies_of_arcadia_dc` — Skies of Arcadia (Dreamcast, USA MK-51052, region U): the same budget and build rules for the disc's `FIELD\*.SCT` scripts (little endian). **Build** writes the translated GD-ROM set (cue sheet and tracks).
- `castlevania_dxc` — Castlevania: The Dracula X Chronicles (PSP, English ULKS-46155). **Source:** the
  workspace's `source` folder, filled by `1_unpack.bat` from the UMD image; **Translation:** `translation`.
  Text: the remake's English dialogue (`remake\text\std00.txt`–`std07.txt`, one message per line, `\n` on
  screen is a new line in the editor), the program's English save-data strings (`remake\program\BOOT.BIN`,
  each in its own room) and the Symphony of the Night strings in the PSP overlays (`sotn\PSPBIN\*.bin`: menus,
  item / enemy / spell names, descriptions, stage dialogue, the endings; found by pattern, each string keeps
  its place and room — a longer text is cut with a warning; `{XX}` tags are bytes to keep). 41 files, 1,837
  lines, byte-exact when unedited. Font Editor: the remake dialogue font (`remake\font\msgfont.gim`, 16x16
  cells; 66 empty cells already carry the Ukrainian letters' codes from `translation_map.json`) and the SotN
  8x8 font (`sotn\hdbin\f_game.bin.pic`). Textures window: ~200 text pictures — the remake's logo, menus,
  staff roll, stage names, speaker names, movie subtitles (`gim`), SotN title, HUD, game over and file select
  (`raw` PlayStation VRAM blocks), the PC Engine Rondo of Blood's English menus, notices and cutscene
  subtitles and Peke's pictures (`tim2`). `2_build.bat` puts each changed piece into every pack that held the
  same bytes (the font is in 8 event packs), writes the program as a plain-ELF `EBOOT.BIN` when it changed or
  the dialogue uses Ukrainian letters, copies changed SotN strings into their duplicates, and writes a copy of
  the image (`build\Castlevania The Dracula X Chronicles (UA).iso`); `3_run.bat` starts PPSSPP.
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
- `donkey_kong_tropical_freeze` — Donkey Kong Country: Tropical Freeze (Switch, update v131072). **Source:** the workspace's `source` (`text\<package>__<asset>.msbt`: the English USEN message tables of the three packages with text, 6 tables). **Translation:** `translation`, starts with the Ukrainian USEN tables of the UKR mod. `2_build.bat` writes the changed tables into copies of the three packages (big-endian Retro RFRM PACK). Fonts (the Scaleform GFX library) and textures are not opened yet.
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
- `spore_hero` — Spore Hero (Wii, Europe). **Source:** the workspace's `source` (`1_unpack.bat` makes a plain
  ISO from the RVZ once and puts there, at the disc paths, the English text
  `game\localization\localization\ENG_US.rpk` (the EA package decompressed), `sys\main.dol`, the three game
  fonts `Game.rpk\*.gfn`, the HOME Menu messages `Game.rpk\home*.csv` and every UI texture of the packages as
  `<package>.rpk\<name>.gsh` / `.lsi`); **Translation:** `translation`. The project shows the 2,285 English
  strings (menus, quests, dialogue, creature and part names, credits headings, save and disc messages) in the
  order they were written, a hundred to a block; `&` breaks the line, `<c>…</c>` colours, `[PLAYER_NAME]` is the
  creature's name, `\[A]`-style codes are icons. A character the text has no byte for gets a free byte and the
  game's character table is updated on save, so Ukrainian letters can be typed; the fonts must have the glyphs.
  A letter drawn over an unused glyph with the Font Editor's translation map is saved as that glyph's character. `main.dol` holds the
  early disc and Wii memory messages (each within its own bytes). The Font Editor opens the three fonts (`fntg`)
  and the HOME Menu font; the Textures window lists 2,126 UI textures (`shpg`, the title logo of every language
  included). `2_build.bat` packs the changes back into the packages (the same texture in every zone),
  compresses them again and writes them into the disc image.
- `rabbids_party` — Raving Rabbids: Party Collection (Wii, Europe): a menu and three games on one disc.
  **Source:** the workspace's `source` (`1_unpack.bat` makes a plain ISO from the RVZ once and reads every file
  straight from it: the menu's `files\*.dol`, pictures `files\*.tpl`, HOME Menu and banner; Rabbids 1 and 2's
  English text `rrr1.bf\text_english.jtxt` / `rrr2.bf\...`, fonts `fonts\*.jfnt` and menu textures
  `textures\<world>\*.jtex`; TV Party's `rrr3_bin_wii.bf\TextPackages.bin`, Flash font movies `flash\*.gfx` and
  interface textures `textures\*.jtx`); **Translation:** `translation`. The project shows Rabbids 1 and 2 as one
  block per text list (backslash codes such as `\cFF7FFF\` colours and `\p16\a` button icons), TV Party's English
  column a hundred rows to a block (`<font color=…>` rich text), and the menu titles, prompt and disc messages of
  each executable (each within its own bytes). Rabbids 1/2 text is single bytes: a letter the fonts lack is drawn
  over an unused glyph and mapped to it in the Font Editor's translation map (TV Party text uses the map too).
  The Font Editor opens the Jade fonts (`jade`), the menu's Wii archived fonts (`brfna`), TV Party's vector Flash
  fonts (`swf_font`), the Rabbids 2 disc error font and the HOME Menu font; the Textures window lists the menu
  pictures (`tpl`), the Jade menu-world textures (`jade`) and TV Party's interface textures (`jade_jtx`).
  The few captions baked into TV Party's Flash movies (`flash\*.gfx`: "NEXT", "OK", "WARNING!" of the
  minigame screens) are blocks too; a saved caption is encoded through the movie's own font, so it takes only
  the letters that font has. The movies hold no pictures (the menus and logos are vector art).
  `2_build.bat` packs every change back (only the changed LZO blocks again, a grown file at the end of its
  bigfile) and writes it into the disc image.
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
- `ikenie_no_yoru` — Ikenie no Yoru (Wii, Japan) with the English fan translation "Night of the Sacrifice".
  `1_unpack.bat` writes the English patch (Riivolution files) into the Japanese disc and puts into the
  workspace's `source` every message table `package\<package>\<id>.mes` (88 tables, 1,944 messages), the
  layouts with text boxes (`*.brlyt`), the strings of `sys\main.dol` (save title, disc and memory errors,
  default names; each fits its slot) and the HOME Menu `hbm\HomeButton*\*.csv` (the game shows the Japanese
  column); **Translation:** `translation`. Control codes read `{NAME:1}` (the name of girl 1..5), `{PAGE}`,
  `{COLOR:FF0000FF}`, `{SIZE:3F800000}`, `{U0008}`. Lines the English patch left Japanese are in the category
  "Japanese source". A table that several packages share is in `source` once (the block's description names
  the others); `2_build.bat` writes it into each of them. The Font Editor opens the four BRFNT fonts and the
  HOME Menu font; the Textures window lists every TPL (title logo, layouts, banners). The build also fixes
  `main.dol` so the game boots and makes its own save without the patch's save file.
- `pokemon_gen1` — Pokémon Red / Blue and Pokémon Yellow (Game Boy, USA) through the pret decomps pokered and pokeyellow. **Source:** the workspace's `source` (`1_unpack.bat` copies from `port\pokered` / `port\pokeyellow`): every asm file with game text (289 / 295 files: dialogue in `text\`, battle and system text in `data\text\`, Pokédex, names of Pokémon, moves, items, places, trainer classes, menus in `engine\`), every `gfx\*.png` and `constants\charmap.asm` with the Ukrainian letters added (21 capitals and 14 small letters in the free font cells $C0–$DF and $E9–$EB, look-alikes on their Latin tiles; ґ є ж й ї ф ц ч ш щ ю take the English cells 'd 'l 's 't 'v 'r 'm, é, ¥, × and <DOT> by the decision of 2026-10-09, so the English text on those cells must be translated first). One editor string is one text: a line break is `line`/`cont` (a list: `next`), an empty line `para` (Pokédex: `page`), text commands show as `{text_ram wStringBuffer}` and can move; another macro than the expected one shows as `{cont}`. Unchanged texts save back byte for byte. Fonts: `gfx\font\font.png` and `font_extra.png` (format `texture_grid` over the new `png` texture format); 20 picture entries (title logo, version names, copyright, SGB borders, slot machine, diploma, Surfing Pikachu) open in Tools → Textures as `png`. Speakers (the map person's sprite), maps and script lines come from the decomp (`picoripi\context.json`); names seed the glossary. Where the decomp gives no speaker or location, a local GameFAQs transcript in the project's `script` folder fills them in (`plugins/common/gamefaqs_script.py`; the transcript never goes into git). `2_build.bat` lays `source` and `translation` over a copy of the decomp in `build\work` and runs the Makefile steps with rgbds 1.0 (Python ports of the pret `gfx`, `pkmncompress` and `pcm` tools); unedited it gives the original ROMs byte for byte; text that outgrows its bank goes into floating sections; a letter without a font cell stops the build with the file and line. Seen in mGBA: an edited main-menu line, a filled font cell and the inverted title logo. **ROM mode (Red, Blue, Yellow; the UE `.gb` dumps, identified by SHA-1):** the Project Manager's **Game ROM** role takes the `.gb` file. Unpacking writes every text body (dialogue, signs, Pokédex entries) to `text/*.asm` with the decompilation's macro lines, and keeps a copy of the ROM as `rom/base.gb`; no make, rgbasm or other tool is needed. **Patched ROM** writes a `.gb` with the changed bodies: a body that is longer than the original moves to free space and its `text_far` references are rewritten; a body that a pointer table names (Pokédex categories, credits, badge names) moves inside its own bank and its table entries are rewritten, after each entry is checked against the ROM bytes. Every text run of the ROM is a unit (the census: 3,241 of 3,245 runs in Red, 3,244 of 3,245 in Blue, 3,414 of 3,417 in Yellow; the rest are coordinate bytes of the map table and picture data). Text the decompilation builds with macros (the name lists, the default names) comes from the ROM bytes and keeps its size. A field the ROM keeps in place (a name, a list entry, a string no pointer reaches) has a byte budget in `rom\meta.json`: the editor flags **Byte budget exceeded** when the text is longer, and the build refuses it. Several units in one body share its space: each unit has its own budget, the body's text minus the other units' lengths. The header and global checksums are fixed. **Preview:** the message box draws the selected text in the game's font, read from the ROM. The font tiles and the box frame are found by their bytes, and `tools/pokemon_gb_font_facts.py` writes their addresses to the facts. Two rows: `cont` scrolls the box, `para` clears it, and a line that does not fit shows a warning under the box.
- `zelda_lttp` — Zelda: A Link to the Past (SNES) through its PC port snesrev/zelda3. **Source:** the workspace's `source` (`1_unpack.bat` runs the port's own `restool.py` on the USA ROM): `dialogue.txt` (397 messages, the port's `[Name]`, `[Waitkey]`, `[Color 02]` codes; a line break shows before `[2]`, `[3]` and `[Scroll]`, and a break typed without one gets the code of its line), `font.png` (the Ukrainian dialogue font, format `zelda3` in the Font Editor: the English glyphs plus empty cells 95–119 for б–я and 128–148 for Б–Я, 114 cells more free; look-alikes use the Latin glyphs) and `gfx\*.bin` (8 graphics sheets with text — menu labels, item names, GAME OVER, title logo — in Tools → Textures as `snes:2bpp`/`snes:3bpp`); **Translation:** the same files under `translation`. Speakers, conversations and source lines come from the port's C code (`context.json`). `2_build.bat` compiles the translation as the port language `uk` of `build\zelda3\zelda3_assets.dat` with the port's own compiler (English stays as it is; `zelda3.ini` gets `Language = uk`) and builds `zelda3.exe` with Visual Studio Build Tools and SDL2 (one 2-line change to a copy of `messaging.c`: glyphs 128–255 through the escape code 0x86). Seen in the game: an edited intro line, font cells and the title logo.
- `donkey_kong_country` — Donkey Kong Country (DKC1), Diddy's Kong Quest (DKC2) and Dixie Kong's Double Trouble! (DKC3), SNES USA v1.0 through their Switch PC ports. **Source:** the workspace's `source` (`1_unpack.bat` reads `ISO\rom.sfc` and checks its SHA-256): `text.json` — strings read from the ROM in groups; every group is translated the same way. A group that holds a second copy of text is named "other copy" (for example "Other copy, French"). Each string keeps its ROM slot length, so a longer line is refused at build. DKC1 also has two raw 4 bpp graphic sheets. **Translation:** `translation`. `2_build.bat` writes the text into `build\dkc1|dkc2|dkc3\rom.sfc` and prints its SHA-256. The PC ports read the ROM at run time; DKC1 takes the SHA-256 through `DKC1_ALLOW_ROM_SHA256`; DKC2 and DKC3 need a build with that hash in it.
- `donkey_kong_gba` — Donkey Kong Country 3 (GBA, Europe). **Source:** the workspace's `source` (`1_unpack.bat` reads `ISO\*.gba`): `text.json` — the 238 strings that the ROM's name table points to (bear, level, world and map names, page labels). Dialogue, fonts and textures are not opened yet. **Translation:** `translation`. `2_build.bat` writes `build\Donkey Kong Country 3 (UA).gba`; an edited string moves to free space at 0xFE4000 and its pointers change. The text is plain ASCII: a Ukrainian letter is written as UTF-8 bytes until the game has a font cell for it.
- `super_metroid` — Super Metroid (SNES) through its PC port sm_rewrite. **Source:** the workspace's `source` (`1_unpack.bat` reads the USA ROM): `text.json` — every text the game draws from tilemaps in six blocks (message boxes, file select and game over, options, pause map area names, intro, credits; 180 strings). The game has capital letters only and one 8-pixel cell per letter: a string is as wide as its `width`; tiles that are not letters are tags (`[press1]`, `[#304B]`) and stay in place. Ukrainian look-alikes (А, В, Е, І …) use the Latin tile; the other Ukrainian letters have cells only in the message-box font and, on the intro's first screen, in 21 pairs of cells that held the Japanese subtitle art (removed 2026-10-12: those tiles are empty in `source\gfx`; a person draws the letters). The intro story pages have 21 cells of their own in `source\gfx\story_window.bin` (tiles 0x30-0x44 of the story window, loaded from a ROM block that is empty). The Japanese text switch is off in the port and in the ROM: the JAPANESE TEXT row of the options screen is blank in the ROM (it is not in `text.json`), and so is the Japanese picture beside it, and the controller_jp and special_jp layouts are not in `text.json` either. Fonts (Font Editor, `texture_grid` over the raw tile sheets; ten entries: the intro story letters and the big first-screen letters share `intro_font.bin`, the Ukrainian story capitals are on `story_window.bin`, the HUD digits are a separate entry) and 13 text sheets (Textures, `snes:2bpp`/`4bpp`) are in `source\gfx`. `2_build.bat` writes a translated ROM (`build\sm\sm.smc`) and builds `sm.exe`. Context: the source line and function of each item in the port's C code; the intro is Samus's narration.
- `castlevania_cotm` — Castlevania: Circle of the Moon (GBA, USA). **Source:** the workspace's `source` (`1_unpack.bat` reads the ROM, padded to the 8 MiB No-Intro image): `text.json` — the game's one text table in 13 blocks (names, enemies, items, areas, abilities, prologue, story, ability messages, DSS card effects and cards, item descriptions, file and pause menus; 527 strings; control codes as `{02}` / `{1D 44}` tags, `[` `]` are letters of the game), `font\font.bin` (the text font in the Font Editor, format `texture_grid` over GBA tiles: the English letters, the item names pre-drawn for the menus, and 66 empty cells labelled А–я for Ukrainian letters) and `gfx\*.bin` (56 sheets with words — title logo and copyright, Press Start, file and pause menus, DSS card names, mode names, endings, staff roll — in Tools → Textures as GBA 4/8 bpp tiles); **Translation:** the same files under `translation`. `2_build.bat` writes `build\Castlevania - Circle of the Moon (UA).gba`: an unedited translation gives the original ROM byte for byte; longer text, a used Ukrainian cell or a sheet that packs bigger go to the free space after the game data. Seen in mGBA: an edited menu line, a drawn Ukrainian cell, an edited glyph and a recoloured menu sheet.
- `castlevania_belmonts_curse` — Castlevania: Belmont's Curse (Switch, 1.1.0 = v65536). **Source:** the English string tables of the Unity Localization bundle (45 tables, 2 751 strings, `source\message\<table>.json`), the two TextMesh Pro fonts of `fonts-latin` (`source\font\fonts-latin\`, Font Editor `tmp_sdf`), and the 29 interface and room bundles with shown text (`source\ui\<bundle>.json`, 7 628 strings), read from the update's RomFS over the base (sparse). **Translation:** the same files under `translation`; `3_import_swuk.bat` imports the SWUK Ukrainian mod: its tables by table and id, and its font as the translation of the fonts. `2_build.bat` writes a LayeredFS mod (`build\atmosphere\contents\0100BA4026E94000\romfs\...`) with the rebuilt bundles and the catalog's new sizes. Not yet checked on a console; open items in the plugin's OPEN_ITEMS section.
- `pokemon_gsc` — Pokémon Gold, Silver and Crystal (Game Boy Color, USA) through the pret decompilations pokegold and pokecrystal. **Source:** the workspace's `source` (`1_unpack.bat` copies every asm file with text: map dialogue, signs and trainers, Pokédex, phone calls, battle, item and radio text, the names of Pokémon, moves, items and places, menus; 797 files and 10,162 strings in Crystal, 921 and 7,621 in Gold/Silver, which share one project). A block is one asm file; a message shows as text (a line break is the next window line, an empty line a new window or Pokédex page; other commands as `[cont]`, `[text_ram wStringBuffer3]`; charmap codes such as `<PLAYER>` and `#` stay). A save rewrites only the changed messages, so an unedited file stays byte for byte; speakers and conversations come from the map scripts. Fonts (`gfx/font/*.png`, format `texture_grid` over `png`) and pictures with words (title logos, menus; format `png`) open in the Font Editor and Tools → Textures. `2_build.bat` assembles the ROMs with rgbds (an unedited build gives the original SHA-1) and, for Crystal, the PC port suiCune with the same strings, font and pictures. Ukrainian look-alike letters print with the Latin glyphs; 24 lower-case letters have empty font cells to draw. Nintendo Switch: with the port "Alek's Ultimate NX Edition" cloned in `port\alek-nx`, `2_build.bat` also writes the SD-card folder `build\switch\switch\Zelda3` (the same `zelda3_assets.dat`, the language as the port's pack `languages\uk.z3lang`, and the port's NRO built by devkitPro in WSL with the same `messaging.c` change); the port's own menu words are a second file of the project, `nx_ui.txt` (234 words; the port's menu font draws only A-Z, 0-9 and some punctuation, so a word with other letters stays English). Seen in Eden: the edited intro line, a filled upper-case cell and the title logo. **ROM mode (Gold, Silver, Crystal; the USA `.gbc` dumps, identified by SHA-1):** unpacking writes the text bodies to `text/*.asm` and keeps `rom/base.gb`; no make or rgbasm is needed. The census covers 6,645 of 6,651 text runs in Gold, 6,646 of 6,652 in Silver and 8,579 of 8,581 in Crystal 1.0 and 1.1 (the leftovers are one code or pointer byte before a string). Pointer tables and byte budgets work as in Red, Blue and Yellow, and the editor flags **Byte budget exceeded**. The 251 Pokédex entries of each game are units (name, height and weight, text): an entry that grows moves inside its own bank, because the engine takes that bank from the species number. Trainer names inside party records and strings inside menu structures stay in place, each with a byte budget. Ukrainian: the uppercase letters and ґ take the Latin cells D F G J L N Q R S U V W Y Z, Ä Ö Ü and d f g h k (decision of 2026-10-09), so the English text on those cells must be translated first. **Preview:** the message box draws the selected text in the game's font, read from the ROM. The font tiles and the box frame are found by their bytes, and `tools/pokemon_gb_font_facts.py` writes their addresses to the facts. Two rows: `cont` scrolls the box, `para` clears it, and a line that does not fit shows a warning under the box. Build target **Recomp package (Gen2Recomp)** (Gold, Silver, Crystal) writes one folder per dump in `Gen2Recomped\<id>\`: the translated ROM, `recomp.json`, `README_UA.txt` and `set_gen2_gate_UA.py`. The script adds the ROM's SHA-1 to the gate of your own Gen2Recomp checkout (the `sha1Alt` line of its block in `GameVersion.lua`; it keeps a `.bak`). The README says how to run the game with LÖVE 11.5. No port code is written. A changed pret build also holds `set_gen2_gate_UA.py` and the build's `.sym`: the script writes a manifest with the new symbol addresses into your Gen2Recomp checkout (the importer reads the symbol addresses) and adds the ROM's SHA-1 to the gate.
- `metroid_prime_remastered` — Metroid Prime Remastered (Switch, base game). The same formats and rules as
  `metroid_prime4`. **Source:** the workspace's `source` (`text\TEXT_*.msbt`: 27 tables, 3,132 messages,
  named as in Metroid Prime 1, e.g. `TEXT_ScansChozoRuins`; `font\FONT_*.rfont`: Geneva, Deface and the
  title-screen Deface; `texture\<package>\*.txtr`: 771 textures); **Translation:** `translation`. Extra tag
  `{image:TXTR_RStickIdle:1}` (a picture by texture name). `2_build.bat` writes USEN and EUEN and every
  package that holds a changed asset into a LayeredFS mod.
- `zelda_ladx` — Zelda: Link's Awakening DX (Game Boy Color, English v1.0 ROM). **Source:** `1_unpack.bat` takes the ROM from the English ZIP; **Translation:** the same file under `translation`. Four blocks: 688 dialogues (one editor line per 16-character row of the text box, names `DialogNNN`, symbols such as `<flower>` and `<ask>`, unnamed codes as `{XX}`) and the 56 credit rows of 18 characters. A row over its width is refused with its number; dialogues that share one place in the ROM must have the same text. A save fixes the header and global checksums; an unedited file stays byte for byte. The Font Editor opens the 160-cell dialogue font at file 0x3D000 (2 bpp, format `texture_grid` over `raw`); Tools → Textures lists the two title logos (DX and original) and the file and save menu tiles. Reference columns beside the English: Ukrainian GB v0.1 (decoded by a substitution solve, with confidence per letter) and SWUK (matched by words); they are shown, never written into the translation. Not yet: item labels as pictures, and the Ukrainian letters in the font (a reading of the Ukrainian font is a proposal for the translator).
- `zelda_las` — The Legend of Zelda: Link's Awakening (Switch, 2019, base game v1.0.0 only). **Source:** a new project from the base game package (`.nsz` or `.nsp`; the wizard asks for `prod.keys` once). The unpacked `romfs` is the source, and only the MSBT files of `regionUS/USen` are blocks: LAS Recomp runs the game in US English and reads no other slot. The other slots, `regionEU/EUen` too, are reference columns: choose the `unpacked\romfs` folder as the reference folder, and each message shows its text in every other slot, matched by label. **Translation:** `translation`, the same paths. The Ukrainian SWUK mod (written for v1.1.0) comes in with `python -m plugins.zelda_las.swuk <mod.zip> <romfs> <translation>` (close the project first): each message matches by label into `regionUS/USen`, and the report counts matched, kept-English and dropped labels per file. **Font:** the game draws its text with the console's Standard font, which the game files do not hold, so the build needs a TrueType font (`.ttf` with `glyf` outlines; a CFF font crashes the recomp) that has І і Ї ї Є є Ґ ґ, ʼ and □ (U+25A1: the game looks it up at start and crashes when the font has none). Put it in `fonts\` of the project folder, or name a file or folder with `"lasrecomp_font"` in `project_settings.json`. A free choice is DejaVu Sans (`DejaVuSans.ttf`); keep its `LICENSE` beside it. Noto Sans has no □ and does not work. The build refuses a font without these characters and names each file it tried. Build target **LAS Recomp (romfs.bin)** writes `romfs.bin`, the translated files under `romfs\` and the font as `fonts\nintendo_udsg-r_std_003.ttf` (with its `OFL.txt` or `LICENSE`) in the build folder; its README says where to copy them. The version check reads the build id of `exefs\main`; an update package is refused. Tags show raw as `{tag:G:T:hex}`. Checked in LAS Recomp beta_4 with DejaVu Sans: the Ukrainian title screen, file select, difficulty choice and name entry of the SWUK import show, with the L and R button icons, without a NintendoExt font dump (`fonts\nintendo_ext_003.bfttf` in the recomp folder).
- `silent_hill2_switch` — Silent Hill 2 (Switch, Ukrainian). **Build** has the target **sh23ds 3DS port**: it writes `3ds/sh23ds/events/*.msg` (the translated message files) and `3ds/sh23ds/ui/font.bin` and `font.t3x` (the Ukrainian text font, made from the translation's `EE/sh2e/font/font000.tga`). Copy that `3ds` folder over the output of the sh23ds packer. It needs a DC-layout `sh2pc.exe` (the Director's Cut build), and the packer's exe check must be bypassed in your local copy: (1) make a private copy of the sh23ds repository; (2) in the packer's file tools/sh2conv/pack.py, skip the `DC_MD5` comparison in `check()`; (3) run the packer's make_pack.sh script with <game folder> <out> --strip-extras with `SH2EE=0`, the game folder holding the DC-layout `sh2pc.exe` and `data/`; (4) copy this target's `3ds/sh23ds/events` and `ui` over the packer's `3ds/sh23ds`; (5) copy `3ds/sh23ds` to the SD card root.
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
- `zelda_ds` — The Legend of Zelda: Phantom Hourglass and Spirit Tracks (DS, USA; workspaces `Zelda\Phantom Hourglass\DS`
  and `Zelda\Spirit Tracks\DS`). **Source:** the workspace's `source` folder (`1_unpack.bat` takes the BMG messages of the
  English folder from the clean USA ROM, and `staff.bmg` of Spirit Tracks); **Translation:** `translation` (whole BMG files;
  `2_build.bat` rebuilds the `.nds`). **Fonts:** the `Font/*.nftr` files (Phantom Hourglass: 3-bit and 2-bit NFTR;
  Spirit Tracks: LZ10-wrapped NFTR) open in the Font Editor; a redrawn glyph updates its width and spacing unless the
  width was typed by hand. **Pictures:** the LZ10 NARC files with NCGR tiles and their NCLR palettes (menus, title
  and map pictures; Spirit Tracks' Download Play child pictures). Textures window entries are not wired yet.
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
- `mii_3ds` — Tomodachi Life and Miitopia (3DS, Europe; the A Link Between Worlds engine with Tomodachi Life's
  tags). **Source:** `source`; **Translation:** `translation`; `1_unpack.bat` writes each archive as a folder
  of its members and `2_build.bat` rebuilds the archive around the changed ones. Tomodachi Life: 1,038 English
  MSBT in the LZ11 darc archives `romfs\message\<Set>\<Set>_EU_English_LZ.bin` (53,195 messages; `ArcBase` is the
  shown text, `ArcVoice` the same messages as the text-to-speech voice reads them), tags named by the game's
  `Game.msbp` (`{Nickname:...}`, `{Food:0:Name:Singular}`, `{SingularPluralFood:...}`, `{CS_Pause:500}`; `Color`
  is R:G:B:A); the Textures window lists 2,467 BCLIM menu pictures and the title logo. Miitopia: 388 MSBT in
  `romfs\eu\svn_message\EU_English.sarc` (14,979 messages; `LayoutMsg\` are interface labels; the game's own tags
  stay raw `{tag:G:T:hex}`), the Font Editor opens the four BFFNT fonts of `svn_font\EU_English.sarc`, the
  Textures window 1,212 BFLIM layout pictures and the title logo. Both games draw their main text with the
  console's shared font, so messages have no width limit
- `bravely_default` — Bravely Default (3DS, Europe, English set `Common_en`). **Source:** the workspace's `source`
  folder; `1_unpack.bat` writes every `index.fs` + `crowd.fs` pair as a folder of its files:
  `romfs\Common_en\<Table>\crowd.fs\<Name>.btb` (401 BTBF tables, 56,865 strings: event dialogue `.txb`, party
  chat `.spb`, tutorials `.trb`, menus `.mtb`, items, abilities, jobs, monsters, D's Journal, shops, subtitles; one
  block per table, one string per entry of its string table), the game font
  `romfs\Graphics\UI_en\Font\Font\root\font\hikari.bcfnt` and 4,403 English layout pictures
  (`romfs\Graphics\UI_en\**\*.bclim`: the title menu, chapter titles, tutorials). Markup stays as typed:
  `[PCM1]`-style names, `$` and `%ls` values. A table saves byte for byte when unedited and may grow.
  `2_build.bat` packs the changed files back into their `crowd.fs` / darc archives in a Luma `romfs` mod.
- `bravely_default` also opens Bravely Second: End Layer (3DS, USA; workspace `Bravely\Second\3DS`): 1,284 English tables (`Common_en` and the English `Script\Scene` files, 71,219 strings), both fonts (`Graphics\UI\Font\Font` and `FontK`) and 5,073 pictures in `Graphics\UI`. `1_unpack.bat` takes the decrypted `.3ds` image; members packed as deflate are unpacked and packed again. The Bravely Default PC fonts (Unity Font data exported by `zt\bdffhd_pc.py`, Font Editor format `ttf`) and its English pictures (PNG) are in the same lists.
- `kid_icarus` — Kid Icarus: Uprising (3DS, Europe, English set `eu`). **Source:** the workspace's `source`
  folder; `1_unpack.bat` writes the LZ11 darc archives (`.arc`, `.zrc`, nested) as folders: 148 English MSBT
  files (25,833 messages; a member gets `.msbt` added): `eu\0.arc\resident\03.bin.msbt` (menus, guidance,
  weapons, powers, idols), `eu\stage\<stage>.zrc\stage\bin.arc\bin\msg_00.bin.msbt` (in-level dialogue;
  `msg_05` is the English set of the ground sections; the other four languages are left out). Tags:
  `{Size:N}`, `{Color:R:G:B:A}`. The Font Editor opens the two bitmap fonts (`eu\00.arc\resident\04.bin`,
  `fnt.bin` of stage a2800); dialogue uses the console's shared font. The Textures window lists the 985 CGFX files
  (6,367 textures, title logo `menu\000.zrc\...\bind\00.bcres`) that the German folder overrides, so they carry
  text. `2_build.bat` repacks and compresses the archives again into a Luma `romfs` mod.
- `final_fantasy_explorers` — Final Fantasy Explorers (3DS, Europe, English). **Source:** the workspace's
  `source` folder; `1_unpack.bat` decrypts the game and writes its files plain (the game packs every file with
  BLZ and names it by a hash; the unpack finds the names from the program's strings): the two text tables
  `romfs\message\message_en.textres` (6,891 messages) and `message_home_en.textres` (5,285 messages), the CFNT
  fonts `romfs\font\font.bcfnt` and `font_localize.bcfnt`, and the pictures: 347 layout archives `romfs\ui\*.darc`
  (BCLIM), 545 `romfs\gfx\*.cgfx`, the CTPK icons in `romfs\gfx` and `message\messageIcon.tpl` (4,812 pictures;
  13 pixel formats). Control characters in a message show as `{c01}`, `{c05}` and so on. `2_build.bat` packs
  the changed files with BLZ again and writes them under their hash names as a Luma `romfs` mod. All text
  files, fonts and pictures write back byte for byte.
- `metal_gear_solid_3d` — Metal Gear Solid: Snake Eater 3D (3DS, Europe, English). **Source:** the workspace's
  `source` folder. `1_unpack.bat` writes `text\vox.mgssubs`, `movie.mgssubs`, `demo.mgssubs` (JSON: the English
  subtitle lines of the three stream files `vox.dat`, `movie.dat`, `demo.dat` as hex bytes with their timing; 6,878
  lines: radio calls, in-game voices, movies, cutscenes; one block per file) and `text\gcx.mgsgcx` (JSON: the 9,684
  English strings of the scripts `stage\*\scenerio.gcx` and `codec.dat` -- item and weapon help, codec call text,
  profiles, menu messages; each string once, one block per script). A script's strings sit in an encrypted
  resource table (LCG keystream seeded with the table stamp) in all five languages; the English ones are found by
  their words and written back with the other languages' strings giving room, so no file changes size. It also
  opens the 232 `.la2` layout archives (darc) as folders: 43 `font/*.bcfnt` fonts and 1,064 `timg/*.bclim`
  pictures (`romfs\ui\<name>.la2\...`; the `_f _g _i _j _s` language variants are left out), and the 15 layouts
  inside the stage `.hpk` archives (146 pictures: staff roll, epilogue, title cards; zlib entries). Text is ASCII
  with `1F xx` escapes for accented letters (Latin-1 minus 0x7F); the subtitles break lines with `80 7C`, the
  scripts with `0A`; other bytes show as `{xNN}`; a project's `translation_map.json` maps a letter to the glyph that
  draws it. `2_build.bat` puts the changed lines back (a subtitle slot cannot move: when the English text outgrows
  it, the French to Spanish lines of that record lose their text), repacks the changed `.la2` and `.hpk` files and
  writes the whole changed game file into a Luma `romfs` mod (LayeredFS replaces files, not parts of them).
  Strings inside the script byte code and the model textures of the `.hpk` archives are not opened.
- `kingdom_hearts_ddd` — Kingdom Hearts 3D: Dream Drop Distance (3DS, Europe, English). **Source:** the
  workspace's `source` folder; `1_unpack.bat` opens the game's `.rbin` archives (`CRAR`; English, French and
  German files share one name, the language is found from the crc32 of the path) and writes the English
  message files `romfs\message\en\<folder>\bin\ct*.ctd` (69 files, 8,374 messages, UTF-16; button icons and
  colour switches show as `{UE026}`), the six CFNT fonts `romfs\font\*.bcfnt`, and the English pictures:
  126 `.ctt` files (`CTRT`) and 54 `.l2d` layouts with pictures inside (`romfs\menu\en`, the title screen and
  menus), `romfs\font\iconfont.ctt`. `2_build.bat` writes the changed files back into `message.rbin`,
  `menu.rbin` and `font.rbin` (compressed again like the original) as a Luma `romfs` mod. New texture formats
  `ctrt` and `l2d`; all 1,575 `.ctt` and 248 `.l2d` files of the game read and write back byte for byte.
- `castlevania_mof` — Castlevania: Lords of Shadow - Mirror of Fate (3DS, Europe, English). **Source:** the
  workspace's `source` folder; `1_unpack.bat` copies `romfs\system\localization\english.txt` (1,522 messages
  `KEY##text` / `KEY#Speaker#text`: help boxes, menus, cutscene dialogue with its speaker, credits; one block, one
  string per message), the seven `romfs\system\fonts\*.bfont` and the 40 CGFX pictures
  `romfs\gui\textures\*.bctex` (logo, English controls, icons). In the editor `|` is a line break and `@[A]`
  shows as `{A}`. The text is one Windows-1252 byte per character: letters the font has no byte for are written
  as `?` unless the project has a `translation_map.json` (`{"Є": "Æ"}`: the letter is written as the byte of
  that glyph and shown back as the letter). The Font Editor opens the fonts as `mof_font` (editing and moving
  glyph boxes inside the atlas; no room for new codes). `2_build.bat` writes the changed files into a Luma
  `romfs` mod and the new sizes into a copy of `system\files.toc`.
- `paper_mario_ss` — Paper Mario: Sticker Star (3DS, Europe, English set). **Source:** the workspace's `source`
  folder; `1_unpack.bat` copies the 46 `messages\EU_English\*.msbt` files (2,859 messages; dialogue per stage
  `stgW_L`, `global` menus and items, the sticker museum, credits) and unpacks the game's BLZ-packed files under
  their own names: the two CFNT fonts `Font\pop_120px.bcfnz` / `pop_240px.bcfnz` (Font Editor) and the CGFX
  pictures `Graphics\ui\*.bcrez`, `Graphics\shared\ui.bctez`, `Effect\main\EUR_en.bctez` (Textures window) plus
  the 50 language pictures of `Lang\EUR_en.bin` (logo, Press START, battle words) and `NWTexture\EUR_en.bin\lg_welcome`
  as `<archive>\<name>.bcres`. Tags: `{Size:N}`, `{Color:R:G:B:A}`, `{PageBreak}`, `{Icon:mic_a:...}`,
  `{Choice:...}`, `{Variable:item}`, `{Number:0:%d}`, `{Wait:N}`. `2_build.bat` packs the changed files again and
  rebuilds the texture archive and its `_info.bin` into a Luma `romfs` mod. All 1,456 CGFX files of the game read
  and write back byte for byte.
- `ace_attorney_trilogy` — Phoenix Wright: Ace Attorney Trilogy (3DS and Switch). **Source:** `source`; **Translation:** `translation`. 3DS: the 37 English scripts of the resource pack `pack.dat` (`script\sNN.bin`, 37,757 messages), the two game fonts and 12,008 BCH pictures; Switch: the 106 English scripts `GS1|GS2|GS3\scenario\*_u.mdt` (122,343 messages, own character codes). In a message `\n` is a line break, `{page}` waits for a tap, `{wait:N}` pauses, `{xNNN}` is a game character without a letter; a text may be longer or shorter than the original
- `code_of_princess` — Code of Princess (3DS) and Code of Princess EX (Switch). **Source:** `source`; the text is compiled into the executable (`exefs\code.bin` UTF-16, `exefs\main` NSO UTF-32); a string is written in place and may not be longer than the original (`{x08}` ends a message); `FD` fonts and `RTEX` pictures
- `corpse_party` — Corpse Party (3DS; Switch 2021). **Source:** `source`; the 20 `*_scriptlist.MSG` files (128-byte message slots, 8,717 messages; a text may not outgrow its slots) and the quoted lists `itemdatalist`, `deaddatalist`, `endinglist`, `playersettinglist`; on the Switch the same files are TextAssets of `resources.assets` (`text\`)
- `ever_oasis` — Ever Oasis (3DS, Europe, English). **Source:** the workspace's `source` folder;
  `1_unpack.bat` writes `romfs\data\Region_EU\English\main.gmsg` (GMSG v3: 8,515 messages; names, menus, items,
  dialogue; tags `{wait}`, `{clear}`, `{style:..}`, `{cNN:..}`, plural `{c14:..|a|b|c}`), the font
  `main.gzf` (GZFX, 470 glyphs) and 666 CTXB pictures of the GAR v5 archives (title, menus, dungeon names).
  A message may grow; `2_build.bat` rebuilds the GAR archives in a Luma `romfs` mod.
- `code_name_steam` — Code Name: S.T.E.A.M. (3DS, Europe, English). **Source:** the workspace's `source` folder;
  `1_unpack.bat` writes the 76 message files `mess\EU_English` (4,406 lines; the Fire Emblem Awakening message
  format, LZ13), 9 fonts (`.bfnt`, `cbf_std.bcfnt`) and 536 BCH files (938 pictures) of the RASI archive
  `arc\EU_English.arc` and the neutral folders. `2_build.bat` packs the changed files back into a Luma mod.
- `stella_glow` — Stella Glow (3DS, Europe). **Source:** the workspace's `source` folder; `1_unpack.bat` unpacks
  the IECP-packed `.cmp` files: the 18 `param\*.str` tables (4,330 strings, any length), the 1,554
  `event\*.flw` scripts (24,800 dialogue lines; a line cannot be longer than the original yet), 7 `.bffnt` fonts
  and 3,202 BFLIM pictures of the SARC archives (`indicator`, `picture`, `adventure`, `chara`). `2_build.bat`
  compresses the changed archives again into a Luma mod.
- `fantasy_life` — Fantasy Life (3DS, Europe). **Source:** the workspace's `source` folder; `1_unpack.bat`
  writes the LZ11 files of `romfs\_file_archive.bin` by their number in the archive (`05774.l5txt`): 2,527
  English text files (both English sets; 238,614 strings: item, quest and dialogue tables, and rows with string
  pointers for menus; `{c:XXXX.XXXX}` tags), 12 fonts (`.fnt`, Font Editor format `l5_fnt`) and 36 `.ztex`
  pictures; the 354 UI containers `.l5ui` are unpacked too but are not opened as textures until a game check
  passes. A text longer than its place is cut to that place, with a warning in the build log; moving it to the
  end of the file is off, because it hung the game. `2_build.bat` packs the changed files back into `_file_archive.bin` in a Luma `romfs` mod.
- `digimon_redigitize` — Digimon World: Re:Digitize Decode (3DS, Japanese release with the English fan
  translation). **Source:** the workspace's `source` folder; `1_unpack.bat` writes the files of
  `romfs\ARCV0.BIN` (zlib) that hold text, by their path in the archive plus `.btxt`: 177 `KCAP` containers with
  8,861 `BTX` tables (73,374 strings; one block per table; the tables' offsets are stale, the game reads the
  strings in order) and the 1,930 `GMIO` textures plus `.gmio` (RGBA8, RGB8, RGB565, L8). A string may change its
  length (the containers are rebuilt) except in two files with data behind the container. `2_build.bat` packs
  the changed files back into `ARCV0.BIN` (a file that no longer fits its slot goes to the end).
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
- `story_of_seasons_3ds` — Harvest Moon 3D: A New Beginning, Story of Seasons, Story of Seasons: Trio of Towns (one engine: XBB archives of `PAPA` record tables) and Harvest Moon 3D: The Tale of Two Towns (the older DS engine), all 3DS Europe. **Source:** the workspace's `source` (`1_unpack.bat` decrypts the .cia): one `.papa` file per text table of every XBB archive (`romfs\Msg.xbb\*.papa` — dialogue, events, tutorials, menus; `romfs\GameData\*.xbb`, `Chara\AvatarData.xbb` — item, crop, animal, recipe, place, title and avatar names; A New Beginning: 390 files, 47,267 strings; Story of Seasons: the English set `MsgGB.xbb`, 430 files, 42,862 strings; Trio of Towns: `en\Msg.xbb` and the nested `en\DataText.xbb.gz\*.xbb` tables, 844 files, 43,899 strings — the other languages' files are left out), or one `.mes` file per entry of the Tale of Two Towns packs `romfs\mes_data.bin\` and `event_mes_data.bin\` (568 files, 30,716 strings, the English set). A file is one block; which columns of a record table are text is read from the data; markup such as `<MYNAME>` stays text, control characters show as `{0D}`, Tale of Two Towns codes as `{1000}`. Saving rebuilds the table (unchanged fields keep their bytes) and `2_build.bat` packs the tables back into their archives and packs. Fonts: the BCFNT / BFFNT fonts (A New Beginning's `marugothic.bcfnt` and Trio of Towns' `mainfont.bffnt` have Russian Cyrillic, Ґ Є І Ї ґ є і ї missing; Story of Seasons' fonts have none) and the Tale of Two Towns 8x16 cell font in `font_data.bin` (format `cells`; cells 159–224 are reserved for the Ukrainian letters and the text codec writes them). Pictures: the layout `.bclim` / `.bflim` files as folders of their `.arc` archives (darc, or Trio of Towns' gzipped SARC; 3DS BCLIM and BFLIM pictures read upright without a parameter; `params.flip` turns a picture over after its crop, and no plugin sets it), the CTPK logos and icons. Speakers come from the table names (`Talk_ALLEN`). Seen in Azahar: an edited string, a filled glyph and a framed title picture in all four games. Story of Seasons and Trio of Towns are seed-encrypted: `1_unpack.bat` reads the title seed from `_shared\3ds_keys\seeds`.
- `xenoblade_de` — Xenoblade Chronicles: Definitive Edition (Switch, 1.1.1). The Xenoblade 2 engine again, with the `xenoblade_2` rules. **Source:** the workspace's `source` folder (`1_unpack.bat` converts the .nsz files and decrypts base + update; the game keeps every file loose in its romfs, so `source` is the romfs root): the 60 English legacy BDAT tables `bdat\gb\*_ms.bdat` (58,336 text cells), the seven LAFT fonts `menu\font\*.wifnt` (zlib-packed in an `xbc1` block in the game, plain in `source`, packed again by `2_build.bat`) and the layouts with pictures `menu\image\*.wilay` (BC1 / BC3 / BC7 / RGBA8 textures; `menu\image\tutorial_gb` has the English tutorial pictures). **Translation:** `translation`; the mod replaces the loose files.
- `miitopia_nx` — Miitopia (Switch, 1.0.0 + update 1.1.0): the 3DS game's engine again, with the `mii_3ds` text rules. **Source:** the workspace's `source` folder (`1_unpack.bat` converts the .nsz files, decrypts base + update with `prod.keys` and opens the archives as folders): `eu\svn_message\EU_English.sarc\**\*.msbt` and `us\svn_message\US_English.sarc\**\*.msbt` (412 files each; 33,164 strings with both slots), the four BFFNT fonts `FontInfo` / `FontCaption` of both slots (format `bffnt`) and the combined BNTX picture sets of the 169 layout archives `cmn\lyt\**\*.arc.szs\timg\__Combined.bntx` (format `bntx`). **Translation:** `translation`; `2_build.bat` rebuilds each archive around the changed members into a LayeredFS mod.
- `one_piece_uwr` — One Piece: Unlimited World Red (3DS, Europe). **Source:** the workspace's `source` folder (`1_unpack.bat` decrypts the .cia and opens the `.jarc` archives as folders): the Ganbarion `jMSG` tables with an English block — `message_eu\msg_en.jmsg` (9,320 strings), `system.jmsg`, `tutorial.jmsg`, the staff roll, the 288 cutscene and talk subtitle files `event\**\*_en_eu.jarc\_talkconv_msg.bin`, the quest texts and the character voice lines (426 files, 12,250 strings; the other languages of a multi-language file stay untouched); colour commands show as `{c:..}` tags. **Translation:** `translation`; `2_build.bat` appends each changed member to its archive (zlib again like the original) and writes a Luma / Azahar mod. The Font Editor opens the seven `.jfnt` fonts (format `jfnt`, A8 glyph grids) and Tools → Textures the 7,706 `.jtex` pictures of `menu_eu` (format `jimg`: ETC1A4 and ETC1). The Switch Deluxe Edition uses the same plugin: `1_unpack.bat` opens the CRI `CPK` archives `rom0.cpk`..`rom4.cpk` as folders (`source\romfs\romN.cpk\...`; `rom4` text and fonts, `rom0` / `rom1` / `rom2` jARC text, `rom3` pictures; pictures are linear RGBA8).
- `luigis_mansion_2` — Luigi's Mansion: Dark Moon (3DS, Europe) and Luigi's Mansion 2 HD (Switch, base game `010048701995E000`). **Source:** the workspace's `source` folder (`1_unpack.bat` decrypts the .cia and opens the `.dict` / `.data` pairs of `art\fe` as folders; the New Project wizard writes the same folder from the .cia, or from the HD base game's `.nsp` / `.nsz` with `prod.keys`, where only the `art\fe` pairs are written and the bundles are `bundle.nlgh`): the NLOC text tables `english.data\strings.nloc`, `ukenglish.data\strings.nloc` and `russian.data\strings.nloc` (1,935 strings each: dialogue, menus, hints; `{p}` breaks, `{tp:..}`, `{clr:..}` tags; default target slot is `russian`, which a console set to Russian loads; `english` / `ukenglish` are alternatives) and the staff roll `credits.credits` (291 text lines of `credits.txt`). **Translation:** `translation`; `2_build.bat` rebuilds each changed pair (the changed member is appended and the dict entry points to it) into a Luma / Azahar mod. The Font Editor opens the five fonts of the three font bundles (Alor 15 and Alor Narrow, DFGKyoGeki 18 Russian and Japanese, NTLG-DB 9; `nlg_font`) and Tools → Textures the 16 front-end texture bundles (`nlg_tex`, ETC1 / ETC1A4). Luigi's Mansion 2 HD (Switch) uses the same plugin: NLOC version 2 tables (2,109 strings per slot), the four `febundle*_res` bundles as `bundle.nlgh` (DXT1 / DXT5 pictures, five fonts with 1024 x 1024 pages).
- `monster_hunter_stories_nx` — Monster Hunter Stories (Switch). **Source:** `1_unpack.bat` opens the English message archive `nativeNXx64\archive\message_R\message_all_eng.arc` as a folder of 685 `.gmd` tables (36,797 strings; `<COL ..>`, `<SPNM ..>`, `<PAGE>`, `<ICON ..>` markup are tags) and copies the English `gui` / `lyt` `.tex` pictures and `.gfd` fonts. **Translation:** `translation`; `2_build.bat` appends each changed table to the archive and writes a LayeredFS mod. The Font Editor opens the two English raster fonts and three icon fonts (`mt_font`), Tools → Textures the Switch `.tex` pictures (`mt_tex`: BC1, BC7, RGBA8).
- `rune_factory_4` — Rune Factory 4 (3DS, USA). **Source:** the workspace's `source` folder (`1_unpack.bat` decrypts the .cia): the game's English `TEXT` tables at their romfs paths — `script\rf3mc.eng` (99,572 dialogue and event lines), `text\*.eng` and `textAndData\text\*.eng` (items, NPCs, quests, skills, menus, map names; 107,220 strings in 25 files, UTF-8, saved byte for byte when unchanged); `＠…＠` variables and the `＋` emphasis mark show as tags. **Translation:** `translation`; `2_build.bat` writes changed files into a Luma / Azahar mod. The game has no font file (it draws with the console's shared font, like Kid Icarus: Uprising); Tools → Textures lists the 495 CGFX `.bctex` pictures of the menus, dialogue window, save slots and staff roll (every one saved byte for byte). **Rune Factory 4 Special (Switch, workspace `RUNE_FACTORY_4_SPECIAL_SWITCH`)** opens with the same plugin: the same 25 English tables (116,980 strings; `rf4TxtShinkonHelp` is new) and 377 BC7 `.bntx` pictures at the same paths.
- `yokai_watch` — Yo-kai Watch (3DS, USA). **Source:** the workspace's `source` folder (every English text
  table `*_en.cfg.bin` at its path inside the game archive `yw1_a.fa`, the fonts `fnt\*.xf`, the English menu
  textures); **Translation:** `translation`. The game's codes show in curly brackets (`{PAGE}` — next page of
  the 2-line message window, `{PNAME01}` — the hero's name, `{CG}…{/C}` — colour); story files exist twice,
  `_m` (Nate) and `_f` (Katie). Japanese leftovers and passwords are not shown; an unedited file stays byte for
  byte. Speakers come from the game's speaker tables in the workspace's `meta` folder. The Font Editor opens
  `ft_nrm` and `ft_sml` (format `xf`, real Ukrainian letters); the Textures window lists 594 English textures
  (`imgc`). The workspace's `2_build.bat` rebuilds `yw1_a.fa` into the LayeredFS mod. The New Project wizard makes
  a Yo-kai Watch 1 project straight from the game too: the 3DS image (USA) or, for Switch, the base game and its
  update (`.nsp` or `.nsz`; the wizard asks for the Switch key file). It writes `unpacked\source` and
  `unpacked\meta` the way `1_unpack.bat` does; a Switch project made this way has the game's Japanese text (the
  English fan mod is not added). Yo-kai Watch 3 (EUR, workspace
  `YOKAI_WATCH_3`) opens with the same plugin: its English text is in `data/txt/ev/en` and the archive
  `yw_lg_en.fa`; the hero of a line comes from its voice clip (`{PV#pv_c001000_23}`: Nate). Its Textures window lists all 5,817
  English textures (title logo, menus, telops, help, captions, signs; loading them takes several minutes).
  Yo-kai Watch 2: Psychic Specters (EUR cartridge, workspace `YOKAI_WATCH_2`) opens with the same plugin: the
  British English tables `*_engb.cfg.bin` (4,737 files, about 104,600 lines; event text in `data/txt/ev/engb`,
  archive `yw2_lg_engb.fa`), Nate or Katie by the `_m` / `_f` file; the Russian fan translation built into that
  image (the workspace's `reference` folder) shows in the **Russian (RU)** reference tab, never as the source.
  The Textures window lists its 2,683 English textures (11 IMGC pixel formats).
  Yo-kai Watch 1 for Switch (Japanese game, workspace `YO_KAI_WATCH_SWITCH`) opens with the same plugin: the
  source text is the English fan mod written into the Japanese tables (`*_ja.cfg.bin`, 2,014 files, about
  48,000 lines, and the 13,800 lines the mod left Japanese, to translate from Japanese: each block that has
  them lists them under its category "Japanese source"; a Shift-JIS table that gets Ukrainian text is saved
  as UTF-8); the Font Editor opens
  `ft_nrm`, `ft_lrg`, `ft_sml` and `dbg` (Switch XF: A8 texture); the Textures window lists the menu,
  title, telop, help and caption images (IMGN, the Switch IMGC: RGBA8, RGBA4, LA8, A8, BC3).
  Width limits: every Yo-kai game has them. They come from the game's English text, measured with the game's own
  main font (`scripts/build_yokai_layouts.py`). So a line too wide for a Switch window is flagged as on the 3DS,
  also when it is a translation from the other platform. A letter the font does not have counts as an average
  letter of that font.
  Yo-kai Watch 4++ and Yo-kai Academy Y for Switch (Japanese games, workspaces `YO_KAI_WATCH_4_SWITCH`,
  `YO_KAI_ACADEMY_Y_SWITCH`) open with the same plugin: the source text is each game's English fan mod in
  the Japanese tables `data/common/text/ja` (2,316 tables, about 38,500 lines; 1,672 tables, about 19,600
  lines — the lines the mods left Japanese, about 550 and 12,300, are shown too, under each block's category
  "Japanese source"); colour codes `[CR1]`…`[C]`
  and pictures `[$gaiji_…]` are tags; the Font Editor opens the G4 fonts (`font_ja`, `font_def`, Academy Y
  also `font_ja2` and a second style; each with its furigana font); the Textures window lists the menu,
  title, telop, help, caption and button pictures (G4TX: RGBA8, BC1, BC3, BC7).
- `layton_3ds` — Professor Layton and the Miracle Mask, Professor Layton and the Azran Legacy and Professor
  Layton vs. Phoenix Wright: Ace Attorney (3DS, EUR; workspaces `LAYTON_MM_3DS`, `LAYTON_AL_3DS`,
  `LAYTON_VSPW_3DS`). **Source:** the workspace's `source` folder: the English XSCR scripts `txt\uk\<folder>\*.xs`
  (one block each; folders 01–09 story, 15 opening subtitles, 30 examine lines, 40 journal, 50 puzzles, 52 puzzle
  help, 80–83 minigames; vs. Phoenix Wright: 04 trials, `cmn` courtroom) and the definitions file
  `res\uk\*_def*.xs` (puzzle titles and types, minigame names, the game title), the fonts `fnt\[eu]\nrm.xf` and
  `sml.xf` and every image pack of the `uk` folders; **Translation:** `translation`. A line keeps the game's
  markup (`<T>`, `<W8>`, `<M4/2/1>`, `{'e}` for é); Japanese leftovers and empty lines are not shown; an
  unedited file stays byte for byte, an edited one is written again (CRLF in vs. Phoenix Wright). The speaker
  comes from the script's Japanese label (the main cast is shown in English). The Font Editor opens both XF
  fonts; the Textures window lists the title screen, menus, chapter titles, help pages, puzzle pictures and
  pop-ups, minigame screens and story pictures (IMGC in `.xi` files and inside `.xa` / `.xp` / `.xy` / `.xc`
  packs). The workspace's `2_build.bat` rebuilds the XFSA (`lt5_uk.fa`, `vs1.fa`) or ARC0 (`lt6_uk.fa`) archives
  into the Luma mod. Layton's Mystery Journey (3DS, EUR; workspace `LAYTON_MJ_3DS`) opens with the same plugin:
  its English scripts are `txt\en\**\*.xs` in `lt6_en.fa` (1,664 files, about 14,900 lines), written in UTF-8 so
  Ukrainian letters are stored as they are (only the fonts lack them); the logo is `menu\en\ctr\title_a.xc`. The Switch
  Deluxe Edition (workspace `LAYTON_MJ_NX`, LayeredFS mod) keeps the same files loose in the RomFS: `txt\en\**\*.xs`,
  the US spelling `_us\txt\en\**`, `res\lt6_def.xs`, the fonts `fnt\[eu]` and `fnt\[na]` (nrm, sml, lrg) and
  the pictures of the `en` and `_us` folders (IMGN / IMGA); edit both the `txt\en` and the `_us` file of a chapter
  (Eden's region USA reads `_us`).
- `layton_ds` — Professor Layton and the Curious Village, Pandora's Box, Lost Future and Spectre's Call
  (Nintendo DS, EUR; workspaces `LAYTON_CV_DS`, `LAYTON_PB_DS`, `LAYTON_LF_DS`, `LAYTON_SC_DS`). **Source:** the
  workspace's `source` folder: the game's own files at their NitroFS paths (Spectre's Call: at their paths in
  the three `lt4_*.fa` archives), still compressed as the game keeps them; one block per file, only files that
  show text. Curious Village: `data\otext\en\*.txt`, the `etext` / `htext` / `itext` / `otext` / `qtext`
  `.pcm` packs and the `data\script\**\*.gds` scripts (puzzle titles and questions, hotel room lines, event
  talk); Pandora's Box: `data_lt2\event|nazo|place|rc\en\*.plz` and the `rc\en\*.dlz` databases; Lost Future:
  `lt3\txt\uk\*.cpck`, `lt3\rc\nazo\uk\*.cdat` (puzzles), `lt3\rc\**\*.cpck` / `.cbin`; Spectre's Call:
  the `GSD1` scripts `txt\uk\**\*.cb` and `res\uk\*.cb`. **Translation:** `translation` (whole files). A line
  keeps the game's markup (`<T>`, `<W>`, `@p`, `<'e>`); an unedited file stays byte for byte; a longer string is
  written again with the pack's offsets and the `.gds` jumps moved; a fixed-width database field refuses a
  longer string. The Font Editor opens the `NFTR` fonts (Curious Village, Pandora's Box, Lost Future) and the
  Spectre's Call `GFNT` fonts; none has a Ukrainian letter yet (52 Latin letters each). The Textures window
  lists the title, menu, puzzle and map pictures: backgrounds (`.arc` BG), animation atlases (`.arc` / `.arj`),
  Lost Future `.cimg` / `.cani` (`LIMG`) and Spectre's Call `.ci` / `.ca` (`GFSP`: 4-bit, 8-bit, A5I3, A3I5).
  The workspace's `2_build.bat` rebuilds the ROM (NitroFS laid out again, the GFSA archives of Spectre's Call
  patched member by member). The Android HD ports for Switch homebrew (workspaces `LAYTON_CV_HD_NX`, `LAYTON_PB_HD_NX`,
  `LAYTON_LF_HD_NX`; `switch.7z` of the port) use the same plugin: **Source** is the port's `assets` folder at the same
  paths (the English folders `data-en`, `data-EU`, `data-en-EU` and `data`): loose UTF-8 `.txt` / `.lbin` / `.dat`
  files, PNG pictures and the bitmap font `data\font\font.dat` (the Font Editor adds letters: the engine reads UTF-8).
  The build writes the changed files to `build\sd\switch\<dir>\assets` for the SD card; Eden's homebrew launch has no
  process handle, so the loader of these ports stops there. `layton_mr` (Layton Brothers: Mystery Room, workspace
  `LAYTON_MR_NX`) opens the strings of the Unity data files exported by the workspace script (`{"strings": [...]}` per
  data file) and their textures (PNG).
- `eternal_darkness` — Eternal Darkness: Sanity's Requiem (GameCube, USA). **Source:** the workspace's
  `source\game` (`1_unpack.bat` decompresses the disc's `*SK_ASC*` files there): `EBootPak.bin` (menus,
  items, spells, runes, system messages), `EBookPak.bin` (Tome pages, save menu), `EMemcardText.bin`,
  `RmTxt*.cmp` (room texts), `Chars\cin*\cin*.bin` (cinematic subtitles) and `sys\main.dol` (chapter
  titles of the cinematics list, written in place, each in its slot); **Translation:** `translation\game`.
  Each string table with text is one block (about 4,270 strings); control codes show as `{ay}` (colour),
  `{i21}` (button), `{s0.6}` (scale), `{~p}` (the player's character); text is written in cp1251, so
  Ukrainian letters use the free font cells 0x80–0xFF (the build patches the game to read them). The Font
  Editor opens both fonts of `EFonts.tpl` with their widths in `EBootPak.bin` (format `eternal_darkness`);
  **Tools → Textures…** lists the title screen with the logo, menus, credits, Tome, maps and boot screens
  (TPL CMPR, I4, I8; the game stores them upside down). `2_build.bat` compresses the changed files again.
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
- `ff12rw` — Final Fantasy XII: Revenant Wings (Nintendo DS, Europe AXFP; the English set is translated, the
  other four languages stay). **Source:** the workspace's `source` folder, filled by `1_unpack.bat` with the
  English text files `data/**/E/` under their NitroFS paths (menus `.btx`, crafting talk `.btk`, reports, log,
  lore and tutorials `.brt`, airship talks `.hscd`, characters, items and abilities `.bch` / `.bit` / `.bsk`,
  the world map `.bmw`, the opening scroll `.bst`, event dialogue and mission objectives in `.dpk` packs:
  14,398 strings), the fonts `data/FontPack.dpk` and the English pictures; **Translation:** `translation`.
  Text is Windows-1252: `\n` is a line break, `[page]` a new box, `[xNN]` a colour or icon byte; a longer text
  lays its file out again, an unedited file stays byte for byte. The Font Editor lists the four NFTR fonts
  of `FontPack.dpk`; the Textures window lists ~200 tile sheets (title logo, company logos, mission and chapter
  titles, menus, mini maps, tutorials). `2_build.bat` puts every file of `translation` back into the ROM.
- `ffta2` — Final Fantasy Tactics A2: Grimoire of the Rift (Nintendo DS, Europe A6FP; the English set is
  translated). **Source:** the workspace's `source` folder: `1_unpack.bat` takes the five English message packs
  out of `master/pc.bin` as `.a2msg` files (menus, names and descriptions in 55 tables, quests, rumours, notices,
  event dialogue: 33,198 strings), the font `menu/font/UseMoji_image.bin` with `FontWidthTable.bin`, the menu
  pictures `menu/nc_rom/us/nc.a2pak` and the title logo `effect/common/c_all_title_eu.efx`; **Translation:**
  `translation`. Codes are glyphs (ASCII, accented Latin, symbols); `\n` breaks the line, `[page]` and `[end]`
  end a page or text, `[CA:01]`-style tags insert values, icons and choices, `[xNN]` is a glyph without a
  character. The Font Editor lists the font (format `ffta2`); the Textures window lists the title and company
  logos and the auction and world map effects (format `ffta2_efx`) and 11 menu tile sheets. `2_build.bat`
  writes changed members into `pc.bin` (in place when they fit, else at its end) and rebuilds the ROM.
- `rock_n_roll_racing` — Rock N' Roll Racing (SNES, USA). **Source:** `source\text\rrr_text.rrrtext` (223 strings of the
  ROM text table, each with its byte budget) and `source\rom\` (the ROM copy); **Translation:** `translation`. A line
  break is a new line; `[80]`..`[8F]` are picture codes and stay as they are. A translation longer than its budget is
  refused at build time. **Build:** a patched ROM and an IPS patch (header checksum fixed). Not yet: the font.
- `ffta_gba` — Final Fantasy Tactics Advance (Game Boy Advance, USA AFXE). **Source:** the project's `unpacked`
  folder: New Project (Project Manager) recognises the ROM and writes `rom/` (the copy the build starts from),
  `text/*.fftatext` (menus, items, names, missions and notices, story events and battles: 9,543 strings in 104
  blocks: 10 pointer tables and 94 offset tables) and `fonts/font.bin` (the 16x16 font with its widths); **Translation:** `translation`. A space and a
  line break are plain text; `[wait]`, `[next]`, `[clear]` wait, turn the page and clear the box (after a
  `[clear]` inside a text the editor starts a new line); `[crn:XX]` and
  `[var:XX]` insert a name or a number; `[choice:XX]` starts a two-way choice whose answers end with `[sep]`;
  `[sp:XX]` is a space of XX pixels; `[xXXXX]` is a character without a letter in the editor. Ukrainian letters
  use the kana cells of the font: the Font Editor (format `cells`) shows them under their Ukrainian names, and
  the translator draws them there. A character with no code is refused by name when you save. The build target
  **Translated GBA ROM** writes edited strings and the edited font; a changed string or table goes after the
  end of the ROM and its pointers follow it.
- `infinite_space` — Infinite Space (Nintendo DS, Europe C6CP). **Source:** the workspace's `source` folder,
  filled by `1_unpack.bat` with the NitroFS files: the script `data/Event/SpaceShip.scx` (every line of the
  game's text: dialogue, menus and choices of the script, tutorials; the editor lists the ~5,000 lines that
  hold letters, 100 a block), the screens `data/Cg/Bgd/*.bgd`, the menu sprites `data/Cg/Obd/*.obd` and the
  textures with text `data/Cg/Texture/*.tex`; **Translation:** `translation`. Letters are the game's 78-glyph
  list (`0-9 A-Z a-z ! ? - ・ = / . , ( ) “ ” : ’ &`); a line break shows as a new line, `[\r]` opens the next
  window, `[\c,1,12]`-style commands (speaker, portrait, events) stay as they are; a longer line lays the
  script out again. The Font Editor lists the 8x16 dialogue font (format `is_obd`, `Obd/T000OBJ.obd`: no room
  for more glyphs); the Textures window lists the title logo (`Bgd/title.bgd`, `Bgd/TITLE000BG1.bgd`), every
  screen and sprite sheet (format `tiles`) and the opening text and ship plans (format `is_tex`).
  `2_build.bat` puts every file of `translation` back into the ROM.
- `dq9` — Dragon Quest IX: Sentinels of the Starry Skies (Nintendo DS, Europe YDQP; the English set is
  translated, the French, German, Spanish and Italian sets stay). **Source:** the workspace's `source`
  folder, filled by `1_unpack.bat` with the GPC2 archives (`*.gp2`) that hold English members: NPC talk,
  signs, quests and story events (`*_en.bin`), menus, items, monsters, spells, skills and their
  descriptions (`*_en.nat`) -- 60,222 strings in 1,537 files -- plus the credits, the name keyboards, the
  fonts `data/pack_lv5/fi_*.bin` + `fd_*.bin` and the picture packs; **Translation:** `translation`. A file
  is one archive, a block one English member; the game's `<tags>` show as `{tags}` (`{PAGE}` a new box,
  `{1}` the apostrophe, `{,}` the comma), the game's `\n` as a line break. A longer string lays its member
  out again and repacks the archive; an unedited archive stays byte for byte. The Font Editor lists both
  fonts (format `dq9`); a letter typed into one of the 66 empty cells becomes a new glyph and the game draws
  it where the text has that letter (UTF-8). The Textures window lists the title logo (`menu/bg_up*.gp2`),
  the menus and the album pages (formats `tiles` and `dq9_spr`). `2_build.bat` puts every file of
  `translation` back into the ROM.
- `twewy` — The World Ends with You (Nintendo DS, Europe AWLP). **Source:** the workspace's `source` folder,
  filled by `1_unpack.bat` with every game file but the sound under its NitroFS path; the text is
  `Apl_Fuk/mestxt.mes` (the game's `mestxt.bin`: all 25,233 messages, 500 a block); **Translation:**
  `translation`. Codes are glyphs of the text font (ASCII, accented Latin and symbols show as characters,
  other glyphs as `[g:XXX]`); tags `[color:1]`…`[color:4]`, `[/color]`, `[num]`, `[value]`, `[name]`; an
  unedited file stays byte for byte. The Font Editor lists the four fonts of `Apl_Fuk/Grp_Font.bin` (format
  `twewy`: 10x10 text font, 10x12, two 16x16); the Textures window lists ~300 tile sheets of menus, titles,
  credits, location titles and copyright screens in the game's `pack` archives (sprites shown as a plain tile
  sheet). `2_build.bat` makes the message index `mestable.bin` again and rebuilds the ROM.
- `castlevania_gba` — Castlevania: Harmony of Dissonance (GBA, Europe ACHP) and Aria of Sorrow (GBA, USA A2CE),
  one plugin for both. **Source:** the workspace's `source` folder, filled by `1_unpack.bat` from the ROM (the
  trimmed dump in `ISO` plus its cut padding, checked against No-Intro): `text/strings.cvtext` (every English
  string as raw bytes: HoD 683, AoS 965 -- the French and German text of the AoS ROM stays as it is), shown in
  blocks by kind (story, item, enemy and soul names and descriptions, menus, sound mode, area names);
  **Translation:** `translation`. Tags: `[face:XX]` portrait, `[name:XX]` speaker, `[insert:XXXX]` a name the
  game fills in, `[page]` / `[box]` / `[wait]` / `[clear]` / `[scroll]` text-box steps, `[A]` `[B]` `[L]` `[R]`
  `[UP]` `[DOWN]` buttons, `[num]`, `[xHH]` a code with no letter; an unedited string keeps its bytes. Ukrainian
  letters: AoS has none, each of the 66 gets a blank font cell; HoD has the Russian letters, Ґ Є І Ї ґ є і ї get
  blank cells (draw them in the Font Editor). The Font Editor lists two 1-bit fonts per game (format `cv_gba`:
  8x12 text font, 8x8 small font; AoS widths are editable); the Textures window lists the text pictures (title
  logo, menus, area names, staff roll; unpacked 4bpp tiles, shown in grey). `2_build.bat` writes a longer
  string or picture into the free end of the 8 MB ROM and moves its pointer.
- `castlevania_ds` — Castlevania: Dawn of Sorrow (ACVE), Portrait of Ruin (ACBE) and Order of Ecclesia (YR9E),
  Nintendo DS, USA; one plugin for the three. **Source:** the workspace's `source` folder, filled by
  `1_unpack.bat` under a folder per game (`dos`, `por`, `ooe`): `<game>/strings.cvdstext` (the game's whole
  string table as raw bytes: 1,291 / 1,865 / 1,893 strings), shown in blocks by kind (character, item, enemy,
  soul / skill names and descriptions, system, menus, quests, music and area names, library or term list,
  events = dialogue); **Translation:** `translation`. Tags: `[name:XX]` speaker, `[face:XX]` portrait, `[wait]`,
  `[box]` (new text box) and `[same]` (new page, same speaker) — both shown with a line break after them —,
  `[next]`, `[choice]`, `[endchoice:XXXX]`, `[color:XX]`, `[cmd:XX]`, buttons `[L]` `[R]` `[A]` `[B]` `[X]` `[Y]`
  `[LEFT]` `[RIGHT]` `[UP]` `[DOWN]`, `[xHH]` a code with no letter; `[` `]` of the text show as `［` `］`. An
  unedited string keeps its bytes. Ukrainian letters: the fonts have none; each of the 66 takes the cell of an
  accented letter the English text never uses (draw them in the Font Editor; Order of Ecclesia's French text
  uses those cells too). The Font Editor lists two fonts per game (format `cv_nds`: 16x12 text font, 8x8 small
  font, fixed advance); the Textures window lists the title logo, menus, area names, credits and game-over
  pictures (OoE: both the `_e` and `_u` English sets). `2_build.bat` lays all strings out again when one
  changed (as DSVEdit does); what does not fit goes into a new overlay that the patched game loads at start.
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
  The preview draws the message window at the game's place, in the game font, with the portrait of the `{FA:xx}` tag from the `LUNADATA\FACE_nnn.TIZ` files (`1_unpack.bat` copies them; they are not in older workspaces). Portrait colours come from the table `plugins/lunar_sssc/face_palettes.json`; a project's `portrait_colours.json` overrides it; `PEO.PAL` covers indices with no colour. The window's band is a translucent dark strip drawn over a neutral grey backdrop, because the game's scene is not drawn. The speaker name is shown only for numbers checked on screen (`{FA:6E}` is Nall).
  The opening script (`TEXT001.DAT`) also has a block **Voice subtitles**: one line per speech segment of the opening monologue (8 lines; an empty line shows nothing). Each line appears in a text window for its segment while the voice plays. The lines go after the script op that starts the clip, so `2_build.bat` builds them with the script.
  Portrait colours table: to rebuild it, run `python scripts/lunar_portrait_colours.py <LUNADATA folder> <sheet.png> plugins/lunar_sssc/face_palettes.json`. A `portrait_colours.json` in the project folder, if present, overrides the table.
- `lunar_ebc` — Lunar 2: Eternal Blue Complete (PlayStation, USA, 3 discs). **Source:** the workspace's
  `source` folder (`1_unpack.bat`, files of `DATA.PAK`): `DATA\EVENT` (event scripts), `DATA\PEOPLE` (what
  people on a map say), `DATA\SYSTEM\2499\05-12.bin` (items, spells, menus, memory-card messages),
  `DATA\BATTLE` (monster names, 21 letters), `DATA\MAP` (place names, fixed length),
  `DATA\SYSTEM\0003.bin`. Font Editor: the text font `DATA\SYSTEM\2499\18_font.bin` (94 glyphs and their
  widths). Textures: title screen and logos, battle status page, card game words, 50 full-screen pictures.
  Tags: `\n` next line, `{2000}` new page, `{3007}` the 'more' arrow, `{B2C9}` speaker, `{XXXX}` other codes.
  A longer text moves the messages; a file that outgrows its place goes to the end of the disc.
- `paper_mario_64` — Paper Mario (N64, USA 1.0) in the PC port PaperBoat 1.0.2. **Source:** the workspace's
  `source\text\paper_mario_64_messages.txt` (one line per message, 8,009: `MSG_<name>` and the editor text, codes in
  brackets such as `[@F0]`); the message font `source\font\charset_standard.bin` (a texture grid of 166 16x16
  CI4 glyphs) and the logo pictures `source\texture\LOGO_*.bin` (RGBA16). `2_build.bat` writes the changed
  messages, glyphs and logos into the port's mod `build\mods\zz_Picoripi_UA.o2r`; the ROM is not changed.
  The charset has no Ukrainian letters yet.
- `conker_bfd` — Conker's Bad Fur Day (N64, USA 1.0), plugin in progress. **Source:** the workspace's
  `source\text\bank_1A\` (the catapult instruction book) and `source\text\bank_1C\` (menu, pause menu, chapter
  names, credits): one JSON per table, text as plain characters with `[@hh]` tags for inline codes; the font
  `source\font\glyph_00.pgm` to `glyph_94.pgm` with `glyphs.json` and `glyph_map.json`; the voice streams
  `source\voice\streams\NNNN.mp3` with the index `source\voice\streams.json`. Build targets: `rom` writes a
  patched ROM; `bps` writes a BPS patch from the US ROM. The text can grow: when a table gets longer, banks 0x1A to
  0x1D move to the free end of the ROM, and the ROM keeps its size. The text box does not grow yet, and the in-game
  preview is not verified yet. **Reference:** pick a finished translation ROM (`.z64`) as the reference; it shows
  as the "Spanish (ES, fan)" column. Patch files (xdelta, BPS) are not applied: give the patched ROM. A table is
  matched by position only when its string count equals the US count; other tables are skipped.
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
- `animal_crossing_3ds` — Animal Crossing: New Leaf - Welcome amiibo and Animal Crossing: Happy Home Designer
  (3DS, EUR), one plugin for both. **Source:** the workspace's `source` (`1_unpack.bat`: game + update):
  `romfs\Script\**\*.umsbt` (New Leaf 3,299 files, 87,425 messages; Happy Home Designer 507 files, 57,737
  messages; a UMSBT holds one MSBT per language — English, Spanish, French, Italian, German — and opens as its
  English one; saving writes the other languages back untouched), `romfs\Layout\Swkbd\message\EU_English\swkbd.msbt`
  (the keyboard), `romfs\Font\*.bcfnt` / `*.bffnt` (3DS fonts) and the layout archives as folders of their
  pictures (`romfs\Layout\<x>\<y>.arc\timg\*.bclim` darc in New Leaf, `*.bflim` SARC in Happy Home Designer;
  the title logos are letters in `Layout\Title`). Every control code has a readable name: New Leaf's names come
  from MSBT Editor's `ACNL.gcf` (`{color:NPC}`, `{pageBreak}`, `{delay:8}`, `{anim37}`, `{wordInfo:…}`) and
  from what the code does in the text (`{playerName}`, `{catchphrase}`, `{nickname}`, `{waitButton}`,
  `{menu5:0}` with the answers on the next lines, `{random1:…}`); Happy Home Designer has its own catalogue
  (`{delay:8}`, `{anim37}`, `{menu0:0}`). Old names (`{G5_7}`, `{PageBreak}`) still read. The three `*_ASR`
  name tables are one-byte MSBT files (UTF-8 / Latin-1) and open too.
  **Windows.** Each file knows its window: dialogue box 320 px of the game font, 3 lines (the game goes on by
  itself every 3 lines; `{pageBreak}` starts a new box), letters and the bulletin board 257 px × 6 rows,
  system dialogs 256 px, answers 200 px. Widths are measured with the game's own `Garden_msg_size16` (the
  measure breaks exactly where the game breaks); a name tag counts as a typical 8-letter name, `{size}`
  scales. A line that is too wide is shown red (the game breaks it in the middle of a word); Autofix and AI
  translation re-wrap the text with the game's own breaks and never touch answer lines. Problems: changed
  answer count, too many lines in a letter or on the board. The preview draws the window with the game's
  font and textures and pages it as the game does. AI replies must keep every tag (`strict_tags`). The
  workspace build also writes `code.ips`: villagers speak Cyrillic letters (Animalese) with the sound of
  the closest Latin letter.
- `castlevania_sotn_saturn` — Castlevania: Symphony of the Night for the Sega Saturn, in the "Dracula X
  Ultimate" v1.1 English build. **Source:** the workspace's `source` folder, filled by `1_unpack.bat`:
  `text\<FILE>.sotnstext` (1,130 strings of 38 program files: items, relics, spells, enemies, the librarian,
  menus, save screens, area names, room messages, cutscene speaker names), `fonts\MENU_12x12.BIN` (the font
  of the title, data-select and save menus), `fonts\SYSTEM_8x8.BIN` and `fonts\ASCII.FON` (Tools → Font Editor), `dialogue\*.BIN` (the cutscene dialogue is pictures of its
  lines, 20 files), `title\TITLE_LOGO.BIN` (the title screen as one 320x256 picture: logo, copyright, PRESS
  START BUTTON) and `title\TITLE_MENUS.BIN` (the eight menu screens with their gothic headings — player
  select, data select, name entry, data copy and delete, the main menu — one picture each; Tools →
  Textures). A redrawn piece of a screen reuses an equal 8x8 cell, redraws a cell only that place uses, or
  takes a free cell; the build packs the cells into `TITLE.MAP` again and moves the game's chunk table. A
  longer string moves its neighbours and their pointers; a speaker name keeps its letter count. Keep the
  first cell of a dialogue picture empty: the game fills the dialogue box with it.
- `pokemon_nx` — Pokémon Sword/Shield (with both DLC) and Pokémon Legends: Arceus (Switch). **Source:** the
  workspace's `source` (`1_unpack.bat`: base + newest update): `bin\message\English\common` and `script`
  `*.dat` (one block per file; the `.tbl` next to it names each line), `bin\font` (`.BFOTF`, `bmp\*.bffnt`)
  and `bin\appli\*\bin\*_eng.arc` (English layout pictures); Legends: Arceus also
  `bin\archive\appli\*_eng.gfpak.d\*.arc` (the battle and HUD layouts of the Oodle packs, packed back by
  `2_build.bat`). Tags (the same as `pokemon_trinity`): `{PAGE}`
  next text box, `{COLOR 0002}` colour, `{VAR 0100 0000}` an inserted name, `M{GENDER 00FF|aster|iss}` word forms
  (their lengths are written again on save), `{CHAR E305}` a button icon.
  The text fonts lack Ґ Є І Ї ґ є і ї: `translation_map.json` writes І і Ї ї as Latin I i Ï ï and Є є Ґ ґ as
  Э э Ъ ъ, whose glyphs are redrawn in the Font Editor. Sword and Shield share one romfs: `2_build.bat` writes
  the mod for both title ids. The Project Manager wizard unpacks Sword / Shield itself: it takes the base game and
  the update (the update's patch is applied) with Picoripi's Switch reader, and gives the same `source` as
  `1_unpack.bat`. Legends: Arceus: the wizard writes its `.gfpak` packs and decodes them into `<pack>.gfpak.d` with the Oodle library. It asks once for the Oodle library file (`oo2core` or `oo2ext` `*_win64.dll`) and remembers its path. The Switch build target writes the changed files as a LayeredFS mod (Sword / Shield: both title ids; Legends: Arceus: a changed pack is stored, not compressed). Default tag aliases (Settings →
  Tag Aliases): `[PAGE]`, `[SCROLL]`, `[POKEMON]`, `[MOVE]`, `[ITEM]`, `[LEVEL]`, `[NAME1]`, colours `[COLOR6]`.
  Dialogue box preview (Sword / Shield): the box is drawn from the game's own layout `bin\appli\msg\bin\msg_00.arc` (two text panes, the window size, the font list of its `fcpx`) with the `.BFOTF` fonts from `bin\font`. The window texture is not drawn yet; a flat box stands in for it. A game line longer than its pane flows into the next pane (word wrap); a word wider than the box is flagged. Legends: Arceus shows its battle box (`bin\archive\appli\battle_menu_eng.gfpak.d\11_msg_sys_00_s.arc`); Scarlet / Violet its sub-window box (`appli\data\msg_sub\msg_sub_body_00.arc`, unpacked now that the wizard takes the `msg_sub` and `msg_btl` archives). Legends: Z-A has three boxes in one switch above the preview: the field box (`msg_00.bflyt` in `msg_body_00.arc`, glyph size not measured), the NPC speech bubble (font `UniversNextPro-Cond.bfotf`, glyphs 29.5 by 29 px, measured on an Eden frame: every ink edge within 1 px) and the lower-left message window (from the layout, no frame yet). The bubble and the window take their facts from `config.json` (`speech_bubble`, `hud_message`); each box is read on a worker thread.
- `pokemon_gen6` — Pokémon X / Y and Omega Ruby / Alpha Sapphire (3DS), one project per pair (X and Y share
  every text, font and picture file; so do Omega Ruby and Alpha Sapphire). **Source:** the workspace's
  `source` (`1_unpack.bat` takes the English members out of the GARC archives): `romfs\a\0\7\4\NNN.dat`
  game text and `romfs\a\0\8\2\NNN.dat` story (X/Y; ORAS `a\0\7\3`, `a\0\8\1`; one block per table,
  named after its content: `080 Species names`, `Story 012`), `romfs\a\0\2\0\NNN.2.bin` name-entry keyboard
  rows (one line, keep the character count), `romfs\a\1\8\5\*.bcfnt` fonts (ORAS `a\1\6\7`) and
  `romfs\a\*\*\*\000.2\timg\*.bclim` English layout pictures (plus the title logos and Press Start of each
  game). Tags are the same as `pokemon_nx`: `{PAGE}`, `{COLOR 0002}`, `{VAR 0100 0000}`,
  `Master Ball{PLURAL 00FE||s}`, `{CHAR E08E}`. The fonts have no Cyrillic: the Font Editor adds letters
  (`min_sheets` leaves room). `2_build.bat` rebuilds the GARCs into a Luma / Azahar mod for every CIA in `ISO\`.
  The wizard unpacks the CIA itself (Picoripi readers, no `zt` step): X gives the same 718 files as the workspace `source` (Y the same files), Omega Ruby 993. **Preview:** the language box (bottom screen) and the in-game dialogue (top screen, the cutscene box) are drawn with the game's own font (X `a\1\8\5`, Omega Ruby `a\1\6\7`), at the measured glyph scale and box, by the shared renderer `plugins/common/message_window.py`; a line wider than the measured box is flagged. The unpack keeps the archives in `source\garc_original\<title id>\`, which the build starts from. The build target **3DS mod (LayeredFS)** writes `titles\<title id>\romfs\...`; a pack member (a DARC inside a GARC member) is rebuilt from its translated files.
- `pokemon_gen7` — Pokémon Sun / Moon and Ultra Sun / Ultra Moon (3DS, decrypted `.3ds` images in `ISO\`). Sun and The message box preview draws the language-screen box with the game font (`romfs/a/0/2/5/000.bffnt`); the other windows are not measured yet.
  Moon share every English file; so do the two Ultra games. The Ultra games read the v1.2 update as an overlay.
  The wizard unpacks the image itself (Picoripi's own readers, no `zt` step): Sun gives the same 4667 files as the workspace `source`, Ultra Sun with its v1.2 update 3189. The unpack also keeps the text, font and picture archives in `source\garc_original\<title id>\` (about 37 MB), which the build starts from. The build target **3DS mod (LayeredFS)** writes `titles\<title id>\romfs\...` with each changed archive; a longer line is accepted.
  **Source:** `romfs\a\0\3\2\NNN.dat` English game text (898 tables in Sun), `romfs\a\0\4\2\NNN.dat` Battle Tree
  text, `romfs\a\0\2\5\NNN.bffnt` fonts, and `romfs\a\*\*\*\NNN.bflim` pictures. The fonts have no Cyrillic: the
  Font Editor adds letters. `2_build.bat` rebuilds the changed GARCs into a Luma / Azahar mod for each title.
- `pokemon_gen5` — Pokémon Black / White and Black 2 / White 2 (Nintendo DS). **Source:** the workspace's `source` (`1_unpack.bat` takes the NARC members out of the ROM): `text/a_0_0_2/NNNN.msg` (menus, names, descriptions, battle) and `text/a_0_0_3/NNNN.msg` (story, scripts), one block per message file; `a/0/2/3` the NARC with the NFTR fonts and `a/*/*/*` the NARCs with NCGR pictures. Tags: `{PAGE}`, `{SCROLL}`, `{VAR 0101 0000}`, `{COLOR 0001}`, `{CHAR E447}`; a line break is a new line. The message box draws with the game's font: NFTR `a/0/2/3` member 0 in a 230 px box. Each glyph's advance and left offset come from row 0 of its cell in the font (the game's widths); the page arrow is measured on Black dialogue frames (`plugins/pokemon_gen4/message_preview.py`). Saving keeps each line's flags and packing; `2_build.bat` writes changed files into their NARCs and lays the ROM out again (a plain NDS image). Build target **Translated DS ROM** writes `<game code>_UA.nds` from the wizard's own copy of the clean image (`source
omase.nds`, made by the unpack) with the edited banks and files put in; no `zt` script runs. A DSi-enhanced dump comes out as a plain NDS image.
- `pokemon_gen4` — Pokémon Diamond / Pearl, Platinum, HeartGold / SoulSilver (Nintendo DS, USA). **Source:** the workspace's `source` (`1_unpack.bat` takes the message banks and the NARCs out of the clean ROM in `ISO\`): `text/<narc>/NNNN.msg`, one block per message bank; only the English text is edited, and an untouched line keeps its bytes. Fonts: the Gen 4 font bins of the font NARCs (`graphic/font.narc` and the others) open in the Font Editor as 16 x 16 glyph grids with 2-bit pixels (`gen4_glyphs`); no new glyphs are added, and an edited glyph keeps the four colour levels. The Font Editor labels each glyph cell with its character from the game's charmap (glyph index = text code - 1); a cell without a character shows its index. Pictures: the NARCs with NCGR members (Textures); a compressed (LZ10) member is decompressed to open and compressed again to save, as a valid stream. `2_build.bat` writes changed banks, fonts and pictures into the ROM and lays it out again. The pret decompilation text (`.gmm` / `.json`) is a second mode; it needs the decompilation's own toolchain for the ROM, and the `ZT_GEN4_MODE=pret` variable (or `zt_mode.txt` in the workspace) selects it in `zt.py`. Build target **Translated DS ROM** writes `<game code>_UA.nds` from the wizard's own copy of the clean image (`source Platinum: the preview draws the message box with the game's own font (Platinum 216 px wide, Diamond / Pearl / HeartGold / SoulSilver 216 px, 2 lines; the table `WINDOWS` in `plugins/pokemon_gen4/message_preview.py` gives the font and width of each game; the widths come from the pret and ctrl-cheeb-del window templates, 27 x 4 tiles); a line wider than the box is flagged, and the game does not wrap lines. The box colours are the game's own: dark ink 81,81,89, grey ink 162,162,170 on 251,251,251 (read from a melonDS frame of the Diamond intro box and the HeartGold dialogue box).
omase.nds`, made by the unpack) with the edited banks and files put in; no `zt` script runs. A DSi-enhanced dump comes out as a plain NDS image.
- `pokemon_bdsp` — Pokémon Brilliant Diamond / Shining Pearl (Switch, Unity), one project for both games. An edited font `font\<name>.json` (its glyph tables) is written back into the font bundle; an unchanged one is not.
  **Source:** the workspace's `source` (`1_unpack.bat`: base + update 1.3.0; the Unity bundles become plain
  files): `message\english_*.bdmsg` (128 tables, 42,946 lines: story, Pokédex of both games, names,
  menus, battle), `font\<bundle>\` (TextMesh Pro SDF fonts: Font Editor format `tmp_sdf`, glyph table +
  atlas; the font files of the dynamic fallback open as `bfotf`) and `texture\...\*.png` (24 English
  pictures: title logos, "Press any button", menu and battle words; Textures window format `png`).
  `2_build.bat` writes every edited file back into its bundle for both games. The Project Manager wizard unpacks the message tables, the fonts and the pictures itself (Picoripi's own
  Unity readers; base + update). The Switch build target writes the edited bundles as a LayeredFS mod (their blocks
  stored, not compressed) and re-measures the word width (`strWidth`) of each edited label with the English fonts.
  An edited picture (`texture\...\*.png`) is encoded in its own format and written into the bundle's stream, at the same
  size; an edited font atlas (`font\<bundle>\<font>.png`) is written into the font bundle. Not yet in Picoripi: the
  glyph tables of the fonts (the `.json` files) are not written back. Tags: `\n` new line,
  `{scroll}` / `{clear}` + new line (wait for the button), `{wait:0.5}`, `{tag:A:G:T…}` a name, number or
  word form the game fills in (argument A; word forms after `|`), TextMesh Pro `<color=…>` stay as they are.
- `dragon_quest_builders` — Dragon Quest Builders and Dragon Quest Builders 2 (Switch). **Source:** the workspace's `source` folder (`1_unpack.bat` decrypts base + update; Builders 1 `excel\excel\<Table>.en.bin` from `excel.nxarc` (17 English tables, 19,905 lines) and, from `build.nxarc`, the 4 Phyre fonts `build\gra\font\*.fgen.NXGL.phyre` and 82 pictures (the two HUD sprite packs `uitex` and `uiicon` with 345 and 980 sprites included); Builders 2 `LINKDATA\text\<first>-<last>.dqbp` (28 packs of the English member of each five-language group of `LINKDATA.BIN`: 4,219 tables, 81,129 lines; one pack is one block), the font `LINKDATA\font\00598.g1t` and 62 localized pictures `LINKDATA\texture\<index>.g1t`); **Translation:** `translation`. The game's codes stay in the text (`<key>` end of page, `<br>` new line, `<pname>`, `<speaker(Name)>`, `<color(0xAARRGGBB)>`). The Japanese key column of a Builders 1 table is not shown and never rewritten. `2_build.bat` stores a changed file raw at the end of `excel.nxarc` / `build.nxarc` / `LINKDATA.BIN` and points the index at it (LayeredFS mod; the original is copied once).
- `xenoblade_3` — Xenoblade Chronicles 3 + the 4 DLC waves incl. Future Redeemed (Switch). **Source:** the
  workspace's `source` folder (`1_unpack.bat` reads only the needed entries of the game's `bf3.ard` and DLC
  `bf3_dlc0N.ard` archives — one copy per path, the newest wave's — and puts there, at the archive paths, the
  English text tables `bdat\gb\game\*.bdat` and `bdat\gb\evt\<kind>\*.bdat`, the fonts `menu\font\*.wifnt`
  and the layouts `menu\image\*.wilay`); **Translation:** `translation`. One block per table file (4,118 files,
  117,513 text cells); the game's codes stay in the text as `[ML:icon icon=btn_a ]`-style tags. The Font Editor
  opens the six LAFT fonts (none has a Cyrillic letter; 8 free rows of cells are shown for new letters and the
  atlas grows on save); the Textures window lists the English title logo (`mnu001_cont01_en`), the title
  layouts and the English tutorial pictures (BC7 textures written back in place, JPEG pictures re-encoded).
  `2_build.bat` writes changed files as loose romfs files for the game and every DLC that holds them and hides
  their entries in each archive index.
- `xenoblade_2` — Xenoblade Chronicles 2 + Torna: The Golden Country and the other DLC (Switch, update 2.1.0).
  **Source:** the workspace's `source` folder (`1_unpack.bat` writes the `.nsz` images once as `nsp\*.nsp`, reads
  only the needed entries of the game's `bf2.ard`, Torna's `aoc1.ard` and the loose files of the small DLC, and
  puts there, at the archive paths, the English text tables `bdat\gb\*_ms.bdat`, the fonts `menu\font\*.wifnt`
  and the layouts `menu\image\*.wilay`); **Translation:** `translation`. One block per table file (4,537 files,
  83,323 text cells: the `name` column of the legacy BDAT tables; labels stay), folders by kind (`common_ms` =
  menus, system, names and descriptions; story events `bf`, quests `qst`, NPC talk `tlk`, field and camp events,
  heart-to-hearts and inns) with Torna and the three DLC packs as their own folders; the game's codes stay in the
  text as `[ML:undisp ]` / `[System:Color name=tutorial ]…[/System:Color]` tags. The Font Editor opens the eight
  LAFT fonts (`standard`, `subtitle` and `mincho` have Russian Cyrillic and lack only Ґ Є І Ї ґ є і ї; the
  others have no Cyrillic; 8 free rows of cells are shown for new letters); the Textures window lists the English
  title logos (`mnu001_titlelogo_us`, the wide `_b_us`, Torna's `dlc3_mnu001_titlelogo_us`), the title layouts
  and every picture with English text (`*_us`: BC1/BC3/BC4/BC7 textures written back in place). `2_build.bat`
  writes changed files as loose romfs files for the title that holds them and hides their entries in the
  `bf2.arh` / `aoc1.arh` index.
- `xenoblade_x_de` — Xenoblade Chronicles X: Definitive Edition (Switch, update 1.0.2). **Source:** the
  workspace's `source` folder (`1_unpack.bat` reads only the needed entries of the game's `sts.ard` — its
  `sts.arh` index holds path hashes, named from a public hash list — and puts there, at the archive paths, the
  English text tables `bdat\us\*.bdat`, the credits `ui\credit\endroll.crt`, the fonts `ui\font\*.wifnt`, the
  layouts `ui\image\*.wilay` and the English pictures `ui\stream\us\*.wilay`); **Translation:** `translation`.
  One block per file (1,801 tables with 121,843 text cells + 654 credits lines), folders by kind (`common_ms` =
  menus, system, names and descriptions; story events `xs`, quest events `qev`, talk events `tev`, credits); the
  game's codes stay in the text as `[ST:wait ]` / `[ST:icon p1=a ]` / `[ST:col p1=red ]` tags. The Font Editor
  opens the six LAFT fonts (`standard`, `caption`, `standard_kr`, `standard_tw` have Russian Cyrillic and lack
  only Ґ Є І Ї ґ є і ї; `numeric` and `unique` hold digits and signs; 99 free cells plus 8 free rows shown for
  new letters); the Textures window lists the English title logo (`ui\stream\us\strm_title_thumb001`), the title
  layouts (`10010_*`), the English layouts (`*_en`) and pictures (BC7 / RGBA8 written back in place, JPEG
  re-encoded). `2_build.bat` writes changed files under `romfs\mod\` of the LayeredFS mod together with
  masagrator's XCXDE-ModLoader (`exefs`), which makes the game read them instead of the archive entries.
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
  The editor flags a dialogue page with more lines than its balloon (`VGS_LINES_EXCEEDED`; `{page}` starts a
  new page) and a name or staff-roll line longer than its place (`VGS_BYTES_EXCEEDED`). The staff roll
  takes Ukrainian letters on the bytes listed in `credits_map.json` (46 letters on the 46 cells the English
  credits never draw; a byte that is one of them cannot be typed as its ASCII character); the owner draws
  their glyphs in the staff-roll font. The preview column draws the page of the selected line with the game's
  12 x 12 font (regular for menus, italic for balloons) and the balloon's size (chars per line × 12 + 10 px,
  lines × 13 + 4 px, read from the script); Previous/Next page follow `{page}`. The balloon frame art is not drawn.
  A staff-roll line that types an ASCII character the Ukrainian letters use is flagged with the reason
  (`VGS_CREDITS_RESERVED`).
  Scene context names the area and room of a room file (`vs_index.json`); the game data names no
  speakers. `2_build.bat` writes the changed files over their own sectors of the disc image (EDC/ECC
  recomputed) and splits the font back into `SYSTEM.DAT` and `BATTLE.PRG`.
- `castlevania_sotn` — Castlevania: Symphony of the Night (PlayStation, USA SLUS-00067) and its PC port
  SymphonyRecomp. **Source:** the workspace's `source` (`1_unpack.bat`): the program files under their disc
  paths — `DRA.BIN` (item, relic, spell and enemy names and descriptions, menus, memory card messages),
  `ST\SEL\SEL.BIN` (title and file select, endings, staff roll) and the stage and boss overlays
  `ST\*\*.BIN`, `BOSS\*\*.BIN` (cutscenes, the librarian's shop and bestiary, pick-up messages, and the
  prologue caption in `ST\ST0\ST0.BIN`: one editor line per script line, `{PAGE}` at a line's end ends a
  page; the caption is drawn in the console font, so Cyrillic needs the reader that the build installs; Ї Є Ґ
  and their small letters come from the caption's own letter table, Tools → Font Editor, "Caption letters";
  a line wider than the 512-pixel panel is flagged) — and the
  picture files `BIN\F_*.BIN.pic`, `ST\SEL\F_SEL.BIN.pic` (the disc files with `.pic` added, so they are not
  listed as text); **Translation:** `translation`. Where each string is comes from the decompilation
  (`layout_us.json`, made by the workspace's `tools\sotn_layout.py`), so no text is guessed. Two fonts: the
  8x8 font (menus, names, cutscene dialogue; Tools → Font Editor, `F_GAME.BIN`, format `texture_grid`; the
  build copies it into `F_GAME2` and `F_TITLE1`) and the console's BIOS font (descriptions, messages:
  Shift-JIS, it has Cyrillic but no Ґ Є Ї; І і are written as Latin). Ukrainian letters of the 8x8 font go
  through `translation_map.json` to free katakana cells (look-alike letters use the Latin cells). A second 8x8 font, the red damage numbers and status words (`F_GAME.BIN` at 0x10000), is in the Font Editor too: its digit row is mapped, its word rows are free. Saving a font writes its copies (`F_GAME2`, `F_TITLE1`) into the translation folder. The cutscene dialogue window preview draws the first page in the 8x8 font at the window place of its script's POS command. Its text position matches one DuckStation dialogue frame; the speaker name and the menus are not drawn yet. On the prologue stage (ST0) it also draws the two hearts digits of the Richter HUD (preview only; the sheet is read from `ST0.BIN`). Cutscene
  lines show timing commands as tags (`{WAIT 30}`, `{SPEED 02}`) and the speaker from the portrait; a
  staff-roll line starts with its tag (`{ENTRY 10}`). Text may grow: a string only data points at moves
  inside its pool (pointers rewritten) or into a range the decompilation marks unused; a cutscene that
  outgrows its room continues there through a jump command; a string code points at keeps its slot; a
  save that does not fit says which file and group. Tools → Textures (formats `sotn_blocks`: VRAM tile
  blocks, and `sotn_cmp`: the game's nibble-packed pictures, packed again into their room) lists the title
  logo (with its palette), title, prologue, HUD, game-over and file-select pictures and the area names.
  Saving keeps pictures already edited in the same file. `2_build.bat` writes the changed files over
  their sectors (sizes unchanged, EDC/ECC recomputed; nothing changed = the USA disc byte for byte) and
  builds the PC port once; `3_run_pc.bat` starts it with the translated disc (the port reads the game data
  from the disc, only the code is recompiled).
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
  them and the packages into a copy of the ISO. The same plugin opens the GameCube Metroid Prime (USA 1.00
  `GM8E01`) of the workspace `Metroid\Prime (GC + PC port)` (folders `text`, `font`, `texture` without a game
  level; GameCube fonts through `retro_font_gc`): `2_build.bat` there writes the changed resources as loose
  `<id>.STRG/.FONT/.TXTR` files in `build\mods\Picoripi_UA`, the mods folder of the native PC port
  Odrannnn/MetroidPrimePort, which runs from the original disc (`3_run.bat`)
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
- `metal_gear_solid_23_mc` — Metal Gear Solid 2 and 3, Master Collection Version (Switch; PC not yet).
- `metal_gear_mc_bonus` — Metal Gear Solid Master Collection Bonus Content (Vol.1 and Vol.2, Switch): the two M2 apps' PSB menu and message text (English lines); fonts and pictures open in the shared font and texture tools.
  **Source:** the workspace's `source` folder (`1_unpack.bat`): `text\<group>.json` (codec, scenario, demo,
  movie, vox, books and the launcher's text; one block per game file, each English string once per group;
  `2_build.bat` puts the translated line into every place the string stands). Keep the line breaks, the `|`
  marks and the button symbols. Fonts: `font\MGS_Font_nht.raw` (Font Editor format `mgs_nht`; spare cells
  take new letters) and the launcher's SDF fonts (`tmp_sdf`). Pictures: the `.ctxr` files under `texture`
  (Textures format `ctxr`) and the launcher's PNG pictures.
- `fragile_dreams` — Fragile Dreams: Farewell Ruins of the Moon (Wii, Europe). **Source:** the workspace's
  `source` folder (`1_unpack.bat` unpacks the disc's compressed `FILE_<id>` files there): `text\60001061.msg`
  (every dialogue, subtitle, item description, memory and the title menu), `text\40003100\1\*.msg`,
  `text\60001083\0.msg`, `text\600010AF\0.msg` (end credits), `sys\main.dol` (the save check, Wii Remote and
  disc messages, written in place, each block in its room) and `hbm\10000081.csv` (HOME Menu). Each message
  block is one Picoripi block (about 3,900 strings); `<w>`, `<v1>`, `<p>`, `<c#404040ff>` and `[Value]` stay
  as they are; text is written in cp1251, so Ukrainian letters use the font cells 0xC0–0xFF and those of
  Ґ Є І Ї. The Font Editor opens all 14 FONT fonts (format `fragile_dreams`; Japanese glyphs are kept as
  they are); **Tools → Textures…** lists about 2,800 TPL pictures (title logo, tutorials, menus, maps,
  health and safety screens, HOME Menu, disc banner). `2_build.bat` compresses the changed files again.
- `no_more_heroes` — No More Heroes (Wii, Europe). **Wizard:** choose the disc image (ISO or RVZ); the wizard
  unpacks it into the project's `source` folder. An encrypted ISO needs the Wii key file in console keys.
  **Build:** "Wii disc image (ISO, English)" writes a plain ISO. An RVZ or WIA source is first written as a plain ISO
  (every partition is hashed and encrypted again; this takes several minutes); the build needs the Wii key file.
  **Source:** the unpacked `source` folder (the game's RMHG resource files, unpacking the game's LZ): `text\<disc file>.nmt` — the
  English lines of every text box of one game file (cut-scenes, stages and the city, side jobs, items, menus;
  about 12,000 lines in 1,064 files), `text\main.dol.nmt` (menu words kept in the program: title copyright,
  save screen, map and shop key guides, job board; written in place) and `hbm\home.csv` (HOME Menu). The game
  draws no text from a font: each box carries a picture of its own glyphs, which the build draws anew from
  the old picture and the fonts. The Font Editor opens 15 fonts as glyph grids (format `texture_grid`, I4;
  each has empty cells for the 66 Ukrainian letters, written as Shift-JIS Cyrillic codes) and the HOME Menu
  font; **Tools → Textures…** lists about 1,080 pictures (boot logos, menus, loading and safety screens, item
  cards). The title logo is a 3D model, not a picture.
- `madworld` — MadWorld (Wii, Europe). **Source:** the workspace's `source` folder: `text\<disc file>.mwt`
  — the English message tables (cut-scene subtitles `event\*`, mission and tutorial messages `case*\idpac_*`,
  system and save messages `subscr\*`; about 1,630 messages in 68 files) and `hbm\home.csv`. The tables keep
  glyph numbers, not character codes; the characters are known from the glyph pictures. `<8010:0064>`,
  `<8002>` and `<#0003>` are the game's codes and stay as they are. The Font Editor opens the subtitle and the
  heading font (`texture_grid`, IA8; empty cells for the Ukrainian letters), the ASCII system font and the
  HOME Menu font; **Tools → Textures…** lists about 500 pictures with text (the MADWORLD logo, menus, HUD,
  tutorials, safety screen; the English health-and-safety pictures `strap\strap_*_us.tpl` are in it too). The wizard
  unpacks the disc (`.iso` or `.rvz`; an encrypted `.iso` needs the Wii key file). The build target **Wii disc
  image (ISO)** writes a plain ISO and draws each changed table's glyph picture anew. An `.rvz` source is written
  as an ISO first (several minutes). It also needs the Wii key file. A letter with no picture in the font is
  left out of the game; the build status line names it and `BUILD_WARNINGS.txt` beside the ISO lists it.
- `wario_land_shake_it` — Wario Land: Shake It! (Wii, USA, RWLE01 rev 0). **Wizard:** choose the disc image (ISO, WIA
  or RVZ); the wizard unpacks the English message packs into the project's `unpacked` folder and writes one text
  document per message file (`MessageData\*.json`). **Source:** one block per BMG file: 575 messages in six files
  (area, demo, error, game, stage, treasure); a `{esc:FF:00000100}` in the text is a game code and stays as it is.
  **Build:** "Wii disc image (ISO, English)" writes a plain ISO with the English pack replaced; the build needs the
  Wii key file in console keys. **Not yet:** fonts (the game's font has no Ukrainian glyphs), textures with text,
  other languages as reference columns.
- `xenoblade_wii` — Xenoblade Chronicles (Wii, USA) and Xenoblade Chronicles 3D (New 3DS, EUR): one plugin,
  one translation. **Source:** the workspace's `source` folder (`1_unpack.bat`), at the same paths on both
  platforms: the English BDAT table files `bdat\bdat_common.bin` (120 tables: menus, items, arts, skills,
  enemies, names, system messages, battle chatter), `bdat\common\bdat_*.bin` (quests, descriptions,
  tutorials, achievements, story log), `bdat\map\bdat_ma*.bin` (NPC auto-talk, trade talk, gimmick messages
  per map) and the scripts `script\*.sb` (NPC talk, events, heart-to-hearts: 24,600 lines in 494 scripts;
  identifiers and debug prints are left out); Wii only: `bdat\code_mes_en.bdat` (the disc messages of
  `main.dol`, written in place) and `hbm\hbm.arc\hbm\home.csv` (HOME Menu). About 62,800 lines in all;
  `<n>`, `<col=s2>`, `<wait=key>` stay as they are and `@` breaks a line in menu text. The Wii files are
  big-endian (tables and script strings scrambled), the 3DS files little-endian and plain; the 3DS
  `2_build.bat` also takes every text file translated in the `..\Wii` workspace and not in its own, so one
  translation feeds both. The Font Editor opens the game fonts (Wii `RFNA`, 3DS `ANFR` with QuickLZ sheets,
  format `brfnt`), the 3 battle fonts and the HOME Menu font; **Tools → Textures…** lists the TPL pictures
  (Wii about 3,100, format `tpl`; 3DS about 3,000, format `tpl_ctr`: title logo and title menu words, every
  menu layout, maps, banners). `2_build.bat` writes a patched WBFS (Wii) or a Luma romfs mod (3DS).
- `fire_emblem_awakening` — Fire Emblem Awakening (3DS, EUR, English slot). **Source:** the workspace's `source` folder
  (`1_unpack.bat` decrypts the .cia and decompresses the English files there): `romfs\m\U\*.bin` (854 LZ11 message
  archives: story and support conversations, unit / class / item / skill names and descriptions, menus, tutorials, DLC
  chapter text; 15,817 messages), the six `romfs\fonts\*.bfnt` atlas fonts (`fe13_bfnt`) and the English CTPK / CGFX
  images with text (`ui\*_U`, `bs\*_U`, `chapter\title\U`, `tut\U`, `telop\*_U.r`, the title logo `ui\title_U.ctpk`).
  Control codes stay in the text (`$k`, `$Wmクロム|0`, `$E通常,|`...); the speaker of `$Wm` / `$Ws` is named in English
  from `GameData.bin`. `2_build.bat` compresses the changed files again (LZ11 / LZ13) into a Luma `romfs` mod.
- `smt_iv` — Shin Megami Tensei IV and IV: Apocalypse (3DS, EUR). **Source:** the workspace's `source` folder: every
  `romfs\**\*.mbm` (Atlus MSG2 tables: events, quests, battle and demon talk, menus, names, descriptions), the DLC
  tables under `dlc\content_NN\romfs\`, `exefs\code.bin` (skill, place and menu names inside the executable, edited in
  place), the Shift-JIS keyed `romfs\font\*.bcfnt` fonts and the UI STEX textures (`tex\stex\<folder>`, the title logo
  `title\rogo.stex`). The text shows the game's full-width letters as ASCII and its control codes as `{F8xx 0001}` tags;
  Ukrainian letters get the free Shift-JIS codes 0x8492–0x8499 (`core/font_formats/sjis.py`). `2_build.bat` writes the
  changed files (Apocalypse's `.cmp` textures compressed again) into a Luma `romfs` mod; the DLC's files go under the
  DLC title id (Azahar applies them; Luma on a console does not patch DLC).
  Strange Journey Redux (EUR, `SMT_SJR_3DS`) uses the same plugin: 106 `.mbm` and 27 `Event\EventMessage*.bin` files
  (`TBB1` blocks, `0000`-terminated strings), the DLC title list, six BCFNT fonts and 419 STEX pictures.
- `dragon_quest_vii` — Dragon Quest VII: Fragments of the Forgotten Past (3DS, EUR, English slot `EN`). **Source:**
  the workspace's `source` folder (`1_unpack.bat` decrypts the .cia and decompresses the LZ11 / LH files there):
  `romfs\MESS\EN\*.fpt` (331 FPT0 packs of `#NNNNNN.txt` messages: dialogue and events, 56,720 messages; a string is
  one message, its `#window,speaker` header stays in the pack and names the speaker), `romfs\MENULIST\EN\*.txt`
  (22 CSV menu lists: commands, items, spells, monsters, vocations, places, StreetPass; 23,920 lines), the 20 BCFNT
  fonts (`Font.bcfnt`, `demox\demo_font.bcfnt` and the `tbud_maru`, `m7_win`, `iwamaru` fonts inside the
  `LAYOUT\*.arc` darc archives) and the screens and atlases as `DMP` textures (`SCREENTEX\<folder>\*.fpt`: 64x64
  tiles of each screen, `LAYOUTTEX\*.fpt`, `LAYOUTTEX\*\*.dmp`). Tags: `{HERO}`-style names, `%a00` codes,
  `%E` / `%Y` grammar codes, `{LF}` for the game's lone LF line break. `2_build.bat` compresses the changed files
  again (LZ11, LH 0x40) into a Luma `romfs` mod.
- `dragon_quest_viii` — Dragon Quest VIII: Journey of the Cursed King (3DS, EUR, English slot `eng`). **Source:**
  the workspace's `source` folder: `romfs\data\Message\eng\*.binE` (menus, items, spells, skills, monsters, battle,
  church, casino, alchemy, quests) and `romfs\data\Script\field\message\eng\**\*.binE` (events, NPC talk, party
  chat, records; 581 tables, 39,164 strings with their ids), `romfs\data\Params\WordTable\eng\*.txt` (item and word
  tables, one string per line), the five `rom\Font\*.bffnt` fonts and the BFLIM pictures inside the SARC layouts
  `data\Layout\**\*.arc` (the title logo `title\title_u.arc`). Text is UTF-8 with `[...]` codes. `2_build.bat`
  puts the changed files into a Luma `romfs` mod.
- `dq_monsters_joker3` — Dragon Quest Monsters: Joker 3 (3DS, Japan, with the English fan patch 1.02 applied; the
  patched game is the source). **Source:** the workspace's `source` folder: `romfs\data\Message\**\*.mes` and
  `romfs\data\Script\Field\**\*.mes` (417 hashed tables, 16,697 UTF-16 strings with their labels: menus, items,
  skills, monsters, scouting, synthesis, help, trivia, scenes; control characters show as `{01}`), the credits
  scripts `data\Menu\EndRoll\*.nut` (quoted strings), the four `*.bffnt` fonts (the RGBA4 `break_font`) and the
  BFLIM pictures inside the SARC layouts `data\Layout\**\*.arc` (the title logo `title\upper\title_logo.arc`).
  Lines the patch left Japanese stay visible. `2_build.bat` puts the changed files into a Luma `romfs` mod.
- `mhp3rd` — Monster Hunter Portable 3rd HD (PSP image NPJB-40001, Yakumo PC port). **Source:** the workspace `source` folder holds `en_source.json`, built by the workspace script build_source_lang.py (not in this repository) from the user's PSP image and the English patch: keys are `TABLE:INDEX` (quests `ref:offset`). **Translation:** `translation/uk.json`; `2_build.bat` writes `uk.lang` into Yakumo's translations folder, and the disc is not changed. Not yet: the Character Creation labels (not in the extracted blocks) and the font choice (Yakumo's `text.font` in its `settings.ini`). **Required Yakumo:** a build from commit 43190f0 or later (the released builds alpha.4 and alpha.5 cannot load translation files).
- `monster_hunter_3ds` — Monster Hunter 3 Ultimate, Monster Hunter 4 Ultimate and Monster Hunter Stories
  (3DS, Europe; Capcom MT Framework Mobile). **Source:** the workspace's `source` folder (`1_unpack.bat`
  decrypts the game and takes the English and language-neutral files out of the `.arc` archives, at the
  game's own paths; a file that sits in several archives is one file). Text: `.gmd` tables (MH3U, UTF-8),
  `.lmd` tables (MH4U and Stories, UTF-16) and the quests' English slot (`.quest` MH3U, `.mib` MH4U); each
  file is one block; `<COLO 1>`, `</COL>`, `<SUBS 3>` and `%s` stay as they are; strings may grow; an
  unedited file is saved byte for byte. The Font Editor opens the `GFD` / `lfd` fonts with their `TEX` page
  (format `mt_font`; the main fonts have the Russian Cyrillic letters, Ґ Є І Ї ґ є і ї are added as new
  letters). **Tools → Textures…** lists the UI and title pictures (`mt_tex`). `2_build.bat` rebuilds every
  archive that holds a changed file into a Luma romfs mod.
- `plain_text` — Plain Text
- `pokemon_fr` — Pokémon FireRed / LeafGreen, Ruby / Sapphire and Emerald: JSON dumps of the ROM text, or the source files of the pret decompilations (`.inc`, `.s`, `.c`, `.h`; one block per file; `\n`, `\l`, `\p` and `{PLAYER}` codes; the `$` terminator is not shown). Speakers come from each map's `map.json`. The region map names and FireRed item names (JSON) are messages too. A saved decompilation file keeps its LF line endings, and an indexed PNG keeps its palette, bit depth and unedited pixels. **ROM mode (FireRed / LeafGreen, USA rev 0, the first version):** the Project Manager's **Game ROM** role takes the `.gba` file (identified by its SHA-1). Unpacking writes every message to `text\messages.inc` and keeps a copy of the ROM in `romase.gba`; no other tool is needed. **Patched ROM** writes a `.gba` with the changed messages: a message that is longer than the original moves to free space and the pointers to it are rewritten; an unchanged message stays byte for byte. A message that no pointer reaches keeps its length: the editor shows **Byte budget exceeded** for a longer text, and the build refuses it. Sound-effect codes are not text codes: `{PLAY_SE ...}` and `{PLAY_BGM ...}` take the game's sound ids. Default tag aliases: `{Player}`, `{Rival}`, `{Var1}`–`{Var3}`, `{A}`, `{B}`, `{Start}`, `{Up/Down}`, `{Left/Right}`, `{Plus}`, `{Lv2}`. Not yet in ROM mode: the font and the message box preview. **Message box preview:** for FireRed, LeafGreen and Emerald the preview draws the selected message in the game's own font, read from the base ROM in a worker thread, page by page, in the game's text width and two-line box. A line that is too wide, or a third line without a line scroll or a page break, gets a warning under the box. Ruby and Sapphire have no font entry yet. **C-built name tables:** the names the C code reads sit in fixed-size fields, so they cannot grow. They unpack to their own files in `text\`: species (412, `species_names.inc`), moves (`move_names.inc`), abilities, types, trainer classes, items (`item_names.inc`), trainer names (`trainer_names.inc`) and berries. A field longer than its size shows the warning **Byte budget exceeded** under the editor line; the build refuses it and gives the byte count. FireRed, LeafGreen, Emerald, Ruby and Sapphire also have their move, ability and item descriptions, nature names, Pokédex descriptions and Pokédex categories in the project. These texts may grow: a longer text moves to free space and its pointer is rewritten. The texts the C code builds (the string literals of the decompilation) are also in the project when the ROM holds each one as a single text; they unpack to `text\c_<source file>.inc`. Texts of other languages and of debug code are not in the English ROM and are left out. The item descriptions of `items.json`, the trainer and decoration name fields (every place of one name is a field of one unit; they unpack to a new table file named after the source, for example `text\c_trainers_h.inc`), and the English messages the ROM holds that no source names, for example the text of the multiboot programs (`text\c_rom_messages.inc`), are in the project too. Picture, palette, font and sound bytes are not texts and are not opened. Build target **Recomp package** writes one folder per dump: `EmeraldRecomp\emerald\` (Emerald), `FireRedLeafGreenRecomp\firered\` and `...\leafgreen\`. Each holds the translated ROM, `recomp.json`, `run_UA.bat` (starts the port with `--rom-sha1`) and `README_UA.txt`. A changed build of Emerald, FireRed or LeafGreen also holds `recompile_UA.sh`: it runs the port's importer and `gba_recompile` on that ROM and the build's ELF (WSL), then builds the port. A changed build moves code, so the stock release stops at a dispatch miss and the port must be rebuilt with this script. The BIOS dump stays with the user.
  Preview: the message box is drawn in the game's own font (Ruby / Sapphire: font 3, 4bpp, read from the ROM). Default tag aliases include `{Kun}`, `{Version}` and the team and leader names; argument codes have aliases: `{COLOR:Red}`, `{HIGHLIGHT:Red}`, `{SHADOW:DarkGray}`, `{Pause}` (waits for a press), `{PlaySE:Select}`, `{PlayBGM:LevelUp}` and `{FONT:Normal}`. `{PAUSE}` with a frame count has no alias. Each alias builds the bytes of its raw tag.
- `pokemon_trinity` — Pokémon Scarlet/Violet (+ The Teal Mask, The Indigo Disk) and Pokémon Legends: Z-A
  (+ Mega Dimension) (Switch, Game Freak's Trinity engine). **Source:** the workspace's `source`
  (`1_unpack.bat` reads only the needed packs of `arc\data.trpfs` and puts there, at the game's paths, the
  English text `message\dat\English\{common,script}\*.dat` — Z-A: `ik_message\...` — the fonts
  `appli\font\bin` / `ui\font\bin` and the English layout archives `*_eng.arc`). The Project Manager wizard does
  this itself with Picoripi's readers: the base game and its update, and the Oodle library file, which the wizard
  asks for once and remembers (the packs are Oodle-compressed). The output equals the workspace `source`, file by
  file. The Switch build target writes the changed files and a patched index for each title: Scarlet from its
  base and update, Violet from the other version's roles (its own base and update). **Translation:**
  `translation`. One block per message file (Scarlet/Violet 913 files, 85,331 lines; Z-A 427 files, 76,810
  lines); the `.tbl` next to each file gives every line its label (the line's name in the game); variables read `{VAR 0101 0000}`, `{PAGE}`, `{SCROLL}`, `{COLOR 0001}`, icons `{CHAR E300}`; grammar branches carry their
  two texts, `M{GENDER 00FF|aster|iss}`, `{VERSION 00FF|Ko|Mi}raidon` (Scarlet | Violet), and their lengths are
  written again on save. The Font Editor opens the `.bfotf` and `.bffnt` fonts; the Textures window opens the
  BNTX pictures of the English layouts (title logo, menus). `2_build.bat` writes the changed files into a
  LayeredFS mod with an `arc\data.trpfd` that no longer points the game to the packed originals (a changed
  English layout `X_eng.arc` also goes in as `X.arc`: the game reads language layouts only from its packs); Scarlet and
  Violet share one project and get the same mod. **Message box preview:** the box is drawn from the game's own layout
  with the `.bfotf` fonts. Scarlet / Violet: `msg_sub_00.bflyt` (sub-window archive). Legends: Z-A: `msg_00.bflyt` in
  `msg_body_00.arc`, placed by the outer `msg_body_00.bflyt` at y -370; the wizard writes that archive (its view is
  `view_msg_body_00.truiv`). The window picture is not drawn. The Z-A glyph size is not measured yet.
- `wii_sysfont` — the Wii system bitmap fonts `wbf1.brfna` / `wbf2.brfna` (the NW4R archived fonts of the
  System Menu, shipped as copies on discs that draw prompts with them, e.g. Raving Rabbids: Party Collection).
  The vWii NAND of the EUR console has the same two files; its WiiNTLG-Regular.ttc faces
  (`fonts/WiiNTLG-Gothic.ttf`, `fonts/WiiNTLG-PGothic.ttf`) open in the Font Editor as TTF. A face cannot be written back into the collection yet.
  **Source:** the workspace's `source` (`1_unpack.bat` takes the fonts from Dolphin's NAND `shared1` content
  or from the Rabbids disc copies and prepares the Ukrainian letters: І і Ї ї get the glyphs of I i Ï ï,
  Є є Ґ ґ get empty cells at the end of the ASCII sheet); **Translation:** `translation`. The Font Editor opens
  both fonts (`brfna`); `2_build.bat` writes the fonts for a disc (`build\disc\fonts`) and, when the NAND was the
  source, the shared content for a NAND (`build\nand\shared1`).
- `pokemon_md_3ds` — Pokémon Mystery Dungeon: Gates to Infinity and Pokémon Super Mystery Dungeon (3DS,
  EUR), one plugin for both games. **Source:** the workspace's `source` (`1_unpack.bat`): the English message
  files — Gates to Infinity `message\*.bin` (884 files, 55,081 lines), Super Mystery Dungeon the members of the
  `message_en.bin` pack as `message_en.bin\*.bin` (808 files, 68,716 lines), its debug label copies
  `message_debug_en.bin\*.dbin` (808 files, 68,716 labels) and the scripts with text `script\...\*.lua` (Lua 5.1
  string constants: the credits, debug labels; 28 files, 359 lines) — one block per file (story,
  dungeon, item, move and Pokémon names and descriptions in `common`, menus, Pelipper and Connection Orb text);
  the fonts `font\*.dic` + `*.img` (Font Editor format `pmd_font`) and the pictures `image_2d\*.img` /
  `image_2d.bin\*.img` (title logo, menus; Textures window format `pmd_img`). The wizard unpacks the image itself
  (Picoripi readers; the Super Mystery Dungeon CIA needs the 9.6 seed from the key folder, `seeds\` or `seeddb.bin`)
  and writes the same tree as `1_unpack.bat`. **Build target 3DS mod (LayeredFS)** writes `titles\<title id>\romfs\...`:
  a changed loose file as it is, a changed pack member rebuilt into the game's own pack. **Preview:** Gates to
  Infinity draws the intro dialogue on the top screen with the game's font (`FOT-RodinProN-DB_14`, the box at
  y 170..232); Super Mystery Dungeon draws the story text on the top screen with `Fot-TskuARdGothic_Std_B_14` at scale 1.0 (no panel, line pitch 24). Gates to Infinity marks every line wider than the box edge (text width 320 px); the game does not word-wrap there. Tags: `[CN]` centre a line,
  `[K]` wait for a button, `[C]` new box, `[hero]` / `[partner]` / `[my_team]` names, `[CS:06]…[CR]` colour,
  `[M:B05]` button icons, `[value:02:0003:0001]` numbers and inserted names (keep them as they are); a literal
  bracket is `[[` / `]]`. Text may grow: `2_build.bat` lays each message file out again and repacks the packs.
- `senran_kagura_burst` — Senran Kagura Burst (3DS, EUR). **Source:** the workspace's `source`: the 432 `TAMS`
  message files `romfs\scenario\{hanzo,hebijo}\*.bin` (3,759 messages of any length: story chapters and
  conversations; `{v02001}` voice, `{cff0000ff}` … `{r}` colour, `{b008}`, `{s022}` stay as typed), the strings
  compiled into `exefs\code.bin` (2,629 menu, mission, item and battle texts, 200 to a block, written in place: a
  text may not be longer than the original), the five `.bcfna` fonts (`cfna`, no new letters) and the BCLIM
  pictures inside the `romfs\ui\lyt_*.bin` packs (a pack of `darc` archives; a compressed pack is compressed
  again), CTPK gallery pictures and logos. `2_build.bat` writes a Luma mod (`code.bin` + `romfs`).
- `attack_on_titan_3ds` — Attack on Titan: Humanity in Chains (3DS, USA). **Source:** `romfs\_catfiles_lists\system.cf`
  (5,501 UTF-16 strings, written in place: a translation may not be longer than the original) and 293 `.ctpk`
  pictures; the `.rhg` UI pictures and the font are not opened.
- `dragon_ball_fusions` — Dragon Ball Fusions (3DS, EUR). **Source:** `message\msg_en.jmsg` (18,683 strings of any
  length), nine atlas fonts (`jfnt`; the packed outline font `default01` is not opened) and 2,099 `.jtex` pictures
  (`jimg`) from `DOF.cpk` and its `.jarc` archives; `2_build.bat` writes a new `DOF.cpk`.
- `gravity_falls_gemulets` — Gravity Falls: Legend of the Gnome Gemulets (3DS, EUR, UbiArt). **Source:**
  `localisation.loc8` (six languages, 1,542 strings each), two glyph-table fonts (`ubiart_tfn`: a new letter is a
  new table record) and 619 `.tga.ckd` / `.png.ckd` pictures (`ubiart_tex`) of the `.ipk` bundles, which the build
  packs again. The credits are not opened.
- `rhythm_paradise_megamix` — Rhythm Paradise Megamix (3DS, EUR). **Source:** the 18 English MSBT files in the
  `.zlib` SARC archives (5,715 messages; tags named by `pajama.msbp`), ten BFFNT fonts and 2,318 BFLIM / CTPK / CGFX
  pictures; the build packs the changed members into the `.zlib` files again.
- `default_plugin` — Default Plugin Template

<!-- wiki-nav -->
---

**Previous:** [Supported games](Supported_Games.md) · [Back to the wiki index](README.md) · **Next:** [Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md)
