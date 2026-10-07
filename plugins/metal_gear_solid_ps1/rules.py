"""Metal Gear Solid (PlayStation, USA) plugin: codec calls, subtitles, scripts and program strings."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import codec
from . import doc as docs
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN_DIR = Path(__file__).resolve().parent

_ROLES = {
    docs.CODEC: ("Codec call", "A line of a codec (radio) conversation shown under the faces; at most three short "
                               "lines per page, a line break is a new line on screen."),
    docs.SUBTITLE: ("Subtitle", "A subtitle of a cutscene, a voice or a movie; one or two lines, timed to speech."),
    docs.SCRIPT: ("Game text", "A pick-up label, a mission log line, a VR menu title or a location name."),
    docs.PROGRAM: ("Menu text", "An item name or description, a menu label or a memory card message, edited in "
                                "place: never longer than the English."),
    "contact": ("Codec contact", "A name added to the codec memory list."),
    "save": ("Save location", "A location name shown in the save screen."),
    "prompt": ("Codec prompt", "A choice offered in a codec call (SAVE / DO NOT SAVE)."),
}


class GameRules(BaseGameRules):
    """Metal Gear Solid (PlayStation, USA, SLUS-00594 / SLUS-00776).

    The project's source folder is the ``source`` folder the workspace's unpack step fills:
    ``RADIO.DAT`` (codec calls, the same on both discs), ``SLUS_005.94`` (the program),
    ``stage/<stage>/*.gcx`` and ``*.bin`` (scripts and overlays of STAGE.DIR, each distinct one once)
    and ``subs/*.subs`` (the subtitle blocks of DEMO.DAT, VOX.DAT and ZMOVIE.STR of both discs), plus
    the font (``font/font.res``) and the stage textures (``texture/<stage>/*.pcx``). Saving writes the
    same files into the translation folder; the build step puts them back on both discs.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._known: Dict[str, List[Tuple[int, int]]] = {}
        self._save_source: Optional[bytes] = None
        self._save_name = ""
        self._last_loaded: Optional[bytes] = None
        self._last_doc: Optional[docs.Doc] = None
        self._map_path: Optional[str] = None
        self._map_mtime = 0.0
        self.translation_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Metal Gear Solid (PlayStation)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".gcx", ".subs", ".94", ".bin"), "bytes", "Metal Gear Solid data"),
                *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the plugin's: Ukrainian letter -> font character."""
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
            log_warning(f"metal_gear_solid_ps1: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if len(k) == 1 and len(v) == 1 and 0x20 <= ord(v) < 0x7F}
        self.reverse_map = {v: k for k, v in self.translation_map.items() if not v.isascii() or not v.isalnum()}

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            parsed = docs.parse(data, known=self._known)
        except (ValueError, IndexError, KeyError) as error:
            log_debug(f"metal_gear_solid_ps1: not a Metal Gear Solid text file ({error})")
            return [[]], {}
        docs.remember(data, parsed, self._known)
        self._last_doc = parsed
        self.load_translation_map()
        texts = parsed.texts(self.reverse_map)
        return (texts or [[]]), parsed.names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_name = str(getattr(context, "relative_path", "") or "")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        missing: Set[str] = set()
        parsed = docs.parse(source, known=self._known)
        name = self._save_name.replace("\\", "/") or "file"
        out = docs.build(source, parsed, data or [], self.translation_map, missing, name, self.reverse_map)
        if missing:
            log_warning(f"metal_gear_solid_ps1: characters the font has no glyph for were written as '?': "
                        f"{''.join(sorted(missing))}")
        return out

    def export_runtime_state(self) -> Any:
        return {"known": {key: [list(region) for region in regions] for key, regions in self._known.items()}}

    def restore_runtime_state(self, state: Any) -> None:
        if isinstance(state, dict) and isinstance(state.get("known"), dict):
            self._known = {str(key): [tuple(int(v) for v in region) for region in regions]
                           for key, regions in state["known"].items()}

    def reset_runtime_state(self) -> None:
        self._known.clear()
        self._save_source = self._last_loaded = None
        self._last_doc = None

    # -- editor ----------------------------------------------------------------

    def get_enter_char(self) -> str:
        return "\n"

    def get_shift_enter_char(self) -> str:
        return "\n"

    def get_ctrl_enter_char(self) -> str:
        return "\n"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_spellcheck_ignore_pattern(self) -> str:
        return codec.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        return "A game code (button icon, colour or extra glyph): keep it as it is."

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        line = self._line(block_idx, string_idx)
        if line is None:
            return {}
        role, instruction = _ROLES.get(line.kind, ("", ""))
        return {"content_role": role, "role_instruction": instruction, "where": line.where} if role else {}

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        line = self._line(block_idx, string_idx)
        if line is None:
            return None
        attributes: Dict[str, Any] = {"kind": line.kind, "where": line.where}
        if line.room:
            attributes["bytes_available"] = line.room - 1
        return attributes

    def _line(self, block_idx: int, string_idx: int) -> Optional[docs.Line]:
        """The parsed line behind a project string, from the project file of that block."""
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            project = getattr(pm, "project", None)
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = project.blocks[project_idx]
            data = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            parsed = docs.parse(data, known=self._known)
            return parsed.blocks[sub][int(string_idx)]
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"metal_gear_solid_ps1: no line behind block {block_idx} string {string_idx}: {error}")
            return None
