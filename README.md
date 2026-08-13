# Picoripi v0.3.080-dev

The **Picoripi** (v0.3.080-dev) is a visual translation and localization workbench built with **Python** and **PyQt6**. It is designed for precise, visual, and highly convenient translation of texts with strict length and layout constraints. While initially built to excel at retro game localization (supporting complex Nintendo formats and custom tags), its core architecture is fully generalizable to any structured translation, alignment, or editing workflow.


---

## Documentation Map

- [Feature Reference](docs/FEATURE_REFERENCE.md): detailed description of the main user-facing and engineering subsystems.
- [AI Development Manifesto](docs/AI_DEVELOPMENT_MANIFESTO.md): rules for AI-assisted architecture, implementation, testing, documentation, and release work.
- [MemPalace Context Manifesto](docs/MEMPALACE_CONTEXT_MANIFESTO.md): living roadmap and completion contract for Markup Studio, story timeline, character context, glossary, and context-aware AI translation integration.
- [Testing Strategy And Test Audit](docs/TESTING_STRATEGY_AND_AUDIT.md): test-suite audit, risk register, and parallel test commands.
- [Plugin Authoring Guide](docs/PLUGIN_AUTHORING_GUIDE.md): current guide for creating new plugins from `plugins/default_plugin/`.
- [Default Plugin Template](plugins/default_plugin/README.md): copy-ready baseline plugin for new game/text formats.
- [AI Plugin Assistant Prompt](plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md): guided prompt for AI-assisted plugin development.
- [Wiki Plugin Developer Guide](docs/wiki/3_Plugin_Developer_Guide.md): extended plugin API and hook reference.

---

## Key Features

### 1. Project Management & Workspace Navigation
- **Project-Based Workflow**: Creates, loads, and manages `.uiproj` projects encapsulating all translation files, virtual categories, and settings.
- **Redesigned Script Markup Studio Interface**: Reorganized the workspace to separate workflow stages, file operations, and advanced tools. Features a centralized File menu, a Live Save Status Indicator, a dynamic 4-stage Progress Bar, and an intelligent Next Action dashboard suggesting context-aware buttons (AI Auto-fill, suggestions review, or MemPalace transition) based on project completion.
- **Virtual Folder Structure**: Organizes text blocks into nested virtual folders (categories) for logical narrative layout. Supports drag-and-drop file organization.
- **Granular Status & Propagation**: Unsaved changes propagate dynamically as asterisks (`*`) up the folder tree, with specialized error/warning counts on parent nodes.
- **Partial Changes Saving**:
  - **Selected Blocks Saving**: Allows saving only specifically selected blocks/categories containing translation modifications via the project tree context menu, keeping other changes in-memory.
  - **Targeted String Saving**: Context menus in both translation editors and read-only previews allow saving either a single selected string or a targeted set of lines to files, leaving the remaining edits untouched.
  - **Export Original Text**: Provides the ability to export the original (source) string values across all blocks in the project directly to a structured JSON file through the File menu, matching the translation export schema.
- **Fault-Tolerant Session Autosaving**:
  - Automatically saves the workspace state using a human-readable, durable JSON session file (`.picoripi_session.json`) alongside a binary crash recovery snapshot (`.picoripi_session`) using the `Pickle` protocol.
  - **Compact & Versioned**: Avoids writing heavy original game texts or translation files to disk. Instead, it serializes only UI filters, navigation paths, unsaved changes, and metadata.
  - **Durable JSON Checkpoints & Fallback**: Fast autosave operations are debounced (2 seconds) and use Pickle to prevent disk lag. A schema-based, validated JSON checkpoint is saved at application shutdown, periodically (every 5 minutes), and before long operations. Startup loads the JSON checkpoint first, falling back to the Pickle snapshot if JSON is missing or corrupted.
  - **Undo/Redo History Persistence**: The complete Undo/Redo operations stack is preserved within the session file, enabling users to seamlessly undo (`Ctrl+Z`) and redo (`Ctrl+Y`) edits across application restarts.
  - **Instant Recovery**: If a crash occurs or the app is closed, the application automatically loads fresh data from disk asynchronously and recovers the exact session state on startup.
