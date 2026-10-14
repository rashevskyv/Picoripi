"""Link's Awakening (Nintendo Switch, 2019) plugin: the base game's MSBT text, built into romfs.bin for LAS Recomp.

The project unpacks the base game (v1.0.0 only; see ``recomp.py``). The source folder is the unpacked ``romfs``, so
every MSBT of every region opens as one block. The English slots are ``regionEU/EUen`` and ``regionUS/USen``.
Build target ``lasrecomp`` writes ``romfs.bin`` with the translated files replaced. The SWUK import is ``swuk.py``.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import recomp
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import CODEC


class GameRules(BaseGameRules):
    """Link's Awakening (Nintendo Switch, 2019)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True
    codec = CODEC

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None          # the file loaded or about to be saved

    def get_display_name(self) -> str:
        return "Link's Awakening (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[self.codec.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == self.codec.to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(self.codec.from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            self._msbt = None
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"{type(self).__module__}: cannot read {context.relative_path}: {error}; "
                            "trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return self.codec.describe(self.replace_aliases_with_tags(str(tag)))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    # -- unpack and build (Project Manager) ------------------------------------

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": "Nintendo Switch"}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        """The base game only: its title ID and the base kind. Updates (a separate title) are refused."""
        found = images.identify(path)
        if not found or found.get("game_id") != recomp.TITLE_ID or found.get("title_kind") != "base":
            return None
        return {"role": "base", "platform": "switch"}

    def unpack_key_consoles(self) -> List[str]:
        return ["switch"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        if images.extract(base, target_dir, progress, is_cancelled) is None:
            return None
        recomp.check_unpacked(target_dir)
        return target_dir

    def get_source_subfolder(self) -> Optional[str]:
        """The source is the romfs tree: the build writes romfs.bin from it."""
        return "romfs"

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": recomp.TARGET_ID, "label": "LAS Recomp (romfs.bin)", "platforms": ["switch"], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != recomp.TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return recomp.build(source_dir, translation_dir, output_dir, progress, is_cancelled)
