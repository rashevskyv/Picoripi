"""Luigi's Mansion (GameCube, USA, GLME01 rev 0): the message tables of the event archives.

Each ``message/messageNN.csv`` member of an event archive (``files/Event/eventNN.szp``, Yay0 around a RARC) is one
block; ``messages.py`` reads and writes it. Unpack writes the whole disc (``sys/`` and ``files/``) with each archive
folded into a folder. Build target: ``gc_iso``, the translated disc image.

The English slot is the only one this plugin edits; the Japanese script in ``text/eventNN.txt`` is not a text table.
Fonts: ``system/system.arc/font_12.bfn`` (``font_sources.json``). The executable's copy of the font is not edited yet.
"""
from typing import Any, Callable, Dict, List, Optional, Set

from core.i18n import tr
from core.project_library import images
from plugins.common.disc_source import write_source_mark
from plugins.common.table_rules import TableRules

from . import build, messages
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

GAME_ID = "GLME01"
REVISION = 0


class GameRules(TableRules):
    """Luigi's Mansion (GameCube, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Luigi's Mansion (GameCube)"
    file_formats = (((".csv",), "Luigi's Mansion message table (CSV, Shift-JIS)"),)
    default_script_name = "luigis_mansion_1_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return messages.Table(raw)
        except ValueError:
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if not self._locate(block_idx):
            return {}
        return {"role": "Dialogue / menu text",
                "description": "A line of the game. A line break inside a message is a new line on screen; "
                               "<TAG>(n) tags (for example <COLOR>(3)...<COLOR>(0)) stay as they are."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None

    # ----- Project Manager and wizard: the disc is unpacked whole; its archives become folders

    def get_platforms(self) -> list:
        return [{"id": "gc", "label": tr("GameCube")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found["kind"] != images.KIND_GC or found["game_id"] != GAME_ID or found["revision"] != REVISION:
            return None
        return {"role": "base", "platform": "gc"}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = images.extract(base, target_dir, progress, is_cancelled)
        if done is None or not build.fold_archives(target_dir, is_cancelled):
            return None
        write_source_mark(target_dir, base)
        return done

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def unpack_key_consoles(self) -> List[str]:
        return []   # a GameCube disc needs no key file

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "gc_iso", "label": tr("GameCube disc image (ISO)"), "platforms": ["gc"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == "gc_iso":
            return build.build_gc_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
