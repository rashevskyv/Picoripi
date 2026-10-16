"""Silent Hill 1 (Switch port, PAL disc): the Silent Hill (PlayStation) text rules with the PAL font grid.

The text code is ``silent_hill_ps1`` (PAL overlays, PAL item tables). This plugin owns the font and texture lists of
the PAL disc, and the PAL menu and credit strings (``silent_hill_ps1.pal_runs``): the title menu, the option and the
save/load menus, and the credits roll, which have no pointer table the overlay parser reads.
"""
from typing import Any, Optional, Tuple

from plugins.silent_hill_ps1 import pal_runs
from plugins.silent_hill_ps1.rules import GameRules as PsxGameRules
from utils.logging_utils import log_warning


class GameRules(PsxGameRules):
    """Silent Hill 1 (Switch port, PAL disc SLES_015.14)."""

    pal_glyphs = True

    def get_display_name(self) -> str:
        return "Silent Hill 1 (Switch, PAL)"

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[list, dict]:
        windows = pal_runs.windows_for(bytes(json_obj)) if isinstance(json_obj, (bytes, bytearray)) else None
        if windows is None:
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_kind = "disc"
        self._last_loaded = data
        slots = pal_runs.find(data, windows)
        return [[slot.text for slot in slots]], {"0": "menu and credit strings"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source: Optional[bytes] = self._save_source if self._save_source is not None else self._last_loaded
        windows = pal_runs.windows_for(source) if source is not None else None
        if windows is None:
            return super().save_data_to_json_obj(data, block_names)
        out, problems = pal_runs.build(source, (data[0] if data else []) or [], windows)
        for problem in problems:
            log_warning(f"silent_hill1_switch: not written, {problem}")
        return out
