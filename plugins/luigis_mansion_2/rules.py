"""Luigi's Mansion: Dark Moon plugin (3DS, Europe): the front end's text tables, fonts and pictures.

``1_unpack.bat`` (``zt/r3b3ds.py``) opens the game's ``.dict`` / ``.data`` pairs as folders in the project's source
folder: ``romfs/art/fe/english.data/strings.nloc`` (the English text table; ``ukenglish`` is what a European
console loads, ``russian`` what a console set to Russian loads), ``romfs/art/fe/febundle*_res.data/bundle.nlgb``
(the texture and font bundles, ``font_sources.json`` / ``texture_sources.json``; ``bundle.nlgh`` for the Switch HD
version, whose tables are NLOC version 2) and ``romfs/art/fe/credits.txt``.
Each text table is one block; ``2_build.bat`` rebuilds the pair around a changed member.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from plugins.common.table_rules import TableRules

from . import nloc
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(TableRules):
    """Luigi's Mansion: Dark Moon (3DS, European)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Luigi's Mansion: Dark Moon (3DS)"
    file_formats = (((".nloc",), "Next Level Games NLOC text table"), ((".credits",), "Staff roll script (credits.txt)"))
    default_script_name = "luigis_mansion_2_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return nloc.Table(raw) if raw[:4] == nloc.MAGIC else nloc.Credits(raw)
        except (ValueError, UnicodeDecodeError):
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        if not found:
            return {}
        return {"role": "Dialogue / menu text",
                "description": "A line of the game: {p} is a line or page break, {tp:..}{/tp} a typewriter effect, "
                               "{clr:..}{clr:pop} a colour; the tags stay as they are."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None
