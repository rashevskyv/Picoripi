All notable changes to the **Picoripi** project will be documented in this file.

## [0.3.080-dev] - 2026-08-13

### Added
- **Confirmed Speaker Reassignment**: A confirmed Character now keeps a Speaker identity panel that identifies its game code and lets the user reassign that code to another permanent character name without recreating the glossary.

## [0.3.079-dev] - 2026-08-13

### Fixed
- **Conflicting Speaker Aliases**: Legacy values such as `ASHEI / TELMA` are now treated as unresolved evidence, not confirmed identities. They remain purple and manually editable in Glossary/Merge Speakers, and cannot reach speaker folders or translation AI context as a name.

## [0.3.078-dev] - 2026-08-13

### Fixed
- **Legacy Speaker Codes in Glossary**: Glossary Characters now consult the active game's placeholder-speaker rule as a fallback, so older entries such as `Ash` receive the same purple identity UI and manual Apply path without recreating the glossary.

## [0.3.077-dev] - 2026-08-10

### Added
- **Glossary Primary Speaker Identity Resolver**: Made the Glossary Characters tab the primary manual interface for resolving provisional game speaker codes into permanent character names with an editable combo selector, candidate filtering, AI proposal & evidence display, and explicit Apply action.

### Changed
- **Provisional Speaker Styling**: Provisional character rows in the Glossary are styled in purple (`#6a1b9a`), matching Merge Speakers unmatched manual rows, with an updated tooltip clarifying game-data origin.
- **Version Updates**: Bumped application and documentation version to `0.3.077-dev`.

## [0.3.076-dev] - 2026-08-10

### Added
- **Manual Speaker Identity Review**: Added a five-source Merge Speakers review with editable unmatched codes, evidence and conflict details, and explicit Apply-only persistence.

### Changed
- **Confirmed Speaker Propagation**: Confirmed code-to-name identities now migrate provisional glossary entries and update speaker lists, virtual folders, Story Context, and single/batch translation prompts.
- **Version Updates**: Bumped the application and documentation version to `0.3.076-dev`.

### Fixed
- **Speaker Prompt Safety**: Kept marked-script matching on original game text and prevented unresolved developer speaker codes from reaching translation AI context.

## [0.3.075-dev] - 2026-07-17

### Added
- **Manual MemPalace Context Assignment**: Added searchable chapter and speaker pickers, drag-and-drop assignment, context-menu actions, aggregate virtual-folder browsing, and stable selection restoration for Story, Speaker, and Item context.
- **Script Markup Studio Tree Search**: Added live filtering of the hierarchy and review queue with automatic branch expansion and restoration of the previous expansion state.
- **Game-Aware AI Context**: Added plugin-provided window and content roles to translation and glossary prompts, including dedicated Zelda BMG boss-name handling and glossary categorization.
- **BFN Preview Page Navigation**: Replaced the compact page counter with a vertical page rail containing direct page indicators and previous/next controls.

### Changed
- **Tree Expansion Performance**: Avoided rebuilding the block tree for expand/collapse-all actions and enabled uniform row heights and stretched tree columns.
- **Version Updates**: Bumped the application and documentation version to `0.3.075-dev`.

### Fixed
- **Tag Validation and Spacing**: Canonicalized raw tags and aliases, respected zero-width font-map controls, narrowed missing-icon-spacing checks, and invalidated stale issue caches after rule changes.
- **Story and Speaker Navigation**: Preserved physical row identity and tree selection while editing virtual Story/Speaker views.

## [0.3.073-dev] - Unreleased

### Fixed
- **Width Recalculation Dialog Timing**: Delayed the "Recalculation Complete" dialog when forcing a recalculation until the asynchronous issue scan has fully completed.
- **Forced Issue Rescan**: Resolved an issue where subsequent recalculation/rescan requests would immediately return cached results without scanning because modification times (`mtime`) were unchanged. The recalculate action now bypasses and invalidates the cache by utilizing a new `force=True` parameter.

### Changed
- **Version Updates**: Bumped version to `0.3.073-dev` across `utils/constants.py`, `GEMINI.md`, and `CHANGELOG.md`.

## [0.3.072-dev] - 2026-07-16

### Changed
- **Version Updates**: Bumped version to `0.3.072-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, `AUDIT.md`, and `CHANGELOG.md`.

## [0.3.071-dev] - 2026-07-16

### Added
- **Redesigned Script Markup Studio Interface**:
  - Reorganized the workspace layout: separated workflow progress stages, file operations, and advanced/legacy tools.
  - Implemented a centralized **File** menu button and menu containing: Open script, Open project, Save, Save As, and Close.
  - Added a **Live Save Status Indicator** displaying `Project saved ✓` (green), `Unsaved changes *` (red/orange), or `Autosaved` (grey).
  - Added a dynamic **Progress Bar** displaying workflow stages: `1. Source ── 2. Markup ── 3. Review ── 4. MemPalace`.
  - Added an intelligent **Next Action** dashboard panel featuring dynamic context-aware buttons (AI Fill, Suggestions review, or MemPalace transition) based on project completion status.
  - Moved legacy settings (Template, Export, Legacy tools) to the **Advanced** menu button.
  - Retained 100% backward compatibility for all existing tests and underlying code contracts.
  - **Compact Header Integration**: Removed duplicate window title label. Positioned breadcrumbs progress bar and save status indicator on the exact same horizontal level.
  - **Sidebar Actions Panel**: Relocated the `Next Action` box and the status bar into the right outline sidebar panel below the script tree, expanding raw text editor height to its maximum.
  - **Compact Status Metrics**: Introduced `CompactLegendLabel` displaying color-coded letter blocks (e.g. `[S]`, `[P]`) and `CompactStatsLabel` displaying shorthand labels (`N: X | D: Y`), with both displaying full descriptions in tooltips.

### Fixed
- **Taskbar Window Proliferation**: Resolved issue where unparented legacy widgets (`Save Project...`, `Finish for MemPalace...`, `Template`, `Auto-fill`, `Recipe`, and `mode_combo`) spawned separate windows on the Windows taskbar, by passing `self` as parent to all dialog-owned components.

## [0.3.069-dev] - 2026-07-09

## [0.3.068-dev] - 2026-07-08

### 🐛 Fixed
- **MemePalace Startup Crash on Stale Temp Path (contributed by @Mnkach)**:
  - Fixed a `FileNotFoundError [WinError 3]` crash that occurred at startup in `get_mempalace_client()` (`core/translation/story_context_manager.py`).
  - The root cause was the sibling-scan walk-up calling `os.listdir()` on directories (e.g. cleaned-up temp extraction paths like `...Temp\picoripi\...\extracted\sources\Fontus`) without first verifying they exist.
  - Fix adds an `os.path.isdir(parent_dir)` guard to the condition and wraps `os.listdir()` in `try/except OSError`, falling back to an empty list so the walk-up skips missing or inaccessible directories and keeps climbing instead of crashing.

### 🚀 Added
- **Script Markup Studio — major enhancements**:
  - **Glossary node type**: New `HierarchyType.GLOSSARY` that renders as a MemPalace source section. Its direct children become named categories (Characters, Items, Locations, or custom). The type appears in the type picker and is fully supported in colour coding, tree rendering, and Markdown export.
  - **Minimap** (`components/editor/minimap.py`): A new `TextMinimap` widget provides a scrollable document overview on the right side of the raw script pane. Drag the viewport handle to jump quickly through long scripts. Auto-hides when the editor is too narrow or the document has only one block.
  - **Search bar**: `_SearchLineEdit` widget with `Enter` / `Shift+Enter` for next/previous match, plus **Aa** (case-sensitive), **Word** (whole-word), and **.\*** (regex) toggles. `Ctrl+F` focuses the search field from anywhere in the dialog.
  - **Continue from marked examples** (`core/script_markup/local_autofill.py`): Studies your approved hierarchy marks and locally fills matching unmarked lines without any AI call. The action is undoable with `Ctrl+Z`.
  - **Keyboard shortcuts**: `Ctrl+S` Structure, `Ctrl+P` Speaker, `Ctrl+T` Text, `Ctrl+B` Breaker, `Ctrl+I` Ignore, `Ctrl+M` mark/save. **F2** renames the selected tree node; clicking an already-selected node also opens rename without jumping to source.
  - **AI mark missing**: Renamed from "AI mark unmarked" to clarify it is a separate explicit action.
  - **IGNORE rendering fix**: IGNORE marks now override all other mark colours correctly in `line_styles_for_marks`, and IGNORE lines are excluded from the Markdown export body.
- **`AIStatusDialog.set_model_name()`**: New public method to update the visible model name after a dialog has started, used by the Script Markup Studio when switching AI operations.
- **Adaptive scrollbars** (`ui/adaptive_scrollbars.py`): Refined dark/light-theme scrollbar style — slimmer 8 px tracks, hover background tint, pressed handle state, and no dead-zone pages.

### ⚙️ Changed
- **`render_hierarchy_markdown`** now skips IGNORE-marked lines in the body text output and sorts child nodes by `(start_line, depth, order)` for deterministic export.
- **`mark_text`** and **`line_styles_for_marks`** updated to handle `HierarchyType.GLOSSARY` the same way as `STRUCTURE` (use explicit label, scan heading lines).
- **Version Updates**: Bumped version to `0.3.068-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `CHANGELOG.md`.

## [0.3.067-dev] - 2026-06-27

### ⚙️ Changed
- **Line Wrapping and Merging Heuristics in ShortLineRule (AUD-L4)**:
  - Added custom punctuation checks to prevent merging short lines that end with colons (`:`), semicolons (`;`), dashes (`—`, `–`), or closing brackets/parentheses (`]`, `}`, `)`) preceding punctuation, protecting lists and distinct phrase ends.
  - Implemented a conservative header and standalone line protection: blocks merging of a line that is shorter than 50% of the line width threshold, starts with an uppercase letter, and the next line also starts with an uppercase letter. This keeps distinct titles, menu items, and standalone labels from being aggressively compacted.
  - Corrected test cases in `test_spacing_rules.py` (`test_autofix_page_local` and `test_zelda_mc_autofix_page_local_prevent_empty`) to use lowercase letters for next-line continuations, avoiding false header-protection triggers in page-local padding tests.
  - Added new test contracts `test_short_line_rule_header_protection` and `test_short_line_rule_punctuation_protection` to `test_rule_engine_contract.py`.
- **Version Updates**: Bumped version to `0.3.067-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.066-dev] - 2026-06-26

### ⚙️ Changed
- **Monolithic GUI Modules Decomposition (AUD-A5)**:
  - Decomposed the massive settings dialog layout builder `ui/settings/settings_ui_setup.py` (~1236 LOC) into four specialized mixins: `general_spelling_mixin.py` (Global & Spelling), `plugin_mixin.py` (Project/Plugin tables and paths), `ai_mixin.py` (AI translation and glossary configurations), and `logging_mixin.py` (Logging settings and plugin scan helpers). SettingsDialogUiMixin now acts as a compact facade class.
  - Decomposed the MemePalace Context Builder dialog `ui/mempalace_builder_dialog.py` (~1380 LOC) into a package structure `ui/mempalace/` with three submodules: `mempalace_sleep.py` (Windows API sleep prevention), `mempalace_ui.py` (widget construction and styling), and `mempalace_pipeline.py` (orchestration of steps 1-4).
  - Restored the missing `_clear_database` slot in `MemePalaceBuilderDialog` to prevent test and database cleaning failures.
  - Added QPushButton to `PyQt6.QtWidgets` imports in `plugin_mixin.py` to fix runtime NameErrors.
  - Standardized git ignores by adding `.tmp_test_run/` and `pytest-of-Administrator/` test artifact directories to `.gitignore`.
- **Version Updates**: Bumped version to `0.3.066-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.065-dev] - 2026-06-26

### ⚙️ Changed
- **Line Break and Tag Preservation in AI Translation (AUD-L2, AUD-L3)**:
  - Preserved structured deliberate newlines and normalized spaces inside each line during prompt preparation instead of stripping all line breaks.
  - Added conversion to editor representation for input text before prompt preparation to unify page/line breaks (e.g. from plugin-specific `\\n` to `\n`).
  - Added tag alias legend to JSON payloads for batch translation and a dedicated section for single-string prompts, filtering out forced aliases.
  - Added instructions for AI to identify and lock anchored system tags (e.g. `{0}`, `{1}`) to prevent deletion or relocation.
  - Refactored `TextFormatter.format_and_wrap_translation` to process segments individually when split by page breaks, preserving deliberate line breaks and wrapping only lines exceeding thresholds.
  - Added comprehensive test suites to verify tag alias legends, newline preservation, formatting, and anchored tags.
- **Version Updates**: Bumped version to `0.3.065-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.064-dev] - 2026-06-25

### ⚙️ Changed
- **Version Updates**: Bumped version to `0.3.064-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.


## [0.3.063-dev] - 2026-06-25

### ⚡ Optimized
- **Binary Search for Line Splitting (AUD-P6)**:
  - Replaced the linear $O(N)$ scanning in `WidthRule.fix` with a binary search $O(\log N)$ based on subline pixel width measurements.
  - Optimized the search for split points near punctuation from the back of the split index to bypass extra calls to `_get_string_width`.
- **Precomputed Problems & Pre-allocated Colors in Gutter Painting (AUD-P8)**:
  - Eliminated dynamic `QColor` allocations and alpha value modification (`setAlpha()`) in the hot loop of `LNETLineNumberAreaPaintLogic`.
  - Added precomputed severity prioritizing ranks to sort layout problems once per paint event.

### ⚙️ Changed
- **Consolidated Text Iteration (AUD-R4)**:
  - Introduced a shared lazy generator `iter_all_strings()` in `core/tag_utils.py` to unify the loop structure for iterating over all strings across all blocks and categories.
  - Refactored `AutofixWorker`, `TextOperationHandler`, and `TranslationHandler` to utilize the new unified generator.
  - Added test suite `test_iter_all_strings` to verify iterator correctness.
- **Version Updates**: Bumped version to `0.3.063-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.062-dev] - 2026-06-25

### ⚡ Optimized
- **O(1) Displayed Indices Map (AUD-P7)**:
  - Replaced the linear O(n) search over `displayed_string_indices` via `.index()` and `in` with an O(1) reverse lookup map `_displayed_string_indices_map` generated inside the `AppDataStore.displayed_string_indices` setter.
  - Implemented a mock-safe `_get_relative_index(target)` helper in `ListSelectionHandler` to prevent `MagicMock` type errors in unit tests by falling back to O(n) lookup when mock instances are detected.
  - Optimized index mapping paths in `list_selection_handler.py`, `preview_updater.py`, `search_handler.py`, and `ui_event_filters.py`.
  - Added unit test `test_AppDataStore_displayed_string_indices_properties` to verify map population, and ensured correct first-match index resolution semantics using `dict.setdefault()`.

### 🐛 Fixed
- **Theater Tests Assertion Fixes (AUD-W1)**:
  - Added a missing width assert verification inside `test_empty_font_map` in `test_utils.py`.
  - Added call-args check assertions inside `test_JsonTagHighlighter_highlightBlock_colors` in `test_syntax_highlighter.py` to ensure proper syntax highlighter coloring formats are applied under WW and MC plugin formats.

## [0.3.061-dev] - 2026-06-25

### 🚀 Added
- **Dynamic Target Language Selection (AUD-L1)**:
  - De-hardcoded target language ("Ukrainian") from default prompts and system workflows to support any target language (e.g., Spanish, German) seamlessly.
  - Added target language controls to Settings UI and decoupled logic via the `ProjectContext` protocol.
  - Added regression test `test_mempalace_builder_dialog_passes_target_lang_to_chapter_analyzer` verifying call-site language propagation.
  - Added regex-based test `test_resolved_defaults_prompts_have_no_cyrillic` validating prompt translation templates.

### ⚙️ Changed
- **Prompt Isolation & Localized Fallbacks**:
  - Replaced Cyrillic/Ukrainian references in all default prompts JSON files with neutral English instructions and `{target_lang}` placeholders.
  - Localized entities metadata formatting ("Entity Type", "Gender", etc.) and fallback speech styles in MemePalace workers dynamically.
  - Translated Glossary Builder UI status messages to English, enforcing the English UI policy.
- **Double-Substitution Guard**:
  - Reinforced `resolve_target_language_prompt` with a temporary placeholder mapping to prevent recursive loops when `target_lang` contains "Ukrainian".
- **Version Updates**: Bumped version to `0.3.061-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.060-dev] - 2026-06-24

### 🚀 Added
- **Export Original Text (AUD-EXP1)**: Implemented "Export Original" menu action in the File menu, allowing users to export the original string content of the project blocks to a structured JSON file. Added tests for connection, enabling state, and functionality.
- **Script Markup Studio Auto-follow**: Added a checkbox `Auto-follow scroll` to the Script Markup Studio toolbar. When checked, scrolling the raw script pane dynamically aligns the preview pane to the top visible line in the raw pane using `ensureCursorVisible()` (gentle scrolling). If the target line is already visible, the view remains stationary to avoid layout jumping. Added tests verifying active scrolling behavior, including viewport mocking.

### ⚙️ Changed
- **Bounded LRU Width Cache (AUD-P5)**: Transitioned `_STRING_WIDTH_CACHE` in `utils/utils.py` to a bounded LRU cache with a maximum capacity of 10,000 entries. This prevents memory leaks and full cache flushes/thrashing after exceeding the limit.
- **QThread Lifecycle Test Stabilization**: Restored true asynchronous thread lifecycle testing (`worker.start()`) in `tests/test_dialogs/test_real_workers_lifecycle.py`. Replaced unreliable polling loops (`qtbot.waitUntil`) and synchronous `.run()` bypasses with deterministic QTest signal waiters (`qtbot.waitSignal`).
- **Git Diff Compliance**: Fixed formatting issues highlighted by `git diff --check` (extra newlines at end-of-file).
- **Version Updates**: Bumped version to `0.3.060-dev` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.058] - 2026-06-23

### ⚙️ Changed
- **Decomposed SearchReviewDialog and MainWindowActions (AUD-A3)**:
  - Created a new package `dialogs/search/` and extracted background search logic into `SearchWorker` in `search_worker.py` and pure utility functions in `search_utils.py`.
  - Created `dialogs/tag_alias_dialog.py` for `TagAliasDialog` and `AliasUpdateWorker`.
  - Extracted BFN Editor actions into `ui/main_window/bfn_actions.py` and MemePalace actions into `ui/main_window/mempalace_actions.py`.
  - Integrated helpers into `MainWindowActions` with proxy calls, keeping 100% backward compatibility for all importers and test suites.
  - Reduced `main_window_actions.py` code length by ~650 lines.
- **Removed mock-aware guards from product code (AUD-A4)**:
  - Removed all 5 occurrences of `hasattr(..., 'assert_called_with')` checks from `translation_handler.py` and `batch_translator.py`.
  - Cleared production codebase from testing mock artifacts, leaving assertions solely to unit tests.
- **Improved Test Suite Robustness under Parallel xdist (AUD-T8)**:
  - Set QThread timeouts to 30 seconds for real workers lifecycle test suits to prevent flaky failures under CPU starvation.
  - Set spellchecker performance budget threshold to 800ms under high load.
  - Converted GlossaryOccurrenceWorker execution to synchronous in user journey tests to eliminate thread scheduling dependency.
- **Version Updates**:
  - Bumped version to `0.3.058` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.057] - 2026-06-20

### 🚀 Added
- **Full Fast Session Restoration (B04-FIX)**:
  - Added full parsed state serialization (`data` and `edited_file_data`) inside the `AppDataStore` session snapshot.
  - Implemented base64 encoding/decoding helper in `SessionManager` to safely process raw binary `bytes` in JSON format.
  - Added automatic restoration of `plugin_original_keys` runtime state within the session lifecycle.
  - Implemented session fast-path check in `ProjectActionHandler._restore_project_session_fast_path()`. If session is valid and populated, the app loads instantly, skipping the background `ProjectLoadWorker` thread and its visual progress dialog.
  - Added regression test suite covering fast restoration path, fallback behavior, bytes serialization, and project saving.

### 🐛 Fixed
- **Project Saving Stability**:
  - Decoupled project-save execution from legacy `edited_json_path` configuration, saving directly using the individual block translation paths.
  - Added defensive validation to prevent `IndexError` on save when `plugin_original_keys` is incomplete or missing.

### ⚙️ Changed
- **Version Updates**:
  - Bumped version to `0.3.057` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.056] - 2026-06-20

### 🚀 Added
- **Real QThread Worker Smoke Tests (T02)**:
  - Created `tests/test_dialogs/test_real_workers_lifecycle.py` to establish solid non-mock QThread lifecycle integration tests.
  - Implemented async lifecycle tests (start, status signals, cancellation, finished callbacks) for `WidthCalculationWorker`, `ProjectLoadWorker`, `SpellcheckWorker`, `ProviderTestWorker`, `AliasUpdateWorker`, and `SaveWorker`.
- **Scenario-Based User Journeys (T04)**:
  - Created `tests/test_integration/test_user_journeys.py` covering multi-step user scenarios under realistic asynchronous operations.
  - Added integration tests for:
    - Undo/Redo & Preview Update sequence.
    - Plugin Switch & Width Validation rules dynamically adapting to layout settings.
    - Glossary CRUD flow alongside automatic highlighting and session autosaves.

### ⚙️ Changed
- **Decomposed DataStateProcessor (B08)**:
  - Decomposed the monolithic state mutations inside `core/data_state_processor.py` into localized, dedicated modules under `core/data_processor/` to improve testability and code separation:
    - `SessionManager`: encapsulates session serialization, JSON checkpoints, Pickle binary snapshots, and crash recovery.
    - `RevertManager`: handles partial reverting of modified translation blocks and categories.
    - `SetCalculator`: performs mathematical index set computations for modified elements.
  - Maintained 100% backward compatibility of the public `DataStateProcessor` interface.
- **Test Stability and Parallel Optimization**:
  - Resolved potential thread leaks in worker tests under high CPU loads during parallel test suites run (`pytest -n auto`).
  - Added a defensive `finally` thread cleanup helper and explicit worker waits (`worker.wait(5000)`) to avoid leftover zombie threads upon test assertion failures.
  - Corrected mock target patching within `test_data_state_processor.py` to patch `core.data_manager.save_json_file`, fixing local import side-effects.
- **Version Updates**:
  - Bumped version to `0.3.056` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.055] - 2026-06-20

### 🚀 Added
- **Audit Consistency Refactoring**:
  - Updated `AUDIT.md` metrics, removing the retired `core/mempalace_worker.py` from the list of the largest files (which is now a clean 6-line shim).
  - Renamed the active `B08` issue section in `AUDIT.md` to a follow-up task targeting other large coordinators (`handlers/translation_handler.py`, etc.).
  - Documented completion of the first step (MemePalace workers decoupling) under the `B08` entry in the TODO list.

### ⚙️ Changed
- **Version Updates**:
  - Bumped version to `0.3.055` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.054] - 2026-06-20

### 🚀 Added
- **Decoupled core/mempalace_worker.py (B08)**:
  - Created a new package `core/mempalace/` with individual modules to host background `QThread` workers for MemePalace pipelines.
  - Moved worker classes into dedicated files:
    - `weaver_worker.py` containing `MemePalaceWorker` and `robust_json_loads`.
    - `script_analyzer.py` containing `MemePalaceScriptAnalyzerWorker`.
    - `chapter_mapper.py` containing `MemePalaceChapterMapperWorker`.
    - `chapter_ai_analyzer.py` containing `MemePalaceChapterAIAnalyzerWorker`.
    - `character_profiler.py` containing `MemePalaceCharacterProfilerWorker`.
    - `chapters_loader.py` containing `MemePalaceChaptersLoadWorker`.
  - Updated `core/mempalace_worker.py` to import and re-export all classes and functions, maintaining 100% backward compatibility for all importers and test suites.

### ⚙️ Changed
- **Version Updates**:
  - Bumped version to `0.3.054` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.053] - 2026-06-20

### 🚀 Added
- **Extended Deterministic Performance Coverage (B09)**:
  - Added comprehensive performance tests covering key UI-adjacent operations:
    - **Glossary Builder chunk preparation**: verified background chunking and tag masking performance on 5,000 lines (budget: < 50ms).
    - **Preview pre-cache time-slicing**: verified that the tick operation does not exceed the budget of 20ms per cycle on 1,000 lines.
    - **Warning filter toggle**: measured index resolution performance under filter conditions on 5,000 lines (budget: < 50ms).
    - **Dictionary fetch fallback**: verified that the fetch worker's fallback handling on network error completes under 50ms without blocking UI.
  - Adjusted `test_warning_filter_toggle_performance` parameters (`hide_categorized`, `hide_translated`, `show_overrides_only`, `show_unsaved_only`, `show_warnings_only`, `active_warning_filters`, `detection_config`, `hide_empty_strings`) to match the actual signature of `FilterQueryAPI.get_filtered_string_indices`.

### ⚙️ Changed
- **Version Updates**:
  - Bumped version to `0.3.053` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.052] - 2026-06-20

### 🚀 Added
- **Glossary Builder Exception Safeguard**:
  - Replaced unsafe `response.text` evaluation in the outer `catch-all` block of `AIWorker.run()` with a null-safe reference `resp_t = response.text if 'response' in locals() and response is not None else None`. This avoids `AttributeError` when provider calls or parsing raise exceptions before the response object is instantiated.
- **Unit Testing**:
  - Added `test_ai_worker_build_glossary_exception_handling` to ensure the outer exception handling path runs safely and broadcasts the `error` signal.

### ⚙️ Changed
- **Version Updates**:
  - Bumped version to `0.3.052` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.051] - 2026-06-20

### 🚀 Added
- **Glossary Builder Enhancements**:
  - **Tag Leakage Prevention on Chunk Boundaries**: Mask tags using `ALL_TAGS_PATTERN` *before* slicing the aggregated text into chunks. This guarantees that tags crossing chunk boundaries are correctly stripped and do not leak into AI prompts.
  - **Chunk Size Normalization & Validation**: Added robust validation and clamping for `chunk_size`. Non-numeric, zero, or negative values automatically fallback to `8000`, and valid values are clamped to the safe range `1000..32000`.
  - **Clean Error Reference Tracking**: Explicitly reset the `response` variable to `None` at the start of each iteration in the glossary request loop to prevent referencing a stale response from a prior successful chunk in error handlers.
- **Unit Testing**:
  - Added `test_ai_worker_build_glossary_boundary_tags` to verify boundary tag leakage protection.
  - Added `test_ai_worker_build_glossary_chunk_size_normalization` to cover invalid configurations (e.g. `0`, `-1`, `"bad"`, `None`) and clamping thresholds.
  - Refactored `test_ai_worker_build_glossary_background_processing` to align with the clamped chunk size threshold of 1000.

### ⚙️ Changed
- **Version Updates & Docs**:
  - Bumped version to `0.3.051` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.

## [0.3.050] - 2026-06-20

### 🚀 Added
- **Glossary Builder Background Offload (B06)**:
  - Moved string collection, tag masking using `ALL_TAGS_PATTERN`, and text chunking logic from the main UI thread into the background `AIWorker` thread (`task_type == 'build_glossary'`). This prevents UI freezes and memory spikes when preparing large categories or files for translation/glossary generation.
  - Integrated `total_chunks_calculated` signal to dynamic progress updates in the main window's status bar.
- **Unit Testing**:
  - Added `test_ai_worker_build_glossary_background_processing` to verify background chunking and tag masking logic.
  - Updated and fixed `test_AIWorker_run_build_glossary` in `tests/test_handlers/test_translation/test_ai_worker.py`.

### ⚙️ Changed
- **Version Updates & Docs**:
  - Bumped version to `0.3.050` across `utils/constants.py`, `README.md`, `GEMINI.md`, and `AUDIT.md`.
  - Moved B06 task in `AUDIT.md` from the TODO list/Active Issues into the Completed section.

## [0.3.049] - 2026-06-20

### ⚙️ Changed
- **Cancellable Startup Pre-cache Timer**:
  - Replaced the static `QTimer.singleShot` deferred execution wrapper inside `schedule_pre_cache` with an instance-level single-shot `QTimer` (`_pre_cache_start_timer`).
  - Added explicit cancellation of `_pre_cache_start_timer` inside `cancel_idle_caching()` to eliminate the risk of executing delayed background caching callbacks after a project is closed or reloaded.
