"""The default key source in the Console keys tab: what it shows, the switch, the consent, the download."""
import pytest
from PyQt6.QtWidgets import QDialog, QWidget

from core.project_library import console_keys, key_source
from test_core.key_source_server import serve_all, serve_loopback
from ui.settings import console_keys_mixin
from ui.settings.console_keys_mixin import SettingsConsoleKeysMixin
from utils import constants

@pytest.fixture
def loopback_source():
    with serve_loopback() as value:
        yield value



class Host(SettingsConsoleKeysMixin, QDialog):
    """The mixin needs a widget host, as the settings dialog is."""

    def __init__(self):
        super().__init__()
        self.console_keys_tab = QWidget(self)
        self.setup_console_keys_tab()


@pytest.fixture
def data_folder(tmp_path, monkeypatch):
    folder = tmp_path / "data"
    monkeypatch.setattr(constants, "SETTINGS_DIR", folder)
    return folder


def test_the_tab_shows_the_default_source_and_that_nothing_is_downloaded_yet(qtbot, data_folder):
    host = Host()
    qtbot.addWidget(host)

    qtbot.waitUntil(lambda: host._source_view_data is not None, timeout=5000)
    assert host._source_on.isChecked()
    assert host._source_address.text() == ""
    assert not host._source_default.isEnabled()
    assert host._source_info.text() == "Nothing has been downloaded yet."


def test_switching_the_source_off_is_saved_and_disables_the_download(qtbot, data_folder):
    host = Host()
    qtbot.addWidget(host)
    qtbot.waitUntil(lambda: host._source_view_data is not None, timeout=5000)

    host._source_on.setChecked(False)

    qtbot.waitUntil(lambda: key_source.config()["enabled"] is False, timeout=5000)
    qtbot.waitUntil(lambda: not host._source_get.isEnabled(), timeout=5000)


def test_a_declined_consent_starts_no_download(qtbot, data_folder, monkeypatch):
    monkeypatch.setattr(console_keys_mixin, "confirm_download", lambda *_args: False)
    host = Host()
    qtbot.addWidget(host)
    qtbot.waitUntil(lambda: host._source_view_data is not None, timeout=5000)

    host._get_from_source()

    assert host._download_job is None
    assert console_keys.path_for("3ds") is None


def test_get_from_the_source_downloads_into_the_data_folder_after_consent(qtbot, data_folder, loopback_source, monkeypatch):
    base, routes = loopback_source
    serve_all(routes)
    key_source.set_config(base_url=base)
    monkeypatch.setattr(console_keys_mixin, "confirm_download", lambda *_args: True)
    host = Host()
    qtbot.addWidget(host)
    qtbot.waitUntil(lambda: host._source_view_data is not None, timeout=5000)

    host._get_from_source()

    qtbot.waitUntil(lambda: host._download_job is None and "Downloaded" in host._source_status.text(), timeout=15000)
    assert "Nintendo 3DS" in host._source_status.text()
    assert console_keys.path_for("3ds") == str(key_source.managed_dir("3ds") / "aes_keys.txt")
    qtbot.waitUntil(lambda: host._console_key_states["3ds"].text() == "File found", timeout=5000)
