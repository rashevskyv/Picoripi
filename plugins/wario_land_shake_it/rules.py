"""Wario Land: Shake It! (Wii, USA) plugin: message text blocks, one block per BMG file.

The project's files are the text documents ``MessageData/*.json`` written by the unpack. Each document is one
block: one text per message, in file order. A save writes the document back with the new texts; the message count and
each message's INF1 attributes stay as the game has them. Build: ``plugins/wario_land_shake_it/build.py``.
Not in this version: the font (Font Editor), textures, the other languages as reference columns, and text-fit checks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import build, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(BaseGameRules):
    """Wario Land: Shake It! (Wii, USA): text blocks of the English message archives."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return "Wario Land: Shake It!"

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".json",), "json", tr("Wario Land: Shake It! message documents"))]

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": unpack.WII, "label": tr("Wii disc (USA)")}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": unpack.WII, "label": tr("Wii")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "wii_riivolution", "label": tr("Wii: Riivolution patch and Dolphin launcher"),
                 "platforms": [unpack.WII], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "wii_riivolution":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_wii_riivolution(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, dict) or json_obj.get("format") != unpack.FORMAT_ID:
            self.reset_runtime_state()
            return [[]], {}
        self._doc = json_obj
        texts = [message["text"] for message in json_obj["messages"]]
        return [texts], {"0": str(json_obj.get("entry", ""))}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._doc is None:
            return {}
        values = data[0] if data and isinstance(data[0], list) else []
        doc = dict(self._doc)
        messages = []
        for index, message in enumerate(self._doc["messages"]):
            new = values[index] if index < len(values) and values[index] is not None else message["text"]
            messages.append({"info": message["info"], "text": str(new)})
        doc["messages"] = messages
        return doc

    def reset_runtime_state(self) -> None:
        self._doc = None