- **Documentation**:
  - Synced and cleaned up `AUDIT.md` by transferring the historical B05 description from Active Issues into the Completed Improvements section.

### 🚀 Added
- **Unit Testing**:
  - Added `test_schedule_pre_cache_cancellation` to `tests/test_ui/test_updaters/test_preview_cache_stabilization.py` verifying that calling `cancel_idle_caching()` stops the pending pre-cache timer and prevents the `pre_cache_all_blocks` method from firing.

## [0.3.048] - 2026-06-20

### 🚀 Added
- **Time-Sliced Background Pre-Caching (B05)**:
  - Redesigned the background idle caching loop `_cache_next_idle_block` to process preview lines in small increments restricted by a 10ms execution budget. This completely avoids micro-stuttering on massive blocks containing thousands of lines.
  - Implemented automatic acceleration of the timer (30ms interval) while a block is partially cached, and restoration of the standard 200ms background pause once the block is completed.
  - Added robust caching cancellation `cancel_idle_caching()` which clears current queues and resets caching state. This is hooked up to pre-cache rebuilds and project closure.
  - Added queue constraints to restrict `_idle_cache_queue` to the `MAX_CACHE_SIZE = 15` nearest blocks, preventing memory and CPU wastage on large-scale projects.
  - Added a proxy `cancel_idle_caching` to `PreviewUpdater` and implemented cancellation on project close inside `close_project_action`.
- **Stabilization Testing**:
  - Created a new test file `tests/test_ui/test_updaters/test_preview_cache_stabilization.py` containing comprehensive unit tests verifying queue limits, caching cancellation, time-slicing logic, and store success conditions.

## [0.3.047] - 2026-06-20

### ⚙️ Changed
- **Enhanced Atomic Write Unit Testing**:
  - Improved `test_atomic_json_write` in `tests/test_core/test_durable_session.py` to assert that `_save_durable_session_json(force=True)` correctly returns `False` upon write failure and successfully cleans up the temporary `.tmp` file from the disk.

## [0.3.046] - 2026-06-20

### ⚙️ Changed
- **Forced Session JSON Sync Retries**:
  - Refactored `_save_durable_session_json()` to return a boolean success state and to clean up the temporary `.tmp` file immediately if an exception is raised (preventing orphan temp files on disk).
  - Reset `_durable_session_dirty` only after a successful write.
  - Adjusted `load_session_file()` to set `_durable_session_dirty = True` before initiating a forced JSON sync after choosing a newer Pickle fallback. If this forced save fails, the dirty flag remains `True`, ensuring that the 5-minute timer retry handler will attempt to sync it again.

### 🚀 Added
- **Unit Testing**:
  - Added `test_newer_pickle_chosen_json_sync_fails_dirty_remains` in `tests/test_core/test_durable_session.py` to verify that the durable dirty flag remains set to `True` upon a failed forced JSON sync.

## [0.3.045] - 2026-06-20

### 🚀 Added
- **Robust Unit Testing Coverage**:
  - Expanded `tests/test_core/test_durable_session.py` to validate stale JSON vs newer Pickle fallback behavior, separate dirty flag timer tracks, atomic writing resilience under IOErrors, and complex Undo/Redo stacked action roundtrips.

### ⚙️ Changed
- **Durable JSON Checkpoint Stabilizations**:
  - **Freshness Policy**: Introduced `saved_at` timestamp comparison inside `load_session_file` to resolve conflicts where stale JSON checkpoints could overwrite newer Pickle autosave files after application crashes.
  - **Separate Dirty State Flags**: De-conflicted dirty trackers by splitting them into `_session_dirty` (Pickle autosave debounce) and `_durable_session_dirty` (durable JSON timer). `schedule_autosave` now marks both, preventing quick Pickle dumps from prematurely clearing JSON saves.
  - **Atomic JSON Writes**: Replaced raw file writers with atomic `.tmp` file writing, flushing/fsync-ing, and `Path.replace` replacement to prevent session corruption on sudden power-off or disk failure.
- **QThread Test Stabilization**:
  - Stabilized `test_autofix_worker_real_thread_lifecycle` and `test_autofix_worker_real_thread_cancellation` in `tests/test_handlers/test_autofix_worker.py` under heavy CPU load from `pytest-xdist`.
  - Replaced non-thread-safe `MagicMock` game rules with a clean and thread-safe `FakeGameRules` helper class.
  - Replaced flaky `qtbot.waitUntil` signal monitoring with robust `QThread.wait()` execution tracking and queued signal propagation using `QCoreApplication.processEvents()`, eliminating timing issues under extreme CPU starvation.

## [0.3.044] - 2026-06-19

### 🚀 Added
- **Durable JSON Session Checkpoints**:
  - Introduced a schema-based human-readable JSON session saving mechanism (`.picoripi_session.json`) alongside the binary Pickle-based `.picoripi_session` file.
  - Automatically serializes internal fields (like tuple keys in `edited_data` and `problems_per_subline`, sets in `unsaved_block_indices`, and custom Undo/Redo stack actions) to valid JSON structures.
  - Saves the JSON session checkpoint at application shutdown (`closeEvent`), periodically (every 5 minutes) via a background timer, and before major operations.
- **Robust Startup Restoration & Fallback**:
  - Refactored `load_session_file` to preferentially load and validate the durable JSON session checkpoint to avoid Python/PyQt binary incompatibility issues.
  - Falls back smoothly to the fast binary Pickle snapshot if the JSON session is absent or corrupted.
- **Durable Session Unit Testing**:
  - Created a comprehensive test suite in `tests/test_core/test_durable_session.py` covering serialization, deserialization of types, checkpoint saving, and robust Pickle fallback behavior.

### ⚙️ Changed
- **Autosave Debounce Focus**:
  - Retained fast binary Pickle serialization for quick 2-second debounced autosaves to keep the editor thread completely free of JSON performance overhead.

## [0.3.043] - 2026-06-19

### 🚀 Added
- **Asynchronous Dictionary Loading**:
  - Introduced `DictionaryListFetchWorker` (subclassing `QThread`) to download the remote repository dictionaries list in the background, keeping the main thread free and opening the Dictionary Manager dialog instantly.
- **Dictionary Manager Testing**:
  - Created a comprehensive test file `tests/test_ui/test_dictionary_manager.py` validating async fetching, error scenarios, and proper thread shutdown on dialog rejection.
- **Failsafe Shutdown Tests**:
  - Expanded thread utility tests in `tests/test_utils/test_thread_utils.py` to cover both cooperative shutdown and forced termination logic.

### ⚙️ Changed
- **Cooperative Thread Shutdown**:
  - Refactored `safe_shutdown_thread()` in `utils/thread_utils.py` with an `allow_terminate=False` default parameter. Abrupt `thread.terminate()` call is now disabled by default, replacing forced termination with safe warning logs to prevent PyQt/SQLite runtime crashes.
  - Realigned `SettingsDialog` and `MemePalaceBuilderDialog` to invoke `safe_shutdown_thread()` for their respective workers (`ProviderTestWorker` and pipeline workers) during close events.
  - Linked `finished.connect(worker.deleteLater)` to all MemePalace workers to clean up their resources smoothly upon successful completion.

### 🐛 Fixed
- **Cooperative Cancel in Downloads**:
  - Integrated `self._is_cancelled` check into `DownloadThread` chunk iterator to abort download operations cooperatively and clean up partial files when the manager is closed early.

## [0.3.042] - 2026-06-19

### 📝 Documentation
- **Audit TODO Wording Alignment**:
  - Updated the TODO description of the **B01** task in `AUDIT.md` to perfectly match the implemented `repaint()` solution and removed references to obsolete signal-oriented or timer-based placeholders, ensuring document consistency.

## [0.3.041] - 2026-06-19

### 🚀 Added
- **QThread Test Robustness**:
  - Increased `qtbot.waitSignal` timeouts in QThread integration tests `test_autofix_worker_real_thread_lifecycle` (to 15s) and `test_autofix_worker_real_thread_cancellation` (to 10s) in `tests/test_handlers/test_autofix_worker.py` to prevent flaky failures under high concurrent CPU load (e.g. parallel execution with 16 workers).

### 🐛 Fixed
- **Reentrancy Risks Mitigation in Progress Dialog**:
  - Completely removed `QCoreApplication.processEvents()` from the sync progress tracker (`UIProgressTracker` inside `create_progress_tracker` in `main.py`) to eliminate reentrancy risks (e.g., unintended event dispatching, widget updates, or window closure in the middle of transactional procedures).
  - Disabled the "Cancel" button on the progress dialog (`setCancelButton(None)`) during strings/blocks reverting because these operations run entirely in-memory and execute extremely fast (within milliseconds to a second), making asynchronous cancellation unnecessary.
  - Replaced manual event pumping with a direct `self.dialog.repaint()` call which safely and instantly redraws the progress widget without triggering the event queue dispatch.

## [0.3.040] - 2026-06-19

### 🚀 Added
- **QThread Test Suite Stabilization**:
  - Fixed a race condition in `test_autofix_worker_real_thread_cancellation` by triggering `worker.cancel()` directly inside the `qtbot.waitSignal` context manager.
  - Added deterministic cleanup utilizing QThread `.wait()` in `tests/test_handlers/test_autofix_worker.py` to prevent background threads from outliving test executions.

### 🐛 Fixed
- **Mock Cleanup in Product Code**:
  - Removed all remaining mock-specific comments and terminology from product modules (`report_dialog.py`, `toast.py`, `undo_manager.py`, and `text_autofix_logic.py`), replacing them with neutral terms like "non-QWidget parent", "test/fallback context", and "synthetic widget context".

## [0.3.039] - 2026-06-19

### 🚀 Added
- **A13. Real QThread Lifecycle Tests**:
  - Implemented real `QThread` integration tests verifying worker thread start, cancellation, and clean execution cycles using `qtbot` (pytest-qt) in `tests/test_handlers/test_autofix_worker.py` and `tests/test_text_operation_handler.py`.
  - Expanded search integration tests to assert precise parameters for `add_search_match_highlight` after block navigation in `tests/test_handlers/test_search_handler.py`.

### 🐛 Fixed
- **AutofixWorker lifecycle**:
  - Fixed a reentrancy and thread wait blocking issue by removing direct `_cleanup_active_autofix()` calls from `completed`, `cancelled`, and `error` signals. The thread cleanup is now driven strictly by the standard `QThread.finished` signal, preventing UI thread pauses (`.wait(2000)`) during execution.
- **Mock/MagicMock Cleanup in Product Code**:
  - Completely removed test-specific `Mock` and `MagicMock` name checks (such as `_mock_self`, `_mock_name`, and conditional `filter_query_api is None` fallbacks) from production modules (`FilterQueryAPI`, `PreviewUpdater`, `PreviewRenderer`, `BlockListUpdater`, `PreviewCache`).
  - Standardized mock window fixtures (`mock_mw`) in the unit test suite (`conftest.py`, `test_asterisk_logic.py`, `test_small_updaters.py`, and `test_block_list_updater.py`) to inject real `FilterQueryAPI` instances and default to clean `displayed_string_indices = []`.
- **Project Audit Document**:
  - Updated `AUDIT.md` to document the completed `B04-CR` and `B07` stabilization tasks and updated overall test suite statistics (1212 passed).

## [0.3.038] - 2026-06-18

### 🚀 Added
- **A11. Cancellable Asynchronous Operations UX**:
  - Made Glossary Indexing (`GlossaryOccurrenceWorker`) fully cancellable by enabling the "Cancel" button on the `QProgressDialog` and connecting it to `worker.requestInterruption()`.
  - Upgraded Spellcheck and Advanced Search & Replace dialogs to allow window closing during long-running background tasks. When closed during analysis, the dialogs safely cancel the worker threads in the background and wait for their termination before rejecting the dialog, preventing memory leaks and Qt runtime thread destruction warnings.
  - Added a non-blocking preview cache progress indicator in the main window status bar, showing `Caching previews: X/Y blocks...` during idle generation.
  - Implemented unit tests validating asynchronous cancellation flows for glossary indexing, spellchecking, and search workers in `tests/test_dialogs/test_cancellable_workers.py`.

### 🐛 Fixed
- **QStatusBar Callability**: Fixed a PyQt6 `TypeError: 'QStatusBar' object is not callable` in `ui/updaters/preview_updater.py` by changing status bar method invocations (`self.mw.statusBar()`) to property lookups (`self.mw.statusBar`), matching the initialization in `statusbar_builder.py`.
- **Glossary Dialog Test Mocking**: Fixed a test failure in `test_gh_show_glossary_dialog` by mocking `isInterruptionRequested()` on `GlossaryOccurrenceWorker` to return `False` to prevent the mocked worker from skipping dialog construction.

## [0.3.037] - 2026-06-18

### 🚀 Added
- **A10. Performance Regression Tests for Large Projects**:
  - Registered the new pytest marker `performance` inside `pyproject.toml` and configured default execution options (`addopts`) to ignore performance tests by default (`-m "not performance"`) to prevent flaky test runs in standard CI environments and local dev environments.
  - Implemented high-performance, deterministic regression tests in `tests/test_performance.py` using large synthetic datasets (5000 lines, 100 glossary terms) covering:
    - Width calculation (`calculate_string_width`) with Trie + caching.
    - Spellcheck manager scan throughput (2000 alphabetical words, validated via successful Hunspell dictionary loads).
    - Block tree filter toggle performance (20 runs over index sets).
    - Preview manager load and layout preparation (`populate_strings_for_block` for 5000 lines).
    - AI translation context composition (`compose_batch_request` for 100 items).
  - Enhanced the standalone benchmark script `scripts/benchmark.py` with automatic in-memory synthetic fallback data when real game resources are missing, printing formatted comparison tables.
  - Updated `AUDIT.md` to reflect the completed state of the A10 issue.

## [0.3.036] - 2026-06-18

### 🚀 Added
- **A09 Sub-Handlers Decomposition**:
  - Extracted virtual category, virtual speaker, and folder navigation logic from `ListSelectionHandler` into three dedicated components: `CategoryHandler` (`handlers/category_handler.py`), `SpeakerHandler` (`handlers/speaker_handler.py`), and `VirtualFolderHandler` (`handlers/virtual_folder_handler.py`).
  - Configured `ListSelectionHandler` to act as a clean facade and delegate, reducing its complexity and enforcing Single Responsibility Principle (SRP).
  - Resolved initialization order issues in `MainWindow` by instantiating sub-handlers before `ListSelectionHandler`.
  - Added compatibility checks and fallback instantiation inside `ListSelectionHandler` to maintain mock-testing stability in unit tests.

### 🐛 Fixed
- **Worker Cancellation Race Condition**:
  - Fixed a race condition in `SpellcheckWorker` and `SearchReviewDialog` where canceling a worker right after its final check but before completion could result in a silent exit without emitting any signal. Added fallback `self.cancelled.emit()` in worker run loops.
  - Updated `AUDIT.md` checkboxes to reflect implementation status correctly.

## [0.3.034] - 2026-06-18


### 🐛 Fixed
- **Missing Tag Spacing Custom Width Tag Mapping**:
  - Fixed a syntax error and fallback issue in `JsonTagHighlighter` where it incorrectly queried `tag_mappings` instead of `default_tag_mappings` on `MainWindow`. This corrected the width-alias checks for custom control tags (such as `[L-Stick]`) that are mapped to escape codes, ensuring they are correctly treated as width-carrying kept tags rather than zero-width tags in text spacing checks, thereby preventing false positive missing spacing warnings.
  - Added a dedicated regression test `test_JsonTagHighlighter_missing_tag_spacing_width_alias` in `tests/test_utils/test_syntax_highlighter.py` to verify formatting behaves correctly when custom tag mappings are resolved.

## [0.3.033] - 2026-06-17

### 🚀 Added
- **Show Unsaved Only Automatic Updates**:
  - Configured the strings preview list to automatically hide newly saved lines if the "Show Unsaved Only" filter is active.
  - Configured the block tree to update immediately if "Show Unsaved Blocks Only" is enabled and blocks become fully saved.

### 🐛 Fixed
- **Zebra Parity and Color Alignment**:
  - Aligned background colors and line parity calculation between the Line Number Area and the Text Edit viewport, resolving visual zebra-striping misalignments.
  - Fixed a bug where warning overlays would interfere with zebra backgrounds in the text field; warning states are kept strictly in the Line Number Area.
- **Saved String Asterisk Re-emergence**:
  - Correctly updated `edited_file_data` inside the memory data store after granular saving, ensuring saved strings do not regain the modified asterisk state when focused.

## [0.3.032] - 2026-06-17

### 🚀 Added
- **Tab Relocation and Clean Spacing**:
  - Relocates `{tab}` (and escape code `{escape:6:000b}`) control codes to the start of the next line during AutoFix, preventing them from being merged back during sentence compaction.
  - Automatically cleans unwanted spaces immediately following `{tab}`.
  - Prepend `{*}` list markers if `{tab}` is present but `{*}` is missing (if star rules are enabled).
- **Session Warnings and Issues Persistence**:
  - Scheduled autosave events after issue scans and text operations to ensure that detected warnings and issues are persisted to the `.picoripi_session` file and correctly restored upon next launch.

### 🐛 Fixed
- **Missing Tag Spacing false positive**: Fixed potential false positive spacing checks on tab control characters.

## [0.3.031] - 2026-06-17

### 🚀 Added
- **A12 Warning filtering button and dialog**: Replaced the warning filter combobox (`warnings_combobox`) with a custom `Warnings: X / Y` filter button and a modal dialog (`WarningsFilterDialog`). The button displays the number of active warning filters (X) out of the total number of warning rules enabled in the settings (Y).
- **WarningsFilterDialog component**: A dedicated dialog window allowing users to filter preview results by checking/unchecking active warnings. It shows warning types with custom color tags, descriptions in tooltips, and includes "Select All" and "Select None" options.

### 🐛 Fixed
- **Preview selection synchronization**: Reconfigured warning filters to immediately reload the preview pane when warning checkboxes are toggled in the dialog. If no warnings are selected, the preview is cleared.

### 🗑️ Removed
- **CheckableComboBox component**: Removed `CheckableComboBox` class and its test suite as they were completely replaced by the button-dialog workflow.

## [0.3.030] - 2026-06-17

### 🚀 Added
- **A07 prompt context cache invalidation**: Tied caching of script lines and distilled mappings in `AIPromptComposer` to script file paths, mtime, size, and active game plugin. This prevents stale prompt contexts from being sent to AI APIs after editing timeline script files on disk.
- **Glossary Occurrence worker lifecycle**: Added proper parent-child ownership, `deleteLater` registration for automatic memory cleanup, and `prepare_to_close` thread termination hooks.

### 🐛 Fixed
- **A01 event loops removal**: Replaced nested/blocking event loop execution (`QEventLoop.exec` and `QProgressDialog.exec`) with fully asynchronous, signal-driven workflow transitions for saving files, building glossary indices, and calculating widths.
- **Save State Corruption**: Resolved a critical issue where the live edit state in `data_store.edited_data` was temporarily overridden during async partial saves, leaving the UI state corrupt until completion. Now copies transaction edits safely without mutating global state.
- **Stale Imports**: Cleaned up unused `QEventLoop` imports from `app_action_handler.py` and `glossary_handler.py`.

## [0.3.029] - 2026-06-17

### 🚀 Added
- **Speaker Editor Undo/Redo Routing**: Intercepted Undo/Redo key sequences (Ctrl+Z / Ctrl+Y) within the Speaker input combobox and routed them to the global application `UndoManager`. This prevents text typing loss and allows unified undo/redo histories.
- **Improved Speaker Folder Selection Retention**: Enhanced `BlockListUpdater` to track and restore selected speaker items during dynamic list rebuilds, avoiding focus and selection resets.

### 🐛 Fixed
- **Virtual Preview Selection Reference**: Fixed virtual folder preview indexing by mapping selected lines to `physical_block_idx` instead of `current_block_idx`, improving stability during navigation in Speaker/Chapter views.
- **Git Ignore Custom Audits**: Appended lowercase `audit.md` to `.gitignore` to prevent tracking local temporary audit logs.

## [0.3.028] - 2026-06-17

### 🚀 Added
- **Physical Block Index State**: Introduced `physical_block_idx` in `AppDataStore` to keep track of the real physical block index independently from `current_block_idx` (which can be `-2` or `-3` for Chapters and Speakers modes respectively).
- **Virtual Folders Operations Support**: Integrated `physical_block_idx` in text operations, string settings, undo manager, and autofix logic to ensure editing text or changing settings while in virtual modes correctly modifies the physical block data without triggering navigation jumps.

### 🐛 Fixed
- **Virtual Folder Jumps**: Fixed a system-wide bug where editing text or changing font/width settings inside virtual folders (Speakers or Chapters) caused the active tree selection to jump back to a physical block, preserving complete user navigation context.
- **Unit Tests Compatibility**: Fixed MagicMock type-errors and attribute errors in the test suite by monkeypatching `Mock` and `NonCallableMagicMock` classes in `conftest.py` to support `physical_block_idx`.

## [0.3.027] - 2026-06-17

### 🚀 Added
- **Speaker Terminology Rename**: Renamed Character/Characters terminology to Speaker/Speakers throughout the application UI, database components, tooltips, configuration files, and test suites to provide cleaner domain mapping.

### 🐛 Fixed
- **Navigation Context Preservation**: Fixed a major UI navigation issue where changing a speaker assignment while in a virtual Speakers directory caused the program to auto-jump back to the physical source block, causing the user to lose their navigation state.

## [0.3.026] - 2026-06-17

### 🐛 Fixed
- **Block Navigation Jump on Character Selection**: Resolved an issue where opening the character dropdown selection or choosing a character while navigating virtual folders (such as Characters or Chapters) would unexpectedly jump/reset the block tree selection to a physical block, causing the user to lose their navigation context. Normalization has also been added to treat `None`, `none`, and empty string `""` as equivalent to prevent false-positive change detections during dropdown focus events.

## [0.3.025] - 2026-06-17

### 🚀 Added
- **Virtual Characters Folder Enhancements**:
  - Implemented a dedicated `"None"` folder at the very top of the list under the virtual `Characters` tree node, grouping all lines that do not have character assignments.
  - Added support for displaying the real count of dialogue lines inside square brackets next to each speaker's name in the `Characters` folder list (e.g. `ASHEI [12]`).
  - Added a `"None"` option to the character dropdown selection box to enable clearing character assignments for any string.
  - Integrated the MemePalace speaker and glossary information directly into the character label and combobox tooltips, hiding the redundant green "Speaker" label to clean up the UI layout.
- **Robust BMG ID Normalization**: Added folder/extension normalization when matching BMG IDs from MemePalace mapping to physical project blocks, enabling accurate mapping across complex subdirectories.

### 🐛 Fixed
- **Filter Checkboxes Desynchronization**: Resolved a critical GUI issue where filters inside the preview area (such as `Show Unsaved Only`, `Hide translated`, etc.) became desynchronized with the internal `data_store` configuration on startup, session load, or project load. Implemented `sync_filter_checkboxes_with_store()` to silently restore correct graphical checkbox marks.
- **TypeError in CustomTreeWidget**: Fixed `TypeError: int() argument must be a string...` when key press events triggered item navigation inside the blocks tree widget.

## [0.3.024] - 2026-06-17

### 🚀 Added
- **Virtual Characters Navigation**: Group dialogue lines dynamically by Character speakers. Dialogue lines from any physical `.bmg` or `.json` blocks are gathered into a virtual `Characters -> Character Name` node structure in the Blocks panel. Adding strings to these folders automatically assigns the corresponding character metadata to them. Supports direct selection and interactive input of character names via a combo box located above the translation editor, instantly updating character assignments and hot-reloading virtual folders.
- **Warning-Specific Preview Filtering**: Allows filtering the preview panel by specific warning categories. Adds a checkable combo box next to the preview layout toggles, enabling users to isolate strings matching a subset of selected warnings (e.g., width violations, tag spacing errors, custom plugin validation errors), or view all warnings if no specific filters are checked.

### 🐛 Fixed
- **Integration Test Parallel Execution Race Conditions**: Combined ARC/BMG modification, verification, and reverting integration tests into a single unit test to eliminate parallel execution race conditions under `pytest-xdist`.
- **MagicMock Truthiness in Test Updaters**: Standardized the mock-window fixture initialization by explicitly defining default values for filter variables to prevent `MagicMock` truthiness from triggering unexpected preview filter branches.

## [0.3.023] - 2026-06-17

### 🚀 Added
- **Undo/Redo Command History Serialization**: Integrated the complete undo and redo stacks (`undo_stack` and `redo_stack`) from `UndoManager` directly into `AppDataStore`. These stacks are now persisted inside the `.picoripi_session` binary file via `pickle` serialization and successfully restored upon restart, enabling seamless undo/redo actions across application closures.
- **Hierarchical Unsaved Asterisk Propagation**: Implemented recursive scanning of virtual categories and project subtrees for unsaved blocks. Unsaved changes are now propagated dynamically as asterisks (`*`) all the way from modified subline blocks up to their parent category folders in the project block tree.
- **Light Theme Controls Standardization**: Standardized the visual borders, padding, and height dimensions of both the **Font** ComboBox and the **Width** SpinBox widgets inside the light theme stylesheet, ensuring perfect visual scaling and alignment.

### 🐛 Fixed
- **UndoManager Mock Compatibility**: Added direct `__dict__` checks in `UndoManager` to prevent test mock structures from dynamically spawning mock attributes and causing unexpected failures during unit testing.
- **App Exit Save Confirmation Removal**: Removed the blocking "Save changes before closing?" popups from `handle_close_event()` and `close_project_action()`, replacing them with an automatic, silent session autosave execution (`_autosave_session(force=True)`).

## [0.3.022] - 2026-06-16

### 🚀 Added
- **Granular Saving for Selected Elements**: Integrated context menu actions in the project tree to save only selected blocks and categories, leaving other modified blocks intact. Similarly, added context menus in both the translation editor and the read-only preview to save a single string or multiple selected lines.
- **Fault-Tolerant Session Autosaving**: Implemented localized workspace state saving into a `.picoripi_session` binary file using `pickle` serialization.
- **Dirty State Control**: The autosave mechanism now monitors state changes and only writes to disk if actual changes (text editing, selection navigation, filter switches) have occurred, using a 2-second debounce timer. This completely eliminates redundant I/O operations when the user is idle.
- **Instant Recovery**: If a session file is present at startup, it loads the complete workspace state immediately, bypassing standard BMG/JSON file parsing.

### 🐛 Fixed
- **MagicMock Test Crash Prevention**: Added strict type checks in `get_session_file_path()` to skip path resolution when mock structures are encountered during unit testing.
- **Strict load_session_file Verification**: Resolved a test-mock crash by using strict `is True` validation for `load_session_file()`, preventing `MagicMock` truthy evaluations from bypassing raw file parsing.
- **Safe Selection State Access**: Replaced direct references to `is_loading_data` in `list_selection_handler.py` with safe `getattr` accesses to prevent crashes in mocked test environments.

## [0.3.021] - 2026-06-16

### 🐛 Fixed
- **Dash Wrap Prevention**: Added em-dash (`—`) and en-dash (`–`) to the list of punctuation characters that cannot begin a line after width-exceeded generic text wrapping. This prevents dashes from being wrapped to the start of a new line alone.

## [0.3.020] - 2026-06-16

### 🐛 Fixed
- **Selected Text in AI Variations**: Fixed a bug where requesting AI variations for a selected text segment in `edited_text_edit` would send the entire string to the AI translation provider instead of only the selected text. The selected text is now captured immediately in the context menu logic and explicitly passed as a parameter down to `AIVariationsHandler`.

## [0.3.019] - 2026-06-16

