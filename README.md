# Picoripi v0.2.1

A PyQt5-based translation workbench designed for simple, visual, and convenient translation of any texts, especially optimized for cases with strict length and formatting constraints. While it includes robust support for retro game localization, the tool is a versatile environment for any structured translation task.

## Features

- **AI-Assisted Translation**: Context-aware translation with glossary management
- **Custom Font Rendering**: Character width calculation for game-specific display constraints
- **Plugin System**: Game-specific rule systems for different titles
- **Tag Management**: Handle game control codes (player names, button icons, etc.)
- **Multi-line Analysis**: Visual feedback for line width violations
- **Spellchecking**: Integrated spellchecking with custom dictionary support
- **Revert to Original**: Quickly restore original text for individual lines or entire blocks with undo support.
- **Enhanced UI**: Context menus with icons and better visual cues for actions.

## Visual Problem Markers

The application uses colored markers in the line numbers area to indicate structural or length issues in the text.
Some markers might be rendered at **half-height** (for example, the purple Empty Odd Subline marker in Zelda MC tags), which visually signifies that the problem is not critical and relates to an empty line meant for spacing.

### Pokémon FireRed Plugin Colors:
- **Red (Width Exceeded)**: The subline is too wide for the in-game text box bounds. Text will likely bleed out of the display.
- **Green (Short Line)**: The subline is too short. It does not end with punctuation and there is actually enough space to fit the first word of the following line, meaning the wrapping is suboptimal.
- **Orange (Empty Subline)**: There is an entirely empty line (created by consecutive newlines), which might waste text box space if not intended.
- **Blue (Single Word Subline)**: The subline consists only of one word. This usually looks awkward in the game dialog.
- **Yellow (Tag Warning)**: A game control code tag inside `{}` or `[]` is either unknown, misspelled, or lacking a closing bracket.

### Plugin Customization (descriptions & markers)
All labels and descriptions for these markers are defined in the plugin's `config.py` file. You can customize them there:
- **`PROBLEM_DEFINITIONS`**: A dictionary mapping problem IDs to their names, descriptions, colors, and priorities. These appear when you hover over the number area or the text with errors.
- **`COLOR_MARKER_DEFINITIONS`**: A dictionary for manual markers (red, green, blue). You can change their descriptions here to match your workflow (e.g., "Red" -> "Needs Review").

Descriptions from these dictionaries will appear as **tooltips** throughout the application (in the block list, editor view, and line number area).

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
   # OpenAI API Keys
   # Get your key from https://platform.openai.com/api-keys
   OPENAI_API_KEY=your_openai_api_key_here

   # Font Tool OpenAI Key (if different from main)
   # If empty, will use OPENAI_API_KEY
   FONT_TOOL_OPENAI_API_KEY=

   # Gemini API Key
   # Get your key from https://aistudio.google.com/app/apikey
   GEMINI_API_KEY=your_gemini_api_key_here

   # DeepL API Key (optional)
   # Get your key from https://www.deepl.com/pro-api
   DEEPL_API_KEY=
   ```

3. **Important**: The `.env` file is excluded from git to protect your API keys. Never commit this file.

### 4. Run the Application

#### Windows
```bash
run.bat
```

The `run.bat` script automatically creates a virtual environment (`venv`) if it doesn't exist, installs dependencies, and launches the application.

#### Manual Start
```bash
python main.py
```

## Supported Games

The application uses a plugin system to support different games:

- **Zelda: Minish Cap** (`zelda_mc`)
- **Zelda: The Wind Waker** (`zelda_ww`)
- **Pokemon FireRed** (`pokemon_fr`)
- **Plain Text** (`plaintext`) - Generic text files

## Project Structure

```
jsonreader/
├── main.py                 # Application entry point
├── core/                   # Core functionality
│   ├── settings_manager.py
│   ├── translation/        # AI translation providers
│   └── ...
├── handlers/               # Business logic handlers
├── ui/                     # UI components
├── components/             # Custom widgets
├── plugins/                # Game-specific plugins
│   ├── zelda_mc/
│   ├── zelda_ww/
│   ├── pokemon_fr/
│   └── plaintext/
├── resources/              # Assets and resources
│   └── spellchecker/       # Dictionary files
├── .env                    # Your API keys (not in git)
├── .env.example            # Template for .env
└── requirements.txt        # Python dependencies
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guide and architecture documentation
- **[PROJECT_MANAGER_README.md](PROJECT_MANAGER_README.md)** - Project management features

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development documentation including:
- Architecture overview
- Plugin development
- Adding new game support
- Code organization

## Plugins and Extensibility

The workbench is highly modular. Each plugin in the `plugins/` directory is a self-contained unit that defines:
1. **Rules (`rules.py`)**: Inherits from `BaseGameRules`. Manages tag parsing, pasted text processing, and UI actions.
2. **Configuration (`config.py`)**: Defines constants, problem types, and marker descriptions.
3. **Fonts (`fonts/` directory)**: Contains JSON font maps used for pixel-perfect width calculations.
4. **Tag Logic (`tag_manager.py`, `tag_logic.py`)**: Handles game-specific control codes and formatting.

To add a new game:
1. Create a new directory in `plugins/`.
2. Implement your rules by inheriting from `BaseGameRules`.
3. Define your font maps and control codes.

## Logs

Application logs are written to `app_debug.txt` in the project root directory.

## License

[Add your license here]
