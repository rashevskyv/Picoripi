"""Paper Mario: The Thousand-Year Door (GameCube) plugin: the message files ``msg/US/*.txt``."""
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.constants import user_plugin_file_or_shipped
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import msgfile
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN_DIR = Path(__file__).resolve().parent

# area code (file name prefix) -> (place, chapter)
AREAS = {
    "aaa": ("Mario's house", "Prologue"), "gor": ("Rogueport", "Prologue"),
    "tik": ("Rogueport Sewers", "Prologue"), "hei": ("Petal Meadows", "Chapter 1"),
    "nok": ("Petalburg", "Chapter 1"), "gon": ("Hooktail Castle", "Chapter 1"),
    "win": ("Boggly Woods", "Chapter 2"), "mri": ("The Great Boggly Tree", "Chapter 2"),
    "tou": ("Glitzville", "Chapter 3"), "usu": ("Twilight Town", "Chapter 4"),
    "gra": ("Twilight Trail", "Chapter 4"), "jin": ("Creepy Steeple", "Chapter 4"),
    "muj": ("Keelhaul Key", "Chapter 5"), "dou": ("Pirate's Grotto", "Chapter 5"),
    "rsh": ("Excess Express", "Chapter 6"), "eki": ("Riverside Station", "Chapter 6"),
    "hom": ("Excess Express platform", "Chapter 6"), "pik": ("Poshley Heights", "Chapter 6"),
    "bom": ("Fahr Outpost", "Chapter 7"), "moo": ("The Moon", "Chapter 7"),
    "aji": ("X-Naut Fortress", "Chapter 7"), "las": ("Palace of Shadow", "Chapter 8"),
    "jon": ("Pit of 100 Trials", "Extra"), "kpa": ("Bowser's interludes", "Extra"),
    "yuu": ("Pianta Parlor games", "Extra"), "dmo": ("Opening demo", "Extra"), "end": ("Ending", "Extra"),
    "global": ("Menus, items, battle", "Global"),
}
_CHAPTER_OF_STAGE = {"stg0": "Prologue", **{f"stg{n}": f"Chapter {n}" for n in range(1, 9)}}

# global.txt: key prefix -> (block name, window kind); the first matching prefix wins
GLOBAL_GROUPS = (
    ("name_", "Names", "name"), ("title_", "Names", "name"),
    ("in_", "Item and badge names", "item_name"),
    ("menu_enemy_", "Tattle Log", "tattle_log"),
    ("btl_un_", "Enemy names", "enemy_name"),
    ("btl_hlp_", "Battle tattles", "battle_tattle"),
    ("btl_", "Battle", "battle"),
    ("msg_", "Descriptions and menu help", "description"),
    ("list_", "Recipes", "description"),
    ("menu_", "Menus", "menu"),
    ("", "Other", "global_other"),
)
# window kind -> (warn width, max width, lines per page): the widest English line of the kind in
# papermarioset_US.bfn units, measured over the whole US text (workspace tools\research\measure_kinds.py)
LAYOUTS = {
    "talk": (336, 342, 3), "keyxon": (336, 342, 3), "system": (330, 342, 3), "boss": (356, 362, 3),
    "majo": (330, 342, 3), "tec": (336, 342, 3), "housou": (336, 342, 3), "plate": (336, 342, 3),
    "kanban": (330, 342, 3), "diary": (330, 342, 3), "select": (330, 342, 7), "battle_tattle": (336, 342, 3),
    "item_name": (176, 190, 1), "enemy_name": (220, 248, 1), "name": (120, 130, 1),
    "description": (336, 342, 10), "menu": (336, 342, 10), "tattle_log": (336, 342, 10),
    "global_other": (336, 342, 10), "battle": (360, 376, 2),
}
WINDOW_TAGS = ("kanban", "diary", "housou", "plate", "tec", "majo", "boss", "system", "keyxon", "select")
_ROLES = {
    "talk": ("Dialogue", "A line of dialogue in a speech balloon (3 lines a page)."),
    "keyxon": ("Goombella's tattle", "Goombella describes a person, enemy or place to Mario: chatty, sassy, "
               "a bit nerdy (she is an archaeology student)."),
    "system": ("System message", "A blue system window: game instructions, item got, save prompts."),
    "boss": ("Boss speech", "A boss or villain speaks in a dramatic window."),
    "majo": ("Shadow Sirens", "Beldam, Marilyn or Vivian speak (the Shadow Sirens' window)."),
    "tec": ("TEC-XX", "The X-Naut computer TEC writes to Princess Peach: polite, mechanical, learning love."),
    "housou": ("Broadcast", "An announcement over a speaker (Glitz Pit, train, fortress)."),
    "plate": ("Notice board", "Text on a notice board or newspaper."),
    "kanban": ("Sign", "A signpost; short, often with an arrow."),
    "diary": ("Diary", "A diary page read aloud."),
    "select": ("Choice", "A question with answer options; each option is one short line."),
    "battle_tattle": ("Battle tattle", "Goombella's tattle of an enemy in battle: stats then a joke."),
    "item_name": ("Item or badge name", "The name of an item or badge; keep it short, it is a list entry."),
    "enemy_name": ("Enemy name", "The name of an enemy; short, shown above the HP bar."),
    "name": ("Character name", "A party member's name."),
    "description": ("Description", "The description of an item, badge, move or menu entry."),
    "menu": ("Menu text", "Text of the pause menu or its help line."),
    "tattle_log": ("Tattle Log entry", "Goombella's notes about an enemy in the Tattle Log."),
    "battle": ("Battle message", "A short message during battle."),
}
_PLACEHOLDER_WIDTHS = {"ITEM": 130, "AN_ITEM": 160, "NUM": 30, "S": 9, "AN": 22, "N": 9}
ICON_WIDTH = 36            # an icon tag's advance at scale 1.0 (estimate)
_SCALE_RE = re.compile(r"\{scale ([0-9.]+)\}")
_ICON_RE = re.compile(r"\{icon \S+ ([0-9.]+)")


