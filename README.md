# Picoripi v0.2.38

A PyQt5-based translation workbench designed for simple, visual, and convenient translation of any texts, especially optimized for cases with strict length and formatting constraints. While it includes robust support for retro game localization, the tool is a versatile environment for any structured translation task.



## Features

### Project Management
- Create, load, and save `.uiproj` projects that encapsulate all files and settings for a translation effort.
- Organize strings into **virtual folders (categories)** for logical grouping of translated texts.
- **Visual Status Tracking**: Unsaved changes propagate via clear asterisk (*) indicators up the project tree. Virtual folders display their own specialized error counts and custom cloud icons for easy identification.
- Automatic synchronization of local files with project data during work.
- Move files or individual text blocks between categories with drag-and-drop support.

### Advanced Text Editing
- Specialized multi-line editor (`LineNumberedTextEdit`) that calculates **pixel-perfect width** of every character based on game-specific fonts.
- Visual feedback (red and yellow markers) for text that exceeds the game's displayable width limit.
- Syntax highlighting for game control codes and tags (e.g., `{Color:Red}`, `[PLAYER]`, `[L-Stick]`).
- Convenient insertion of control codes (button icons) through a visual interface and context menus.
- **Revert to Original**: Quickly restore original text for individual lines or entire blocks with full undo support.

### Plugin System
- Game-specific logic handled by a robust plugin system in the `plugins/` directory.
- Each plugin defines its own rules for text parsing, tag handling, font metrics, and problem analysis.
- Custom font maps (`font_map.json`) for pixel-perfect character width calculation.
- Currently supported games: **Zelda: Minish Cap**, **Zelda: The Wind Waker**, **Pokemon FireRed**, **Plain Text** (generic).

### AI-Assisted Translation
- Integration with **OpenAI**, **Google Gemini**, and **DeepL** directly in the interface.
- Built-in **AI Chat** window for interacting with AI within the development environment.
- Automatic batch translation of glossary terms or specific phrases while preserving game context.
- **Translation Variations**: Generate creative alternative translations for overly long sentences.
- Configurable AI prompts for fine-tuning translation quality.

### Glossary Management
- Intelligent recognition and highlighting of glossary terms throughout the entire text using high-performance **Aho-Corasick** algorithm.
- **Translation Glossary Bridge**: Automatic highlighting of glossary terms in the translation field, now supporting **multi-line matching** and **multiple translation variations** (separated by `;`).
- **Slavic Morphology Support**: Intelligent matching of inflected word forms (like "Меча", "Мечем") for Slavic languages using localized stemming.
- **Interactive Tooltips**: Hovering over terms in either editor shows a tooltip with original/translation and dictionary notes. Responsive tooltips correctly track position even for multi-line terms.
- Quick access to notes and contextual explanations for specific terms.
- Full CRUD operations: create, edit, search, and delete glossary entries.
- **AI-powered glossary fill**: Automatically suggest translations for glossary terms using AI.
- **Occurrence update**: Batch-update all occurrences of a glossary term across the project.

### Integrated Spellchecker
- Built-in Hunspell spellchecking via the `spylls` library.
- **High-Performance Caching**: Uses both in-memory and **persistent disk-based caching** (`spell_cache.json`) to skip redundant checks for known words, ensuring smooth UI performance even with large dictionaries.
- **Global Background Prefetching**: Dictionaries and suggestions are loaded entirely in the background, ensuring instant context menu suggestions without UI freezes.
- Underlines errors and provides quick replacement suggestions from the context menu.
- Built-in dictionary manager: download required languages directly from the app.
- Add game-specific slang to personal or project-level custom dictionaries.

### Analysis, Navigation & Safety
- **Analysis Tool**: Histograms and visualizations for text sizes and problem counts.
- **Undo / Redo**: Comprehensive undo system covering text edits, folder structure changes, reverts, and even tree navigation.
- **Global Search**: Project-wide search panel with fuzzy matching support.
- **Issue Scan**: Scan all blocks for width violations, tag errors, and other problems.
- **Text Autofix**: Automatic correction of common text issues (short lines, width exceeded, empty sublines, spacing around tags).

## Visual Problem Markers

The application uses colored markers in the line numbers area to indicate structural or length issues in the text.
Some markers might be rendered at **half-height**, which visually signifies that the problem is not critical and relates to an empty line meant for spacing.

### Default Plugin Warning Markers
- **Red (Width Exceeded)**: The subline is too wide for the in-game text box bounds.
- **Green (Short Line)**: The subline is too short — there is enough space to fit the first word of the following line.
- **Orange (Empty Subline)**: An entirely empty line (from consecutive newlines) that might waste text box space.
- **Blue (Single Word Subline)**: The subline consists of only one word, which may look awkward in-game.
- **Yellow (Tag Warning)**: A game control code tag is unknown, misspelled, or lacks a closing bracket.

### Plugin Customization
All labels and descriptions for markers are defined in each plugin's `config.py`:
- **`PROBLEM_DEFINITIONS`**: Maps problem IDs to names, descriptions, colors, and priorities.
- **`COLOR_MARKER_DEFINITIONS`**: Configurable manual markers (red, green, blue) with custom descriptions.

Descriptions from these dictionaries appear as **tooltips** throughout the application.

## Setup

### 1. Prerequisites

- Python 3.14.0 or higher
- pip (Python package manager)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

