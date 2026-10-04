"""Metal Gear Solid: The Twin Snakes (GameCube) plugin: codec calls, scripts, subtitles."""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_info, log_warning
from utils.utils import clean_spaces

from . import doc as docs
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .gcx import FormatError as GcxError
from .subtitles import FormatError as SubsError
from .tag_manager import TagManager
from .textcodec import TAG_RE

_PLUGIN_DIR = Path(__file__).resolve().parent

_ROLES = {
    "codec": ("Codec conversation", "One subtitle line of a codec (radio) call, shown under the two faces. "
              "Spoken aloud by the speaker; keep it as natural speech."),
    "script": ("Menu, briefing or system text", "Text of the title menu, options, briefing files, item "
               "descriptions or memory-card messages."),
    "cutscene": ("Cutscene subtitle", "One subtitle of a real-time cutscene, timed to the voice."),
    "voice": ("In-game voice subtitle", "A voiced line said during play (enemies, bosses, radio)."),
    "movie": ("Movie subtitle", "One subtitle of a pre-rendered movie (briefing videos)."),
}
_ITEM_NAME_RE = re.compile(r"^([^\n]{2,24})\n")
# Measured in Dolphin: a 509-wide row fits the codec text box, a 514-wide one wraps (font units).
CODEC_TEXT_WIDTH = 509
SCRIPT_NEIGHBOURS = 8      # strings on each side that count as the same window


