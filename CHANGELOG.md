All notable changes to the **Picoripi** project will be documented in this file.

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
