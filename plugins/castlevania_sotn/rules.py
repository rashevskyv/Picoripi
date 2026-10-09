"""Castlevania: Symphony of the Night (PlayStation, USA) plugin: program strings, cutscenes, staff roll."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import codec
from . import doc as docs
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_PATTERN, TagManager

_PLUGIN_DIR = Path(__file__).resolve().parent

_ROLES = {
    "item_name": ("Item name", "An equipment, relic or item name in the 8x8 menu font; keep it short (the menu "
                               "column is about 16 characters)."),
    "item_desc": ("Item description", "One line shown under the item list in the console's font; about 34 "
                                      "characters fit."),
    "spell_name": ("Spell name", "A spell name in the spell list."),
    "enemy_name": ("Enemy name", "An enemy name in the bestiary and the enemy-name display."),
    "menu": ("Menu text", "A menu word, option or label; keep its length close to the English."),
    "message": ("System message", "A memory card or option message in the console's font."),
    "shop": ("Librarian / shop text", "The Master Librarian's shop and bestiary text; a line break is a new line."),
    "pickup": ("Pick-up message", "Shown when an item is picked up (followed by the item name)."),
    "speaker": ("Speaker name", "A character name shown over a cutscene portrait."),
    "dialogue": ("Cutscene dialogue", "A page of cutscene dialogue in the 8x8 font: up to about 20 characters a "
                                      "line and 4 lines a page; tags such as {WAIT 30} or {SPEED 02} time the "
                                      "text and must stay."),
    "credits": ("Staff roll", "One staff roll line; the leading tag ({ENTRY 10}) holds its kind and position."),
}


class GameRules(BaseGameRules):
    """Castlevania: Symphony of the Night (PlayStation, USA, SLUS-00067).

    The project's source folder is the ``source`` folder of the workspace (``1_unpack.bat``): the
    program files of the disc under their disc paths (``DRA.BIN``, ``ST/SEL/SEL.BIN``, the stage and
    boss overlays ``ST/*/*.BIN``, ``BOSS/*/*.BIN``) and the picture files. Each program file is one
    project file: its string groups (item names, descriptions, menus, messages), its cutscene scripts
    and (``SEL.BIN``) the staff roll. Saving writes the same file into the translation folder; the
    build step puts the files back into the disc.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._save_current: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._docs: Dict[str, Tuple[float, docs.Doc]] = {}
        self._map_path: Optional[str] = None
        self._map_mtime = 0.0
        self.translation_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Castlevania: Symphony of the Night (PlayStation)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Symphony of the Night program file"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed", "speaker_attribution"}

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the plugin's: Ukrainian letter -> 8x8 font cell."""
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None) if self.mw else None
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(_PLUGIN_DIR / "translation_map.json")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        if path == self._map_path and mtime == self._map_mtime:
            return
        self._map_path, self._map_mtime = path, mtime
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_warning(f"castlevania_sotn: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items()
                                if len(k) == 1 and len(v) == 1 and v in codec.CELL_OF}
        self.reverse_map = {v: k for k, v in self.translation_map.items() if not v.isascii()}

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        self.load_translation_map()
        try:
            parsed = docs.parse(data, self.reverse_map)
        except (ValueError, IndexError, KeyError) as error:
            log_debug(f"castlevania_sotn: not a Symphony of the Night program file ({error})")
            return [[]], {}
        return (parsed.texts(self.reverse_map) or [[]]), parsed.names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_current = versions[0] if len(versions) > 1 else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None or docs.file_of(source) is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        missing: Set[str] = set()
        out = docs.build(source, data or [], self.translation_map, missing, self.reverse_map)
        if missing:
            log_warning(f"castlevania_sotn: characters the fonts have no glyph for were written as '?': "
                        f"{''.join(sorted(missing))}")
        # pictures edited in the translation copy (Tools -> Textures) stay: only the text regions change
        return docs.merge(self._save_current, out) if self._save_current else out

    def reset_runtime_state(self) -> None:
        self._save_source = self._save_current = self._last_loaded = None
        self._docs.clear()

    # -- editor ----------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_PATTERN

    def get_tag_tooltip(self, tag: str) -> str:
        return "A game code (script command, timing, raw byte): keep it as it is."

    # -- context ----------------------------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _line(self, block_idx: int, string_idx: int) -> Optional[Tuple[docs.Doc, docs.Line]]:
        try:
            pm, project = self._project()
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            path = pm.get_absolute_path(project.blocks[project_idx].source_file)
            mtime = os.path.getmtime(path)
            cached = self._docs.get(path)
            if cached is None or cached[0] != mtime:
                cached = (mtime, docs.parse(Path(path).read_bytes()))
                self._docs[path] = cached
            parsed = cached[1]
            return parsed, parsed.blocks[sub][int(string_idx)]
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"castlevania_sotn: no line behind block {block_idx} string {string_idx}: {error}")
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._line(block_idx, string_idx)
        if found is None:
            return None
        _doc, line = found
        attributes: Dict[str, Any] = {"kind": line.kind, "where": line.where,
                                      "font": "bios" if line.enc == "sj" else "8x8"}
        if line.room:
            attributes["bytes_available"] = line.room - (2 if line.enc == "s8" else 1)
        if line.speaker:
            attributes["speaker"] = line.speaker
        return attributes

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if found is None:
            return {}
        parsed, line = found
        role, instruction = _ROLES.get(line.kind, ("", ""))
        context: Dict[str, Any] = {"where": line.where, "source": docs.source_ref(parsed.path, line)}
        if role:
            context.update({"content_role": role, "role_instruction": instruction})
        if line.speaker:
            context["speaker"] = line.speaker
        return context

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        return (found[1].speaker or None) if found else None

    def is_placeholder_speaker(self, name: str) -> bool:
        return False

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        if found is None or found[1].enc != "cs":
            return None
        return f"{found[0].path}#cutscene{found[1].ref[1]}"

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if found is None:
            return {}
        parsed, line = found
        scene: Dict[str, Any] = {"resource": docs.source_ref(parsed.path, line),
                                 "location_candidates": [docs.place_name(parsed.path)]}
        if line.enc == "cs":
            scene["candidate_actors"] = list(docs.layout()["files"][parsed.path].get("actors") or [])
            scene["msg_group"] = line.where.rsplit(" line ", 1)[0]
        return scene

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Item, relic, spell and enemy names of DRA.BIN with their descriptions."""
        pm, project = self._project()
        if project is None:
            return []
        out: List[Dict[str, Any]] = []
        for block in getattr(project, "blocks", []):
            try:
                data = Path(pm.get_absolute_path(block.source_file)).read_bytes()
                if docs.file_of(data) == "DRA.BIN":
                    out.extend(docs.glossary(data))
            except (OSError, ValueError, AttributeError) as error:
                log_debug(f"castlevania_sotn: glossary seed skipped: {error}")
        return out
