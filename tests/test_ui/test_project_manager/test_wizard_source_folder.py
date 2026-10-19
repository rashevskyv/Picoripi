"""Existing extracted sources and recoverable console-key errors in the project wizard."""
from pathlib import Path

import pytest

from core.containers.console_crypto import KeyFileError
from core.project_library import build
from core.project_library.source_folder import validate_source_folder
from plugins.base_game_rules import BaseGameRules
from plugins.yokai_watch.rules import GameRules
from test_core.test_n3ds_image import build_cci, build_ncch
from test_plugins.test_yokai_watch.samples import cfg_file, text_info
from ui.project_manager import wizard as wizard_module
from ui.project_manager.wizard import ProjectWizard


def _ready(qtbot, wizard):
    qtbot.waitUntil(lambda: not wizard._jobs, timeout=10000)
    wizard._game.addItem("Test game", "test")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)


def test_yokai_extracted_folder_creates_without_image_or_keys(qtbot, tmp_path, monkeypatch):
    source = tmp_path / "source"
    table = source / "data/res/text/system_text_en.cfg.bin"
    table.parent.mkdir(parents=True)
    content = cfg_file([text_info(1, 0, "Hello")])
    table.write_bytes(content)
    translation = tmp_path / "existing-translation"
    translation.mkdir()
    created = []
    wizard = ProjectWizard(None, lambda _name: GameRules(), created.append)
    qtbot.addWidget(wizard)
    _ready(qtbot, wizard)
    wizard.add_paths([str(source)], source_folder=True)
    qtbot.waitUntil(lambda: not wizard._jobs, timeout=10000)
    wizard._name.setText("Yo-kai")
    wizard._folder.setText(str(tmp_path / "project"))
    wizard._use_existing.setChecked(True)
    wizard._existing_folder.setText(str(translation))

    def no_image_unpack(*_args, **_kwargs):
        pytest.fail("an extracted source must not enter image unpacking")

    monkeypatch.setattr(build, "run_unpack", no_image_unpack)
    wizard._create_clicked()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)
    assert created[0]["source_path"] == str(source)
    assert created[0]["is_directory_mode"] is True
    assert created[0]["translation_path"] == str(translation)
    assert created[0]["metadata"]["unpacked"] is False
    assert table.read_bytes() == content
    assert wizard._picked_keys == {}
    assert not (tmp_path / "project" / "unpacked").exists()
    from core.project.manager import ProjectManager
    info = created[0]
    manager = ProjectManager()
    assert manager.create_new_project(
        info["directory"], info["name"], info["plugin"], source_path=info["source_path"],
        translation_path=info["translation_path"], is_directory_mode=info["is_directory_mode"],
        auto_create_translations=info["auto_create_translations"])
    reopened = ProjectManager()
    assert reopened.load(manager.project_file_path)
    assert reopened.project.metadata["source_path"] == str(source)
    assert reopened.project.metadata["translation_path"] == str(translation)
    assert reopened.project.metadata["is_directory_mode"] is True


def test_invalid_extracted_source_is_recoverable(qtbot, tmp_path):
    source = tmp_path / "romfs"
    source.mkdir()
    (source / "yw1_a.fa").write_bytes(b"unexpanded archive")
    (source / "README.txt").write_text("Instructions, not game text", encoding="utf-8")
    (source / "config.json").write_text('{"name": "unrelated"}', encoding="utf-8")
    created = []
    wizard = ProjectWizard(None, lambda _name: GameRules(), created.append)
    qtbot.addWidget(wizard)
    _ready(qtbot, wizard)
    wizard.add_paths([str(source)], source_folder=True)
    qtbot.waitUntil(lambda: not wizard._jobs, timeout=10000)
    wizard._name.setText("Yo-kai")
    wizard._folder.setText(str(tmp_path / "project"))
    wizard._create_clicked()
    qtbot.waitUntil(lambda: wizard._unpack_job is None, timeout=10000)
    assert wizard._progress_text.text() == (
        "Unpacking failed: No readable game text was found. Choose the extracted source folder for this game, "
        "with its text tables unpacked from game archives.")
    assert created == []
    assert wizard._create.isEnabled()
    assert not (tmp_path / "project").exists()


def test_folder_resolves_plugin_subfolder_and_obeys_cancel(tmp_path):
    class Rules(BaseGameRules):
        def get_source_subfolder(self):
            return "files/text"

    source = tmp_path / "files/text"
    source.mkdir(parents=True)
    (source / "dialogue.txt").write_text("Hello", encoding="utf-8")
    assert validate_source_folder(Rules(), tmp_path, lambda: False) == str(source)
    assert validate_source_folder(Rules(), source, lambda: False) == str(source)
    with pytest.raises(build.Cancel):
        validate_source_folder(Rules(), tmp_path, lambda: True)


