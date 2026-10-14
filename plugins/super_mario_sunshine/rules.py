"""Super Mario Sunshine (GameCube, USA, GMSE01 Rev 0): the BMG message files inside the disc's archives.

The message files are JSystem BMG, the same format as Twilight Princess, so this plugin reuses the Twilight Princess
rules (``plugins.zelda_bmg``) for reading, saving and checks. Unpack extracts the whole disc (as Wind Waker does).
Build targets: ``gc_iso`` (a new disc image) and ``port_pack`` (the mods/uk overlay for the PC and Switch ports).
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from core.project_library import images
from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

from . import build
from .dol_text import FORMAT as DOLSTR_FORMAT, STRINGS as DOL_STRINGS, is_text_document

GAME_ID = "GMSE01"
REVISION = 0


class GameRules(TwilightPrincessRules):
    """Super Mario Sunshine (GameCube, USA)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._dolstr_ids: Optional[List[str]] = None          # the ids of the executable text being edited
        self._dolstr_save = False                             # the file being saved is that text, not a BMG

    def get_file_formats(self) -> list:
        """The executable's text is a JSON document, one member per file; the BMG and BFN formats are as before."""
        return [FileFormat((".dolstr",), "bytes", "Executable text (main.dol)"), *super().get_file_formats()]

    def prepare_save_context(self, context) -> None:
        self._dolstr_save = str(context.relative_path).lower().endswith(".dolstr")
        if not self._dolstr_save:
            super().prepare_save_context(context)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        if isinstance(json_obj, (bytes, bytearray)) and is_text_document(bytes(json_obj)):
            rows = json.loads(bytes(json_obj).decode("utf-8"))["strings"]
            self._dolstr_ids = [row["id"] for row in rows]
            return [[self.decode_string_with_mapping(row["text"]) for row in rows]], {"0": "Executable text (main.dol)"}
        self._dolstr_ids = None
        return super().load_data_from_json_obj(json_obj)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._dolstr_save and self._dolstr_ids is not None:
            texts = data[0] if data and isinstance(data[0], list) else []
            rooms = {ident: room for ident, _offset, room, _english in DOL_STRINGS}
            rows = [{"id": ident, "text": self.encode_string_with_mapping(texts[index]) if index < len(texts) else "",
                     "room": rooms[ident]} for index, ident in enumerate(self._dolstr_ids)]
            return json.dumps({"format": DOLSTR_FORMAT, "strings": rows}, ensure_ascii=False, indent=1).encode("utf-8")
        return super().save_data_to_json_obj(data, block_names)

    def get_display_name(self) -> str:
        return "Super Mario Sunshine"

    # Project Manager: the GameCube disc (USA) is unpacked whole; the source is the disc's folder tree.
    def get_platforms(self) -> list:
        return [{"id": "gc", "label": tr("GameCube")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found["kind"] != images.KIND_GC or found["game_id"] != GAME_ID or found["revision"] != REVISION:
            return None
        return {"role": "base", "platform": "gc"}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = images.extract(base, target_dir, progress, is_cancelled)
        if done is None or not build.fold_archives(target_dir, is_cancelled):   # each RARC .szs: a folder of members
            return None
        build.write_text_member(target_dir)    # sys/main_strings.dolstr: the executable's English text
        build.write_source_mark(target_dir, base)
        return done

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [
            {"id": "gc_iso", "label": tr("GameCube disc image (ISO)"), "platforms": ["gc"], "kind": "patch"},
            {"id": "port_pack", "label": tr("PC and Switch port pack (mods/uk)"), "platforms": [],
             "kind": "layeredfs"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == "gc_iso":
            return build.build_gc_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == "port_pack":
            return build.build_port_pack(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
