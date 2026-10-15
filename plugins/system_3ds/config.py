"""Problem definitions and defaults of the 3DS system plugin.

Only the width check is on. The plugin's analyzer reports it as the owner's validate.py does: a string whose widest
line is wider than its budget (budgets.json). A string without a budget has no limit, so config.json sets the global
limits far past any 3DS screen (no invented limit). The generic dialog rules (short lines, sublines, spacing) do not
apply to menu text.
"""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SYS3D"
WIDTH_PROBLEM = f"{PLUGIN_PREFIX}_WIDTH_EXCEEDED"

PROBLEM_DEFINITIONS, _DETECTION, _AUTOFIX = generate_base_config(PLUGIN_PREFIX)
DEFAULT_DETECTION_SETTINGS = {key: key == WIDTH_PROBLEM for key in _DETECTION}
DEFAULT_AUTOFIX_SETTINGS = {key: False for key in _AUTOFIX}