- **Soft Shading & Progress Bars**:
  - **Translated Lines Shading**: Renders a soft, pastel-green background (`QColor(46, 139, 87, 40)`) under line numbers in translation editors and preview screens for translated strings, facilitating rapid document navigation.
  - **File Progress Bars**: Tree items render smooth, semi-transparent green progress bars (`QColor(46, 139, 87, 25)`) left-to-right beneath file names, proportional to the translation completion rate.
  - **Translatable String Detection**: Intelligently ignores empty, whitespace-only, or tag-only original strings when calculating progress ratios, preventing false progress inflation.
  - **Unified Font & Width Override Highlights**: Renders an identical soft-purple background (`rgba(186, 85, 211, 40)`) and a bold, 2px bright-purple border (`rgb(186, 85, 211)`) around both the **Font** ComboBox and the **Width** SpinBox widgets when custom line overrides are active, providing visual consistency.
  - **Unified Light Theme Controls Height**: Standardized styling of `QComboBox` (Font selector) and `QSpinBox` (Width selector) in the light theme, matching their borders, padding, and heights perfectly for visual symmetry.
- **Virtual Chapters Navigation**: Integrates a virtual `Chapters -> Act -> Chapter` hierarchical node structure in the Blocks panel. Dialogue lines scattered across physical `.bmg` or `.json` blocks are dynamically grouped chronologically based on story timeline database coordinates. Supports right-click context menu actions (rename, delete, assign font overrides, toggle markers).
- **Virtual Speakers Navigation**: Group dialogue lines dynamically by Speaker. Dialogue lines from any physical `.bmg` or `.json` blocks are gathered into a virtual `Speakers -> Speaker Name` node structure in the Blocks panel, including a dedicated `"None"` folder at the very top of the list for all unassigned strings. Dialogue lines counts are displayed next to names (e.g. `ASHEI [12]`). Adding strings to these folders automatically assigns the corresponding speaker metadata to them. Supports direct selection and interactive input of speaker names via a combo box located above the translation editor (featuring a `"None"` option to clear assignments), instantly updating speaker assignments and hot-reloading virtual folders, while showing the MemePalace speaker mapping and glossary details directly in the speaker label and combobox tooltips to eliminate visual clutter.
- **Auto-Synchronized Filter Checkboxes**: Automatically synchronizes the graphical states of all filter checkboxes (such as `Show Unsaved Only`, `Hide translated`, etc.) inside the preview panel with the internal `AppDataStore` values upon startup, session restoration, or project settings loading to prevent visual UI state desynchronization.
- **Warning-Specific Preview Filtering**: Allows filtering the preview panel by specific warning categories. Adds a filter button (`Warnings: X / Y`, where X is the number of active warning filters and Y is the number of enabled warnings in Settings -> Detection) next to the preview layout toggles. Clicking the button opens a modal dialog (`WarningsFilterDialog`) with checkboxes and descriptive tooltips for each warning type, enabling users to isolate strings matching a subset of selected warnings or view all warnings if no specific filters are checked. If no warnings are selected, the preview is cleared.
- **Auto-follow scroll in Script Markup Studio**: Adds a toolbar checkbox `Auto-follow scroll` inside the Script Markup Studio. When enabled, scrolling the raw script pane dynamically aligns the preview pane to the top visible line in the raw pane using `ensureCursorVisible()` (gentle scrolling). If the target line is already visible, the view remains stationary to avoid layout jumping.

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
- **Missing Tag Spacing Detection & Auto-fix**:
  - Introduces a light-blue warning (`QColor(173, 216, 230, 150)`) for missing spacing around physical icon/button tags (e.g., `{(A)}`, `[(A)]`), as well as between words separated by zero-width tags (e.g., `{color:red}`) or direct punctuation-word boundaries where words stick together (e.g., `побував.Жовта`).
  - Implements a robust **Clean Text Analysis** engine: the text is analyzed with zero-width (hidden) tags removed while layout-carrying tags with non-zero widths (like `{tab}`, `{*}`, `{escape:6:000a}`, `{escape:6:000b}`) are kept visible and are not hidden.
  - Automatically identifies missing spacing transitions (alphanumeric-to-alphanumeric separated by tags, punctuation-to-alphanumeric, and alphanumeric-to-visible-tag) on the clean text, and maps them back to the original text.
  - Includes full project-wide Auto-fix capabilities and configurable toggles in Global Settings.
