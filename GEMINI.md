# --- START OF FILE GEMINI.md ---
# GEMINI.md - Project Context for Gemini

This document provides a comprehensive overview of the "Picoripi" project to be used as a working context for Gemini.

## Project Overview

The "Picoripi" (v0.2.50-dev) is a desktop application built with **Python** and **PyQt5**. Its primary purpose is to facilitate the simple, visual, and convenient translation of any texts, specifically optimized for cases with strict length and formatting constraints.

The application is designed to be highly versatile, with features tailored to handling various text constraints, such as character limits, pixel-perfect width calculations (using game-specific or custom fonts), and custom control codes. While it excels at retro game localization, its core architecture is suitable for any structured translation project.

### Core Features

- **Project Management**: A fully project-based workflow. A "project" (`.uiproj` file) encapsulates all files and settings for a specific translation effort. Supports virtual "categories" (folders) for logical grouping, **robust inline renaming**, and persistent selection state.
- **Visual Feedback System**: Automatic file synchronization, clear problem counts and warning indicators across the project tree with **recursive asterisk propagation for unsaved changes**.
- **Plugin-Based Architecture**: Game-specific logic is handled by a robust plugin system located in the `plugins/` directory. Each plugin (e.g., `zelda_mc`, `zelda_ww`, `pokemon_fr`, `plain_text`) defines its own rules for text parsing, tag handling, font metrics for width calculation, problem analysis, and autofix behavior. Plugins inherit from `BaseGameRules` (`plugins/base_game_rules.py`).
- **AI-Assisted Translation**: Integrates with external AI services (OpenAI, Gemini, DeepL) for translation. Features include: batch translation, translation variations for long sentences, AI-powered glossary fill, glossary occurrence batch-update, and a dedicated AI Chat window. The system uses configurable prompts (`AIPromptComposer`) and a full lifecycle manager (`AILifecycleManager`) for reliable async operations.
- **Glossary System**: Full CRUD glossary management with intelligent, high-performance highlighting of glossary terms using the **Aho-Corasick** algorithm. Supports Slavic-friendly morphological matching, **multiple translation variations** (semicolon-separated), multi-line Bridge Highlighting, AI-powered term filling, batch occurrence updates, and interactive tooltips.
- **Specialized UI Components**: Custom widgets like `LineNumberedTextEdit` that calculates pixel-perfect character widths using game-specific font maps, provides line numbers, shows visual warnings (colored markers) for text exceeding display limits, and provides contextual tooltips for glossary and issues.
- **Tag Management**: Recognizes and provides syntax highlighting for special in-game control codes (e.g., `{Color:Red}`, `[PLAYER]`, `[L-Stick]`).
- **Integrated Spellchecker**: Uses `spylls` (Hunspell implementation) for spellchecking with an **asynchronous background worker** for non-blocking suggestions and **persistent disk-based caching** for optimized performance. Supports custom dictionaries and glossary integration.
- **Analysis & Safety**: Built-in Analysis Tool for visualizing text sizes and problem counts with **multi-font support** and **instant font switching** using a stacked-view architecture. Features background processing via `WidthCalculationWorker` to prevent UI freezes. Project-wide Issue Scan for width violations and tag errors. Text Autofix engine for automatic correction of common problems.
- **Comprehensive Undo/Redo**: Multi-level undo system (`UndoManager`) that covers text edits, folder structure changes, block reverts, paste operations, and navigation history.
- **Global Search**: Project-wide search panel with **fuzzy matching**, case-sensitive/insensitive modes, and tagless search support. Features **precision highlighting** for fuzzy matches, even when the matched word form deviates from the query.
- **Advanced Navigation**: Efficient result cycling with ergonomic "Prev/Next" controls and automatic selection jumping.

## Building and Running the Project

### 1. Setup

The project uses a Python virtual environment. The `run.bat` script automates its creation.

**Dependencies** are listed in `requirements.txt`. Key libraries include:
- `PyQt5`: The GUI framework.
- `deep-translator`, `googletrans`, `playwright`: For AI translation services.
- `spylls`: For spellchecking.
- `markdown`: For parsing glossary files.

To install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration

API keys for AI services are required.
1.  Copy `.env.example` to `.env`.
2.  Fill in the necessary API keys in the `.env` file.

General application settings are stored in `settings.json`.

### 3. Running the Application

-   **On Windows:**
    ```bash
    run.bat
    ```
-   **On other platforms (or manually):**
    ```bash
    python main.py
    ```

### 4. Running Tests

The project uses `pytest` with 600+ unit tests:
```bash
# Windows
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest tests/

# With coverage
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest --cov=core --cov=handlers --cov=ui tests/
```

## Codebase Structure & Conventions

The project follows a well-organized, modular structure with clear separation of concerns.

### Directory Layout

-   `main.py`: Application entry point. Contains `MainWindow` — the central orchestrator that initializes all managers, handlers, and UI.
-   `core/`: Core business logic and data models:
    -   `data_state_processor.py`: Central data access and mutation layer. All reads/writes to block and string data go through this module.
    -   `data_store.py`: `AppDataStore` — the shared state container holding `data`, `edited_data`, `block_names`, `current_block_idx`, etc.
    -   `data_manager.py`: Low-level JSON/text file I/O (no UI dependencies).
    -   `project_manager.py`: `.uiproj` project lifecycle (create, load, save, sync, block management).
    -   `project_models.py`: Dataclasses for `Project`, `Block`, `Category`.
    -   `glossary_manager.py`: Glossary parsing (markdown tables), matching, CRUD, and occurrence indexing.
    -   `spellchecker_manager.py`: Hunspell integration via `spylls` with custom dictionary support.
    -   `state_manager.py`: `StateManager` with `AppState` enum — replaces the old boolean flag system with context managers (`with state.enter(AppState.LOADING):`).
    -   `undo_manager.py`: Multi-level undo/redo with deep-copy snapshots.
    -   `context.py`: `ProjectContext` (Protocol) for decoupling handlers from `MainWindow`.
    -   `settings_manager.py`: Facade for the `settings/` subsystem.
    -   `settings/`: Decomposed settings: `global_settings.py`, `plugin_settings.py`, `font_map_loader.py`, `recent_projects_manager.py`, `session_state_manager.py`.
