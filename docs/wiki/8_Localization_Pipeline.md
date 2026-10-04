---
status: current
updated: 2026-10-03
owns: core/glossary_build, core/glossary
tokens: 4.0k
purpose: Pipeline wizard: script, glossary build, reconcile
---
# Localization Pipeline

**Language:** English · [Українська](uk/8_Localization_Pipeline.md)

Open with **Tools → Localization Pipeline…**. Window title: **Localization Pipeline**.

The dialog is deliberately thin (`ui/pipeline_wizard_dialog.py`): it computes no pipeline of its own. Every button runs the same `QAction` as the Tools menu. Steps that are whole workflows are **embedded** in the right pane instead of opening a second window.

Left: a tree of steps with a status icon and a count. Right: the tool, or an explanation plus a run button. Footer: **Refresh** and **Close**. Coming back to the window re-reads the project after 250 ms.

Headline: `Localization pipeline — N / M steps complete`.

| Icon | State (`core/pipeline_status.py`) |
|------|-----------------------------------|
| ⚪ | not started |
| 🟡 | partial |
| ✅ | done |

---

## Which steps you see

`steps_for(plugin.get_capabilities())`. An empty capability set is valid: you still get every step that works on extracted text. A step with `requires="…"` appears only if the active plugin declared that name.

Recognised capability names (from `plugins/base_game_rules.py`):

| Capability | What the plugin must implement | Wizard effect |
|------------|--------------------------------|---------------|
| `glossary_seed` | `get_glossary_seed_entries()` | Seeds the glossary from game data |
| `external_lore` | `get_external_lore(term)` | Extra describe-pass material |
| `speaker_attribution` | `get_speaker_for_string()` | Shows **Name the speakers** |
| `message_window_preview` | window chrome / pagination | Preview chrome (not a wizard step) |

Twilight Princess (`plugins/zelda_bmg`) declares all four. **Default Plugin Template** declares none.

---

## The steps (as shipped)

Order in `STEPS`:

### 1. Mark up the script (`markup`)

Embedded: Script Markup Studio (Close hidden; host Close is the wizard’s).

A walkthrough is prose. Markup says which line is a speaker and which is speech. Merge Speakers and the Context Builder read this file.

Status: markable (non-blank) source lines covered by approved marks, excluding type Unmarked. “No script found for this game” vs “script not marked up” are different.

**Do:** finish markup before Merge Speakers. **Do not** skip it and hope ALL-CAPS guessing will name the cast.

Details: [9. Script Markup](9_Script_Markup.md).

### 2. Name the speakers (`speakers`) — child of markup

Shown only if `speaker_attribution` is in capabilities.

Button: **Merge speakers from the script** → `merge_speakers_action`.

The game groups lines by voice (`Voice 8`, placement names). The script has display names. This joins them on line text (`SpeakerMergeHandler.merge_from_script`). Needs an open project and `get_speaker_for_string`. If markup speaker lines are missing, it may guess from ALL-CAPS and warn. Apply saves aliases beside the project. Names then reach the Speaker field, virtual folders, translation prompts, and glossary seeds.

Status: named placeholder codes / total placeholder codes the plugin still reports.

**Do** merge before a glossary auto-pass if you want characters seeded under the decided name rather than `CLERK_B`. **Do not** vote a script line onto the plugin’s `System` speaker (TP: signs, credits, item windows, location plates, howling stones, boss cards).

### 3. Build the story context (`context`)

Embedded: MemePalace Context Builder (its own Close / Done buttons are hidden; Stop stays while a job runs).

Copies markup into MemePalace and links each game line to a place in the story.

Window title **MemPalace Context Builder**. Tab **1. Source**: **Select project…**, **Import/Sync**, **Continue to Story Context →**. Then:

- **Step 1 — Find Context Automatically** — no AI.
- **Step 2 — Build Timeline with AI**
- **Step 3 — Analyze Character Voices with AI**

Steps 2–3 need an AI provider. They do not invent glossary terms and they do not replace Merge Speakers.

Status: all-or-nothing — “story context built” if a MemePalace DB path exists, else “no story context yet”.

Without this step, translation still works as “translate this sentence”. With it, the prompt can know the scene.

**Do** run step 1 before timeline/voices. **Do not** expect voices to work before lines are linked.

### 4. Prepare and enrich the glossary (`glossary`)

Embedded: **Prepare Glossary** (`GlossaryPipelineHandler` with `target_step="auto"`).

One automatic pass:

1. Seed terms from game data (`get_glossary_seed_entries`) and from Script Markup characters.
2. Rename seeds using Merge Speakers aliases (one voice that names several characters becomes several terms, never `"A / B"`).
3. Sweep selected project blocks for missing terms.
4. Build descriptions from available context.
5. Propose translation variants.

