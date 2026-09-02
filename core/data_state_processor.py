from pathlib import Path
from typing import List, Optional, Any, Set
from utils.logging_utils import log_warning

from PyQt6.QtCore import QTimer
from .data_manager import save_json_file, save_text_file
from .data_processor.session_manager import SessionManager
from .data_processor.revert_manager import RevertManager
from .data_processor.set_calculator import SetCalculator
from .data_processor import save_mixin as _save_mixin
from .data_processor.ui_msg_mixin import UiMsgMixin
from .data_processor.query_mixin import QueryMixin
from .data_processor.save_mixin import SaveMixin


class _ShimName:
    """Late-bound name that always reads from this module."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _resolve(self):
        import sys
        return getattr(sys.modules[__name__], object.__getattribute__(self, "_name"))

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __repr__(self):
        return repr(self._resolve())


# Tests patch these on core.data_state_processor; SaveMixin uses them as globals.
_save_mixin.Path = _ShimName("Path")
_save_mixin.save_json_file = _ShimName("save_json_file")
_save_mixin.save_text_file = _ShimName("save_text_file")

__all__ = [
    "DataStateProcessor",
    "Path",
    "save_json_file",
    "save_text_file",
]


class DataStateProcessor(UiMsgMixin, QueryMixin, SaveMixin):
    """Data state processor implementation."""
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

        # Decomposed managers
        self.session_manager = SessionManager(self)
        self.revert_manager = RevertManager(self)
        self.set_calculator = SetCalculator(self)

        try:
            self.autosave_timer = QTimer()
            self.autosave_timer.setSingleShot(True)
            self.autosave_timer.setInterval(2000)  # 2 seconds debounce
            self.autosave_timer.timeout.connect(self._autosave_session)

            self.durable_session_timer = QTimer()
            self.durable_session_timer.setInterval(300000)  # 5 minutes
            self.durable_session_timer.timeout.connect(lambda: self._save_durable_session_json(force=False))
            self.durable_session_timer.start()
        except Exception as e:
            log_warning(f"DSP: Failed to initialize QTimer (probably running in non-GUI test environment): {e}")
            self.autosave_timer = None
            self.durable_session_timer = None

    @property
    def _session_dirty(self) -> bool:
        return self.session_manager._session_dirty

    @_session_dirty.setter
    def _session_dirty(self, val: bool) -> None:
        self.session_manager._session_dirty = val

    @property
    def _durable_session_dirty(self) -> bool:
        return self.session_manager._durable_session_dirty

    @_durable_session_dirty.setter
    def _durable_session_dirty(self, val: bool) -> None:
        self.session_manager._durable_session_dirty = val

    def revert_strings_to_original(self, block_idx: int, string_indices: List[int], progress_dialog=None, progress_offset: int = 0) -> int:
        """Reverts multiple strings in a block to their original state (from the loaded file)."""
        return self.revert_manager.revert_strings_to_original(block_idx, string_indices, progress_dialog, progress_offset)

    def perform_revert_strings(self, block_idx: int, string_indices: List[Any], confirm: bool = True) -> None:
        """Unified revert function with optional confirmation and UI updates."""
        self.revert_manager.perform_revert_strings(block_idx, string_indices, confirm)

    def revert_blocks_to_original(self, block_indices: List[int]) -> None:
        """Reverts entire blocks to their state from the loaded edited file (or original)."""
        self.revert_manager.revert_blocks_to_original(block_indices)

    def revert_edited_file_to_original(self) -> bool:
        """Revert edited file to original."""
        return self.revert_manager.revert_edited_file_to_original()

    def get_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading session data."""
        return self.session_manager.get_session_file_path()

    def get_durable_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading durable JSON session data."""
        return self.session_manager.get_durable_session_file_path()

    def _serialize_action(self, action: Any) -> dict:
        return self.session_manager._serialize_action(action)

    def _deserialize_action(self, data: dict) -> Any:
        return self.session_manager._deserialize_action(data)

    def serialize_session_to_json(self, snapshot: dict) -> dict:
        """Serialize AppDataStore snapshot to a JSON-compatible dictionary."""
        return self.session_manager.serialize_session_to_json(snapshot)

    def deserialize_session_from_json(self, json_data: dict) -> dict:
        """Deserialize JSON-compatible dictionary to AppDataStore snapshot format."""
        return self.session_manager.deserialize_session_from_json(json_data)

    def schedule_autosave(self) -> None:
        """Schedule session autosave after a short delay (debounce)."""
        self.session_manager.schedule_autosave()

    def _autosave_session(self, force: bool = False) -> None:
        """Autosave entire data_store into a pickle file if dirty or forced."""
        self.session_manager._autosave_session(force)

    def _save_durable_session_json(self, force: bool = False) -> bool:
        """Autosave entire data_store into a JSON file if dirty or forced."""
        return self.session_manager._save_durable_session_json(force)

    def finalize_clean_shutdown_checkpoint(self) -> bool:
        """Finalize the fast Pickle checkpoint for a clean application exit."""
        return self.session_manager.finalize_clean_shutdown_checkpoint()

    def load_session_file(self) -> bool:
        """Load entire project state from a JSON file (preferred) or a pickle file (fallback)."""
        return self.session_manager.load_session_file()

    def clear_session_file(self) -> None:
        """Delete the temporary session file if it exists."""
        self.session_manager.clear_session_file()

    # === Fast Filtering Indexes (A05) ===

    def get_empty_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of empty string indices for the given block."""
        return self.set_calculator.get_empty_set(block_idx)

    def get_translated_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of translated string indices for the given block."""
        return self.set_calculator.get_translated_set(block_idx)

    def get_needs_translation_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of strings whose original text needs translation."""
        return self.set_calculator.get_needs_translation_set(block_idx)

    def get_unsaved_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of unsaved string indices for the given block."""
        return self.set_calculator.get_unsaved_set(block_idx)

    def get_overrides_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of override string indices for the given block."""
        return self.set_calculator.get_overrides_set(block_idx)

    def get_categorized_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of categorized string indices for the given block."""
        return self.set_calculator.get_categorized_set(block_idx)

    def ensure_index_warnings(self, block_idx: int):
        """Helper to build warnings index if it is missing."""
        self.set_calculator.ensure_index_warnings(block_idx)

    def get_warnings_matching_set(self, block_idx: int, active_filters: List[str], detection_config: dict) -> Set[int]:
        """Get the set of string indices matching active or enabled warnings."""
        return self.set_calculator.get_warnings_matching_set(block_idx, active_filters, detection_config)
