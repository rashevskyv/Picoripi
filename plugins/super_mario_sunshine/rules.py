"""Super Mario Sunshine (GameCube, USA, GMSE01 Rev 0): the BMG message files inside the disc's archives.

The message files are JSystem BMG, the same format as Twilight Princess, so this plugin reuses the Twilight Princess
rules (``plugins.zelda_bmg``) for reading, saving and checks. Unpack extracts the whole disc (as Wind Waker does).
Build targets: ``gc_iso`` (a new disc image) and ``port_pack`` (the mods/uk overlay for the PC and Switch ports).
The European disc (GMSP01) is the reference: five languages beside each US message (``reference.py``, D37).

The game's text is one byte per character. ``translation_map.json`` (this folder; the project's copy once a project is
open) gives each Ukrainian letter and the apostrophe a code the game's text does not use (D35). A save that holds a
character with no code is refused with the character and the message; nothing is written as '?'.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from core.project_library import images
from plugins.common.disc_source import write_source_mark
from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

from . import build, reference
from .dol_text import FORMAT as DOLSTR_FORMAT, STRINGS as DOL_STRINGS, is_text_document

GAME_ID = "GMSE01"
REVISION = 0


class UnmappedCharacter(ValueError):
    """A character the game's one-byte text has no code for."""

    def __init__(self, char: str):
        super().__init__(char)
        self.char = char


class GameRules(TwilightPrincessRules):
    """Super Mario Sunshine (GameCube, USA)."""

    data_dir = os.path.dirname(os.path.abspath(__file__))   # translation_map.json: the Cyrillic codes

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

    def encode_string_with_mapping(self, s: str) -> str:
        """``s`` with each Ukrainian letter on its code. Raises UnmappedCharacter for a character with no one-byte code,
        or one whose code belongs to a Ukrainian letter (it would show as that letter)."""
        self.load_translation_map()
        out = []
        for char in s:
            code = self.translation_map.get(char)
            if code is None:
                if char in self.reverse_translation_map:
                    raise UnmappedCharacter(char)
                code = char
            try:
                if len(code.encode("cp1252")) != 1:
                    raise UnmappedCharacter(char)
            except UnicodeEncodeError:
                raise UnmappedCharacter(char) from None
            out.append(code)
        return "".join(out)

    def _refuse_unmapped(self, text: str, where: str, encode) -> Any:
        try:
            return encode(text)
        except UnmappedCharacter as error:
            raise ValueError(tr("{0}: the character {1} has no code in the game's text", where, repr(error.char))) from None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        texts = data[0] if data and isinstance(data[0], list) else []
        if self._dolstr_save and self._dolstr_ids is not None:
            rooms = {ident: room for ident, _offset, room, _digest in DOL_STRINGS}
            rows = [{"id": ident,
                     "text": self._refuse_unmapped(texts[index], f"main.dol/{ident}", self.encode_string_with_mapping)
                     if index < len(texts) else "", "room": rooms[ident]} for index, ident in enumerate(self._dolstr_ids)]
            return json.dumps({"format": DOLSTR_FORMAT, "strings": rows}, ensure_ascii=False, indent=1).encode("utf-8")
        # Checked before the BMG save, which turns any error into an empty file.
        bmg = self.last_loaded_bmg
        for index, text in enumerate(texts):
            message = bmg.messages[index] if bmg and index < len(bmg.messages) else None
            self._refuse_unmapped(text, tr("Message {0}", getattr(message, "id", index)), self.editor_text_to_msg_content)
        if bmg is not None:
            bmg.encoding = "cp1252"     # one byte per character; dolpic1.bmg is read as Shift-JIS, its text is replaced
        return super().save_data_to_json_obj(data, block_names)

    def get_display_name(self) -> str:
        return "Super Mario Sunshine"

    # Reference languages: the European disc (GMSP01), unpacked into the project (reference.py).
    def get_reference_language_label(self) -> str:
        return reference.LANGUAGES[0][1]

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        return self.load_multi_reference(patch_path, block_names).get(self.get_reference_language_label(), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """The European languages of a ``reference_eu`` folder for each block, by file and message number. A disc
        image gives nothing here: ``unpack_reference`` unpacks it first, on a worker thread."""
        root = Path(patch_path)
        if not root.is_dir():
            return {}
        blocks = {}
        for key in block_names or {}:
            try:
                manager = self.mw.project_manager
                block = manager.project.blocks[self.mw.block_to_project_file_map.get(int(key), int(key))]
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                continue
            blocks[int(key)] = (str(block.source_file).replace("\\", "/"),
                                Path(manager.get_absolute_path(block.source_file)))
        return reference.load_languages(root, blocks, self.get_text_representation_for_editor)

    def unpack_reference(self, path: str, project_dir: str, progress, is_cancelled) -> Optional[str]:
        """The European disc: its message files go to ``<project>/reference_eu``. Any other path is used as it is."""
        if not reference.is_european_disc(path):
            return None
        return reference.unpack(path, project_dir, progress, is_cancelled)

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
        write_source_mark(target_dir, base)
        return done

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def unpack_key_consoles(self) -> List[str]:
        return []   # a GameCube disc only; the Twilight Princess base class reads the Wii key

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
