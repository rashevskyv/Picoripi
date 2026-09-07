---
name: update-wiki
description: Keep Picoripi docs/wiki and README.md in sync with user-visible product changes, new features, moved or rearranged UI menus, dialog controls, and settings. Trigger: /update-wiki, "онови вікі", "update-wiki", "онови документацію".
---

# Update Picoripi Wiki & README

This skill defines the canonical workflow for keeping `docs/wiki/` and `README.md` synchronized with codebase changes — especially when new functions/capabilities are added, or when UI menus, dialogs, and controls are relocated or restructured.

## When to Run

- **Explicit trigger**: The user says `/update-wiki`, "онови вікі", "оновлення вікі", "update wiki", "update readme".
- **Automatic rule**: After implementing or modifying any user-visible feature, adding plugin hooks, changing shortcuts, or moving/rearranging UI controls (menus, dialog tabs, checkboxes, buttons).

---

## Operating Principles

1. **Source of Truth First**: Never write documentation from memory or stale docs. Always inspect the actual Python/UI source code (`ui/`, `components/`, `dialogs/`, `handlers/`, `plugins/`) and strings in `tr("...")` and `locales/uk.json`.
2. **Single Responsibility**: Each fact has one owning wiki page (defined in `docs/wiki/7_Maintaining_This_Wiki.md`). Do not duplicate full how-to text across multiple pages.
3. **Bilingual Synchronization**: Every change to an English wiki page (`docs/wiki/*.md`) must be mirrored in its Ukrainian counterpart (`docs/wiki/uk/*.md`). In Ukrainian pages, use the exact UI wording from `locales/uk.json`.
4. **README.md Reflection**: When a feature is added, changed, or when main entry points / UI controls move, organically update `README.md` (in "Core Features", specialized component overviews, or the "Documentation Map"). Do not paste the full wiki into README; keep it clear, concise, and structural.

---

## Step-by-Step Workflow

### Step 1: Detect Deltas from Git

Inspect recent changes:
```powershell
git status --short
git diff HEAD~1 --stat
```
Identify:
- **New functions / plugin contracts**: e.g., `BaseGameRules.get_external_reference_url(term)`.
- **Relocated / restructured UI controls**: e.g., filter checkboxes moved from a search bar to a table footer, side-by-side grid layouts, collapsible panels, rebalanced column widths.
- **Menu changes**: new or renamed menu items in `File`, `Edit`, `View`, `Tools`, `Language`, `Navigation`, `Bookmarks`, or `Help`.
- **Toolbar & shortcuts**: new toolbar buttons, modified keyboard shortcuts or modifier clicks (Ctrl+Click, Shift+Click).
- **Settings & configuration**: new keys in `settings.json`, `.env`, or session checkpointing.

### Step 2: Verify Exact Names & Behavior in Code

- Read the widget creation and signal binding code in the corresponding Python files.
- Identify the exact literal in `tr("...")`.
- Verify the Ukrainian translation in `locales/uk.json`.
- Note the visual placement (e.g. "directly underneath the terms table `_tab_widget`", "aligned side-by-side in `QGridLayout` with fixed height 26px").

### Step 3: Update Owning Wiki Pages (`docs/wiki/`)

Consult `docs/wiki/7_Maintaining_This_Wiki.md` for page ownership:

| Topic / Change Area | Owning Wiki Page |
|---------------------|------------------|
| Menus, toolbar, dialogs (Glossary, etc.), shortcuts, layout | `docs/wiki/1_User_Guide_and_Workflow_Pipeline.md` |
| Core architecture, data store, handlers, delegates | `docs/wiki/2_API_Reference.md` |
| Plugins (`BaseGameRules`, hooks, capabilities) | `docs/wiki/3_Plugin_Developer_Guide.md` |
| Configuration, settings, environment, session | `docs/wiki/4_Configuration_Guide.md` |
| Gemini Web2API proxy, batch translation, models | `docs/wiki/5_Gemini_Web2API.md` |
| Virtual folders, preview widget, filter buttons | `docs/wiki/6_Virtual_Navigation_and_Preview.md` |
| Wiki maintenance table & ownership | `docs/wiki/7_Maintaining_This_Wiki.md` |
| Localization Pipeline wizard & automated passes | `docs/wiki/8_Localization_Pipeline.md` |
| Script Markup Studio | `docs/wiki/9_Script_Markup.md` |
| AI Translation, variations, prompts, AI chat | `docs/wiki/11_AI_Translation.md` |

For each modified page:
1. Update the English file (`docs/wiki/<Page>.md`).
2. Update the Ukrainian twin file (`docs/wiki/uk/<Page>.md`), using approved terms from `locales/uk.json`.
3. If an entirely new page is required, update `docs/wiki/7_Maintaining_This_Wiki.md` and `docs/wiki/README.md` (and Ukrainian twins) first.

### Step 4: Update `README.md`

Check whether the changes warrant updates to `README.md`:
- **Core Features**: If a new feature or user-visible workflow was added, add or update a descriptive bullet point in the "Core Features" section.
- **UI & Components**: If major dialogs or widgets (such as the Glossary Dialog, Preview Widget, or Search Panel) were rearranged, reflect their current ergonomics and controls in the relevant component summary.
- **Documentation Map**: If new wiki pages or workflow guides were added, add corresponding links to the map.

### Step 5: Propagate Plugin Capabilities (Mandatory)

If a plugin gained a new capability or hook (e.g. external wiki lookup, speaker attribution, custom preview mode):
- Update `docs/PIPELINE_ROADMAP.md` (design of record).
- Update `docs/PLUGIN_AUTHORING_GUIDE.md` Section 4.
- Update `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` Question 8.

### Step 6: Quality & Validation Checks

1. **Verify Git diff**:
   ```powershell
   git diff --check
   ```
2. **Run Linter**:
   ```powershell
   .\venv\Scripts\python.exe -m ruff check .
   ```
3. **Verify Links & Content**:
   Ensure all file/markdown links exist and no sensitive data (passwords, cookies, machine-local absolute paths) was introduced.
