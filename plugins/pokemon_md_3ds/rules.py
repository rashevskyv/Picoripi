"""Pokémon Mystery Dungeon: Gates to Infinity and Super Mystery Dungeon (3DS, EUR) plugin: SIR0 message files.

One plugin, two games. The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/pmd3ds.py``): the English message files (Gates to Infinity: ``romfs/message/*.bin``; Super
Mystery Dungeon: the members of the ``message_en.bin`` pack, unpacked as ``romfs/message_en.bin/*.bin``), a block
per file, a string per message in file order (``message.py``: control codes as ``[name...]`` tags, ``codes.py``);
the ``.dic`` + ``.img`` fonts (``font_sources.json``, ``core.font_formats.pmd_font``) and the ``.img`` pictures of
the menus and the title (``texture_sources.json``, ``core.texture_formats.pmd_img``). Saving writes the rebuilt
message file into the translation folder; ``2_build.bat`` packs the Luma mod (and the FARC pack of Super Mystery
Dungeon) from it. The game is told from the project's file paths (``message_en.bin`` = Super Mystery Dungeon): the
two games' code tables differ in the icon codes.
"""
from __future__ import annotations

from pathlib import Path
from struct import error as struct_error
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import message
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

PSMD_MARKER = "message_en.bin"


class GameRules(BaseGameRules):
    """Pokémon Mystery Dungeon: Gates to Infinity / Super Mystery Dungeon (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.game_override: Optional[str] = None       # "gti" / "psmd"; tests and tools set it
        self._game_name: Optional[str] = None
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._attributes: Dict[int, Optional[List[Dict[str, str]]]] = {}

    def get_display_name(self) -> str:
        return "Pokémon Mystery Dungeon (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Mystery Dungeon message file (SIR0)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- which game -------------------------------------------------------------

    def game(self) -> str:
        """``psmd`` when the project holds the ``message_en.bin`` pack's members, else ``gti``."""
        if self.game_override:
            return self.game_override
        if self._game_name is None:
            paths = ""
            try:
                blocks = self.mw.project_manager.project.blocks if self.mw else []
                paths = " ".join(str(getattr(block, "source_file", "")) for block in blocks)
            except AttributeError:
                blocks = []
            self._game_name = "psmd" if PSMD_MARKER in paths else "gti"
            if not blocks:
                self._game_name = None      # no project yet: decide again next time
                return "gti"
        return self._game_name

    # -- load and save ----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [message.File(self._last_loaded).texts(self.game())], {}
        except (message.FormatError, ValueError, struct_error) as error:
            log_debug(f"pokemon_md_3ds: not a message file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return message.File(source).rebuild([str(s) for s in (data[0] if data else [])], self.game())

    def reset_runtime_state(self) -> None:
        self._attributes.clear()
        self._game_name = None
        self._save_source = self._last_loaded = None

    # -- context ----------------------------------------------------------------

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if block_idx not in self._attributes:
            found = None
            try:
                pm = self.mw.project_manager
                block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
                block = pm.project.blocks[block_map.get(block_idx, block_idx)]
                found = message.attributes(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
                log_debug(f"pokemon_md_3ds: no message file behind block {block_idx}: {error}")
            self._attributes[block_idx] = found
        found = self._attributes[block_idx]
        if not found or int(string_idx) >= len(found):
            return None
        return dict(found[int(string_idx)])

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Names from the ``common`` message file (Pokémon, moves, items, Abilities, dungeons, types): its short
        one-line strings with no tags and no sentence ending, in the game's own English wording."""
        entries, seen = [], set()
        try:
            pm = self.mw.project_manager
            for block in [b for b in pm.project.blocks if Path(str(b.source_file)).name == "common.bin"]:
                texts = message.File(Path(pm.get_absolute_path(block.source_file)).read_bytes()).texts(self.game())
                for row, term in enumerate(texts):
                    term = term.strip()
                    if (term and term not in seen and term[0].isupper() and len(term) <= 24 and "\n" not in term
                            and "[" not in term and term[-1] not in ".!?:," and len(term.split()) <= 3):
                        seen.add(term)
                        entries.append({"term": term, "section": "Names", "description": "common.bin",
                                        "source_ref": f"{block.source_file} line {row}"})
        except (AttributeError, OSError, TypeError, ValueError, struct_error) as error:
            log_debug(f"pokemon_md_3ds: no glossary terms: {error}")
        return entries

    # -- editor -----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return message.TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "pokemon_md_3ds_script.md"
