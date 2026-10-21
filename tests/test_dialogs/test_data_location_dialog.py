"""Data folder chooser dialog: the confirmed choice is written to the pointer; cancel writes nothing."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core import i18n
from core.data_location_choice import OPTION_CUSTOM, OPTION_LEGACY, OPTION_PORTABLE
from dialogs import data_location_dialog as dld
from utils import app_mode
from utils import data_location as dl


@pytest.fixture(autouse=True)
def _search_stops_at_the_temp_folder(tmp_path, monkeypatch):
    """A temp folder can sit inside a git work tree on this machine (the C: root is one): keep the search inside it."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


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
    copied = json.loads((app_folder / "data" / "settings.json").read_text(encoding="utf-8"))
    assert copied == {"ui_language": "en"}     # the old settings, plus the language shown in the dialog
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


@pytest.fixture
def english_after():
    """Language tests switch the global catalog: put English back afterwards."""
    yield
    i18n.set_language("en")


def _choose_language(dialog, code):
    dialog._language_combo.setCurrentIndex(dialog._language_combo.findData(code))


def test_first_start_offers_every_interface_language(qtbot, app_folder, english_after):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    codes = [dialog._language_combo.itemData(i) for i in range(dialog._language_combo.count())]
    assert codes == i18n.available_languages()
    assert codes[:1] == ["en"] and len(codes) > 1      # English first, then every catalog with translations


def test_switching_the_language_translates_the_dialog_and_keeps_the_choices(qtbot, app_folder, tmp_path,
                                                                          english_after):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    chosen = tmp_path / "mine"
    _pick(dialog, OPTION_CUSTOM)
    dialog._folder_edit.setText(str(chosen))
    _choose_language(dialog, "uk")
    assert dialog.windowTitle() == i18n.tr("Where Picoripi keeps your data") != "Where Picoripi keeps your data"
    assert dialog._ok_button.text() == i18n.tr("Use this folder")
    assert dialog._selected_option() == OPTION_CUSTOM
    assert dialog._current_target() == chosen


def test_confirming_saves_the_chosen_language_into_the_data_folder(qtbot, app_folder, english_after):
    dialog = dld.DataLocationDialog(app_folder, first_start=True)
    qtbot.addWidget(dialog)
    _choose_language(dialog, "uk")
    dialog._confirm()
    saved = json.loads((app_folder / "data" / "settings.json").read_text(encoding="utf-8"))
    assert saved == {"ui_language": "uk"}


def test_the_saved_language_keeps_the_other_settings(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "dark", "ui_language": "en"}), encoding="utf-8")
    dld.save_ui_language(tmp_path, "uk")
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {"theme": "dark", "ui_language": "uk"}


def test_copied_settings_keep_their_language_unless_the_user_picked_one(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"ui_language": "uk"}), encoding="utf-8")
    dld.save_ui_language(tmp_path, "en", keep_existing=True)
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {"ui_language": "uk"}


def test_an_unreadable_settings_file_is_left_alone(tmp_path):
    (tmp_path / "settings.json").write_text("{broken", encoding="utf-8")
    dld.save_ui_language(tmp_path, "uk")
    assert (tmp_path / "settings.json").read_text(encoding="utf-8") == "{broken"


def test_the_settings_dialog_has_no_language_list(qtbot, app_folder, tmp_path):
    current = tmp_path / "current"
    current.mkdir()
    dialog = dld.DataLocationDialog(app_folder, current=current, first_start=False)
    qtbot.addWidget(dialog)
    assert dialog._language_combo is None


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


def test_first_start_keeps_the_application_alive_for_the_chooser():
    """Regression: the QApplication made for the chooser was dropped at once, so the dialog failed with
    'Must construct a QApplication before a QWidget' on a start with no chosen folder (seen on macOS)."""
    probe = Path(__file__).with_name("first_start_probe.py")
    done = subprocess.run([sys.executable, "-I", str(probe)], capture_output=True, text=True, timeout=120,
                          stdin=subprocess.DEVNULL, cwd=str(probe.parent))
    assert done.returncode == 0, done.stderr
    assert "RESULT True True" in done.stdout
