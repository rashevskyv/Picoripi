"""Okami (PlayStation 2, USA): the message containers of the disc's AFS archives as text, one block per file.

The containers are the same as the HD ones (``plugins.okami_hd``), with the same text. The build writes a new disc image
(``plugins.okami_ps2.build``): the changed entries go into their AFS archives, and the archive is moved to the end of the
image when it grows past the sectors after it. The build is not booted in an emulator yet (no PS2 BIOS on disk).
"""
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.okami_hd import textfile
from plugins.okami_ps2 import build, unpack
from utils.logging_utils import log_warning

_PLUGIN = "okami_ps2"
TARGET_ID = "ps2_disc_image"


class GameRules(BaseGameRules):
    """Okami (PlayStation 2, USA): English text of the message containers in the AFS archives."""
    ENDIAN = "<"          # byte order of the message containers (the Wii plugin uses ">")

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
        return [{"id": TARGET_ID, "label": tr("PlayStation 2: disc image (ISO)"),
                 "platforms": ["ps2"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_ps2(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Okami PS2 message containers"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        return [textfile.read_text(data, self.ENDIAN)], {"0": "messages"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._last_loaded is None:
            return super().save_data_to_json_obj(data, block_names)
        lines = (data[0] if data else []) or []
        new_bytes, warnings = textfile.write_text(self._last_loaded, list(lines), self.ENDIAN)
        for warning in warnings:
            log_warning(f"{_PLUGIN}: {warning}")
        return new_bytes
