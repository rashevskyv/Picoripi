# The "Picoripi" (v0.3.066-dev)


This document provides a comprehensive overview of the "Picoripi" project to be used as a working context for Gemini.

## AI Development Manifesto (Mandatory)

Picoripi is largely AI-developed, so every AI agent must behave like a careful maintainer, not like a one-shot code generator. This section is the required operating contract for AI work in this repository. The extended version lives in `docs/AI_DEVELOPMENT_MANIFESTO.md`, but the rules below are authoritative even when that file is not opened.

### Core Rules

- Protect user work first: always inspect `git status --short`, never revert unrelated changes, and treat unknown modified files as user work.
- Prefer small, verified changes over broad rewrites. Decompose large modules only around stable contracts and tests.
- Read nearby code before editing. Follow existing architecture, naming, Qt signal patterns, and helper APIs.
- Keep product code free of test-specific checks such as `Mock`, `MagicMock`, `_mock_self`, `_mock_name`, or string checks for mock types.
- Preserve backwards compatibility for projects, sessions, plugins, glossary data, and user translation files unless a migration path is implemented and tested.
- Do not remove old behavior unless the replacement is implemented, tested, documented, and compatible with existing workflows.

### Required AI Workflow

1. Inspect the current state with `git status --short`.
2. Read the relevant local code and tests before forming the implementation plan.
3. Identify the ownership boundary: `core/`, `handlers/`, `ui/`, `components/`, `plugins/`, `tests/`, or docs.
4. Implement the narrowest complete fix.
5. Add or update tests for changed behavior.
6. Update documentation when behavior, test policy, plugin contracts, release process, or user workflows change.
7. Run relevant parallel tests and `git diff --check`.
8. Report what changed, what was verified, and what risk remains.

### Architecture Rules

- `AppDataStore` owns shared state; `DataStateProcessor` owns data mutation, save, revert, and session operations (delegated to `SessionManager`, `RevertManager`, and `SetCalculator` inside `core/data_processor/`).
- Handlers should use processor/context APIs instead of directly mutating data arrays or UI internals.
- `MainWindow` is an orchestrator. New behavior should usually live in a handler, service, updater, component, or plugin.
- UI updaters should coordinate rendering, not own business rules.
- Plugin-specific behavior belongs in plugins. Shared plugin rules belong in `plugins/common/problem_rules/`.
- New plugin work should start from `plugins/default_plugin/` and update `docs/PLUGIN_AUTHORING_GUIDE.md` if contracts change.

### PyQt And Performance Rules

- Never add synchronous disk, network, AI, SQLite, archive parsing, or heavy computation to the UI thread.
- Use `QThread`, cancellable timers, chunking, or time-slicing for long work.
- Avoid `QCoreApplication.processEvents()` in production paths unless the reason is documented and safer alternatives were rejected.
- Every worker/thread pair needs clear ownership, cooperative cancellation, bounded shutdown, and cleanup.
- Avoid static `QTimer.singleShot(...)` for deferred work that can outlive a project, dialog, or owner; prefer instance-owned cancellable timers.
- Cache only when invalidation is clear. Hot paths include preview rendering, filtering, block tree updates, width calculation, glossary matching, spellchecking, archive compression, session persistence, and MemePalace mapping.

### Testing Rules

