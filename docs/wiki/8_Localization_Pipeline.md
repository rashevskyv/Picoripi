# Localization Pipeline

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
- Button: **Run automatic glossary pass**.

Status: empty → “automatic pass not run”; else `N terms; M awaiting review` (unconfirmed entries). Partial until the review backlog is empty.

Manual glossary: **Glossary…** / `Ctrl+G`. Same store.

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

### 5. Translate the text (`text`)

No run button. Translation is done in the editor (**AI Translate**, selection right-click, tree **AI: Translate All Blocks**).

Status: non-empty rows whose current text differs from the original. Lines kept identical (names, numbers) undercount on purpose.

See [11. AI Translation](11_AI_Translation.md).

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