### ⚡ Improved
- **Typing Responsiveness — Zero-Lag Input**: Eliminated UI lag and dropped keystrokes during text editing by significantly increasing the debounce delay from **250ms to 1500ms**.
  - All heavy background operations (glossary highlighting, spellcheck, issue scanner, width warning recalculation, preview update) are now deferred until the user pauses typing for 1.5 seconds.
  - During active typing, the syntax highlighter's `_typing_mode` flag suppresses: synchronous spellcheck passes (including the in-block synchronous path for `comparison_editor_text_edit` and `variations_preview_text_edit`), bad-spacing detection regex passes (double spaces, leading spaces, tag-split spaces, missing icon spacing), and glossary match rebuilding.
  - Once typing stops and the debounce fires, the `AsyncIssueScanner` runs in a background thread and sets the `_typing_mode` back to `False`, triggering a clean `rehighlight()` that applies all deferred annotations at once.



### 🚀 Added
- **Interactive AI Translation Comparison & Revision**: Integrated direct, split-view interactive comparison capabilities into `AITranslationComparisonDialog` (`dialogs/ai_translation_comparison_dialog.py`). Users can revert individual translations by clicking "Old Translation" or apply them by clicking "New Translation".
- **Inline Table Editing**: Implemented `MultilineItemDelegate` (a subclass of `QStyledItemDelegate` utilizing `QTextEdit` internally) to allow double-click editing of "New Translation" cells with support for `Ctrl+Enter` to save and `Escape` to cancel.
- **AI Variations Context Menu**: Added a custom context menu (right-click) in the comparison dialog to generate and apply AI variations for specific strings on the fly via `AIVariationsHandler.generate_variation_for_string`.
- **Expanded Spellcheck Integration & Load Tests (D31)**: Added a set of high-load integration tests to verify `SpellcheckerManager` and its background thread `SpellcheckWorker` under rapid queue flooding (500+ items), dynamic state transitions (`set_enabled` toggling), and fast program shutdown during processing.
- **Async Dictionary Loading Race Condition Tests (D31)**: Added test coverage simulating slow dictionary file loading and validating concurrent lookup/suggestion safety.

### 🐛 Fixed
- **Highlight Update Signal Loop**: Fixed a recursion loop in the comparison dialog where updating cell background colors triggered the `itemChanged` signal and reset choices.
- **Mock Parent Window Compatibility**: Resolved test errors where `MagicMock()` parents caused database operations to fail due to `isinstance(parent, QWidget)` evaluation.

## [0.3.015] - 2026-06-13

### 🚀 Added
- **Asynchronous Chapter Loading**: Integrated an asynchronous chapters loader using a background worker thread (`MemePalaceChaptersLoadWorker`) to dynamically populate virtual chapter nodes in the Block tree panel without freezing the main application GUI. Displays a clean, non-blocking `Loading...` status indicator.
- **Enhanced DataStore Type Hinting**: Added comprehensive PEP 484 type hints for core state containers in `AppDataStore`, mapping block data collections and diagnostic issues precisely to support static analyzers.

### 🐛 Fixed
- **Safe QTreeWidgetItem Lifecycle Management (D28, D29)**: Integrated PyQt6 `sip.isdeleted` lifecycle checks and try-except blocks in tree view builders, delayed selection handlers (`_delayed_select`), and virtual category cleanup methods (`_delete_folder_by_id`) to prevent C++ deleted pointer crashes.
- **Search and Replace AttributeError Fix (D30)**: Corrected a runtime crash in `SearchReviewDialog` when saving replaced strings by replacing the missing `mark_block_unsaved` project manager invocation with `data_store.mark_dirty`.
- **Background Spellcheck Worker Thread Safety**: Refactored `SpellcheckerManager` to use a robust, subclassed `QThread` (`SpellcheckWorker`) with explicit mutex-protected thread-safe message queues and early exit interrupts, eliminating GUI lockups and PyQt parent-thread warnings.
- **Thread-Local Database Connections**: Replaced redundant SQLite connection allocations in `MemePalaceClient` with a shared, thread-local connection pool and consolidated multiple BMG mapping writes inside a single SQL transaction block, dramatically improving disk I/O performance.

## [0.3.014] - 2026-06-13

### 🔄 Changed
- **Migration to PyQt6 and Refactoring**: Completed the global migration of all UI components, dialogs, widgets, and handlers from PyQt5 to PyQt6, ensuring support for modern windowing frameworks.
- **Docstring Documentation Coverage**: Added extensive Python docstrings (PEP 257 compliant) across all modules, classes, and functions in the codebase (including components, core logic, handlers, and utility scripts) to improve static linting, code readability, and development quality.
- **UTF-8 BOM Encoding**: Saved all modified Python source code files with UTF-8 BOM encoding to maximize editor compatibility under Windows environments.

## [0.3.013] - 2026-06-12

### 🚀 Added
- **Smart Search & Navigation**: Implemented punctuation-insensitive and word-level case-sensitive search behavior.
  - If the search query contains punctuation marks (e.g. `Та годі тобі, Бет`), the search performs a strict match matching punctuation. If no punctuation is typed in the search query, the engine ignores punctuation in the target strings, matching across commas, quotes, and hyphens.
  - Word-level case sensitivity: Search is case-sensitive only for words that contain capital letters in the query. For example, searching `Та` matches only `Та` (case-sensitive), but `годі` matches both `годі` and `Годі` (case-insensitive).
- **Search Focus Preservation**: Pressing the Enter key while the search input panel is active cycles to the next result, updating the text editor and highlighting the text, but keeps keyboard focus active on the search input itself. This allows for fluid, continuous "Next" traversal without manual mouse focus restoration.
- **Unit Test Coverage for Smart Search**: Added comprehensive unit tests in `tests/test_handlers/test_search_handler_logic.py` and updated existing tests in `test_search_handler.py` and `test_search_review_dialog.py` to verify the new search behavior.

## [0.3.012] - 2026-06-12

### 🐛 Fixed
- **AutoFix Dialog Settings Synchronization**: Fixed an issue where the simple "AutoFix" button click and the "Fix All" button inside the Ctrl+AutoFix settings dialog would produce different formatting results. The app now properly honors active plugin-specific configurations (such as `prevent_empty_lines_in_autofix`) in all AutoFix workflows.
- **Ctrl+Shift+A Hotkey Interference**: Corrected a bug where using the keyboard shortcut `Ctrl+Shift+A` mistakenly triggered the page-local AutoFix isolation mode. The `Shift` modifier is now ignored as a page isolation trigger when it is pressed as part of a keyboard shortcut, ensuring consistent project-wide AutoFix execution across both UI buttons and hotkeys.

## [0.3.011] - 2026-06-12

### 🚀 Added
- **Non-blocking Toast Notifications**: Implemented a custom semi-transparent black `ToastNotification` widget to notify users of events like successful saves. The notifications appear in the bottom-left corner, staying for 2 seconds with fade-out animation and a width matching the project sidebar (260-300px), without blocking user input.
- **Unit Tests for Toast Notifications**: Added a comprehensive test suite in `tests/test_ui/test_toast.py` to verify the creation, lifecycle, parent handling, and cleaning up of toast notifications.

### 🔄 Changed
- **Silent Save Flow**: Pressing `Ctrl+S` or clicking "Save" now saves the project silently without showing a modal dialog. Confirmation dialogs are now shown exclusively when closing the application with unsaved changes.

### 🐛 Fixed
- **Strict Page-Local AutoFix (Shift+AutoFix)**: Restored page isolation during Shift+AutoFix (`page_local = True`). The fixer now pads modified pages back to their original size to prevent sentences from subsequent pages from shifting upwards into empty lines on the current page, ensuring clean page-boundary enforcement even when `prevent_empty_lines_in_autofix` is globally active.

## [0.3.010] - 2026-06-11

### 🐛 Fixed
- **Sentence Compaction Breaking Page Layout**: Rewrote `_compact_sentences_on_pages` in `plugins/common/text_fixer.py` to fix a critical bug where the compactor was incorrectly restructuring pages when the input text had no empty-line padding (e.g. when `shift_split_sentences_aligned` was used or `prevent_empty_lines_in_autofix = True`).
  - **Root cause**: The old implementation rebuilt the entire page layout from scratch using an internal `page_pos` counter. When the input text had no empty-line padding (pages separated only by escape codes), the `page_pos` tracking was incorrect, causing sentences to be placed on the wrong pages — e.g. line 4 becoming "Призначай..." instead of being an empty padding line.
  - **New approach**: The compactor now works purely by **line-index arithmetic** (`line_index // lines_per_page`). It iterates over lines, and when a sentence-ending line `K` has empty slots remaining on its page, it looks for the next sentence. If that next sentence is **on the same page** (by index), a merge is attempted. If it's on a **different page** (or starts with a page-break code), the compactor **does nothing** — it never moves sentences between pages.
  - **Guarantee**: The method now never changes which page a sentence is on. It only fills empty slots within an already-established page boundary.



### 🚀 Added
- **Sentence Compaction on Pages (`_compact_sentences_on_pages`)**: New final AutoFix step in `plugins/common/text_fixer.py` that eliminates unnecessary empty padding lines between sentences within a page.
  - **How it works**: After `_shift_split_sentences` lays out pages, the compactor inspects each consecutive sentence pair. It tries to append the next sentence directly after the last line of the current sentence (on the same line), then re-wraps the combined text by width. If the wrapped result fits within the remaining lines of the current page, the sentences are merged. Otherwise the next sentence is pushed to a new page.
  - **Result**: `"Речення перше\nпродовження.\n\nРечення друге"` → `"Речення перше\nпродовження. Речення\nдруге"` when both fit on the page.
  - **`prevent_empty_lines_in_autofix` flag**: When enabled, empty padding lines between sentences are removed; when disabled, they are preserved as-is before a page boundary.
  - **Sentence detection**: Sentence boundary = line ending with `.` `!` `?` `;` (or closing quote/paren after these). Page-break escape codes (e.g. `{escape:0:0007...}`, `{pause}`) are always hard sentence/page boundaries and are never merged across.
  - **Gate**: The compaction step is activated only when the `SHORT_LINE` AutoFix option is enabled, since it is semantically part of "reducing short/empty lines".
  - **Placement**: Runs **before** `_fix_single_word_orphans_generic` so that any single-word orphans created by compaction are immediately cleaned up.
  - **Scope**: Applied uniformly to all 5 plugins: `zelda_bmg`, `zelda_ww`, `zelda_mc`, `pokemon_fr`, `plain_text`.



### 🐛 Fixed
- **Green SHORT_LINE Warnings Vanishing After AutoFix**: Fixed a race condition where green "short line" warning highlights would silently disappear after pressing AutoFix, even when no text was actually changed.
  - **Root cause**: Any `AsyncIssueScanner` that was still running from a previous typing session could complete *after* the synchronous `_rescan_issues_for_current_string` call inside AutoFix, overwriting the freshly computed `problems_per_subline` with stale results based on the pre-fix text.
  - **Fix**: AutoFix now cancels the in-flight async scanner at the very start (before running the fix logic). After the synchronous rescan, a new `AsyncIssueScanner` is launched against the fixed text so glossary and spellcheck highlights are also refreshed correctly.
  - **No-change case**: When AutoFix makes no textual changes, a synchronous rescan is now performed and the UI is refreshed (`update_text_views`). This prevents stale async scans that may have been queued before AutoFix from later clearing existing problem highlights.
- **Added `_launch_async_scanner_for_fixed_text` helper** in `TextOperationHandler` that correctly constructs and submits a new `AsyncIssueScanner` for a given fixed text, reusing the same parameters as the typing-debounce path but without going through the debounce timer.



### 🔄 Changed
- **Git Ignore Spellchecker Cache**: Excluded the dynamic Hunspell spellchecker cache (`resources/spellchecker/spell_cache.json`) from Git tracking and added it to `.gitignore` to prevent unnecessary large binary diff commits and history pollution.

## [0.3.006] - 2026-06-11

### 🚀 Added
- **Asynchronous Save & Archive Packing**: Integrated `SaveWorker(QThread)` in `DataStateProcessor` and `AppActionHandler` to perform disk saves and Yaz0 archive compression on a background thread. Leverages a modal `QProgressDialog` and local `QEventLoop` to block the GUI during execution without triggering "Not Responding" application freezes.
- **Dedicated AI Variations Handler**: Decomposed `TranslationHandler` by extracting caching, generation, and selection of AI translation variations into a specialized `AIVariationsHandler` class in `handlers/translation/ai_variations_handler.py`.

### 🐛 Fixed
- **MemePalace Worker GUI Freezes**: Removed high-latency `build_occurrence_index` invocations from intermediate progress reporting callbacks (`_handle_worker_progress`) in `ui/mempalace_builder_dialog.py`. The index is now rebuilt exactly once after the worker finishes executing.
- **Spellchecker Startup Blocking**: Relocated the heavy synchronous Hunspell dictionary initialization (`Dictionary.from_files`) from the GUI thread constructor to an asynchronous background worker using `threading.Thread`. Replaced risky timers with a type-safe PyQt signal `dictionary_loaded` to thread-safely register the dictionary instance with the GUI thread.

### ⚡ Improved
- **SQLite Database Transaction Performance**: Optimized database operations in `MemePalaceClient` and `MemePalaceWorker` by adding support for shared connection context managers and wrapping multi-row insertion loops within single transaction blocks (`BEGIN/COMMIT`), dramatically reducing Disk I/O overhead.

### 🧪 Tested
- **Comprehensive Async & Decomposed Test Suites**: Added new unit tests verifying the asynchronous dictionary loading flow (`test_core/test_spellchecker_manager.py`), background save worker lifecycle and event loops (`test_app_action_handler.py`), and the state/caching behavior of the new `AIVariationsHandler` (`test_handlers/test_translation/test_ai_variations_handler.py`).

## [0.3.005] - 2026-06-11

### 🚀 Added
- **Handler Decomposition & SRP Compliance**: Extracted text wrapping and pagination logic from `translation_handler.py` into a dedicated `TextFormatter` class inside `handlers/translation/text_formatter.py`. Also refactored virtual folder operations from `project_action_handler.py` into a specialized `VirtualFolderHandler` class inside `handlers/virtual_folder_handler.py`. This ensures proper separation of concerns, simplifies maintenance, and improves overall system architecture.
- **Double-Click Variation Apply Fix**: Resolved an `AttributeError: 'MainWindow' object has no attribute 'current_font_map'` crash that occurred when double-clicking or applying options in the AI Translation Variations dialog, by using `getattr` to safely access `current_font_map` or fallback to `font_map`.

### 🧪 Tested
- **TextFormatter & VirtualFolderHandler Unit Tests**: Implemented comprehensive unit test suites in `tests/test_handlers/test_text_formatter.py` and `tests/test_handlers/test_virtual_folder_handler.py` to verify formatting accuracy and project tree folder operations.

## [0.3.004] - 2026-06-11


### 🚀 Added
- **AI Variations Progress Highlights Scroll Compensation**: Constrained the soft-green relative length progress bar highlights to the visible area (`viewport().width()`) in the AI Translation Variations dialog, and adjusted the painting offset by the horizontal scroll position (`scroll_bar.value()`). This prevents the progress bar background from scrolling off-screen and allows users to easily compare variation lengths visually without horizontal scrolling.
- **Button/Icon Tag Parentheses Normalization**: Implemented automated tag normalization in `is_visible_tag` and `get_tag_width` (`utils/utils.py`). This allows the editor to successfully resolve button/icon tags written without parentheses (such as `{btn5}`) against parenthesized definitions in mappings (`aliases.json`) and font metrics (`font_map.json`). It correctly computes their physical display width and eliminates false "bad spacing" and "extra spacing" warnings.

### 🧪 Tested
- **Tag Normalization Unit Test**: Added test coverage in `tests/test_spacing_rules.py` verifying that unparenthesized tags (e.g. `{A}`) are correctly recognized as visible when parenthesized definitions are present in the active configuration.

## [0.3.003] - 2026-06-11

### 🚀 Added
- **Option to prevent empty padding lines in AutoFix**: Added `prevent_empty_lines_in_autofix` option to the plugin settings and Ctrl+AutoFix dialog. This prevents the pagination/wrapping logic from adding trailing blank lines on page boundaries when autofixing.
- **Single Word Orphan Auto-Fix Protection**: Relocated the single-word orphan fixer step (`_fix_single_word_orphans_generic`) to the final stage of text autofix execution, executing it after wrapping and pagination to prevent pagination rules from reversing orphan corrections.

### 🔄 Changed
- **Unconditional Sentence Alignment with Original**: Improved `shift_split_sentences_aligned` to unconditionally strip old page split codes and accurately insert original page breaks (e.g. `[escape:0:0007...]`) from matching source sentences when aligning translations to the original page layout.
- **Plugin Parameter Passing**: Refactored the core pagination helper in all 5 plugins (`zelda_bmg`, `zelda_ww`, `zelda_mc`, `pokemon_fr`, `plain_text`) to accept `block_idx` and `string_idx` parameters, ensuring correct font assets and width configuration constraints are accessed during mass/batch autofix tasks.
- **UIUpdater Refactoring**: Cleaned up code duplication in `UIUpdater` by removing direct private methods (`_create_menu`, etc.) that were delegated to `main.py`.

## [0.3.002] - 2026-06-10

### Added
- **Auto-width from Original (B10)**: Implemented an automated text limit matching mechanism. Added "Auto-width from original" checkbox to `MassWidthDialog` for single/multiple selected strings in Strings in Block. When enabled, it calculates the maximum pixel width among all sublines of the original string (taking into account active font maps, control tags, and icons) and assigns this value individually to each target string in the translation editor.
- **Context Menu 'Set Width from Original'**: Integrated a quick action shortcut directly into the `Width` spinbox context menu on the right-hand settings panel, allowing users to instantly fetch and apply the original string's max width for the currently active translation item.
- **Width tags as words (B9)**: Upgraded the single-word line spacing validator to treat tags that have a physical display width (e.g., buttons like `[L-Stick]`, `{PLAYER}`, `{var:0}`) as words, successfully resolving false single-word alignment warnings.

## [0.3.001] - 2026-06-09

### Fixed
- **PyQt6 Migration: Dialog Return Codes**: Replaced deprecated `QDialog.Accepted` and class-specific `Accepted` attributes with `QDialog.DialogCode.Accepted` across all dialog handling code to prevent `AttributeError` runtime crashes:
  - `handlers/text_operation_handler.py` (AutofixSelectionDialog)
  - `handlers/translation/glossary_handler.py` (CategorySelectionDialog)
  - `ui/components/bfn_preview_widget.py` (TextEffectsDialog)
  - `components/project_dialogs.py` (NewProjectDialog, OpenProjectDialog, ImportBlockDialog)
  - Updated mock-dialog asserts in `tests/test_text_operation_handler.py` to check for `QDialog.DialogCode.Accepted`.
- **PyQt6 Migration: Qt Enums Namespace**: Fixed `AttributeError: type object 'Qt' has no attribute 'TopLeftCorner'` crash when opening the AI Chat window by referencing `Qt.Corner.TopLeftCorner`.
- **Recursion Safeguard for Descriptors**: Updated `SettingsManager` and `GlobalSettings` to ignore class descriptors (detecting them via `hasattr(attr, '__set__')`) during settings loading to prevent infinite recursion loop on attributes like `theme` or `editors_font_size`.

### Changed
- **MainWindow Properties Refactoring (B8)**: Replaced 26 redundant boilerplate property-proxies for state and settings flags in `MainWindow` with unified class-level Python descriptors (`StateProperty` and `SettingsProperty`), shrinking `main.py` code footprint and enhancing maintainability.
- **ProjectContext Decoupling & Typing (B2, B3)**: Finalized strict type hinting and protocol structures on `BaseHandler` and `ProjectContext` (`core/context.py`) and purged old defensive `hasattr`/`getattr` calls.

## [0.3.000] - 2026-06-09

### Changed
- **Major Milestone: Migration to PyQt6**: Upgraded the entire graphical engine and UI subsystems from PyQt5 to PyQt6, ensuring support for modern windowing frameworks, high-resolution rendering, and long-term ecosystem compatibility.
- **Deduplication of Plugin Configurations**: Created a unified `plugins/common/config_factory.py` to generate baseline problem check configurations, пріоритетів та кольорів для всіх плагінів (`zelda_ww`, `zelda_mc`, `zelda_bmg`, `pokemon_fr`, `plain_text`), reducing config boilerplate to simple custom overrides.

## [0.2.179] - 2026-06-09

### Fixed
- **Grey Space Dot Indicators for Multiple Spaces**: Fixed space dot indicators (`·`) representing double/multiple spaces or bad spacing turning black under default styles. They are now rendered in the standard grey color (`#BBBBBB`) matching end-of-line spacing dots.

## [0.2.178] - 2026-06-09

### Fixed
- **Clean Mock Imports in Production**: Removed `unittest.mock` imports completely from production code files (`plugins/common/text_fixer.py` and `handlers/list_selection_handler.py`). Used class name inspection `'Mock' not in type(obj).__name__` as a runtime safeguard.
- **Double HotkeyManager Initialization Fix**: Removed duplicate creation of `HotkeyManager` in `_init_handlers` inside `main.py`.

## [0.2.177] - 2026-06-09

### Changed
- **Audit Documentation Update**: Refreshed the architectural audit documentation in `AUDIT.md` to map out the current PyQt6-based status of Category A and Category B refactoring sprint lists.

## [0.2.176] - 2026-06-09

### Fixed
- **PyQt6 Migration: QDialog.Accepted Namespace**: Fixed `AttributeError: 'QDialog' object has no attribute 'Accepted'` runtime crash when accepting prompt, project, or block dialogs. In PyQt6, `Accepted` must be referenced via `QDialog.DialogCode.Accepted`. Fixed all occurrences in:
  - `handlers/translation/translation_ui_handler.py`
  - `handlers/translation_handler.py`
  - `handlers/project_action_handler.py`
  - `tests/manual_test_project_dialogs.py`
  - `tests/test_handlers/test_project_action_handler.py` (updated mocks to expect `QDialog.DialogCode.Accepted` to prevent test failures)

## [0.2.175] - 2026-06-09

### Fixed
- **Spellcheck Test: Incorrect `highlightBlock` Assertion**: Fixed `test_translation_editor_spellcheck_highlighting` in `tests/test_ui/test_search_panel_spellcheck.py`. The test previously mocked `currentBlock()` in a way that caused `block.isValid()` to return `False`, setting `block_number = -1` and bypassing the entire spellcheck path. The test now supplies a properly configured mock block (`isValid=True`, `position=0`, `blockNumber=0`), patches `setFormat` at the class level to capture calls via their `underlineStyle()`, and correctly asserts `SpellCheckUnderline` is applied to the misspelled word range.

## [0.2.174] - 2026-06-09


### Fixed
- **PyQt6 Migration: QStyle.SP_* Enum Namespace**: Fixed `AttributeError: type object 'QStyle' has no attribute 'SP_...'` errors that crashed context menus (both tree and editor). In PyQt6, standard pixmap constants moved from the flat `QStyle.SP_*` namespace into `QStyle.StandardPixmap.SP_*`. Updated all occurrences across:
  - `components/editor/lnet_context_menu_logic.py` (glossary, spellcheck, translate, AutoFix, revert, restore menu actions).
  - `components/editor/mouse_handlers.py` (AI discuss action icon).
  - `components/tree_context_menu_mixin.py` (all project tree context menu icons).
  - `components/project_dialogs.py` (folder creation and navigation dialogs).
  - `components/folder_delete_dialog.py` (delete confirmation dialog icon).
- **PyQt6 Migration: QTextCursor.SelectionType Enum Namespace**: Fixed `AttributeError: type object 'QTextCursor' has no attribute 'WordUnderCursor'/'BlockUnderCursor'` errors in editor and spellcheck logic. Selection type constants moved to `QTextCursor.SelectionType.*` in PyQt6. Updated:
  - `handlers/text_operation_handler.py` — word-under-cursor selection during issue scan.
  - `components/editor/lnet_context_menu_logic.py` — word selection for glossary add (two locations).
  - `components/editor/lnet_spellcheck_logic.py` — block selection when applying spellcheck corrections.
- **Clean Console Output**: Removed all diagnostic `print()` statements that polluted the console during startup and normal operation (from `main.py`, `line_numbered_text_edit.py`, `syntax_highlighter.py`, `hotkey_manager.py`, `custom_tree_widget.py`, `bfn_preview_widget.py`). The application now outputs only structured log messages via the rotating file logger.
- **Problem Count Display on Startup**: Fixed issue counts in parentheses not appearing next to compacted virtual folder names until the user clicked each block. The `_add_virtual_folder_to_tree` method in `block_list_updater.py` now calculates and applies issue counts for all `compaction_type == 2` folders immediately during initial tree population.
- **Tooltip globalPos Crash**: Fixed `AttributeError: 'QMouseEvent' object has no attribute 'globalPos'` that occurred when hovering over line numbers in the block list. Replaced the PyQt5-only `event.globalPos()` call with the PyQt6-compatible `QCursor.pos()` in `custom_list_item_delegate.py`.

## [0.2.172] - 2026-06-08


### Added
- **Spellchecking in Search Panel**: Integrated spellchecking functionality into the search panel (`SearchPanelWidget`). When a user enters text into the search edit field (`SearchLineEdit`), it dynamically analyses the string and highlights misspelled words with a red wavy underline, matching standard IDE styling without modifying overall widget colors or backgrounds. It also features a custom context menu (right-click) providing correction suggestions and an option to add words to the user dictionary, while ensuring no styling conflicts occur with standard menus (`QMenu`).
- **External Asset Uploader copy to USB**: Modified `pack_iso.bat` to scan for active external storage (checking drive letters `A, B, F, H..Z`) containing a `dusk` directory and target ISO file. If found, it automatically rebuilds the ISO and copies both the game ISO and the memory card save file (`01-GZ2E-gczelda2.gci`) onto the external drive using `robocopy` with a live console copy progress indicator (`%`).

## [0.2.171] - 2026-06-08

### Added
- **Persistent "Hide Empty Strings" Filter**: Enabled saving and restoring the "Hide Empty Strings" checkbox filter state across application restarts by storing it in the global configuration file (`settings.json`). Bypassed MagicMock serialization issues during testing.

### Fixed
- **Persistent Console Window for External Script Runner**: Upgraded the external script execution on Windows to use `cmd.exe /k` with a brand-new console window (`CREATE_NEW_CONSOLE`). This ensures scripts and batch files are executed inside an active, visible command line prompt that remains open after execution, allowing the user to review compilation logs, output, or emulator start details.

## [0.2.170] - 2026-06-08

### Fixed
- **Twilight Princess Auto-fix Behaviour**: Fixed a bug where Auto-fix would incorrectly merge lines separated by a page break code (`{escape:0:0007000a}`) or empty lines, ruining manual page layouts.
- **Empty Line Preservation in Wrapping**: Updated `shift_split_sentences` in `utils.py` to preserve empty lines as page boundaries and respect page break escape codes, ensuring sentences are wrapped cleanly without merging pages.
- **Unit Test Alignment**: Updated and adapted `test_autofix_page_isolation` in `tests/test_spacing_rules.py` to expect empty line preservation, ensuring the entire test suite remains green.

## [0.2.169] - 2026-06-08

### Added
- **Modal Progress Blocking on Filter Reset**: Integrated fully synchronous chunked rendering under a modal `QProgressDialog` (with instant duration `setMinimumDuration(0)`) when disabling "Show Overrides Only" filter for large blocks. This blocks all user interaction and shows a smooth loading progress from 0% to 100%.

### Fixed
- **Scroll Position Flicker/Jump**: Fixed a bug where disabling filters caused the scrollbar to momentarily reset to 0 (top) before bouncing back. The scrollbar position is now restored programmatically while the modal progress dialog is active, preventing visual glitches.
- **Unit Test Compatibility**:
  * Fixed `TypeError` in `test_populate_strings_chunked` and `test_populate_strings_lazy_loads_from_cache` by bypassing chunked rendering paths when the document object is a Mock/MagicMock.
  * Fixed `test_UIUpdater_populate_strings_preserves_scrollbar` by mocking `displayed_string_indices` correctly to reflect unchanged string visibility.
  * Fixed `test_ListSelectionHandler_toggle_show_overrides_only_unchecked_same_string` to assert `setValue` on the vertical scrollbar instead of the decommissioned `QTimer.singleShot` behavior.

## [0.2.168] - 2026-06-08