The pass does **not** stop for questions. Ambiguities stay as AI notes / review backlog.

UI (auto mode):

- **Project blocks:** **Whole project** plus a checkable list. Area radios are hidden.
- **Also propose translations now** is on and hidden.
- Optional: **Re-scan every selected block with AI** (normally only new/changed blocks).
- Optional: **Resume unfinished entries only** when some terms still need description or translation.
- Optional: **Force re-translate already translated terms** to re-translate all entries using current rules, overwriting existing translations.
- Optional: **Reconcile related terms afterwards** to compare related entries after translating and make them agree (see below).
- Button: **Run automatic glossary pass**.

Status: empty → “automatic pass not run”; else `N terms; M awaiting review` (unconfirmed entries). Partial until the review backlog is empty.

Manual glossary: **Glossary…** / `Ctrl+G`. Same store. Features a direct **Force Retranslate...** button (with automatic `glossary.json.bak` backup creation) to re-translate all terms via AI and update proposals in place. When a reference patch is loaded, reference variants from external patches are styled distinctly (cyan/italic), blocked from double-click application, and kept separate in AI notes (with automatic context from mention lines when no explicit variant exists).

**Do** configure AI first ([11](11_AI_Translation.md), [5](5_Gemini_Web2API.md)). **Do not** treat unconfirmed entries as a blocker for translating text.

Other launch titles exist in `GlossaryBuildDialog` for non-auto routes (**Sweep Text with AI**, **Describe Glossary Terms**, **Build Glossary from Text**) with depths:

| Radio | Meaning |
|-------|---------|
| Thorough (recommended) | Sweep, then describe from every occurrence |
| Draft (fast, rough) | One sweep; first-seen descriptions; unconfirmed |
| Structural seed only (no AI) | Game tables + markup names only |
| Augment existing entries | Describe existing terms; no sweep |
| Translate existing entries only | Propose translations for described-but-untranslated terms |

Chunk size: Local / small (2000), Balanced (4000), Cloud / large (8000).

#### How the glossary stays consistent

