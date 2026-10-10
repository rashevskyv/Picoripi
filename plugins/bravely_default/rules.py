"""Bravely Default plugin (3DS, EUR English): the game's BTBF text tables, its font and its pictures with text.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it). The game keeps its
English text in ``Common_en`` as BTBF tables, most of them inside ``index.fs`` + ``crowd.fs`` pairs that the
unpack writes as folders of members (``2_build.bat`` packs them back):

- ``romfs/Common_en/<Table>/crowd.fs/<Name>.btb`` (``.txb`` event text, ``.spb`` party chat, ``.trb``
  tutorials, ``.mtb`` menus, ``.tbl``, ``.subtitles``) -- one block per table, one string per entry of its
  string table (``btbf.py``). An unedited table is written back byte for byte.
- ``romfs/Graphics/UI_en/Font/Font/root/font/hikari.bcfnt`` -- the game font (``font_sources.json``).
- ``romfs/Graphics/UI_en/**/*.bclim`` -- every English layout picture (``texture_sources.json``).

Text markup is plain: ``\\n`` line breaks, ``[PCM1]``-style name slots and ``$`` variables stay as typed.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning

from .btbf import Btbf, label_of
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

EXTENSIONS = (".btb", ".txb", ".spb", ".trb", ".mtb", ".tbl", ".subtitles")
# What a table holds, by its name (the rest are named by the table itself).
ROLES = {"ItemTable": "Item name or description", "MonsterData": "Enemy name", "CommandAbility": "Ability name or description",
         "SupportAbility": "Ability name or description", "SpecialTable": "Special move text", "JobTable": "Job name",
         "PcTable": "Character name", "Subtitles": "Movie subtitle", "PartyChat": "Party chat dialogue",
         "TextTable": "Event dialogue", "TutorialTable": "Tutorial text", "MenuTable": "Menu text",
         "MessageTable": "System message", "Shop": "Shop text", "DReportTable": "D's Journal entry"}


class GameRules(BaseGameRules):
    """Bravely Default (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._table: Optional[Btbf] = None
        self._paths: Dict[int, Optional[str]] = {}

    def get_display_name(self) -> str:
        return "Bravely Default"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat(EXTENSIONS, "bytes", "BTBF tables"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._table = None
            return super().load_data_from_json_obj(json_obj)
        self._table = Btbf(json_obj)
        return [list(self._table.texts)], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._table is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = [str(texts[i]) if i < len(texts) and texts[i] is not None else original
                   for i, original in enumerate(self._table.texts)]
        return self._table.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """A table is rebuilt from the existing file (rows, ASCII table): load the newest that parses."""
        self._table = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(EXTENSIONS):
            return
        for raw in context.existing_versions():
            try:
                self._table = Btbf(raw)
                return
            except (ValueError, IndexError, KeyError) as error:
                log_warning(f"bravely_default: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._table = None
        self._paths.clear()

    # -- where a string comes from -----------------------------------------------

    def _path(self, block_idx: int) -> Optional[str]:
        if block_idx not in self._paths:
            found = None
            try:
                pm = self.mw.project_manager
                project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
                found = Path(str(pm.project.blocks[project_idx].source_file)).as_posix()
            except (AttributeError, IndexError, KeyError, TypeError):
                found = None
            self._paths[block_idx] = found
        return self._paths[block_idx]

    def _role(self, block_idx: int) -> Optional[str]:
        path = self._path(block_idx)
        if not path:
            return None
        parts = Path(path).parts
        for key, role in ROLES.items():
            if any(part.startswith(key) for part in parts):
                return role
        return f"Text of table {Path(path).stem}"

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        role = self._role(block_idx)
        return {"content_role": role, "has_speaker": False} if role else {}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        path = self._path(block_idx)
        if not path:
            return None
        try:
            table = Btbf(Path(self.mw.project_manager.get_absolute_path(path)).read_bytes())
            cell = label_of(table, int(string_idx))
        except (AttributeError, OSError, TypeError, ValueError):
            cell = None
        return f"{Path(path).name}" + (f", {cell}" if cell else "")

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        path = self._path(block_idx)
        return {"resource": path} if path else {}
