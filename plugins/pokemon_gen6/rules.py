"""Pokémon X/Y and Omega Ruby/Alpha Sapphire (3DS) plugin: Game Freak ``.dat`` text tables (the gen 6 ancestor of the
Switch format, the same ``plugins/common/gfmsg`` codec), one block per GARC file; name-entry keyboard rows as one line."""
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import gfmsg
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN = "pokemon_gen6"
_PLUGIN_DIR = Path(__file__).resolve().parent
# English GARC -> (game key of tables.json, kind)
_GARCS = {"a/0/7/4": ("xy", "game"), "a/0/8/2": ("xy", "story"),
          "a/0/7/3": ("oras", "game"), "a/0/8/1": ("oras", "story"),
          "a/0/2/0": ("", "keyboard")}
_ROLE_WORDS = (("Species names", "Pokémon name", "The name of a Pokémon species."),
               ("Form names", "Form name", "The name of a Pokémon form."),
               ("Move names", "Move name", "The name of a move."),
               ("Move descriptions", "Move description", "The description of a move."),
               ("Item names", "Item name", "The name of an item."),
               ("Item descriptions", "Item description", "The description of an item."),
               ("Ability names", "Ability name", "The name of an Ability."),
               ("Ability descriptions", "Ability description", "The description of an Ability."),
               ("Place names", "Place name", "The name of a place."),
               ("Trainer names", "Trainer name", "The name of a trainer."),
               ("Trainer classes", "Trainer class", "A trainer class (Youngster, Gym Leader...)."),
               ("Type names", "Type name", "The name of a Pokémon type."),
               ("Natures", "Nature", "The name of a Pokémon nature."),
               ("Pokédex entries", "Pokédex entry", "A Pokédex description of a Pokémon."),
               ("Battle", "Battle message", "A message of the battle screen."),
               ("Staff credits", "Staff credits", "A line of the staff credits."))


def _rel(path: Any) -> str:
    return str(path).replace("\\", "/")


def locate(rel: str) -> Optional[Tuple[str, str, int]]:
    """``(game key, kind, file index)`` of a source file ``romfs/a/0/7/4/080.dat``; None for other files."""
    m = re.search(r"(a/\d/\d/\d)/(\d{3})(?:\.\d+)?\.(?:dat|bin)$", _rel(rel))
    if not m or m.group(1) not in _GARCS:
        return None
    game, kind = _GARCS[m.group(1)]
    return game, kind, int(m.group(2))


def table_name(rel: str) -> str:
    """The block name of a text table: ``080 Species names``, ``Story 012``, ``Keyboard row 3``."""
    where = locate(rel)
    if where is None:
        return Path(_rel(rel)).stem
    game, kind, index = where
    if kind == "story":
        return f"Story {index:03d}"
    if kind == "keyboard":
        return f"Keyboard {index:03d}"
    label = _tables().get(game, {}).get(str(index), ["Game text", ""])[0]
    return f"{index:03d} {label}"


_TABLES: Optional[Dict[str, Any]] = None


