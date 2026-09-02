"""UI message helpers for DataStateProcessor."""
from typing import Any, List, Optional

from utils.logging_utils import log_error, log_info, log_warning


class UiMsgMixin:
    """UI message and source-string helpers."""

    def _show_message(self, title: str, text: str, type: str = "info"):
        """Internal helper to show message."""
        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            self.mw.ui_provider.show_message(title, text, type)
        else:
            if type == "error":
                log_error(f"{title}: {text}")
            elif type == "warning":
                log_warning(f"{title}: {text}")
            else:
                log_info(f"{title}: {text}")

    def _ask_yes_no(self, title: str, text: str, default_yes: bool = True) -> bool:
        """Internal helper to ask yes no."""
        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            return self.mw.ui_provider.ask_yes_no(title, text, default_yes)
        return default_yes

    def _get_string_from_source(self, block_idx: int, string_idx: int, source_data: List[Any], source_name: str) -> Optional[str]:
        """Internal helper to get the string from source."""
        if not source_data:
            return None
        if not (0 <= block_idx < len(source_data)):
            return None

        current_block = source_data[block_idx]
        if not isinstance(current_block, list):
            return None

        if not (0 <= string_idx < len(current_block)):
            return None

        value = current_block[string_idx]
        return value
