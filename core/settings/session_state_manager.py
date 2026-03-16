# --- START OF FILE core/settings/session_state_manager.py ---
import json
from pathlib import Path
from utils.logging_utils import log_debug, log_error

class SessionStateManager:
    """Manages the UI session state (expanded nodes, selection, etc.)"""
    def __init__(self, settings_file_path="session_state.json"):
        self.settings_file_path = settings_file_path
        self._state = {}
        self.load()

    def load(self):
        if not Path(self.settings_file_path).exists():
            self._state = {}
            return
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                self._state = json.load(f)
        except Exception as e:
            log_error(f"Error loading session state: {e}")
            self._state = {}

    def save(self):
        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            log_error(f"Error saving session state: {e}")

    def get_state_for_file(self, file_path_key: str):
        """Returns the state dictionary for a specific file/project path."""
        # Using the file path as a key to persist per-file state
        return self._state.get(file_path_key, {})

    def set_state_for_file(self, file_path_key: str, state_data: dict):
        self._state[file_path_key] = state_data
        self.save()

    def cleanup_old_states(self, max_entries=50):
        # Optional: prevent the file from growing indefinitely
        if len(self._state) > max_entries:
            # Simple cleanup: keep newest entries
            pass