- **Prevent Empty Padding Lines in Auto-Fix**: Added a configurable option in Global Settings and the Ctrl+AutoFix dialog to completely omit trailing blank lines on page boundaries when wrapping or paginating, preventing unwanted empty padding lines from being generated.
- **Silent Ctrl+S Saving with Toast Notification**: Refactored the file saving mechanism so that pressing `Ctrl+S` (or using the Save action) instantly saves all changes without displaying blocking confirmation dialogs. A non-blocking, semi-transparent black **Toast Notification** with rounded corners appears in the bottom-left corner of the screen for 2 seconds to confirm the success.
- **Strict Page-Local AutoFix (Shift+AutoFix)**: Pressing `Shift` while running AutoFix isolates wrapping and fixes to the current page only. It strictly preserves page boundaries by padding each page back to its original length, preventing text from next pages from overflowing into previous ones, even when the empty padding lines prevention is enabled globally.
- **Unconditional Page Layout Sentence Alignment**: Refactored sentence wrapping to allow matching target text pages directly with the source. When enabled, it strips old layout markers and replicates exact game-specific page break codes (like `[escape:0:0007...]`) from matching source sentences.
- **Tab Relocation and Clean Spacing**:
  - Automatically relocates control codes `{tab}` to the start of the next line during Auto-fix operations.
  - Ensures `{tab}` never remains inside text blocks (even when general star tag rules are disabled) and prevents sentence compaction or word wrapping from merging them back.
  - Cleans any unwanted spaces immediately following `{tab}` (e.g. converting `{tab}  text` to `{tab}text`).

---

### 4. Developer-Friendly Plugin Architecture & Rule Engine
- **Centralized Rule Engine**:
  - Integrates a robust system of rules (`ProblemRule`) and rule registry (`ProblemRuleRegistry`) located in `plugins/common/problem_rules/` that serves as a single source of truth for both detection and auto-fixing capabilities.
  - Eliminates duplicated parsing logic between analyzers and fixers. All rules (e.g., `WidthRule`, `BadSpacingRule`, `ShortLineRule`, `MissingIconSpacingRule`) encapsulate their specific validation parameters and correction procedures.
  - Features high-level adapters `GenericProblemAnalyzer` and `GenericTextFixer` acting as wrappers to maintain backwards compatibility while executing clean rule pipelines.
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
- **Asynchronous Cancel & Progress Pipeline**: Long local operations (glossary indexing, spellcheck scanning, advanced search) are non-blocking and completely cancellable. The Glossary Indexing progress dialog features a functional "Cancel" button. Spellcheck and Advanced Search dialogs allow closing the window at any time during execution, safely stopping the background worker thread in the background before dialog rejection to prevent memory leaks and UI freezes.
- **Preview Cache Progress Indicator**: Displays a non-blocking caching progress message (e.g., `Caching previews: X/Y blocks...`) in the main window's status bar during background preview generation.
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
  - Local parsing of `.md` scripts formatted using the [script_template.md](plugins/script_template.md) file.
  - Automatically extracts cast profiles, terms, and chapters locally, saving all AI API token costs for the pre-analysis step.

---

### 9. Nintendo Binary Font (BFN) Editor
- **Integrated Visual Suite**: Opens, edits, and recompiles `.bfn` fonts embedded within U8/RARC archives.
- **Texture Sheet Operations**: Exports/imports sheet PNGs with alpha transparency.
- **Spreadsheet Glyph Grid**: Edits mapping ranges, Unicode offsets, widths, and kerning. Modifying values automatically triggers font map reloading and text editor guideline recalculations instantly.
- **Live Simulator**: Renders real-time text layouts to test custom kerning.

