"""Yo-kai Watch (3DS, Switch) plugin: Level-5 cfg.bin text, speakers from the game's tables, XF fonts, IMGC/IMGN textures."""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import tags
from .cfgbin import FormatError
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .speakers import GAMES, Speakers, game_of
from .tag_manager import TagManager
from .textfile import TextFile

_PLUGIN_DIR = Path(__file__).resolve().parent
_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿]")
# The Switch games show the lines the English fan mods left Japanese (they are translated from Japanese).
JAPANESE_SHOWN = ("ywnx", "yw4", "yay")

# category -> (role, instruction). The category of a string comes from its file and entry (``category``).
_ROLES = {
    "dialogue": ("Dialogue", "A line said in the message window (2 lines per page). Kids, adults and Yo-kai talk "
                 "casually; Whisper is a know-it-all butler, Jibanyan a lazy cat who ends lines with -nyan."),
    "name": ("Name", "The name of a Yo-kai, person, item, skill or ability as menus and battles show it. Yo-kai "
             "names are puns on what they do or look like: keep a pun in Ukrainian, short."),
    "plural": ("Plural name", "The plural form of the item name in the line before it."),
    "medallium": ("Medallium entry", "A Yo-kai's description in the Medallium (short lines, up to 5)."),
    "description": ("Description", "Help text of an item, skill, quest or menu."),
    "objective": ("Current goal", "The current objective shown on the bottom screen."),
    "movie": ("Movie subtitle", "A subtitle of the opening or ending movie."),
    "menu": ("Menu or system text", "A menu label, button, or system message."),
    "battle": ("Battle text", "A battle message or battle tip."),
}


def category(rel_path: str, kind: str, param: int) -> str:
    """The layout and role group of a string: its file and entry decide it."""
    rel = rel_path.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    if kind == "NOUN_INFO":
        return "plural" if param == 9 else "name"
    if rel.startswith(("data/common/text/ja/event/", "data/common/text/ja/map/", "data/common/text/ja/phase/")):
        return "dialogue"
    if rel.startswith(("data/common/text/ja/purpose/", "data/common/text/ja/mission/")):
        return "objective"
    if rel.startswith(("data/txt/ev/", "data/res/map/", "data/res/text/phs/")):
        return "dialogue"
    if rel.startswith("data/txt/pps/"):
        return "objective"
    if rel.startswith("data/txt/"):
        return "movie"
    if name.startswith(("chara_text", "chara_desc_text")):
        return "medallium"
    if name.startswith("battle_text"):
        return "battle"
    if name.startswith(("item_text", "skill_text", "skill_desc_text", "chara_ability_text", "quest_text", "quest_navi_text",
                        "quest_mistery_text", "help_text", "friendbook_text", "watchanalyze_text")):
        return "description"
    if name.startswith(("face_text", "capsule_text", "wanted_npc_text")):
        return "dialogue"
    return "menu"


def layout_key(rel_path: str, kind: str, param: int) -> str:
    """The key of ``layout.json``: the measured width of the English text of that file kind."""
    rel = rel_path.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    if rel.startswith(("data/txt/ev/", "data/res/map/")):
        group = "dialogue"
    elif rel.startswith("data/txt/pps/"):
        group = "objective"
    elif rel.startswith("data/txt/"):
        group = "movie"
    elif rel.startswith("data/res/text/phs/"):
        group = "phase"
    else:
        group = re.sub(r"_text_en\.cfg\.bin$|\.cfg\.bin$", "", name)
    return f"{group}|{kind}|{param}"


