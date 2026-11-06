"""Lunar: Silver Star Story dialogue for PS1, Switch and PC: the Japanese text as the source, one translation for all.

The project's source is the unpacked folder (``unpack.py``): ``data.cpk`` whole, ``FIL/TEXTnnn.DAT`` (Remastered
Japanese, the source of the project), ``FIL_us/TEXTnnn.DAT`` (Remastered English) and, when the PS1 disc was added,
``LUNADATA/TEXTnnn.DAT`` (PS1 English). Both English files are reference columns. One project file is one dialogue
file; its strings are numbered in file order (``text.py``). The translation file is UTF-8 (``text.py``); each build
writes the translated strings into the English slots of its platform (``build.py``). The PS1 names, menus, font and
voice stay in the ``lunar_sssc`` plugin.
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
ENGLISH_LABEL = "English (Remastered)"
PS1_LABEL = "English (PS1)"
REFERENCE_FOLDERS = ((ENGLISH_LABEL, "FIL_us"), (PS1_LABEL, unpack.PS1_FOLDER))


class GameRules(BaseGameRules):
    """Lunar: Silver Star Story Remastered (Switch title 0100DCD01E9EE000, PC) and Complete (PS1, SLUS-00628)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True
    display_name = "Lunar: Silver Star Story (Japanese base: PS1, Switch, PC)"

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

    # -- reference: the English files of the unpacked folder -------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return ENGLISH_LABEL

    def default_reference_path(self) -> Optional[str]:
        """The project's unpacked folder: it holds the English files, so the columns show with no setting."""
        try:
            return str(self.mw.project_manager.project.metadata.get("source_path") or "") or None
        except AttributeError:
            return None

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """The English line of each Japanese string: Remastered (``FIL_us``) and PS1 (``LUNADATA``), one column each.

        ``patch_path`` is the unpacked folder. A block is matched by its file name (``TEXT001``). A column with no
        file is left out.
        """
        root = Path(patch_path or "")
        if not root.is_dir():
            return {}
        columns: Dict[str, Dict[Tuple[int, int], str]] = {}
        for label, folder in REFERENCE_FOLDERS:
            result: Dict[Tuple[int, int], str] = {}
            for block, name in self._block_pairs(block_names):
                stem = name.replace("\\", "/").split("/")[-1].split(".")[0]
                english, japanese = root / folder / f"{stem}.DAT", root / "FIL" / f"{stem}.DAT"
                if not (english.is_file() and japanese.is_file()):
                    continue
                lines = text.reference_for_japanese(english.read_bytes(), japanese.read_bytes())
                for index, line in enumerate(lines):
                    if line:
                        result[(block, index)] = line
            if result:
                columns[label] = result
        return columns

    @staticmethod
    def _block_pairs(block_names) -> List[Tuple[int, str]]:
        if isinstance(block_names, dict):
            return [(int(key), str(value)) for key, value in block_names.items()]
        if isinstance(block_names, (list, tuple)):
            return [(index, str(value)) for index, value in enumerate(block_names)]
        return []

    # -- source, unpack and build (LayeredFS, PC data.cpk, PS1 files) ----------

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": "Base game"},
                {"id": unpack.PS1_ROLE, "label": tr("PlayStation disc (Silver Star Story Complete, USA)")}]

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
                 "kind": "files"},
                {"id": build.PS1_TARGET, "label": tr("PlayStation dialogue files (LUNADATA)"), "platforms": ["psx"],
                 "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == build.TARGET:
            return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == build.PC_TARGET:
            return build.build_pc(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == build.PS1_TARGET:
            return build.build_ps1(source_dir, translation_dir, output_dir, progress, is_cancelled)
        raise ValueError(f"Unknown build target: {target_id}")
