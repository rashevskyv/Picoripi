"""Luigi's Mansion: Dark Moon plugin (3DS, Europe): the front end's text tables, fonts and pictures.

``1_unpack.bat`` (``zt/r3b3ds.py``) opens the game's ``.dict`` / ``.data`` pairs as folders in the project's source
folder: ``romfs/art/fe/english.data/strings.nloc`` (the English text table; ``ukenglish`` is what a European
console loads, ``russian`` what a console set to Russian loads), ``romfs/art/fe/febundle*_res.data/bundle.nlgb``
(the texture and font bundles, ``font_sources.json`` / ``texture_sources.json``; ``bundle.nlgh`` for the Switch HD
version, whose tables are NLOC version 2) and ``romfs/art/fe/credits.txt``.
Each text table is one block; ``2_build.bat`` rebuilds the pair around a changed member.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from core.project_library import images
from core.project_library.plugin_facts import generic_identity
from plugins.common.table_rules import TableRules

from . import nloc, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_ROLE_RANK = {"base": 0, "update": 1}


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

    # ----- wizard: the 3DS image is unpacked whole; its text and picture pairs become the source folder

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        """A 3DS image, or the Switch HD base game: its role comes from the header, as for a game without a plugin."""
        found = images.identify(path)
        if not found:
            return None
        if found.get("kind") == images.KIND_3DS:
            return generic_identity(found)
        if found.get("kind") == images.KIND_SWITCH and str(found.get("title_id") or "").upper() in self._declared_ids():
            return generic_identity(found)
        return None

    def unpack_key_consoles(self) -> List[str]:
        return ["3ds", "switch"]

    def get_source_subfolder(self) -> Optional[str]:
        return unpack.SOURCE_SUBFOLDER

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        """Unpack the 3DS image(s) into ``target_dir`` (romfs, exefs, exheader.bin) and the Switch HD image into its
        RomFS pairs only, then write the source folder.

        A folder or any file that is not a 3DS or Switch image is left to the wizard, which returns None for it.
        """
        kinds = {path: (images.identify(path) or {}).get("kind") for path in sources.values()}
        if not sources or any(kind not in (images.KIND_3DS, images.KIND_SWITCH) for kind in kinds.values()):
            return None
        ordered = [path for _role, path in sorted(sources.items(), key=lambda item: _ROLE_RANK.get(item[0], 2))]
        for path in ordered:
            select = unpack.switch_pairs_only if kinds[path] == images.KIND_SWITCH else None
            if images.extract(path, target_dir, progress, is_cancelled, select) is None:
                return None
        unpack.expand_pairs(Path(target_dir), hd=images.KIND_SWITCH in kinds.values())
        return target_dir