### Added
- **Preview Cache Key Filter Sensitivity**: Expanded `PreviewUpdater.get_cache_key` to a 6-tuple key `(block_idx, category_name, show_overrides, hide_trans, hide_cat, hide_empty)` so that different filter settings (such as "Show Overrides Only") cache their filtered lines separately.
- **Cache Synchronization on Text Edit & Revert**: Added `PreviewUpdater.update_cached_string` to automatically synchronize edited and reverted string preview lines across all cached filter configurations of the same block, preventing stale preview text after toggling checkboxes.
- **Lazy Loading for Cached Blocks**: Integrated lazy loading for cache hits where the number of lines is large. Rather than setting the entire text synchronously (which freezes the UI layout thread), the first 200 lines are set instantly and the rest are loaded incrementally using the background timer.
- **Background Timer Cache Reuse**: Optimized `_load_next_preview_chunk` to directly fetch ready preview strings from the cache when available, avoiding redundant text representation calculations.

### Fixed
- **Pre-Cache Unit Test Alignment**: Fixed the mock window data store in `test_PreviewUpdater_pre_cache_all_blocks` unit test inside `tests/test_ui/test_ui_updater.py` by initializing filter boolean flags to prevent MagicMock attribute lookup errors during assertions on the new 6-tuple keys.

## [0.2.167] - 2026-06-08

### Fixed
- **MassWidthDialog Default Value Fix**: Fixed a bug where the **Default** button in the "Set Width for Multiple Lines" dialog (`MassWidthDialog`) incorrectly reset the width to the warning threshold (`line_width_warning_threshold_pixels`, e.g., 410px) instead of the project maximum width setting (`game_dialog_max_width_pixels`, e.g., 435px). The default width value and QLabel description were updated to correctly reference `game_dialog_max_width_pixels` and support resets using both `0` and `game_dialog_max_width_pixels`.
- **Unit Test Alignment**: Updated `test_update_string_settings_panel_default_meta` and `test_update_string_settings_panel_custom_width` unit tests inside `tests/test_ui/test_updaters/test_small_updaters.py` to assert the stylesheet changes directly on `width_spinbox` instead of its nested `lineEdit()`, ensuring all tests pass with no regressions.

### Changed
- **Unified & Bold Font/Width Highlights**: Unified the visual feedback styles for the string settings panel. Both the `QComboBox` (Font) and the `QSpinBox` (Width) fields now share an identical CSS class styling (`self.highlight_style`), applying a bold `2px solid rgb(186, 85, 211)` bright-purple border and a soft-purple background `rgba(186, 85, 211, 40)` when custom overrides are active.
- **Improved QSpinBox Styling**: Transitioned stylesheet application from the internal line edit field (`width_spinbox.lineEdit()`) to the top-level `QSpinBox` widget, making its internal line edit background transparent and removing its internal border. This draws a complete border around the entire widget without breaking or hiding the native step up/down arrow buttons on Windows platforms.

## [0.2.166] - 2026-06-06

### Fixed
- **Search Review Dialog Unit Test Alignment**:
  - Updated the expected match line indices inside `test_SearchReviewDialog_find_matches` unit test to reflect the removal of artificial blank spacers. The second match now correctly evaluates to line index `2` instead of `4`.

## [0.2.165] - 2026-06-06

### Fixed
- **Horizontal Separators inside Multi-line Messages in Advanced Search**:
  - Fixed a bug where horizontal green separator lines were incorrectly drawn inside multi-line messages (e.g. message 1532 with 11 lines). The logic now uses `custom_message_numbers` to accurately detect the boundaries of message blocks and only draws separators when transitioning to a different message.
  - Replaced the visual row index `doc_visual_line_index` with the logical `QTextBlock.blockNumber()` inside `LNETPaintEventLogic` to prevent separator misalignment (splitting) when automatic text wrapping is active.
  - Ensured that the separator line is only drawn beneath the last visual line of a block (`i == layout.lineCount() - 1`).

## [0.2.164] - 2026-06-05

### Added
- **Tag Word-Shifting Support in AutoFix**:
  - Upgraded the single-word orphan shifting logic (`_fix_single_word_orphans_generic`) in `plugins/common/text_fixer.py` to correctly treat visible tags (such as button/icon tags `{(Y)}`, `{(X)}`) and forced tags (such as `{F:Link}`) at the end of the previous line as words, allowing them to be pulled down to resolve orphans on the next line.
  - Added unit test cases in `tests/test_spacing_rules.py` verifying correct shifting of visible and forced tags from the previous line.
- **Smart Alt+Up/Down Navigation**:
  - Upgraded the `Alt+Up` and `Alt+Down` shortcuts in `ui/ui_event_filters.py` to skip empty lines (lines containing no text, visible tags, or forced tags) in the preview list.
  - Added a new unit test suite in `tests/test_ui/test_ui_event_filters.py` to verify the smart navigation behavior.

## [0.2.163] - 2026-06-05

### Changed
- **Refined Single Word Orphan Auto-fix**:
  - Moved the `_fix_single_word_orphans_generic` step to run as a post-processing pass at the very end of `autofix_data_string`, rather than inside the main formatting loop. This completely avoids feedback loops that caused text to be split into unnecessarily short lines.
  - Added smart punctuation checks: a single word at the end of a line is no longer pulled to the previous line if it ends with punctuation (`.`, `,`, `!`, `?`, `;`, `:`, `…`, `)`).
  - Added sentence boundary protection: a word is not pulled if the previous line ends with sentence-ending punctuation (`.`, `!`, `?`, `…`).
- **Unused Logical Warnings Cleanup**:
  - Removed the inactive `Empty Odd Logical Subline` (`PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL`) warning definitions and settings from `zelda_bmg` and `zelda_ww` plugins to simplify the settings UI.

## [0.2.162] - 2026-06-05

### Added
- **Missing Icon Spacing Detection & Auto-fix**:
  - Implemented a new light-blue warning (`QColor(173, 216, 230, 150)`) for identifying missing spaces adjacent to visible tags (button tags containing parentheses `(...)` or tags with positive widths).
  - Added new helper functions `is_visible_tag`, `find_missing_icon_spacing_spans`, and `fix_missing_icon_spacing` to `utils/utils.py` to handle the detection and spacing repair.
  - Enabled the new warning to turn on/off via the project settings dialog under "Detection" and "Auto-fix" tabs (`PROBLEM_MISSING_ICON_SPACING` / short name `"IconSpacing"`).
  - Integrated the spacing checks into the problem analysis pipelines of all game plugins: `zelda_mc`, `zelda_ww`, `zelda_bmg`, `pokemon_fr`, and `plain_text`.
  - Integrated the autofix rules for missing icon spacing into the Auto-fix engines of all plugins for both local and project-wide Auto-fix operations.
  - Added full test coverage for the visibility checks, span extraction, and plugin-specific Auto-fix behaviors in `tests/test_spacing_rules.py`.

### Changed
- **Adjacent Punctuation Exemption**:
  - Refined the spacing check rules: punctuation marks (`.`, `,`, `!`, `?`, `-`, `:`, `;`) adjacent to visible tags are now exempt from triggering the missing spacing warning. This ensures that icons/buttons do not merge with words, while keeping the native sentence structure and punctuation flow intact.
- **Double Space Check Polish**:
  - Updated `_check_bad_spacing` in the generic problem analyzer to treat visible tags as text placeholder `"X"` rather than stripping them, which prevents false double-space warnings (yellow warning) when spaces are correctly placed on both sides of a physical button.

## [0.2.161] - 2026-06-04

### Added
- **Split "Hide tags" Feature**:
  - Replaced the single global "Hide tags" setting with independent `hide_original_tags` and `hide_translation_tags` properties in `AppDataStore`.
  - Added individual `Hide tags` checkboxes to both the Original (Read-Only) panel and the Translation (Editable Text) panel.
  - Updated the syntax highlighter (`JsonTagHighlighter`) to dynamically inspect the widget context and apply transparent formatting + percentage spacing + stretching to collapse hidden tags to absolute 0 width.
  - Added new slot methods `toggle_hide_original_tags` and `toggle_hide_translation_tags` to `list_selection_handler.py` to synchronize state changes and refresh views correctly.
  - Added unit test coverage verifying the independent visibility behavior in `test_syntax_highlighter.py`.

## [0.2.160] - 2026-06-03

### Added
- **Non-Zero Width Tag Spacing Protection**:
  - Excluded tags with non-zero width/length (such as game button icons `{(Y)}`, `{(X)}`, `{(DUP)}`) from being flagged by spacing checks.
  - Added `get_active_font_map()` and `get_active_icon_sequences()` helpers to `utils.py` to retrieve active workspace metrics dynamically.
  - Updated `clean_spaces` in `utils.py` to treat non-zero width tags as text (words), preserving necessary spacing around icons during auto-fix/pasting.
  - Modified the syntax highlighter (`syntax_highlighter.py`) to skip bad spacing highlights (red wavy underline) around tags that have physical length.
  - Updated `_check_bad_spacing` in `problem_analyzer.py` to replace non-zero width tags with a dummy character `"X"` instead of stripping them, preventing false double-space warnings.
  - Added robust unit test coverage in `test_spacing_rules.py` and `test_syntax_highlighter.py`.

## [0.2.159] - 2026-06-03

### Fixed
- **Unified Search Line Selection**:
  - Fixed a search navigation bug where the found string was not visually highlighted or updated in the `StringsInBlock` list if it matched the currently active string index. Now, selecting a found match unconditionally updates `StringsInBlock` and synchronizes both original and translation editor views.
- **AI Variations Caching Polish**:
  - Modified the AI Variations logic to display cached variants instantly even if the current translation has been modified, preventing unwanted automatic AI token consumption. Users can fetch updated variations manually using the "Refresh" button in the variations window.
- **Global Settings Mock Serialization Fix**:
  - Added strict type checking for `translation_presets`, `current_translation_preset`, `variations_window_geometry`, and `variations_splitter_state` when saving settings. This prevents serialization of `MagicMock` instances during unit test runs, resolving multiple `TypeError` test crashes.

## [0.2.158] - 2026-06-03

### Added
- **AI Translation Presets**:
  - Implemented a complete preset system for AI Translation settings directly inside the Settings Dialog (AI Translation tab).
  - Added a dropdown selector (`Preset:`) alongside **Save Preset** and **Delete Preset** buttons.
  - Allows saving all active AI Translation parameters (provider, endpoint, api key, model, temperature, max tokens, timeout) under a custom name, with easy switching back and forth.
  - Saved presets are persisted globally in `settings.json` under `translation_presets`, with the active selection tracked by `current_translation_preset`.
  - Fully covered the new preset loading, saving, and deleting logic with new unit tests in `test_settings_dialog_presets.py`.

## [0.2.157] - 2026-06-03

### Added
- **AI Variations Caching & Refresh Options**:
  - Implemented caching for generated translation variations: opening AI Variations for the same string displays cached variants instantly without calling the API again.
  - Added a "Refresh" button in the AI Variations window to discard the cache and fetch fresh translations.
- **Force Alias Polish**:
  - Added a "Do not show next time" checkbox to easily suppress the Force Alias informational dialog.
  - Re-mapped the informative text from the popup to be displayed as a tooltip on the "Force Alias" checkbox.
  - Automatically disables the alias width input field when the "Force Alias" option is enabled.

### Fixed
- **Unified & Corrected Search Navigation**:
  - Combined the normal and advanced search logic to ensure consistent result lists across both modes.
  - Resolved the index shifting bug when navigating to a string from search results: replaced `string_selected_from_preview` with `select_string_by_absolute_index` to jump to the correct string even with active list filters.
  - Fixed highlighting in the read-only preview edit by calculating the dynamic relative indices properly.
- **Unit Tests Stabilization**:
  - Fixed various unit test failures caused by `MagicMock` parent window mismatching, ensuring the entire test suite passes without regressions.

## [0.2.156] - 2026-06-03

### Fixed
- **Preview Toggle Visibility & Background Resource Usage**:
  - Fixed a bug where hiding the BFN visual preview window via the toolbar or View menu toggle button would cause it to automatically reappear on any subsequent text edit or row selection. The visibility state is now strictly controlled by the `toggle_preview_action` state.
  - Implemented immediate preview text updates when showing the preview panel again, preventing a blank or stale screen from rendering.
  - Integrated `self.isHidden()` guards within both `update_preview_text()` and `paintEvent()` of the `BfnPreviewWidget`. When the preview is toggled off, all text layout calculations (`BfnCore.layout_text`), shadow/glow effect rendering, and offscreen canvas operations are entirely bypassed, ensuring zero CPU and GPU resource usage in the background.

## [0.2.155] - 2026-06-02

### Added
- **Archive Size Verification Warning**:
  - Implemented automatic file size checking for all modified archives against their original counterparts during native packing inside `core/data_state_processor.py`.
  - Added a visual warning popup (`QMessageBox.warning`) that alerts the user if any packed translation archive exceeds the original on-disk size, prompting them to shorten translation strings to avoid ROM crashes and truncation.
  - Added unit test validation coverage inside `test_data_state_processor_native_packing.py`.

## [0.2.154] - 2026-06-02

### Added
- **High-Compression Candidate Extension & Alignment Tuning**:
  - Parameterized the sliding-window match lookup candidates (`max_candidates`) in the pure-Python Yaz0 compression algorithm, defaulting to `100` instead of `25`.
  - Added support for auto-padding compressed Yaz0 archives to match exact original disk-sector boundaries using trailing zero-padding (`\x00`).
  - Achieved smaller compressed archive footprints than original file sizes (124,552 bytes vs 124,756 bytes) to completely bypass in-place file replacement and FST size limitations in retro modding environments.

## [0.2.153] - 2026-06-02

### Added
- **High-Performance Lazy LZ77 Yaz0 Compressor**:
  - Replaced the legacy naive literal-only `compress` implementation in `core/containers/yaz0.py` with a highly optimized sliding-window LZ77 Yaz0 compression algorithm featuring lookahead lazy evaluation.
  - Implemented prefix-based hash mapping to prune search space, capping candidates lookup to 25 to achieve sub-second compression runs (~0.37s for Zelda TP `bmgres.arc`) with maximum performance in pure Python.
  - Resolved console-crashing buffer overflows and out-of-memory errors on GameCube and Wii hardware caused by legacy archives being 3x larger than the original optimized archives.
  - Achieved a highly optimized compression ratio matching official Nintendo tools within a 0.24% file size difference (125 KB vs 124 KB).
  - Added new robust regression testing `test_yaz0_compression_ratio_against_original` in `test_containers.py` to continuously verify compression ratios and lossless roundtrip decompressions on original assets.
- **Smart Empty Lines Hiding & Gutter Highlight**:
  - Implemented a smart empty lines collapse threshold inside `populate_strings_for_block` in `ui/updaters/preview_updater.py`.
  - Single or double consecutive empty lines are kept fully visible in the read-only preview panel to preserve minor paragraph breaks, whereas sequences of 3 or more empty lines are collapsed into a single placeholder: `[start-end] X empty line(s)`.
  - Added regex-based early matching (`_PLACEHOLDER_PATTERN`) inside `JsonTagHighlighter.highlightBlock` (`utils/syntax_highlighter.py`). When the read-only preview panel encounters a collapsed empty lines placeholder, the entire line is instantly styled with a subtle dark gray color (`#888888`) and bypasses all other syntax formatting rules (such as bracket tags or spellchecking), keeping the preview clean and uncluttered.
  - Added new regression and unit tests: `test_populate_strings_hide_empty_strings` in `test_small_updaters.py` and `test_JsonTagHighlighter_placeholder_highlighting` in `test_syntax_highlighter.py`.

### Fixed
- **Corrupted MID1 Message ID Section Dropped in Zelda TP Archives**:
  - Fixed a critical bug in `bmg_tool.py` where Twilight Princess archives `bmgres1.arc` through `bmgres8.arc` had their `MID1` Message ID mapping sections completely deleted when re-saving.
  - The bug was triggered by a GameCube BMG header quirk where `entry_len` was set to `4096` (`0x1000`) instead of `4` in the `MID1` section header. The parser trusted this literally, loading all Message IDs as corrupted string lists. When saving, the writer evaluated the ID type and assumed there were no valid integer message IDs (`has_ids = False`), causing the entire `MID1` section to be dropped from the file.
  - Implemented automatic entry length validation: if `entry_len` is not a standard stride (4 or 8), the real stride is dynamically computed based on the section's actual bytes and entry count: `(section_size - 16) // count`.
  - Restored absolute byte-perfect load and save parity (**Byte-perfect identical: True**) across all nine Twilight Princess game archives, successfully preserving all game control structures.

## [0.2.152] - 2026-06-01

### Fixed
- **Glossary Global Replace Flow & UI Synchronization**:
  - Upgraded `global_replace` in `GlossaryManager` to track and return all modified glossary entries (including changes in original terms and descriptions/notes), rather than restricting returns to translation changes only.
  - Implemented smart filtering inside `global_replace_glossary` in `GlossaryHandler` to skip project-wide string translation synchronizations for entries where the translation column was not altered.
  - Resolved a critical bug where performing a global replace on glossary term notes (e.g., changing "Русл" to "Расл") erroneously reported "No occurrences found in the glossary" and failed to refresh the dynamic UI, despite saving successfully to disk.

## [0.2.151] - 2026-06-01

### Fixed
- **Width Guideline and Hard Warning Split**:
  - Re-anchored vertical line guidelines to correctly turn red upon crossing the desired `line_width_warning_threshold_pixels` (e.g. 422px), rather than the hard game dialog limit.
  - Eliminated premature red width-limit warning markers in the line numbers column for string lengths between the warning threshold (422px) and the game maximum width limit (460px).
  - Ensured auto-fix and background width calculations default back to the warning threshold for smart page/word wrap targets.
  - Introduced `"cache_format_version": 2` settings validation to safely invalidate old cached issue scans containing deprecated warnings.

## [0.2.150] - 2026-06-01

### Added
- **Balanced Proportional Word Wrapping**:
  - Implemented a sophisticated proportional word wrap algorithm in `_format_and_wrap_translation` within `handlers/translation_handler.py`.
  - The algorithm fits words up to `line_width_warning_threshold_pixels` (desired width), but allows a single word to cross the warning threshold if the total width remains below `game_dialog_max_width_pixels` (hard maximum limit), providing an excellent visual balance.
- **Sentence Integrity Page Building**:
  - Separates translated lines into pages according to `lines_per_page`.
  - Ensures sentence integrity by keeping entire sentences together. If adding a sentence would exceed the page limit, it is pushed to a new page using the active game's page break indicator (e.g. `\p`, `\l`).
- **Comprehensive Proportional Test Suites**:
  - Introduced automated real-world and randomized wrapping test routines simulating typical GBA, DS, GameCube, and Wii screen resolution configurations and proportional font letter widths.

## [0.2.149] - 2026-06-01

### Fixed
- **Auto-fix race condition and text reverting**:
  - Resolved a critical race condition where programmatic changes made by `Auto-fix` were reverted because `text_edited()` deferred saving (250ms timer) while `update_text_views()` read old data synchronously.
  - Implemented immediate synchronous database update via `data_processor.update_edited_data()` and cancelled active debounce timers.
- **Zelda BMG character width discrepancies in Problem Analyzer**:
  - Integrated `_calculate_width` helper in Zelda BMG problem analyzer and text fixer to respect game-specific tag aliases and defaults for correct line-shortness thresholds.
  - Added test cases in `test_zelda_bmg_rules.py` verifying word wrap splits and tag width limits.
- **Console log handler file truncation and startup cleanup**:
  - Replaced rotating backup logs with single-write FileHandler to clear the log file at startup. Added clean up logic to delete old log files.

## [0.2.148] - 2026-06-01

### Added
- **Autonomous Tag Aliases Storage (`aliases.json`)**:
  - Implemented persistent saving of custom tag mappings (aliases) to an independent `aliases.json` file inside the active plugin's directory.
  - Custom aliases are dynamically loaded and merged with default plugin rules upon startup or plugin switch, fully preserving user mappings even without an active project open.
  - Integrated immediate mappings saving inside `PluginSettings.save()` and `handle_add_tag_mapping_request()` callbacks.

### Fixed
- **PyQt5 slot mocking TypeError and sipBadCatcherResult in unit tests**:
  - Resolved `TypeError: TagAliasDialog.__init__() missing 1 required positional argument: 'title'` inside `test_tag_aliases_logic.py` by providing the required `title` parameter during instantiation.
  - Eliminated `TypeError: invalid argument to sipBadCatcherResult()` in Qt event loop by replacing `patch.object` slot interception with a robust python fake function.

## [0.2.147] - 2026-06-01

### Changed
- **Toolbar Layout Ergonomics**:
  - Relocated the External Script Runner `>_` action button to the far right side of the toolbar, immediately to the left of the Help button, improving layout hierarchy and interface balance.

### Fixed
- **QStatusBar is not callable Exception**:
  - Fixed a crash/exception `'QStatusBar' object is not callable` in `run_external_script` when launching an external script. Corrected the syntax to access the `statusBar` instance attribute directly instead of calling it as a function.

## [0.2.146] - 2026-06-01

### Added
- **Visual Progress Bar for Virtual Chapters**:
  - Implemented visual translation progress tracking for virtual chapters (chapters mapped from MemePalace SQLite database with `block_idx == -2`).
  - Chapter items in the project tree now render a smooth, semi-transparent pastel green background shading proportional to the chapter's completion rate, perfectly consistent with physical files progress styling.

### Fixed
- **Incomplete Tags Ignored in Guideline and Width Calculations**:
  - Fixed a critical rendering issue where vertical guidelines and character limits would jump incorrectly inside tag syntax (such as `{escape:255:00`).
  - Updated character slicing in width calculations (`_calculate_string_width_impl`) to gracefully identify and break out on incomplete tags at the end of slice, preventing syntax characters (e.g. `{`, `e`, `s`, `c`, `a`, `p`, `e`) from being measured as regular text with standard character widths.
  - Enhanced tag mapping resolution fallback to safely ignore unmapped tags or return zero width, while correctly measuring forced alias tags (e.g., `{F:Link}` as `"Link"` width).
- **Test Suite Stability & block_list_updater Icon TypeError**:
  - Fixed a crash/TypeError in `test_BlockListUpdater_populate_chapters` (where `self.mw.style().standardIcon` returned `MagicMock` instead of `QIcon` during test suite runs) by introducing a type-safe `_set_item_style_icon` helper method that validates the icon object before calling `setIcon()` on the tree item.

## [0.2.145] - 2026-06-01

### Fixed
- **Accumulative Width Calculation for Wrapped Lines**:
  - Fixed an issue where the vertical line guideline warning (width threshold tick) recalculated itself starting from zero for each visually wrapped segment of a single logical line. It now correctly computes and displays a single guideline at the cumulative end of the logical line.
- **Guideline Color De-synchronization**:
  - Fixed an issue where the editor guidelines failed to dynamically recolor (red on threshold violation, green/blue otherwise) when typing Cyrillic text. Resolved by ensuring consistent font map resolution (via active plugins) within both background recalculation and the paint event cycle.

## [0.2.144] - 2026-06-01

### Added
- **Narrative Navigation via Acts & Chapters (MemePalace Integration)**:
  - Added a virtual hierarchical tree navigation structure `Chapters -> Act -> Chapter` directly inside the left Blocks panel on the bottom.
  - Dynamically parses acts and chapters based on local MemePalace SQLite database timeline mappings (format: `"Act X, Ch Y"`).
  - Actively mapped dialogue counts are now displayed next to each virtual chapter node in real-time (e.g., `[76]`, `[148]`).
  - Supports smooth chronological navigation. Selecting a chapter populates all corresponding dialogue lines across various physical `.bmg` blocks straight into the central preview panel.
- **Full Context Menu for Virtual Chapters**:
  - Permitted right-click context menus for all virtual chapters (`block_idx == -2`), matching physical blocks behavior. Translators can now seamlessly rename chapters, delete them, assign custom fonts, toggle color markers, and rescan issues.
  - Standardized safety: the root `"Chapters"` folder and `"Act X"` sub-folders remain locked as read-only structures.

### Fixed
- **Name Resolution for BMG-Prefix Mappings in Twilight Princess**:
  - Implemented automatic mapping resolution for BMG-prefixed mappings (e.g., `BMG_Str_X`). Correctly translates dynamic `BMG` block labels to physical block index 0 (`zel_00.bmg`). This ensures chapters successfully map and display correct dialogue lines instead of showing `[0]` count.
- **Scope UnboundLocalError with QTimer**:
  - Resolved `UnboundLocalError: cannot access local variable 'QTimer' where it is not associated with a value` during block selection. Removed duplicate local `QTimer` import definitions from inside `block_selected` in `handlers/list_selection_handler.py` to prevent Python scope hoisting issues.
- **Error Populating Chapters Folder AttributeError**:
  - Fixed a crash when populating chapters on project load where `self.mw.mempalace_client` was accessed directly. The client is now safely resolved dynamically through `translation_handler.prompt_composer._get_mempalace_client()`.

## [0.2.143] - 2026-06-01

### Added
- **Focus in Alias Input Field**:
  - The alias input text field inside `TagAliasDialog` now automatically receives keyboard focus upon window initialization, allowing users to type and submit (via Enter) immediately without manual clicks.

### Fixed
- **UI Performance and Instability Fixes (Large Blocks & Startup Lag)**:
  - Fixed a 4-second UI freeze when switching to large blocks (5000+ lines). Completely disabled Aho-Corasick glossary highlighting for `preview_text_edit` in `JsonTagHighlighter` (`utils/syntax_highlighter.py`), as glossary matching is unnecessary for readonly preview fields.
  - Eliminated the 3-second startup lag (white window) on application and project load. Refactored block pre-caching (`pre_cache_all_blocks`) to run asynchronously via a non-blocking `QTimer.singleShot(100)` handler (`schedule_pre_cache` in `ui/updaters/preview_updater.py`), allowing the main window interface to render instantly.
  - Optimized the `QProgressDialog` behavior by changing its minimum display duration to 500 ms, preventing the dialog from flickering on small files.
- **Test Suite Stabilization & Bug Fixes**:
  - Fixed `UnboundLocalError: cannot access local variable 'width_to_check'` in `_fix_width_exceeded` within `handlers/text_autofix_logic.py` by initializing the variable `width_to_check = 0` before the loop.
  - Fixed `TypeError` in `_format_and_wrap_translation` within `handlers/translation_handler.py` by safely checking for `str` type and casting non-string parameters. Configured `prompt_composer.restore_placeholders` mock in `test_translation_handler.py` to return the input string to prevent `MagicMock` type leakage during testing.
  - Fixed `test_IssueScanHandler_rescan_all_tags` in `tests/test_handlers/test_issue_scan_handler.py` by adding `qapp` event loop processing (`qapp.processEvents()`) to let the async timer trigger the scan mock successfully.
  - Corrected test assertion in `test_StringSettingsHandler_apply_width_to_lines` to reflect that `apply_width_to_lines` correctly assigns the width setting to all line indices passed in `line_indices`.

## [0.2.142] - 2026-06-01

### Added
- **Force Alias UI Improvements & Interactive Popup**:
  - Added a detailed description tooltip to the "Force alias" checkbox inside `TagAliasDialog` explaining the rationale behind name locking (e.g. hardcoding 'Link' and 'Epona' for proper grammatical inflections in Slavic translations).
  - Implemented an interactive informational dialog (`QMessageBox`) that appears when the user manually checks the "Force alias" option, explaining how it permanently converts the tag into plain text in the final exported script.
  - Implemented real-time validation via `textChanged` to automatically strip manual `F:` or `f:` prefix inputs in the text editor to avoid duplication when the force alias option is enabled.

## [0.2.141] - 2026-06-01

### Added
- **Custom Tag Alias Width Support in UI**: Added the ability to specify a custom width (in pixels) for tag aliases directly within the `Add Alias` and `Edit Alias` dialogs.
  - Replaced standard `QInputDialog.getText` with a custom `TagAliasDialog` that includes an optional custom width field validated via `QIntValidator` (positive integers only).
  - Implemented `_save_font_overrides_to_disk` in `MainWindowActions` to persistently write custom widths to the active plugin's `font_map.json` configuration on disk.
  - Automatically reloads the font map (`_apply_font_overrides`) in-memory and triggers a full silent scan/recalculation of all dialogue widths in the project instantly upon alias addition, modification, or removal.

