"""Application constants: version, settings directory, plugin folders, default tags."""
from pathlib import Path
APP_VERSION = "0.3.155-dev"


# Player tags
EDITOR_PLAYER_TAG = "player"
ORIGINAL_PLAYER_TAG = "original"

# UI Dimensions and Thresholds
DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS = 300
DEFAULT_LINE_WIDTH_WARNING_THRESHOLD = 280

# Font settings
GENERAL_APP_FONT_FAMILY = "Segoe UI"
MONOSPACE_EDITOR_FONT_FAMILY = "Consolas"
DEFAULT_APP_FONT_SIZE = 10

# Theme colors
LT_PREVIEW_SELECTED_LINE_COLOR = "#AEC6E0"
DT_PREVIEW_SELECTED_LINE_COLOR = "#003E6B"

# Settings path in home directory
SETTINGS_DIR = Path.home() / ".picoripi"
SETTINGS_FILE_PATH = str(SETTINGS_DIR / "settings.json")


def plugins_root() -> Path:
    """The ``plugins/`` folder of this installation, whatever the current directory is."""
    return Path(__file__).resolve().parents[1] / "plugins"


def translation_prompts_dir() -> Path:
    """The shared ``translation_prompts/`` folder of this installation, whatever the current directory is."""
    return Path(__file__).resolve().parents[1] / "translation_prompts"


def user_plugin_dir(plugin_name: str) -> Path:
    """Per-user writable data for a plugin. Never write into ``plugins/`` itself."""
    return SETTINGS_DIR / "plugins" / plugin_name


def user_plugin_file_or_shipped(plugin_name: str, filename: str) -> Path:
    """The user's copy of a plugin data file (``user_plugin_dir``) if there is one, else the one the plugin ships."""
    user_file = user_plugin_dir(plugin_name) / filename
    return user_file if user_file.is_file() else plugins_root() / plugin_name / filename
