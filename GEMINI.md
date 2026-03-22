# --- START OF FILE GEMINI.md ---
# GEMINI.md - Project Context for Gemini

This document provides a comprehensive overview of the "Picoripi" project to be used as a working context for Gemini.

## Project Overview

The "Picoripi" (v0.2.11) is a desktop application built with **Python** and **PyQt5**. Its primary purpose is to facilitate the simple, visual, and convenient translation of any texts, specifically optimized for cases with strict length and formatting constraints.

The application is designed to be highly versatile, with features tailored to handling various text constraints, such as character limits, pixel-perfect width calculations (using game-specific or custom fonts), and custom control codes. While it excels at retro game localization, its core architecture is suitable for any structured translation project.

### Core Features

- **Project Management**: The application is moving towards a project-based workflow. A "project" (`.uiproj` file) encapsulates all files and settings for a specific translation effort. A project contains "blocks" (which map to game text files) and allows for virtual "categories" to organize strings.
- **Plugin-Based Architecture**: Game-specific logic is handled by a robust plugin system located in the `plugins/` directory. Each plugin (e.g., `zelda_mc`, `pokemon_fr`) defines its own rules for text parsing, tag handling, font metrics for width calculation, and problem analysis.
- **AI-Assisted Translation**: Integrates with external AI services (OpenAI, Gemini, DeepL) to provide translation suggestions. It uses a glossary system to ensure contextual accuracy and consistency.
- **Specialized UI Components**: Features custom widgets like `LineNumberedTextEdit`, which provides line numbers and visual warnings for text that exceeds the game's displayable width, calculated using game-specific font maps.
- **Tag Management**: Recognizes and provides syntax highlighting for special in-game control codes (e.g., for player names, button icons, text colors).
- **Integrated Spellchecker**: Uses `spylls` (a Hunspell wrapper) for spellchecking within the translation editor.

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

## Codebase Structure & Conventions

The project follows a well-organized, modular structure.

-   `main.py`: The application entry point. Contains the `MainWindow` class which acts as the central orchestrator.
-   `core/`: Contains core business logic and data models, including `project_manager.py`, `settings_manager.py`, and `spellchecker_manager.py`.
-   `handlers/`: Holds specialized classes that manage specific functionalities like file operations (`AppActionHandler`), text editing (`TextOperationHandler`), and AI translation (`TranslationHandler`).
-   `ui/`: Manages the overall UI setup (`ui_setup.py`) and high-level UI logic.
-   `components/`: Contains custom, reusable PyQt5 widgets like the text editors and dialogs.
-   `plugins/`: Contains the game-specific plugin modules. Each plugin is a self-contained package with its own rules, configuration, and font maps.
-   `utils/`: Contains utility functions, constants, and the logging setup.
-   `CLAUDE.md`, `PLAN.md`: Detailed internal documentation files describing architecture and future plans.

### Key Development Conventions

-   **State Management**: The `MainWindow` class uses a large number of boolean flags (e.g., `is_loading_data`, `is_programmatically_changing_text`) to control application state and prevent recursive event handling. When modifying the code, it is critical to respect these flags.
-   **Delegation**: The `MainWindow` delegates most of its logic to the various handlers in the `handlers/` directory. This promotes a clean separation of concerns.
-   **Logging**: All diagnostic output is managed by `utils/logging_utils.py` and is written to `app_debug.txt` in the project root. Use `log_info()`, `log_warning()`, and `log_error()` for logging.
-   **Plugin Interface**: The `plugins/base_game_rules.py` file defines the abstract base class that all game plugins must inherit from.

Розмовляй та пиши волксру та плани kbit українською

Весь текст в програмі має бути англійською мовою

Середовище виконання - powershell, то ж використовуй відповідні команди 