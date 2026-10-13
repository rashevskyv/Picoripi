"""The game's own preview widget, when its plugin provides one (GameRules.get_custom_preview_widget)."""
from typing import Any, Optional

from PyQt6.QtWidgets import QWidget


def custom_preview_of(main_window: Any) -> Optional[QWidget]:
    """The plugin's preview widget shown in place of the BFN preview, or None."""
    widget = getattr(main_window, "custom_preview_widget", None)
    return widget if isinstance(widget, QWidget) else None
