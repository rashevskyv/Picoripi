from enum import Enum, auto
from typing import Set, ContextManager
from contextlib import contextmanager
from utils.logging_utils import log_debug

class AppState(Enum):
    """
    Enum representing all possible states of the application.
    This replaces the 46+ boolean flags in MainWindow:
    
    1. is_adjusting_cursor
    2. is_adjusting_selection
    3. is_programmatically_changing_text
    4. is_restart_in_progress
    5. is_closing
    6. is_loading_data
    7. is_saving_data
    8. is_reverting_data
    9. is_reloading_data
    10. is_pasting_block
    11. is_undoing_paste
    12. is_auto_fixing
    """
    # UI Interaction & Flow Control
    ADJUSTING_CURSOR = auto()
    ADJUSTING_SELECTION = auto()
    PROGRAMMATIC_TEXT_CHANGE = auto()
    RESTART_IN_PROGRESS = auto()
    CLOSING = auto()

    # Data Operations
    LOADING_DATA = auto()
    SAVING_DATA = auto()
    REVERTING_DATA = auto()
    RELOADING_DATA = auto()
    PASTING_BLOCK = auto()
    UNDOING_PASTE = auto()
    AUTO_FIXING = auto()

class StateManager:
    """
    Centralized manager for application states.
    Prevents recursive events and tracks long-running operations.
    """
    def __init__(self):
        self._active_states: Set[AppState] = set()

    @contextmanager
    def enter(self, state: AppState) -> ContextManager[None]:
        """
        Context manager to safely enter and exit a state.
        Usage: with state_manager.enter(AppState.LOADING): ...
        """
        self._active_states.add(state)
        # log_debug(f"StateManager: ENTERED {state.name}")
        try:
            yield
        finally:
            self._active_states.discard(state)
            # log_debug(f"StateManager: EXITED {state.name}")

    def is_active(self, state: AppState) -> bool:
        """Check if a specific state is currently active."""
        return state in self._active_states

    def any_of(self, *states: AppState) -> bool:
        """Check if any of the given states are active."""
        return any(state in self._active_states for state in states)
    
    def set_active(self, state: AppState, active: bool):
        """Manually set a state (use sparingly, context manager is preferred)."""
        if active:
            self._active_states.add(state)
        else:
            self._active_states.discard(state)

    def clear(self):
        """Reset all states."""
        self._active_states.clear()
