---
status: current
updated: 2026-10-13
owns: ui/, components/, dialogs/
tokens: 11.3k
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
3. The games that Picoripi supports, with their platforms, wizard needs and build targets, are listed on [Supported games](Supported_Games.md).
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
| Project Manager… | Ctrl+Shift+M | The list of added projects. See below |
| Close Project | | Unload. Disabled until a project is open |
| Import Block… | | Add one file. **Project mode only** (tooltip: “only available in Project mode”) |
| Import Directory… | | Add a folder of files. Same restriction |
| Save Changes | Ctrl+S | Write **every** unsaved string. No confirm dialog |
| Save Changes As… | | Copy translations to a new location |
| Reload Original | | Re-read source files from disk |
| Revert Changes File to Original… | | Throw away the translation file and start from source |
| Export Translations to JSON… | | Round-trip translations. Disabled with no project |
| Export Original to JSON… | | Dump source strings |
| Fill Terms from the Glossary… | | Preview the strings a series glossary term translates; fill the untranslated ones. **Fill the other projects of the series** writes the other projects' backups. See wiki 8 |
| Import Translations from JSON… | | Load a previous export |
| Reload Tag Mappings from Settings | | Re-apply aliases after you edited plugin settings |
| Settings… | Ctrl+P | Preferences |
| Exit | | Quit; session checkpoint is written |

Partial save: right-click a block → save that block only. **Do not** use Revert unless you mean to discard the translation file.

### Project Manager

The Project Manager opens at start when no project is open. It lists the projects you added. A project is added
when you create, open or import it.