- Run tests in parallel by default.
- For broad verification, use:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\test_all.ps1
  ```
- For the default suite, use:
  ```powershell
  $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/
  ```
- Run performance tests explicitly because they are excluded from the default pytest lane:
  ```powershell
  $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py
  ```
- For pure logic, add focused unit tests. For workers, add real `pytest-qt` lifecycle smoke tests with start, signal, cancel/finish, and cleanup.
- Avoid fixed sleeps when `qtbot.waitSignal` or `qtbot.waitUntil` can express the condition.
- Do not monkeypatch global `Mock`, `MagicMock`, Python builtins, or Qt classes globally.
- Use explicit fake objects for domain contracts; use `MagicMock` only where call observation is the point.
- Product code must never import or branch on `unittest.mock`.

### Documentation And Release Rules

- Documentation is part of done.
- Update `README.md` for top-level commands and documentation maps.
- Update `GEMINI.md` when AI operating rules, architecture guidance, or default commands change.
- Update `AUDIT.md` for audit findings, completed improvements, active follow-ups, and plans.
- Update `docs/FEATURE_REFERENCE.md` for important user-facing behavior.
- Update `docs/TESTING_STRATEGY_AND_AUDIT.md` for test infrastructure or policy changes.
- Update `docs/PLUGIN_AUTHORING_GUIDE.md` and `plugins/default_plugin/` when plugin contracts change.
- When the user asks to commit or release, bump the version and update `utils/constants.py`, `README.md`, `GEMINI.md`, `AUDIT.md`, and `CHANGELOG.md`.

### Final AI Self-Checklist

- Did I preserve unrelated user changes?
- Did I make the smallest complete change?
- Did I keep product code free of test-only hacks?
- Did I add or update the right tests?
- Did I run relevant parallel tests?
- Did I update the relevant docs?
- Did I run `git diff --check`?
- Did I explain remaining risk honestly?

## Project Overview

The "Picoripi" (v0.3.066-dev) is a desktop application built with **Python** and **PyQt6**. Its primary purpose is to facilitate the simple, visual, and convenient translation of any texts, specifically optimized for cases with strict length and formatting constraints.


The application is designed to be highly versatile, with features tailored to handling various text constraints, such as character limits, pixel-perfect width calculations (using game-specific or custom fonts from a configurable fonts directory path), and custom control codes. While it excels at retro game localization, its core architecture is suitable for any structured translation project.

### Core Features

- **Project Management**: A fully project-based workflow. A "project" (`.uiproj` file) encapsulates all files and settings for a specific translation effort. Supports virtual "categories" (folders) for logical grouping, **robust inline renaming**, and persistent selection state.
- **Granular Saving Actions**: Supports partial saving of changes. Users can choose to save translation changes for specifically selected blocks or categories via the project tree's context menu, or save targeted lines (a single string or multiple selected lines) via the editor context menus.
- **Fault-Tolerant Session Autosaving**: Automatically serializes the complete state container (`AppDataStore`) in a human-readable durable JSON session file (`.picoripi_session.json`) alongside a binary crash recovery snapshot (`.picoripi_session`) using the `Pickle` protocol. Autosave operations use Pickle for debounced (2 seconds) quick writes. A robust JSON-based durable checkpoint is saved at application shutdown, periodically (every 5 minutes), and before long operations. During startup, the JSON session is preferred due to PyQt/Python version changes, with Pickle as a fallback. **Undo/Redo command stacks** are preserved in the session payload, maintaining full edit history across restarts.
- **Virtual Speakers Navigation**: Group dialogue lines dynamically by Speaker. Dialogue lines from any physical `.bmg` or `.json` blocks are gathered into a virtual `Speakers -> Speaker Name` node structure in the Blocks panel. Adding strings to these folders automatically assigns the corresponding speaker metadata to them. Supports direct selection and interactive input of speaker names via a combo box located above the translation editor, instantly updating speaker assignments and hot-reloading virtual folders.
- **Warning-Specific Preview Filtering**: Allows filtering the preview panel by specific warning categories. Adds a filter button (`Warnings: X / Y`, where X is the number of active warning filters and Y is the number of enabled warnings in Settings -> Detection) next to the preview layout toggles. Clicking the button opens a modal dialog (`WarningsFilterDialog`) with checkboxes and descriptive tooltips for each warning type, enabling users to isolate strings matching a subset of selected warnings or view all warnings if no specific filters are checked. If no warnings are selected, the preview is cleared.

- **Visual Feedback System**: Automatic file synchronization, clear problem counts and warning indicators across the project tree with **recursive asterisk propagation for unsaved changes**.
- **Plugin-Based Architecture**: Game-specific logic is handled by a robust plugin system located in the `plugins/` directory. Each plugin (e.g., `zelda_mc`, `zelda_ww`, `pokemon_fr`, `plain_text`) defines its own rules for text parsing, tag handling, font metrics for width calculation, problem analysis, and autofix behavior. Plugins inherit from `BaseGameRules` (`plugins/base_game_rules.py`).
- **Centralized Rule Engine**: Built on the `ProblemRule` interface and `ProblemRuleRegistry` registry located in `plugins/common/problem_rules/`. It provides a unified source of truth for both detecting and auto-correcting layout warnings. High-level adapters `GenericProblemAnalyzer` and `GenericTextFixer` delegate verification tasks to this common engine.
- **Archive Support**: Fully native, in-memory archive management. Automatically detects, parses, edits, and packs RARC and U8 archive containers (including Yaz0 compressed formats) directly in RAM. Eliminates the need for external executables like `ArcExtract.exe` or `ArcPack.exe` and prevents any disk space pollution.
- **AI-Assisted Translation**: Integrates with external AI services (OpenAI, Gemini, DeepL) for translation. Features include: batch translation, translation variations for long sentences, AI-powered glossary fill, glossary occurrence batch-update, a dedicated AI Chat window, and a split-view interactive translation comparison dialog with inline editing, version switching, and AI variation selection. The system uses configurable prompts (`AIPromptComposer`) and a full lifecycle manager (`AILifecycleManager`) for reliable async operations.
- **MemePalace Context Integration**: Fully chronological walkthrough timeline mapping utilizing an SQLite database. Maps flat game dialogue lines to dynamic walkthrough transcripts (such as parsed YouTube captions) and dynamically enriches translation models with visual action environment details and character relations. Features a non-blocking modeless Context Builder and an interactive Database Viewer.
- **Glossary System**: Full CRUD glossary management with intelligent, high-performance highlighting of glossary terms using the **Aho-Corasick** algorithm. Supports Slavic-friendly morphological matching, **multiple translation variations** (semicolon-separated), multi-line Bridge Highlighting, AI-powered term filling, batch occurrence updates, and interactive tooltips. Features a beautiful **dynamic tabbed interface** (`QTabWidget`) that divides terms into semantic categories, and an advanced **Organize via AI** dwo-stage workflow to dynamically classify flat glossary databases on disk and hot-reload tabs in real time.
- **Specialized UI Components**: Custom widgets like `LineNumberedTextEdit` that calculates pixel-perfect character widths using game-specific font maps, provides line numbers, shows visual warnings (colored markers) for text exceeding display limits, and provides contextual tooltips for glossary and issues.
- **Tag Management**: Recognizes and provides syntax highlighting for special in-game control codes (e.g., `{Color:Red}`, `[PLAYER]`, `[L-Stick]`).
- **Integrated Spellchecker**: Uses `spylls` (Hunspell implementation) for spellchecking with an **asynchronous background worker** for non-blocking suggestions and **persistent disk-based caching** for optimized performance. Supports custom dictionaries and glossary integration.
- **Analysis & Safety**: Built-in Analysis Tool for visualizing text sizes and problem counts with **multi-font support** and **instant font switching** using a stacked-view architecture. Features background processing via `WidthCalculationWorker` to prevent UI freezes. Project-wide Issue Scan for width violations and tag errors. Text Autofix engine for automatic correction of common problems. Supports relocation of control codes `{tab}` to the start of the next line and cleaning space after them. Implements a robust **Clean Text Analysis** spacing check (Missing Tag Spacing) that hides zero-width tags but preserves width-carrying tags (like `{tab}` and `{*}`), flagging missing spaces contextually and fixing them safely. Supported by a global `Ctrl+Q` toggle for tag visibility in editors.
- **Comprehensive Undo/Redo**: Multi-level undo system (`UndoManager`) that covers text edits, folder structure changes, block reverts, paste operations, and navigation history.
- **Global Search**: Project-wide search panel with **fuzzy matching**, case-sensitive/insensitive modes, and tagless search support. Features **precision highlighting** for fuzzy matches, even when the matched word form deviates from the query.
- **Advanced Navigation**: Efficient result cycling with ergonomic "Prev/Next" controls and automatic selection jumping.
- **Power-User Modifiers**: Rich set of modifier shortcuts (Ctrl+Click on AutoFix opens selective settings, Ctrl+Click on Translate edits prompt, Ctrl+Click on AI Variations appends instructions, Ctrl+Click on glossary words edits terms, and Ctrl+Click on bracket tags maps them using clipboard tags).

## Building and Running the Project

### 1. Setup

The project uses a Python virtual environment. The `run.bat` script automates its creation.

**Dependencies** are listed in `requirements.txt`. Key libraries include:
- `PyQt6`: The GUI framework.
- `requests`: For AI translation services.
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

The project uses `pytest` with 1281+ default-lane items plus a dedicated performance lane:
```bash
# Windows
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/

