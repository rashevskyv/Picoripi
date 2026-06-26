from .general_spelling_mixin import SettingsGeneralSpellingMixin
from .plugin_mixin import SettingsPluginMixin
from .ai_mixin import SettingsAiMixin
from .logging_mixin import SettingsLoggingMixin

class SettingsDialogUiMixin(
    SettingsGeneralSpellingMixin,
    SettingsPluginMixin,
    SettingsAiMixin,
    SettingsLoggingMixin
):
    """Facade class aggregating all settings subtabs layout setup methods."""
    pass