### Fixed
- **Unwanted Spaces Before Punctuation After Tags**: Fixed a bug in the word wrapping algorithms where a space was incorrectly added before punctuation marks (like commas) that immediately followed game control tags.
  - Corrected in `_format_and_wrap_translation` inside `handlers/translation_handler.py`.
  - Corrected in `_fix_width_exceeded` inside `handlers/text_autofix_logic.py`.

## [0.2.140] - 2026-06-01

### Added
- **Asynchronous External Script Runner**: Added a dedicated console prompt icon button (`>_`) to the main toolbar to quickly compile ROMs or launch emulators directly from the application.
- **Configurable Tool/Script Path**: Added an "External Tool/Script Path" option to the *Global* tab in Settings with a specialized file browsing selector dialog supporting executable files (`.bat`, `.cmd`, `.exe`, `.py`, `.sh`).
- **Asynchronous Execution & CWD Resolution**:
  - Scripts are executed asynchronously in a separate process (`subprocess.Popen`) so that the main UI remains highly responsive.
  - The working directory (CWD) is automatically resolved to the parent directory of the script to ensure local relative paths inside batch files resolve correctly.
  - On Windows platforms, the process is spawned in a brand new console window (`CREATE_NEW_CONSOLE`) allowing real-time inspection of compilation logs and emulator output.
- **Force-Alias Translation Mechanism (`F:` prefix)**: Introduced a powerful tag preservation system for AI translation. Tags whose aliases begin with `F:` (e.g., `{F:Link}` aliasing `{escape:0:0000}`) are automatically converted to their plain-text word equivalents before being sent to the AI translator. After translation, the words are restored back to their original tag form. This allows proper name tags (like player name or horse name) to be contextually translated as real words instead of being stripped as opaque control codes.
  - Created `utils/force_alias.py` with `prepare_text_for_ai()` and `restore_force_alias_placeholders()` functions.
  - Integrated into `AIPromptComposer.compose_batch_request()` for pre-processing and `TranslationHandler._handle_chunk_translated()` for post-processing.
  - Relevant glossary terms matching force-alias words are automatically included in the AI prompt for context.

### Fixed
- **Sleep Prevention on Manual AI Cancellation**: Fixed a bug where the computer would enter sleep mode even when the user manually cancelled an AI translation operation. The `AIStatusDialog` now correctly sets `user_cancelled = True` through a unified `reject()` override, ensuring that the "Put computer to sleep when finished" checkbox is honored only for operations that complete automatically without human intervention. Also fixed potential duplicate signal connections in `TranslationUIHandler.start_ai_operation()` that could cause multiple cancel handlers to fire.

## [0.2.139] - 2026-06-01

### Added
- **AI JSON Normalization Retries**: Improved the AI translation pipeline by adding a specific fallback prompt when the model returns malformed JSON or truncates its response. The `AILifecycleManager` now detects parsing failures and automatically retries with a strict formatting reminder.

### Fixed
- **Preview Scroll Jumping During Background Translation**: Fixed a highly disruptive bug where the string list (`preview_text_edit`) would unexpectedly reset its scrollbar to the very top whenever a background AI translation finished or when manually typing in the translation field. The `PreviewUpdater` now strictly preserves the vertical scroll position for any updates occurring within the same block.
- **Robust Glossary Path Resolving**: Resolved an issue where glossary highlights in the editor would fail to appear (both in translated and untranslated text). Refactored `GlossaryPromptManager._resolve_glossary_path()` to use a strict hierarchical priority system (Level 0 Override -> Level 1 Project -> Level 2 Base Game) and a localized `mtime` cache.
- **Test Suite Stabilization**: Fixed a critical mocking issue where 3 translation handler tests crashed with a `TypeError` due to a `MagicMock` object being passed into `save_progress_to_metadata`. Added type-safe isinstance checks for `MagicMock` inside the production function to guarantee robust unit testing without regressions.

## [0.2.138] - 2026-05-31

### Added
- **Configurable Tooltip Font Size**: Introduced a new user setting `"tooltip_font_size"` that allows dynamic scaling of all HTML-based tooltips (both glossary tooltips and real-time issue warnings).
- **Settings UI Control**: Added a new numeric spinbox `"Tooltip Font Size:"` under the *Global* tab in the Settings Dialog, with a valid range of 6px to 32px (defaulting to 11px).
- **Dynamic Tooltip Scaling**:
  - Upgraded glossary tooltips in `LineNumberedTextEdit` to dynamically read and apply the configured `tooltip_font_size` across terms and notes.
  - Upgraded real-time issue warning tooltips in `LNETTooltipLogic` to scale responsively by wrapping their content inside a dynamically-sized `div` container.
- **Robust Settings Unit Tests**: Added a regression test `test_GlobalSettings_saves_and_loads_tooltip_font_size` in `tests/test_core/test_settings/test_global_settings.py` verifying that the tooltip font size is persisted and reloaded correctly in `settings.json`.

### Fixed
- **Markdown Notes Rendering in Glossary Tooltips**: Upgraded glossary tooltips to render notes formatted with full Markdown syntax (bold text, lists, line breaks) using the `markdown` library with the `nl2br` extension for single-line breaks.
- **Glossary Highlights Regression**: Fixed a critical bug in `text_operation_handler.py` where glossary highlighting was lost in the translation editor. Decoupled the syntax highlighter by retrieving the active `_glossary_manager` directly through the active editor's `highlighter`.
- **Sync Issues on Block Revert**: Resolved a sync issue where cancel/revert on AI block translations would revert text fields but fail to refresh the preview tree. Added `force=True` to the string loading queue to clear preview cache on block revert.

## [0.2.137] - 2026-05-31

### Fixed
- **Unsaved Changes Indicator in Window Title**: Fixed a bug where the window title asterisk (`*`) indicating unsaved changes did not appear when blocks were translated programmatically in the background via AI (batch block translations or chunked previews). Added explicit `self.ui_updater.update_title()` triggers immediately inside `TranslationHandler._handle_chunk_translated()` and `TranslationHandler._handle_preview_translation_success()` callbacks.
- **Granular Subline Asterisk Synchronization**: Enhanced the `update_text_views` pipeline in `PreviewUpdater`. When text is programmatically replaced inside the translation editor (such as immediately after a background AI translation finishes for the current string), `sync_subline_asterisks()` is now dynamically invoked on the spot. This ensures that subline asterisks on the gutter update instantaneously without requiring the user to navigate away and back.
- **Robust Integration Unit Tests**: Added complete regression tests `test_th_handle_chunk_translated_updates_title` and `test_th_handle_preview_translation_success_updates_title` in `tests/test_handlers/test_translation_handler.py`, alongside `test_populate_strings_syncs_subline_asterisks` in `tests/test_ui/test_updaters/test_small_updaters.py` verifying seamless asterisk propagation.

## [0.2.136] - 2026-05-31

### Fixed
- **Index Shifting in Block Translation**: Fixed a critical regression where dialogue translations could shift and align with incorrect original strings, or empty slots could receive texts. This was caused by the chronological scene-based reordering in `AIWorker.run()` for chunked block translation, which altered the original block sequence. If the AI returned simplified sequential IDs (e.g., `0, 1, 2...`) instead of the sparse segment keys, they were incorrectly mapped as direct block row indices when `temp_id_map` was absent.
- **Robust Sequential Mapping**: Implemented a highly resilient **sequence-based mapping** in `TranslationHandler._handle_chunk_translated()`. Translations returned by the AI are now matched step-by-step with the original items of the sent chunk in sequential order (since LLMs consistently preserve translation order). It safely extracts the true block and string indices from the sent chunk data and `temp_id_map`. Additionally, a fallback maps via `temp_id_map` using safe type conversions (handling both `int` and `str` key formats).
- **Persistent Chunk Tracking**: Updated `AIWorker.run()` to store the dynamically calculated/ordered scene chunks directly inside `self.task_details['calculated_chunks']`, making them available for reliable sequential parsing in callbacks.
- **Always-On Temp ID Maps**: Updated `translate_current_block()` and `resume_block_translation()` to always generate and pass a valid `temp_id_map` into the translation task details, preventing any segment index mismatching.

## [0.2.135] - 2026-05-31

### Fixed
- **Progress Calculations Exclude Untranslatable Strings**: Refactored the progress tracking architecture to exclude empty or tag-only original strings from the calculation entirely. Instead of marking them as "translated" (which incorrectly colored empty slots in green), they are now ignored in both numerator and denominator when calculating block progress. `is_string_translated()` correctly returns False for untranslatable rows, preventing incorrect UI highlighting while still allowing fully translated text blocks to reach a 100% progress color fill.
- **Robust Progress Calculations Unit Tests**: Updated unit tests to verify the `string_needs_translation` and `is_string_translated` logic for empty/tag-only strings inside `tests/test_handlers/test_translation/test_surrounding_context_and_metadata.py`.

## [0.2.134] - 2026-05-31

### Fixed
- **Intelligent Block Progress Calculations**: Fixed a bug where blocks containing empty or tag-only original strings would never reach a 100% progress color fill because empty strings were considered "untranslated" by `is_string_translated()`. They are now treated as "completed" by default since they do not need manual translation, which ensures correct 100% green progress bar fill on fully completed files.
- **Robust Progress State Unit Tests**: Added regression tests verifying that empty original strings and strings containing only tags/whitespace correctly return True in `is_string_translated()` inside `tests/test_handlers/test_translation/test_surrounding_context_and_metadata.py`.

## [0.2.133] - 2026-05-31

### Fixed
- **Persistent Glossary Tooltips in Editor**: Fixed a UX bug where hovering over a glossary word in the translation editor would fail to display the tooltip again after it had been hidden by timeout or after the mouse briefly left the text editor viewport. Added state resetting (`_last_tooltip_state = None`) in `leaveEvent()` and bypassed caching limits in `mouseMoveEvent()` if `not QToolTip.isVisible()`, ensuring buttery-smooth and highly responsive tooltips on repeated hovering.
- **Robust Tooltip Unit Tests**: Added regression tests `test_glossary_tooltip_resets_on_leave_event` and `test_glossary_tooltip_reappears_when_hidden_by_timeout` in `tests/test_ui/test_glossary_ui_logic.py` verifying correct state resetting and visibility overrides.

## [0.2.132] - 2026-05-31

### Added
- **Unified AI Translation Base**: Unified glossary processing for all AI translation tasks. The AI prompt composer now dynamically extracts and injects only relevant glossary terms matching the translation segment via `glossary_manager.get_relevant_terms(text)` across single string translations, batch block translations, and variations.
- **Surrounding Dialogue Context**: Integrated rich, surrounding dialogue context. When translating a single string, a selection of strings, or variations, the prompt composer gathers up to 3 preceding and 3 succeeding dialogue rows in their best current translation (or original) state, enabling the LLM to preserve tone, character relationship, and formal address (ty/vy).
- **Standardized Script Formatting**: Created a comprehensive markdown guideline for game script preparation and successfully upgraded `BaseGameRules.parse_walkthrough_transcript()` to support standardized `[Chapter: ...]`, `{Action: ...}`, and uppercase speaker tag separations with 100% backward compatibility.
- **Persistent Translation Metadata**: Enhanced the `update_edited_data()` pipeline in `DataStateProcessor` to dynamically track and serialize translation details (AI model, timestamp, approval state) directly into `.uiproj` Block objects without polluting the filesystem.
- **Progress Visualisation in UI**: Implemented soft pastel-green shading (`QColor(46, 139, 87, 40)`) under line numbers for translated strings in editors and preview, alongside smooth, semi-transparent green progress bars (`QColor(46, 139, 87, 25)`) dynamically rendered left-to-right across tree widget plates in the project tree proportional to file completion rate.

### Fixed
- **Outdated Glossary Unit Tests**: Updated obsolete prompt composer tests (`test_AIPromptComposer_prepare_glossary_for_prompt_full` and `test_AIPromptComposer_prepare_glossary_for_prompt_updates`) in `tests/test_handlers/test_ai_prompt_composer.py` to match the new unified glossary injection pipeline.

## [0.2.131] - 2026-05-31

### Added
- **Chronological Dialogue Translation**: Integrated a project-wide narrative-oriented translation pipeline. Dialogues from all blocks are collected and sorted chronologically based on their actual script lines in the MemePalace database before being sent to the AI translator.
- **Context-Aware Dialogue Translation**: Automatically queries and merges scene/room visual descriptions from MemePalace client mappings directly into translation batch items.
- **Narrative Session History Compression**: Implemented automatic translation history summarization. When the narrative exchange context buffer size exceeds `MAX_HISTORY_MESSAGES`, an LLM summary of the story events, style, and tone is generated and injected into the subsequent system prompts, preserving long-range story context.
- **Chronological Translation Unit Tests**: Added a complete unit test `test_translate_all_blocks_chronologically` in `tests/test_handlers/test_translation_handler.py` verifying sorting, temp ID mapping, and batch initialization.

### Fixed
- **AttributeError in Tree Context Menu Translation**: Fixed a crash where choosing "AI: Translate All Blocks (UA Chronological)" from the tree context menu failed with `AttributeError: 'TranslationHandler' object has no attribute 'composer'`. Corrected the reference to `self.prompt_composer`.

## [0.2.130] - 2026-05-31

### Added
- **Glossary `profiled` Field**: Added a `profiled` boolean field to `GlossaryEntry` in `core/glossary_manager.py`. This flag persists to the glossary JSON file and indicates whether a character entry has already received a detailed AI speech profile. When `profiled=True`, the MemePalace worker skips the entry during batch profiling runs.
- **Profiled Checkbox in Glossary UI**: Exposed the `profiled` flag as a checkbox in the Glossary dialog. Users can manually tick or untick the checkbox to force reprocessing of specific characters in the next profiling pass.
- **Incremental Reprofiling Logic**: The MemePalace character profiler worker (`core/mempalace_worker.py`) now uses a composite check combining the `profiled` marker and the line count of existing notes (threshold: `< 3` lines). If a character has `profiled=True` but fewer than 3 lines in its notes, the `profiled` flag is automatically reset and the character is requeued for AI profiling. This guards against empty or minimal AI responses being silently treated as complete profiles.
- **Quick Glossary Replace-All**: Added a **"Replace All (No AI)"** button to the translation update dialog. Clicking it performs an immediate, AI-free replacement of the selected term across all strings in the project using the new source→target mapping, without invoking any AI endpoint.

### Fixed
- **MemePalace Stop Button Cancels Profiling Correctly**: Fixed a bug where clicking the **Stop** button during an AI profiling run would not actually cancel the active worker. The worker now respects the `_stop_requested` flag set by the Stop button and exits the profiling loop cleanly without completing remaining entries.
- **Glossary Tab Auto-Switch Bug**: Fixed a bug where typing in the Glossary search field or editing any entry would unexpectedly switch the active tab to "Item". The root cause was an unconditional tab index reset being triggered on every glossary reload signal. The tab is now preserved on reload and only reset when explicitly opening a fresh dialog session.
- **UI Test Teardown Segfault (`0xC0000409`)**: Resolved a critical C++ segfault occurring during `tests/test_ui/test_glossary_ui_logic.py` teardown. The issue was caused by Qt's garbage collector destroying the parent widget before the child dialog. Fixed by setting `parent=None` in all test dialogs and adding explicit `deleteLater()` + `processEvents()` cleanup calls.

## [0.2.129] - 2026-05-30


### Added
- **MemePalace Automated Orchestration Pipeline**:
  - Integrated a new **Start Complete Pipeline** green button into the MemePalace Context Builder dialog.
  - Implemented sequentially automated execution of the entire MemePalace workflow steps in their correct order:
    1. *Mining Characters & Terms via AI*
    2. *Mapping BMG dialogue lines to Story Script Chapters*
    3. *AI Analyzing and Generating Chapter Summaries*
    4. *AI Profiling Characters Speech Patterns*
  - Added smart non-blocking transitions (`_advance_pipeline` and `_abort_pipeline`) to safely move forward on success or gracefully stop on failures with full log output.
- **Robust Pipeline Test Suite**:
  - Added a comprehensive unit test `test_mempalace_builder_pipeline_orchestration` in `tests/test_ui/test_mempalace_builder.py` verifying correct step transitions, mock worker execution, and completion callbacks.

## [0.2.128] - 2026-05-30

### Added
- **AI-Powered Glossary Categorization & Dynamic Tabbed Interface**:
  - Replaced the legacy flat glossary table with a beautiful, dynamic `QTabWidget` interface. The editor now automatically scans, constructs, and hot-reloads distinct tabs for all active glossary sections (such as "Characters", "Items", "Locations"), alongside a comprehensive "All" tab and an optional "Unassigned" tab.
  - Implemented an elegant purple **Organize via AI** button. Clicking this triggers a highly sophisticated, two-stage AI workflow:
    - *Stage 1 (Thematic Suggestions)*: The AI analyzes active glossary terms and suggests 4 to 7 highly relevant thematic categories.
    - *Stage 2 (Interactive Checklist & Dynamic Classification)*: The user is presented with a custom checkable dialog allowing them to select and add custom categories. The AI then dynamically classifies all glossary terms into the chosen categories, updates the on-disk markdown file, and hot-reloads the glossary dialog in real time.
  - Implemented smart navigation UX: Double-clicking an occurrence in the editor dynamically switches the tab to the corresponding category and highlights the selected row.

### Fixed
- **AttributeError on Empty Glossary Dialog Initialization**: Fixed a critical bug where opening the Glossary Dialog without a specific target word (via *Tools -> Open Glossary...*) would trigger an `AttributeError` due to direct legacy access to `self._entry_table` (which was initialized to `None`). Replaced all direct references with a dynamic `self._active_table()` call.
- **AttributeError in AI Glossary Classification UI Actions**: Fixed an `AttributeError` during AI classification when attempting to trigger non-blocking status-bar messages via `self.mw.ui_handler`. Correctly mapped the UI worker callbacks to use `self.main_handler.ui_handler` for precise status tracking and animation.
- **Glossary Dynamic Section Preservation on Markdown Generation**: Fixed a critical serialization bug where saving the glossary back to the markdown file on disk would silently delete all entries assigned to dynamically created categories. This occurred because `_generate_markdown()` only outputted sections explicitly matching the static `self._section_order` list. Enhanced the generator to dynamically discover all active sections, preserving the original order of known categories while seamlessly appending new ones to the file.
- **Background API Flood Protection for Character Speech Profiling**: Integrated a consecutive failure detection threshold (max 3) within `MemePalaceCharacterProfilerWorker` to gracefully abort profiling and emit a helpful warning message if the underlying AI provider is misconfigured or has missing credentials, completely preventing system log flooding.

## [0.2.127] - 2026-05-29

### Added
- **Unified Plugin Problem Analyzer Subsystem**: Refactored the validation and warning analysis engine across all plugins. Created a shared baseline `BaseProblemAnalyzer` inside `plugins/common/problem_analyzer.py` to standardize the parsing, width evaluation, and warning generation logic. Decomposed rule checkers in `plain_text`, `pokemon_fr`, `zelda_bmg`, `zelda_mc`, and `zelda_ww` plugins into cohesive analyzer classes, greatly reducing duplicate boilerplate.
- **Enhanced AI Prompt Composer and Translation Workflow**: Substantially upgraded the AI prompt composer and async worker execution lifecycle in `handlers/translation/ai_prompt_composer.py` and `handlers/translation/ai_worker.py`. Strengthened structural JSON processing, refined translation context injection, and resolved type annotations throughout the handlers.
- **Robust Problem Analyzer Test Suite**: Added a dedicated test suite under `tests/test_plugins/test_plain_text/test_problem_analyzer.py` to comprehensively verify problem detection, warning offsets, and customized plugin markers.

## [0.2.126] - 2026-05-29

### Added
- **Direct Database Script Line Mapping**: Integrated a high-performance DB-direct query pipeline inside MemePalace context matching to dynamically map dialogue strings to chronological story events, eliminating flat index traversal delays.
- **Chapter Timeline Quick Access**: Added a new keyboard shortcut `Ctrl+I` to instantly trigger the chronologically mapped chapter walkthrough timeline dialog.
- **Accurate AI Operation Queue Progress Bar**: Enhanced the status indicators with highly accurate queue calculation and real-time step progress updates inside `AIStatusDialog` for long-running AI operations.

## [0.2.125] - 2026-05-29

### Fixed
- **Script Matching: Button-Hint Parentheses Stripped from Distillation**: Fixed a script-line matching failure for BMG strings that contain button-prompt escape tags. In the script file, button descriptions appear as plain parenthesised text, e.g. `(Up on D Pad)`. In the BMG, the same position is an escape code like `{escape:0:0011}`. Previously `distill()` stripped curly-brace tags but not parenthesised content, so the script side produced extra characters (`upondpad`) that had no counterpart in the BMG query, causing mismatches. Now `distill()` also strips `(…)` content, making both sides comparable.
- **Distill Cache Auto-Invalidation**: Introduced an internal `_DISTILL_CACHE_VERSION` constant (currently `2`). The script-cache hit condition now requires the stored version to match. Bumping this constant when `distill()` logic changes forces a fresh rebuild of the global distilled-text cache instead of silently serving stale data from the previous session.

## [0.2.124] - 2026-05-29


### Fixed
- **Script Matching: Link/Epona Tag Substitution Before Distillation**: Fixed a script-line matching failure for BMG strings that contain dynamic runtime name tags (`{PLAYER}`, `{escape:0:0001}` for Link, `{escape:0:0022}` for Epona). Previously these tags were stripped as unknown markup, making the distilled BMG query shorter and mismatching against the script text where the real name appears (e.g. `"whywithouteponathe"` vs `"whywithoutthe"`). Now, a new plugin hook `get_dynamic_name_tags() -> dict` is consulted before tag-stripping. The zelda_bmg plugin returns a mapping of known runtime-name escape codes to their plain-text names; these substitutions are applied first inside `distill()`, so the query matches correctly.

### Changed
- **Plugin API: `get_dynamic_name_tags()` hook on `BaseGameRules`**: Added a new optional override method `get_dynamic_name_tags() -> Dict[str, str]` to `BaseGameRules`. It returns an empty dict by default. Subclasses (e.g. `zelda_bmg`) can override it to declare which tag strings should be treated as plain-text character names during script-line matching. The key is the exact tag string as it appears in editor text; the value is the replacement name.

## [0.2.123] - 2026-05-28


### Fixed
- **Strings in Block: Lazy Loading Timer Cancellation Bug**: Fixed a critical bug where the list of strings in the "Strings in block" preview panel appeared empty (invisible text) for all items beyond the initially loaded chunk (roughly the first 1560 strings) in large files with 5000+ entries. Root cause: `populate_strings_for_block()` unconditionally stopped the lazy loading timer (`_lazy_load_timer.stop()`) on every call — including repeated calls triggered by view updates and selection restores for the same block. Since the block had not changed, the timer was killed but never restarted, leaving most lines blank. Fixed by only stopping the timer when the block or the displayed index set actually changes (`should_regenerate = block_changed or displayed_indices_changed or force`).
- **Window Size Not Restored Correctly**: Fixed a bug where the application window size was always capped to 1280×800 on startup, even if the user had resized it to a larger resolution before closing. Removed the artificial `min(width, 1280)` / `min(height, 800)` constraints from `restore_state_after_settings_load()`. The window now restores to its exact saved geometry, clamped only to the current screen dimensions and the minimum safe size of 800×600.

## [0.2.122] - 2026-05-28

### Added

- **Hybrid Default Fallback & On-Demand Materialization for Plugins**: Implemented an intelligent default filesystem architecture for game plugins. Shared baseline presets (`font_map.json` and `prompts.json`) are stored inside `plugins/common/defaults/` to keep the repository extremely clean. Subsystems (`FontMapLoader`, `GlossaryPromptManager`, `MemePalaceScriptAnalyzerWorker`) automatically fallback to these defaults when plugin files are missing.
- **On-Demand Auto-Creation (Materialization on Edit)**: Added automatic local file creation inside the target plugin's directory (`plugins/{plugin_name}/translation_prompts/prompts.json`) when a user edits prompts via the GUI (`save_prompt_section`) or triggers manual on-disk editing via the "Edit Prompts" settings button. This provides local-specific customization seamlessly on-the-fly.
- **CPU-Efficient Background Spellchecking**: Replaced the performance-intensive busy-loop with `time.sleep(0.05)` inside `SpellcheckWorker` with a high-efficiency `threading.Event()` wait condition mechanism. This completely eliminates idle CPU overhead and instantly wakes up the checker thread when a new word is enqueued.

### Changed
- **Type-Safe Programmatic Text State**: Replaced raw boolean flag assignments `self.mw.is_programmatically_changing_text = True/False` inside `TranslationUIHandler` with the robust `StateManager` context manager: `with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):`. This prevents state corruption or locks in case of unhandled event exceptions.
- **Clean Project Dialogs Imports**: Moved `import json` from inside the `_scan_plugins` loop to the top of `components/project_dialogs.py` adhering to PEP 8 standards.
- **Removed Dead Comments**: Deleted the obsolete `TODO: Add recent projects list here` block inside `OpenProjectDialog` to clean up source clutter.
- **Version Release Synchronization**: Bumped the version across all project resources (`utils/constants.py`, `README.md`, `GEMINI.md`, `CHANGELOG.md`) to `v0.2.121-dev`.

## [0.2.120-dev] - 2026-05-27

### Added
- **AI Script Analyzer Glossary Integration**: Integrated the MemePalace AI Script Pre-Analyzer with the Picoripi Glossary system (`GlossaryManager`). The analyzer now automatically extracts characters with inflected properties (gender, age group, relationships, informal/formal/respectful address types) and gameplay items/locations/terminology.
- **Smart Glossary Synthesis & Name Translation**: Implemented dynamic AI notes synthesis for existing glossary entries, preserving their translation unchanged, and automatic natural Ukrainian translation generation and structured description writing for new terms.
- **Real-time Glossary Highlight Synchronization**: Added automatic glossary reloading from disk, cache synchronization, and real-time syntax highlighter refresh in editors upon successful AI script pre-analysis.
- **Modeless MemePalace Context Builder**: Converted the MemePalace Context Builder dialog to a modeless window (`dialog.show()`), allowing users to freely edit text, navigate blocks, and use the main Picoripi interface concurrently during script-to-timeline context weaving.
- **Dynamic Context Builder Instance Management**: Implemented automatic window focus restoration (`raise_()`, `activateWindow()`) on already open dialog instances, preventing duplicate window spawn, and added clean resource deletion (`WA_DeleteOnClose`) on close.
- **MemePalace Weaving Accuracy Improvements**: Integrated a substring-based matching algorithm that searches the entire BMG database, cuts dynamic names (`Link`, `Epona`) for perfect char alignment, and uses context-aware look-ahead expansions to resolve duplicates.

## [0.2.119] - 2026-05-27

### Changed
- **Release Stability Update**: Bumped version to `v0.2.119` to synchronize release tags and integrate comprehensive codebase auditing, updated documentation across files (`README.md`, `GEMINI.md`), and refreshed codebase audit markers in `AUDIT.md`.

## [0.2.118] - 2026-05-27

### Fixed
- **Guideline Width Limit Synchronization**: Fixed a critical bug where the vertical width guideline in translation editors used the default threshold value (280px) instead of the project-configured value (e.g. 460px). The root cause was that `line_width_warning_threshold_pixels`, `game_dialog_max_width_pixels`, and `show_width_guideline` were set as plain instance variables at widget construction time and never updated when a project was opened or switched. These three properties are now implemented as dynamic Python `property` descriptors in `LineNumberedTextEdit`, which always forward reads directly to the active `MainWindow` instance at call time, guaranteeing the editor always sees the correct project-level limit without any manual synchronization.
- **Guideline Calculated Immediately on String Selection**: Fixed a bug where width guideline lines were only drawn after the user started typing in a string. Previously `recalculate_guidelines()` was called synchronously inside `setPlainText()`, but Qt had not yet finalized the block text layout at that point, so all `layout.lineAt(i).isValid()` calls returned `False` and `guideline_positions` remained empty. The call is now deferred via `QTimer.singleShot(0, self.recalculate_guidelines)`, which schedules the recalculation for after Qt completes the layout pass — ensuring guidelines appear immediately when a string is loaded into the editor.
- **Guideline Repaint After Recalculation**: `recalculate_guidelines()` now calls `self.viewport().update()` at the end to force an immediate visual repaint of the editor, ensuring the newly computed guideline positions are drawn without requiring any additional user interaction.
- **Editor Rules Sync on Project Open/Switch**: Added `update_editor_rules_properties()` calls in `ProjectActionHandler` for all three project lifecycle events — `open_project_action`, `_open_recent_project`, and `create_new_project_action` — ensuring all three editors immediately receive the correct project-specific limits right after a project's settings are loaded from metadata.

