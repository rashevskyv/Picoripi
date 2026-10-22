"""Luigi's Mansion (3DS, 2018, USA, CTR-P-BGNE, title 00040000001D1900): the English message table.

Unpack extracts the CIA's RomFS limited to the English slot (``romfs/Region_US/English/``). Each ``main.gmsg`` is one
block; ``gmsg.py`` reads and writes it. Build target: ``layeredfs`` (a Luma LayeredFS folder, ``build.py``).
The fonts (``romfs/Region_US/*.gzf``) and the UI archives (``UI*.gar``, GAR version 5) are not read yet.
"""
from typing import Any, Callable, Dict, List, Optional, Set

from core.i18n import tr
from core.project_library import images
from core.project_library.plugin_facts import generic_identity
from plugins.common.table_rules import TableRules
from .gmsg import TAG_RE

from . import build, gmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TITLE_ID = build.TITLE_ID


class GameRules(TableRules):
    """Luigi's Mansion (3DS, 2018, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Luigi's Mansion (3DS, 2018)"
    file_formats = (((".gmsg",), "Grezzo GMSG message table (main.gmsg)"),)
    default_script_name = "luigis_mansion_1_3ds_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return gmsg.Table(raw)
        except ValueError:
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if not self._locate(block_idx):
            return {}
        return {"role": "Dialogue / menu text",
                "description": "A message of the game. {clear} and {wait} and the {cNN} codes stay as they are; "
                               "a line break is a new line on screen."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None

    # ----- wizard: the CIA is unpacked; the English message table becomes the source folder

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found.get("kind") != images.KIND_3DS:
            return None
        if str(found.get("title_id") or "").upper() != TITLE_ID:
            return None
        return generic_identity(found)

    def unpack_key_consoles(self) -> List[str]:
        return ["3ds"]

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        """Extract the CIA's English RomFS tables into ``target_dir``; another image is left to the wizard."""
        base = sources.get("base") or next(iter(sources.values()), None)
        if not base or (images.identify(base) or {}).get("kind") != images.KIND_3DS:
            return None
        return images.extract(base, target_dir, progress, is_cancelled, build.select_english)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "layeredfs", "label": tr("Luma LayeredFS (titles folder, romfs)"), "platforms": ["3ds"],
                 "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == "layeredfs":
            return build.build_layeredfs(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
