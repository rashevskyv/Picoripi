from pathlib import Path
APP_VERSION = "0.3.047"



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
