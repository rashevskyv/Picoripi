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

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from utils.utils import clean_spaces

from . import pret_context, pret_text
from plugins.pokemon_gen1 import rom_project, rom_text
from plugins.pokemon_gen1.problem_analyzer import ProblemAnalyzer

ROM_FACTS_DIR = Path(__file__).with_name("rom_facts")
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tag_manager import SERIES_TAG_MAP

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


def _macro_of(token: pret_text.Token) -> Tuple[str, str]:
    """A token of an edited unit as the codec reads it: a string as a quoted literal, a command as its macro line."""
    if token.is_string:
        return token.cmd, '"' + pret_text.escape(token.content) + '"'
    word, _, args = token.raw.strip().partition(" ")
    return word, args.strip()


def _parse_text(rel: str, path: str) -> Tuple[List[pret_text.Unit], Dict[str, Dict[str, List[str]]]]:
    """``(units, context of the map)`` of a text file. Reads the disk: called from a worker."""
    with open(path, encoding="utf-8") as stream:
        text = stream.read()
    units = pret_text.parse(text)
    context = pret_context.map_context(text, {u.label for u in units}) if rel.startswith("maps/") else {}
    return units, context


def _budgets_near(source: Path) -> Optional[Tuple[Dict[str, int], rom_text.Names]]:
    """The budgets of the rom/meta.json a few folders above a text file (None when there is none). Called from a worker."""
    for folder in list(source.parents)[:4]:
        candidate = folder / rom_project.ROM_DIR / "meta.json"
        if candidate.is_file():
            return rom_project.read_budgets(str(candidate))
    return None


class GameRules(BaseGameRules):
    """Pokémon Gold / Silver / Crystal (GBC), pret decompilations."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    problem_analyzer_class = ProblemAnalyzer
    show_spaces_as_dots_default = True
    game_name = "Pokémon Gold, Silver and Crystal (pret)"

    def get_series_tag_map(self):
        """The control tags of this game, with a kind each, for the series reuse (plugins/common/series_tags.py)."""
        return SERIES_TAG_MAP

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[str] = None
        self._last_loaded: Optional[str] = None
        # Read off the UI thread (plugins/common/block_loader.py): a block's text units and its ROM budgets.
        self._texts = ReadThrough("pokemon_gsc text", lambda block_idx: rescan_block(self.mw, block_idx))
        self._budgets = ReadThrough("pokemon_gsc budgets", lambda block_idx: rescan_block(self.mw, block_idx))

    def get_display_name(self) -> str:
        return self.game_name

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message box in the game's own font (plugins/pokemon_gsc/preview_panel.py)."""
        from .preview_panel import MessageWindowPreview
        return MessageWindowPreview(main_window)

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

    def _block_file(self, block_idx: int) -> Optional[Tuple[str, Path]]:
        """``(relative path, absolute path)`` of the source file of a block, from the open project."""
        return source_of(self.mw, block_idx)

    def _parsed(self, block_idx: int) -> Optional[Tuple[List[pret_text.Unit], Dict[str, Dict[str, List[str]]]]]:
        """``(units, context of the map)`` of a block's text file, from memory; None until it is read or without a file.

        ponytail: cached until the project state is reset, as the Gen 1 rules do; the old per-call mtime check is a disk stat.
        """
        found = self._block_file(block_idx)
        if not found:
            return None
        rel, path = found
        return self._texts.get(block_idx, lambda: _parse_text(rel, path))

    def _unit(self, block_idx: int, string_idx: int) -> Tuple[str, Optional[pret_text.Unit], Dict[str, List[str]]]:
        found = self._block_file(block_idx)
        if not found:
            return "", None, {}
        rel = found[0]
        parsed = self._parsed(block_idx)
        if parsed is None:
            return rel, None, {}
        units, context = parsed
        if not 0 <= int(string_idx) < len(units):
            return rel, None, {}
        unit = units[int(string_idx)]
        return rel, unit, context.get(unit.label, {})

    # -- byte budgets (a field the ROM keeps in place) -----------------------------------------------

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._texts.clear()
        self._budgets.clear()

    def _budget_data(self, block_idx: int) -> Optional[Tuple[Dict[str, int], rom_text.Names]]:
        """The budgets and names of the ROM project a block's text file belongs to, from memory (read off the UI thread)."""
        found = self._block_file(block_idx)
        if not found:
            return None
        path = Path(found[1])
        return self._budgets.get(block_idx, lambda: _budgets_near(path))

    def exceeds_byte_budget(self, block_idx: int, string_idx: int, text: str) -> bool:
        """True when a field the ROM keeps in place cannot hold this text. Keys are ``label#k`` (see the Gen 1 rules).

        A plain body has a budget only when it holds one unit, the same rule the unpack applies.
        """
        _rel, unit, _context = self._unit(block_idx, string_idx)
        parsed = self._parsed(block_idx)
        if unit is None or not unit.label or parsed is None:
            return False
        units = parsed[0]
        same_label = [other for other in units if other.label == unit.label]
        if unit.kind != pret_text.LITERAL_KIND and len(same_label) != 1:
            return False
        ordinal = sum(1 for earlier in units[:int(string_idx)] if earlier.label == unit.label)
        data = self._budget_data(block_idx)
        if data is None:
            return False
        budgets, names = data
        size = budgets.get(f"{unit.label}#{ordinal}")
        if size is None:
            return False
        try:
            lines = [_macro_of(token) for token in pret_text.from_editor(text, unit.kind, unit.hidden_at)]
            return rom_text.encoded_length(lines, names) > size
        except (rom_text.CodecError, ValueError, IndexError):
            return False

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

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """The short aliases of config.json, in place of the raw tags they stand for."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(path, encoding="utf-8") as handle:
            return dict(json.load(handle).get("default_tag_mappings") or {})

    # ----- Project Manager: ROM mode (a game ROM unpacks to asm text; the build writes a patched ROM) -----

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": rom_project.ROM_ROLE, "label": "Game ROM (Game Boy Color)"}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return rom_project.identify(path, ROM_FACTS_DIR)

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "gbc", "label": "Game Boy Color"}]

    def get_source_subfolder(self) -> Optional[str]:
        return rom_project.SOURCE_DIR

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        rom = sources.get(rom_project.ROM_ROLE)
        if not rom:
            return None
        return rom_project.unpack(rom, target_dir, progress, is_cancelled, ROM_FACTS_DIR)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "rom", "label": "Patched ROM", "platforms": ["gbc"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
        if target_id != "rom":
            raise ValueError(f"Unknown build target: {target_id}")
        return rom_project.build(source_dir, translation_dir, output_dir, progress, is_cancelled, ROM_FACTS_DIR)
