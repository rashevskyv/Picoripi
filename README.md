# Picoripi v0.3.143-dev

**Picoripi** is a visual translation and localization workbench (Python, **PyQt6**) for texts with strict length and layout constraints. It started as a Nintendo-format editor (BMG, BFN, U8/RARC) and stays general enough for any structured translation project.

The recommended AI backend for glossary and bulk translation is **Gemini Web2API** (local proxy + WebTOP dashboard). See [Wiki: Gemini Web2API](docs/wiki/5_Gemini_Web2API.md).

---

## Documentation Map

**Wiki (start here):** [English](docs/wiki/README.md) · [Українська](docs/wiki/uk/README.md)

- [Interface](docs/wiki/1_User_Guide_and_Workflow_Pipeline.md)
- [Code map](docs/wiki/2_API_Reference.md)
- [Plugins](docs/wiki/3_Plugin_Developer_Guide.md)
- [Configuration](docs/wiki/4_Configuration_Guide.md)
- [Gemini Web2API / WebTOP](docs/wiki/5_Gemini_Web2API.md)
- [Virtual navigation and preview](docs/wiki/6_Virtual_Navigation_and_Preview.md)
- [Maintaining the wiki](docs/wiki/7_Maintaining_This_Wiki.md)
- [Localization Pipeline](docs/wiki/8_Localization_Pipeline.md)
- [Script Markup](docs/wiki/9_Script_Markup.md)
- [AI Translation](docs/wiki/11_AI_Translation.md)
- [Picoripi Companion (Mobile & Sync)](docs/wiki/12_Picoripi_Companion.md)

Interface language: **Language** menu lists every `locales/*.json` that already has translations (name from `@language_name` in that file). Missing strings stay English. Fill catalogs with `tools/i18n-translate/run.bat`. See [Configuration](docs/wiki/4_Configuration_Guide.md).

**Engineering / process:**

- [Feature Reference](docs/FEATURE_REFERENCE.md)
- [AI Development Manifesto](docs/AI_DEVELOPMENT_MANIFESTO.md)
- [MemPalace Context Manifesto](docs/MEMPALACE_CONTEXT_MANIFESTO.md)
- [Pipeline Roadmap](docs/PIPELINE_ROADMAP.md)
- [Testing Strategy](docs/TESTING_STRATEGY_AND_AUDIT.md)
- [ChatMock (ChatGPT web proxy)](docs/chatmock_setup.md)

Older markdown under `docs/` (PLUGIN_AUTHORING_GUIDE, pipeline roadmap, plugin READMEs) may lag the code. Use the wiki, then the source.

---

## Key Features