def test_yokai_folder_filter_preserves_base_exclusions(monkeypatch):
    monkeypatch.setattr(BaseGameRules, "includes_source_file", lambda _self, path: not path.startswith("reference/"))
    rules = GameRules()
    assert rules.includes_source_file("data/text.cfg.bin") is True
    assert rules.includes_source_file("reference/text.cfg.bin") is False
    assert rules.includes_source_file("README.txt") is False


def test_yokai_image_failure_is_unsupported_plugin_not_missing_keys(tmp_path):
    image = tmp_path / "game.cia"
    image.write_bytes(build_cci(build_ncch(encrypted=True)))
    with pytest.raises(ValueError) as caught:
        build.run_unpack(GameRules(), {"base": str(image)}, tmp_path / "project", lambda *_: None, lambda: False)
    assert str(caught.value) == (
        "This game's plugin cannot unpack this image. Choose an already-extracted "
        "game folder with its text tables unpacked from game archives.")
    assert not isinstance(caught.value, KeyFileError)
    assert list((tmp_path / "project").iterdir()) == []


def test_wrong_key_can_be_replaced_in_same_wizard(qtbot, tmp_path, monkeypatch):
    class Rules(BaseGameRules):
        def unpack_sources(self, sources, target_dir, progress, is_cancelled):
            from core.containers.console_crypto import key_path
            if Path(key_path("3ds") or "missing").name != "replacement.txt":
                raise KeyFileError("3ds", "The key file does not decrypt the Nintendo 3DS image.")
            Path(target_dir, "dialogue.txt").write_text("Hello", encoding="utf-8")
            return target_dir

    from utils import constants
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "settings")
    image = tmp_path / "game.bin"
    image.write_bytes(b"source")
    replacement = tmp_path / "replacement.txt"
    replacement.write_text("synthetic fixture", encoding="ascii")
    created = []
    wizard = ProjectWizard(None, lambda _name: Rules(), created.append)
    qtbot.addWidget(wizard)
    _ready(qtbot, wizard)
    wizard.add_paths([str(image)])
    qtbot.waitUntil(lambda: not wizard._jobs, timeout=10000)
    wizard._name.setText("Retry")
    wizard._folder.setText(str(tmp_path / "project"))
    wizard._create_clicked()
    qtbot.waitUntil(lambda: wizard._unpack_job is None, timeout=10000)
    assert not wizard._add_key.isHidden()
    assert wizard._progress_text.text() == "Unpacking failed: The key file does not decrypt the Nintendo 3DS image."

    monkeypatch.setattr(wizard_module.QFileDialog, "getOpenFileName", lambda *_: (str(replacement), ""))
    wizard._add_key.click()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)
    assert created[0]["name"] == "Retry"
    assert created[0]["source_path"] == str(tmp_path / "project/unpacked")
    assert created[0]["metadata"]["source_roles"] == {"base": str(image)}
    assert Path(created[0]["source_path"], "dialogue.txt").read_text(encoding="utf-8") == "Hello"


def test_missing_key_cancel_and_retry_preserve_project_inputs(qtbot, tmp_path, monkeypatch):
    from core.project_library import images
    from test_core.test_n3ds_decrypt import encrypt_ncch, standard_keys
    from utils import constants

    class Rules(BaseGameRules):
        def unpack_key_consoles(self):
            return ["3ds"]

        def unpack_sources(self, sources, target_dir, progress, is_cancelled):
            return images.extract(sources["base"], target_dir, progress, is_cancelled)

    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "settings")
    image = tmp_path / "encrypted.cci"
    image.write_bytes(build_cci(encrypt_ncch(build_ncch())))
    created = []
    wizard = ProjectWizard(None, lambda _name: Rules(), created.append)
    qtbot.addWidget(wizard)
    _ready(qtbot, wizard)
    wizard.add_paths([str(image)])
    qtbot.waitUntil(lambda: not wizard._jobs, timeout=10000)
    wizard._name.setText("Encrypted game")
    project = tmp_path / "project"
    wizard._folder.setText(str(project))
    monkeypatch.setattr(wizard_module.QFileDialog, "getOpenFileName", lambda *_: ("", ""))
    wizard._create_clicked()
    assert wizard._progress_text.text() == "No key file was chosen. Nothing was created."
    assert not wizard._add_key.isHidden()
    assert not project.exists()
    assert created == []
    wizard._add_key.click()
    assert wizard._name.text() == "Encrypted game"
    assert wizard._folder.text() == str(project)
    assert created == []

    keys = standard_keys(tmp_path)
    monkeypatch.setattr(wizard_module.QFileDialog, "getOpenFileName", lambda *_: (keys, ""))
    wizard._add_key.click()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)
    assert created[0]["name"] == "Encrypted game"
    assert Path(created[0]["source_path"], "romfs/a.bin").read_bytes() == b"hello"
