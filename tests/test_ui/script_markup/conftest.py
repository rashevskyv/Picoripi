import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from .helpers import (
    _fresh_autosave_path,
)


class _FakeSettingsManager:
    def __init__(self, initial=None):
        self.values = dict(initial or {})
        self.saved = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save_settings(self, save_project_settings=True):
        self.saved += 1


class _FakeMainWindow(QWidget):
    def __init__(self, settings_manager=None):
        super().__init__()
        self.current_game_rules = None
        self.settings_manager = settings_manager
        self.script_markup_studio_autosave_path = _fresh_autosave_path()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app