### 1. Project Management & Workspace Navigation
- **Project-Based Workflow**: Creates, loads, and manages `.uiproj` projects encapsulating all translation files, virtual categories, and settings.
- **Derived virtual views**: **Story**, **Speakers**, **Windows**, **Items**, and **Notated** pack non-empty strings in roughly sorted groups. Empty BMG padding stays only in the physical file. Warning ticks appear on virtual folders the same way they do on files. See the [virtual navigation wiki](docs/wiki/6_Virtual_Navigation_and_Preview.md).
- **Twilight Princess window preview**: When the Zelda BMG plugin exposes `message_window_preview`, the BFN preview draws talk / item-get / sign chrome from a local game dump (not shipped in this repo). Page `n/N` and original/translation (`T`/`O`) sit on the preview.
- **Bidirectional Proportional Preview Scaling & Aspect Ratio Lock**: The game window starts fitted to the preview; with a visible background, the image, frame, and dialogue text share the same transform as the panel resizes or `Ctrl+Wheel` zooms. Hiding the background restores the ordinary window fit. "Fix Font Scale" retains the chosen text size across reopening, and "Reset Scale (100%)" restores 100% zoom. Expanded offscreen rendering buffers prevent text, shadow, and glyph descender clipping, while the preview sidebar adapts button sizes (down to 24px/20px) on compact panels.
- **Show Unsaved Only** (tree and string list) is a session filter. A restart always clears it so a forgotten check cannot hide the project.
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
- **Reference Translation Tabs & Unpacked Multi-Language ROM / ISO Support (PAL Multi-5)**:
  - **Single Patch, Unpacked ROM & ISO Image Support**: Supports loading an external reference translation patch (`File -> Load Reference Translation Patch...`), an unpacked multi-language ROM directory, or a GameCube/Wii `.iso` disc image directly (`File -> Load Unpacked ROM (Multi-Language Reference)...`). If an `.iso` file is selected, Picoripi automatically locates `wit.exe` and extracts the message files into an extracted folder.
  - **Deep Recursive Directory Scanning**: Searches recursively for language directories (`**/Msg*` and `**/msg*`), discovering nested PAL localization folders without requiring users to navigate into internal game directory structures.
  - **Intelligent Region & Language Mapping**: In European PAL dumps (e.g. Twilight Princess), game dialogue resides in language-specific directories (`Msguk`/`Msgen`/`Msgus`/`Msge`, `Msgde`, `Msgfr`, `Msgit`, `Msgsp`). When a community Russian patch was applied, Russian replaced English in the UK English folder (`Msguk`) and is decoded with single-byte `cp1251` under the label **`Russian (RU)`**. Native Nintendo European localizations are concurrently loaded with `cp1252` as **`German (DE)`**, **`French (FR)`**, **`Italian (IT)`**, and **`Spanish (ES)`**.
  - **Dynamic Multi-Language Source Tabs**: Replaces the fixed source panel with dynamically generated read-only editor tabs (`Original (EN)`, `Russian (RU)`, `German (DE)`, `French (FR)`, `Italian (IT)`, `Spanish (ES)`). All tabs share synchronized line navigation and cursor tracking while preserving active tab choice across block changes.
  - **Context-Aware Text Copying**: Clicking the copy/revert arrow (`→`) copies the text from whichever reference tab is currently active directly into the target translation editor.
  - **Multi-Language Context for AI Translations**: Reference translations from all loaded languages are automatically structured and injected into AI translation prompts (`handlers/translation/prompt_composer/`), giving LLMs explicit guidance on grammatical gender, formal/informal address forms (e.g., German *du/Sie*, French *tu/vous*), and character tone across European releases. The translator always translates from the original source text and treats reference translations strictly as contextual evidence, with an explicit rule against translating from or copying a reference language as the target result.
  - **Glossary Variants Extraction**: Multi-pass reference variant extraction (`tools/extract_ru_glossary_variants.py`) matches reference dialogue strings with glossary terms (exact standalone, tagged/colored spans, character frequencies, and multi-word phrases) and enriches `glossary.json` `translation_variants` with `rationale="RU патч v2.0"`.
