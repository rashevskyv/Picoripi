"""Metal Gear Solid -- Master Collection Version (PC Steam, Switch) plugin.

The collection runs the PlayStation game (USA) in M2's emulator, so the game's own text is the PlayStation
text: this class reuses the Metal Gear Solid (PlayStation) rules for it -- codec calls, subtitles, scripts,
program strings -- and adds M2's own text: the PSB files of its menus, messages, credits and Master Book
(``m2/text/**/*.psb``), English lines only, saved as UTF-8 (M2's fonts draw Cyrillic letters themselves).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from plugins.metal_gear_solid_ps1.rules import GameRules as PlayStationRules
from utils.logging_utils import log_debug

from . import psb_text

_M2_ROLE = ("Menu text", "A line of M2's menus, messages, credits or Master Book (the collection around the "
                         "PlayStation game); keep the codes like #{color,...} and <b> as they are.")


class GameRules(PlayStationRules):
    """Metal Gear Solid (Master Collection Version, USA game; PC Steam and Switch).

    The source folder is the workspace's ``source`` (``1_unpack.bat``): the PlayStation files of the
    PlayStation plugin (``SLUS_005.94`` is the program as M2 loads it) plus ``m2/text/**/*.psb``.
    """

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._psb_lines: List[Tuple[tuple, str]] = []
        self._places: Dict[tuple, Any] = {}       # the last file asked about: (path, mtime) -> its lines

    def get_display_name(self) -> str:
        return "Metal Gear Solid (Master Collection)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".gcx", ".subs", ".94", ".bin", ".psb"), "bytes", "Metal Gear Solid data"),
                *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if isinstance(json_obj, (bytes, bytearray)) and psb_text.is_psb(json_obj):
            data = bytes(json_obj)
            self._last_loaded = data
            try:
                self._psb_lines = psb_text.lines(data)
            except (ValueError, IndexError, KeyError, UnicodeDecodeError) as error:
                log_debug(f"metal_gear_solid_mc: not an M2 text file ({error})")
                return [[]], {}
            return [[text for _path, text in self._psb_lines]], {"0": "M2 text"}
        return super().load_data_from_json_obj(json_obj)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is not None and psb_text.is_psb(source):
            return psb_text.build(source, (data or [[]])[0] if data else [])
        return super().save_data_to_json_obj(data, block_names)

    # -- context -----------------------------------------------------------------

    def _psb_place(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Where an M2 text line sits in its file, or None for a PlayStation line."""
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            path = Path(pm.get_absolute_path(block.source_file))
            key = (str(path), path.stat().st_mtime_ns)
            if key not in self._places:
                data = path.read_bytes()
                self._places = {key: psb_text.lines(data) if psb_text.is_psb(data) else None}
            found = self._places[key]
            if found is None:
                return None
            return f"{block.source_file}: {psb_text.where(found[int(string_idx)][0])}"
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"metal_gear_solid_mc: no M2 line behind block {block_idx} string {string_idx}: {error}")
            return None

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        place = self._psb_place(block_idx, string_idx)
        if place is None:
            return super().get_translation_context_for_string(block_idx, string_idx)
        return {"content_role": _M2_ROLE[0], "role_instruction": _M2_ROLE[1], "where": place}

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        place = self._psb_place(block_idx, string_idx)
        if place is None:
            return super().get_message_attributes(block_idx, string_idx)
        return {"kind": "m2", "where": place}