class GameRules(BaseGameRules):
    """Metal Gear Solid: The Twin Snakes (GameCube, USA).

    The project's source folder is the ``text`` folder the workspace's unpack step fills:
    ``common/codec.dat`` (every codec call), ``stage/*.gcx`` (scripts taken out of stage.dat:
    menus, briefing, item descriptions, credits), ``*/demo.subs``, ``common/vox.subs`` and
    ``common/movie.subs`` (subtitles of cutscenes, in-game voices and movies) and the font in
    ``font/``. Every string exists in six languages; only the English ones are shown. Saving
    writes the same files into the translation folder; the build step packs them into the discs.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._english: Dict[str, List[List[int]]] = {}     # layout key -> English indices per section
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, docs.Doc, int]]] = {}
        self._parsed: Dict[str, docs.Doc] = {}
        self._speakers: Optional[Dict[int, str]] = None
        self._widest: Dict[Tuple[int, str], int] = {}
        self._map_path: Optional[str] = None
        self._map_mtime = 0.0
        self.translation_map: Dict[str, str] = {}
        self.reverse_translation_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Metal Gear Solid: The Twin Snakes"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".gcx", ".subs"), "bytes", "Twin Snakes text"), *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the plugin's: Ukrainian letter -> font slot."""
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
            log_warning(f"mgs_ts: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if len(k) == 1 and len(v) == 1}
        self.reverse_translation_map = {v: k for k, v in self.translation_map.items()}

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            parsed = docs.parse(data, known=self._english)
        except (GcxError, SubsError, ValueError) as error:
            log_debug(f"mgs_ts: not a Twin Snakes text file ({error})")
            return [[]], {}
        if parsed.kind == "gcx":
            key = docs.layout_key(data)
            self._english.setdefault(key, parsed.english)
        self.load_translation_map()
        return parsed.texts(self.reverse_translation_map) or [[]], parsed.names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        missing: Set[str] = set()
        notes: List[str] = []
        parsed = docs.parse(source, known=self._english)
        out = docs.build(source, parsed, data or [], self.translation_map, missing, notes)
        if missing:
            log_warning(f"mgs_ts: characters the font has no glyph for were written as '?': {''.join(sorted(missing))}")
        for note in notes:
            log_info(f"mgs_ts: {note}")
        return out

    def export_runtime_state(self) -> Any:
        return {"english": self._english}

    def restore_runtime_state(self, state: Any) -> None:
        if isinstance(state, dict) and isinstance(state.get("english"), dict):
            self._english = {str(k): [list(map(int, v)) for v in lists] for k, lists in state["english"].items()}

    def reset_runtime_state(self) -> None:
        self._english.clear()
        self._located.clear()
        self._parsed.clear()
        self._widest.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, docs.Doc, int]]:
        """``(relative path, parsed source file, block inside the file)``, cached."""
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
            rel = str(block.source_file).replace("\\", "/")
            if rel not in self._parsed:
                path = Path(pm.get_absolute_path(block.source_file))
                self._parsed[rel] = docs.parse(path.read_bytes(), path.name, known=self._english)
            found = (rel, self._parsed[rel], sub)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"mgs_ts: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _line(self, block_idx: int, string_idx: int) -> Optional[Tuple[str, docs.Doc, int, docs.Line]]:
        located = self._locate(block_idx)
        if not located:
            return None
        rel, parsed, sub = located
        try:
            return rel, parsed, sub, parsed.blocks[sub][int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None

    def _speaker_name(self, speaker: Optional[int]) -> Optional[str]:
        if not speaker:
            return None
        if self._speakers is None:
            self._speakers = docs.speaker_names()
        return self._speakers.get(speaker, f"speaker {speaker:06x}")

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._line(block_idx, string_idx)
        if not found:
            return None
        rel, _parsed, _sub, line = found
        attributes: Dict[str, Any] = {"file": rel, "kind": line.kind, "where": line.where}
        if line.timing:
            attributes.update(start=line.timing[0], end=line.timing[1])
        if line.speaker:
            attributes["speaker_hash"] = f"{line.speaker:06x}"
        return attributes

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if not found:
            return {}
        role, instruction = _ROLES.get(found[3].kind, ("", ""))
        return {"content_role": role, "role_instruction": instruction} if role else {}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        return self._speaker_name(found[3].speaker) if found else None

    def is_placeholder_speaker(self, name: str) -> bool:
        return str(name).startswith("speaker ")

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if not found:
            return {}
        rel, parsed, sub, line = found
        return {"resource": rel, "label": parsed.names.get(str(sub), Path(rel).stem), "where": line.where}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        return f"{found[0]}#{found[2]}" if found else None

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        if not found:
            return None
        rel, parsed, sub, line = found
        role = _ROLES.get(line.kind, ("Text", ""))[0]
        return f"{role} -- {parsed.names.get(str(sub), Path(rel).stem)}"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Character names (the speakers the game data names) and item names (item descriptions)."""
        entries, seen = [], set()
        for name in sorted(set(docs.speaker_names().values())):
            seen.add(name)
            entries.append({"term": name, "section": "Characters",
                            "description": "Character who speaks in codec calls, cutscenes or play",
                            "source_ref": "speaker name hash in codec.dat / vox.dat"})
        for rel, parsed in self._iter_project_docs():
            if parsed.kind != "gcx" or len(parsed.blocks) != 1:
                continue
            for line in parsed.blocks[0]:
                match = _ITEM_NAME_RE.match(line.raw.decode("latin-1"))
                if match and line.raw.count(b"\n") >= 2 and match.group(1) not in seen:
                    seen.add(match.group(1))
                    entries.append({"term": match.group(1), "section": "Items",
                                    "description": "Weapon or item name (item description window)",
                                    "source_ref": rel})
        return entries

    def _iter_project_docs(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        project = getattr(pm, "project", None)
        for block in getattr(project, "blocks", []) or []:
            rel = str(block.source_file).replace("\\", "/")
            if not rel.endswith(".gcx"):
                continue
            try:
                if rel not in self._parsed:
                    path = Path(pm.get_absolute_path(block.source_file))
                    self._parsed[rel] = docs.parse(path.read_bytes(), path.name, known=self._english)
                yield rel, self._parsed[rel]
            except (OSError, ValueError) as error:
                log_debug(f"mgs_ts: cannot read {rel} for the glossary seed: {error}")

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Width limit of one string. The game breaks a row that is too wide by itself, in the middle
        of a word, so the limit is the box, with no slack.

        Codec: the measured box (``CODEC_TEXT_WIDTH``). Script text: one table mixes windows of
        different widths (option help, item descriptions, memory-card dialogs, briefing), and the
        strings of one window sit together, so the limit is the widest English row among the
        neighbouring strings. Subtitles: the widest English row of the block.
        """
        found = self._line(block_idx, string_idx)
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if not found or not font_map:
            return None
        _rel, parsed, sub, line = found
        if line.kind == "codec":
            return {"warn_width": CODEC_TEXT_WIDTH, "max_width": CODEC_TEXT_WIDTH}
        index = int(string_idx)
        key = (block_idx, index if line.kind == "script" else line.kind)
        if key not in self._widest:
            lines = parsed.blocks[sub]
            if line.kind == "script":
                lines = lines[max(0, index - SCRIPT_NEIGHBOURS):index + SCRIPT_NEIGHBOURS + 1]
            widths = [self._width(text, font_map) for other in lines if other.kind == line.kind
                      for text in docs.textcodec.decode(other.raw).split("\n")]
            self._widest[key] = max(widths, default=0)
        widest = self._widest[key]
        if widest <= 0:
            return None
        if line.kind == "script":
            return {"warn_width": widest, "max_width": widest}
        return {"warn_width": widest, "max_width": round(widest * 1.05)}

    @staticmethod
    def _width(text: str, font_map: dict, default_char_width: int = 14) -> int:
        total = 0
        for char in TAG_RE.sub("", text):
            entry = font_map.get(char)
            total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
        return total

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 14) -> Optional[int]:
        return self._width(text, font_map or {}, default_char_width)

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        match = TAG_RE.fullmatch(str(tag))
        return f"Raw byte 0x{match.group(1).upper()} of the game text" if match else ""

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