- **Interface Localization (i18n) & Language Menu**: Comprehensive localization across all application chrome using `tr()`. The **Language** menu dynamically lists all active translations (`locales/*.json`) with their native titles (e.g. English, Українська, 日本語, etc.). Missing keys fall back gracefully to English. Supported by an automated batch translation pipeline (`tools/i18n-translate/`) with Gemini Web2API proxy integration.
- **Compact 2-Row Editor Header & Vertical Height Alignment**:
  - Re-engineered `header_grid` above the translation editor into a compact 2-row layout (Row 0: `Window:` + `Chapter:` on left, Navigation/AI/Fix actions on right; Row 1: `Speaker:` on left, Font/Max-width/Apply on right), raising text editing areas by ~35px and eliminating excessive top margin.
  - Implemented dynamic vertical alignment (`HeaderSyncFilter`) synchronizing the top edge of text editing areas across left (source tabs) and right (editable translation) panels (`left_header.height = right_header.height - tab_bar.height`).
  - Aligned the middle panel revert string button (`→`) directly with Line 1 of both text editors.

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
- **AI Chat Window with Queue, Context Reset, Auto-Scroll & Diagnostics**:
  - Multi-tab AI Chat window with real-time token/character counts and live elapsed generation timer.
  - Queues subsequent user messages with interactive `[In Queue]` badges and a "Cancel Queue" action banner while generation is in progress.
  - Features an active "Stop" button and preserves partial responses on network timeouts, interruptions, or cancellations with clean Markdown formatting and error indicators.
  - Dynamic button width calculation ensuring Ukrainian action labels (`Надіслати`, `Зупинити`) fit cleanly across diverse font scaling and high-DPI setups.
  - Intelligent auto-scrolling that follows streaming responses in real time, with viewport movement to incoming responses and auto-scroll pause when reading earlier chat history.
  - Dedicated "Reset Context" (`Скинути контекст`) button to clear conversation memory and start a fresh dialogue without previous turns.
  - Dual "Scroll to Bottom" (`↓ В самий низ`) controls: a top toolbar jump button and a floating circular scroll button that appears whenever scrolled up.
  - Reliable multi-turn dialogue memory ensuring previous messages and system instructions are consistently sent to stateless LLM backends (Gemini Web2API, OpenAI, Ollama).
  - Independent top-level OS window architecture with full Windows `Alt+Tab` task switcher and taskbar integration.
