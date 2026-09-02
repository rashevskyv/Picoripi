# User Guide: Interface

This page is the map of the main window as built in `ui/builders/menu_builder.py`, `toolbar_builder.py`, and `layout_builder.py`. Labels below match the English UI.

Recommended order of work: [8. Localization Pipeline](8_Localization_Pipeline.md). Virtual folders and the in-game preview: [6. Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md). AI buttons: [11. AI Translation](11_AI_Translation.md).

---

## 1. Layout

```
+---------------------------------------------------------------------------------+
| File  Edit  View  Tools  Navigation  Bookmarks                         Help     |
+---------------------------------------------------------------------------------+
| Toolbar: Save  Undo Redo  Find  Preview  AI Chat  BFN  Recalc  Settings  >_  F1 |
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
| Left | Project tree: physical files plus derived virtual roots. Header: **Blocks (double-click to rename):** |
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
   - `zelda_bmg` — Zelda: Twilight Princess BMG
   - `zelda_mc` — The Legend of Zelda: The Minish Cap
   - `zelda_ww` — Zelda: The Wind Waker
   - `plain_text` — also labelled Zelda: The Wind Waker in its `config.json`
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
| Rescan All Issues | | Full warning scan |
| Recalculate Font Widths | Ctrl+Shift+R | Re-measure widths and re-scan every string. After fonts or width settings change |

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
| BFN Font Editor… | | Nintendo `.bfn` in a separate window; the project stays open |
| Script Markup Studio… | | Mark a walkthrough (Phase 0 for MemePalace). See [9](9_Script_Markup.md) |
| MemePalace Context Builder… | Ctrl+M | Weave the marked script into story memory |
| Prepare Glossary… | | One automatic glossary pass |
| Merge Speakers from Script… | | Match script names to game voice codes. Needs plugin capability `speaker_attribution` |
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
| Add Bookmark… | Ctrl+B | Current line of the active block |
| Clear All Bookmarks | | Permanent delete |

Bookmarks listed under the separator survive restart.

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

Save · Undo · Redo · Find · Preview · **Open AI Chat** (`Ctrl+Shift+C`) · BFN Font Editor · Recalculate Font Widths · Settings · (spacer) · **Run External Script** (`>_`) · Shortcuts Help.

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

Right-click (empty space): **Create Folder**, **AI: Translate All Blocks (UA Chronological)**, **Revert All Blocks to Original**, **Restore All Translations**.

Right-click a file: import, save this block, rescan, widths, markers, restore. **Chapters** root and Act folders have no context menu (read-only structure).

Status bar (bottom of the window): Original path, Changes path, Plugin name, `Strings: N | Unbound: N`, then cursor Pos / Line / Width.

---

## 12. Strings in block (top right)

Click a line to bind Original + Editable. The list itself is read-only.

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

## 13. Original and Editable

**Original**

- Read-only. Selectable.
- **Max-width:** click the value to copy it into the translation Max-width field, then press **Apply** on the right.
- **Hide tags** (`Ctrl+Q`).

**Column of icon buttons** (between the panes)

| Button | Action |
|--------|--------|
| Arrow | **Revert string** — replace the current translation with the original file content |
| Document+arrow | **Restore translation** — last backup (`Ctrl+Shift+T`) |
| S | **Inspect story context** (`Ctrl+I`) |
| R | **Open in Script Markup Studio** — jump to the marked-script place for this string |

**Editable**

- This is where you type.
- Title **Editable**.
- Under it: visual BFN preview (if Preview is on) with a window-kind bar when the plugin supports it.

**Do not** apply Font / Max-width without **Apply**. **Apply** is enabled only while there is an unapplied change.

---

## 14. Story Context (above Editable)

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
| **Global** | Theme (restart), Active Game Plugin (restart), font sizes, external script path, space dots, restore session, prompt editor before AI, live preview, real-time warning scan, glossary system, archive size warnings, auto-sleep idle delay |
| **Project** | Only with a project open. Subtabs: File Paths (Directory Mode, Auto-generate translation path, original/changes/fonts paths), Display, Rules, Context Tags, Tag Aliases, Font Map, Detection, Auto-fix (**Align sentences to original page layout**, **Prevent adding empty padding lines during pagination**, plus per-problem toggles) |
| **Spelling** | Enable spell checking, dictionary language, Manage Dictionaries… |
| **AI Translation** | See [11](11_AI_Translation.md) |
| **AI Glossary** | Provider, key, Use API key from AI Translation, model, chunk size, Parallel Requests, Retry Delay |
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
