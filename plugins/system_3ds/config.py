"""Problem definitions and defaults of the 3DS system plugin.

Only the width check is on, and only a string whose pane box is known (boxes.json) has a limit: the plugin gives it
through ``get_string_layout``. The other strings have none, so config.json sets the global limits far past any
3DS screen (no invented limit). The generic dialog rules (short lines, sublines, spacing) do not apply to menu text.
"""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SYS3D"

PROBLEM_DEFINITIONS, _DETECTION, _AUTOFIX = generate_base_config(PLUGIN_PREFIX)
DEFAULT_DETECTION_SETTINGS = {key: key == f"{PLUGIN_PREFIX}_WIDTH_EXCEEDED" for key in _DETECTION}
DEFAULT_AUTOFIX_SETTINGS = {key: False for key in _AUTOFIX}