- **Strict Orthography, Transliteration & Transcription Rules (Ukrainian & Japanese Kovalenko System)**:
  - System prompts and glossary templates enforce Ukrainian Orthography (2019) standards: rendering plosive sound [g] (letter G) strictly as Ukrainian **Ґ / ґ** (*Hogwarts* -> **Гоґвортс**, *Ganon* -> **Ґанон**, *Gandalf* -> **Ґандальф**) instead of Russian calques with Г/Х, and sound [h] strictly as Ukrainian **Г / г** (*Harry* -> **Гаррі**, *Hyrule* -> **Гайрул**).
  - Enforces strict canonical unification for the Zelda `Hy-` [haɪ] root: **Hyrule** -> **Гайрул**, **Hylia** -> **Гайлія**, **Hylian** -> **гайлійський / гайлієць** (including all landmarks, fish, and fauna: *Lake Hylia* -> **озеро Гайлія**, *Hylian shield* -> **гайлійський щит**, *Hyrule Bass* -> **гайрульський окунь**, *Hylian Loach* -> **гайлійський в'юн**), eliminating Russian-style "Хайрул" and desynchronized "Гілія / Хілія / гілійці".
  - Enforces the Ukrainian practical transcription of Japanese (Kovalenko system): **shi** -> **сі** (*Yoshi* -> **Йосі**), **chi** -> **ті** (*Hitachi* -> **Хітаті**), **tsu** -> **цу**, **ji** -> **дзі** (*Fuji* -> **Фудзі**), plosive g -> **ґ**, and zero tolerance for Russian-style Polivanov forms (*ши*, *чи*, *джи*).
  - Integrated into global prompts, all individual game plugins (*The Minish Cap*, *The Wind Waker*, *Twilight Princess*, *Pokémon FireRed*, *Plain Text*, *Default Plugin*), batch/single translation instructions, and AI Chat via dynamic language blocks (`[IF_TARGET_LANG: Ukrainian]`).
- **Multi-Agent Translation Consilium (Translator + Inline Arbiter/Editor)**:
  - Integrates a collaborative multi-agent translation workflow: the primary translator generates the target text while an inline Editor/Arbiter supervisor reviews and polishes the draft.
  - The Arbiter verifies terminology against the active glossary, enforces narrative voice consistency, and refines phrasing while keeping layout constraints and control tag variations non-blocking (e.g. `[PLAYER]` being translated or replaced with the protagonist name like "Лінк").
- **Two-Phase Chronological & Semantic Pipeline (Story First ➔ Remaining Blocks)**:
  - Intelligently classifies all project text items (`classify_project_items`) into chronological **Story Dialogue** (using MemePalace `script_line` mappings and story block heuristics) and **Semantic / System Blocks** (menus, UI, item descriptions, mini-games, shops).
  - Phase 2 runs after the story text is settled; both phases use the same glossary and per-line context.
- **Top AI Batch Translation Buttons & Interactive Modes Dialog**:
  - Added a prominent **AI** action button directly on the main toolbar (`main_toolbar`) and in the blocks panel header (`block_header_layout`) opening the comprehensive **AI Batch Translation Dialog** (`AIBatchTranslationDialog`).
  - The dialog clearly presents and explains each pipeline mode (Story First, Remaining Blocks, Full Pipeline, Chronological Legacy) with detailed cards, step badges, and non-blocking rules guidance.
  - Cleaned up the block tree context menu: removed whole-project batch translation actions from individual block menus, ensuring block context menus contain only actions relevant to the selected block (`AI: Translate Block` and `AI: Build Glossary`), while providing an `AI Batch Translation...` action on empty space.
- **Dedicated AI Batch Translation Submenus & Localization Pipeline Wizard**:
  - Organized all batch translation operations into dedicated `AI Batch Translation ➔` submenus in both the project tree context menu and the main `Tools` menu (`Translate Story First`, `Translate Remaining Blocks`, `Run Full Pipeline (Story ➔ Semantic)`, and `Translate All Blocks (Chronological)`).
  - Embedded direct action triggers into Step 5 ("Translate the text") of the Localization Pipeline Wizard (`PipelineWizardDialog`), allowing translators to initiate each phase with a single click.

---

### 6. Glossary & Terminology Subsystem
- **One Automatic Glossary Route**: Structural game data and Script Markup seeds, incremental AI discovery, context descriptions, and translation variants now run in one uninterrupted pass. The project defaults to all blocks but exposes a per-block checklist, keeps confirmed user choices intact, and offers an explicit full re-scan when fresh evidence is needed.
- **Separate AI Review Notes**: The glossary keeps its clean translation description separate from sweep observations, alternative rationales, speaker-identity evidence, and conservative possible-duplicate proposals. Ambiguities remain actionable without blocking text translation.
- **Backlog Report Instead of “Done”**: Completion reports show review, ambiguity, untranslated, undescribed, and duplicate counts with direct actions to review the glossary or continue in the editor.
- **High-Performance Highlighting**: Evaluates text for glossary occurrences instantly using the **Aho-Corasick** algorithm.
- **Slavic Morphological Matcher**: Uses stemming algorithms to highlight inflected forms of terms (e.g. matching "Меча", "Мечем" for "Меч").
- **Dynamic Tabbed Interface (`QTabWidget`)**: Categorizes glossary databases into separate semantic tabs ("Characters", "Items", "Locations", etc.) with an "All" master index.
- **Organize via AI Wizard**:
  - Stage 1: Scans terms and suggests 4 to 7 thematic categories.
  - Stage 2: Displays checkable UI, dynamically classifies all entries, writes back to the markdown database, and reloads active tabs.
- **HTML Tooltips & Font Scaling**: Renders rich markdown glossary descriptions on hover (supporting lists, line breaks, bold styling). Configurable `tooltip_font_size` SpinBox (6px to 32px) scales tooltips globally.
- **External Wiki Reference Integration**: Directly opens relevant lore/character search pages (e.g. Zelda Wiki via `BaseGameRules.get_external_reference_url`) using an interactive "Wiki ↗" button next to the original term.
- **Unified Side-by-Side Term Editing**: Presents the original term (read-only, selectable) alongside the editable translation on a single line, paired with a compact confirmation button.
- **Collapsible Section Panes**: Notes/Description, AI Notes, and Occurrences sections feature toggleable collapsible headers (`[▼]/[▶]`) to reclaim vertical space and minimize visual clutter.
- **Granular Occurrence Filtering**: Features independent checkboxes to filter term occurrences by Mentions (direct text matches) and Spoken lines (dialogue spoken by character).
- **Relocated "Needs Review" Filter**: The unconfirmed terms filter checkbox has been relocated from the search bar directly beneath the terms and categories table (`_tab_widget`), preserving all vertical space for term details while visually grouping it with the table it filters.
- **Context-Enriched AI Discussion**: Opens an interactive AI chat window directly from the entry toolbar or table context menu with comprehensive context automatically compiled into the prompt (category, original term, translation, external wiki reference link, confirmed speaker codes, description notes, and in-game dialogue occurrences with script line quotes).
- **Reference Patch Occurrences Context**: For every dialogue occurrence, the glossary dialog displays the complete original source message and the full corresponding reference record for that (block, string) without trimming surrounding lines. The occurrence is highlighted within the full original message, and matching reference terms are highlighted within the reference lines while preserving all line breaks and HTML formatting. The `RU:` preview is shown only when the loaded reference is explicitly identified as Russian (other loaded reference languages provide context to the AI translator without being labeled as RU). If the reference record is absent or empty, the `RU:` block is omitted.
- **Force Retranslate with AI & Safe Backup**:
  - Dedicated **"Force Retranslate..."** button in the Glossary dialog bottom toolbar (styled with distinct orange highlight `#ea580c`) allowing users to re-translate all glossary entries using AI with the latest prompts, orthography, and transcription rules.
  - Automatically creates a durable safety backup copy (`glossary.json.bak`) prior to starting.
  - Overwrites existing translations with freshly generated AI proposals, sets entry status to `translated` (flagged for review), and hot-reloads the glossary dialog in real time upon completion.
  - Also integrates a **"Force re-translate already translated terms"** checkbox option in the Glossary Build / Prepare dialog for full pipeline re-runs.
- **Unified Term Save Button & Dedicated Action Row**:
  - A clean, prominent **Save** button (`_save_term_button`), **Confirm translation** (`_confirm_button`), and **Discuss with AI…** (`_discuss_variant_button`) organized on a dedicated action row directly below the translation input field.
  - Gives the translation input field full unobstructed horizontal width (up to 400–550px+), allowing long character names and localized phrases to fit comfortably without clipping or premature scrolling.
  - The Save button automatically lights up with a vivid blue accent (`#2563eb`) whenever any field (translation, description, or notes) has uncommitted changes, saving the record in place without navigating away.
  - Fully supports `Ctrl+S` from anywhere in the dialog.
  - Removed clumsy, cluttered save buttons from the collapsible section headers (`[▼] Description` and `[▼] AI Notes`), keeping pane titles focused and distraction-free while retaining full backward compatibility.
- **Unsaved Changes Navigation Protection (Pop-Up)**:
  - Automatically prompts the user (`Save` / `Discard` / `Cancel`) when selecting another term row in the table, switching category tabs, or closing the dialog with uncommitted edits, protecting custom notes and translations from accidental loss.
- **Proposed Variant Application & Double-Click Support**:
  - Double-clicking any proposed AI translation variant in the list or clicking the **"Apply selected variant"** button instantly applies the candidate into the translation editor, updates rendered notes, and bolds the active variant in the list without advancing to the next entry.
  - Advancing to the next term is strictly decoupled and happens only when explicitly confirming via the **"Confirm translation"** button, allowing full review and manual adjustments before settling the entry.
- **Reference Variant & Notes Context Isolation**:
  - In the proposed variants list, reference translations from external patches (e.g. `RU patch v2.0`) are visually isolated with distinctive cyan styling and italic font, clearly marked for contextual reference. Double-clicking and applying via button are safely disabled on reference items.
  - In AI Notes, reference variants are separated from target translation choices under an explicit "Russian reference translation (for context)" section. If no direct variant exists, the counterpart reference text from the first mention string is automatically provided as reference context.
- **Picoripi Companion (Mobile Web PWA & Synchronization Server)**:
  - Full mobile web application (PWA) and synchronization server allowing you to open your translation glossary on your smartphone (iOS Safari / Android Chrome) or tablet.
  - Installable as a native-feeling standalone app via "Add to Home Screen".
  - Features an ergonomic **"✓ Confirm & Next"** workflow to rapidly approve terms from your phone with automatic navigation to the next unreviewed entry, touch-optimized controls (44×38px touch targets, tap animations), a minimalist glowing status indicator dot, and streamlined project header.
  - Full fidelity: horizontal category tabs, live debounced search, "Needs review" filter, interactive candidate variant cards, dynamic lore description with real-time `{{TERM}}` substitution, editable user notes, and in-game dialogue occurrences with English quotes and reference translations.
  - **Smart Bidirectional Synchronization**: Smart diff-based two-way sync comparing per-entry modification timestamps (`updated_at`). Automatically pulls newer reviewed terms from mobile Companion and pushes local edits/additions to the server with automatic backup creation (`.bak`).
  - **Visual Synchronization Dialog**: When opening the glossary, launching sync from the toolbar/menu, or closing the application/project, displays a dedicated synchronization progress window (`CompanionSyncDialog`) showing live status ("Connecting to Companion server…", "Analyzing local and remote changes…", "Pushing local updates to Companion server…") with an animated progress bar and offline bypass ("Skip & Work Offline" / "Skip & Close").
  - **Exit & Shutdown Synchronization**: Automatically synchronizes the glossary upon closing the application (`File -> Exit` or window close `X`), ensuring that all changes made on the local PC are immediately pushed to the Companion cloud with automatic shutdown completion.
  - **Interactive Conflict Resolver**: In rare cases of simultaneous conflicting changes on the same term, opens `CompanionConflictDialog` allowing users to inspect local vs remote translations and notes side-by-side and choose individual or bulk ("Keep All Local" / "Keep All Remote") resolutions.
  - 1-click manual desktop synchronization via the **`[☁ Companion Sync...]`** button in `GlossaryDialog` with automatic backup protection (`.bak`).
  - Automated deployment on Ubuntu servers via Docker Compose (`docker compose up -d`) or native systemd service (`install_ubuntu.sh`). See [companion/README.md](companion/README.md).



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

### Gemini Web2API (recommended)

Glossary builds and block translation need **many** LLM calls. The supported way to do that at scale is **Gemini Web2API**: a local process that exposes `http://127.0.0.1:8081/v1` and rotates signed-in Gemini web accounts. Its dashboard (**WebTOP**, `http://127.0.0.1:8081/`) is where you add accounts and watch cooldowns.

1. Start the proxy (`run.bat` in the `gemini-web2api` checkout).
2. In Picoripi: **Settings → Preferences → AI Translation** → Active Provider **OpenAI Compatible**, Endpoint `http://127.0.0.1:8081/v1`, model `gemini-3.7-flash`, timeout **180 s**, Parallel Requests **4–8** (not higher than the number of Active accounts).
3. **Test Provider**, then **Save Preset**.
4. AI Glossary should reuse the translation key.

Full steps, failure cases, and what Picoripi does *not* store (cookies stay in the proxy): [Wiki: Gemini Web2API](docs/wiki/5_Gemini_Web2API.md).

### Other providers

Configure these in the same **AI Translation** tab:
- **OpenAI Compatible**: OpenAI, OpenRouter, Llama.cpp, or any `/v1` endpoint (including Web2API).
- **Google Gemini API**: Official Google key. Leave Base URL empty. Optional Base URL can also point at Web2API (`http://127.0.0.1:8081/v1`) without a Google key.
- **Ollama Chat API**: Local models at `http://localhost:11434`.
- **Perplexity API**: Perplexity chat models.
- **ChatMock**: ChatGPT web proxy — [docs/chatmock_setup.md](docs/chatmock_setup.md).

### Core AI Capabilities
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

To update the knowledge graph after code changes (AST-only, no API key, no cost):
```bash
graphify update .
```
`.graphifyignore` keeps tests, locales, archives and markdown out of the graph. How agents query it is defined
once, in `.agents/rules/graphify.md`.

Output is written to `graphify-out/`:
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
