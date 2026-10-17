"""The Console keys tab of the settings dialog: one row per console, Browse stores a path, Clear forgets it."""
import pytest
from PyQt6.QtWidgets import QDialog, QWidget

from core.project_library import console_keys
from ui.settings import console_keys_mixin
from ui.settings.console_keys_mixin import SettingsConsoleKeysMixin
from utils import constants


class Host(SettingsConsoleKeysMixin, QDialog):
    """The mixin needs a widget host, as the settings dialog is."""

    def __init__(self):
        super().__init__()
        self.console_keys_tab = QWidget(self)
        self.setup_console_keys_tab()


class ChosenFile:
    """Stands in for the file dialog: returns the path the test picked."""
    path = ""

    @staticmethod
    def getOpenFileName(*_args, **_kwargs):
        return ChosenFile.path, ""


@pytest.fixture
def data_folder(tmp_path, monkeypatch):
    folder = tmp_path / "data"
    monkeypatch.setattr(constants, "SETTINGS_DIR", folder)
    monkeypatch.setattr(console_keys_mixin, "QFileDialog", ChosenFile)
    return folder


def test_tab_has_one_row_per_console_and_shows_none_stored(qtbot, data_folder):
    host = Host()
    qtbot.addWidget(host)

    assert set(host._console_key_edits) == set(console_keys.CONSOLES)
    qtbot.waitUntil(lambda: host._console_key_states["3ds"].text() == "Not set", timeout=5000)
    assert not host._console_key_clears["3ds"].isEnabled()


def test_browse_stores_the_path_and_the_tab_says_the_file_is_found(qtbot, data_folder, tmp_path):
    key_file = tmp_path / "aes_keys.txt"
    key_file.write_bytes(b"placeholder")
    host = Host()
    qtbot.addWidget(host)
    ChosenFile.path = str(key_file)

    host._console_key_browse("3ds")

    qtbot.waitUntil(lambda: host._console_key_states["3ds"].text() == "File found", timeout=5000)
    assert host._console_key_edits["3ds"].text() == str(key_file)
    assert console_keys.path_for("3ds") == str(key_file)


def test_clear_forgets_the_path(qtbot, data_folder, tmp_path):
    key_file = tmp_path / "prod.keys"
    key_file.write_bytes(b"placeholder")
    console_keys.set_path("switch", str(key_file))
    host = Host()
    qtbot.addWidget(host)
    qtbot.waitUntil(lambda: host._console_key_states["switch"].text() == "File found", timeout=5000)

    host._console_key_clear("switch")

    qtbot.waitUntil(lambda: host._console_key_edits["switch"].text() == "", timeout=5000)
    assert console_keys.stored("switch") == ""
