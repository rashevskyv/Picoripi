from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import MainWindow
from ui.main_window.actions.settings_mixin import MainWindowSettingsActionsMixin
from ui.main_window.actions.tools_mixin import MainWindowToolsActionsMixin
from ui.main_window.actions.tag_alias_mixin import MainWindowTagAliasActionsMixin


class MainWindowActions(
    MainWindowSettingsActionsMixin,
    MainWindowToolsActionsMixin,
    MainWindowTagAliasActionsMixin,
):
    """Main window actions implementation."""
    def __init__(self, main_window: MainWindow):
        """Initialize a new instance."""
        self.mw = main_window
        self.helper = main_window.helper
        from ui.main_window.bfn_actions import BfnActions
        from ui.main_window.mempalace_actions import MempalaceActions
        self.bfn_actions = BfnActions(self.mw)
        self.mempalace_actions = MempalaceActions(self.mw)

