"""Zelda DS plugin (Phantom Hourglass, Spirit Tracks).

The project's source folder is the workspace's ``source``: the game's own BMG message files at their paths in the
cartridge's file system (``English/Message/*.bmg``, and ``staff.bmg`` of Spirit Tracks). One block is one file; one
string is one message. Saving writes the whole file into the translation folder: only the edited messages change,
every other byte of the file stays as it was (see ``bmg``). The workspace's build puts the files into the ROM.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

from .bmg import Bmg, BmgError, build
from . import unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(BaseGameRules):
    """Zelda DS: the plugin reads each BMG file as the list of its messages."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, Bmg]]] = {}

    # Project Manager: the cartridge (USA) is read by core/project_library/images.py; unpack.py picks the files.
    def get_platforms(self) -> list:
        return [{"id": "nds", "label": tr("Nintendo DS")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, self._declared_ids())

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        return unpack.extract(base, target_dir, progress, is_cancelled) if base else None

    def get_display_name(self) -> str:
        return "Zelda (DS): Phantom Hourglass / Spirit Tracks"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bmg",), "bytes", "Zelda DS messages (BMG)"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [Bmg(self._last_loaded).texts()], {}
        except (BmgError, ValueError, IndexError, UnicodeDecodeError, StopIteration) as error:
            log_debug(f"zelda_ds: not a BMG message file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        """Every save starts from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        strings = [str(s) for s in (data[0] if data else [])]
        current = Bmg(source).texts()
        changed = {i: s for i, s in enumerate(strings) if i < len(current) and s != current[i]}
        return build(source, changed)

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, Bmg]]:
        """``(relative path, parsed source file)`` of a block, cached."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            rel = str(block.source_file).replace("\\", "/")
            path = Path(pm.get_absolute_path(block.source_file))
            found = (rel, Bmg(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError, BmgError) as error:
            log_debug(f"zelda_ds: no file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        located = self._locate(block_idx)
        if not located or not 0 <= string_idx < located[1].count:
            return None
        rel, bmg = located
        return {"file": rel, "index": string_idx, "file_offset": bmg.offsets[string_idx]}