def _tables() -> Dict[str, Any]:
    global _TABLES
    if _TABLES is None:
        try:
            _TABLES = json.loads((_PLUGIN_DIR / "tables.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_debug(f"{_PLUGIN}: tables.json not read: {error}")
            _TABLES = {}
    return _TABLES


def keyboard_header(data: bytes) -> int:
    """Length of the header of a name-entry keyboard row (a/0/2/0): the leading u16 counts (values below 0x20),
    then UTF-16 characters to the end of the file; 0 when the file is not such a row."""
    if len(data) < 6 or len(data) % 2 or gfmsg.is_gfmsg(data):
        return 0
    at = 0
    while at + 2 <= len(data) and int.from_bytes(data[at:at + 2], "little") < 0x20:
        at += 2
    if not 2 <= at <= 8 or at >= len(data):
        return 0
    text = data[at:].decode("utf-16-le", "replace")
    return at if all((ch.isprintable() and ch != "�") or "" <= ch <= "" for ch in text) else 0


def is_keyboard(data: bytes) -> bool:
    return keyboard_header(data) > 0


class GameRules(BaseGameRules):
    """Pokémon X/Y and Omega Ruby/Alpha Sapphire (3DS).

    A project points at the workspace ``source`` folder made by ``1_unpack.bat``: the English text tables
    ``romfs/a/0/7/4/NNN.dat`` (game text) and ``romfs/a/0/8/2/NNN.dat`` (story) of X/Y (ORAS: ``a/0/7/3``,
    ``a/0/8/1``), the name-entry keyboard rows ``romfs/a/0/2/0/NNN.2.bin`` (one line each; keep the number of
    characters), the fonts and the English layout pictures. Each ``.dat`` is one block; saving rebuilds it
    (unchanged files stay byte-exact); ``2_build.bat`` puts the changed files back into the GARC archives.
    The fonts hold no Cyrillic letters: the Font Editor adds them (``min_sheets`` leaves room).
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[bytes] = None        # the file a save writes over (line flags / keyboard header)
        self._located: Dict[int, Optional[str]] = {}

    def get_display_name(self) -> str:
        return "Pokémon X/Y + Omega Ruby/Alpha Sapphire (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat",), "bytes", "Pokémon (3DS) text tables"),
                FileFormat((".bin",), "bytes", "Pokémon (3DS) keyboard rows"), *DEFAULT_FORMATS]

    # -- load and save -----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if gfmsg.is_gfmsg(raw):
            self._file = raw
            return [[gfmsg.to_editor(units) for units, _flags in gfmsg.read(raw)]], {"0": "Text"}
        if is_keyboard(raw):
            self._file = raw
            return [[raw[keyboard_header(raw):].decode("utf-16-le")]], {"0": "Keyboard row"}
        log_debug(f"{_PLUGIN}: not a text table")
        self._file = None
        return [[]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(text) for text in (data or [[]])[0]]
        if not gfmsg.is_gfmsg(self._file):
            if len(texts) != 1:
                raise ValueError("a keyboard row is one line")
            return self._file[:keyboard_header(self._file)] + texts[0].encode("utf-16-le")
        old = gfmsg.read(self._file)
        if len(texts) != len(old):
            raise ValueError(f"{len(texts)} lines for a file of {len(old)}")
        return gfmsg.write([(gfmsg.from_editor(text), flags) for text, (_units, flags) in zip(texts, old)])

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): the newest that parses."""
        self._file = next((raw for raw in context.existing_versions() if gfmsg.is_gfmsg(raw) or is_keyboard(raw)),
                          self._file)

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()

    # -- where a block comes from ------------------------------------------------

    def _source_of(self, block_idx: int) -> Optional[str]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None)
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            found = _rel(pm.project.blocks[block_map.get(block_idx, block_idx)].source_file)
        except (AttributeError, IndexError, KeyError, TypeError) as error:
            log_debug(f"{_PLUGIN}: no source file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        rel = self._source_of(block_idx)
        if rel is None:
            return None
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        return {"file": rel, "line": index, "table": table_name(rel)}

    # -- AI and story context ----------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel = self._source_of(block_idx)
        where = locate(rel) if rel else None
        if where is None:
            return {}
        game, kind, index = where
        context: Dict[str, Any] = {"table": table_name(rel)}
        if kind == "story":
            context["content_role"] = "Dialogue"
            return context
        if kind == "keyboard":
            context.update(content_role="Keyboard row",
                           role_instruction="Characters of the name-entry keyboard; keep the same count.")
            return context
        label, section = _tables().get(game, {}).get(str(index), ["", ""])
        for word, role, instruction in _ROLE_WORDS:
            if word in label:
                context.update(content_role=role, role_instruction=instruction)
                break
        if section:
            context["glossary_section"] = section
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel = self._source_of(block_idx)
        if not rel:
            return {}
        return {"resource": rel, "label": table_name(rel)}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        return f"Table {context['label']} ({context['resource']})" if context else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, moves, items, Abilities, places, trainer names and types from the game's own name tables."""
        entries, seen = [], set()
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        try:
            blocks = list(pm.project.blocks)
        except (AttributeError, TypeError):
            return []
        for block in blocks:
            rel = _rel(block.source_file)
            where = locate(rel)
            if where is None or where[1] != "game":
                continue
            label, section = _tables().get(where[0], {}).get(str(where[2]), ["", ""])
            if not section or "(plural" in label or "(dash)" in label or "(menu)" in label:
                continue
            try:
                texts = [gfmsg.to_editor(units) for units, _flags
                         in gfmsg.read(Path(pm.get_absolute_path(block.source_file)).read_bytes())]
            except (OSError, ValueError) as error:
                log_debug(f"{_PLUGIN}: no glossary terms from {rel}: {error}")
                continue
            for row, term in enumerate(texts):
                term = term.strip()
                if not term or term in seen or "{" in term or len(term) > 40 or term.strip("-—–?") == "":
                    continue
                seen.add(term)
                entries.append({"term": term, "section": section, "description": label,
                                "source_ref": f"{rel} line {row}"})
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- editor ------------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return gfmsg.describe(str(tag))

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://bulbapedia.bulbagarden.net/w/index.php?search={urllib.parse.quote(term.strip())}"

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