## [0.2.117] - 2026-05-25

### Fixed
- **Tag-Layering Visual Correction**: Fixed a rendering bug where glossary underlines (blue line) and custom font colors (e.g. red color from `{color:red}`) would bleed or overflow onto adjacent control tags (like `{color:white}` or `[PLAYER]`) when written in close proximity without spaces (e.g., `word{color:white}`).
- **Priority-Based Highlight Layers**: Restructured the formatting passes in `JsonTagHighlighter.highlightBlock` to apply heavy text metadata styling (Aho-Corasick glossary matches, Translation Glossary Bridge, and Spellcheck underlines) at the very beginning of the block layout render loop, before executing plugin-specific and built-in tag matching. This guarantees that control codes are rendered last and completely clean up any underlying highlights, ensuring pixel-perfect text validation aesthetics.

## [0.2.116] - 2026-05-25

### Added
- **Ergonomic Revert Button Placement**: Relocated the "Revert String to Original" button into a dedicated, elegant 34px vertical middle panel between the Original and Edited text editors. The button is styled with subtle rounded corners and hover highlighting, and its icon has been changed to a forward arrow (`QStyle.SP_ArrowForward`) to intuitively symbolize restoring the original text from left to right.
- **Top-Border Alignment**: Vertically positioned the Revert button with a precise 32px top spacing, perfectly aligning its top edge with the top borders of both adjacent text editor windows.

### Fixed
- **Sub-Millisecond Instant Revert**: Completely eliminated the 4-second UI freeze when restoring a string to original. Replaced the heavy, synchronous full block rebuild (`populate_strings_for_block(force=True)`) with highly optimized, surgical single-line updates using `QTextCursor`.
- **Persistent Selection & Scroll State**: Added automatic vertical scrollbar state preservation during reverts. The "Strings in block" list now maintains its exact scroll position, focus, and selected line highlighting without resetting the cursor to the top of the list.

## [0.2.115] - 2026-05-25

### Added
- **Global Performance Toggles**: Introduced new checkbox toggles in the **Global Settings** tab to allow users to completely enable or disable heavy subsystems (Live BFN Dialog Preview, real-time warning scans, and glossary matches). Disabling these features allows for diagnosing and fully eliminating typing latency (input lag) on slower hardware.
- **Debounced Typing Mode in QSyntaxHighlighter**: Implemented a dynamic `_typing_mode` state inside `JsonTagHighlighter`. During rapid typing, heavy synchronous glossary cache rebuilding and Slavic morphological searches are bypassed. These features fall back to debounced async background calculations, ensuring that character input is buttery-smooth and instantly rendered on the screen.

### Fixed
- **Isolated Preview Toggling & Correct Strings in Block Indexing**: Fixed a critical bug where disabling "Live Preview" would prematurely exit `populate_strings_for_block()` and completely clear the "Strings in block" list. Mapped the preview toggle to control only the graphical `BfnPreviewWidget` visibility, keeping the textual lines index, category filtering, and editor synchronization fully operational.

## [0.2.114] - 2026-05-25

### Added
- **Dynamic Guidelines (Visual Width Alignment)**: Replaced the static vertical width warning guideline with smart, dynamically computed individual guidelines (vertical ticks) for each visible text line inside the editors. Proportional positions are calculated on-the-fly using the line's real game font width ($text\_w \times \frac{limit\_px}{width\_px}$). Guidelines automatically turn red upon width limit violations and remain soft gray/green when valid, ensuring real-time accurate visual estimation of the remaining space.

### Fixed
- **Optimized Rendering Event Execution**: Verified that all dynamic width calculations execute only for onscreen blocks inside the rendering viewport loop, avoiding CPU lag during keystroke input.

## [0.2.113] - 2026-05-25

### Added
- **Double-Click Line Sync in Preview**: Implemented an intuitive navigation shortcut allowing translators to double-click the line number area (`LineNumberArea` showing widths/line numbers) in any active editor to instantly scroll the `"Strings in block"` preview panel to the currently edited string. Focuses and highlights the corresponding line, keeping visual context fully synchronized even in long files.

### Fixed
- **Type-Robust Mock Test Suite**: Resolved a pytest failure by fully mocking `QTextCursor` instantiation on dynamic `QTextBlock` elements during unit-testing, completely eliminating `TypeError` occurrences in mock environments while preserving clean production code.

## [0.2.112] - 2026-05-25

### Added
- **Show Guideline Option**: Added a new **"Show guideline"** checkbox right next to the `Editor Line Width Warning (px)` field inside `Settings` -> `Project` -> `Rules`. Allows translators to easily toggle the visual vertical dotted guideline in the translation editors on or off. State is persistent and saved in `settings.json` under `show_width_guideline` (defaults to `True`).

### Fixed
- **Stable QSpinBox Width Arrows**: Fixed a bug where QSpinBox arrows (up/down step buttons) disappeared on Windows after issue scans or string list updates. Transitioned the purple override highlight styling from the parent `QSpinBox` widget level to exclusively target its nested line edit field via `width_spinbox.lineEdit().setStyleSheet()`, leaving the system step button rendering completely intact.
- **Zero-Lag Default Width Sidebar Updates**: Eliminated the visual delay/lag when default width parameters were updated. Sidebar string settings panel updates are now executed instantly at the very start of the settings saving routine, bypassing blocked modal `QMessageBox` rescan dialogues and keeping the source of truth fully synchronized in real-time.
- **Robust Mock-Context Suite and Safe Width Fallback**: Patched the pytest unit testing suite by registering the new `game_dialog_max_width_pixels` properties within mock context fixtures (`MockContext` and `mock_mw`). Integrated safe fallback `getattr(self.mw, 'game_dialog_max_width_pixels', 200)` inside аsync handlers to prevent `AttributeError` exceptions under high-concurrency Qt event execution contexts.

## [0.2.111] - 2026-05-25

### Added
- **BFN Font Editor Independent Sliders**: Decoupled kerning (blue) and glyph width (red) sliders in BFN Font Editor's interactive glyph viewer and simulation previews. Moving the kerning slider now automatically adjusts the glyph width internally to ensure the width line remains visually static in absolute coordinates, preventing unexpected layout modifications. Included safe clamping to prevent value overflows.
- **BFN Editor Auto-Rescan on Close**: Integrated automatic full project re-scans upon closing the BFN Font Editor if changes to custom font metrics were successfully saved during the session, allowing instant propagation of updated font metrics to translation alerts.
- **Rules Limits Redefinition (Game Dialog Max Width)**: Restructured text safety limits. `Game Dialog Max Width` is now the primary limit that drives string warning highlights, issue scanner errors, and the Auto-Fix wrapping engine.
- **Visual Editor Line Width Guideline**: `Editor Line Width Warning` is now dedicated solely to drawing a subtle vertical guideline inside the translation inputs, giving translators full control over safe visual boundaries without throwing annoying errors or blocking auto-fixes.
- **Improved Guideline Styling**: Restyled the vertical guideline to be a thin 1px dashed line with 50% opacity (`QColor(0, 128, 0, 128)`) for an elegant, distraction-free appearance, and successfully hid it inside the "Strings in block" preview list.
- **Settings Dialog Rescan Trigger**: Implemented safe pre-dialog value caching for Game Dialog Width, Editor Line Warning, and Lines Per Page. When the Settings dialog is closed via "Ok", a full rescan of all tags and issues is automatically triggered if and only if one of these parameters has actually changed.
- **Reactive Side Panel Sync**: Integrated automatic UI side panel updates upon saving settings, immediately synchronizing the default width value inside the String Settings panel's spinbox without requiring block or string selection refreshes.

## [0.2.110] - 2026-05-24

### Fixed
- **Fixed Multi-Selection Reset in Strings in Block Preview**: Fixed a critical bug where Shift-clicking or Ctrl-clicking to select multiple lines in the preview list ("Strings in block") would immediately reset and disappear.
  - Implemented instant focus setting (`setFocus()`) in `mousePressEvent` in [mouse_handlers.py](components/editor/mouse_handlers.py) to resolve async focus transfer latency when clicking from the translation editor.
  - Optimized focus checks in `handle_preview_selection_changed` in [list_selection_handler.py](handlers/list_selection_handler.py) to perform `hasFocus()` verification only on native Qt selection updates, skipping it entirely for custom selection signals.
  - Protected multi-selection state in `set_selected_lines` in [line_numbered_text_edit.py](components/editor/line_numbered_text_edit.py) from being programmatically overwritten by lazy-loading timer blocks or background view updates, ignoring single line selection events if they are already part of an active multi-selection.

## [0.2.109] - 2026-05-24

### Fixed
- **Zelda BMG Plugin: Fixed Empty-Glyph Cyrillic Render Offset in Twilight Princess**: Fixed a bug where assigning Cyrillic characters to empty glyphs (with synthetic mapping keys like `#g{idx}`) caused the wrong character (e.g. letter "Ю" instead of "Я") to render in the game. Added a shifted encoding stride `+1` inside `encode_string_with_mapping()` and a matching `-1` stride decoding logic inside `decode_string_with_mapping()`, perfectly neutralizing the game's internal glyph index offset. Updated `test_synthetic_empty_glyph_mapping` to cover the correct shifted roundtrip.
- **BFN Editor: Seamless Font Filtering & Selection in RenderFontDialog**: Refactored `RenderFontDialog`'s system font selection. Removed the separate search field and made the `Font Family` combo box editable (`setEditable(True)`) with real-time popup display (`showPopup()`) upon typing.
- **BFN Editor: Focus-Robust Keyboard Event Proxying**: Added full keyboard event forwarding inside `eventFilter()` for `self.font_combo.view()`. When typing with the drop-down list open, all standard key presses (letters, Backspace, spaces) are caught at the popup list level and forwarded to the editable lineEdit via `QCoreApplication.sendEvent`, ensuring smooth, zero-latency multi-word typing without losing system focus. Integrated Photoshop-style automatic selection of all text (`selectAll()`) on mouse click and focus transitions with a 50ms delayed timer to safely override default Qt mouse release handlers.
- **BFN Editor: Clear Mapping Read-Only Protection**: Made `Font Char` visually read-only when executing the `Clear mapping` contextual action, clearing only virtual translation map definitions while leaving physical header mapping bytes perfectly intact.
- **BFN Editor: Empty Glyph Character Persists After Restart**: Fixed the root cause of Cyrillic characters (like «я») disappearing from empty glyphs after application restart. The issue had two causes:
  1. When a character was typed into an empty glyph, `update_char_mapping()` updated MAP1 **only in memory** but the BFN file was never written to disk. Now `save_changes(silent=True)` is automatically called immediately after registering a new empty glyph, persisting the MAP1 entry.
  2. On load, if `translation_map.json` contained a valid mapping (e.g. `"я" → chr(161)`) but the BFN file's MAP1 didn't have that code registered (e.g. from a previous unsaved session), the character silently disappeared. A new **4th pass** in `load_translation_map()` now detects such orphaned codes and re-registers them to the first available empty glyph, then auto-saves.
- **BFN Editor: Load/Save Filter for translation_map.json**: `save_translation_map()` now filters out corrupt entries (control character codes < 161, synthetic keys) before writing to disk. `load_translation_map()` now only accepts entries where the key is non-ASCII (ord ≥ 128) and the value is a printable CP1252 code in range 161–255, rejecting all control character entries that previously caused silent loss of mapped characters.

## [0.2.108] - 2026-05-24

### Fixed
- **BFN Editor: Dynamic Mapping Self-Healing & Direction Normalization**: Enhanced `load_translation_map()` to automatically detect, normalize, and swap backwards key-value pairs (so Ukrainian characters with ord >= 256 are always keys, and CP1252 codes with ord < 256 are always values).
- **BFN Editor: Automatic Control Character Healing**: Implemented on-the-fly detection and healing of invalid control/non-printable character codes. Any legacy mapping pointing to non-printable ranges (like `\u0001` or Unicode C1 controls) is automatically resolved by allocating a clean CP1252 printable code in range 161–255, remapping the physical BFN block, and saving changes to disk.
- **BFN Editor: Dynamic Code Allocation Improvements**: Updated `get_next_free_char_code()` to only consider a CP1252 code as "used" if it is actually present in the translation map, completely ignoring standard 1-to-1 MAP1 physical blocks. This ensures a clean code is always found in default-mapped fonts.

## [0.2.107] - 2026-05-24

### Fixed
- **BFN Editor: Persistence Fix on Migration**: Integrated automatic BFN-font file saving (`self.save_changes(silent=True)`) during the synthetic-key migration process inside `load_translation_map()`. This commits the newly migrated physical `MAP1` mappings permanently to the `.bfn` file immediately, preventing Cyrillic characters from disappearing upon application restart.
- **BFN Editor: Shifted Search Range to Printable Codes (161-255)**: Restricted the dynamically generated character codes to range `161–255` (0xA1–0xFF). This completely avoids the Unicode C1 control characters range (128–159), ensuring every registered character is visually printable in the table and safely encoded in the JSON database.

## [0.2.106] - 2026-05-24

### Fixed
- **BFN Editor: Fixed Load-Order and Migration Bugs**: Resolved a critical load-order sequence bug in `load_from_extracted_dir()` inside `bfn_io.py` where `load_translation_map()` was called before the `metadata` was parsed from `data.json`, causing the physical `MAP1` mappings to be overwritten and leading to Cyrillic letters disappearing upon restart.
- **BFN Editor: Enhanced Forceful Synthetic Key Migration**: Upgraded the migration pipeline in `load_translation_map()` to always forcefully migrate synthetic keys to physical codes using `get_next_free_char_code()`, bypassing mapping conflicts on standard range structures. Cyrillic letters like `"я"` now render perfectly in the game instead of the placeholder character `"à"`.

## [0.2.105] - 2026-05-24

### Added
- **BFN Editor: Conflict-Free Dynamic Empty Glyph Physical Mapping**: Upgraded the automatic empty-glyph registration logic to dynamically scan, allocate, and assign the first available CP1252 printable character code (starting at 128) instead of the hardcoded non-printable index values. This completely eliminates mapping conflicts and redundant synthetic keys.
- **BMG Plugin: Simplified Filtering Rules**: Streamlined the Zelda BMG rules loading process to allow any single-character mapping without enforcing the legacy >= 128 ASCII limit, ensuring maximum reliability and compatibility for clean mappings.
- **Unit Tests: Updated Test Cases**: Updated the unit test suite to assert the new, safer dynamic printable character code allocation (verifying `chr(128)` allocation for empty glyphs).

## [0.2.104] - 2026-05-24

### Added
- **BFN Editor: Non-Character-Based Navigation**: Added helper methods `goto_next_empty_glyph()`, `goto_prev_empty_glyph()`, and `jump_to_glyph_index(glyph_idx)` in `bfn_navigation.py` to support quick positioning and empty cell traversal without using specific character codes.

### Fixed
- **BFN Editor: Automatic Legacy Mapping Migration**: Implemented dynamic migration of legacy synthetic mappings (e.g. `"#g224"`) to standard physical `MAP1` mappings upon loading `translation_map.json`. This cleans up existing legacy databases instantly and saves the normalized file to disk.

## [0.2.103] - 2026-05-24

### Fixed
- **BFN Editor: Automatic Physical MAP1 Registration for Empty Glyphs**: Implemented automatic on-the-fly registration of physical character codes in the BFN `MAP1` metadata when assigning characters to previously unmapped (empty) glyphs.
  - Upon manual editing (`on_table_item_changed`), sequence filling (`fill_sequence_dialog`), or clipboard pasting (`paste_glyph_values`), if a target glyph does not have a physical character mapping in `MAP1`, the editor automatically registers the physical code `glyph_idx` to this glyph.
  - This converts previously synthetic empty-glyph mappings (like `#g224`) into clean, standard, and robust physical translations (e.g. `"я": "à"` where `"à"` is `chr(224)`), writing these physical mappings directly into the BFN file header and allowing the game engine to naturally locate these Cyrillic glyphs without custom runtime hacks.
  - Keeps backward compatibility fallback in the Zelda BMG plugin to load and repack older virtual maps using synthetic `#g` keys correctly.
  - Added full test coverage in `tests/test_ui/test_bfn_editor.py` with `test_bfn_editor_empty_glyph_automatic_physical_registration()` verifying the automatic physical registration pipeline.

## [0.2.102] - 2026-05-24

### Fixed
- **Zelda BMG Plugin: Fixed Encoding Loss (Swapping to Question Marks `?`) for Synthetic Empty Glyphs**: Fixed a critical bug where Cyrillic letters that were assigned to empty glyphs (with synthetic mapping keys like `#g224`) were written to the binary BMG file as question marks (`?`).
  - In `plugins/zelda_bmg/rules.py`'s `load_translation_map()`, updated the loading filter logic to accept synthetic empty-glyph mappings (`k.startswith("#g")` or `v.startswith("#g")`) instead of discarding them due to the ASCII value of `#` being lower than 128.
  - In `encode_string_with_mapping()`, implemented dynamic conversion of synthetic `#g{idx}` strings into one-byte characters with character code `idx` (e.g. converting `"#g224"` into `chr(224)`) when encoding messages to be written to BMG binary buffers, allowing them to perfectly map to physical BFN texture sheets inside the game.
  - In `decode_string_with_mapping()`, added fallback logic where if a CP1252 character is not present in `reverse_translation_map`, the plugin dynamically constructs a synthetic lookup key (`#g{ord(char)}`) and checks `translation_map` to successfully decode it back into the original virtual Ukrainian letter.
  - Added full test coverage in `tests/test_plugins/test_zelda_bmg_rules.py` containing a comprehensive end-to-end unit test `test_synthetic_empty_glyph_mapping()` that verifies mapping, encoding, decoding, packing, and unpacking of synthetic characters in the BMG lifecycle.

## [0.2.101] - 2026-05-24

### Fixed
- **BFN Editor: Empty Glyph Support for Character Mapping & Rendering**: Fixed issues when attempting to map, render, or save newly assigned characters for completely empty (unmapped) glyphs (e.g. glyphs with no pre-existing MAP1 entries in the `.bfn` file).
  - In `on_table_item_changed`, fixed a blocking guard `if not orig_char: return` which was preventing the editor from assigning virtual characters (`reverse_translation_map`) to empty glyphs.
  - In `load_translation_map`, fixed a filtering condition `ord(k) >= 128` that was discarding synthetic keys like `#g182` due to the ASCII value of `#` being lower than 128. Synthetic keys are now explicitly preserved and successfully reloaded upon restarting the application.
- **BFN Editor: Automatic Metric Calibration for Empty Glyphs**: Fixed a bug where auto-detecting and applying width metrics during font rendering was skipped for empty glyphs.
  - Extended the WID1 packet array on-the-fly both inside the rendering loop (`bfn_io.py`) and inside the command undo/redo structures (`RenderFontCommand` in `bfn_commands.py`) whenever a glyph's index falls outside the initial WID1 range. This guarantees that newly rendered Cyrillic characters are perfectly calibrated using pixel-accurate automatic widths immediately after generation, even if their respective physical glyphs were originally unallocated.

## [0.2.100] - 2026-05-24

### Added
- **BFN Editor: Vertical Scale Slider for System Font Rendering**: Added a **Vertical Scale** control in the "Render System Font to Glyphs" dialog alongside the existing Horizontal Scale. Both controls are now fully interactive sliders (`ScaleSliderWidget`) with adjustable min/max boundaries (including negative values for mirror flipping) and a live-updating current-value spinbox.
- **BFN Editor: `ScaleSliderWidget` — Reusable Interactive Scale Control**: Implemented a new reusable `ScaleSliderWidget` component in `bfn_widgets.py`. It combines a minimum boundary spinbox, a `QSlider`, a maximum boundary spinbox, and a current-value spinbox (with `%` suffix) in a single row. The widget features full two-way reactive binding: dragging the slider updates the value field instantly; typing a value outside the current bounds automatically extends the min/max limits accordingly; changing the boundaries dynamically updates the slider range.

### Fixed
- **BFN Editor Simulation Preview: Cyrillic Characters Displayed as Empty Boxes**: Fixed a bug where typing Cyrillic text into the BFN Editor simulation panel produced empty rectangles (fallback boxes) instead of the correct glyphs. The root cause was that the simulation's `update_simulation()` method called `layout_text` without passing the active `translation_map`, causing the character-to-glyph lookup to fail for all virtual (Cyrillic) characters. Fixed by reading the editor's `translation_map` attribute and forwarding it into the `layout_text` call: `bfn_temp.layout_text(text, translation_map=trans_map, ...)`. The simulation preview now correctly renders Cyrillic symbols matching the main Picoripi preview.

### Changed
- **BFN Editor: QPainter-Based 2D Scaling Replaces `QFont.setStretch`**: The system font rendering pipeline (both live preview in `RenderFontDialog._update_preview` and final batch rendering in `bfn_io.py`) now scales glyphs via `QPainter.scale(sx, sy)` centered on the glyph cell's geometric midpoint, instead of the limited `QFont.setStretch` (horizontal only). This enables independent horizontal and vertical stretch with full support for negative scale factors (mirroring), and guarantees that the live preview pixel-accurately matches the final rendered output written to the BFN texture.

## [0.2.99] - 2026-05-24

### Added
- **Tools Menu: Import Current BMG from JSON**: Added a new action `Tools → Import Current BMG from JSON...` that imports text content from a previously exported JSON file back into the currently selected BMG block.
  - Opens a file picker dialog to select any `.json` file.
  - Automatically detects the JSON structure: supports files with both `source` and `translation` sections (prompts the user to choose which one to import), files with only one section, or plain single-block JSON exports.
  - Shows a confirmation dialog listing the block name and number of strings to be replaced before applying changes.
  - Reconstructs each message via `BMGMessage.from_dict` and converts it to editor text using the active plugin's `msg_to_editor_text`, preserving all control codes and tag formatting.
  - Replaces all existing in-memory edits for the block with the imported strings (clean overwrite using tuple-keyed `edited_data`).
  - Automatically triggers a full UI refresh: block list, string list, text views, title bar, and issue rescan for the affected block.
  - Action is enabled only when a project is open and automatically enables/disables with the project via `_set_project_actions_enabled()`.
  - Displays a summary dialog on success with the count of imported strings.

### Fixed
- **Import BMG from JSON: TypeError on `edited_data` Key Type**: Fixed a `TypeError: cannot unpack non-iterable int object` that occurred when importing a JSON file. The previous implementation stored imported strings as `ds.edited_data[block_idx] = list`, but `edited_data` expects `(block_idx, string_idx)` tuple keys. Changed to store each string individually as `ds.edited_data[(block_idx, string_idx)] = text`.

## [0.2.98] - 2026-05-24

### Fixed
- **BFN Font Editor: Sheet 0 Renders as Black on Initial Open**: Fixed a bug where opening the BFN Font Editor (or navigating from the Glyph Table to Sheet 0) caused the canvas to remain completely black until the user manually clicked on another sheet and returned to Sheet 0. Root cause: `set_current_sheet_row` blocks tree widget signals to avoid recursion when selecting the sheet item, which prevented `currentItemChanged` from firing and thus `select_sheet` (the method that actually loads and paints the sheet texture) was never called. Fixed by adding an explicit `self.select_sheet(sheet_idx)` call inside `set_current_sheet_row` after the tree selection is programmatically set.
- **BFN Font Editor: "Render Font to Selected" Preview Shows Empty Glyph**: Fixed a bug where the "Render System Font to Glyphs" dialog showed a black square for the preview of the currently selected glyph. The character mapping lookup for `mapping_type == 2` in `bfn_io.py` was incorrectly using `entries[idx]` (direct index lookup by glyph index), which produced wrong or control character codes. The correct approach is to iterate entries searching for a matching glyph index and compute the character code as `m_first + c_idx`, consistent with all other places in the codebase that handle type-2 mappings.

## [0.2.97] - 2026-05-24

### Fixed
- **BMG Packer: Unicode Characters Encoded with `errors='replace'`**: Fixed a critical silent data-loss bug in `bmg_tool.py` where attempting to save a translated BMG block containing characters absent from the CP1252 encoding (e.g. Cyrillic letters that map to a different code-page) would raise `UnicodeEncodeError` inside the plugin. The exception was silently swallowed and the plugin returned empty bytes `b""`, causing the archive packer to overwrite the on-disk BMG with an empty/corrupt file. All subsequent reloads of the project would show the old (pre-translation) text because the packed archive still contained the original bytes. Fixed by passing `errors='replace'` to `part.encode(self.encoding, ...)`, which substitutes unmappable characters with `?` instead of crashing. Text is now always saved correctly, even when individual glyphs are outside the active code-page.
- **`zelda_bmg` Plugin: `log_error` NameError on Save Failure**: Fixed a `NameError: name 'log_error' is not defined` crash inside `plugins/zelda_bmg/rules.py`. The function `log_error` was called inside the `except` block of `save_data_to_json_obj` but was never imported. Added the missing import from `utils.logging_utils` and wrapped the entire save body in a `try/except` to produce a clean log entry on failure instead of a raw unhandled exception.
- **`app_action_handler`: TypeError in `_apply_scroll` During Tests**: Fixed a `TypeError` in `handlers/app_action_handler.py` when `_apply_scroll` was invoked in a mock/test environment where `scrollbar.value()` returned a `MagicMock` instead of an integer. Added an `isinstance` guard before arithmetic comparison.
- **Title/Status Bar: Plugin State Check**: Fixed an incorrect plugin availability check in `ui/updaters/title_status_bar_updater.py` that would cause an `AttributeError` when no plugin was loaded.

## [0.2.96] - 2026-05-23


### Fixed
- **BMG Pre-loading**: Fixed a critical bug in `core/data_state_processor.py` where BMG structure was pre-loaded using temporary disk-based `.extracted/` paths. Because `.extracted/` paths always resolve to the temp directory regardless of the `is_translation` flag, the application was reading stale or corrupt BMG files from previous sessions. BMG structures are now pre-loaded directly from the **archive containers** in memory (via `get_archive_container`), ensuring proper and up-to-date metadata.
- **Archive Block Selection**: Fixed a bug in `handlers/project_action_handler.py` where `edited_file_data` was populated by taking index `0` of the parsed data for archive blocks, causing a mismatch if the block had a different `internal_key` or `sub_idx != 0`. The sub-block is now correctly selected using `block.internal_key` or list index matching.
- **Pristine UA Archive Recovery**: Copied the original clean English `bmgres.arc` to the UA translation directory, successfully recovering the translation workspace after it had been corrupted by older versions of the repacker.

### Changed
- **Test Suite Alignment**: Updated `tests/test_core/test_data_state_processor_native_packing.py` to match the new native in-memory preloading logic.

## [0.2.95] - 2026-05-23

### Added
- **Tools Menu: Export Current BMG to JSON**: Added a new action `Tools → Export Current BMG to JSON...` that exports the text content of the currently selected BMG block to a human-readable JSON file.
  - Reads both the **source** (ENG) and **translation** (UA) BMG files from their respective archives.
  - The resulting JSON contains all message metadata: `id`, `is_null`, `info` (hex), and `parts` (text strings and escape tags serialized via `BMGMessage.to_dict()`).
  - Includes file header info: `encoding`, `endianness`, `file_id`, `section_order`, `message_count`.
  - Provides a save file dialog with a default name based on the block name.
  - Action is enabled only when a project is open, and automatically enables/disables with the project via `_set_project_actions_enabled()`.
  - Useful for debugging: you can verify exactly what text is stored in the archive before and after translation.

## [0.2.94] - 2026-05-23