### 10. Smart Search & Navigation
- **Punctuation-Insensitive Match**: If the search query contains punctuation marks (like commas, periods, exclamation points, etc.), the match is strictly mapped to the exact punctuation layout. If no punctuation is typed in the search query, the engine ignores any punctuation present in the target strings, seamlessly matching across commas, quotes, and hyphens.
- **Word-Level Case Sensitivity**: Case sensitivity is evaluated on a per-word basis. Typing a word with a capital letter (e.g. `Link`) makes that specific word's match case-sensitive, while words typed in lowercase (e.g. `sword`) remain case-insensitive.
- **Search Focus Preservation**: Pressing the Enter key while the search input panel is active cycles to the next result, updating the text editor and highlighting the text, but keeps keyboard focus active on the search input itself. This allows for fluid, continuous "Next" traversal without manual mouse focus restoration.
- **Advanced Search Shortcut**: Pressing `Ctrl + H` opens the Advanced Search & Replace dialog instantly, auto-populating it with parameters from the active inline search panel.
- **Search & Replace Undo/Redo Integration**: The Advanced Search & Replace dialog is fully synchronized with the application's global undo stack. Reverting changes (Undo/Redo) in the main window instantly updates the active search results view. Additionally, pressing `Ctrl + Z` or `Ctrl + Y` while focused inside search dialog text editors seamlessly routes actions to the main window's undo manager and updates the dialog dynamically.
- **Non-Modal Dialogs Workflow**: The Advanced Search & Replace, Spellcheck, AI Translation Comparison, and AI Translation Result dialogs operate in a non-modal mode. This allows seamless switching, text copying, and interaction with the main window while they remain open. Previously opened instances are automatically focused, reused, or refreshed when re-triggered, maintaining a highly fluid UI.

---

## AI Translation Subsystem & Configuration

Picoripi features a powerful, highly customizable AI Translation subsystem designed specifically to tackle the complexities of retro game localization. Below is an overview of the supported AI providers, capabilities, and configuration options.

### 1. Supported AI Providers & Models
You can configure the active translation engine in the **AI Translation** tab within the Global Settings dialog. The system supports:
- **OpenAI Compatible**: Connects to the standard OpenAI chat completions API or any compatible endpoints (e.g., Local LLMs, Llama.cpp, OpenRouter, Perplexity, DeepSeek, Anthropic wrappers).
  - *Parameters*: API Key, Endpoint URL, Model Name, Temperature, Max Output Tokens, Request Timeout.
- **Google Gemini API**: Native Google Gemini integration supporting the official API endpoints or custom proxy endpoints.
  - *Parameters*: Base URL (optional), API Key, Model Name (e.g., `gemini-1.5-flash-latest` or `gemini-1.5-pro-latest`).
- **Ollama Chat API**: Fully local, zero-cost execution using Ollama.
  - *Parameters*: Base URL (defaults to `http://localhost:11434`), Model Name, Temperature, Request Timeout, and Keep Alive settings (e.g., `5m` to keep models cached in VRAM).
- **Perplexity API**: Tailored wrapper for Perplexity AI models, supporting custom temperatures and token limits.

### 2. Core AI Capabilities
- **Dialogue Translation**: Translate single lines, selected ranges in the preview panel, entire project blocks, or virtual chapters chronologically.
- **Session/Chat History Tracking**: Enables session-based translations where the context of the conversation is preserved across multiple requests. This ensures consistent character tones, pronoun genders, and verbs (highly critical for languages like Ukrainian).
- **Surrounding Context Injection**: For every string sent to translation, Picoripi gathers up to 3 preceding and 3 succeeding strings (with their current translation status) and injects them as conversation context, preventing the AI from translating sentences in a vacuum.
- **Smart Glossary Filtering**: Only the glossary terms detected in the active lines are sent to the AI prompt, protecting system context limits and preventing model confusion.
- **Tag Preservation (Force-Alias)**: Game control codes and tags (like `{Color:Red}`, `[L-Stick]`, `[PLAYER]`) are translated into plain-text equivalents (e.g., `{F:Link}`) before calling the API. They are translated contextually as real words and automatically restored post-translation, avoiding tag corruption or deletion.
- **AI Translation Variations**: Generates up to 10 different translation variants for any selected string. Features a non-blocking modeless variations dialog, client-side variations caching to prevent duplicate token costs, and a manual "Refresh" trigger.
- **AI Translation Comparison & Revision**: When re-translating lines that already have translations, a split "Old/New Translation" comparison dialog is displayed. Allows interactive revision: click "Old Translation" to revert to the previous text, click "New Translation" to apply the new text, double-click "New Translation" to edit the text on the fly (with Ctrl+Enter to save), or right-click to generate AI variations for that specific line.
- **Glossary Occurrence Batch Update**: When a term's translation in the glossary is updated, the AI can scan, locate, and automatically retranslate all of its occurrences in the project, adjusting grammar declensions contextually.
- **AI Glossary Fill**: Generates translation suggestions and notes for new glossary entries automatically based on the term and the active game context.
- **AI Chat Dialog**: A modeless chat window ("Discuss with AI") accessible from the editor context menu. It auto-fills with selected original/translated text, allowing real-time prompt conversations.

