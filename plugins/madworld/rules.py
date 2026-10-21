"""MadWorld (Wii, Europe RZZP8P) plugin.

The wizard unpacks the disc (``unpack.py``) into the source folder: ``text/<disc file>.mwt`` -- the English
messages of one message table (cut-scene subtitles in ``event``, mission and tutorial messages in ``case*``, system
and save messages in ``subscr``), as JSON blocks -- and ``hbm/home.csv`` (Wii HOME Menu). The game draws each table's
text from a picture of just the glyphs it uses; the build (``build.py``) draws that picture anew from the old one and
the fonts (``font/font_subtitle.tpl``, ``font/font_heading.tpl``; Ukrainian letters have empty cells to draw) and
writes the result into a copy of the ISO (``wii_patch.py``).
Control codes show as tags: ``<8010:0064>`` (a code and its argument), ``<8002>``, ``<#0003>`` (a number or
argument word).
"""
import re
from typing import Any, Dict, List, Optional, Set

from core.i18n import tr
from core.project_library import images
from plugins.common.block_json import BlockJsonRules
from plugins.common.disc_source import write_source_mark
from plugins.common.tag_manager import GenericTagManager

from . import build, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"<[0-9A-F]{4}(?::[0-9A-F]{4})?>|<(?:G:|#)[0-9A-F]{4}>")
WII_TARGET = "wii_iso"


class TagManager(GenericTagManager):
    """The game's control codes (``<8010:0064>``, ``<8002>``) and raw words (``<#0003>``, ``<G:1012>``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BlockJsonRules):
    """MadWorld (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    text_extension = ".mwt"
    text_label = "MadWorld text"

    def get_display_name(self) -> str:
        return "MadWorld"

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        if not TAG_RE.fullmatch(str(tag)):
            return ""
        return "Number or argument the game reads" if str(tag).startswith(("<#", "<G:")) else "Game control code"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "wii", "label": tr("Wii")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found["kind"] != images.KIND_WII or found["game_id"] != unpack.GAME_ID:
            return None
        return {"role": "base", "platform": "wii"}

    def unpack_key_consoles(self) -> List[str]:
        return ["wii"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = unpack.unpack_disc(base, target_dir, progress, is_cancelled)
        if done is None:
            return None
        write_source_mark(target_dir, base)     # the build finds the disc again through this record
        return done

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": WII_TARGET, "label": tr("Wii disc image (ISO)"), "platforms": ["wii"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == WII_TARGET:
            return build.build_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