### Fixed
- **BMG Packer: Perfect Byte-Perfect Roundtrip for Twilight Princess Archives**: Fixed multiple critical bugs in `bmg_tool.py` that caused corrupted BMG files when saving to `bmgres.arc` in Twilight Princess projects.

  **Bug 1 — MID1 `entry_len=0` quirk (Twilight Princess format)**: The original `zel_00.bmg` uses `entry_len=0` in the MID1 section header — a non-standard Twilight Princess convention where message IDs are stored contiguously. The old code treated `entry_len=0` as a literal stride, appending empty strings `''` as IDs instead of integers. As a result, `has_ids` was `True` but `bytes.fromhex('')` returned `b''`, so MID1 was written with only a 16-byte header instead of 20,032 bytes. Fixed by computing the real stride from section size divided by count:
  ```python
  if entry_len == 0 and count > 0:
      real_entry_len = (len(sec_data) - 16) // count  # e.g., 4 bytes
  ```

  **Bug 2 — `has_ids` checked attribute existence instead of type**: Changed from `hasattr(m, 'id')` to `hasattr(m, 'id') and isinstance(getattr(m, 'id'), int)`, so messages with `id=''` (empty string from old corrupt files) no longer trigger MID1 writing.

  **Bug 3 — `original_total_size` not preserved**: In Twilight Princess BMGs, the `total_size` header field does not match the actual on-disk file size (it excludes trailing data and FLW1 alignment padding). Saving the recomputed size corrupted the file header. Now `original_total_size` is stored at load time and written back unchanged.

  **Bug 4 — Trailing bytes after last section were lost**: `zel_00.bmg` contains 632 bytes of trailing data after the FLW1 section that were silently dropped during repacking. Now `trailing_data` is preserved and appended at the end of `save()`.

  **Bug 5 — MID1 header written with wrong `entry_len`**: The original header stores `entry_len=0` (the TP quirk), but the save code was writing `4`. Added `_mid1_entry_len_header` field to preserve the original value for exact roundtrip.

  **Bug 6 — Null messages missing from MID1**: Messages with `is_null=True` were skipped in MID1 generation, breaking ID-to-index alignment for all subsequent messages. Null messages now write a zero ID to maintain proper index alignment.

  **Result**: Both `zel_00.bmg` (309,208 bytes) and `zel_unit.bmg` (448 bytes) now achieve **100% byte-perfect roundtrip** — `repacked == original` verified by section-level and full byte comparison.

- **Archive Save: Cache Invalidated After Pack**: After `container.pack()` writes the packed archive to disk, `clear_archive_cache()` is now called immediately. This ensures the next read of the same archive gets the fresh on-disk version rather than the stale in-memory container.

### Changed
- `BMGFile` now stores additional roundtrip metadata: `original_total_size`, `trailing_data`, `mid1_entry_len`, `mid1_unk`, `_mid1_entry_len_header`.

## [0.2.93] - 2026-05-23

### Fixed
- **BFN Glyph Table: 32-Position Index Shift on New Projects**: Fixed a critical bug in `core/bfn_core.py` where BFN fonts with linear `mapping_type == 0` were converted to `mapping_type == 2` with incorrectly shifted `entries`. The old code used `entries = [first_char + i for i in range(entry_count)]`, which placed the space glyph (character code 32) at grid position 32 instead of position 0. The fix changes the formula to `entries = [i for i in range(entry_count)]`, so entries correctly start from 0 regardless of the font's first character code. This resolves glyph misalignment visible in the Glyph Table when opening a new project with freshly unpacked game fonts.
- **Unit Test Alignment**: Updated `test_bfn_core_linear_mapping_type_0_conversion` in `tests/test_ui/test_bfn_preview_widget.py` to expect index-based entries `[0, 1, …, 10]` instead of the previously incorrect character-shifted values `[32, 33, …, 42]`.

## [0.2.92] - 2026-05-23

### Improved
- **BFN Font Editor: Alphabet Selector in Fill Dialog**: The "Fill sequentially From/To..." dialog now shows an **Alphabet** dropdown combobox with named presets (Latin A–Z, Cyrillic А–Я uppercase/lowercase, Greek, Arabic, Hiragana, Katakana, Hangul, and a Custom option).
  - Selecting a preset instantly updates the Start and End character fields.
  - Manually editing Start or End automatically switches the combobox to "Custom" so the preset does not override user input.
  - The default preset is still determined automatically from the active spellchecker language (`uk`/`ru`/`be` → Cyrillic uppercase, `el` → Greek, etc.).

## [0.2.91] - 2026-05-23

### Added
- **BFN Font Editor: Language-Aware Alphabet Fill Defaults**: The "Fill sequentially From/To..." dialog in the Glyph Table now automatically pre-fills the Start and End character fields based on the active spellchecker language.
  - If the spellchecker is set to a Cyrillic language (`uk`, `ru`, `be`, `bg`, `sr`, `mk`), the dialog defaults to А–Я (`U+0410`–`U+042F`).
  - Greek (`el`) defaults to Α–Ω; Arabic (`ar`) to the basic Arabic block; Japanese (`ja`) to Hiragana; Korean (`ko`) to the beginning of the Hangul syllable block; all other languages default to A–Z.
  - The language is determined automatically from `spellchecker_language` in the parent `MainWindow` (no extra configuration needed). The hint `(detected: uk)` is shown in the dialog for transparency.
  - The user can still override the values manually before confirming.

## [0.2.90] - 2026-05-23

### Fixed
- **BFN Font Editor: Kerning/Width Marker Dragging in `ImageView`**: Fixed a bug where the kerning (blue) or width (red) vertical lines in the glyph grid could be grabbed even when the mouse cursor was positioned *above* or *below* the actual glyph row that owns the line. The hit-test now correctly checks that the cursor's Y coordinate falls within the vertical bounds of the glyph cell before activating the drag handle.
- **BFN Font Editor: Drag-to-Edit Metrics Correctness**: Replaced the old erratic per-pixel drag logic in both `ImageView` and `SimGlyphItem` with a delta-based approach. The drag now stores the exact values of `kerning` and `width` at the moment of mouse press and calculates the new value as `initial_value + Δx`. This removes the "rubber-band" jumping effect that occurred when dragging resumed from an unexpected position.
- **BFN Font Editor: Undo Stack Flooding on Drag**: Fixed a regression where every pixel moved while dragging a metric line pushed a separate `EditMetricsCommand` onto the undo stack, making Ctrl+Z effectively unusable after a drag. Now `blockSignals(True/False)` wraps the spinbox update during drag, and a single `EditMetricsCommand` is pushed only on `mouseReleaseEvent`, making the entire drag one undoable action.
- **BFN Font Editor: AutoWidth Adds 1px Air Around Glyph**: The `auto_detect_width` function in `bfn_io.py` now adds 1 pixel of padding on each side when setting kerning and width, unless the glyph has a sharp edge (fewer than 5 consecutive pixels in the topmost or bottommost contact row). Sharp glyphs (e.g., W, Y, V with pointed tops/bottoms) are detected by scanning the contact row and counting only the longest *unbroken* run of set pixels — if the run is < 5, the boundary is placed flush to the glyph without padding.

## [0.2.89] - 2026-05-23

### Added
- **Interactive Angle Picker Wheel for Drop Shadow**: Replaced the plain numeric spinbox for shadow angle with a Photoshop-style interactive angle wheel (`AnglePickerWidget`) in the Drop Shadow settings dialog.
  - Drag the needle or click anywhere on the wheel to set the shadow direction visually.
  - A `QSpinBox` next to the wheel stays in sync for precise numeric input — changing one updates the other instantly.
  - 0° = right, 90° = down, 270° = up, 315° = upper-left (same convention as the rendering engine).
  - The widget auto-adapts its color scheme based on the application theme (dark/light background detection).
- **Fix Font Scale for BFN Preview**: Added a new checkable option **"Fix Font Scale"** to the BFN Preview right-click context menu.
  - When enabled, the current glyph scale factor is frozen. All subsequent string switches will render at the same letter size, regardless of string length or text rect dimensions.
  - When disabled, the widget returns to automatic scaling (letters fill the text rect proportionally).
  - Both the enabled state and the locked scale value are persisted in `settings.json` across sessions (`preview_fix_font_scale`, `preview_fixed_font_scale`).

## [0.2.88] - 2026-05-23

### Added
- **Drop Shadow Effect for BFN Preview Text**: Added a Photoshop-style drop shadow effect to the BFN Preview widget text rendering.
  - Configurable shadow **color**, **opacity** (0–255), **angle** (0°–360°) and **distance** in pixels.
  - Accessible via right-click context menu → **Text Effects → Drop Shadow...**.
  - Settings are persistent across sessions (stored in `settings.json`).
- **Outer Glow Effect for BFN Preview Text**: Added an outer glow halo around the rendered BFN glyphs.
  - Configurable glow **color**, **opacity** (0–255), and **spread** radius in pixels (1–20).
  - Implemented via multi-pass offset rendering in 8 directions — no external blur dependencies.
  - Accessible via right-click context menu → **Text Effects → Outer Glow...**.
- **Text Color for BFN Preview**: Added the ability to set an arbitrary color for the rendered BFN text.
  - Uses offscreen `QImage` rendering with `CompositionMode_SourceIn` for accurate glyph tinting without alpha artifacts.
  - Color is selected via standard `QColorDialog` (**Text Effects → Text Color...**).
- **`TextEffectsDialog`**: New reusable `QDialog` (`ui/components/text_effects_dialog.py`) shared between Shadow and Glow settings. Includes a color preview swatch + color picker button, opacity slider with synced spinbox, and angle/distance/spread spinboxes.
- **Offscreen Glyph Pipeline**: Introduced `_render_glyphs_to_image()` helper that renders all BFN glyphs onto a transparent `QImage` for compositing (used for shadow, glow, and tint passes). Rendering order is: **Glow → Shadow → Tinted main glyphs**.

## [0.2.87] - 2026-05-23

### Added
- **Background Image Ctrl+Drag Scaling**: Holding `Ctrl` while dragging with the left mouse button inside the BFN Preview widget now adjusts the background image scale. The further you drag from the click origin, the more the image scales. No separate "Scale Background" button is needed — scaling is now a pure keyboard+mouse interaction.
- **Background Image Alt+Drag Panning**: Holding `Alt` while dragging with the left mouse button pans (moves) the background image freely in 2D within the preview widget. The offset is persisted to `settings.json` on mouse release.
- **Hide Background Context Menu Action**: Added a "Hide Background" toggle action to the BFN Preview right-click context menu. The action is checkable, reflects current visibility state, and is disabled when no background image is set.
- **Background Position Persistence on Image Swap**: When replacing the background image with a new one, Picoripi now preserves the current offset (`bg_offset_x`/`bg_offset_y`) so the new image is placed at the same position as the previous one. The image is centered automatically only when there is no prior positioned background (offset is zero and no image was loaded). This allows using a first reference image to position text and then switching to a final screenshot without losing alignment.
- **Preview Toggle Menu Action**: Added a "Show Preview" checkable action to the View menu (`toggle_preview_action`), connected to `update_preview_visibility`. The action respects BFN font availability — it is disabled and unchecked when no BFN fonts are loaded.
- **`update_preview_visibility` Method**: New method in `PreviewUpdater` that controls BFN preview widget show/hide based on loaded fonts and the toggle action state.

### Fixed
- **Width-Exceed Green Highlight Marker Visibility**: Fixed a regression where the green rectangle marker (indicating the exact character where a line exceeds the allowed pixel width) would flash briefly on click and then disappear. Root cause: `add_width_exceed_char_highlight` added extra selections but did not call `applyHighlights()`, so Qt never rendered them. Fixed by calling `self.applyHighlights()` at the end of `add_width_exceed_char_highlight` and `clear_width_exceed_char_highlights` in `TextHighlightManager`.
- **Background Image Renders Behind Text**: Fixed a rendering order bug where the background image was painted over the BFN text rendering, making text invisible when a background was active. The background is now painted first in `paintEvent`, then text and overlays are drawn on top.
- **Text/Background Misalignment on Preview Resize**: Resolved a bug where resizing the preview window caused the text and background image to shift independently. The background position is now stored as an absolute pixel offset and the text rectangle is computed relative to the widget via `get_absolute_text_rect()`, keeping them anchored consistently regardless of widget size changes.

## [0.2.86] - 2026-05-23

### Fixed
- **BFN Preview Glyphs Rendering Consistency**: Resolved an issue where glyphs were loaded using a skewed character mapping table upon initial application startup.
  - **Automatic Linear Mapping Conversion**: Integrated dynamic `mapping_type == 0` (linear map) conversion directly into the binary `BfnCore.load()` parser. It now converts linear mappings to index-based `mapping_type = 2` and generates a proper contiguous `entries` array on-the-fly, replicating BFN Editor's save-time behavior for out-of-the-box consistency.
  - **Relatively Offset Indices in `layout_text`**: Corrected index calculations for `mapping_type == 0` within `BfnCore.layout_text()`, ensuring characters are mapped to `idx - m_first` (relative grid position) rather than their absolute character code `idx`.
- **Permanent BFN Fonts Cache Persistence**: Modified `FontMapLoader.load_all_font_maps` to copy and preserve already loaded BFN fonts inside `mw.all_bfn_fonts` instead of completely clearing the dictionary. This prevents BFN fonts synchronized from BFN Editor from being lost when reloading plugin settings or closing the editor.
- **Preview Standalone Fallback**: Enabled `BfnPreviewWidget.get_active_bfn_font` to fall back to the first available BFN font in the cache if the active block does not specify a font filename (e.g. when working outside a project context).

## [0.2.84] - 2026-05-23

### Added
- **Premium Light Theme Menus**: Implemented dynamic HSL-based light stylesheet styling for `QMenuBar` and `QMenu` inside `LIGHT_THEME_STYLESHEET`. This forces Qt to use its internal stylesheet-based engine instead of native OS menu elements on Windows.

### Fixed
- **Disabled Menu Item Graying**: Resolved a visual issue in Light Theme where disabled menu items (such as "Import Block..." or "Import Directory...") were rendered with default dark system text color instead of being visibly grayed out. Disabled items now render beautifully in a muted gray color (`#888888`).
- **Disabled Menu Tooltips**: Fixed standard Qt event routing for disabled menu items. Intercepting `QEvent.ToolTip` in `MenuToolTipEventFilter` now correctly retrieves and shows explanation tooltips (e.g. *"This action is only available in Project mode (within a .uiproj project)."*) when hovering over disabled elements.
- **Import Directory Signal Binding**: Resolved a binding bug where clicking **File -> Import Directory...** when active did not trigger any handler action. Connected `triggered` signal of `import_directory_action` to `project_action_handler.import_directory_action`.
- **Project Close State Sync**: Secured program startup logic to correctly determine and set the initial enabled state of `close_project_action` and block navigation toolbar buttons based on whether a project/file was loaded via auto-restore.

## [0.2.83] - 2026-05-22

