"""Settings dialog: all tab-building mixins in one class."""
from .general_spelling_mixin import SettingsGeneralSpellingMixin
from .plugin_mixin import SettingsPluginMixin
from .ai_mixin import SettingsAiMixin
from .logging_mixin import SettingsLoggingMixin
from .companion_mixin import SettingsCompanionMixin

class SettingsDialogUiMixin(
    SettingsGeneralSpellingMixin,
    SettingsPluginMixin,
    SettingsAiMixin,
    SettingsLoggingMixin,
    SettingsCompanionMixin
):
    """Facade class aggregating all settings subtabs layout setup methods."""
    pass
