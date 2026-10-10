"""Kid Icarus: Uprising plugin (3DS, EUR English): the game's MSBT text, its two bitmap fonts and the pictures
that depend on the language.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it). The game keeps its
files in ``darc`` archives (``.arc``, LZ11 ``.zrc``), often one inside another; the unpack writes each as a
folder of members at the path a LayeredFS mod replaces one member with (``2_build.bat`` repacks around it):

- ``romfs/eu/0.arc/resident/03.bin.msbt`` (Palutena's guidance, menus, weapons, powers, idols), ``04.bin.msbt``
  (system prompts), ``romfs/eu/00.arc/resident/00.bin.msbt`` (SpotPass and save messages),
  ``romfs/eu/menu/460.zrc/menu/bin.arc/bin/01.bin.msbt`` (idol toss and vault; 540 holds the same file),
  ``romfs/eu/stage/<stage>.zrc/stage/bin.arc/bin/msg_00.bin.msbt`` (in-level dialogue; ``msg_05`` is the English
  ground-section set of the ground stages). An MSBT member gets ``.msbt`` added by the unpack, so the plugin
  sees it; the build drops it again. An unedited file is written back byte for byte (``plugins.common.msbt``).
- ``romfs/eu/00.arc/resident/04.bin`` and ``romfs/eu/stage/a2800.zrc/stage/bin.arc/bin/fnt.bin`` -- the two
  bitmap fonts (``font_sources.json``). Dialogue is drawn with the console's shared font, not shipped here.
- ``romfs/eu/**/*.bcres`` -- the CGFX pictures the German folder ``eu_de`` overrides, so they carry text
  (``texture_sources.json``).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import tags
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# What a file holds, by its path inside the source folder.
ROLES = {"0.arc/resident/03.bin": "Menu, guidance, weapon, power and idol text", "0.arc/resident/04.bin": "System prompt",
         "00.arc/resident/00.bin": "System message (SpotPass, save data)", "bin/01.bin": "Idol and vault text"}


class GameRules(BaseGameRules):
    """Kid Icarus: Uprising (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}

    def get_display_name(self) -> str:
        return "Kid Icarus: Uprising"

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
        return [[tags.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            if text is None or text == tags.to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(tags.from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        self._msbt = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"kid_icarus: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".msbt"):
                found = (Path(source).as_posix(), Msbt(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"kid_icarus: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        rel_path, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        parts = Path(rel_path).parts
        stage = next((Path(part).stem for part in parts if part.lower().endswith(".zrc")), "")
        role = next((role for key, role in ROLES.items() if rel_path.endswith(key + ".msbt")), None)
        if role is None and "/stage/" in rel_path:
            role = f"In-level dialogue (stage {stage})"
        return {"path": rel_path, "file": Path(rel_path).name, "stage": stage, "label": msbt.labels.get(index, ""),
                "role": role}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found or not found["role"]:
            return {}
        return {"content_role": found["role"], "has_speaker": "dialogue" in found["role"]}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"resource": found["path"], "label": found["label"]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        where = f" (stage {found['stage']})" if found["stage"] else ""
        return f"Message {found['label']} in {found['file']}{where}"

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return tags.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