class GameRules(BaseGameRules):
    """Paper Mario: The Thousand-Year Door (GameCube, USA, G8ME01).

    The project's source folder is ``files/msg/US`` of the extracted disc (the workspace's unpack step);
    each ``<area>_NN.txt`` is the text of one area, ``global.txt`` the menus, items, badges, battle text
    and tattles. Saving writes the same files into the translation folder; the build step patches them
    into the disc. Ukrainian letters are written as the font slots of ``translation_map.json``.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._leftovers: Dict[str, List[str]] = {}      # layout (hash of the keys) -> leftover keys (hex)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Any] = {}
        self._context: Optional[dict] = None
        self._map_stamp: Optional[tuple] = None
        self.translation_map: Dict[str, str] = {}
        self.reverse_translation_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Paper Mario: The Thousand-Year Door"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".txt",), "bytes", "Paper Mario TTYD messages"), *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the user's or the plugin's: letter -> font slot.
        Look-alike slots (a Latin letter, the apostrophe) are shared with English, so reading the game's
        text never turns them into Ukrainian letters."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        project_dir = getattr(pm, "project_dir", None)
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(user_plugin_file_or_shipped(_PLUGIN_DIR.name, "translation_map.json"))
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
            log_warning(f"paper_mario_gc: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if isinstance(v, str) and len(k) == 1 and len(v) == 1}
        self.reverse_translation_map = {v: k for k, v in self.translation_map.items()
                                        if not (v.isascii() and (v.isalnum() or v == "'"))}

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _layout_key(entries: List[msgfile.Entry]) -> str:
        return hashlib.sha1(b"\0".join(e.key for e in entries)).hexdigest()

    def _groups(self, entries: List[msgfile.Entry]) -> List[Tuple[str, str, List[msgfile.Entry]]]:
        """``(block name, kind of the block, entries)`` the editor shows; Japanese leftovers left out.
        The leftovers are judged once per file layout (its keys), on the first version read: a
        translation can never turn a message into a leftover or back."""
        layout = self._layout_key(entries)
        if layout not in self._leftovers:
            self._leftovers[layout] = [e.key.hex() for e in entries if msgfile.is_leftover(e.text)]
        skip = set(self._leftovers[layout])
        shown = [e for e in entries if e.key.hex() not in skip]
        if not any(e.name.startswith(("btl_un_", "msg_menu_")) for e in shown):
            return [("Messages", "", shown)]
        groups: Dict[str, Tuple[str, List[msgfile.Entry]]] = {}
        for entry in shown:
            name, kind = next((n, k) for prefix, n, k in GLOBAL_GROUPS if entry.name.startswith(prefix))
            groups.setdefault(name, (kind, []))[1].append(entry)
        order = [n for _p, n, _k in GLOBAL_GROUPS]
        return [(name, groups[name][0], groups[name][1]) for name in sorted(groups, key=order.index)]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        try:
            entries = msgfile.parse(data)
        except ValueError as error:
            log_debug(f"paper_mario_gc: not a message file ({error})")
            return [[]], {}
        self._last_loaded = data
        self.load_translation_map()
        groups = self._groups(entries)
        blocks = [[msgfile.decode(e.text, self.reverse_translation_map) for e in group] for _n, _k, group in groups]
        return blocks or [[]], {str(i): name for i, (name, _k, _g) in enumerate(groups)}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        entries = msgfile.parse(source)
        groups = self._groups(entries)
        if len(data or []) != len(groups):
            raise ValueError(f"Expected {len(groups)} blocks, got {len(data or [])}")
        texts = {}
        for (name, _kind, group), block in zip(groups, data):
            if len(block) != len(group):
                raise ValueError(f"Expected {len(group)} messages in block '{name}', got {len(block)}")
            for entry, text in zip(group, block):
                texts[entry.key] = str(text)
        missing: Set[str] = set()
        out = [msgfile.Entry(e.key, msgfile.encode(texts[e.key], self.translation_map, missing))
               if e.key in texts else e for e in entries]
        if missing:
            log_warning("paper_mario_gc: characters the font has no glyph for were written as '?': "
                        f"{''.join(sorted(missing))}")
        return msgfile.build(out)

    def export_runtime_state(self) -> Any:
        return {"leftovers": self._leftovers}

    def restore_runtime_state(self, state: Any) -> None:
        if isinstance(state, dict) and isinstance(state.get("leftovers"), dict):
            self._leftovers = {str(k): [str(x) for x in v] for k, v in state["leftovers"].items()}

    def reset_runtime_state(self) -> None:
        self._leftovers.clear()
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int):
        """``(file name, [(block name, kind, entries)], block inside the file)``, cached."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            project = getattr(pm, "project", None)
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = project.blocks[project_idx]
            path = Path(pm.get_absolute_path(block.source_file))
            found = (path.name, self._groups(msgfile.parse(path.read_bytes())), sub)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"paper_mario_gc: no message file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _entry(self, block_idx: int, string_idx: int):
        """``(file name, area, window kind, entry)`` of a string, or None."""
        located = self._locate(block_idx)
        if not located:
            return None
        name, groups, sub = located
        try:
            _block, kind, entries = groups[sub]
            entry = entries[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None
        return name, name.split(".")[0].split("_")[0], kind or self.window_kind(entry), entry

    @staticmethod
    def window_kind(entry: msgfile.Entry) -> str:
        """The window an area file's message is shown in, from its tags."""
        if any(c >= 0x80 for c in entry.key):          # keyed by a Japanese NPC name: a tattle
            return "keyxon"
        tags = {t[1:-1].split(b" ")[0].decode("latin-1") for t in re.findall(rb"<[^<>\n]*>", entry.text)}
        return next((k for k in WINDOW_TAGS if k in tags), "talk")

    def _context_data(self) -> dict:
        if self._context is None:
            try:
                self._context = json.loads((_PLUGIN_DIR / "context.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                log_warning(f"paper_mario_gc: cannot read context.json: {error}")
                self._context = {}
        return self._context

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        name, area, kind, entry = found
        return {"file": name, "key": entry.name, "area": area, "window": kind}

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return {}
        kind = found[2]
        role, instruction = _ROLES.get(kind, ("", ""))
        result: Dict[str, Any] = {"window_type": kind}
        if role:
            result.update(content_role=role, role_instruction=instruction)
        return result

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        _name, area, kind, entry = found
        if kind in ("keyxon", "battle_tattle", "tattle_log") or entry.name == "msg_kuri_map":
            return "Goombella"
        return self._context_data().get("speakers", {}).get(area, {}).get(entry.name)

    def is_placeholder_speaker(self, name: str) -> bool:
        """The game's Japanese internal NPC name: the script-merge step may replace it."""
        return not str(name).isascii()

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return {}
        name, area, _kind, entry = found
        place, chapter = AREAS.get(area, (area, ""))
        stage = re.match(r"(?:peach_|kpa_)?(stg\d)", entry.name)
        if stage:
            chapter = _CHAPTER_OF_STAGE.get(stage.group(1), chapter)
        if entry.name.startswith("peach_"):
            place = "Princess Peach interlude"
        elif entry.name.startswith("kpa_"):
            place = "Bowser interlude"
        return {"resource": name, "label": f"{chapter}: {place}" if chapter else place, "key": entry.name}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        # the keys of one conversation share their stem: stg1_nok_45, stg1_nok_45_01 ...
        return f"{found[0]}#{re.sub(r'(_[0-9a-z]{1,3})+$', '', found[3].name)}"

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        scene = self.get_scene_context_for_string(block_idx, string_idx)
        return scene.get("label") if scene else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """The party and the item, badge and enemy names of global.txt, the places, and the characters
        the game data names as speakers."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        def add(term, section, description, source):
            if term and term not in seen:
                seen.add(term)
                entries.append({"term": term, "section": section, "description": description, "source_ref": source})

        context = self._context_data()
        kinds = context.get("items", {})
        for entry in self._global_entries():
            if msgfile.is_leftover(entry.text):
                continue
            text = msgfile.decode(entry.text).strip()
            if entry.name.startswith("name_"):
                add(text, "Party", "Mario or a partner", entry.name)
            elif entry.name.startswith("in_"):
                section = {"badge": "Badges", "key_item": "Key items"}.get(kinds.get(entry.name, "item"), "Items")
                add(text, section, {"Badges": "Badge", "Key items": "Key item"}.get(section, "Item"), entry.name)
            elif entry.name.startswith("btl_un_"):
                add(text, "Enemies", "Enemy (battle name)", entry.name)
        for area, (place, chapter) in AREAS.items():
            if area not in ("global", "kpa", "yuu", "dmo", "end"):
                add(place, "Places", f"Place ({chapter})", f"msg/US/{area}_*.txt")
        for name in sorted({n for area in context.get("speakers", {}).values() for n in area.values()
                            if n.isascii() and n[:1].isupper()}):
            add(name, "Characters", "Character who speaks (evt_msg_print in the area modules)", "rel/*.rel")
        return entries

    def _global_entries(self) -> List[msgfile.Entry]:
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        project = getattr(pm, "project", None)
        for block in getattr(project, "blocks", []) or []:
            if Path(str(block.source_file)).name == "global.txt":
                try:
                    return msgfile.parse(Path(pm.get_absolute_path(block.source_file)).read_bytes())
                except (OSError, ValueError) as error:
                    log_debug(f"paper_mario_gc: cannot read global.txt for the glossary seed: {error}")
        return []

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Width and lines per page of the window the message is shown in (``LAYOUTS``)."""
        found = self._entry(block_idx, string_idx)
        if not found:
            return None
        warn, limit, lines = LAYOUTS.get(found[2], LAYOUTS["talk"])
        return {"warn_width": warn, "max_width": limit, "lines_per_page": lines}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 23) -> Optional[int]:
        """Width of one line in font units: ``{scale x}`` scales what follows, icons and placeholders
        count with their usual size, other tags are zero-width."""
        font_map = font_map or {}
        total, scale, pos = 0.0, 1.0, 0
        while pos < len(text):
            tag = msgfile.EDITOR_TAG_RE.match(text, pos) if text[pos] == "{" else None
            if tag:
                body = tag.group()[1:-1]
                scaled, icon = _SCALE_RE.fullmatch(tag.group()), _ICON_RE.match(tag.group())
                if scaled:
                    scale = float(scaled.group(1))
                elif icon:
                    total += ICON_WIDTH * float(icon.group(1))
                elif body in _PLACEHOLDER_WIDTHS:
                    total += _PLACEHOLDER_WIDTHS[body] * scale
                elif isinstance(font_map.get(tag.group()), dict):
                    total += font_map[tag.group()].get("width", 0)
                pos = tag.end()
                continue
            entry = font_map.get(text[pos])
            total += (entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width) * scale
            pos += 1
        return round(total)

    def get_spellcheck_ignore_pattern(self) -> str:
        return msgfile.EDITOR_TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
