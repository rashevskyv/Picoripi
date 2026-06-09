# Picoripi v0.3.000
 
The **Picoripi** (v0.3.000) is a visual translation and localization workbench built with **Python** and **PyQt6**. It is designed for precise, visual, and highly convenient translation of texts with strict length and layout constraints. While initially built to excel at retro game localization (supporting complex Nintendo formats and custom tags), its core architecture is fully generalizable to any structured translation, alignment, or editing workflow.

---

## Key Features

### 1. Project Management & Workspace Navigation
- **Project-Based Workflow**: Creates, loads, and manages `.uiproj` projects encapsulating all translation files, virtual categories, and settings.
- **Virtual Folder Structure**: Organizes text blocks into nested virtual folders (categories) for logical narrative layout. Supports drag-and-drop file organization.
- **Granular Status & Propagation**: Unsaved changes propagate dynamically as asterisks (`*`) up the folder tree, with specialized error/warning counts on parent nodes.
- **Soft Shading & Progress Bars**:
  - **Translated Lines Shading**: Renders a soft, pastel-green background (`QColor(46, 139, 87, 40)`) under line numbers in translation editors and preview screens for translated strings, facilitating rapid document navigation.
  - **File Progress Bars**: Tree items render smooth, semi-transparent green progress bars (`QColor(46, 139, 87, 25)`) left-to-right beneath file names, proportional to the translation completion rate.
  - **Translatable String Detection**: Intelligently ignores empty, whitespace-only, or tag-only original strings when calculating progress ratios, preventing false progress inflation.
  - **Unified Font & Width Override Highlights**: Renders an identical soft-purple background (`rgba(186, 85, 211, 40)`) and a bold, 2px bright-purple border (`rgb(186, 85, 211)`) around both the **Font** ComboBox and the **Width** SpinBox widgets when custom line overrides are active, providing visual consistency.
- **Virtual Chapters Navigation**: Integrates a virtual `Chapters -> Act -> Chapter` hierarchical node structure in the Blocks panel. Dialogue lines scattered across physical `.bmg` or `.json` blocks are dynamically grouped chronologically based on story timeline database coordinates. Supports right-click context menu actions (rename, delete, assign font overrides, toggle markers).

---

### 2. High-Performance Archive Management
- **In-Memory Virtual File System**: Native, zero-dependency parser for U8 and RARC archive containers (`.arc`, `.rarc`, `.ark`). Extracts, edits, and repacks archives entirely in RAM, preventing disk clutter and avoiding external executables.
- **Lazy LZ77 Yaz0 Compressor**:
  - Pure-Python implementation of Nintendo's Yaz0 compression featuring a sliding-window LZ77 algorithm with lookahead lazy evaluation.
  - Uses prefix-based hashing to prune the lookback search space, achieving sub-second compression runs for game assets.
  - Generates byte-perfect parity output compatible with original hardware, preventing console-crashing buffer overflows and out-of-memory errors on GameCube and Wii.
  - Supports automatic sector alignment zero-padding (`\x00`) to match disk sector boundaries.
- **Archive Size Verification Warning**:
  - Automatically compares the size of compressed/packed archives against original disk allocations during final save.
  - Triggers a clear warning popup if a modified archive exceeds the size of the original file, prompting the user to shorten translation strings to prevent ROM crashes.

---

### 3. Advanced Text Layout & Proportional Wrapping
- **LineNumberedTextEdit Component**: Custom editor widget that calculates character widths on a pixel-perfect level using proportional font tables, rendering a responsive horizontal guideline (tick) representing the target display limit.
- **Proportional Word Wrapping**:
  - Wraps strings using font metrics to fit within `line_width_warning_threshold_pixels`.
  - Balanced evaluation: permits a single word to cross the warning threshold if the cumulative line width remains below `game_dialog_max_width_pixels` (the hard limit), avoiding ugly, premature wrapping splits.
- **Sentence Integrity Page Building**:
  - Groups dialogue lines into multi-page views separated by page break codes (e.g. `\p`, `\l`).
  - Preserves sentence structure: entire sentences are kept together on a single page. If adding the next sentence would overrun the page limit, the sentence is automatically pushed to the next page.
- **Dynamic Guidelines & Coloring**: Guideline tickers dynamically recolor to red upon width violation and green/blue otherwise. Strips incomplete tag syntaxes (e.g. `{escape:0:...`) during character slices to prevent tag characters from bloating text width measurements.
- **Smart Empty Lines Hiding**: Condenses consecutive empty lines (3 or more) in the read-only preview panel into a single placeholder line: `[start-end] X empty line(s)`, styled with a dark gray color (`#888888`) that bypasses spellchecking and tag parsing to keep views clean. Double-clicking the line number immediately scrolls the editor to the active string.
- **Missing Icon Spacing Detection & Auto-fix**:
  - Introduces a light-blue warning (`QColor(173, 216, 230, 150)`) for missing spacing around physical icon/button tags (e.g., `{(A)}`, `[(A)]`, or tags with positive widths).
  - Intelligently ignores adjacent punctuation (`.`, `,`, `!`, `?`, `-`, `:`, `;`) so warnings only trigger when tags directly merge with alphanumeric characters.
  - Includes full, project-wide Auto-fix capabilities and configurable toggles in Global Settings.