- **Add:** press `+`. Choose New project (a wizard), Add existing project (a `project.uiproj` file), or Import projects from a folder. **File → New Project** (Ctrl+N) opens the same wizard.
- **New project wizard:** choose the game (type a part of its name to find it); its name fills **Project name**, which you can change. Then add the files: the game, its update and its DLC, as files (**Add files...**) or unpacked folders (**Add folder...**). Each file gets a role (**Base game**, **Update** or **DLC**) and a platform: from the game's plugin, else from the file's own header (a Switch or 3DS title ID tells base, update and DLC apart; a folder tells its platform by its files or by a folder name in its path such as `Switch`, and a game on one platform gives that platform; else the platform reads **Not detected**). The role names stay English in every interface language. The platform list holds the platforms of the game's plugin, or every platform Picoripi knows when the plugin names none. Change them if needed; to give many files one role, select their rows, pick the role beside **Apply** and press it. Only DLC may repeat. The **Status** column and the red text under the list say at once what stops the project: two files with one role, a file this game cannot read (add its unpacked folder instead), or an encrypted file without its console's key file (**Add the key file for ...** gives it, or add the unpacked folder). **Next** stays off until the list is fine. A folder row shows the last three parts of its path. Then choose the project folder. **Create project** shows a progress window at once while the files are matched in the background; when the project is open, the Project Manager closes. The originals are not copied; the project refers to them by path. To keep a translation folder you already have, tick **Use an existing translation folder** and choose it; Picoripi then creates no translation files in it. A game of one file has no folder for translations, so the option is refused for it. When the game needs unpacking, the wizard unpacks into the project folder. Cancel stops the unpacking and removes what it wrote. A game image that the chosen game cannot unpack is refused: the wizard says so and asks you to unpack the image into a folder first; nothing is created. A project that fails to create or to open is removed and is not kept as the last project. At start, a last project that fails to load, or makes no progress for two minutes, is forgotten, its reason is shown, and the Project Manager opens. For a GameCube or Nintendo DS image the wizard first checks that the drive has room (the image size plus 10 %, or 256 MB when that is larger) and stops before writing if it does not. Some games use only part of the unpacked files: the project then starts from that folder (for example Twilight Princess `files/res/Msgus`). Metal Gear Solid: The Twin Snakes takes two discs: add each disc and the wizard gives it its role. Picoripi reads GameCube ISO and NKit discs, Nintendo DS ROMs, Nintendo 3DS programs (`.3ds`, `.cia`, `.cxi`, decrypted or encrypted), Switch `.nsp` packages and Wii discs; GameCube and Wii RVZ and WIA images are read as they are (a Wii one needs no key file: the format stores the partition decrypted), and `.xci` needs an NSP first. Encrypted files need the key file of their console: 3DS `aes_keys.txt` (with `boot9` beside it when the workspace uses one), Switch `prod.keys` or Wii `keys.bin`. The wizard offers **Get keys from the default source** first, then **Choose a file**. It asks for a console's key file once, and only when the game's plugin unpacks that console; it remembers only where the file is. Details: [Console keys](4_Configuration_Guide.md#default-source-for-key-files). If you cancel that dialog, the wizard stops and creates nothing. Picoripi checks no hashes of the decrypted data.
- **Unpacking:** a GameCube disc (ISO or GCM) or a Nintendo DS ROM (`.nds`) is unpacked into the folder `unpacked` inside the project folder. Picoripi recognises the file by its content. The game's plugin decides which files it keeps. GameCube RVZ and WIA files are read as the disc they hold (the file is read only, never converted or written; the rebuilt disc is still a plain ISO). Wii RVZ and WIA files are read the same way and need no key. NKit files of other kinds are not read: convert them to a plain ISO first. A game that needs no unpacking, for example a Game Boy Advance ROM, uses the file as it is.
- **Import:** finds `picoripi/project.uiproj` files under a folder. Folders named `_…` or `.…` are skipped. Duplicates and unreadable projects start unchecked. Each series folder becomes one manager folder.
- **Folders and shared glossaries:** create your own folders. Right-click a project → Move to folder. Deleting a folder moves its projects to the top level. A folder can optionally own a shared series glossary (**Group glossary...** button or right-click folder header → **New shared glossary...** or **Link shared glossary...**). Projects in the folder automatically inherit the shared glossary across translation, fill and series tabs, while existing personal links and ancestor `_glossary` discovery remain intact without duplicate links. Moving a project between folders, removing it from the manager, or unlinking/deleting the folder updates only the group-derived association; a project whose file is missing is skipped.
- **Order:** the last opened project is always at the top. Group and sort choices are saved.
- **Search:** the **Search projects** field above the list filters as you type. Ctrl+F moves the cursor into it; Esc clears it. It matches the project name, series, platform, plugin, the manager folder (group) the project is in and the folder path, ignores case, and works with Ukrainian and Latin letters. Each word must match one of these fields. Groups without a match are hidden, and group counts show the matches. Searching reads no files.
- **Closing:** with no project open, closing the Project Manager (close button, Esc or Alt+F4) quits Picoripi, as File → Exit does. With a project open, closing it returns you to that project.
- **Views:** **List** (default) shows a row per project with a 64 px icon, name, platform, series, plugin, progress (translated of the strings that need a translation, with a bar), last opened and status flags. **Grid** shows the same projects as 128 px tiles. Select a tile to see its details under the grid: the same details as an expanded row in the list. Groups apply to the list only.
- **Icons:** a project's icon is `icon.png` beside its `project.uiproj`, scaled to 128 px. Without one, the game's plugin may supply a picture; without that, a coloured tile with the series initials is shown. **Change icon...** (row menu or Details) copies a picture you choose, scaled to 256 px. **Clear icon** removes that file only. The wizard asks no icon: a new project takes the game's own picture when Picoripi reads it from the base image (the 3DS icon or the GameCube banner; not yet Switch, Wii or a folder). Use **Change icon...** on the row to replace it.
- **Scan and progress:** a scan reads the cards, icons and counts of all projects in a separate process, so the window stays responsive. It reads every project's name first (about a second), so the list and the search have all names at once. A project without a name in its file is shown under its game folder (the folder above `picoripi`). While the icons and files of each project are checked, a strip above the list shows "Checking 37 of 191 projects..."; then it shows "Scanning 37 of 191 — name — about 2 min left"; **Hide** hides the strip and the scan goes on; **Cancel scan** stops it after the project being counted; if the scan process does not stop within 2 seconds, it is ended. The strip hides when the scan ends. Rows whose counts are not known yet show `…`.
- **Cache:** the second start shows the last counts at once and scans again only what changed: a project whose project file, plugin config, or a source or translation file it names changed since the last count is counted again. So does a project after a change to its game's Python files, to the shared plugin files, or after a Picoripi update. Other projects keep their counts. The cache is `project_index.json` and `pm_icons` in the data folder; deleting them only costs a new scan.
- **Columns:** lines and translated % are counted in the background, also for projects you have not opened. Blocks inside archives are not counted yet.
- **Plugin missing:** a project whose game plugin is not installed shows the flag **Plugin missing** and is not counted. Nothing is deleted.
- **Details:** expand a row to see the path, the source files you chose with their roles, the stats, a list of the folders with their blocks and lines, the files of the source folder by kind (text, font, texture, other: counted on a worker the first time the row opens, and kept until the manager closes; the game's plugin may name a file's kind, otherwise its extension decides), and what needs attention (for example blocks with no translation file yet). Two flags, **Built** and **Verified in game**, are set only when you tick them. The details also show the series glossaries the project uses (the folder glossaries above it and an explicit link), with the number of terms in them, whether the glossary is linked or found in the folders above, and how many of the project's strings another project of the series translated; the manager reads them and writes nothing.
- **Build mod:** builds the game's targets into the project's `build` folder. A game that declares no target shows the button off.
- **Export mod:** copies a built target to a folder you choose. The folder must be empty.
- **Share project...** (Details button or row menu): packs the project into one `.zip` for another person. The package holds the project folder, the translation files and the linked series glossaries. It does not hold the original game files. Sessions, caches, backups and the `unpacked` and `build` folders are not packed either. A path in the project files is written relative to its folder (game, translation or project). A path outside these folders (fonts, references, game images) is cleared, so the package holds no path of your computer. Changes that are not saved in the editor are not in the package: save the project first.
- **Import shared project...** (`+` button): choose the package, a folder for the project and your own original game files (the extracted game folder, or a file when the sender used one). Picoripi unpacks the project into `picoripi`, the translation into `translation` and the glossaries into `glossaries` of that folder, writes your paths and adds the project to the manager. These folders must be empty. Set cleared paths again in the project settings.
- **Run in emulator:** builds the target and starts the emulator of the target's platform on it. Set one command for each platform with **Emulator...** (one line per platform). Write `{path}` where the built file or folder goes, for example `"C:\Emu\emu.exe" {path}`. The item is off for a platform with no command. The **Emulator...** dialog shows one line for each platform that a build uses; a line with no name appears only for a build that has no platform. A command saved before per-platform commands applies to every platform until that platform has its own line.
- **Icon:** a project can show a picture of its game. It is the file `picoripi/icon.png` next to `project.uiproj` (PNG, up to 256 px). A project without the file has no picture. `scripts/harvest_project_icons.py` fills missing icons from the game's own files; it never replaces an existing `icon.png`, and without `--apply` it only prints a table.
- **Remove from manager** never deletes project files.

---

**Already extracted game:** in New Project, step 2, choose **Add extracted game folder...** instead of adding an image. Choose the folder containing the game's expanded text tables (for Yo-kai Watch, the workspace's `source` folder containing `data/.../*.cfg.bin`; a RomFS holding only `.fa` archives is not enough). The wizard validates the folder on a worker, uses it in place, and skips extraction and keys. This source folder is separate from **Use an existing translation folder**. Use one source folder at a time. If the plugin cannot unpack an image, the wizard explains that limitation. For a missing or unsuitable console key, **Add key file...** lets you replace it and retry in the same wizard, preserving the source and location choices. Missing crypto dependencies and malformed images retain their own error messages.

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
| Font Editor… | | Bitmap fonts in a separate window; the project stays open. Opens Nintendo `.bfn` (Twilight Princess, Wind Waker), the message font inside an N64 Zelda ROM (OoT, MM), Hyrule Warriors `.g1t` atlases, Age of Calamity `.g1n` fonts, Switch and Wii U `.bffnt` (The Wind Waker HD: big-endian, GX2-tiled sheets; Paper Mario: Color Splash: two-tone BC5 sheets, shown as the letter in grey over its shape in alpha), Wii `.brfnt` (Skyward Sword HD and Wii: GX I4 sheets) and the 3DS fonts: `.bcfnt` / 3DS `.bffnt` (A Link Between Worlds, Tri Force Heroes), Grezzo `.qbf` (Ocarina of Time 3D) and `.gzf` (Majora's Mask 3D), and the Switch scalable fonts `.bfotf` / `.bfttf` (Tears of the Kingdom, Animal Crossing: widths are saved as the glyph advances, a redrawn glyph is saved as an outline traced from its pixels, CFF or TrueType), 2bpp text fonts of Metal Gear Solid: The Twin Snakes and of Metal Gear Solid (PlayStation, `font.res`) and the 12x12 text font of Vagrant Story (regular and italic, with the advances of `BATTLE.PRG`; the two staff-roll fonts of `ENDING.PRG`) and the Tingle Tuner's GBA tile font inside `client_u.bin` of The Wind Waker (each from its project only), Nintendo DS `.nftr` (Four Swords Anniversary Edition) — open them with **Open** (no project needed; Save writes the file back). In a font that maps Unicode characters (`.bffnt`, `.g1n` and the 3DS fonts), typing a letter into an empty cell's character column adds that real character to the font (no translation slot; a character the font already has is refused): draw the glyph in a free cell and give it its letter. The game's own fonts, named by its plugin, are listed in the font tree and open from the project (the translation copy once there is one); Save writes the translation copy and the font's widths with the translation map to `<project>/font_maps/`, which the width checks read. Hyrule Warriors DE takes its advances from a table in the game's executable, not from the atlas: the editor shows that table (in atlas pixels) and Save also writes it as executable patches `exefs/<build id>.ips` in the translation folder, one per game version (the workspace's `2_build.bat` puts them into the mod). Wind Waker also lists its name-entry and system fonts; Twilight Princess lists its text and ruby fonts (the archives in `res/Fontus`). **Render System Font to Glyphs** takes a TTF/OTF through **Font File...** (no install needed) and can **Thicken** strokes for small heavy fonts; with baseline alignment each rendered letter is moved to stand on the font's own Latin baseline (р у ф hang like p, д ц щ line up by their top); **Move glyph** (◀ ▲ ▼ ▶ or Ctrl+Arrow keys) shifts the selected glyphs' pixels 1 px inside their cells, with undo, in every format. Uses the same **Language** as the rest of the app Two identical copies (same format, cell size and code layout) can share changes. The editor asks once; the checkbox "Copy changes to: <font>" turns a pair on (off by default). A save copies the copy's own changes to the other copy, and the latest change per glyph wins; the log is font_sync.json in the project. If the other copy is open with unsaved edits, its file is not written: the glyphs wait there until it is saved or reopened, and the save message counts them. When a code of the translation map has no cell in the font, opening the font gives the code an empty cell in memory and marks the font unsaved: nothing is written until Save, and Save writes the map to the project (no project: the user's plugin folder, never `plugins/`). |
| Textures… | Ctrl+E export, Ctrl+I import, Ctrl+O open, F5 reload | Text baked into game textures (title cards, menu labels, logos) in a separate window; the project stays open. The textures the game's plugin names are listed with a thumbnail, the game file, the pixel format, the size and a status (Not started / Redrawn / Checked in game, kept in `<project>/textures/status.json`); the selected one is shown original next to translated. **Export PNG…** / **Export All…** save PNGs into a folder (default `<project>/textures/png`) under stable names made from the game file and member; redraw them in any image editor, then **Import PNG…** (one texture; another size is resized after a question) or **Import Folder…** (every PNG whose name matches). Picoripi encodes the image in the game's own format (GameCube/Wii BTI, TPL and BMD/BDL model textures, GBA tiles inside a packed multiboot program, 3DS BFLIM/BCLIM, CTPK and Grezzo CTXB (also the textures inside CMB models and CMAB animations) in ZAR/GAR/LzS archives, Wii U BFLIM and GX2 (GTX, TMPK packs), Switch BNTX (BC1-BC5, BC7, every ASTC block size; also the BNTX inside a model's BFRES), Koei Tecmo G1T, Retro TXTR (Metroid Prime 4), GBA / DS character tiles, N64 textures in the ROM, PlayStation TIM and headerless 4/8/16-bit pictures, Vagrant Story GIM screens, help sprites and the compressed title screen, Retro TXTR of the Wii Metroid Prime games, PSP GIM, Policenauts picture packs, Metal Gear Solid PCX and M2 PSB pictures, Level-5 IMGC and G4TX, Wii U BFRES textures) and writes the translation copy, repacking the archives around it, so the workspace's `2_build.bat` puts it into the mod; only the changed blocks are encoded again. **Revert** puts the original back. **File → Open Texture File…** opens a texture or an archive of them directly (games without a plugin, such as the 3DS ones); that file is then edited in place. PNGs exported from 3DS BCLIM and flag 0 BFLIM textures before this change were upside down or cut off; re-export them before editing. Not yet: BRRES model textures (Wii) |
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

**Loading fonts:** the Font Editor shows an indicator immediately while reading and decoding a project font. **Cancel loading** stops adopting that request. During glyph-table preparation, the status shows the completed and total glyph counts; the window stays responsive. Selecting another font keeps only the latest load result. Cancelling before the new model arrives preserves the previous font. Cancelling a partially filled table clears that table and disables it until another font is loaded. Closing the window discards late load callbacks; queued writes still finish in order.


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

Reference tabs appear only when that language has nonblank text for the selected row. A language missing from that row stays hidden.
Yo-kai Watch discovers existing language tables in the source/reference folders and workspace `romfs/*.fa` archives automatically.
Discovery runs in the background and reads game files without changing them. An explicit reference path takes priority.
Languages may cover only part of the game. A fan reference appears only where it contains matching text.
Yo-kai Watch in-game message window preview renders dialogue and system windows using Level-5 XF font glyphs, layout metrics, control tags ({CR}, {CG}, {CY}, {PAGE}), and route-aware hero substitutions ({PNAME} -> Nate / Katie).
Cross-platform translation reuse between 3DS and Switch shares accepted memory entries through the series registry; missing Switch layout measurements are treated as unverified candidates for manual confirmation and do not block permitted duplicate followers in batch runs.

**Source Panel (Left)**

- **Dynamic Reference Tabs**: When a reference patch or multi-language ROM / ISO is configured in project settings (**Settings → Project → File Paths → Reference Translation / ROM Path**), the panel dynamically generates comparison tabs (`Original (EN)`, `Russian (RU)`, `German (DE)`, `French (FR)`, `Italian (IT)`, `Spanish (ES)`). A game image the plugin unpacks first (an RVZ or ISO of another region) is read in the background into a folder of the project; that folder then becomes the reference path.
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

<!-- wiki-nav -->
---

**Previous:** [Recipes: I want to ...](Recipes.md) · [Back to the wiki index](README.md) · **Next:** [Keyboard shortcuts](Hotkeys.md)
