"""Castlevania: Belmont's Curse (Switch, Unity Localization): the English texts of the game as project files.

A project's source folder is ``source``, written by the wizard's unpack: ``message\\<table>.json`` for each of the 45 English
string tables (``tables.py``), and ``ui\\<bundle>.json`` for each interface, room or narration bundle with shown text (``ui_text.py``). A table entry of a narration line may
carry the ``scenes`` and ``speakers`` that use it (``dialogue.py``); the build ignores them.
Each file is one block; each entry is one string. The build writes the edited texts back into the bundles, the fonts
(``fonts.py``) and the catalog (``catalog.py``), as a LayeredFS mod (``build.py``).
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import build, tables, ui_text, unpack


class GameRules(BaseGameRules):
    """Castlevania: Belmont's Curse (Switch, title 0100BA4026E94000; the update is 0100BA4026E94800, version 1.1.0)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        # (kind, table name, ids of the file, metadata of the entries: id -> optional scenes / speakers lists)
        self._file: Optional[Tuple[str, str, List[Any], Dict[Any, Dict[str, List[str]]]]] = None

    def get_display_name(self) -> str:
        return "Castlevania: Belmont's Curse"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".json",), "bytes", "Castlevania texts")]

    # -- wizard: unpack and build ----------------------------------------------

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}, {"id": "update", "label": tr("Update")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        return unpack.identify(path)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_source_subfolder(self) -> Optional[str]:
        return unpack.SOURCE_DIR

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": tr("Nintendo Switch")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "switch_layeredfs", "label": tr("Switch: LayeredFS mod (Atmosphere)"),
                 "platforms": ["switch"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "switch_layeredfs":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        body = json.loads(bytes(json_obj).decode("utf-8"))
        name = str(body["table"])
        items = body["entries"]
        if items and isinstance(items[0]["id"], str):
            self._file = ("ui", name, [str(item["id"]) for item in items], {})
        else:
            ids = [int(item["id"]) for item in items]
            meta = {key: {field: item[field] for field in ("scenes", "speakers") if item.get(field)}
                    for key, item in zip(ids, items)}
            self._file = ("table", name, ids, {key: value for key, value in meta.items() if value})
        return [[str(item["text"]) for item in items]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        kind, name, ids, meta = self._file
        texts = list(data[0]) if data and isinstance(data[0], list) else []
        texts += [""] * (len(ids) - len(texts))
        if kind == "ui":
            return ui_text.table_json(name, list(zip(ids, texts)))
        return tables.table_json(name, list(zip(ids, texts)), meta)

    def reset_runtime_state(self) -> None:
        self._file = None
