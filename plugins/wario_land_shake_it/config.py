"""Problem definitions and defaults of the Wario Land: Shake It! plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "WLS"

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {}},
)