# With coverage
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto --cov=core --cov=handlers --cov=ui tests/
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
    -   `virtual_folder_handler.py`: Virtual folders navigation and selection.
    -   `category_handler.py`: Virtual category CRUD and block operations.
    -   `speaker_handler.py`: Virtual speakers dialog mapping, combo assignment, and string retention.
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
-   `components/`: Reusable PyQt6 widgets (text editors, tree widgets, dialogs, glossary edit dialog, toast notification, and `checkable_combobox.py` for warning filtering). Contains `block_properties_dialog.py` for displaying file metadata and `toast.py` for non-blocking notifications.
-   `plugins/`: Game-specific plugin modules:
    -   `base_game_rules.py`: Abstract base class for all plugins.
    -   `common/`: Shared markers and utilities (`markers.py`).
    -   `common/problem_rules/`: Shared Rule Engine logic (`base.py`, `registry.py`, `common_rules.py`).
    -   `zelda_mc/`, `zelda_ww/`, `pokemon_fr/`, `plain_text/`: Individual game plugins.
-   `tools/`: Helper utilities and embedded tools, including `bfn_editor/` (Nintendo Binary Font visual editor and compiler).
-   `utils/`: Utility functions (`utils.py`), constants (`constants.py`), syntax highlighter (`syntax_highlighter.py`), and logging (`logging_utils.py`).
-   `tests/`: 1281+ default-lane pytest items plus performance tests organized by module.

