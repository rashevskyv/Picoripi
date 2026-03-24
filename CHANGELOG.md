All notable changes to the **Picoripi** project will be documented in this file.

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
