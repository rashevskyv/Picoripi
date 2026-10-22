"""The wizard and the default key source: the order of the offers, the consent, the download, the create-time choice."""
import os

import pytest

from core.project_library import key_source
from test_core.key_source_server import serve_all, serve_loopback
from test_core.test_n3ds_image import build_cci, build_ncch
from test_ui.test_project_manager.test_wizard_and_rows import _loader, _wait_for_plugins
from ui.project_manager import wizard as wizard_module
from ui.project_manager.wizard import ProjectWizard

@pytest.fixture
def loopback_source():
    with serve_loopback() as value:
        yield value



def _encrypted_wizard(qtbot, tmp_path):
    locked = tmp_path / "locked.cci"
    locked.write_bytes(build_cci(build_ncch(encrypted=True)))
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard._show_page(1)
    wizard.add_paths([str(locked)])
    qtbot.waitUntil(lambda: (wizard._key_status.get(str(locked)) or {}).get("key") == "3ds", timeout=10000)
    qtbot.waitUntil(lambda: wizard._source is not None, timeout=10000)
    return wizard


def _key_buttons(wizard):
    buttons = [wizard._key_bar.itemAt(index).widget() for index in range(wizard._key_bar.count())]
    return [button for button in buttons if button is not None]


def test_the_default_source_is_offered_before_the_file_button(qtbot, tmp_path, loopback_source):
    base, _routes = loopback_source
    key_source.set_config(base_url=base)
    wizard = _encrypted_wizard(qtbot, tmp_path)

    texts = [button.text() for button in _key_buttons(wizard)]

    assert texts == ["Get keys from the source you set", "Add the key file for Nintendo 3DS..."]


def test_the_get_button_downloads_after_consent_and_clears_the_problem(qtbot, tmp_path, loopback_source, monkeypatch):
    base, routes = loopback_source
    serve_all(routes)
    key_source.set_config(base_url=base)
    monkeypatch.setattr(wizard_module, "confirm_download", lambda *_args: True)
    wizard = _encrypted_wizard(qtbot, tmp_path)

    _key_buttons(wizard)[0].click()

    qtbot.waitUntil(lambda: wizard._download_job is None and wizard._files_problems.text() == "", timeout=15000)
    assert wizard._picked_keys["3ds"].endswith("aes_keys.txt")
    assert os.path.isfile(wizard._picked_keys["3ds"])


def test_a_declined_consent_starts_no_download(qtbot, tmp_path, loopback_source, monkeypatch):
    base, _routes = loopback_source
    key_source.set_config(base_url=base)
    monkeypatch.setattr(wizard_module, "confirm_download", lambda *_args: False)
    wizard = _encrypted_wizard(qtbot, tmp_path)

    assert wizard._get_keys_from_source("3ds") is False
    assert wizard._download_job is None
    assert "3ds" not in wizard._picked_keys


def test_at_create_time_get_downloads_and_then_creates_again(qtbot, tmp_path, loopback_source, monkeypatch):
    base, routes = loopback_source
    serve_all(routes)
    key_source.set_config(base_url=base)
    monkeypatch.setattr(wizard_module, "confirm_download", lambda *_args: True)
    monkeypatch.setattr(ProjectWizard, "_ask_key_source", lambda self, console: "get")
    wizard = _encrypted_wizard(qtbot, tmp_path)
    created = []
    monkeypatch.setattr(wizard, "_create_clicked", lambda: created.append(True))

    assert wizard._ask_key_files(wizard._file_choices()) is None   # the download runs; the create waits for it
    qtbot.waitUntil(lambda: wizard._download_job is None and created == [True], timeout=15000)
    assert wizard._picked_keys["3ds"] == str(key_source.managed_dir("3ds") / "aes_keys.txt")


def test_at_create_time_choose_opens_the_file_dialog(qtbot, tmp_path, loopback_source, monkeypatch):
    base, _routes = loopback_source
    key_source.set_config(base_url=base)
    key_file = tmp_path / "chosen_aes_keys.txt"
    key_file.write_bytes(b"placeholder")
    monkeypatch.setattr(ProjectWizard, "_ask_key_source", lambda self, console: "choose")

    class FakeDialog:
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return str(key_file), ""

    monkeypatch.setattr(wizard_module, "QFileDialog", FakeDialog)
    wizard = _encrypted_wizard(qtbot, tmp_path)

    assert wizard._ask_key_files(wizard._file_choices()) == {"3ds": str(key_file)}
