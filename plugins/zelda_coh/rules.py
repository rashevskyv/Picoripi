"""Cadence of Hyrule plugin: the English strings of ``localization.xml`` (Switch romfs), by id range."""
import math
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .locxml import CreditsFile, FormatError, LocalizationFile
from .tag_manager import TagManager
from .tags import TAG_RE, describe, from_editor, to_editor

# The game numbers its strings by purpose ("UI TEXT (0-999)" says the file). (first id, block, role,
# glossary section of the names in it, whether the lines are spoken).
BLOCKS = (
    (0, "Menus and options", "Menu, option or mode text", None, False),
    (1000, "NPC dialogue", "Dialogue in a text box", None, True),
    (1500, "Tutorials", "Tutorial hint in a text box", None, False),
    (2000, "HUD messages", "Short message shown over the game", None, False),
    (3000, "Item names", "Item name, shown when it is picked up", "Items", False),
    (3500, "Item found", "Item found message", None, False),
    (3600, "Item descriptions", "Inventory description: item name, who can use it, what it does", None, False),
    (3900, "Character unlocks", "Message when a playable character joins", None, False),
    (4000, "Enemy names", "Enemy name", "Enemies", False),
    (5000, "Signs", "Text of a sign", None, False),
    (6000, "Places", "Place name on the map or the area banner", "Places", False),
    (6500, "Playable characters", "Playable character name or description", "Characters", False),
    (7000, "Cutscenes", "Cutscene caption", None, True),
    (8000, "Credits", "Credits heading", None, False),
    (9000, "Achievements", "Achievement name or description", None, False),
)

# Who speaks a dialogue line, from the string key (``zora4_1``, ``deku_king_yves``). A name of None
# keeps the key as an id ("npc:mellan"): the game does not say who that is.
SPEAKERS = (
    ("cutscene_2_cadence", "Cadence"), ("cadence", "Cadence"), ("impa", "Impa"), ("king", "King of Hyrule"),
    ("beedle", "Beedle"), ("ganondorf", "Ganondorf"), ("ganon_fight_intro", "Ganon"), ("tingle", "Tingle"),
    ("octavo", "Octavo"), ("yves", "Yves"), ("aria_intro", "Aria"), ("frederick_intro", "Frederick"),
    ("fortune", "Fortune Teller"), ("fairy_synth", None), ("fairy", "Great Fairy"), ("dark_fairy", None),
    ("zora_leader", None), ("zora_ghost", None), ("zora", "Zora"), ("gerudo_leader", None),
    ("gerudo_mechanic", None), ("gerudo_helmsperson", None), ("gerudo", "Gerudo"), ("villager", "Villager"),
    ("npcguard", "Hyrule Guard"), ("npcscrub", "Deku Scrub"), ("goron_merchant", "Goron Merchant"),
    ("dark_shopkeeper", None), ("shopkeeper", "Shopkeeper"), ("deku_king", "Deku King"),
    ("deku_princess", "Deku Princess"), ("deku_butler", "Deku Butler"), ("deku_tree", "Great Deku Tree"),
    ("skull_kid", "Skull Kid"), ("fisherman", "Fisherman"), ("error", "Error"),
    ("necrodancer", "NecroDancer"), ("preganoncutscene_cadence", "Cadence"), ("preganoncutscene_zelda", "Zelda"),
    ("preganoncutscene_link", "Link"), ("preganoncutscene_yves", "Yves"), ("mellan", None),
    ("gravekeeper", None), ("gravedigger", None), ("target_shooting", None), ("bombchu_bowling", None),
    ("npcironknuckle", None), ("skull_ganon", None), ("skull_mask", None), ("synthrova", None),
)
_SPEAKERS = sorted(SPEAKERS, key=lambda item: -len(item[0]))
# A dialogue variant for the player character (``deku_king_yves``): who the line is said to.
ADDRESSEES = {"yves": "Yves", "skullkid": "Skull Kid", "skull_kid": "Skull Kid", "octavo": "Octavo"}
_LABEL_MAX_CHARS = 40


