"""Problem definitions and defaults of the Sly Cooper plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SLY"

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {}},
)
