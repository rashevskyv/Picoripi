# Script Markup Studio

**Language:** English · [Українська](uk/9_Script_Markup.md)

Opens from **Tools → Script Markup Studio…**, from pipeline step **Mark up the script**, or from the purple **R** button next to the editors (jump to the place linked to the current game string).

Implementation: `ui/script_markup_studio_dialog.py`. Logic: `core/script_markup/` (Qt-free). The in-window Help HTML is the product’s own description; this page follows that plus the menus/shortcuts in the same file.

---

## What it is for

Turns a raw walkthrough into the standardized script that MemePalace builders consume:

- `[Chapter:]` / `[Location:]` / `{Action:}` / `SPEAKER: text`

You work in **one** colour-coded view of the raw script. There is no second pane to keep in sync. **Preview result…** shows the finished file; **Export** writes it.

Colours (`_KIND_COLORS`):

| Kind | Colour | Meaning |
|------|--------|---------|
| Chapter | red-ish | Chapter header |
| Location | blue-ish | Location |
| Action | amber | Stage direction |
| Speaker / dialogue | green | Speech (adjacent speaker blocks alternate green/teal) |
| Ignored / dropped | grey | Not exported |
| Narration / blank | white | Unclassified / empty |

---

## Modes

Default is **Hierarchy markup**. **Picoripi rules** and **Custom recipe** live under **Advanced ▾ → Legacy tools**.

| Mode | Use |
|------|-----|
| **Hierarchy markup** (default) | Manual depth-indexed tree marks. Each mark has depth, type, label/text, colour. Exports canonical Markdown |
| **Picoripi rules** (legacy) | The program’s walkthrough parser (speakers and scenes). Best for already-structured scripts |
| **Custom recipe** (legacy) | Tunable rules plus teach-by-example, for messy raw walkthroughs |

The window is staged **1. Source — 2. Markup — 3. Review — 4. MemPalace**.

**File ▾:** Open script..., Open project..., Save, Save As..., Close. **Auto-fill ▾:** Join selected structures; Continue from marked examples... (local, no AI); AI mark missing.... **Advanced ▾:** Template, Export (**Preview result…**, **Export game_script.md…**), Change Type Color..., Legacy tools.

**Ctrl+M** in the **main window** is MemePalace Context Builder. **Ctrl+M inside Studio** marks the selection (or saves an in-progress edit). They are not the same command.

---

## Workflow

1. **Script → Open script...** — load the raw walkthrough.
2. *Hierarchy:* mark selections, review the script tree, then **Project**, **Template**, and **Auto-fill** when you need reusable marks or assisted fill-in.
3. *Picoripi rules / Custom recipe:* **Start from cursor** and **End at cursor** to cut table of contents, cast list, and legal front/back matter.
4. *Custom recipe:* tune checkboxes, or teach by example.
5. Watch colours and the Review queue; **Preview result…** to check.
6. **Export** the standardized script.

The pipeline wizard locates an existing markup project on disk and publishes `script_markup_studio_project_path` on the main window so the Context Builder does not ask you to browse the same file again.

---

## Navigation and search

- **Find:** type in the search box, **Enter** next match, **Shift+Enter** previous. **Aa**, **Word**, `.*` refine matching.
- **Minimap:** drag the right-side overview.
- **Script tree:** double-click a node or review item to jump to its source line.

---

## Keyboard shortcuts (Studio)

| Key | Hierarchy markup | Picoripi rules / Custom recipe |
|-----|------------------|--------------------------------|
| Ctrl+F | Focus Find | same |
| Ctrl+M | Mark selection with the chosen Type; while editing a node, save the edit | Mark selected/current lines as Action |
| Ctrl+I | Select Ignore; with a selection, mark it ignored | Mark as Ignore |
| Ctrl+S | Structure (with selection: mark; without: change Type picker) | — |
| Ctrl+P | Speaker | — |
| Ctrl+T | Text | — |
| Ctrl+B | Breaker | — |
| F2 | Rename selected script tree node (clicking an already selected node also opens rename; double-click still jumps) | |
| Ctrl+Z / Ctrl+Y | Undo / redo Studio changes | same |

---

## Hierarchy Markdown export

| Type | Renders as |
|------|------------|
| Structure depth 0 / 1 / 2 | `#` / `##` / `###` headings |
| Glossary | MemPalace source section; direct children become categories (Characters, Items, Locations, or custom names) |
| Speaker + Text | Marked separately, rendered together: `**MIDNA**: dialogue` |
| Action | Standalone square-bracket line: `[*Midna drops from a branch*]` |
| Unmarked | Does **not** count as done in the pipeline status probe |

Blank source lines are not “markable”. A stray empty line will not hold the pipeline step at `N / N+1` forever.

---

## Downstream consumers

- **Merge Speakers from Script…** matches marked names to game voice codes.
- **MemePalace Context Builder** imports the hierarchy timeline.
- Glossary auto-pass seeds character names from markup (`core/glossary_build/script_seeds.py`).
- **R** on the main window jumps from a game string to its marked place.

**Finish for MemPalace…** refuses to proceed while unmarked ranges remain.

**Do not** export and then edit the Markdown by hand if you still expect Studio to own the project — keep working in Studio and re-export.

**Do not** skip markup and expect Merge Speakers or glossary character seeds to be complete.
