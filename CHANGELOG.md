All notable changes to the **Picoripi** project will be documented in this file.

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
  - Implemented instant focus setting (`setFocus()`) in `mousePressEvent` in [mouse_handlers.py](file:///d:/git/dev/Picoripi/components/editor/mouse_handlers.py) to resolve async focus transfer latency when clicking from the translation editor.
  - Optimized focus checks in `handle_preview_selection_changed` in [list_selection_handler.py](file:///d:/git/dev/Picoripi/handlers/list_selection_handler.py) to perform `hasFocus()` verification only on native Qt selection updates, skipping it entirely for custom selection signals.
  - Protected multi-selection state in `set_selected_lines` in [line_numbered_text_edit.py](file:///d:/git/dev/Picoripi/components/editor/line_numbered_text_edit.py) from being programmatically overwritten by lazy-loading timer blocks or background view updates, ignoring single line selection events if they are already part of an active multi-selection.

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
