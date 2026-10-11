"""Castlevania: Lords of Shadow - Mirror of Fate plugin (3DS, EUR): the game's localization text, its bitmap fonts
and the pictures that depend on the language.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it), at the game's romfs paths:

- ``romfs/system/localization/english.txt`` -- 1,522 messages ``KEY##text`` / ``KEY#Speaker#text`` (help
  boxes, menus, dialogue of the cutscenes, credits). One block, one string per message; ``|`` is a line break
  and ``@[A]`` shows as ``{A}`` (``text.py``). An unedited file is written back byte for byte.
- ``romfs/system/fonts/*.bfont`` -- the bitmap fonts (``font_sources.json``, format ``mof_font``).
- ``romfs/gui/textures/*.bctex`` -- CGFX pictures with text: the English controls, the logo (``texture_sources.json``).
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Castlevania: Lords of Shadow - Mirror of Fate (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._source: Optional[bytes] = None        # the file the strings of the loaded block come from
        self._messages: List[Tuple[str, str, str]] = []
        self.translation_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Castlevania: Lords of Shadow - Mirror of Fate"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".txt",), "bytes", "Mirror of Fate localization text"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    # -- translation map -------------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project: a letter the font lacks -> the character whose glyph is drawn."""
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None) if self.mw else None
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        raw: Dict[str, str] = {}
        if path and os.path.isfile(path):
            try:
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                log_warning(f"castlevania_mof: cannot read {path}: {error}")
        self.translation_map = {k: v for k, v in raw.items() if len(k) == 1 and len(v) == 1 and text.encode_char(v)}
        self.reverse_map = {v: k for k, v in self.translation_map.items() if not v.isascii()}

    # -- load and save ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._source, self._messages = None, []
            return super().load_data_from_json_obj(json_obj)
        self.load_translation_map()
        self._source = bytes(json_obj)
        parsed = text.MofText(self._source)
        self._messages = parsed.messages
        return [[text.to_editor(value, self.reverse_map) for _key, _speaker, value in self._messages]], {}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from the newest version that parses (keys and speakers stay as they were)."""
        self._source = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".txt"):
            return
        for raw in context.existing_versions():
            if text.MofText(raw).messages:
                self._source = bytes(raw)
                return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._source is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        texts = data[0] if data and isinstance(data[0], list) else []
        parsed = text.MofText(self._source)
        values = []
        for index, (_key, _speaker, original) in enumerate(parsed.messages):
            shown = texts[index] if index < len(texts) else None
            if shown is None or str(shown) == text.to_editor(original, self.reverse_map):
                values.append(original)
            else:
                values.append(text.from_editor(str(shown), self.translation_map))
        missing: Set[str] = set()
        out = text.build_bytes(self._source, values, missing)
        if missing:
            log_warning(f"castlevania_mof: characters the font has no byte for were written as '?': "
                        f"{''.join(sorted(missing))}")
        return out

    def reset_runtime_state(self) -> None:
        self._source, self._messages = None, []

    # -- context ---------------------------------------------------------------------

    def _message(self, string_idx: int) -> Optional[Tuple[str, str, str]]:
        try:
            return self._messages[int(string_idx)]
        except (TypeError, ValueError, IndexError):
            return None

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(string_idx)
        return found[1].replace("_", " ") if found and found[1] else None

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(string_idx)
        if not found:
            return {}
        key, speaker, _value = found
        role = "Help box" if key.startswith("HELP_") else "Menu text" if key.startswith("GUI_") else \
            "Credits" if key.startswith("CREDIT_") else "Cutscene dialogue" if speaker else "Game text"
        return {"content_role": f"{role} ({key})", "has_speaker": bool(speaker)}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(string_idx)
        return f"Message {found[0]}" if found else None

    # -- editor ----------------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        name = str(tag).strip("{}")
        return f"Button icon or value '{name}' (written as @[{name}] in the game text)"

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""