The application supports AI-powered translation using OpenAI and Google Gemini. To use these features:

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your API keys**:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   DEEPL_API_KEY=                             # optional
   FONT_TOOL_OPENAI_API_KEY=                  # optional, falls back to OPENAI_API_KEY
   ```

3. **Important**: The `.env` file is excluded from git to protect your API keys.

### 4. Run the Application

#### Windows
```bash
run.bat
```

The `run.bat` script automatically creates a virtual environment, installs dependencies, and launches the application.

#### Manual Start
```bash
python main.py
```

### Running Tests

The project uses `pytest` for unit testing with 600+ tests.

#### Run All Tests
```bash
# Windows
set PYTHONPATH=.
.\venv\Scripts\python.exe -m pytest tests/

# Linux/macOS
export PYTHONPATH=.
python -m pytest tests/
```

#### Run with Coverage Report
```bash
.\venv\Scripts\python.exe -m pytest --cov=core --cov=handlers --cov=ui tests/
```

## Project Structure

```
Picoripi/
├── main.py                     # Application entry point (MainWindow orchestrator)
├── core/                       # Core business logic and data models
│   ├── data_state_processor.py # Central data access & mutation layer
│   ├── data_store.py           # AppDataStore — shared state container
│   ├── data_manager.py         # JSON/text file I/O
│   ├── project_manager.py      # .uiproj project lifecycle
│   ├── project_models.py       # Project, Block, Category dataclasses
│   ├── glossary_manager.py     # Glossary parsing, matching, CRUD
│   ├── spellchecker_manager.py # Hunspell integration via spylls
│   ├── state_manager.py        # StateManager with enum-based AppState
│   ├── undo_manager.py         # Multi-level undo/redo with snapshots
│   ├── context.py              # ProjectContext (Protocol) for decoupling
│   ├── settings_manager.py     # Facade for settings subsystem
│   └── settings/               # Decomposed settings modules
│       ├── global_settings.py
│       ├── plugin_settings.py
│       ├── font_map_loader.py
│       ├── recent_projects_manager.py
│       └── session_state_manager.py
├── handlers/                   # Business logic handlers
│   ├── base_handler.py         # Base class with ctx/data_processor/ui_updater
│   ├── app_action_handler.py   # Global app actions (export, import, open)
│   ├── project_action_handler.py # Project CRUD, block management
│   ├── list_selection_handler.py # Block/string selection logic
│   ├── text_operation_handler.py # Text editing, paste, revert
│   ├── text_analysis_handler.py  # Width/length analysis
│   ├── text_autofix_logic.py     # Auto-correction engine
│   ├── search_handler.py         # Global search with fuzzy matching
│   ├── issue_scan_handler.py     # Project-wide issue scanning
│   ├── string_settings_handler.py # Per-string settings
│   ├── ai_chat_handler.py        # AI chat window
│   ├── translation_handler.py    # Translation facade
│   └── translation/              # AI translation subsystem
│       ├── ai_lifecycle_manager.py
│       ├── ai_prompt_composer.py
│       ├── ai_worker.py
│       ├── glossary_handler.py
│       ├── glossary_builder_handler.py
│       ├── glossary_occurrence_updater.py
│       ├── glossary_prompt_manager.py
│       └── translation_ui_handler.py
├── ui/                         # UI management
│   ├── ui_updater.py           # Central UI refresh coordinator
│   ├── ui_setup.py             # UI initialization entry point
│   ├── settings_dialog.py      # Application settings dialog
│   ├── themes.py               # Theme management
│   ├── builders/               # UI construction (MenuBar, Toolbar, Layout, StatusBar)
│   ├── updaters/               # Decomposed UI updaters (block list, preview, etc.)
│   └── main_window/            # MainWindow event handling & actions
├── components/                 # Reusable PyQt5 widgets
├── plugins/                    # Game-specific plugins
│   ├── base_game_rules.py      # Abstract base class for all plugins
│   ├── common/                 # Shared markers and utilities
│   ├── zelda_mc/               # Zelda: Minish Cap
│   ├── zelda_ww/               # Zelda: The Wind Waker
│   ├── pokemon_fr/             # Pokemon FireRed
│   └── plain_text/             # Generic plain text
├── utils/                      # Utilities, constants, logging
├── tests/                      # 600+ unit tests (pytest)
├── .env                        # API keys (not in git)
├── .env.example                # Template for .env
└── requirements.txt            # Python dependencies
```

## Plugins and Extensibility

The workbench is highly modular. Each plugin in the `plugins/` directory is a self-contained unit that defines:
1. **Rules (`rules.py`)**: Inherits from `BaseGameRules`. Manages tag parsing, data loading/saving, pasted text processing, problem analysis, and autofix rules.
2. **Configuration (`config.py`)**: Defines constants, problem types, marker descriptions, and enter characters.
3. **Fonts (`fonts/` directory)**: Contains JSON font maps for pixel-perfect width calculations.
4. **Tag Logic (`tag_manager.py`, `tag_logic.py`)**: Handles game-specific control codes and formatting.

To add a new game:
1. Create a new directory in `plugins/`.
2. Implement your rules by inheriting from `BaseGameRules`.
3. Define your font maps and control codes in `config.py`.

## Logs

Application logs are written to `app_debug.txt` in the project root directory.
Logs use `RotatingFileHandler` with a 2 MB limit and 5 backup files.

## License

[Add your license here]