def block_of(string_id: int) -> int:
    """Index in BLOCKS of a string id."""
    index = 0
    for position, block in enumerate(BLOCKS):
        if string_id >= block[0]:
            index = position
    return index


CREDITS = ("credits", "Credits roll", "Credits roll line: a heading, company or person name", None, False)
GameFile = Union[LocalizationFile, CreditsFile]


def parse(data: bytes) -> GameFile:
    """``localization.xml`` or ``credits.xml``; FormatError for anything else."""
    try:
        return LocalizationFile(data)
    except FormatError:
        return CreditsFile(data)


def groups_of(game_file: GameFile) -> List[Tuple[tuple, List[int]]]:
    """``(kind, entry indices)`` per block (file order inside a block); empty blocks are dropped.
    ``kind`` is a BLOCKS row (or CREDITS)."""
    if isinstance(game_file, CreditsFile):
        return [(CREDITS, list(range(len(game_file.entries))))]
    groups: List[List[int]] = [[] for _ in BLOCKS]
    for index, entry in enumerate(game_file.entries):
        groups[block_of(entry.id)].append(index)
    return [(BLOCKS[n], group) for n, group in enumerate(groups) if group]


def split_blocks(game_file: GameFile) -> List[List[int]]:
    """Entry indices per block."""
    return [group for _kind, group in groups_of(game_file)]


def speaker_of(description: str) -> Optional[str]:
    key = description.lower()
    for prefix, name in _SPEAKERS:
        if key == prefix or key.startswith(prefix + "_") or re.match(re.escape(prefix) + r"\d", key):
            return name or f"npc:{prefix}"
    return None


def addressee_of(description: str) -> Optional[str]:
    """The player character a line variant is for (``deku_king_yves``); only for lines with a known speaker."""
    if speaker_of(description) is None:
        return None
    key = description.lower()
    prefix = next(prefix for prefix, _name in _SPEAKERS if key.startswith(prefix))
    key = key[len(prefix):]
    for token, name in ADDRESSEES.items():
        if re.search(rf"(^|_){token}(_|\d|$)", key):
            return name
    return None


def plain_text(text: str) -> str:
    return TAG_RE.sub("", text)