---

### 4. Developer-Friendly Plugin Architecture
- **Abstract Base Rules (`BaseGameRules`)**: Extensible class in `plugins/base_game_rules.py` defining hooks for load/save logic, entering/shift-entering carriage controls, custom tag syntax checking, text auto-fixes, and spellcheck patterns.
- **Custom Fonts Directory**: Specify a custom folder path (`fonts_dir_path`) to dynamically load external `.json` font maps or `.bfn` Nintendo Binary Font files.
- **Background Archive Font Extractor**: Automatically scans `.arc` or `.u8` containers inside the fonts directory, extracts nested fonts in memory, and registers them under `{archive}/{font_name}` for real-time width warning metrics.
- **Autonomous Tag Aliases (`aliases.json`)**: Persistently saves user-defined tag mappings inside the active plugin's folder, merging them with baseline defaults upon startup or plugin switch.
- **Tag Custom Width Dialog**: Interactive input dialog with `QIntValidator` to assign custom pixel widths to game control codes. Saves directly to the active plugin's `font_map.json` and triggers instant layout updates.
- **Standardized Script Parser**: Core support for structured transcripts with inline chapters, room locations, action notes, and speakers. Supports dynamic name tag substitutions (`get_dynamic_name_tags()`) before text distillation to map runtime placeholders.

---

### 5. AI-Powered Orchestration & Translation
- **Unified AI Translation Base**: Composers automatically extract and inject only glossary entries relevant to the active translation block (`glossary_manager.get_relevant_terms(text)`) into system prompts, protecting context limits.
- **Surrounding Context Injection**: Gathers up to 3 preceding and 3 succeeding dialogue strings (utilizing their current translation state) to inform the LLM, preserving tone, pronoun gender, and formal/informal address endings (like Slavic *ty/vy* verb inflections).
- **Force-Alias Tag Preservation (`F:` prefix)**:
  - Preserves tags during translation by converting them to plain-text word equivalents (e.g., `{F:Link}` instead of `{escape:0:0000}`) before querying the AI.
  - Translators translate names contextually as real words (respecting grammar declensions), and the engine automatically restores original tags in post-processing.
- **AI JSON Normalization Retries**: Automatically detects malformed or truncated JSON payloads and enqueues formatting reminders to recover structured translations.
- **Narrative Session History Compression**: Compresses dialogue history into a cohesive story synopsis when the active message log exceeds limit, retaining long-range story context.
- **AI Translation Presets**:
  - Save, load, and manage custom API provider presets (endpoint URL, model names, API keys, parameters) directly from the settings dialog.
  - Allows quick, seamless switching between different setups (e.g., local Ollama, OmniRouter, native Google Gemini, or customized OpenAI endpoints) without re-entering credentials.

---

### 6. Glossary & Terminology Subsystem
- **High-Performance Highlighting**: Evaluates text for glossary occurrences instantly using the **Aho-Corasick** algorithm.
- **Slavic Morphological Matcher**: Uses stemming algorithms to highlight inflected forms of terms (e.g. matching "Меча", "Мечем" for "Меч").
- **Dynamic Tabbed Interface (`QTabWidget`)**: Categorizes glossary databases into separate semantic tabs ("Characters", "Items", "Locations", etc.) with an "All" master index.
- **Organize via AI Wizard**:
  - Stage 1: Scans terms and suggests 4 to 7 thematic categories.
  - Stage 2: Displays checkable UI, dynamically classifies all entries, writes back to the markdown database, and reloads active tabs.
- **HTML Tooltips & Font Scaling**: Renders rich markdown glossary descriptions on hover (supporting lists, line breaks, bold styling). Configurable `tooltip_font_size` SpinBox (6px to 32px) scales tooltips globally.

---

### 7. Asynchronous Spellchecker & Quality Tools
- **CPU-Efficient background Worker**: Replaced busy-loops in `SpellcheckWorker` with a high-efficiency `threading.Event()` wait condition, keeping CPU usage at 0% when idle and waking up instantly when a word is enqueued.
- **Persistent Disk Caching**: Stores spellchecking suggestions in `spell_cache.json` to optimize performance across large files.
- **Search Panel Spellchecking**: Integrated real-time spellchecking into the search query input box. Incorrectly spelled words are highlighted with a red wavy underline matching standard IDE style formats without affecting standard context menus (`QMenu`) or line edit background colors.
- **Asynchronous External Script Runner (`>_` button)**: Compile ROMs or launch emulators directly from the toolbar. Spawns processes asynchronously via `subprocess.Popen` in a new console window (`CREATE_NEW_CONSOLE` on Windows) resolving paths relative to the script's parent folder.
- **Global Performance Toggles**: Disable heavy systems (Live BFN Dialog Preview, real-time warning scans, and glossary matches) inside the Global Settings tab. Bypassing these subsystems completely eliminates typing lag (input latency) during rapid text entry on any hardware.