### 3. Presets & Prompt Settings
- **Translation Presets**: Save all active parameters (provider, endpoint, model, temperature, timeout, etc.) under custom names. Switch between different setups (e.g., local Ollama for drafts, Gemini Pro for final review) instantly.
- **Editable Prompts JSON**: Hold custom system prompts for translations, glossary fills, and notes generation. Click the **Edit Prompts JSON** button on the settings panel to customize instructions globally.

---

## Power-User Features (Ctrl Modifier Shortcuts)

Picoripi includes several advanced shortcuts and modifier combinations that simplify the translation workflow for power-users:

### 1. Interactive Dialog Modifiers
- **Ctrl + Click on AutoFix**: Instead of executing all Auto-Fix routines automatically, holding `Ctrl` opens the **Selective Auto-Fix Dialog**, where you can toggle specific rules (such as page alignment, icon spacing checks, or preventing empty padding lines).
- **Ctrl + Click on Translate / iTranslations**: Opens the **Prompt Editor Dialog** instantly. This allows you to customize the system prompt or user prompt instructions specifically for the current translation run before calling the AI.
- **Ctrl + Click on Variation (AI Variations)**: Triggers a **Force Prompt Dialog**, allowing you to append custom, specific instructions for the next variations generation (e.g. "make it sound more formal", "add a sarcastic tone").

### 2. Editor & Tree Context Clicks
- **Ctrl + Click on Glossary Words in Original Panel (Read-only)**: Instantly opens the glossary manager dialog focused on the clicked term, allowing you to edit its translations or notes directly.
- **Ctrl + Click on Bracketed Tags (`[...]`) in Translation Panel**: If the clipboard contains a valid curly tag (like `{PLAYER}` or `{Color:Red}`), Ctrl+clicking a placeholder bracketed tag maps and replaces it with the clipboard contents instantly.
- **Ctrl + Click on Preview Panel Lines**: Enables multi-line selection within the active block, useful for bulk operations or selective translations.

### 3. Navigation & Zoom Shortcuts
- **Ctrl + Mouse Wheel**: Adjusts zoom (font size scaling) dynamically. Works on the original and translation editor panes, the preview list panel, and the project file-tree widget.
- **Ctrl + PageUp / PageDown**: Navigates to the previous or next block in the project block tree view without requiring mouse focus.
- **Ctrl + H**: Launches the Advanced Search & Replace dialog instantly, passing active parameters from the inline search panel.

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
│   ├── default_plugin/         # Copy-ready baseline for new plugins
│   ├── zelda_mc/               # Zelda: Minish Cap plugin
│   ├── zelda_ww/               # Zelda: The Wind Waker plugin
│   ├── pokemon_fr/             # Pokemon FireRed plugin
│   ├── plain_text/             # Generic ruleset
│   ├── DEVELOPER_GUIDE.md      # AI-oriented developer guide for plugins
│   └── script_template.md      # Template for markdown timeline scripts
├── utils/                      # Syntax Highlighters, constants, logging
└── tests/                      # Pytest unit testing suite
```

*Note on ignored folders:*
- `gemini/`: A local, git-ignored backup directory containing old reference code copies.
- `scratch/`: A local, git-ignored directory reserved for developer scratchpads, temporary test scripts, and debugging logs.

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
The suite currently collects 1,515 default-lane pytest items plus 10 dedicated performance-lane items:
```bash
# Windows PowerShell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/

