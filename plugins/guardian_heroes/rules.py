"""Guardian Heroes (Xbox 360 XBLA, 2011): the English script ``media/script_eng.mrg``, scene by scene.

Scope of this version:
- identify the game's STFS package (title id 0x58410B2B) or a folder with ``media/script_eng.mrg``, keep the original
  script under ``original/`` for the build, and write its text as JSON (format ``guardian-heroes-script/1``) under
  ``text/``: one block per scene, one string per line of the script;
- build the translated ``media/script_eng.mrg`` from the original and the translation (``script.py``).
Not in this version: the font (``media/font.xprc``, compressed), the menu pictures and the text inside ``default.xex``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import script, stfs
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .problems import ProblemAnalyzer
from .tag_manager import TagManager

ROLE_PACKAGE = "package"
PLATFORM_X360 = "x360"
TITLE_ID = 0x58410B2B
SCRIPT_PATH = "media/script_eng.mrg"
FORMAT_ID = "guardian-heroes-script/1"
ORIGINAL_DIR = "original"
TEXT_JSON_DIR = "text"
TEXT_JSON_NAME = "script_eng.json"
TARGET_FILES = "translated_files"


def _is_package_folder(path: str) -> bool:
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, *SCRIPT_PATH.split("/")))


class GameRules(BaseGameRules):
    """Guardian Heroes: the English script, one JSON file with a block per scene."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    problem_analyzer_class = ProblemAnalyzer
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def get_display_name(self) -> str:
        return "Guardian Heroes"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".json",), "json", tr("Guardian Heroes script"))]

    def includes_source_file(self, rel_path: str) -> bool:
        return rel_path.startswith(TEXT_JSON_DIR + "/") and rel_path.endswith(".json")

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, dict):
            return [[]], {"0": ""}
        if json_obj.get("format") != FORMAT_ID:
            raise ValueError(tr("Not a Guardian Heroes script file ({0})", FORMAT_ID))
        scenes = [[str(text) for text in scene] for scene in json_obj.get("scenes", [])]
        return scenes or [[]], {str(i): tr("Scene {0}", i + 1) for i in range(len(scenes) or 1)}

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        return {"format": FORMAT_ID, "file": SCRIPT_PATH, "scenes": [[str(text) for text in block] for block in blocks]}

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": ROLE_PACKAGE, "label": tr("Xbox 360 game package (STFS) or its extracted folder")}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": PLATFORM_X360, "label": tr("Xbox 360")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        if _is_package_folder(path) or stfs.title_id(path) == TITLE_ID:
            return {"role": ROLE_PACKAGE, "platform": PLATFORM_X360}
        return None

    def _read_script(self, source: str) -> bytes:
        """The bytes of the game's English script from a package file or an extracted folder."""
        if os.path.isdir(source):
            return Path(source, *SCRIPT_PATH.split("/")).read_bytes()
        if stfs.title_id(source) != TITLE_ID:
            raise ValueError(tr("The file is not the Guardian Heroes package (title id 0x58410B2B)."))
        with stfs.Package(source) as package:
            return package.read(SCRIPT_PATH)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        source = sources.get(ROLE_PACKAGE)
        if not source:
            return None
        root = Path(target_dir)
        progress(10, tr("Reading the package"))
        data = self._read_script(source)
        try:
            parsed = script.parse(data)
        except script.ScriptError as exc:
            raise ValueError(tr("{0}: {1}", SCRIPT_PATH, str(exc))) from exc
        if is_cancelled():
            return None
        original = root / ORIGINAL_DIR / Path(*SCRIPT_PATH.split("/"))
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(data)
        text_dir = root / TEXT_JSON_DIR
        text_dir.mkdir(parents=True, exist_ok=True)
        obj = {"format": FORMAT_ID, "file": SCRIPT_PATH, "scenes": parsed.strings}
        (text_dir / TEXT_JSON_NAME).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        progress(100, SCRIPT_PATH)
        return str(root)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_FILES, "label": tr("Translated script (media/script_eng.mrg)"),
                 "platforms": [PLATFORM_X360], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_FILES:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        original_path = Path(source_dir, ORIGINAL_DIR, *SCRIPT_PATH.split("/"))
        if not original_path.is_file():
            raise ValueError(tr("The original {0} is missing: unpack the game again.", SCRIPT_PATH))
        text_path = Path(translation_dir, TEXT_JSON_DIR, TEXT_JSON_NAME)
        if not text_path.is_file():
            raise ValueError(tr("The translation file {0} is missing.", TEXT_JSON_NAME))
        obj = json.loads(text_path.read_text(encoding="utf-8"))
        if obj.get("format") != FORMAT_ID:
            raise ValueError(tr("{0} is not a Guardian Heroes script file.", TEXT_JSON_NAME))
        try:
            parsed = script.parse(original_path.read_bytes())
            data = script.build(script.with_strings(parsed, obj.get("scenes", [])))
        except script.ScriptError as exc:
            raise ValueError(tr("{0}: {1}", SCRIPT_PATH, str(exc))) from exc
        target = Path(output_dir, *SCRIPT_PATH.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        progress(100, SCRIPT_PATH)
        return output_dir