---

### 8. MemePalace Context Integration
- **Modeless Context Builder**: YouTube transcript fetcher and chronological matching worker (`MemePalaceWorker`) operating in the background.
- **Narrative Event Chapters**: Segments game scripts into acts, chapters, and locations, storing them in a local SQLite database (`mempalace_local.db`).
- **Interactive Database Viewer**: Browses generated visual descriptions, characters, and dialogues. Double-clicking any row jumps directly to the editor line.
- **Local Markdown Script Parser**:
  - Local parsing of `.md` scripts formatted using the [script_template.md](file:///d:/git/dev/Picoripi/plugins/script_template.md) file.
  - Automatically extracts cast profiles, terms, and chapters locally, saving all AI API token costs for the pre-analysis step.

---

### 9. Nintendo Binary Font (BFN) Editor
- **Integrated Visual Suite**: Opens, edits, and recompiles `.bfn` fonts embedded within U8/RARC archives.
- **Texture Sheet Operations**: Exports/imports sheet PNGs with alpha transparency.
- **Spreadsheet Glyph Grid**: Edits mapping ranges, Unicode offsets, widths, and kerning. Modifying values automatically triggers font map reloading and text editor guideline recalculations instantly.
- **Live Simulator**: Renders real-time text layouts to test custom kerning.

---

## Directory Structure

```
Picoripi/
├── main.py                     # Entry point (MainWindow orchestrator)
├── core/                       # Core business logic and database models
│   ├── data_state_processor.py # Central data access & mutation layer
│   ├── data_store.py           # AppDataStore — shared state container
│   ├── data_manager.py         # JSON/text file I/O
│   ├── project_manager.py      # .uiproj project lifecycle
│   ├── project_models.py       # Dataclasses (Project, Block, Category)
│   ├── glossary_manager.py     # Glossary parsing, Aho-Corasick, CRUD
│   ├── spellchecker_manager.py # Hunspell spellcheck & disk-caching
│   ├── state_manager.py        # AppState context managers
│   ├── undo_manager.py         # Multi-level undo/redo snapshots
│   ├── context.py              # ProjectContext Protocol
│   ├── script_segmenter.py     # Flat text script chapter segmenter
│   ├── markdown_script_parser.py # Local Markdown script parser
│   └── settings/               # Settings subsystems
├── handlers/                   # Feature logic handlers
│   ├── app_action_handler.py   # Project load/save, export/import
│   ├── project_action_handler.py # Project-tree CRUD
│   ├── list_selection_handler.py # Tree selections & preview reloading
│   ├── text_operation_handler.py # Editor inputs, copy-paste, reverts
│   ├── text_analysis_handler.py  # Character width & guideline metrics
│   ├── text_autofix_logic.py     # Smart page-breaks & word-wrap fixing
│   ├── search_handler.py         # Global search & fuzzy highlighting
│   ├── issue_scan_handler.py     # Project-wide validation scans
│   ├── string_settings_handler.py # Line settings and font overrides
│   ├── ai_chat_handler.py        # AI Assistant Chat window
│   ├── translation_handler.py    # Main translation facade
│   └── translation/              # Prompt composers, workers, glossary UI
├── ui/                         # Qt Interface layout, dialogs and themes
│   ├── ui_updater.py           # Main UI sync coordinator
│   ├── settings_dialog.py      # Settings panels
│   └── builders/               # Menu, toolbar, layout builders
├── components/                 # Reusable UI widgets (BFN, text fields)
├── plugins/                    # Extensible game-specific plugins
│   ├── base_game_rules.py      # Rules base class (API specifications)
│   ├── common/                 # Shared default metrics and prompts
│   ├── zelda_mc/               # Zelda: Minish Cap plugin
│   ├── zelda_ww/               # Zelda: The Wind Waker plugin
│   ├── pokemon_fr/             # Pokemon FireRed plugin
│   ├── plain_text/             # Generic ruleset
│   ├── DEVELOPER_GUIDE.md      # AI-oriented developer guide for plugins
│   └── script_template.md      # Template for markdown timeline scripts
├── utils/                      # Syntax Highlighters, constants, logging
└── tests/                      # Pytest unit testing suite
```

---

## Setup & Execution

### 1. Requirements
- Python 3.14.0 or higher
- Windows OS (supports Linux/macOS with manual startup)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Credentials
Create a `.env` file in the root directory based on the template:
```bash
cp .env.example .env
```
Fill in the API keys:
- `OPENAI_API_KEY`: For OpenAI models.
- `GEMINI_API_KEY`: For Google Gemini models.
- `DEEPL_API_KEY`: For DeepL translation (optional).

### 4. Launch
- **Windows**: Run `run.bat` to automatically build/verify virtual environment and launch the app.
- **Other Platforms**: Run `python main.py` directly.

### 5. Running Tests
The suite consists of over 900 test cases using `pytest`:
```bash
# Windows PowerShell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest tests/
```

---

## License
This project is licensed under the MIT License - see the LICENSE file for details.