### Key Development Conventions

-   **State Management**: The application uses `StateManager` (`core/state_manager.py`) with `AppState` enum values (e.g., `LOADING_DATA`, `SAVING_DATA`, `ADJUSTING_CURSOR`). States are entered via context managers: `with self.state.enter(AppState.LOADING_DATA):`. This replaced the old system of 46+ boolean flags.
-   **Data Flow**: All data mutations go through `DataStateProcessor` ([core/data_state_processor.py](file:///d:/git/dev/Picoripi/core/data_state_processor.py)), which delegates session persistence, reverts, and set calculations to [core/data_processor/](file:///d:/git/dev/Picoripi/core/data_processor/) submodules. Direct access to `data`/`edited_data` arrays should be avoided — use the processor's methods instead.
-   **Delegation**: `MainWindow` delegates logic to handlers in `handlers/`. Each handler receives `ProjectContext`, `DataStateProcessor`, and `UIUpdater` via `BaseHandler`.
-   **Decoupling**: Handlers use `ProjectContext` (Protocol, defined in `core/context.py`) instead of direct `MainWindow` references, enabling unit testing with mocks.
-   **Logging**: All diagnostic output is managed by `utils/logging_utils.py` using `RotatingFileHandler` (2 MB limit, 5 backups). Written to `app_debug.txt`. Use `log_info()`, `log_warning()`, `log_error(msg, exc_info=True)` for logging.
-   **Plugin Interface**: `plugins/base_game_rules.py` defines the abstract base class. Plugins must implement: `load_data_from_json_obj`, `save_data_to_json_obj`, `get_enter_char`, `analyze_subline`, and optionally `autofix_data_string`, `process_pasted_segment`.
-   **Testing**: All tests use `pytest` with fixtures defined in `tests/conftest.py`. Mock-based unit tests for handlers use `unittest.mock.MagicMock` for `MainWindow` and Qt widgets. Prefer parallel local verification with `pytest -n auto` unless a specific serial Qt timing investigation is required.

Розмовляй та пиши волксру та плани лише українською

Весь текст в програмі має бути англійською мовою

Середовище виконання - powershell, то ж використовуй відповідні команди

Коли кажу коммітити - обов'язково піднімай версію. Обов'язково актуалізовуй файли аудиту, джемінай, рідмі та чейнджлог.
