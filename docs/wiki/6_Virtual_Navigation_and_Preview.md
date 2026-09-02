# Virtual Navigation and Preview

The left **Blocks** tree mixes physical files with derived views. Physical rows stay the source of truth for save/load. Virtual folders only **group** existing strings.

## Physical tree

- Nested virtual folders (GitHub-style path compaction, e.g. `bmgres4.arc / zel_00.bmg`).
- Warning ticks (colored gutter strips) and `(N)` issue counts on files and compacted folder/block rows.
- Unsaved `*` on files and parents.
- Green progress fill for translation completion (empty/tag-only originals do not count).
- **Show Unsaved Only** above the tree hides files with no unsaved edits. This filter is **session-only**: a restart always unchecks it.

Expanding/collapsing a real folder only stores open/closed state. It does not rebuild the whole tree.

## Derived views

| Root | Meaning |
|------|---------|
| **Story** | Acts / chapters / scenes from MemePalace + manual Story Context |
| **Speakers** | Lines grouped by resolved speaker, plus `None` for unassigned **non-empty** lines |
| **Items** | Catalogue / item-get copy linked to reference items |
| **Windows** | Grouped by in-game message-window kind (Talk, Item Get, signs, …) |
| **Notated** | Lines with an explicit translator note |

Empty BMG padding slots stay in the **physical** file. They are **not** stuffed into Speakers / Windows / Items / Story / Notated. A kind that would only contain blanks (e.g. Item Get with 270 empty IDs) does not appear.

Clicking a physical file always loads that file’s strings, even if a parent folder is an aggregate. Clicking a virtual leaf loads only its mapped `(block, string)` rows.

## Strings in block (preview)

- Click a line to bind the translation editor to that row.
- **Hide empty strings** collapses long empty runs (this one *is* restored from settings).
- Page switcher (`n/N`) follows the last explicit action (preview click or editor line).
- For Twilight Princess, when the plugin declares `message_window_preview`, the BFN preview draws the official talk/item/sign chrome from a local dump (not bundled). Toggle **T/O** for translation vs original.

## Story Context fields

Above the editor: Window kind, Chapter/structure, Speaker, Item. These write the same assignments the virtual folders read. Dropping strings onto a virtual leaf assigns that facet.
