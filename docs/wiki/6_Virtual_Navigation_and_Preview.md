# Virtual Navigation and Preview

**Language:** English · [Українська](uk/6_Virtual_Navigation_and_Preview.md)

The left **Blocks** tree mixes physical files with derived views. Built in `ui/updaters/block_list_updater.py`. Physical rows are the source of truth for save/load. Virtual folders only **group** existing strings.

---

## Physical tree

- Nested folders. Compacted archive paths look like `bmgres4.arc / zel_00.bmg`.
- Warning ticks (coloured gutter) and `(N)` issue counts on files and compacted rows. Tick data is stored on the item (UserRole+20) so labels are not doubled as `Name (1) (1)`.
- Unsaved `*` on files and parents.
- Green progress fill: translation completion. Empty / whitespace / tag-only originals do not count.
- **Show Unsaved Only** above the tree hides files with no unsaved edits. Session-only: a restart always unchecks it (`AppDataStore.from_snapshot` forces both unsaved filters off).

Expanding or collapsing a **physical** folder only stores open/closed state. It does **not** rebuild the whole tree or re-populate every block.

Clicking a physical file (`UserRole >= 0`) always loads that file’s strings, even if a parent looks like an aggregate.

---

## Derived roots

Stable names on UserRole+4:

| Root | Meaning |
|------|---------|
| **Story** | Acts / chapters / scenes from MemePalace + Chapter combo |
| **Speakers** | Lines grouped by resolved speaker, plus `None` for unassigned **non-empty** lines |
| **Items** | Item-get / catalogue copy linked to reference items |
| **Windows** | Grouped by in-game message-window kind |
| **Notated** | Lines with an explicit translator note (`UserRole == -5`) |

Empty BMG padding stays in the **physical** file. Virtual roots skip blank rows (`_is_blank_row`). A kind that would only contain blanks does not appear.

Clicking a virtual leaf loads only its mapped `(block, string)` rows.

**⟳ Rebuild virtual folders** on the tree toolbar rebuilds Speakers / Chapters / Items from current story data. Translation files are not touched.

Dropping strings onto a virtual leaf assigns that facet (speaker, chapter, …). **Chapters** root and Act folders have no right-click menu.

---

## Strings list vs editor

- Click a line in **Strings in block** to bind Original + Editable.
- **Hide empty strings** collapses consecutive empties to a placeholder (this filter **is** restored from session).
- **Show Unsaved Only** on the strings list is **not** restored.
- **Show Warnings Only** + **Warnings: X / Y** uses Detection-enabled problem ids from the plugin.

---

## Visual preview

**View → Preview** (`Ctrl+Shift+P`), also the toolbar Preview action. Under Editable: `BfnPreviewWidget` + `BfnPreviewWindowBar`.

When the plugin declares `message_window_preview` (Twilight Princess BMG), the preview can draw talk / item-get / sign chrome from a **local** game dump. The repo does not ship Nintendo assets. Page `n/N` and original/translation (`T`/`O`) sit on that bar.

**Global → Enable Live Preview** turns the live simulator off to reduce lag.

**Do not** expect TP window frames without a legal local dump and the Zelda BMG plugin.

---

## Story Context fields

Above Editable: **Window:**, **Chapter:**, **Speaker:**, Font / Max-width. Same assignments the virtual folders read.

- Double-click **Window:** → physical game block.
- Double-click **Chapter:** → virtual Chapter.
- Double-click **Speaker:** → virtual Speaker or Item.
- `None` in Speaker clears the assignment.

**Do not** invent speakers for empty padding slots; those rows are not in Speakers.
