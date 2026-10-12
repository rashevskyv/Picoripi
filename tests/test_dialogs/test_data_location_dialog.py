"""Data folder chooser dialog: the confirmed choice is written to the pointer; cancel writes nothing."""
from pathlib import Path

import pytest

from core.data_location_choice import OPTION_CUSTOM, OPTION_LEGACY, OPTION_PORTABLE
from dialogs import data_location_dialog as dld
from utils import app_mode
from utils import data_location as dl


@pytest.fixture
def app_folder(tmp_path):
    folder = tmp_path / "app"
    folder.mkdir()
    return folder


def _pick(dialog, option):
    dialog._radios[option].setChecked(True)


def test_suggestion_is_pre_filled_but_needs_the_confirm_click(qtbot, app_folder):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    assert dialog._selected_option() == OPTION_PORTABLE
    assert dialog._current_target() == app_folder / "data"
    assert dialog.result_folder is None
    assert dl.read_pointer(app_folder) is None   # nothing is saved before the user confirms


def test_confirming_the_suggestion_saves_it_as_a_relative_pointer(qtbot, app_folder):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    dialog._confirm()
    assert dialog.result_folder == app_folder / "data"
    assert dl.read_pointer(app_folder) == "data"


def test_a_custom_folder_is_saved_as_given(qtbot, app_folder, tmp_path):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    chosen = tmp_path / "usb" / "picoripi"
    _pick(dialog, OPTION_CUSTOM)
    dialog._folder_edit.setText(str(chosen))
    dialog._confirm()
    assert dialog.result_folder == chosen
    assert Path(dl.read_pointer(app_folder)) == chosen


def test_an_unwritable_custom_folder_is_refused_and_nothing_is_saved(qtbot, app_folder, tmp_path, monkeypatch):
    blocker = tmp_path / "plain_file"
    blocker.write_text("x", encoding="utf-8")
    shown = []
    monkeypatch.setattr(dld.QMessageBox, "warning", lambda *args, **kwargs: shown.append(args[2]))
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    _pick(dialog, OPTION_CUSTOM)
    dialog._folder_edit.setText(str(blocker / "data"))
    dialog._confirm()
    assert dialog.result_folder is None
    assert dl.read_pointer(app_folder) is None
    assert shown


def test_old_profile_is_copied_into_the_chosen_folder_and_kept(qtbot, app_folder, tmp_path):
    legacy = tmp_path / "old_profile"
    (legacy / "plugins").mkdir(parents=True)
    (legacy / "settings.json").write_text("{}", encoding="utf-8")
    dialog = dld.DataLocationDialog(app_folder, legacy=legacy, first_start=True)
    qtbot.addWidget(dialog)
    assert OPTION_LEGACY in dialog._model.options()
    assert dialog._copy_check.isChecked()
    dialog._confirm()
    qtbot.waitUntil(lambda: dialog.result_folder is not None, timeout=10000)
    assert (app_folder / "data" / "settings.json").read_text(encoding="utf-8") == "{}"
    assert (legacy / "settings.json").exists()   # the old folder is never touched
    assert dl.read_pointer(app_folder) == "data"


def test_keeping_the_old_profile_saves_it_without_copying(qtbot, app_folder, tmp_path):
    legacy = tmp_path / "old_profile"
    legacy.mkdir()
    dialog = dld.DataLocationDialog(app_folder, legacy=legacy, first_start=True)
    qtbot.addWidget(dialog)
    _pick(dialog, OPTION_LEGACY)
    dialog._confirm()
    assert dialog.result_folder == legacy
    assert Path(dl.read_pointer(app_folder)) == legacy
    assert not (app_folder / "data").exists()


def test_settings_mode_copies_the_current_folder_to_the_new_one(qtbot, app_folder, tmp_path):
    current = tmp_path / "current"
    current.mkdir()
    (current / "settings.json").write_text("{\"a\": 1}", encoding="utf-8")
    dialog = dld.DataLocationDialog(app_folder, current=current, first_start=False)
    qtbot.addWidget(dialog)
    assert OPTION_LEGACY not in dialog._radios      # the current folder is not offered as a choice here
    target = tmp_path / "moved"
    _pick(dialog, OPTION_CUSTOM)
    dialog._folder_edit.setText(str(target))
    dialog._confirm()
    qtbot.waitUntil(lambda: dialog.result_folder is not None, timeout=10000)
    assert (target / "settings.json").read_text(encoding="utf-8") == "{\"a\": 1}"
    assert (current / "settings.json").exists()


def test_cancelled_copy_saves_no_pointer(qtbot, app_folder, tmp_path):
    legacy = tmp_path / "old_profile"
    legacy.mkdir()
    dialog = dld.DataLocationDialog(app_folder, legacy=legacy, first_start=True)
    qtbot.addWidget(dialog)
    dialog._choice = dialog._model.build_choice(OPTION_PORTABLE, None, copy_legacy=True)
    dialog._copy_done(dld.CopyResult(stopped=True))   # the user pressed Cancel copy
    assert dialog.result_folder is None
    assert dl.read_pointer(app_folder) is None


def test_tests_never_open_the_chooser(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(dld.DataLocationDialog, "exec", lambda self: opened.append(True) or 0)
    assert app_mode.headless
    assert dld.ensure_data_location_chosen() is True
    assert opened == []


def test_an_explicit_choice_skips_the_chooser(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(dld.DataLocationDialog, "exec", lambda self: opened.append(True) or 0)
    monkeypatch.setattr(app_mode, "headless", False)
    assert dld.ensure_data_location_chosen() is True   # conftest sets PICORIPI_HOME: an explicit choice
    assert opened == []
