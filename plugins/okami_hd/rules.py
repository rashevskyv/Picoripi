"""Okami HD (Switch): the English message files as text, one block per file; a translation builds a LayeredFS mod.

A file is a container (``u32 count``, offsets, tags). Its MSD sections hold the dialogue and the menu strings. The
text of each string is shown with its control codes as ``{xxxx}`` tags (see ``charset``). Saving writes only the
strings that changed, and only where the record keeps its byte length (see ``textfile``); a change that cannot be
written is reported and the original bytes of that record stay.

Not done yet: the Ukrainian glyph table, the font atlas (``etc/core_30.bin``) and the textures with text.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.okami_hd import build, textfile, unpack
from utils.logging_utils import log_warning

_PLUGIN = "okami_hd"


class GameRules(BaseGameRules):
    """Okami HD, Switch base game (English text)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._role = "source"
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Okami HD (Switch)"

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        """The Okami HD Switch image (the base title id 0100276009872000)."""
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        """The English message files of the base game (``unpack.py``)."""
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch"]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": tr("Nintendo Switch")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "switch_layeredfs", "label": tr("Switch: Atmosphere LayeredFS mod"),
                 "platforms": ["switch"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "switch_layeredfs":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin", ".dat", ".pac"), "bytes", "Okami HD message containers"), *DEFAULT_FORMATS]

    def set_load_role(self, role: str) -> None:
        self._role = role

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
