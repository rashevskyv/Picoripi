"""Conker: Live & Reloaded (Xbox, USA): the English dialogue of the disc's CAFF text files.

Scope of this version:
- identify the USA XISO image (title id 0x4D530051) and unpack the English text files: each file's original
  ``default.bin`` is kept under ``original/`` for the build, and its translatable strings are written as JSON
  (format ``conker-lr-caff-text/1``) under ``text/``;
- build the translated ``default.bin`` files. A longer line grows its block: the LSBL offset table, the header
  pointers and the section sizes are moved with it (``caff_text.write_slots``).
Not in this version: the UI text tables (``UIFrontend`` and ``UIPause`` are left out), fonts, the subtitle box
size, and the XISO rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import caff_text, xiso
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

ROLE_ISO = "iso"
PLATFORM_XBOX = "xbox"
TITLE_ID = 0x4D530051
TEXT_DIR = "dvddata/aid/text/English"
FORMAT_ID = "conker-lr-caff-text/1"
ORIGINAL_DIR = "original"
TEXT_JSON_DIR = "text"
TARGET_FILES = "translated_files"
# The UI table of this folder has keys and layout records, not dialogue: its block count does not match.
NOT_DECODED_FOLDERS = {"UIFrontend", "UIPause"}


def _wanted(path: str) -> bool:
    """True for the English text files this plugin reads (one ``default.bin`` per folder)."""
    if not path.startswith(TEXT_DIR + "/") or not path.endswith("/default.bin"):
        return False
    return path.split("/")[-2] not in NOT_DECODED_FOLDERS


def _folder_of(rel_path: str) -> str:
    return rel_path.split("/")[-2]


class GameRules(BaseGameRules):
    """Conker: Live & Reloaded (Xbox, USA): dialogue of the English slot, one JSON per CAFF file."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def get_display_name(self) -> str:
        return "Conker: Live & Reloaded (Xbox)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".json",), "json", tr("Conker: Live & Reloaded texts"))]

    def includes_source_file(self, rel_path: str) -> bool:
        return rel_path.startswith(TEXT_JSON_DIR + "/") and rel_path.endswith(".json")

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, dict):
            return [[]], {"0": ""}
        if json_obj.get("format") != FORMAT_ID:
            raise ValueError(tr("Not a Conker: Live & Reloaded text file ({0})", FORMAT_ID))
        strings = [str(text) for text in json_obj.get("strings", [])]
        return [strings], {"0": str(json_obj.get("file", ""))}

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        names = block_names or {}
        strings = blocks[0] if blocks else []
        return {"format": FORMAT_ID, "file": names.get("0", ""), "strings": [str(text) for text in strings]}

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": ROLE_ISO, "label": tr("Xbox disc image (XISO, USA)")}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": PLATFORM_XBOX, "label": tr("Xbox")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        if not xiso.is_xiso(path):
            return None
        try:
            with xiso.XisoImage(path) as image:
                xbe = xiso.default_xbe(image)
        except (OSError, xiso.XisoError):
            return None
        if xbe is None or xiso.xbe_title_id(xbe) != TITLE_ID:
            return None
        return {"role": ROLE_ISO, "platform": PLATFORM_XBOX}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        image_path = sources.get(ROLE_ISO)
        if not image_path:
            return None
        root = Path(target_dir)
        original = root / ORIGINAL_DIR
        progress(5, tr("Reading the disc"))
        with xiso.XisoImage(image_path) as image:
            xbe = xiso.default_xbe(image)
            if xbe is None or xiso.xbe_title_id(xbe) != TITLE_ID:
                raise xiso.XisoError(tr("The image is not Conker: Live & Reloaded (USA)."))
            written = image.extract(_wanted, str(original), lambda p, name: progress(5 + p // 2, name), is_cancelled)
        if is_cancelled():
            return None
        progress(60, tr("Writing the text files"))
        text_dir = root / TEXT_JSON_DIR
        text_dir.mkdir(parents=True, exist_ok=True)
        for position, rel in enumerate(written, start=1):
            if is_cancelled():
                return None
            data = Path(original, *rel.split("/")).read_bytes()
            try:
                slots = caff_text.read_slots(data)
            except caff_text.CaffError:
                # a file whose layout is not decoded keeps its original only; it is not a text file
                continue
            texts = [slots[i].text for i in caff_text.translatable(slots)]
            obj = {"format": FORMAT_ID, "file": rel, "strings": texts}
            (text_dir / f"{_folder_of(rel)}.json").write_text(
                json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
            progress(60 + 40 * position // max(1, len(written)), rel)
        return str(root)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_FILES, "label": tr("Translated text files (changed default.bin)"),
                 "platforms": [PLATFORM_XBOX], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_FILES:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        files = sorted(Path(translation_dir, TEXT_JSON_DIR).glob("*.json"))
        for position, path in enumerate(files, start=1):
            if is_cancelled():
                break
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("format") != FORMAT_ID:
                raise ValueError(tr("{0} is not a Conker: Live & Reloaded text file.", path.name))
            rel = obj["file"]
            original_path = Path(source_dir, ORIGINAL_DIR, *rel.split("/"))
            if not original_path.is_file():
                raise ValueError(tr("The original {0} is missing: unpack the disc again.", rel))
            data = original_path.read_bytes()
            try:
                new_data = caff_text.write_slots(data, obj["strings"])
            except caff_text.CaffError as exc:
                raise ValueError(tr("{0}: {1}", rel, str(exc))) from exc
            if new_data != data:
                target = Path(output_dir, *rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new_data)
            progress(100 * position // max(1, len(files)), rel)
        return output_dir
