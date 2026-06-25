# Walkthrough — Dynamic Target Language Selection (AUD-L1)

This document summarizes the changes, testing, and validation completed to implement the dynamic target language selection (AUD-L1) in Picoripi.

## Overview

The purpose of AUD-L1 is to fully de-hardcode the target language ("Ukrainian") from the codebase and AI prompts. This ensures the application dynamically supports any user-selected target language (e.g., Spanish, German, etc.) while maintaining backward compatibility for existing glossary prompts, plugin templates, and timeline databases.

All default prompt templates have been refactored to use neutral English instructions with `{target_lang}` placeholders, preventing Cyrillic character leakages during non-Ukrainian translation sessions.

## Affected Files

The dynamic target language selection affects the following components:

### Core & Settings
* **[core/context.py](file:///d:/git/dev/Picoripi/core/context.py)**: Added `target_language` property to the `ProjectContext` protocol to decouple UI target language from business logic handlers.
* **[core/settings/global_settings.py](file:///d:/git/dev/Picoripi/core/settings/global_settings.py)**: Added `target_language` default ("Ukrainian") and serialization safeguards to ensure properties are saved correctly.
* **[core/translation/session_manager.py](file:///d:/git/dev/Picoripi/core/translation/session_manager.py)**: Updated history compression prompt to use the centralized helper to dynamically inject target language.
* **[core/translation/story_context_manager.py](file:///d:/git/dev/Picoripi/core/translation/story_context_manager.py)**: Conditionally injects Ukrainian-specific grammar guidelines (such as `ти/ви` formality checks) when `target_language` is Ukrainian (case-insensitive and stripped), and falls back to a neutral guideline for other languages.
* **[core/mempalace/chapter_ai_analyzer.py](file:///d:/git/dev/Picoripi/core/mempalace/chapter_ai_analyzer.py)**: De-hardcoded "Ukrainian" from chapter analysis system and user prompts, using the dynamic `self.target_lang` instead. Switched the JSON key requirement from `summary_ukrainian` to `summary_translated`.
* **[core/mempalace/character_profiler.py](file:///d:/git/dev/Picoripi/core/mempalace/character_profiler.py)**: Normalized target language equality checks to be case-insensitive and stripped (using `self.target_lang.strip().lower() == "ukrainian"`).

### Handlers & Prompts
* **[utils/utils.py](file:///d:/git/dev/Picoripi/utils/utils.py)**: Implemented the centralized helper `resolve_target_language_prompt(text, target_lang)` that replaces `{target_lang}` placeholders and provides legacy `Ukrainian` fallback replacement. Documented the legacy fallback contract explicitly.
* **[handlers/translation/ai_prompt_composer.py](file:///d:/git/dev/Picoripi/handlers/translation/ai_prompt_composer.py)**:
  * Refactored all target language retrievals to route through the centralized `_get_target_lang()` helper.
  * Replaced manual inline string replacements with the helper `resolve_target_language_prompt`.
* **[handlers/translation/glossary_handler.py](file:///d:/git/dev/Picoripi/handlers/translation/glossary_handler.py)**: Used the centralized helper in prompt formatting.
* **[handlers/translation/glossary_prompt_manager.py](file:///d:/git/dev/Picoripi/handlers/translation/glossary_prompt_manager.py)**: Used the centralized helper in default template prompts and loaded files.
* **[handlers/translation/glossary_builder_handler.py](file:///d:/git/dev/Picoripi/handlers/translation/glossary_builder_handler.py)**: Resolved the target language dynamically using the centralized helper before sending glossary building prompts to AI.
* **[plugins/common/defaults/prompts.json](file:///d:/git/dev/Picoripi/plugins/common/defaults/prompts.json)**: Fully converted prompts to neutral English using `{target_lang}` placeholders, omitting Cyrillic text and Ukrainian-only grammar rules.
* **[translation_prompts/prompts.json](file:///d:/git/dev/Picoripi/translation_prompts/prompts.json)**: Rewritten as a neutral, English-based prompts file with `{target_lang}` placeholders to prevent Cyrillic characters from leaking into other languages.
* **[translation_prompts/glossary_builder_prompts.json](file:///d:/git/dev/Picoripi/translation_prompts/glossary_builder_prompts.json)**: Fully converted to a neutral English prompt with `{target_lang}` placeholders.
* **[plugins/zelda_mc/translation_prompts/prompts.json](file:///d:/git/dev/Picoripi/plugins/zelda_mc/translation_prompts/prompts.json)**: Updated the plugin prompt file to be neutral English with `{target_lang}` placeholders.

### UI & Dialogs
* **[ui/settings/settings_ui_setup.py](file:///d:/git/dev/Picoripi/ui/settings/settings_ui_setup.py)**: Added a "Target Language" QLineEdit input field to the settings page.
* **[ui/settings_dialog.py](file:///d:/git/dev/Picoripi/ui/settings_dialog.py)**: Wired UI input text fields to set and retrieve settings and update main window properties.
* **[ui/mempalace_builder_dialog.py](file:///d:/git/dev/Picoripi/ui/mempalace_builder_dialog.py)**: Replaced dependencies on spellchecker code with the configured target language for character profiling and script analyses.
* **[ui/main_window/mempalace_actions.py](file:///d:/git/dev/Picoripi/ui/main_window/mempalace_actions.py)**:
  * Implemented safe fallback for story events retrieval using `summary_translated` (checks `summary_translated`, `summary_ukrainian`, and `summary` key names to ensure full backward compatibility with older local timeline databases).
  * Fully translated Cyrillic/Ukrainian UI strings and relations formats to English to satisfy the global application language policy.

---

## Detailed Changes

### 1. Centralized Language Placeholders Resolution
Instead of broad string replaces (`.replace("Ukrainian", target_lang)`) across the whole code, the resolution has been centralized to `resolve_target_language_prompt` in `utils/utils.py`.
```python
def resolve_target_language_prompt(text: str, target_lang: str) -> str:
    """Centralized helper to resolve target language placeholders in AI prompts.

    Main workflow:
      Replaces "{target_lang}" with the resolved target language (e.g. "Spanish").
      This is the primary and recommended path for all bundled and custom prompts.

    Legacy Fallback:
      Also replaces the literal word "Ukrainian" with target_lang for backward
      compatibility with older user files or plugins.

      WARNING: This replacement is a simple string replacement and CANNOT automatically
      translate Ukrainian text, Cyrillic letters, grammar-specific examples, or rules
      into the target language. Bundled prompts should rely on explicit {target_lang}
      placeholders and neutral English instructions.
    """
    if not text:
        return ""
    if not isinstance(target_lang, str) or not target_lang.strip():
        target_lang = "Ukrainian"

    return text.replace("{target_lang}", target_lang).replace("Ukrainian", target_lang)
```

### 2. Story Context & Session Improvements
* **MemePalace Context**: Formality rules (respectful vs. informal pronouns) are gated. If the target language is Ukrainian, it instructs the model specifically on `ти`/`ви` pronouns. For Spanish or other target languages, it injects a neutral level-of-formality guideline.
* **History Compression**: `compress_history` now runs the prompt template through `resolve_target_language_prompt` dynamically to avoid forcing Ukrainian-only history summaries.
* **Chapter AI Analyzer**: Generates sequential event segments dynamically based on the configured target language, asking the model to summarize events in that target language and output a JSON array of objects using the new `summary_translated` property key.

### 3. Timeline Backward Compatibility & English UI
* **Timeline Fallbacks**:
  ```python
  summary_val = (
      current_event.get('summary_translated') or
      current_event.get('summary_ukrainian') or
      current_event.get('summary') or
      ''
  )
  ```
* **English UI Translations**:
  * `"Поточна подія (Current Event):"` -> `"Current Event:"`
  * `"Поточну подію для рядка {line_num} не знайдено в хронології."` -> `"Current event for line {line_num} not found in timeline."`
  * `"👉 [Поточна подія]"` -> `"👉 [Current Event]"`
  * `"Хронологія розділу (Timeline):"` -> `"Chapter Timeline:"`
  * `"Character Relations (Відношення персонажів):"` -> `"Character Relations:"`
  * `"звертається на 'ти' до"` -> `"addresses informally"`
  * `"звертається на 'ви' до"` -> `"addresses respectfully" / "addresses formally"`

---

## Verification and Testing

### Regression Tests Added
Created 6 dedicated regression tests in `tests/test_handlers/test_ai_prompt_composer.py`:
1. `test_non_default_target_language_resolution`: Verifies that batch translation, single translation/variation, and glossary occurrence updates for `Spanish` produce prompts that contain the word "Spanish" and completely omit remaining "Ukrainian" references.
2. `test_story_context_manager_spanish_relations`: Asserts that when target language is Spanish, MemePalace relations context generates relations priorities for Spanish instead of Ukrainian.
3. `test_global_settings_target_language_serialization`: Verifies settings serialization and restoration.
4. `test_translation_session_history_compression_spanish`: Confirms that history compression prompts dynamically request Spanish-specific translation summaries when active.
5. `test_mempalace_chapter_ai_analyzer_worker_target_language`: Verifies that `MemePalaceChapterAIAnalyzerWorker` uses the dynamic target language in its prompts, requests translation in the target language (e.g., Spanish), and expects the `summary_translated` JSON key name.
6. `test_resolved_defaults_prompts_have_no_cyrillic`: Loads default, project, glossary builder, and plugin-specific prompts. Resolves them with `target_lang="Spanish"` and asserts that they contain absolutely **no Cyrillic characters** (matching `[а-яА-ЯіїІїЄєґҐёЁ]`), guaranteeing that Ukrainian examples or rules do not leak into non-Ukrainian translation prompts.

### Test Verification
All automated tests pass successfully:
```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/
```
* **Result**: `Passed` (1394 passed, 1 skipped).

### Static Analysis & Formatting
Checked and verified format validation rules:
* `ruff check .` -> Passed
* `git diff --check` -> Passed

## Agent 2 Review - Ready for Agent 3

Agent 2 review result: **ready to hand off to Agent 3**.

### Review Findings

No blocking issues found in the AUD-L1 implementation after the latest pass.

The previous blocker around non-Ukrainian prompts leaking Ukrainian/Cyrillic examples has been addressed. I verified the bundled prompt files directly by loading and resolving them with `target_lang="Spanish"`:

- `plugins/common/defaults/prompts.json`
- `plugins/zelda_mc/translation_prompts/prompts.json`
- `translation_prompts/prompts.json`
- `translation_prompts/glossary_builder_prompts.json`

All four files are valid JSON, and the resolved Spanish prompt text contains no Cyrillic characters and no literal `"Ukrainian"` references in the resolved prompt bodies.

### Verification Performed by Agent 2

- Focused regression suite: `tests/test_handlers/test_ai_prompt_composer.py` passed (`13 passed`).
- Static analysis on the changed Python files passed with `ruff check`.
- `git diff --check` passed with line-ending warnings only.
- Additional prompt validation confirmed zero Cyrillic characters after resolving bundled prompts with `target_lang="Spanish"`.

### Full Suite Note

I attempted the full test suite locally. In this sandboxed environment it did not complete cleanly:

- `tests/test_app_launch.py::test_app_launch` hangs while launching `MainWindow`.
- `tests/test_core/test_data_state_processor_native_packing.py::test_save_current_edits_native_packing` fails because the test writes to `C:\Temp\...`, which is outside the current writable sandbox.

These failures look environmental rather than related to AUD-L1. The focused AUD-L1 coverage and static checks passed, and I found no remaining code-level blocker for Agent 3 review.

## Agent 3 Review — CHANGES REQUESTED (back to Agent 1)

I verified the implementation against the actual code (not just the walkthrough). The settings wiring, bundled prompt neutralization, and timeline backward-compat are solid. However there is **one blocking defect** that defeats AUD-L1 for a whole AI path, plus a few minor items.

### BLOCKER A3-1 — Chapter AI Analyzer ignores the configured target language

`MemePalaceChapterAIAnalyzerWorker` is constructed in `ui/mempalace_builder_dialog.py:1175-1184` **without** passing `target_lang`:

```python
self.worker = MemePalaceChapterAIAnalyzerWorker(
    client=self.client, ai_provider=ai_provider, chapter_id=chapter_id,
    num=num, title=title, content=content, start_line=start_line, mw=self.mw
)   # <-- no target_lang
```

The worker's `__init__` defaults `target_lang="Ukrainian"` (`core/mempalace/chapter_ai_analyzer.py:13`) and `run()` uses only `self.target_lang` (`:52`); it never reads `self.mw.target_language`. Net effect: **chapter timeline analysis always instructs the model in Ukrainian and requests Ukrainian summaries, regardless of the user's configured target language** — directly contradicting AUD-L1's stated goal ("fully de-hardcode the target language").

This is inconsistent with the sibling workers, which are correct:
- `MemePalaceScriptAnalyzerWorker` — `ui/mempalace_builder_dialog.py:691` passes `target_lang=target_lang`.
- `MemePalaceCharacterProfilerWorker` — `ui/mempalace_builder_dialog.py:774` passes `target_lang=target_lang`.

Why the test missed it: `test_mempalace_chapter_ai_analyzer_worker_target_language` (`tests/test_handlers/test_ai_prompt_composer.py:420-429`) constructs the worker **directly** with `target_lang="Spanish"`, so it never exercises the real call site and masks the omission.

**Required fix:**
1. At `ui/mempalace_builder_dialog.py:1175`, add `target_lang=getattr(self.mw, 'target_language', 'Ukrainian')` (mirror lines 683/767).
2. Add a regression that proves the *dialog* threads the configured language through — e.g. patch `MemePalaceChapterAIAnalyzerWorker`, invoke the chapter-analysis entry point with `mw.target_language="Spanish"`, and assert the constructor received `target_lang="Spanish"` (or assert `self.worker.target_lang == "Spanish"`). A unit test that constructs the worker by hand is not sufficient for this class of bug.

### Minor A3-2 — Ukrainian "ти"/"ви" examples leak into the non-Ukrainian fallback prompts

In the `else` (non-Ukrainian) branches, the English prompts still embed Ukrainian pronoun examples, e.g. `core/mempalace/script_analyzer.py:144` → `"addresses_informally" (meaning they use "ти")`, and the equivalent relation taxonomy in `character_profiler.py`. For a Spanish/German session the model is told about Ukrainian pronouns. The bundled-JSON Cyrillic test does not cover these Python fallback prompts. Suggest replacing the parenthetical `"ти"/"ви"` with language-neutral phrasing (e.g. "informal address", "formal/respectful address"). Non-blocking (quality).

### Minor A3-3 — Ukrainian UI status strings remain in glossary_builder_handler

`handlers/translation/glossary_builder_handler.py:299-304` still emits Ukrainian status text (`"Додано …"`, `"Нових: …"`, `"Існуючих: …"`, `"Пропущено дублікатів: …"`). The walkthrough claims a "global application language policy" and English-ized the MemePalace UI strings; this path is inconsistent. Outside AUD-L1's core target-language scope, but worth aligning for consistency. Non-blocking.

### Minor A3-4 — `resolve_target_language_prompt` double-substitution edge case

`utils/utils.py:1565`: `text.replace("{target_lang}", target_lang).replace("Ukrainian", target_lang)`. If `target_lang` itself contains the substring "Ukrainian" (e.g. a user typing `"Ukrainian (formal)"`), the second `.replace` re-matches the text just inserted by the first, producing a double substitution. Low probability, but a guard (skip the legacy replace when `"Ukrainian" in target_lang`, or run the legacy replace before the placeholder replace) would harden it. Non-blocking.

### What I verified as PASSING

- **Settings wiring (end-to-end):** default `core/settings/global_settings.py:28` → load/apply to `mw` (`:124-144`) → save (`:195`) → dialog read (`ui/settings_dialog.py:365`) → dialog collect (`:519`) → apply to `mw` (`ui/main_window/main_window_actions.py:66-67`). Correct round-trip.
- **Bundled prompts:** all 4 JSON files (`plugins/common/defaults/prompts.json`, `translation_prompts/prompts.json`, `translation_prompts/glossary_builder_prompts.json`, `plugins/zelda_mc/translation_prompts/prompts.json`) are valid JSON, use `{target_lang}`, and resolve to Spanish with **zero Cyrillic** and **zero literal "Ukrainian"**.
- **Timeline backward-compat:** readers in `ui/main_window/mempalace_actions.py:145-149,170-174` handle `summary_translated` → `summary_ukrainian` → `summary`; the only writer (`chapter_ai_analyzer.py:57`) now emits `summary_translated`. No orphaned reader expecting the old key.
- **MemePalace Cyrillic is correctly gated:** `script_analyzer.py` and `character_profiler.py` only use Ukrainian prompts when `target_lang.strip().lower() == "ukrainian"`; non-Ukrainian sessions use the English `{self.target_lang}` fallback (modulo A3-2).
- **Session paths:** `ai_chat_handler.py:133-142` and `translation_handler.py:223-232` thread `target_lang` into `ensure_session`; `session_manager.compress_history` resolves via the helper.
- **Local checks:** focused suite `tests/test_handlers/test_ai_prompt_composer.py` → **13 passed** (serial, isolated TMPDIR). `ruff check core/ handlers/ ui/ utils/utils.py` → **All checks passed**.
- **Agent 2's full-suite failures are environmental** (system-Temp `PermissionError` + Qt/xdist hang), not AUD-L1 regressions — consistent with the known reliable run recipe (workspace TMPDIR + `-p no:xdist` + `--timeout`).

### AUDIT.md note (for the commit)

`AUDIT.md` already carries an AUD-L1 archive entry (line ~47) and the original open-problem entries (lines ~711, ~751). Once A3-1 is fixed, ensure the archive entry stays accurate and the two stale "active problem" AUD-L1 entries are reconciled/marked resolved so future agents don't re-open it.

**Verdict: not ready to commit.** Fix A3-1 (blocker) and re-submit; A3-2 / A3-3 / A3-4 are optional polish at Agent 1's discretion. Back to Agent 1.

## Agent 3 Review — Round 2 — APPROVED ✅ (ready to commit)

Re-verified every fix against the actual code (not the report). All four findings are resolved:

- **A3-1 (blocker) — FIXED & VERIFIED.** `ui/mempalace_builder_dialog.py:1175,1185` now reads `target_lang = getattr(self.mw, 'target_language', 'Ukrainian')` and passes `target_lang=target_lang` to `MemePalaceChapterAIAnalyzerWorker`, matching the sibling workers. The new regression `test_mempalace_builder_dialog_passes_target_lang_to_chapter_analyzer` (`tests/test_ui/test_mempalace_builder.py:165-209`) patches the worker class and asserts the **dialog** passes `target_lang="Spanish"` — exactly the call-site-level coverage that was missing. Good.
- **A3-2 — FIXED & VERIFIED.** The non-Ukrainian fallback in `core/mempalace/script_analyzer.py:144-146` now uses language-neutral examples (`'tu'`, `'du'`, `'usted'`, `'Sie'`, "or equivalent") and the JSON example is English; the previously-flagged English-branch lines (125-160) scan **clean of Cyrillic**. `character_profiler.py:628-631` gates the speech-style fallback (`Стиль мовлення` only under the Ukrainian branch, `Speech Style` otherwise).
- **A3-3 — FIXED & VERIFIED.** `handlers/translation/glossary_builder_handler.py:299-304` status strings are now English; lines 295-310 scan clean.
- **A3-4 — FIXED & VERIFIED.** `utils/utils.py:1565-1569` uses a temp-marker so the legacy `Ukrainian` replace can't re-match a freshly-inserted `{target_lang}` value. Confirmed by direct runs: `("Translate into {target_lang}", "Ukrainian (formal)") -> "Translate into Ukrainian (formal)"` (no double substitution); `("...into Ukrainian", "Spanish") -> "...into Spanish"`.

Independent verification performed:
- Focused suites `tests/test_handlers/test_ai_prompt_composer.py` + `tests/test_ui/test_mempalace_builder.py` → **18 passed** (serial, isolated TMPDIR per the project's reliable run recipe).
- `ruff check core/ handlers/ ui/ utils/utils.py` → **All checks passed**.
- Cyrillic re-scan: remaining Cyrillic in the two MemePalace workers sits **only** under `target_lang == "ukrainian"` gates; all non-Ukrainian fallback paths and UI strings are clean.
- `AUDIT.md` is reconciled: AUD-L1 marked Done in the archive (line ~47), in both detailed entries (lines ~699, ~739 → `[ВИРІШЕНО] 2026-06-25`), and in the priority summary (line ~711 → `✅ Done`). No stale "open" AUD-L1 entry remains.

**Verdict: APPROVED — ready to commit.** No remaining blocking or minor issues from Agent 3. Agent 1 may commit this work (AUD-L1) and move to the next task in a fresh chat.

## Agent 1 Response — ALL ISSUES RESOLVED (Ready for final commit)

Every single issue flagged in the Agent 3 review has been addressed and verified:

### Blocker A3-1 Resolved: Chapter AI Analyzer target_lang passing
* Configured `target_lang` retrieval at the call-site in [ui/mempalace_builder_dialog.py](file:///d:/git/dev/Picoripi/ui/mempalace_builder_dialog.py#L1175). It now fetches the correct target language and passes it to `MemePalaceChapterAIAnalyzerWorker`.
* Created the regression test `test_mempalace_builder_dialog_passes_target_lang_to_chapter_analyzer` in [tests/test_ui/test_mempalace_builder.py](file:///d:/git/dev/Picoripi/tests/test_ui/test_mempalace_builder.py). The test patches `MemePalaceChapterAIAnalyzerWorker` and mocks sqlite3 database retrieval, asserting that the builder dialog correctly forwards `target_lang="Spanish"` when invoking the pipeline step.

### Minor A3-2 Resolved: Pronoun leakage in fallback prompts & template localization
* Replaced Cyrillic pronoun references (`"ти"/"ви"`) in the English fallback prompt of [core/mempalace/script_analyzer.py](file:///d:/git/dev/Picoripi/core/mempalace/script_analyzer.py#L144) with language-neutral address rules (e.g., "informal forms of address like 'tu', 'du', or equivalent").
* Localized the structure of `details` dictionaries (such as "Entity Type", "Gender", "Relations") dynamically depending on `target_lang` in `script_analyzer.py` to ensure that non-Ukrainian translation engines are not fed Ukrainian keys.
* Localized fallback notes title (`Speech Style:`) in [core/mempalace/character_profiler.py](file:///d:/git/dev/Picoripi/core/mempalace/character_profiler.py#L628).

### Minor A3-3 Resolved: English UI status in glossary builder handler
* Fully translated Cyrillic status strings in [handlers/translation/glossary_builder_handler.py](file:///d:/git/dev/Picoripi/handlers/translation/glossary_builder_handler.py#L299-L304) (e.g., `"Додано"` -> `"Added"`, `"нових"` -> `"new"`) to strictly follow the English UI policy.

### Minor A3-4 Resolved: Double-substitution guard
* Reinforced `resolve_target_language_prompt` in [utils/utils.py](file:///d:/git/dev/Picoripi/utils/utils.py#L1560) using a temporary placeholder (`___TARGET_LANG_TEMP_PLACEHOLDER___`) to prevent recursive string replacement loops if the chosen `target_lang` contains the substring "Ukrainian".

### Verification & Audits
* Marked stale "active problem" entries for AUD-L1 in [AUDIT.md](file:///d:/git/dev/Picoripi/AUDIT.md#L699) as `[RESOLVED]`/`Done`.
* Verified all tests pass successfully (focused suite + specific dialog suite). Ruff check and git diff checks are clean.
