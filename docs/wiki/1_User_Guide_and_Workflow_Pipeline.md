---
status: current
updated: 2026-10-03
owns: ui/, components/, dialogs/
tokens: 9.0k
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
   - `zelda_ww` — Zelda: The Wind Waker HD (Wii U): the `Message/*.msbt` and `Font/*.bffnt` taken out of `content/Common/Pack/permanent_2d_UsEnglish.pack` (one block per MSBT). Tags come from the game's `CKing.msbp` (`[Red]…[/C]`, `[Name]`, `[Wait:10]`, `[A]`); speakers, box width (875 font units in a talk box, 812 in signs and item boxes, 4 lines a page), conversations and glossary terms come from each message's attributes. An unedited file saves byte for byte. Load Reference Patch with a folder of `permanent_2d_<Region><Language>.pack` files (the workspace's `reference\`: the game's French and Spanish packs and the Russian patch's pack named `permanent_2d_RuRussian.pack`) shows those languages, Russian first, matched by file and label. Older projects of Kruptar `.txt` dumps still open
   - `zelda_sshd` — Zelda: Skyward Sword HD (Switch) and the Wii original (one plugin; the version is told by the source folder): the English `*.msbt` that `1_unpack.bat` takes out of the `.arc` archives (`US/Object/en_US/<area>/`, interface text `Layout/<name>/text/`), one block per file. Tags are named from the text (`{heroName}`, `{color:Red}`, `{item:11}`, `{icon:41}`, `{wait:15}`, `{choice1:65535}`); an unedited file saves byte for byte and `2_build.bat` packs the files back into the archives. Speakers (the HD's speaker byte, Fi's window, one-character files), conversations (the MSBF flows), line limits per window kind (the game breaks an over-long line mid-word, so keep within them; 4 lines a page) and glossary terms come from the game data. Load Reference Patch with the HD `romfs` folder shows the official Russian first and 12 more languages — also for a Wii project, matched by label
   - `zelda_mm64` — Zelda: Majora's Mask (N64): the US ROM itself (`.z64`, `.n64`, `.v64`) is the source file and the translated ROM the translation file. All 4,589 messages in one block; control codes as `{tags}` (zeldaret/mm); line width per textbox type, from the Font Editor's map of the game font once it is saved in the project, else from the game's own width table. Saving rebuilds the text file and the message table from the source ROM and fixes the header checksum. Speakers (one actor per line when the decompilation shows exactly one), scenes and seed glossary terms come from `context.json`, generated offline from zeldaret/mm and the ROM by `python -m plugins.common.zelda64_context`. Ukrainian letters are saved into the font slots of `translation_map.json` (the project's, else the plugin's): look-alike letters share the Latin glyph (А = A, і = i, Ї = Ï…), the rest take accented and unused punctuation slots chosen by width, so English stays readable; Ocarina of Time uses the same map. Load Reference Patch with the folder that holds `mm3d_seed.json` (Ukrainian carried over from Majora's Mask 3D, keyed by N64 message id) shows it as the "Ukrainian (MM3D)" reference
   - `zelda_oot64` — Zelda: Ocarina of Time (N64): the US 1.0 ROM, the same way as `zelda_mm64` (2,115 messages; codes from zeldaret/oot)
   - `zelda_tww` — Zelda: The Wind Waker (GameCube BMG): `res/Msg/bmgres.arc` of the US or a European disc (`data0`–`data4` are English, German, French, Spanish, Italian). Shares the Twilight Princess machinery; tags, colours and line widths come from the zeldaret/tww decompilation, line width and lines per page follow each message's box type. No speakers or window frames yet
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
     fonts: the Font Editor shows their glyphs but does not edit outlines;
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
     `LoveBug` has no Cyrillic, so it opens with a spare sheet for the Ukrainian letters
   - `zelda_fsae` — Zelda: Four Swords Anniversary Edition (DSiWare, Europe). **Source:** the workspace's `source`
     folder (`eu.kmsg` with the English text, `font_ltn.nftr`); **Translation:** `translation` (whole files; the
     workspace's `2_build.bat` rebuilds the DSi SRL and a CIA). All 220 messages, one block per id range (prologue,
     Chambers of Insight, items, Great Fairies, Vaati and the ending, in-game messages, system, credits); only the
     English (EU) slot is shown and saved, an unedited file stays byte for byte. The game's control codes are tags:
     `[speaker:1]`, `[wait:120]`, `[next:90]`, `[close]`, `[choice]`, `[center]`, `[icon:N]`, `[button:N]`, `[num:N]`,
     `[space:N]`, `[color:N]`; a line break is a real line break (the game does not wrap). Speakers come from
     `[speaker:N]` (Zelda, Vaati) and the Great Fairy messages; widths from the font (225 px in dialogue, 168 px in
     in-game messages, 240 px in menus). **Load Reference Patch** with the Russian build's `nitrofs` folder shows
     its Russian and the game's other languages. The Font Editor opens `font_ltn.nftr` with spare cells: a letter
     typed into one becomes a new character
   - `zelda_aoc` — Zelda: Hyrule Warriors Age of Calamity. Source is the workspace's `source` folder
     (`text\*.bin`, `battle\*.bin`: the game's text cut out of `data/LinkData2.bin`, one file per table
     with all its languages); the English table is shown and saved, and the workspace's `2_build.bat` packs
     the changed files and the edited font (`font\latin.g1n`) into the LayeredFS mod.
   - `yokai_watch` — Yo-kai Watch (3DS, USA). **Source:** the workspace's `source` folder (every English text
     table `*_en.cfg.bin` at its path inside the game archive `yw1_a.fa`, the fonts `fnt\*.xf`, the English menu
     textures); **Translation:** `translation`. The game's codes show in curly brackets (`{PAGE}` — next page of
     the 2-line message window, `{PNAME01}` — the hero's name, `{CG}…{/C}` — colour); story files exist twice,
     `_m` (Nate) and `_f` (Katie). Japanese leftovers and passwords are not shown; an unedited file stays byte for
     byte. Speakers come from the game's speaker tables in the workspace's `meta` folder. The Font Editor opens
     `ft_nrm` and `ft_sml` (format `xf`, real Ukrainian letters); the Textures window lists 594 English textures
     (`imgc`). The workspace's `2_build.bat` rebuilds `yw1_a.fa` into the LayeredFS mod. Yo-kai Watch 3 (EUR, workspace
     `YOKAI_WATCH_3`) opens with the same plugin: its English text is in `data/txt/ev/en` and the archive
     `yw_lg_en.fa`; the hero of a line comes from its voice clip (`{PV#pv_c001000_23}`: Nate).
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
     descriptions and memory-card dialogs, each in its own window). Credits, titles, HUD labels and menu words
     are pictures, not text (`TWIN_SNAKES\reports\visible_text_inventory.md`). `common\mgso.rel` (the game
     module) gives one block of HUD words — LIFE, O2, the item and weapon box labels, boss names: the HUD font
     has only ASCII letters and each word has a fixed number of bytes, so a save refuses Cyrillic or a word
     longer than its slot.
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
| Font Editor… | | Bitmap fonts in a separate window; the project stays open. Opens Nintendo `.bfn` (Twilight Princess, Wind Waker), the message font inside an N64 Zelda ROM (OoT, MM), Hyrule Warriors `.g1t` atlases, Age of Calamity `.g1n` fonts, Switch and Wii U `.bffnt` (The Wind Waker HD: big-endian, GX2-tiled sheets), Wii `.brfnt` (Skyward Sword HD and Wii: GX I4 sheets) and the 3DS fonts: `.bcfnt` / 3DS `.bffnt` (A Link Between Worlds, Tri Force Heroes), Grezzo `.qbf` (Ocarina of Time 3D) and `.gzf` (Majora's Mask 3D), and the Switch scalable fonts `.bfotf` (Tears of the Kingdom: all their glyphs are shown; outlines and widths are not edited here), 2bpp text font of Metal Gear Solid: The Twin Snakes (from its project only), Nintendo DS `.nftr` (Four Swords Anniversary Edition) — open them with **Open** (no project needed; Save writes the file back). In a font that maps Unicode characters (`.bffnt`, `.g1n` and the 3DS fonts), typing a letter into an empty cell's character column adds that real character to the font (no translation slot; a character the font already has is refused): draw the glyph in a free cell and give it its letter. The game's own fonts, named by its plugin, are listed in the font tree and open from the project (the translation copy once there is one); Save writes the translation copy and the font's widths with the translation map to `<project>/font_maps/`, which the width checks read. Hyrule Warriors DE takes its advances from a table in the game's executable, not from the atlas: the editor shows that table (in atlas pixels) and Save also writes it as executable patches `exefs/<build id>.ips` in the translation folder, one per game version (the workspace's `2_build.bat` puts them into the mod). Wind Waker also lists its name-entry and system fonts. **Render System Font to Glyphs** takes a TTF/OTF through **Font File...** (no install needed) and can **Thicken** strokes for small heavy fonts; with baseline alignment each rendered letter is moved to stand on the font's own Latin baseline (р у ф hang like p, д ц щ line up by their top); **Move glyph** (◀ ▲ ▼ ▶ or Ctrl+Arrow keys) shifts the selected glyphs' pixels 1 px inside their cells, with undo, in every format. Uses the same **Language** as the rest of the app |
| Textures… | Ctrl+E export, Ctrl+I import, Ctrl+O open, F5 reload | Text baked into game textures (title cards, menu labels, logos) in a separate window; the project stays open. The textures the game's plugin names are listed with a thumbnail, the game file, the pixel format, the size and a status (Not started / Redrawn / Checked in game, kept in `<project>/textures/status.json`); the selected one is shown original next to translated. **Export PNG…** / **Export All…** save PNGs into a folder (default `<project>/textures/png`) under stable names made from the game file and member; redraw them in any image editor, then **Import PNG…** (one texture; another size is resized after a question) or **Import Folder…** (every PNG whose name matches). Picoripi encodes the image in the game's own format (GameCube/Wii BTI and TPL, 3DS BFLIM/BCLIM, CTPK and Grezzo CTXB in ZAR/GAR/LzS archives, Wii U BFLIM, Switch BNTX, Koei Tecmo G1T, N64 textures in the ROM) and writes the translation copy, repacking the archives around it, so the workspace's `2_build.bat` puts it into the mod; only the changed blocks are encoded again. **Revert** puts the original back. **File → Open Texture File…** opens a texture or an archive of them directly (games without a plugin, such as the 3DS ones); that file is then edited in place. Not yet: ASTC (Tears of the Kingdom's logo colour layers), textures inside models (BMD/BDL/BFRES/CMB) |
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