- **One term, one entry.** A term a build finds is matched to existing entries by exact spelling, then case and spacing, then alias, then a canonical key that folds plurals, articles and possessives. `Rupees` found in a later chunk goes into `Rupee`; it does not become a second entry. A term you add by hand is added as written. Entries that already share a canonical key are listed in the log on load and are never merged automatically.
- **Same input, same glossary.** Results are applied in a fixed order whatever order the requests answer in; a term is named by its most common spelling in the text.
- **Requests know what is decided.** Each sweep chunk and each term translation is shown the settled entries that share a word with it (up to 40, a person's decisions first). One-word terms are translated first, then two-word terms, then longer ones, and related terms one after another, so `Clawshots` is translated knowing what `Clawshot` got and `Zora Armor` knowing `Zora`.
- **Reconcile (optional).** After translating, entries that are one term spelled differently or that share a word are compared, one request per group that looks off. Spellings of one term are merged (the other spelling stays as an alias, its translation as a variant); translations are aligned to a shared root. Confirmed entries are never changed. Every change is listed in the report and in the log, and running the pass again changes nothing.
- **What reaches a translation prompt.** Glossary rows for terms in the text, plurals included (`Rupees` finds `Rupee`). A term found only inside a longer term is not listed on its own (`Lake Hylia`, not also `Hylia`). Entries without a translation are left out. At most 40 rows: confirmed and hand-written entries first, then machine-translated ones; notes are cut to 300 characters in the prompt (the editor keeps the full note).
- **Storage.** A build pass writes the glossary file every 20 results and at the end, replacing the file in one step. Every entry has a stable `id`. A deleted or merged entry leaves a `deleted_at` record in the file so that a Companion sync does not bring it back; a renamed entry is matched by id. A re-sweep adds evidence to a translated entry instead of resetting it.

#### Series glossary (shared by the games of a series)

One glossary for several projects of the same series (for example every Zelda game). It is a separate `glossary.json`-shaped file, by default in `~/.picoripi/series_glossaries/` (`core/glossary/series.py`); the project keeps only the link (`series_glossary` in the `.uiproj` metadata; a project without it has no series glossary).

- **Link it:** **Glossary…** (`Ctrl+G`) → **Series Glossary...** → **New Empty Series Glossary...**, **Link or Import Series Glossary...** or **Unlink Series Glossary**. A file in the `glossary.json` shape is linked where it is and edited in place. Any other glossary JSON — a `{"terms": [...]}` series document with per-source `renderings`, `recommended`, `status`, `options`, `note`, `aliases` — is converted into the series folder first: `recommended` becomes the translation, each distinct rendering a variant (its sources and extra forms as the rationale), `options` more variants, `category` the category; `agreed`/`resolved` terms are confirmed, `decision`/`proposed` ones stay under review, and the original status, games and reason go to the AI-notes field.
- **The tab:** the Glossary window shows **Project Glossary** and **Series: <file name>** side by side, with the same table, search, category tabs and editor. Select terms (`Ctrl`/`Shift`+click) and press **Copy to Project Glossary** in the series tab or **Promote to Series Glossary** in the project tab; a term the other glossary already has takes the copied translation and keeps its own fragments and notes. A term both glossaries translate differently is red in both tabs, with the other translation in the tooltip.
- **In AI prompts:** the project glossary comes first and wins. Series rows are added only for terms of the text the project glossary does not translate, in a separate `series_glossary` field (batch) or **SERIES GLOSSARY** section (single line) marked as lower priority.
- **Builds** write only the project glossary; the series file changes only through the series tab or **Promote to Series Glossary**.

### 5. Translate the text (`text`)

Features embedded action buttons directly in the right pane:
- **Translate Story First (Chronological)**: Translates main narrative dialogue lines in chronological order, so the story text is settled first.
- **Translate Remaining Blocks (Semantic & System)**: Translates menus, shops, and system text after the story, with the same glossary and per-line context.
- **Run Full Pipeline (Story ➔ Semantic)**: Runs the complete automated multi-agent pipeline (Story first, then the remaining blocks).

Translation can also be triggered from the editor (**AI Translate**, selection right-click, main toolbar **AI** button, or **Tools → AI Batch Translation ➔**).

Status: non-empty rows whose current text differs from the original. Lines kept identical (names, numbers) undercount on purpose.

See [11. AI Translation](11_AI_Translation.md).

---

## Appendix: the automatic glossary pass in detail

**Where it starts.** **Tools → Prepare Glossary…**, the wizard step **Prepare and enrich the glossary**, and the
button inside the Glossary dialog all open the same route. The internal modes (`seed`, `thorough`, `augment`,
`translate`) remain as building blocks; nobody has to run them in order.

**Files.** The glossary is `<project folder>/glossary.json`. Beside it the pass keeps `glossary.scan.json`:
fingerprints of the blocks already swept. It is bookkeeping for incremental runs, not a second glossary.

**Scope.** With only part of the project ticked, global structural entries that belong to no block are not
mixed into the partial pass. A block whose content did not change is not swept again; **Re-scan every selected
block with AI** forces the long full sweep and still does not overwrite anything a person confirmed.

**What merges.** An exact normalized match joins an existing entry without touching confirmed translations and
descriptions. A fuzzy match never merges by itself — the pair is shown for a person to decide.

**In the Glossary dialog** the data is kept apart: **Description** (the clean summary used for translation),
**Proposed variants** (candidates with a rationale each), **AI notes and unresolved choices** (sweep
observations, alternative translations, evidence of who a character is, possible duplicates), **Occurrences**.

**The report** after a pass shows a remainder instead of "done": entries awaiting review, entries with several
variants, entries without a translation or a description, possible duplicates. **Review glossary** opens the
queue; **Continue in editor** returns to translating even when the queue is not empty.

**Checking a pass by hand** (ten minutes, two small blocks):

1. Run the pass for the two blocks only: seed → sweep → describe → translate go through without a pause.
2. In the Glossary dialog, description and AI notes are in different panes; an ambiguous term has several
   variants with different rationales.
3. Run the same blocks again: nothing is swept. Change one string in one block and run again: only that block is swept.
4. Confirm a translation by hand and run again: it stays. Tick the full re-scan: sources are read again, the
   confirmed entry still stays.

---

## Recommended order

1. Markup  
2. Merge Speakers (if the plugin has `speaker_attribution`)  
3. Context Builder step 1 (optional 2–3)  
4. Prepare Glossary  
5. Translate in the editor, with glossary + speaker + scene in the prompt  

You can still open every tool from **Tools** without the wizard.

---

## What not to do

- Do not start Merge Speakers with no marked script (the step has to guess from ALL-CAPS).
- Do not run the glossary auto-pass expecting it to pause for review.
- Do not set Parallel Requests above the number of Active proxy accounts.
- Do not treat “N / M rows translated” as a QA score; identical-correct lines look untranslated.
- Do not document or wait for items that exist only in `docs/PIPELINE_ROADMAP.md` — that file is planned work, not this wizard.
