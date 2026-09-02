"""Mixin class for project/plugin settings tab and subtabs.

Composition of specialized plugin settings mixins.
"""
from .plugin_tabs_mixin import PluginTabsMixin
from .plugin_tables_mixin import PluginTablesMixin
from .plugin_paths_mixin import PluginPathsMixin
from .plugin_checkboxes_mixin import PluginCheckboxesMixin
from .plugin_aliases_mixin import PluginAliasesMixin
from .plugin_fontmap_mixin import PluginFontmapMixin


class SettingsPluginMixin(
    PluginTabsMixin,
    PluginTablesMixin,
    PluginPathsMixin,
    PluginCheckboxesMixin,
    PluginAliasesMixin,
    PluginFontmapMixin,
):
    """Mixin class for project/plugin settings tab and subtabs."""


__all__ = ["SettingsPluginMixin"]
