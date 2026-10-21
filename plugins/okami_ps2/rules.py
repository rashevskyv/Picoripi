"""Okami (PlayStation 2, USA): the message containers of the disc's AFS archives as text, one block per file.

The containers are the same as the HD ones (``plugins.okami_hd``), with the same text. Writing text works; a build does
not exist yet: a longer text changes the size of an AFS entry, so the archive and the disc image must be rewritten.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.okami_hd import textfile
from plugins.okami_ps2 import unpack
from utils.logging_utils import log_warning

_PLUGIN = "okami_ps2"


class GameRules(BaseGameRules):
    """Okami (PlayStation 2, USA): English text of the message containers in the AFS archives."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Okami (PlayStation 2)"

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "ps2", "label": tr("PlayStation 2")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return []

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Okami PS2 message containers"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        return [textfile.read_text(data)], {"0": "messages"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._last_loaded is None:
            return super().save_data_to_json_obj(data, block_names)
        lines = (data[0] if data else []) or []
        new_bytes, warnings = textfile.write_text(self._last_loaded, list(lines))
        for warning in warnings:
            log_warning(f"{_PLUGIN}: {warning}")
        return new_bytes
