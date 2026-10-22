"""Conker: Live & Reloaded (Xbox, USA): the English dialogue of the disc's CAFF text files.

Scope of this version:
- identify the USA XISO image (title id 0x4D530051) and unpack the English text files: each file's original
  ``default.bin`` is kept under ``original/`` for the build, and its translatable strings are written as JSON
  (format ``conker-lr-caff-text/1``) under ``text/``;
- build the translated ``default.bin`` files. A longer line grows its block: the LSBL offset table, the header
  pointers, the data and section sizes and the checksum are moved with it (``caff_text.write_slots``);
- build a copy of ``default.xbe`` with the wider subtitle box (``xbe_box``, target ``xbe_box``).
Not in this version: the font atlas (``font_atlas.py`` exports it, the build does not use it yet) and the XISO rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from . import caff_text, xbe_box, xiso
from .config import BOX_HEIGHT, BOX_LINE_LIMIT, BOX_WRAP_CHARS, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .problems import ProblemAnalyzer
from .tag_manager import TagManager

ROLE_ISO = "iso"
PLATFORM_XBOX = "xbox"
TITLE_ID = 0x4D530051
TEXT_DIR = "dvddata/aid/text/English"
FORMAT_ID = "conker-lr-caff-text/1"
ORIGINAL_DIR = "original"
TEXT_JSON_DIR = "text"
TARGET_FILES = "translated_files"
TARGET_BOX = "xbe_box"
XBE_NAME = "default.xbe"


def _wanted(path: str) -> bool:
    """True for the English text files this plugin reads (one ``default.bin`` per folder) and the game's XBE.

    The UI banks (UIFrontend, UIPause) are read the same way: their block count matches the LSBL table, and their
    numeric entries are not text, so they are kept as they are.
    """
    if path == XBE_NAME:
        return True
    return path.startswith(TEXT_DIR + "/") and path.endswith("/default.bin")


def _folder_of(rel_path: str) -> str:
    return rel_path.split("/")[-2]


class GameRules(BaseGameRules):
    """Conker: Live & Reloaded (Xbox, USA): dialogue of the English slot, one JSON per CAFF file."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    problem_analyzer_class = ProblemAnalyzer
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
                 "platforms": [PLATFORM_XBOX], "kind": "files"},
                {"id": TARGET_BOX, "label": tr("default.xbe with the wider subtitle box (copy)"),
                 "platforms": [PLATFORM_XBOX], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == TARGET_BOX:
            return self._build_box(source_dir, output_dir, progress)
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
                caff_text.check(new_data)  # refuse a bank the game would reject (checksum or sizes)
            except caff_text.CaffError as exc:
                raise ValueError(tr("{0}: {1}", rel, str(exc))) from exc
            if new_data != data:
                target = Path(output_dir, *rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new_data)
            progress(100 * position // max(1, len(files)), rel)
        return output_dir

    def _build_box(self, source_dir: str, output_dir: str, progress) -> str:
        """Write a copy of the game's default.xbe with the subtitle box changed (xbe_box.py); the original is kept."""
        original = Path(source_dir, ORIGINAL_DIR, XBE_NAME)
        if not original.is_file():
            raise ValueError(tr("The original {0} is missing: unpack the disc again.", XBE_NAME))
        xbe = original.read_bytes()
        if xiso.xbe_title_id(xbe) != TITLE_ID:
            raise ValueError(tr("The original {0} is not Conker: Live & Reloaded (USA).", XBE_NAME))
        height = xbe_box.scaled_height(BOX_LINE_LIMIT) if BOX_HEIGHT else None
        try:
            patched = xbe_box.patched_box(xbe, BOX_WRAP_CHARS, BOX_LINE_LIMIT, height)
        except xbe_box.XbeError as exc:
            raise ValueError(tr("{0}: {1}", XBE_NAME, str(exc))) from exc
        target = Path(output_dir, XBE_NAME)
        target.write_bytes(patched)
        progress(100, XBE_NAME)
        return str(target)
