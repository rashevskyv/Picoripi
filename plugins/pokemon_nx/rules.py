"""Pokémon Sword/Shield and Legends: Arceus (Switch) plugin: Game Freak ``.dat`` message tables, one block per file."""
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import gfmsg
from utils.constants import user_plugin_file_or_shipped
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN = "pokemon_nx"
# file name (without .dat) -> (content role, instruction, glossary section); the first match wins
_ROLES = (
    (r"monsname|ride_poke_name", "Pokémon name", "The name of a Pokémon species.", "Pokémon"),
    (r"g?wazaname", "Move name", "The name of a move.", "Moves"),
    (r"g?wazainfo", "Move description", "The description of a move.", ""),
    (r"itemname.*|nuts_name|dressup_item_name|kisekae_item_name", "Item name", "The name of an item.", "Items"),
    (r"iteminfo", "Item description", "The description of an item.", ""),
    (r"tokusei", "Ability name", "The name of an Ability.", "Abilities"),
    (r"tokuseiinfo", "Ability description", "The description of an Ability.", ""),
    (r"place_name.*", "Place name", "The name of a place.", "Places"),
    (r"trname|tower_trname", "Trainer name", "The name of a trainer.", "Characters"),
    (r"trtype", "Trainer class", "A trainer class (Youngster, Gym Leader...).", "Characters"),
    (r"typename", "Type name", "The name of a Pokémon type.", "Types"),
    (r"seikaku", "Nature", "The name of a Pokémon nature.", ""),
    (r"zukan_comment_.*", "Pokédex entry", "A Pokédex description of a Pokémon.", ""),
    (r"btl_.*", "Battle message", "A message of the battle screen.", ""),
    (r"staff_list", "Staff credits", "A line of the staff credits.", ""),
)
# script file prefix -> part of the story
_STORY = (("rigel1", "The Isle of Armor (DLC)"), ("rigel2", "The Crown Tundra (DLC)"),
          ("main_event", "Main story"), ("sub_event", "Side story"), ("demo", "Cutscene"))


def _stem(rel: str) -> str:
    return Path(str(rel).replace("\\", "/")).stem


