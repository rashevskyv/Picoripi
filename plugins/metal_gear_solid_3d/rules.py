"""Metal Gear Solid: Snake Eater 3D plugin (3DS, EUR English): subtitles, fonts and pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it):

- ``text/vox.mgssubs``, ``text/movie.mgssubs``, ``text/demo.mgssubs`` -- the English subtitle lines of the game's
  three stream files (radio and in-game voices, movies, cutscenes) as JSON: one record per subtitle block, each
  English line as hex bytes with its timing. One block per file, one string per line. The bytes are ASCII with
  ``0x1F`` + a code for an accented letter (Latin-1 minus 0x7F) and ``0x80 0x7C`` as the line break (``textcodec.py``,
  the scheme of the Twin Snakes); other bytes show as ``{xNN}``. An unedited line keeps its bytes.
- ``romfs/ui/**.la2/...`` -- the ``.la2`` layout archives (darc) as folders: ``font/*.bcfnt`` fonts and
  ``timg/*.bclim`` pictures (``font_sources.json``, ``texture_sources.json``).

A project may have ``translation_map.json`` (``{"Б": "Á"}``): the letter is written as the byte code of the glyph it
is mapped to and shown back as the letter.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import textcodec
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

MARK = "mgs3d-subtitles"


class GameRules(BaseGameRules):
    """Metal Gear Solid: Snake Eater 3D (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._model: Optional[dict] = None          # the file loaded or about to be saved
        self._lines: List[Tuple[int, int]] = []     # string index -> (record, line)
        self.translation_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Metal Gear Solid: Snake Eater 3D"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mgssubs",), "bytes", "Snake Eater 3D subtitles"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- translation map ---------------------------------------------------------------

    def load_translation_map(self) -> None:
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None) if self.mw else None
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        raw: Dict[str, str] = {}
        if path and os.path.isfile(path):
            try:
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                log_warning(f"metal_gear_solid_3d: cannot read {path}: {error}")
        self.translation_map = {k: v for k, v in raw.items() if len(k) == 1 and len(v) == 1}
        self.reverse_map = {v: k for k, v in self.translation_map.items() if not v.isascii()}

    # -- load and save ---------------------------------------------------------------

    @staticmethod
    def _parse(raw: bytes) -> Optional[dict]:
        try:
            model = json.loads(bytes(raw).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return model if isinstance(model, dict) and model.get("format") == MARK else None

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        model = self._parse(json_obj) if isinstance(json_obj, (bytes, bytearray)) else None
        if model is None:
            self._model, self._lines = None, []
            return super().load_data_from_json_obj(json_obj)
        self.load_translation_map()
        self._model = model
        self._lines = [(r, n) for r, record in enumerate(model["records"]) for n in range(len(record["lines"]))]
        texts = [textcodec.decode(bytes.fromhex(model["records"][r]["lines"][n]["hex"]), self.reverse_map)
                 for r, n in self._lines]
        return [texts], {}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from the newest version that parses (timing and offsets stay as they were)."""
        self._model = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".mgssubs"):
            return
        for raw in context.existing_versions():
            model = self._parse(raw)
            if model is not None:
                self._model = model
                return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._model is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        texts = data[0] if data and isinstance(data[0], list) else []
        model = json.loads(json.dumps(self._model))
        index = 0
        missing: Set[str] = set()
        for record in model["records"]:
            for line in record["lines"]:
                original = bytes.fromhex(line["hex"])
                shown = texts[index] if index < len(texts) else None
                index += 1
                if shown is None or str(shown) == textcodec.decode(original, self.reverse_map):
                    continue
                line["hex"] = textcodec.encode(str(shown), textcodec.newline_of(original, textcodec.SUB_LF),
                                               self.translation_map, missing).hex()
        if missing:
            log_warning(f"metal_gear_solid_3d: characters the font has no code for were written as '?': "
                        f"{''.join(sorted(missing))}")
        return json.dumps(model, indent=1).encode("utf-8")

    def reset_runtime_state(self) -> None:
        self._model, self._lines = None, []

    # -- context ---------------------------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        model = self._model
        if not model or not 0 <= string_idx < len(self._lines):
            return {}
        record, line = self._lines[string_idx]
        item = model["records"][record]["lines"][line]
        return {"content_role": "Subtitle line", "has_speaker": False,
                "timing": f"{item['start']}-{item['end']}"}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if not self._model or not 0 <= string_idx < len(self._lines):
            return {}
        record = self._model["records"][self._lines[string_idx][0]]
        return {"resource": f"slot {record['slot']:#x}", "label": f"record {record['offset']:#x}"}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Lines of one subtitle record belong to one clip or cutscene scene."""
        if not self._model or not 0 <= string_idx < len(self._lines):
            return None
        return f"record-{self._model['records'][self._lines[string_idx][0]]['offset']}"

    # -- editor ----------------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return f"Raw byte {str(tag).strip('{}')[1:]} of the game text"

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