class GameRules(BaseGameRules):
    """Zelda: Cadence of Hyrule -- Crypt of the NecroDancer featuring The Legend of Zelda (Switch).

    A project points at a folder with the game's ``localization.xml`` (and ``fonts_bin``). The English
    strings are shown, one block per id range; saving writes the whole file with only the edited
    English strings replaced -- into a LayeredFS ``romfs`` when the translation folder is
    ``atmosphere/contents/01000B900D8B0000/romfs``. ``credits.xml`` (the credits roll, the same in
    every language) opens as one more block.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[GameFile] = None
        self._located: Dict[int, Optional[Tuple[GameFile, tuple, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Zelda: Cadence of Hyrule"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".xml",), "bytes", "Cadence of Hyrule localization.xml, credits.xml"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        try:
            loc = parse(bytes(json_obj))
        except FormatError as error:
            log_debug(f"zelda_coh: not a localization or credits file ({error})")
            self._file = None
            return [[]], {}
        self._file = loc
        groups = groups_of(loc)
        blocks = [[to_editor(loc.entries[i].text) for i in group] for _kind, group in groups]
        names = {str(n): kind[1] for n, (kind, _group) in enumerate(groups)}
        return blocks, names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        loc = self._file
        texts: List[Optional[str]] = [None] * len(loc.entries)
        for group, block in zip(split_blocks(loc), data or []):
            for index, text in zip(group, block or []):
                # An untouched string keeps its exact form, whatever the editor form would re-encode to.
                if text is not None and text != to_editor(loc.entries[index].text):
                    texts[index] = from_editor(text)
        return loc.build(texts)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._file = parse(raw)
                return
            except FormatError as error:
                log_warning(f"zelda_coh: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()

    # -- where a string comes from -----------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[GameFile, tuple, List[int]]]:
        """``(parsed source file, BLOCKS row or CREDITS, entry indices)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = pm.project.blocks[project_idx]
            loc = parse(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            kind, group = groups_of(loc)[sub]
            found = (loc, kind, group)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, FormatError) as error:
            log_debug(f"zelda_coh: no localization file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _entry(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        loc, kind, group = located
        try:
            return loc.entries[group[int(string_idx)]], kind
        except (IndexError, TypeError, ValueError):
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        entry, kind = found
        return {"id": entry.id, "key": entry.description, "block": kind[1]}

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return {}
        entry, (_start, _name, role, section, spoken) = found
        context: Dict[str, Any] = {"content_role": role}
        if not spoken:
            context["has_speaker"] = False
        if section and not entry.description.endswith("_explanation"):
            context["glossary_section"] = section
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return {}
        entry, kind = found
        return {"resource": "credits.xml" if kind is CREDITS else "localization.xml", "label": entry.description,
                "msg_group": kind[1]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        entry, kind = found
        return f"{kind[1]}, string {entry.id} ({entry.description})"

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """One conversation = one key stem (``zora4_0``, ``zora4_1`` -> ``zora4``)."""
        found = self._entry(block_idx, string_idx)
        if not found or not found[1][4]:
            return None
        return "coh:" + re.sub(r"_?\d+$", "", found[0].description)

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._entry(block_idx, string_idx)
        if not found or not found[1][4]:
            return None
        return speaker_of(found[0].description)

    def get_addressee_for_string(self, block_idx: int, string_idx: int,
                                speaker: Optional[str] = None) -> Optional[str]:
        found = self._entry(block_idx, string_idx)
        if not found or not found[1][4]:
            return None
        return addressee_of(found[0].description)

    def is_placeholder_speaker(self, name: str) -> bool:
        return str(name).startswith("npc:")

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Item, enemy, place and character names from their id ranges (English)."""
        loc = self._project_file()
        if loc is None:
            return []
        seen, entries = set(), []
        for entry in loc.entries:
            kind = BLOCKS[block_of(entry.id)]
            term = plain_text(entry.text).strip()
            if (not kind[3] or not term or term in seen or entry.description.endswith("_explanation")
                    or "\n" in term or len(term) > _LABEL_MAX_CHARS):
                continue
            seen.add(term)
            entries.append({"term": term, "section": kind[3], "description": f"{kind[2]} (Cadence of Hyrule)",
                            "source_ref": f"localization.xml id {entry.id} ({entry.description})"})
        return entries

    def _project_file(self) -> Optional[LocalizationFile]:
        try:
            pm = self.mw.project_manager
            for block in pm.project.blocks:
                if str(block.source_file).replace("\\", "/").endswith("localization.xml"):
                    return LocalizationFile(Path(pm.get_absolute_path(block.source_file)).read_bytes())
        except (AttributeError, OSError, TypeError, FormatError) as error:
            log_debug(f"zelda_coh: no localization.xml in the project: {error}")
        return None

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed", "external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Short one-line labels (menu entries, names) may grow to 1.3x / 1.6x their English width.

        Everything else is wrapped by the game to its box, so it gets no width limit.
        """
        found = self._entry(block_idx, string_idx)
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if not found or not font_map:
            return None
        text = found[0].text
        if "[n]" in text or "[p]" in text or len(plain_text(text)) > _LABEL_MAX_CHARS:
            return None
        width = self._width(text, font_map)
        if width <= 0:
            return None
        return {"warn_width": math.ceil(width * 1.3), "max_width": math.ceil(width * 1.6)}

    @staticmethod
    def _width(text: str, font_map: dict, default_char_width: int = 11) -> int:
        total = 0
        for ch in plain_text(text):
            entry = font_map.get(ch)
            total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
        return total

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 11) -> Optional[int]:
        return self._width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(str(tag))

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