# Performance lane, excluded from default pytest addopts
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto -m performance tests/test_performance.py
```

### 6. Codebase Knowledge Graph (Graphify)
Picoripi supports **Graphify** (`graphifyy`), an AST-based semantic knowledge graph builder. This generates an interactive structural graph and analysis of the codebase, which AI coding assistants can query to understand relationships, modules, and workflows without reading raw files.

To generate/update the knowledge graph:
1. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
2. Initialize the platform skill (e.g. for Claude Code, Gemini CLI, etc.):
   ```bash
   .\.venv\Scripts\graphify.exe install
   ```
3. Run the extraction and clustering process from `.venv`:
   ```bash
   # Extract AST and build semantic graph (requires OpenAI/Gemini API key)
   $env:OPENAI_API_KEY="your-api-key"; .\.venv\Scripts\graphify.exe extract . --backend openai

   # Perform clustering and generate interactive visualization & markdown reports
   $env:OPENAI_API_KEY="your-api-key"; $env:GRAPHIFY_VIZ_NODE_LIMIT=10000; .\.venv\Scripts\graphify.exe cluster-only . --backend openai
   ```
4. Zipped output and files are written to `graphify-out/`:
   - `graph.html`: Interactive, searchable 2D network diagram.
   - `GRAPH_REPORT.md`: Architectural summary, structural anomalies, and recommended walkthrough questions.
   - `graph.json`: Serialized knowledge graph dataset.

## Text Validation Rules & Auto-Fix Engine (Standard Plugin)

Picoripi includes a comprehensive, real-time Text Analysis and Auto-Fix engine. Below is a detailed description of the 9 warning metrics, their visual indicator colors in the editor, and the rules applied by the Auto-Fix processor for the standard plugin (`plain_text`):

### 1. Warning Classifications & Visual Gutter Highlights

1. **Tag Validation Warning (`ZWW_TAG_WARNING`) — Light Gray Marker (`rgba(200, 200, 200, 150)`)**
   - *Rule*: Triggers when control codes or bracket tags have invalid format structures, unclosed brackets (e.g., `[Color:Red` instead of `[Color:Red]`), or non-matching tag pairs. Also checks for tag count and name mismatch between original and translation (with exceptions like Link and Epona).
   - *Auto-Fix*: Automatically attempts to close brackets or strip corrupted tag fragments.

2. **Pixel Width Exceeded (`ZWW_WIDTH_EXCEEDED`) — Red Marker (`rgba(255, 0, 0, 100)`)**
   - *Rule*: Triggers when a text subline's physical pixel width (calculated using custom font maps) exceeds the configured dialog threshold.
   - *Auto-Fix*: Performs proportional Word Wrapping relative to the active font metrics and character guidelines.

3. **Short Subline (`ZWW_SHORT_LINE`) — Green Marker (`rgba(0, 200, 0, 100)`)**
   - *Rule*: Triggers when the first word of the next subline (including any preceding visible button/icon tags) can physically fit onto the current subline without violating warning width thresholds.
   - *Lookahead Optimization*: If the next subline contains **exactly two words**, the warning will only trigger if **both** words can fit together on the current line, preventing a single word from being left isolated ("orphaned").
   - *Single-Letter Lookahead*: If the first word of the next subline is a single-letter word (e.g., "в", "й", "і", "а", "з", "у" in Cyrillic, or any single-character alphabetical word), it will only trigger a warning if **both** the single-letter word **and** the word following it can fit together on the current line. This prevents creating orphaned single-letter hanging words/prepositions at the end of lines.
   - *List and Phrase End Protection*: Prevents merging if the current line ends with a colon (`:`), semicolon (`;`), dash (`—`, `–`), or a closing bracket/parenthesis (`)`, `]`, `}`) preceding one of these punctuation marks, protecting itemized lists and line endings from aggressive compaction.
   - *Header & Standalone Line Protection*: Prevents merging if the current line is significantly shorter than the line width threshold (less than 50% of the threshold), starts with an uppercase letter, and the next line also begins with an uppercase letter. This keeps distinct titles, standalone labels, and menu items separated.
   - *Auto-Fix*: Merges the qualifying words from the next subline into the current subline, maintaining correct spacing.

4. **Empty Odd Subline (`ZWW_EMPTY_ODD_SUBLINE_DISPLAY`) — Orange Marker (`rgba(255, 165, 0, 180)`)**
   - *Rule*: Enforced in specific gameplay layouts (such as dual-row scrolling text blocks) where an odd-numbered subline is left empty, disrupting text display flow.
   - *Auto-Fix*: Collapses the empty subline and shifts text upwards to align with necessary row lines.

5. **Single Word Page Start (`ZWW_SINGLE_WORD_SUBLINE`) — Blue Marker (`rgba(0, 0, 255, 120)`)**
   - *Rule*: Triggers when a subline positioned at the very start of a text page contains only one single word, which looks visually unbalanced in standard text dialogs.
   - *Auto-Fix*: Pulls words from subsequent lines or shifts layout blocks to keep text balanced.

6. **Single Word Orphan (`ZWW_SINGLE_WORD_SUBLINE_NON_START`) — Brown Marker (`rgba(139, 69, 19, 120)`)**
   - *Rule*: Triggers when a subline (other than the first line of a page) contains only a single word (an "orphan"), usually caused by aggressive wrapping. **Note**: It is ignored if shifting the last word from the preceding line down would make the new last line wider in pixels than the new preceding line (to maintain a balanced block shape).
   - *Auto-Fix*: Pulls the last word from the preceding subline down to pair it with the orphaned word, unless it violates the line width balance constraint.

7. **Empty First Line of Page (`ZWW_EMPTY_FIRST_LINE_OF_PAGE`) — Pink Marker (`rgba(255, 105, 180, 100)`)**
   - *Rule*: Triggers when the very first line of a multi-line page is empty, but subsequent lines on the same page contain text (causing text to start awkwardly shifted down).
   - *Auto-Fix*: Deletes the blank first line and shifts all subsequent lines on that page up by one slot.

8. **Spacing & Punctuation Cleanup (`ZWW_BAD_SPACING`) — Warning Gutter Line**
   - *Rule*: Triggers when there are multiple consecutive spaces, double spaces, or spaces incorrectly inserted before standard punctuation marks (`,`, `.`, `!`, `?`, `;`, `:`, `…`).
   - *Universal Tag Fix*: Detects spaces inserted between game tags/closing brackets and punctuation (e.g. `[Color:Red] ,` or `{PLAYER} .`) and resolves them to clean spacing layouts (e.g. `[Color:Red],` or `{PLAYER}.`).
   - *Auto-Fix*: Cleans double spaces and removes spaces before punctuation marks.

9. **Missing Icon Spacing (`ZWW_MISSING_ICON_SPACING`) — Light Blue Marker (`rgba(173, 216, 230, 150)`)**
   - *Rule*: Triggers when a visible button tag or graphic icon (e.g., `{(btn)}` or `[(A)]`) is merged directly with adjacent letters or numbers without a space (e.g., `press{(btn)}to` instead of `press {(btn)} to`). Ignored if the tag is adjacent to punctuation marks. Hyphens immediately after the icon (e.g. `{(L)}-наведення`) are treated as an exception and do not trigger warnings. Spacing before the hyphen in such constructs is considered an error.
   - *Auto-Fix*: Automatically inserts standard single spaces before and/or after the tag to guarantee clean visual separation, and strips any spaces before the hyphen in hyphen-word constructs.

10. **Broken Icon-Hyphen Wrap (`ZWW_BROKEN_ICON_HYPHEN`) — Plum/Purple Marker (`rgba(221, 160, 221, 150)`)**
    - *Rule*: Triggers when a tag-hyphen-word construct (e.g. `{(L)}-наведення`) is broken across a line break.
    - *Word Wrap Integration*: The word wrap engine treats these constructs as single entities to prevent automatic splitting.

### 2. Page Break Optimization (Page Lookahead)

When rendering and wrapping text across multiple pages (delimited by page boundary counts or control breaks):
- **Rule**: If a page contains a trailing blank line (acting as a separator), and the subsequent page's sentence can fully fit onto the current page by removing the empty line, the optimizer automatically collapses the break and pulls the sentence up. This avoids creating unnecessary half-empty pages or orphan lines in game dialogues.

---

## License
This project is licensed under the MIT License - see the LICENSE file for details.