### Fixed
- **BFN Preview Layout Coordinate Calculation**: Fixed coordinate grid calculations (`gx` and `gy`) in `BfnPreviewWidget` when mapping BFN font glyphs. Replaced vertical height references with horizontal width references, correcting skewed characters and preview misalignment for non-square font grids (such as the original game's `rodan_b_24_22.bfn` font layout).
- **BFN Type-2 Character Mapping**: Reverted character mapping decoding changes for BFN type-2 formats to ensure the mapping index aligns correctly with the character codes defined in the font.

## [0.2.82] - 2026-05-22

### Added
- **AI Traffic Logging**: Implemented dedicated AI request/response traffic logging to both the main debug log (`app_debug.txt`) and a separate `ai_traffic.log` file in the project root for transparency and debugging of prompt data.

### Fixed
- **Translation Text Source in Glossary/AI Translation**: Fixed a bug where `None` was sent to the AI translator as original text due to referencing the deprecated `self.mw.data` field in `GlossaryHandler`. Updated the glossary handler to retrieve data from `self.mw.data_store.data`.

## [0.2.81] - 2026-05-22

### Fixed
- **Cyrillic Rendering in BFN Preview**: Corrected the glyph mapping logic for `mapping_type == 2` in `BfnPreviewWidget`. This aligns preview rendering with the BFN simulation, correctly rendering Cyrillic characters instead of empty boxes or `NNN` placeholders.

## [0.2.80] - 2026-05-22

### Added
- **Glyph Editor Column Width Persistence**: Implemented automatic saving of user-configured column widths inside the Glyph Table of the BFN Font Editor.
  - The columns width configuration is saved inside `settings.json` under the key `"bfn_glyph_table_column_widths"` upon closing the BFN Font Editor window or exiting the main program.
  - The saved column widths are automatically restored upon opening or reloading BFN fonts in the Glyph Table.
  - If no widths are saved yet, the table defaults to a smart auto-fitting mode that resizes columns according to cell contents while completely excluding long column headers, ensuring optimal visual density without unnecessary blank space.

## [0.2.79] - 2026-05-21

### Added
- **BFN Font Editor Toolbar Access**: Added a dedicated "BFN Font Editor" shortcut button with a custom desktop icon to the main application toolbar (located next to the AI Chat button), allowing users to launch the standalone Nintendo BFN Font Editor with a single click.

### Fixed
- **Font & Icon Clipping in BFN Editor**:
  - Fixed a visual issue where the first letter in the "Glyph Table" tab title (the letter 'G') was cropped vertically. Removed dynamic bold font scaling (`font-weight: bold`) from selected tabs inside the premium stylesheet, ensuring stable, pixel-perfect tab rendering.
  - Resolved a horizontal text-clipping bug where column headers in the Glyph Table (such as "Character" starting with 'C') were clipped by cell grid lines. Replaced the generic `padding: 6px;` inside `QHeaderView::section` with a generous horizontal padding of `6px 12px;`.
  - Implemented smart table column resizing: set the default resizing mode of the Glyph Table to `ResizeToContents` so that short metadata columns are automatically sized perfectly without clipping headers, while allowing "Texture Sheet" and "Tile Position" to `Stretch` and gracefully occupy all residual width.
- **Tree-View Collapse Bug**: Resolved a navigation bug where expanding one archive tree node, expanding another, and then selecting a sheet inside one of the trees would cause the other tree node to collapse. Upgraded `load_from_extracted_dir` inside `bfn_io.py` to collect and preserve the hierarchy's expanded node states *before* clearing and rebuilding the `QTreeWidget` structure.

## [0.2.78] - 2026-05-21

### Added
- **Permanent Black Backgrounds for Glyph Table Renders**: Updated cell label stylesheets inside `populate_glyph_table` and `refresh_table_row` in `bfn_navigation.py` to always utilize a solid black background (`#000000`) for the "Glyph Render" column in the Glyph Table tab, keeping white or transparent glyphs completely visible across all theme configurations.

## [0.2.77] - 2026-05-21

### Added
- **Persistent Font Tree Expansion State**: Upgraded `rebuild_tree_widget` inside `BfnEditorWindow` to preserve the user's manual expand/collapse states for archives and files in the tree view during active font transitions or metadata saves, avoiding disruptive tree resets.
- **Permanent Black Canvas Backgrounds for BFN Views**: Configured both `ImageView` and `SimImageView` in `bfn_widgets.py` to always render with a rich black background brush and viewport style, ensuring light-colored (white/transparent) font glyphs are clearly visible and legible, regardless of whether the light or dark app theme is selected.

## [0.2.76] - 2026-05-21

### Added
- **Automatic Font Tree Scan on Window Show**: Integrated the directory font scanning and hierarchical tree rebuilding directly into the `showEvent` of `BfnEditorWindow`. Opening the BFN Editor in standalone mode or switching settings will now instantly reload all available loose fonts and decompressed archives, automatically filling the tree layout with the correct hierarchy (Archive -> Font -> Sheets) without manual user action.

### Removed
- **Streamlined Font Management Interface**: Removed the manual "Open BFN / Folder..." button from the BFN Font Editor layout. Since all fonts from local folders and game archives are now scanned, decompressed, and populated automatically via the plugin settings, manual file-based opening is no longer required, creating a cleaner and fully-automated visual translation workflow.

## [0.2.75] - 2026-05-21

### Added
- **Global Font Maps Integration**: Integrated all custom and archive-extracted font maps directly into the main window font selector (`font_combobox`) and the mass font assignment dialog (`MassFontDialog`), making every single parsed font immediately available.
- **Hierarchical Font & Archive Scan inside BFN Font Editor**: BFN Font Editor now scans the active plugin and the custom fonts directory upon launching, automatically building a comprehensive hierarchy tree of all archives, files, and texture sheets.
- **Dynamic Save callbacks for Disk Assets**: Implemented smart saving for disk-based loose files and game archives. Modifying and saving files in BFN Font Editor dynamically repackages disk `.arc`/`.rarc`/`.u8` archives and updates the memory cache.
- **Real-Time Font Synchronization**: Changes saved in BFN Font Editor are instantly reloaded across the entire workbench, refreshing all text views and layout warnings immediately.

## [0.2.74] - 2026-05-21

### Added
- **Automatic In-Memory Archive Font Scan**: Added background scanning and decompression of game archives (`.arc`, `.rarc`, `.u8`) inside the user-specified Fonts Directory. Picoripi automatically unpacks these archives in memory and extracts BFN and JSON font maps, registering them as select-able fonts under `{archive}/{font_name}` for real-time text layout.
- **Dynamic BFN Font Metrics & Preview Support**: All fonts found in the archives of the fonts directory are now fully supported for pixel-perfect letter width calculation in Picoripi's main text view and dynamically rendered inside the bottom preview widget.
- **Tree-Based Layout in BFN Editor (QTreeWidget)**: Upgraded the sheet navigation in BFN Font Editor from a flat `QListWidget` to a structured `QTreeWidget`. It represents an intuitive hierarchy: **Archive** -> **Font Files** -> **Texture Sheets** inside each font.
- **Seamless Archive Font Switching**: Allows the user to switch active BFN fonts inside the same archive seamlessly in real-time from the tree navigation. Includes a dirty-check warning to save any pending changes before switching.
- **Dynamic Save Callbacks**: Refactored saving in BFN Font Editor to utilize dynamic save callbacks, allowing individual fonts to be packed directly back into RAM-based container archives and instantly updating the main Picoripi UI.

## [0.2.73] - 2026-05-21

### Added
- **Plugin Fonts Directory Path Configuration**: Added the ability to specify a custom fonts directory path (`fonts_dir_path`) in **Plugin -> File Paths** tab (labeled as **Fonts Directory Path**). This allows loading external fonts (both `.json` and `.bfn` files) dynamically from any local directory.
- **Dynamic Font Map Merging**: Fonts found in the user-specified directory are seamlessly loaded and merged with the active plugin's default fonts. Custom fonts of the same filename elegantly override built-in ones, offering maximum flexibility.
- **Dynamic Font List Reloading**: Modifying the fonts directory path instantly refreshes the default font selection list under the **Plugin -> Display** tab without requiring a restart.
- **Config Persistence**: The custom fonts directory path is saved persistently in the active plugin's `config.json` configuration file, ensuring the settings remain intact across sessions.
- **Comprehensive Unit Testing**: Added robust unit tests verifying the persistence of the new `fonts_dir_path` setting during load and save operations under `PluginSettings`.

## [0.2.72] - 2026-05-21

### Added
- **Dynamic Theme Inheritance for BFN Font Editor**: Added complete support for dynamic dark and light theme inheritance. BFN Font Editor now automatically syncs its UI appearance with the main Picoripi settings (`settings.json`).
- **Premium Light Theme**: Designed and implemented a custom light theme palette and QSS stylesheet specifically tailored for BFN Font Editor, using harmonized HSL-based colors (clean light gray windows, dark text, clean slate buttons, and elegant blue highlights).
- **Theme-Adaptive Glyph Previews**: Configured the glyph character table to dynamically switch background colors depending on the active theme (white background for light theme, dark for dark theme) to maintain pristine visual contrast and readability of glyph texture sheets.
- **Adaptive Context Menus**: The glyph table context menus now fully inherit the active theme stylesheet.

## [0.2.71] - 2026-05-21

### Fixed
- **Theme Isolation in BFN Tool**: Resolved an issue where opening the BFN Font Editor would leak its custom dark color palette (`QPalette`) to the entire QApplication, inadvertently breaking the main Picoripi window style and dialogues. The palette is now properly localized and scoped strictly to the BFN Font Editor window (`widget.setPalette`).

## [0.2.70] - 2026-05-21

### Fixed
- **Light Theme Restoration**: Fully restored and polished the visual design of the Light Theme. Explicitly defined all color palette entries (Window, Base, WindowText, Buttons, etc.) to prevent layout degradation and accidental fallback to dark system colors on Windows operating systems running in dark mode.
- **Unit Tests TypeError Fix**: Fixed unit test failures (`TypeError: '<' not supported...`) within `BlockListUpdater` under mock environments by safeguarding the project blocks validation check against Mock objects.

## [0.2.69] - 2026-05-21

### Added
- **Nintendo Binary Font (BFN) Editor**: Integrated a visual editor and compiler for Nintendo GC/Wii binary fonts (`.bfn` format) as an embedded tool.
- **PyQt5 Adaptation**: Converted the BFN-editor from PySide6 to PyQt5, resolving Process-level Qt runtime conflicts.
- **In-Memory Archive Integration**: Added context menu action "Edit BFN Font..." for `.bfn` files, including those located inside RAM-based `.arc` and `.rarc` archives, allowing in-place edits and instant RAM repacking.
- **Real-Time Font Metrics Sync**: Configured the editor to automatically trigger `FontMapLoader` updates in Picoripi on save, immediately refreshing pixel-perfect line-width calculation and WYSIWYG font preview.
- **Automatic Test Coverage**: Created `tests/test_ui/test_bfn_editor.py` verifying editor initialization and RAM-based font loading.

## [0.2.68] - 2026-05-21


### Fixed
- **Wrapped Logical Block Selection**: Fixed a UI issue in the "Strings in block" list (`preview_text_edit`) where selecting a logical block that spans multiple visual lines (due to word wrap) via clicking or Shift+clicking would only highlight the first physical line or highlight only the text characters without extending to the full width. Now, the background selection is dynamically split into individual full-width highlights for each visual line layout belonging to the wrapped block, ensuring perfect full-width highlights with zero border bleeding.

## [0.2.66] - 2026-05-21

### Added
- **Block Properties Dialog**: Added a comprehensive "Properties..." action to the block tree context menu. It opens a detailed dialog displaying block/file metadata, including original name, container archive details, modified state, internal indices, absolute/relative paths, and physical file sizes on disk with easy path copying.
- **File Extensions in Archive Blocks**: Added original file extension rendering (e.g. `.bmg`) for blocks located inside archive containers (like `.arc`, `.rarc`, `.ark`) within the project tree. During inline renaming, users edit the clean name without extension, which is then dynamically re-appended for display.

## [0.2.65] - 2026-05-21

### Fixed
- **Archive Path Compaction Support**: Allowed single-child archive folders (e.g., `.arc`, `.rarc`, `.ark` containing exactly one block/file) to undergo Type 2 path compaction. Archive files with a single member (like `bmgres1.arc / zel_01`) now display compactly as a single leaf node, while archive folders containing multiple files (like `bmgres.arc` with two blocks) correctly remain uncompacted to show all their nested members.

## [0.2.64] - 2026-05-21

### Fixed
- **Virtual Folder Path Compaction (GitHub-style)**: Fixed a bug where single-child virtual folder path chains would uncompact and show as separate nested items when folders were expanded in the tree. Chains now remain compacted (e.g., `A / B / C`) regardless of the folder's expansion state.
- **Type 2 Compaction File Duplication**: Completely eliminated file duplication under compacted Type 2 nodes (folder containing a single block/file). The parent compacted node now directly represents the block and behaves as a leaf node in the tree without rendering redundant nested files. Also added correct programmatic selection focusing for compacted Type 2 nodes.

## [0.2.63] - 2026-05-21

### Added
- **Native In-Memory Archive Support**: Replaced external dependency executables `ArcExtract.exe` and `ArcPack.exe` with a native Python-based parser system for Nintendo GC/Wii archives.
- **In-Memory Writing & Yaz0 Compression**: Implemented fully virtualized container saving and repacking routines (supporting RARC and U8 formats, including Yaz0-compressed archives) that compile and write final data bytes directly to disk without spawning temp directories or executing sub-processes.
- **Robust Archive Test Coverage**: Added a comprehensive suite of unit tests in `tests/test_core/test_containers.py` verifying Yaz0 decompression/compression and RARC/U8 read/write/pack round-tripping.
- **Zero Disk Pollution**: Eliminated `.extracted/` folder generation entirely, keeping files virtualized in RAM during both read and save operations.

## [0.2.62] - 2026-05-21

### Added
- **System Temp-Dir Extraction**: Archives (`.arc`, `.rarc`, `.ark`) are now extracted into a private temporary directory under the OS `Temp` path (`tempfile.gettempdir()/picoripi/<project_id>`) instead of the `.extracted/` folder inside the project directory. This prevents polluting the user's workspace when opening or creating projects in place.
- **Full `.ark` Archive Support**: Integrated `.ark` files into the automatic archive extraction and packing pipelines. They are now automatically detected during project sync, unpacked using `ArcExtract`, displayed as virtual subfolders in the block tree, and repacked using `ArcPack` upon saving edits.
- **Automatic Temp Directory Cleanup**: Implemented automatic cleanup of the project's temporary directory when a project is closed or when the application is exited, ensuring no orphan extracted files are left behind.

## [0.2.61] - 2026-05-21

### Fixed
- **Virtual Block (Category) Shows All Strings**: Fixed a critical bug where navigating to a virtual block (category) would display all strings of the parent block instead of only the strings belonging to that category. Root cause: `string_selected_from_preview` was reading `category_name` from `self.mw` (which never has this attribute) instead of `self.mw.data_store`. This caused a second `populate_strings_for_block(block_idx, None)` call that overrode the category filter and reloaded all 5000+ strings.
- **~1 Second Block Navigation Lag**: Eliminated the ~1 second freeze when switching between blocks. The lag was caused by a redundant second call to `populate_strings_for_block` inside `string_selected_from_preview` — which, combined with the wrong `category_name=None`, triggered a full `setPlainText` of 5000+ lines even after the block preview was already correctly rendered. Removing the redundant call fixes both the lag and the category display bug simultaneously.
- **Archive Files Not Nested Under Archive Folder**: Fixed Type 2 folder compaction incorrectly merging an archive folder (e.g. `my_archive.arc`) containing a single file into one compacted item `my_archive.arc / filename`. Archive folders (`.arc`, `.rarc`, `.ark`) now always display as proper parent folders with their files nested as children, matching the expected tree hierarchy.

### Added
- **`.ark` Archive Icon Support**: Extended archive folder icon detection to include `.ark` extension in addition to `.arc` and `.rarc`. Folders whose name ends with `.ark` now also display the archive link icon (`SP_DirLinkIcon`).

## [0.2.60] - 2026-05-21

### Fixed
- **Move to Virtual Block Dialog**: Fixed a bug where clicking "Move to Virtual Block" threw a "No strings selected in preview" warning even when strings were highlighted. Corrected the code to retrieve the selected indices from `data_store.selected_string_indices` instead of the deprecated `mw.selected_string_indices` attribute.

### Added
- **Smart Archive Member Auto-Grouping**: Enhanced `ProjectManager.add_block` to automatically detect if a block belongs to an archive path structure (e.g. `.extracted/sources/my_archive.arc/inner_folder/file.txt`). It now automatically builds and nests the block within the corresponding virtual folder hierarchy (including parent directories and nested sub-folders), rather than placing it in the flat root block layout.
- **RARC Archive Folder Support**: Added support for `.rarc` archives to be automatically recognized in the block list tree view, styling them with the archive link icon (`SP_DirLinkIcon`) identical to `.arc` directories.
- **Virtual Structure Self-Healing**: Modified the project loading routine so that projects of version `1.1` without an active `virtual_folders` configuration will automatically undergo a structure rebuild migration, resolving instances of empty project trees in newly converted projects.

## [0.2.59] - 2026-05-21

### Fixed
- **Scroll Jumping in Large Block Previews**: Fixed scrollbar jumping to line 1 on clicking a string inside large block previews by referencing `displayed_string_indices` through `data_store` safely, avoiding incorrect dirty-checks that caused unnecessary full page resets via `setPlainText`.
- **Row Selection Bleed**: Replaced `QTextCursor.BlockUnderCursor` with `QTextCursor.EndOfBlock` keep-anchor selection in `TextHighlightManager` for row selection. This excludes the `\n` line boundary from the background format, ensuring only the target row is highlighted and preventing selection color bleed on adjacent rows under `FullWidthSelection`.

### Optimized
- **Instant Row Clicking with Prioritized Scan**: Optimized the block highlight update process in `_apply_highlights_for_block`. It now scans and calls problem analysis only for lines registered in `problems_per_subline`, removing the lag when selecting rows in blocks with 5000+ lines.

## [0.2.58] - 2026-05-21

### Added
- **Preview Cache System**: Added a caching mechanism (`_preview_cache`) in `PreviewUpdater` that stores the loaded lines and loading state of blocks. Switching between blocks now restores the preview instantly from the cache, eliminating any reload latency.
- **Cache Synchronization**: Tied preview cache lifecycle to project changes. The cache updates dynamically when editing lines and clears automatically during structural Undo/Redo operations or when closing/switching projects.

### Improved
- **Correct Scrollbar Proportions from Start**: The document structure is pre-populated with empty lines (`\n`) for the entire block size on initial load. This sets the scrollbar to the exact correct height instantly, enabling scrolling through the entire 5000+ line block immediately.
- **Background Loading via QTextCursor**: Switched from `appendPlainText` to in-place block updates using `QTextCursor` wrapped in `beginEditBlock()` and `endEditBlock()`. This avoids document height recalculations, eliminating rendering lag and freezing during scrolling.
- **Static Line Number Area Width**: Added `override_total_lines` to `LineNumberedTextEdit` to reserve the correct horizontal width for line numbers beforehand, preventing layout twitching as background loading proceeds.

## [0.2.57] - 2026-05-21

### Optimized
- **Lazy Chunked Loading for Block Previews**: Introduced an asynchronous chunked loading system for the preview panel in `PreviewUpdater`. When a block is selected, the first chunk of 200 lines (or enough to cover the active string) is loaded instantly. The remaining lines are loaded incrementally in the background using a 15ms `QTimer` in chunks of 500 lines. This ensures instant GUI responsiveness and eliminates the 2-3 second freeze on large blocks (5000+ lines).
- **Single-Line Preview Updates**: Optimized `TextOperationHandler._update_preview_content` to perform partial single-line preview updates via `QTextCursor` instead of fully rebuilding the document via `setPlainText` on every character stroke. This reduces text-entry latency to zero even inside blocks containing thousands of lines.

### Added
- **Chunked Loading Verification Tests**: Added comprehensive unit tests (`test_populate_strings_chunked` and `test_TextOperationHandler_update_preview_content_partial`) to guarantee correctness of both lazy loading and partial updates.

## [0.2.56] - 2026-05-21

### Added
- **Directory Mode (Folder) / File Mode Switcher in File Paths**: Added a dedicated `Directory Mode (Load from folder)` toggle directly in the Settings -> Plugin -> File Paths dialog. This allows switching the current workspace loading between single-file and directory-based structures dynamically, applying to both project and standalone configurations.
- **Auto-Generate Translation Path**: Integrated an `Auto-generate translation path` feature. When enabled, it locks the changes path field and dynamically constructs the translation file or directory path on-the-fly based on the original path input:
  - **Directory Mode**: Appends `_translation` to the directory name (e.g. `parent/folder` -> `parent/folder_translation`).
  - **File Mode**: Appends `_translation` to the file stem while preserving the extension (e.g. `parent/file.json` -> `parent/file_translation.json`).
- **Dynamic Browse Sensitivity**: The `...` browse button dynamically adapts its behavior to open either folder selection (`QFileDialog.getExistingDirectory`) or file selection (`QFileDialog.getOpenFileName`) instantly based on the state of the Directory Mode checkbox, without requiring a project reload.

## [0.2.55] - 2026-05-20

### Improved
- **Dynamic Path Settings in Project Mode**: Replaced path field locking with fully dynamic and interactive path settings. Users can now view and edit the project's source and translation folders/files directly from the Settings dialog while a project is active.
- **Adaptive Settings UI Labels**: The Path sub-tab in Settings dynamically checks the project's `is_directory_mode` and updates labels automatically (e.g. "Original Directory Path" instead of "Original File Path").
- **Adaptive Browse Mode**: The "Browse (...)" button automatically invokes `QFileDialog.getExistingDirectory` when the project is folder-based, and uses the correct multi-format file selector (supporting JSON, ARC, RARC, BMG, BFN) when it is file-based.
- **Auto-Sync & Reload on Path Settings Edit**: Modifying paths in Settings automatically updates project metadata, triggers project file re-syncing, and refreshes the project blocks tree immediately. If not in project mode, changing paths automatically reloads the new translation files.

### Fixed
- **PyQt5 Startup Crashes**: Resolved potential `IndexError` on startup during UI initialization by securing index validation inside `preview_updater.py` and resetting stale block indices properly.

## [0.2.54] - 2026-05-20

### Added
- **RARC Archive Support (.rarc)**: Extended archive support to include `.rarc` format alongside `.arc`. Both formats are now transparently extracted and packed using `ArcExtract.exe` / `ArcPack.exe`.
- **BFN File Support (.bfn)**: Added `.bfn` to supported file extensions for both project syncing and inner-archive scanning, enabling font files to be tracked and edited within a project.
- **BMG / BFN Binary Reading in Project Mode**: Project block loading now reads `.bmg`, `.bfn`, `.arc`, and `.rarc` files as raw binary (`bytes`) instead of text, matching the expected input format for binary-aware plugins (e.g., `zelda_bmg`).
- **Expanded File Dialogs**: All file selection dialogs (new project, import block, open original/changes file) now include filters for `*.arc`, `*.rarc`, `*.bfn`, and `*.bmg` formats in addition to existing `*.json` and `*.txt` filters.

### Fixed
- **Settings dialog path fields locked in project mode**: The "Original File Path" and "Changes File Path" fields in the Settings dialog are now read-only (with tooltip explanation) whenever a project is active. Previously these fields showed stale standalone-mode paths and could cause confusion or overwrite project-managed paths on save.
- **Project path initialization when data is empty**: `data_store.json_path` and `data_store.edited_json_path` are now initialized from the first project block regardless of whether any data was actually parsed. This ensures the status bar shows correct paths even when all blocks are missing/empty.

## [0.2.53] - 2026-05-20

### Added
- **ARC Archives Support (.arc)**: Added full support for ARC/RARC archives within projects.
- **Automated Extraction and Packing**: Integrated tools `ArcExtract.exe` and `ArcPack.exe` to handle transparent extraction of archives into `.extracted/` workspace folder on project load, and automated packing back into destination `.arc` files upon saving edits.
- **Archive Visual Folder Representation**: Archive folders are now clearly distinguished in the block tree widget using the `SP_DirLinkIcon` icon.
- **Extracted Path Routing**: Updated file path resolving in `ProjectManager` and `DataStateProcessor` to correctly route `.extracted/` virtual paths within the project directory.

## [0.2.49] - 2026-03-25

### Added
- Unified Review Dialog Architecture: Created `BaseTextReviewDialog` to consolidate shared UI logic (layout, navigation, zebra striping).
- Dual-column line numbering in Review Dialogs (Global String Index + Relative Subline Index).
- Independent zebra striping for dual columns in the line number area.
- Font-aware dynamic column splitting in the line number area to prevent overlaps during zoom.
- Restored visual string separators (horizontal lines) in the unified review window.

### Fixed
- Visual regressions in the spellcheck dialog following the refactoring.
- Line number area margin issues and overlapping elements during font scaling/zoom.
- Corrected NameError and indentation issues in the shared editor paint logic.

## [0.2.48] - 2026-03-24

### ⚡ Improved
- **High-Performance Spellchecker**: Eliminated severe UI lag during text entry. The spellchecker now uses a synchronous, cache-backed `lookup` for immediate feedback while offloading expensive suggestion generation to a non-blocking background `QThread`.
- **Eliminated Redundant Rehighlighting**: Removed document-wide `rehighlight()` calls from the real-time UI update cycle. The syntax highlighter now relies on Qt's native incremental block updates, drastically reducing CPU load during typing.
- **Optimized Background Prefetching**: Disabled automatic background prefetching for the entire document, which was previously causing GIL (Global Interpreter Lock) congestion and UI stuttering. Suggestions are now fetched on-demand for the active word.
- **Non-Blocking Context Menus**: The editor context menu now displays a "Loading suggestions..." state while the background worker processes the request, ensuring the UI remains responsive.

### 🐛 Fixed
- **GIL Congestion**: Fixed a performance regression introduced in `v0.2.23` where high-frequency background `suggest` calls were blocking the main UI thread's event loop.
- **Syntax Highlighter Stability**: Resolved an `AttributeError` in the highlighter by correctly mapping removed prefetch methods to the new asynchronous worker architecture.

## [0.2.47] - 2026-03-24

### 🐛 Fixed
- **Critical Recursion Error**: Resolved a persistent `RecursionError` that occurred when clicking on rows or editing text. The root cause was identified as a circular dependency in the UI update cycle where `is_programmatically_changing_text` flag was prematurely reset, allowing Qt signals to re-trigger updates recursively.
- **UI Update Stability**: Implemented a robust reentrancy guard (`_in_update_text_views`) in the `UIUpdater` to prevent recursive calls during text view synchronization.
- **Highlight Manager Optimization**: Added state tracking (`_last_active_line_block`, `_last_linked_cursor_params`) to `TextHighlightManager` to skip redundant highlight applications when cursor state hasn't changed.
- **Paint Event Safety**: Removed heavy highlight calculation logic from the `paintEvent` of the editor, moving it to logical update points to prevent recursive repaint loops.
- **Line Number Area Fix**: Removed redundant `setViewportMargins` calls from the `updateRequest` handler, which were triggering constant layout recalculations in certain UI states.

### ⚡ Improved
- **Highlighting Logic**: Moved width-exceed and problem highlights to the `PreviewUpdater`'s logic layer, ensuring they are only computed when data actually changes.
- **Regression Testing**: Added a comprehensive suite of tests in `tests/test_components/test_text_highlight_manager_recursion.py` specifically designed to detect and prevent UI update recursion.

## [0.2.46] - 2026-03-23

### 🚀 Added
- **Multi-Font Width Analysis**: The "Calculate Line Widths" tool now computes results for all available font maps simultaneously in a background process.
- **Virtual Block Analysis**: Added dedicated support for calculating line widths for virtual blocks (categories), allowing for focused analysis of specific sub-segments.
- **Instant Font Switching**: Implemented a `QStackedWidget` based UI for the analysis dialog, ensuring zero-latency switching between different font reports.

### 🐛 Fixed
- **Width Analysis UI Restoration**: Restored the visual bar chart reports in the "Original Text Width Analysis" and "Calculate Line Widths" tools after they were missing in previous dev versions.
- **Application Hangups**: Moved the potentially slow width calculation logic to a dedicated `WidthCalculationWorker` thread, preventing the main UI from freezing during large analysis tasks.
- **Progress Visibility**: Added a modal progress dialog for width calculations with accurate percentage tracking linked to the background worker.

### ⚡ Improved
- **Optimized Text Processing**: Integrated a background cache for tag removal and subline splitting, drastically reducing redundant computations during multi-font analysis.
- **Pre-sorted Analysis Reports**: The background worker now pre-sorts the "Top 100" widest entries for every font, eliminating UI-thread sorting bottlenecks.


## [0.2.39] - 2026-03-22

### 🚀 Added
- **Visual Selection Highlighting**: Improved UI feedback when strings are found via search, ensuring matches are clearly visible and correctly highlighted.

### 🐛 Fixed
- **Virtual Block Inline Renaming**: Fixed a critical issue where renaming virtual blocks (categories) within the tree widget would fail with an "editing failed" error or accidentally rename the parent physical block.
- **Qt Role Synchronization**: Resolved a bug where problem counts and technical metadata were appearing inside the inline editor field during renaming due to native Qt role behavior.
- **Fuzzy Search Highlighting**: Fixed an issue where fuzzy search matches were not highlighted with the correct length, especially when the matched word form differed from the search query.
- **Search Navigation Accuracy**: Improved search result navigation and fixed button order (Prev/Next) for a more conventional user experience.
- **Search Term Normalization**: Fixed accuracy issues with search terms containing special characters (like `+`).

### ⚡ Improved
- **Deployment Workflow**: Enhanced the automated release process to include automatic GitHub Release creation using the `gh` CLI.

## [0.2.38] - 2026-03-22

### 🚀 Added
- **Multi-variation Glossary Support**: Added support for multiple translation variations for a single glossary term, separated by semicolons (`;`). Both single-word and multi-word variations are perfectly handled with Slavic inflection support.

## [0.2.37] - 2026-03-22

### ⚡ Improved
- **Glossary Tooltip Responsiveness**: Improved tooltip registration in the translation window. Tooltips now correctly refresh their position when moving between lines of a multi-line glossary term, providing a much smoother user experience.

## [0.2.36] - 2026-03-22

### 🐛 Fixed
- **Translation Glossary Tooltips**: Fixed an issue where glossary tooltips in the translation window were using absolute document coordinates instead of relative block coordinates, causing incorrect hover detection.

## [0.2.35] - 2026-03-22

### 🐛 Fixed
- **Multi-line Glossary in Translation**: Fixed a bug where glossary terms split across multiple lines were not highlighted in the translation window. The `JsonTagHighlighter` now builds a document-wide cache for translation matches, mirroring the robust logic used for original text.
- **Cache Invalidation**: Fixed a generic issue where glossary highlights might not refresh immediately after some text changes.

## [0.2.34] - 2026-03-22

### ⚡ Improved
- **Aho-Corasick Glossary Matching**: Integrated `pyahocorasick` for lightning-fast glossary term detection.
- **Optimized Project Scan**: Project-wide glossary indexing (occurrence scan) now uses Aho-Corasick, providing a 10-100x speedup for large datasets.
- **Hybrid Matching Architecture**: Maintained regex fallback for complex cases (terms with inline tags or multiple spaces), ensuring 100% accuracy while gaining maximum performance for exact matches.

## [0.2.33] - 2026-03-22

### ⚡ Improved
- **Persistent Spellchecker Cache**: Implemented disk-based caching for spellcheck results. This dramatically reduces CPU load during text editing and block switching by avoiding redundant calls to the slow pure-Python `spylls` library.
- **Spellchecker Manager Cleanup**: Fixed indentation and cleaned up internal state management during dictionary reloads.

## [0.2.32] - 2026-03-22

### 🐛 Fixed
- **Tooltip Logic Restoration**: Fixed a critical issue where tooltips for warnings and unsaved changes were missing in editor and translation windows. The logic was updated to correctly read from `AppDataStore`.
- **Robust Tooltip Testing**: Implemented a new testing suite using real `QMainWindow` hierarchies and `AppDataStore` to prevent future regressions in tooltip data access.

## [0.2.31] - 2026-03-22

### 🐛 Fixed
- **Line Number Display Restoration**: Resolved an `AttributeError` that caused line numbers and warning indicators to disappear. Corrected property access to use `data_store`.
- **Warning Indicator Painting**: Fixed the paint logic for line number areas to correctly visualize pixel-width warnings in all editor types.

## [0.2.29] - 2026-03-22

### ⚡ Improved
- **MainWindow Clean Refactoring**: Removed 20+ legacy property stubs from `MainWindow`, fully decoupling UI from the data layer (`AppDataStore`).
- **Data Access Standardization**: Standardized how all handlers and components access core application state, ensuring consistency and testability.

## [0.2.28] - 2026-03-22

### 🚀 Added
- **Glossary Translation Bridge**: Implemented intelligent glossary highlighting for the translation field. It uses a "stemming" algorithm tailored for Slavic languages (Ukrainian, etc.) to match inflected forms like "Меча" or "Мечем" from the base term "Меч".
- **Translation Field Tooltips**: Hovering over underlined glossary terms in the translation field now displays a tooltip with the original term, its translation, and dictionary notes.
- **Context Menu for Translations**: The translation editor now supports glossary-specific context menu actions ("Jump to Glossary", etc.) for highlighted terms.

### 🐛 Fixed
- **Localized Spellcheck for Virtual Blocks**: The spellchecker now correctly targets only the strings contained within a selected virtual block (category) instead of checking the entire parent file.
- **Spellcheck Underline Persistence**: Fixed a UI bug where red zig-zag underlines remained visible after a word was added to the dictionary.
- **GlossaryManager Stability**: Resolved a `NameError` and fixed incorrect regex generation for multi-word glossary terms.

### ⚡ Improved
- **Organic Documentation standard**: Documentation flow has been streamlined across `README.md` and `GEMINI.md`, removing redundant "New in..." sections in favor of integrated feature descriptions.

## [0.2.23] - 2026-03-22

### 🚀 Added
- **Visual Cloud Indicators for Virtual Blocks**: A small "cloud" icon overlay has been added to virtual folders (categories) in the project tree to clearly distinguish them from physical blocks.

### 🐛 Fixed
- **Subline Asterisk Persistence**: Resolved an issue where the modified indicator (asterisk) on sublines was lost upon navigating away and back to the edited string.
- **Asterisk Propagation**: Fixed a bug where unsaved changes in blocks were not propagating the asterisk indicator upwards to their parent virtual folders in the project tree.
- **Virtual Block Tooltips**: Virtual blocks now display their own specific error counts and accurate tooltips sequentially, rather than improperly inheriting them from their parent block.
- **Mouse Event Attribute Error**: Cleaned up residual spellchecker logic to prevent `AttributeError` caused by a non-existent debounced timer when moving the cursor.

### ⚡ Improved
- **Global Spellchecker Prefetching**: Spellcheck suggestions are now prefetched globally via the `SyntaxHighlighter` upon line load rather than cursor movement, drastically improving context menu opening speed.

## [0.2.17] - 2026-03-22

### Fixed
- **Glossary Highlighting Trigger**: Fixed a critical issue where glossary terms were not highlighted until the glossary window was manually opened. Term highlighting is now triggered correctly upon project load.
- **UI Initialization Stability**: Added guard clauses to `UIUpdater` and `JsonTagHighlighter` to prevent `AttributeError` crashes during early application startup.
- **Settings Reloading Leak**: Fixed a memory/logic leak where project settings were not fully reset when switching projects.

### Added
- **Plugin-Specific Context Menus**: Unique context menu tags per plugin now ensure that game-specific markers and formatting options don't leak between different project types.

### Improved
- **High-Performance Glossary Matching**: Implemented first-word pre-filter indexing in `GlossaryManager`, drastically reducing analysis time for large text blocks.
- **Optimized Width Calculation**: Integrated a Trie-based character width calculator for faster pixel-perfect rendering in the editor.
- **Responsive Syntax Highlighter**: Replaced ad-hoc regex compilation with pre-compiled patterns and optimized hit detection.
- **Spellchecker Responsiveness**: Added in-memory caching for spellchecker suggestions and dictionary data.

## [0.2.11] - 2026-03-22

### Added
- **Comprehensive Testing Suite**: over 600 verified unit tests covering core business logic, handlers, and UI components.
- **Testing Documentation**: Added instructions for running tests and generating coverage reports to `README.md`.

### Improved
- **Clean Test Environment**: Removed 2000+ auto-generated stub tests to ensure a 100% green and meaningful test suite.
- **UIUpdater Reliability**: Fixed critical synchronization issues and reached 79% test coverage for the UI update engine.
- **Unit Test Integrity**: Stabilized tests for `TranslationHandler`, `TextOperationHandler`, and `ProjectManager`.

### Fixed
- **Highlight Synchronization**: Resolved issues where UI highlights wouldn't align correctly with the text cursor after certain bulk operations.

## [0.2.10] - 2026-03-18

### Fixed
- **Dynamic Space Visualization**: Spaces are now correctly replaced with dots (·) only for leading, trailing, or multiple consecutive spaces, updating dynamically as you type.
- **Syntax Highlighting Stability**: Fixed an issue where tags would lose their color during space-to-dot conversion by removing redundant manual rehighlighting.
- **Granular Modification Indicators**: Asterisks (*) next to line numbers now only appear for sublines that actually differ from the saved version.
- **Smart Undo/Redo**: Modification stars now correctly disappear when a change is undone and the text returns to its original saved state.

### Improved
- **Code Internationalization**: Translated several internal Python comments from Ukrainian to English to maintain project standards.

## [0.2.6] - 2026-03-18

### Improved
- **GlossaryHandler Decomposition**: Reduced `glossary_handler.py` from 1278 to 917 lines (−28%) by extracting two modules:
  - `components/glossary_edit_dialog.py` (122 lines) — standalone `GlossaryEditDialog` UI component (previously private `_EditEntryDialog` class embedded in handler code)
  - `handlers/translation/glossary_prompt_manager.py` (233 lines) — `GlossaryPromptManager` class handling all prompt file I/O, caching, and glossary highlighting
- **Cleaner Architecture**: `GlossaryHandler` now acts as a facade — entry CRUD and occurrence-update AI logic remain, but prompt management is fully delegated to `GlossaryPromptManager`


## [0.2.5] - 2026-03-17

### Fixed
- **Plugin Loading Standard**: Fixed a critical bug where flat list JSON files caused a `[DATA ERROR]` by standardizing `load_data_from_json_obj` in `BaseGameRules` to always return a block-based structure.
- **None Value Graceful Handling**: Updated `UIUpdater` to prevent literal "None" strings from appearing in original text views when data is absent.
- **Programmatic Interaction Blocking**: Added `AppState.LOADING_DATA` to the data loading context in `AppActionHandler` to correctly silence side-effect events.

### Improved
- **Plugin Architecture**: Cleaned up the `zelda_mc` plugin to leverage the standardized base loading logic.
- **Test Integrity**: Updated automated tests to reflect new data structure expectations.

## [0.2.4] - 2026-03-17

### Added
- **StateManager**: Unified state management to prevent recursive events and track long-running operations.
- **ProjectContext**: Initial implementation of a context hub to decouple handlers from `MainWindow` god-object.
- **Strict Type Hinting**: Added comprehensive type hints (including `Union[str, Path]`) to `ProjectManager` and all Handler classes.
- **Pathlib Standardization**: Replaced `os.path` calls with `pathlib.Path` across core modules and handlers for better cross-platform reliability.

### Improved
- **MainWindow Decomposition**: Refactored `MainWindow.__init__` into specialized initialization methods.
- **Dead Code Pruning**: Removed 34+ unused boolean flags and state enums from `MainWindow` and `StateManager`.
- **Exception Safety**: Replaced manual state flag setting with context managers (`with state.enter(...)`) in `AppActionHandler`.
- **Test Coverage Verification**: Verified all changes with 135+ automated tests passing.

## [0.2.3] - 2026-03-17

### Added
- Automated deployment system (scripts/deploy.py)
- Project renaming to Picoripi (v0.2.3)

### Fixed
- Virtual environment path issues after directory move

### Improvements
- SettingsManager and UI setup decomposition
- Documentation updates (README.md, GEMINI.md)


## [0.2.1] - 2026-03-17

### Added
- **Revert to Original (Strings)**: Added the ability to revert individual strings or a selection of strings in the preview editor back to the original source text. Includes a confirmation dialog for safety.
- **Revert to Original (Blocks)**: Added a "Revert to Original" option in the block list (tree view) context menu to restore all translations for entire blocks.
- **Enhanced UI Icons**: Added visual icons to context menus for all major actions (AI Translation, Spellcheck, Moving to categories, Font/Width settings, and Reverting).
- **App Versioning**: The application version is now tracked in `utils/constants.py` and displayed in the main window title.
- **Unified Revert Logic**: Reverting now always pulls the actual source text (from the left panel), effectively allowing users to use dte original text as a translation template.

### Fixed
- **UI Refresh Consistency**: Fixed a bug where the preview text wouldn't update after an AI translation or a Revert operation until switching blocks.
- **Revert Button Logic**: Fixed the "Revert String" button in the editable panel header to correctly capture the current string index.
- **Selection State Persistence**: Improved handling of selection states after UI refreshes.

### Improvements
- Added status bar feedback for revert operations.
- Updated documentation (README.md, GEMINI.md) with latest features.
- Refined lambda captures in event handlers for more robust UI interactions.