class GameRules(BaseGameRules):
    """Yo-kai Watch (3DS, USA), Yo-kai Watch 3 (3DS, EUR; its English is in ``data/txt/ev/en`` and ``yw_lg_en.fa``)
    Yo-kai Watch 1 on Switch (``ywnx``: the Japanese files ``*_ja.cfg.bin``, English from the fan mod), and
    Yo-kai Watch 4++ / Yo-kai Academy Y on Switch (``yw4`` / ``yay``: ``data/common/text/ja/**.cfg.bin``, English
    from the fan mods; G4 fonts and G4TX textures, each game's own ``<game>_font_sources.json``). On the Switch
    games the lines the fan mods left Japanese are shown too (``JAPANESE_SHOWN``), to translate from Japanese.

    The project's source folder is the workspace's ``source`` folder: every English text table
    (``*_en.cfg.bin``) at its path inside ``yw1_a.fa``, the fonts ``fnt/*.xf`` and the English menu
    textures. Speaker tables are read from ``meta`` next to it. Saving writes the same files into the
    translation folder; the build step puts them into the archive.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, TextFile, Path]]] = {}
        self._speakers: Optional[Speakers] = None
        self._layout: Optional[Dict[str, Dict[str, int]]] = None
        self._japanese_for: Optional[Tuple[Optional[Path], bool]] = None

    def get_display_name(self) -> str:
        return "Yo-kai Watch"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Level-5 text tables (cfg.bin)"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [TextFile(self._last_loaded, japanese=self._japanese_shown()).texts()], {}
        except (FormatError, UnicodeDecodeError, ValueError) as error:
            log_debug(f"yokai_watch: not a text table ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        strings = data[0] if data else []
        return TextFile(source, japanese=self._japanese_shown()).build([str(s) for s in strings])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._speakers = None
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _locate(self, block_idx: int) -> Optional[Tuple[str, TextFile, Path]]:
        """``(relative path, parsed source file, source root)``, cached."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm, project = self._project()
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = project.blocks[block_map.get(block_idx, block_idx)]
            rel = str(block.source_file).replace("\\", "/")
            path = Path(pm.get_absolute_path(block.source_file))
            root = Path(str(path)[:-len(rel)]) if str(path).replace("\\", "/").endswith(rel) else path.parent
            found = (rel, TextFile(path.read_bytes(), path.name, self._japanese_shown()), root)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"yokai_watch: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _row(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        rel, text_file, root = located
        try:
            return rel, text_file.rows[int(string_idx)], root
        except (IndexError, TypeError, ValueError):
            return None

    def _speaker_index(self, root: Path) -> Speakers:
        if self._speakers is None or self._speakers.source_root != root:
            self._speakers = Speakers(root, root.parent / "meta")
        return self._speakers

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._row(block_idx, string_idx)
        if not found:
            return None
        rel, row, _root = found
        return {"file": rel, "entry": row.kind, "text_id": f"{row.text_id:08x}", "number": row.number,
                "category": category(rel, row.kind, row.param)}

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        rel, row, _root = found
        role, instruction = _ROLES[category(rel, row.kind, row.param)]
        return {"content_role": role, "role_instruction": instruction}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        if not found or found[1].kind != "TEXT_INFO":
            return None
        rel, row, root = found
        name = self._speaker_index(root).speaker(rel, row.text_id, row.number, row.text)
        return None if not name or _JAPANESE.search(name) else name

    def is_placeholder_speaker(self, name: str) -> bool:
        return False

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        rel, row, _root = found
        stem = Path(rel).name.split(".")[0]
        context = {"resource": rel, "label": stem}
        chapter = re.search(r"(?:^ev|_c)(\d\d)", stem)
        if chapter:
            context["chapter"] = chapter.group(1)
        if rel.startswith("data/res/map/"):
            context["map"] = rel.split("/")[3]
        return context

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        return f"{found[0]}#{found[1].text_id:08x}" if found else None

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        if not found:
            return None
        rel, row, _root = found
        return f"{_ROLES[category(rel, row.kind, row.param)][0]} -- {Path(rel).name.split('.')[0]}"

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Names from the game's own tables: Yo-kai and people (``chara_text``), items, skills, abilities,
        the eight tribes (``help_text``) and places (the location names of ``system_text``)."""
        root = self._source_root()
        if root is None:
            return []
        from .glossary import seed_entries
        return seed_entries(root, root.parent / "meta", GAMES[game_of(root)]["lang"])

    def _source_root(self) -> Optional[Path]:
        pm, project = self._project()
        source = (getattr(project, "metadata", None) or {}).get("source_path") if project else None
        return Path(source) if source and Path(source).is_dir() else None

    # -- editor ----------------------------------------------------------------

    def _game(self, root: Optional[Path] = None) -> str:
        """``yw1`` or ``yw3`` (``speakers.game_of``: the layout of the source folder)."""
        root = root or self._source_root()
        return game_of(root) if root else "yw1"

    def _japanese_shown(self) -> bool:
        """Per source folder, once (every file of a project loads through here)."""
        root = self._source_root()
        if self._japanese_for is None or self._japanese_for[0] != root:
            self._japanese_for = (root, self._game(root) in JAPANESE_SHOWN)
        return self._japanese_for[1]

    def _layouts(self, game: str = "yw1") -> Dict[str, Dict[str, int]]:
        if self._layout is None:
            try:
                self._layout = json.loads((_PLUGIN_DIR / "layout.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                log_warning(f"yokai_watch: layout.json: {error}")
                self._layout = {}
        return self._layout.get(game, {})

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """``font_sources.json``; a game's own width maps are ``<game>_<font>.json`` (Yo-kai Watch 1 has none)."""
        game = self._game()
        if game in ("yw4", "yay"):
            return self._plugin_json_list(f"{game}_font_sources.json")
        sources = self._plugin_json_list("font_sources.json")
        if game != "yw1":
            sources = [dict(s, font_map=f"{game}_{s['font_map']}") if s.get("font_map") else s for s in sources]
        return sources

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        """``texture_sources.json``; another game has its own list, ``<game>_texture_sources.json`` (other paths)."""
        game = self._game()
        return self._plugin_json_list("texture_sources.json" if game == "yw1" else f"{game}_texture_sources.json")

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The widest English row of the same kind of text (measured with the game's font, ``layout.json``):
        the message window for dialogue, the Medallium box for Yo-kai descriptions, and so on."""
        found = self._row(block_idx, string_idx)
        if not found:
            return None
        rel, row, root = found
        game = self._game(root)
        measured = self._layouts(game).get(layout_key(rel, row.kind, row.param))
        if not measured:
            return None
        result = {"warn_width": measured["warn"], "max_width": measured["max"],
                  "font_file": "ft_nrm.json" if game == "yw1" else f"{game}_ft_nrm.json"}
        if measured.get("lines"):
            result["lines_per_page"] = measured["lines"]
        return result

    @staticmethod
    def _width(text: str, font_map: dict, default_char_width: int = 9) -> int:
        total = 0
        for char in tags.TAG_RE.sub("", text):
            entry = font_map.get(char)
            total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
        return total

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 9) -> Optional[int]:
        return self._width(text, font_map or {}, default_char_width)

    def get_spellcheck_ignore_pattern(self) -> str:
        return tags.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        return tags.describe(tag)

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