-   `handlers/`: Specialized classes for specific functionality:
    -   `base_handler.py`: Base class providing `self.ctx`, `self.data_processor`, `self.ui_updater`.
    -   `app_action_handler.py`: Global app actions (file export/import, open, close).
    -   `project_action_handler.py`: Project-level CRUD and block management.
    -   `list_selection_handler.py`: Block/string selection logic and preview updates.
    -   `text_operation_handler.py`: Text editing, paste, revert, and modification tracking.
    -   `text_analysis_handler.py`: Width and length analysis.
    -   `text_autofix_logic.py`: Auto-correction engine (short lines, width exceeded, empty sublines, tag spacing).
    -   `search_handler.py`: Global search with fuzzy matching.
    -   `issue_scan_handler.py`: Project-wide issue scanning.
    -   `string_settings_handler.py`: Per-string width and display settings.
    -   `ai_chat_handler.py`: AI chat window handler.
    -   `translation_handler.py`: Translation facade coordinating the subsystem below.
    -   `translation/`: Decomposed AI translation subsystem:
        -   `ai_lifecycle_manager.py`: AI request lifecycle (queue, retry, cancellation).
        -   `ai_prompt_composer.py`: Prompt construction with glossary and context injection.
        -   `ai_worker.py`: QThread-based async AI execution.
        -   `glossary_handler.py`: Glossary UI and CRUD operations.
        -   `glossary_builder_handler.py`: AI-powered glossary term generation.
        -   `glossary_occurrence_updater.py`: Batch occurrence updates with AI.
        -   `glossary_prompt_manager.py`: Prompt file I/O and caching.
        -   `translation_ui_handler.py`: Translation progress UI and dialogs.
-   `ui/`: UI management:
    -   `ui_updater.py`: Central UI refresh coordinator — the largest UI module.
    -   `ui_setup.py`: UI initialization entry point.
    -   `settings_dialog.py`: Application settings dialog.
    -   `themes.py`: Theme management.
    -   `builders/`: UI construction modules (`layout_builder.py`, `menu_builder.py`, `toolbar_builder.py`, `statusbar_builder.py`).
    -   `updaters/`: Decomposed UI updaters: `block_list_updater.py`, `preview_updater.py`, `string_settings_updater.py`, `title_status_bar_updater.py`.
    -   `main_window/`: MainWindow event handling and actions.
-   `components/`: Reusable PyQt5 widgets (text editors, tree widgets, dialogs, glossary edit dialog).
-   `plugins/`: Game-specific plugin modules:
    -   `base_game_rules.py`: Abstract base class for all plugins.
    -   `common/`: Shared markers and utilities (`markers.py`).
    -   `zelda_mc/`, `zelda_ww/`, `pokemon_fr/`, `plain_text/`: Individual game plugins.
-   `utils/`: Utility functions (`utils.py`), constants (`constants.py`), syntax highlighter (`syntax_highlighter.py`), and logging (`logging_utils.py`).
-   `tests/`: 600+ unit tests organized by module (pytest).

### Key Development Conventions

-   **State Management**: The application uses `StateManager` (`core/state_manager.py`) with `AppState` enum values (e.g., `LOADING_DATA`, `SAVING_DATA`, `ADJUSTING_CURSOR`). States are entered via context managers: `with self.state.enter(AppState.LOADING_DATA):`. This replaced the old system of 46+ boolean flags.
-   **Data Flow**: All data mutations go through `DataStateProcessor` (`core/data_state_processor.py`). Direct access to `data`/`edited_data` arrays should be avoided — use the processor's methods instead.
-   **Delegation**: `MainWindow` delegates logic to handlers in `handlers/`. Each handler receives `ProjectContext`, `DataStateProcessor`, and `UIUpdater` via `BaseHandler`.
-   **Decoupling**: Handlers use `ProjectContext` (Protocol, defined in `core/context.py`) instead of direct `MainWindow` references, enabling unit testing with mocks.
-   **Logging**: All diagnostic output is managed by `utils/logging_utils.py` using `RotatingFileHandler` (2 MB limit, 5 backups). Written to `app_debug.txt`. Use `log_info()`, `log_warning()`, `log_error(msg, exc_info=True)` for logging.
-   **Plugin Interface**: `plugins/base_game_rules.py` defines the abstract base class. Plugins must implement: `load_data_from_json_obj`, `save_data_to_json_obj`, `get_enter_char`, `analyze_subline`, and optionally `autofix_data_string`, `process_pasted_segment`.
-   **Testing**: All tests use `pytest` with fixtures defined in `tests/conftest.py`. Mock-based unit tests for handlers use `unittest.mock.MagicMock` for `MainWindow` and Qt widgets.

Розмовляй та пиши волксру та плани kbit українською

Весь текст в програмі має бути англійською мовою

Середовище виконання - powershell, то ж використовуй відповідні команди 