class GameRules(BaseGameRules):
    """Pokémon Sword/Shield (with both DLC) and Pokémon Legends: Arceus.

    A project points at the workspace ``source`` folder made by ``1_unpack.bat``: ``bin/message/English``
    (``common/*.dat`` menus, names and descriptions; ``script/*.dat`` dialogue), the fonts in ``bin/font``
    and the English layout archives (``bin/appli/**/*_eng.arc``, textures with words). Each ``.dat`` is
    one block; the ``.tbl`` next to it names its lines. Saving rebuilds the ``.dat`` (unchanged files stay
    byte-exact); ``2_build.bat`` copies the changed files into a LayeredFS mod.

    The text fonts lack Ґ Є І Ї ґ є і ї: ``translation_map.json`` writes І і Ї ї as the look-alike Latin
    letters and Є є Ґ ґ as Э э Ъ ъ, whose glyphs a person redraws in the Font Editor.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[bytes] = None        # the message file a save writes over (line flags)
        self._located: Dict[int, Optional[Tuple[str, List[int], List[str]]]] = {}
        self._map_stamp: Optional[tuple] = None
        self.translation_map: Dict[str, str] = {}
        self.reverse_translation_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Pokémon Sword/Shield + Legends: Arceus (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat",), "bytes", "Pokémon (Switch) message tables"), *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the user's or the plugin's: letter -> font slot.
        Look-alike Latin slots are never turned back into Ukrainian letters when the game's text is read."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        project_dir = getattr(pm, "project_dir", None)
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(user_plugin_file_or_shipped(_PLUGIN, "translation_map.json"))
        try:
            stamp = (path, os.path.getmtime(path))
        except OSError:
            stamp = (path, 0.0)
        if stamp == self._map_stamp:
            return
        self._map_stamp = stamp
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_warning(f"{_PLUGIN}: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if isinstance(v, str) and len(k) == 1 and len(v) == 1}
        self.reverse_translation_map = {v: k for k, v in self.translation_map.items()
                                        if not v.isascii() and not "À" <= v <= "ÿ"}

    # -- load and save -----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not gfmsg.is_gfmsg(raw):
            log_debug(f"{_PLUGIN}: not a message file")
            self._file = None
            return [[]], {}
        self._file = raw
        self.load_translation_map()
        back = str.maketrans(self.reverse_translation_map) if self.reverse_translation_map else None
        texts = [gfmsg.to_editor(units) for units, _flags in gfmsg.read(raw)]
        return [[text.translate(back) if back else text for text in texts]], {"0": "Text"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        table = str.maketrans(self.translation_map) if self.translation_map else None
        old = gfmsg.read(self._file)
        texts = [str(text).translate(table) if table else str(text) for text in (data or [[]])[0]]
        if len(texts) != len(old):
            raise ValueError(f"{len(texts)} lines for a file of {len(old)}")
        return gfmsg.write([(gfmsg.from_editor(text), flags) for text, (_units, flags) in zip(texts, old)])

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): the newest that parses."""
        self._file = next((raw for raw in context.existing_versions() if gfmsg.is_gfmsg(raw)), self._file)

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()

    # -- where a block comes from ------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[int], List[str]]]:
        """``(relative path, line flags, line labels)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None)
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            path = Path(pm.get_absolute_path(block.source_file))
            table = path.with_suffix(".tbl")
            labels = gfmsg.read_labels(table.read_bytes()) if table.is_file() else []
            flags = [flags for _units, flags in gfmsg.read(path.read_bytes())]
            found = (str(block.source_file).replace("\\", "/"), flags, labels)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"{_PLUGIN}: no message file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The line's label (from the ``.tbl``), its index and flags."""
        located = self._locate(block_idx)
        if not located:
            return None
        rel, line_flags, labels = located
        try:
            index = int(string_idx)
            flags = line_flags[index]
        except (IndexError, TypeError, ValueError):
            return None
        attributes: Dict[str, Any] = {"file": rel, "line": index, "flags": flags}
        if index < len(labels):
            attributes["label"] = labels[index]
        return attributes

    # -- AI and story context ----------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel, _message, labels = located
        stem = _stem(rel)
        context: Dict[str, Any] = {}
        for pattern, role, instruction, section in _ROLES:
            if re.fullmatch(pattern, stem):
                context.update(content_role=role, role_instruction=instruction)
                if section:
                    context["glossary_section"] = section
                break
        else:
            if "/script/" in f"/{rel}":
                context["content_role"] = "Dialogue"
        try:
            context["label"] = labels[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            pass
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel = located[0]
        context = {"resource": rel, "label": _stem(rel)}
        story = next((part for prefix, part in _STORY if _stem(rel).startswith(prefix)), "")
        if story and "/script/" in f"/{rel}":
            context["story_part"] = story
        return context

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        if not context:
            return None
        part = f" ({context['story_part']})" if "story_part" in context else ""
        return f"File {context['resource']}{part}"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, moves, items, Abilities, places, trainer names and types from the game's own name tables."""
        entries, seen = [], set()
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        try:
            blocks = list(pm.project.blocks)
        except (AttributeError, TypeError):
            return []
        for block in blocks:
            rel = str(block.source_file).replace("\\", "/")
            stem = _stem(rel)
            section = next((s for pattern, _r, _i, s in _ROLES if s and re.fullmatch(pattern, stem)), "")
            if not section or "/common/" not in f"/{rel}":
                continue
            try:
                texts = [gfmsg.to_editor(units) for units, _flags
                         in gfmsg.read(Path(pm.get_absolute_path(block.source_file)).read_bytes())]
            except (OSError, ValueError) as error:
                log_debug(f"{_PLUGIN}: no glossary terms from {rel}: {error}")
                continue
            for row, term in enumerate(texts):
                term = term.strip()
                if not term or term in seen or "{" in term or len(term) > 40:
                    continue
                seen.add(term)
                entries.append({"term": term, "section": section, "description": f"{stem} table",
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
