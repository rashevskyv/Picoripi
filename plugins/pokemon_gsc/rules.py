"""Pokémon Gold, Silver and Crystal (Game Boy Color) through the pret decompilations pokegold and pokecrystal.

A project block is one asm file of the decompilation (``maps/Route30.asm``, ``data/pokemon/names.asm``...);
``pret_text`` finds its strings (messages and names) and writes them back in place, so ``2_build.bat`` only
copies the translated files over the decompilation and assembles it with rgbds. A save is always built from
the source file: an unchanged message keeps its lines byte for byte.

Context comes from the map files themselves (``pret_context``): the person, trainer or sign whose script
shows a text (speaker) and that script (conversation). Fonts and pictures with words are the decompilation's
PNG files (``font_sources.json``, ``texture_sources.json``, format ``png``); rgbgfx turns them into tiles.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import pret_context, pret_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

LINE_TILES = 18          # a text box line: 18 tiles of 8 pixels
TILE = 8
LINES_PER_BOX = 2
# Charmap names and what they print, in tiles (names: the longest the game allows).
_TOKEN_TILES = {"<PLAYER>": 7, "<RIVAL>": 7, "<MOM>": 7, "<RED>": 7, "<GREEN>": 7, "<PKMN>": 2, "<POKE>": 2,
                "<PC>": 2, "<TM>": 2, "<TRAINER>": 7, "<ROCKET>": 6, "<TARGET>": 16, "<USER>": 16, "<ENEMY>": 16,
                "<……>": 2, "<PLAY_G>": 7, "<BSP>": 1, "<WBR>": 0, "<LF>": 0, "<CR>": 0}
_TOKEN_RE = re.compile(r"<[^<>]*>|\{[^{}]*\}|'[dlmrstv]|#")
_ROLES = (("data/pokemon/dex_entries", "PokedexEntry"), ("data/phone", "PhoneCall"), ("data/radio", "Radio"),
          ("maps/", "Dialogue"), ("data/text/", "SystemMessage"), ("engine/", "Menu"), ("home/", "Menu"),
          ("mobile/", "Menu"), ("data/", "Name"))


def text_tiles(text: str) -> int:
    """Tiles one editor line takes on screen (tags take none)."""
    text = pret_text.TAG_RE.sub("", text)

    def tiles(match: "re.Match[str]") -> str:
        token = match.group(0)
        if token == "#":
            return "...."                    # POKé
        if token.startswith("'"):
            return "."
        if token.startswith("{"):
            return "..."
        return "." * _TOKEN_TILES.get(token, 1)
    return len(_TOKEN_RE.sub(tiles, text).rstrip("@"))


class GameRules(BaseGameRules):
    """Pokémon Gold / Silver / Crystal (GBC), pret decompilations."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True
    game_name = "Pokémon Gold, Silver and Crystal (pret)"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[str] = None
        self._last_loaded: Optional[str] = None
        self._file_cache: Dict[str, Tuple[int, List[pret_text.Unit], Dict[str, Dict[str, List[str]]]]] = {}

    def get_display_name(self) -> str:
        return self.game_name

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".asm",), "text", "pret decompilation asm")]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = json_obj
        return [pret_text.load(json_obj)], {"0": "Text"}

    def prepare_save_context(self, context: Any) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1].decode("utf-8") if versions else None

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        texts = [str(text) for text in (data[0] if data else [])]
        if source is None:
            return "\n".join(texts)
        return pret_text.write(source, texts)

    # -- context from the decompilation ---------------------------------------------------

    def _block_file(self, block_idx: int) -> Optional[Tuple[str, str]]:
        """``(relative path, absolute path)`` of the source file of a block."""
        try:
            pm = getattr(self.mw, "project_manager", None)
            project = getattr(pm, "project", None) if pm else None
            if project is None:
                return None
            block_map = getattr(self.mw, "block_to_project_file_map", {}) or {}
            index = block_map.get(block_idx, block_idx)
            if not isinstance(index, int) or not 0 <= index < len(project.blocks):
                return None
            rel = project.blocks[index].source_file
            path = pm.get_absolute_path(rel)
            return (rel.replace("\\", "/"), path) if path and os.path.isfile(path) else None
        except Exception as error:  # noqa: BLE001 - context is optional
            log_debug(f"pokemon_gsc: no file for block {block_idx}: {error}")
            return None

    def _unit(self, block_idx: int, string_idx: int) -> Tuple[str, Optional[pret_text.Unit], Dict[str, List[str]]]:
        found = self._block_file(block_idx)
        if not found:
            return "", None, {}
        rel, path = found
        stamp = os.stat(path).st_mtime_ns
        cached = self._file_cache.get(path)
        if cached is None or cached[0] != stamp:
            with open(path, encoding="utf-8") as stream:
                text = stream.read()
            units = pret_text.parse(text)
            context = pret_context.map_context(text, {u.label for u in units}) if rel.startswith("maps/") else {}
            cached = (stamp, units, context)
            self._file_cache[path] = cached
        units = cached[1]
        if not 0 <= int(string_idx) < len(units):
            return rel, None, {}
        unit = units[int(string_idx)]
        return rel, unit, cached[2].get(unit.label, {})

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The one person, trainer or sign whose map script shows the text."""
        speakers = self._unit(block_idx, string_idx)[2].get("speakers") or []
        return speakers[0] if len(speakers) == 1 else None

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel, unit, _context = self._unit(block_idx, string_idx)
        if unit is None:
            return {}
        if not unit.is_message:
            return {"content_role": "Name", "has_speaker": False,
                    "role_instruction": "NAMES: one name of a fixed-length list; keep it as short as the "
                                        "original (the build stops when a name is too long)."}
        role = next((name for prefix, name in _ROLES if rel.startswith(prefix)), "")
        return {"content_role": role} if role else {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The file and line of the text, the scripts that show it and their people."""
        rel, unit, context = self._unit(block_idx, string_idx)
        if unit is None:
            return {}
        result: Dict[str, Any] = {"resource": f"{rel}:{unit.start + 1}"}
        if rel.startswith("maps/"):
            result["locations"] = [os.path.splitext(os.path.basename(rel))[0]]
        if context.get("scripts"):
            result["flow_ids"] = list(context["scripts"])
        if context.get("speakers"):
            result["candidate_actors"] = list(context["speakers"])
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        rel, unit, context = self._unit(block_idx, string_idx)
        if unit is None:
            return None
        shown = f", shown by {', '.join(context['scripts'])}" if context.get("scripts") else ""
        return f"Text {unit.label or '(no label)'} in {rel}{shown}."

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Texts one map script shows are one conversation."""
        rel, unit, context = self._unit(block_idx, string_idx)
        scripts = context.get("scripts") or []
        return f"{rel}:{scripts[0]}" if unit is not None and len(scripts) == 1 else None

    # -- width and editing ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        width = LINE_TILES * TILE
        return {"max_width": width, "warn_width": width, "lines_per_page": LINES_PER_BOX}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return text_tiles(text) * TILE

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool,
                        editor_font_map: Optional[Dict] = None, editor_line_width_threshold: Optional[int] = None,
                        full_data_string_text_for_logical_check: Optional[str] = None,
                        is_target_for_debug: bool = False, logical_hard_limit: Optional[int] = None) -> Set[str]:
        threshold = editor_line_width_threshold or LINE_TILES * TILE
        full_text = text if full_data_string_text_for_logical_check is None else full_data_string_text_for_logical_check
        return super().analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map or {}, threshold, full_text,
            is_target_for_debug, logical_hard_limit=logical_hard_limit,
        )

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return LINES_PER_BOX
