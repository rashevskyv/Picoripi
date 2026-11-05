"""Lunar: Silver Star Story Remastered (Switch) plugin: the Japanese dialogue as the source, English as the reference.

The project's source is the unpacked folder (``unpack.py``): ``data.cpk`` whole, ``FIL/TEXTnnn.DAT`` (Japanese, the
source of the project) and ``FIL_us/TEXTnnn.DAT`` (English, the reference column). One project file is one dialogue
file; its strings are numbered in file order (``text.py``). The translation file is UTF-8 (``text.py``); the build writes
the translated strings into the English slots and patches ``data.cpk`` for LayeredFS (``build.py``).
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.lunar_sssc.tag_manager import TagManager
from utils.logging_utils import log_debug

from . import build, text, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

SOURCE_RE = re.compile(r"^FIL/TEXT(0\d\d|100)\.DAT$")
ENGLISH_LABEL = "English (EN)"


class GameRules(BaseGameRules):
    """Lunar: Silver Star Story Remastered (Switch, title 0100DCD01E9EE000)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True
    display_name = "Lunar: Silver Star Story Remastered"

    def get_display_name(self) -> str:
        return self.display_name

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat",), "bytes", "Lunar text data"), *DEFAULT_FORMATS]

    def includes_source_file(self, rel_path: str) -> bool:
        return bool(SOURCE_RE.match(rel_path))

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        lines = text.read_translation(data)
        if lines is None:
            try:
                lines = text.strings_of(data, japanese=True)
            except (ValueError, IndexError) as error:       # the script errors are ValueErrors
                log_debug(f"{self.problem_prefix}: not a Lunar text file ({error})")
                return [[]], {}
        return [lines], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        lines = [str(line) for line in (data[0] if data else [])]
        return text.translation_bytes(lines)

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    # -- reference: the English file of the unpacked folder --------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return ENGLISH_LABEL

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """The English line of each Japanese string, for every project block that has an English file.

        ``patch_path`` is the unpacked folder. A block is matched by its file name (``TEXT001``).
        """
        root = Path(patch_path or "")
        if not root.is_dir():
            return {}
        result: Dict[Tuple[int, int], str] = {}
        for block, name in self._block_pairs(block_names):
            stem = name.replace("\\", "/").split("/")[-1].split(".")[0]
            english, japanese = root / "FIL_us" / f"{stem}.DAT", root / "FIL" / f"{stem}.DAT"
            if not (english.is_file() and japanese.is_file()):
                continue
            lines = text.reference_for_japanese(english.read_bytes(), japanese.read_bytes())
            for index, line in enumerate(lines):
                if line:
                    result[(block, index)] = line
        return {self.get_reference_language_label(): result} if result else {}

    @staticmethod
    def _block_pairs(block_names) -> List[Tuple[int, str]]:
        if isinstance(block_names, dict):
            return [(int(key), str(value)) for key, value in block_names.items()]
        if isinstance(block_names, (list, tuple)):
            return [(index, str(value)) for index, value in enumerate(block_names)]
        return []

    # -- source, unpack and build (LayeredFS) ----------------------------------

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return unpack.identify(path)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": build.TARGET, "label": tr("Switch mod (LayeredFS)"), "platforms": ["switch"],
                 "kind": "layeredfs"},
                {"id": build.PC_TARGET, "label": tr("PC game folder (data.cpk)"), "platforms": ["pc"],
                 "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == build.TARGET:
            return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == build.PC_TARGET:
            return build.build_pc(source_dir, translation_dir, output_dir, progress, is_cancelled)
        raise ValueError(f"Unknown build target: {target_id}")
