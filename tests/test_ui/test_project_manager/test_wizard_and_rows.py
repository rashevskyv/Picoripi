"""The new-project wizard, the unpack job, and the expanded row of the Project Manager (targets, flags, emulator)."""
import json
import os

from PyQt6.QtWidgets import QCheckBox, QToolButton

from core.project_library import index, registry
from plugins.base_game_rules import BaseGameRules
from ui.project_manager import window
from ui.project_manager.emulator_dialog import EmulatorDialog
from ui.project_manager.tasks import UnpackJob
from ui.project_manager.window import ProjectManagerDialog
from ui.project_manager.wizard import ProjectWizard


class FakeGame(BaseGameRules):
    """An explicit fake game: two roles, a platform, one build target that writes one file."""

    def get_source_roles(self):
        return [{"id": "base", "label": "Base game"}, {"id": "update", "label": "Update"}]

    def get_platforms(self):
        return [{"id": "3ds", "label": "Nintendo 3DS"}]

    def get_build_targets(self):
        return [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]

    def identify_source(self, path):
        return {"role": "update", "platform": "3ds"} if path.endswith("update.bin") else None

    def unpack_key_consoles(self):
        return ["3ds"]   # the game's unpack reads the 3DS key file, so the wizard asks for it

    def build_target(self, target_id, source_dir, translation_dir, output_dir, progress, is_cancelled):
        with open(os.path.join(output_dir, "patch.bin"), "w", encoding="utf-8") as handle:
            handle.write("built")
        return os.path.join(output_dir, "patch.bin")


def _loader(name):
    return FakeGame()


def _project(root, name, project_id):
    folder = root / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": project_id, "name": name, "plugin_name": "fake", "blocks": []}),
                            encoding="utf-8")
    return str(project_file)


def _wait_for_plugins(qtbot, wizard):
    qtbot.waitUntil(lambda: wizard._game.count() > 0 or wizard._jobs == [], timeout=10000)
    wizard._game.addItem("Fake game", "fake")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)


def test_wizard_reads_roles_and_creates_the_project_from_the_originals(qtbot, tmp_path):
    base = tmp_path / "base.bin"
    update = tmp_path / "update.bin"
    base.write_bytes(b"base")
    update.write_bytes(b"update")
    created = []
    wizard = ProjectWizard(None, _loader, created.append)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)

    wizard.add_paths([str(base), str(update)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 2", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard._create_clicked()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)

    info = created[0]
    assert info["source_path"] == str(base)
    assert info["is_directory_mode"] is False
    assert info["translation_path"] == str(tmp_path / "Aria" / "translation" / "base.bin")
    assert info["metadata"]["source_roles"] == {"base": str(base), "update": str(update)}
    assert info["platform"] == "3ds"
    assert info["plugin"] == "fake"
    assert (tmp_path / "Aria" / "translation").is_dir()
    assert not [p for p in (tmp_path / "Aria").iterdir() if p.name.startswith(".unpack")]


def test_wizard_refuses_a_folder_that_already_holds_a_project(qtbot, tmp_path):
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    (tmp_path / "Aria").mkdir()
    (tmp_path / "Aria" / "project.uiproj").write_text("{}", encoding="utf-8")
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))

    assert wizard._problem() == "This folder already holds a project."


class UnpackingGame(FakeGame):
    """The fake game with an unpack: the chosen file becomes a folder with one file in it."""

    def unpack_sources(self, sources, target_dir, progress, is_cancelled):
        with open(os.path.join(target_dir, "data.txt"), "w", encoding="utf-8") as handle:
            handle.write("data")
        return target_dir


def test_wizard_uses_an_existing_translation_folder_for_a_folder_project(qtbot, tmp_path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"game")
    existing = tmp_path / "my_translation"
    existing.mkdir()
    created = []
    wizard = ProjectWizard(None, lambda name: UnpackingGame(), created.append)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard.add_paths([str(source)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 1", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard._use_existing.setChecked(True)
    wizard._existing_folder.setText(str(existing))
    assert wizard._problem() == ""

    wizard._create_clicked()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)

    assert created[0]["translation_path"] == str(existing)
    assert created[0]["auto_create_translations"] is False
    assert created[0]["is_directory_mode"] is True


def test_wizard_refuses_an_existing_translation_folder_for_a_one_file_project(qtbot, tmp_path):
    source = tmp_path / "base.bin"
    source.write_bytes(b"base")
    existing = tmp_path / "my_translation"
    existing.mkdir()
    created = []
    wizard = ProjectWizard(None, _loader, created.append)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard.add_paths([str(source)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 1", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard._use_existing.setChecked(True)
    wizard._existing_folder.setText(str(existing))

    wizard._create_clicked()
    qtbot.waitUntil(lambda: "cannot use an existing translation folder" in wizard._progress_text.text(), timeout=10000)

    assert created == []
    assert not (tmp_path / "Aria" / "translation").exists()   # a refused create leaves no empty translation folder


def test_wizard_asks_for_an_existing_translation_folder_that_exists(qtbot, tmp_path):
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard._use_existing.setChecked(True)

    assert wizard._problem() == "Choose the existing translation folder."
    wizard._existing_folder.setText(str(tmp_path / "missing"))
    assert wizard._problem() == "The translation folder does not exist."


def test_wizard_needs_a_role_for_every_file_and_no_two_files_share_one(qtbot, tmp_path):
    first = tmp_path / "one.bin"
    second = tmp_path / "two.bin"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard.add_paths([str(first), str(second)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 2", timeout=10000)
    # Both files start as the first role (base): the second one moves to the update role.
    wizard._files_tree.itemWidget(wizard._files_tree.topLevelItem(1), 1).setCurrentIndex(1)
    assert wizard._problem() == ""

    wizard._files_tree.itemWidget(wizard._files_tree.topLevelItem(0), 1).setCurrentIndex(1)

    assert wizard._problem() == "Two files have the role Update. Only DLC can repeat: give each other file its own role."


def test_unpack_job_that_is_cancelled_leaves_only_the_project_folder(qtbot, tmp_path):
    project_dir = tmp_path / "Aria"
    job = UnpackJob("fake", {"base": "x"}, str(project_dir), _loader)
    cancelled, done = [], []
    job.cancelled.connect(lambda: cancelled.append(True))
    job.done.connect(done.append)
    job.isInterruptionRequested = lambda: True  # the user cancelled before the worker started

    job.run()

    assert cancelled == [True] and done == []
    assert not [p for p in project_dir.iterdir() if p.name.startswith(".unpack")]


def test_wizard_asks_for_a_key_file_only_when_a_chosen_file_needs_one_and_none_is_stored(qtbot, tmp_path, monkeypatch):
    from core.project_library import console_keys, key_source
    from test_core.test_n3ds_image import build_cci, build_ncch
    from ui.project_manager import wizard as wizard_module
    from utils import constants

    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "data")
    key_source.set_config(enabled=False)   # no source offer here: the file dialog is the only choice
    key_file = tmp_path / "keys.txt"
    key_file.write_bytes(b"placeholder")
    locked = tmp_path / "locked.cci"
    locked.write_bytes(build_cci(build_ncch(encrypted=True)))
    asked = []

    class FakeDialog:
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            asked.append(True)
            return str(key_file), ""

    monkeypatch.setattr(wizard_module, "QFileDialog", FakeDialog)
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard.add_paths([str(locked)])
    qtbot.waitUntil(lambda: (wizard._key_status.get(str(locked)) or {}).get("key") == "3ds", timeout=10000)

    assert wizard._ask_key_files(wizard._file_choices()) == {"3ds": str(key_file)}
    assert asked == [True]
    console_keys.set_path("3ds", str(key_file))
    wizard._reread_files()
    qtbot.waitUntil(lambda: (wizard._key_status.get(str(locked)) or {}).get("key_ready") is True, timeout=10000)
    assert wizard._ask_key_files(wizard._file_choices()) == {}
    assert asked == [True]


def test_cancelling_the_key_dialog_stops_create_with_a_message_and_no_unpack(qtbot, tmp_path, monkeypatch):
    from core.i18n import tr
    from core.project_library import key_source
    from test_core.test_n3ds_image import build_cci, build_ncch
    from ui.project_manager import wizard as wizard_module
    from utils import constants

    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "data")
    key_source.set_config(enabled=False)   # no source offer here: the file dialog is the only choice
    locked = tmp_path / "locked.cci"
    locked.write_bytes(build_cci(build_ncch(encrypted=True)))
    constructed = []

    class CancelledDialog:
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return "", ""

    class SpyJob:
        def __init__(self, *args, **_kwargs):
            constructed.append(args)

    monkeypatch.setattr(wizard_module, "QFileDialog", CancelledDialog)
    monkeypatch.setattr(wizard_module, "UnpackJob", SpyJob)
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard.add_paths([str(locked)])
    qtbot.waitUntil(lambda: (wizard._key_status.get(str(locked)) or {}).get("key") == "3ds", timeout=10000)
    monkeypatch.setattr(wizard, "_problem", lambda: "")   # the name, folder and roles are not what this test checks

    wizard._create_clicked()

    assert wizard._progress_text.text() == tr("No key file was chosen. Nothing was created.")
    assert constructed == []


def test_expanded_row_offers_targets_and_saves_flags_for_a_project_that_is_not_open(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counts": {"lines": 3, "needs_translation": 3, "translated": 1},
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}],
        "groups": {"Menu": {"blocks": 1, "lines": 3}}, "skipped": 0}})
    saved_flags, saved_settings = [], []
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: saved_flags.append((path, updates)),
                                  lambda name, value: saved_settings.append((name, value)), _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    item = dialog._items[key]
    item.setExpanded(True)
    detail = dialog._tree.itemWidget(item.child(0), 0)
    buttons = {b.text(): b for b in detail.findChildren(QToolButton)}
    checks = {c.text(): c for c in detail.findChildren(QCheckBox)}

    assert buttons["Build mod"].isEnabled()
    assert buttons["Export mod"].isEnabled()
    assert not buttons["Run in emulator"].isEnabled()
    checks["Built"].setChecked(True)
    assert saved_flags == [(project, {"built": True})]


def test_run_in_emulator_needs_a_command_and_starts_it_detached(qtbot, tmp_path, monkeypatch):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    started, directories = [], []

    class FakeProcess:
        @staticmethod
        def startDetached(program, arguments, working_dir=""):
            started.append([program, *arguments])
            directories.append(working_dir)
            return True, 42

    monkeypatch.setattr(window, "QProcess", FakeProcess)
    dialog._document["settings"] = {"emulator_command": '"emu" --load {path}'}

    dialog._on_action_done(key, "run", "/games/out dir/patch.bin")

    assert started == [["emu", "--load", "/games/out dir/patch.bin"]]
    assert dialog._action_text[key].startswith("Started the emulator")


def _run_action_menu(qtbot, tmp_path, settings, target_platforms):
    """The expanded row of one project with a target for ``target_platforms``, and the Run in emulator menu."""
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": target_platforms, "kind": "patch"}]}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)
    dialog._document["settings"] = settings
    item = dialog._items[key]
    item.setExpanded(True)
    detail = dialog._tree.itemWidget(item.child(0), 0)
    buttons = {b.text(): b for b in detail.findChildren(QToolButton)}
    return dialog, key, buttons["Run in emulator"].menu()


def test_run_is_on_only_for_a_target_whose_platform_has_a_command(qtbot, tmp_path):
    _dialog, _key, menu = _run_action_menu(qtbot, tmp_path / "a", {"emulator_command.3ds": "emu3 {path}"},
                                           ["switch"])
    assert not menu.actions()[0].isEnabled()

    _dialog, _key, menu = _run_action_menu(qtbot, tmp_path / "b", {"emulator_command.switch": "emus {path}"},
                                           ["switch"])
    assert menu.actions()[0].isEnabled()


def test_emulator_dialog_returns_only_the_platform_lines_that_changed(qtbot):
    settings = {"emulator_command": "shared {path}", "emulator_command.3ds": "emu3 {path}"}
    dialog = EmulatorDialog(None, ["3ds", "switch"], settings)
    qtbot.addWidget(dialog)

    assert dialog._fields["switch"].text() == "shared {path}"   # no own line yet: the shared command shows
    dialog._fields["switch"].setText("emus {path}")

    assert dialog.changes() == {"emulator_command.switch": "emus {path}"}


def test_a_project_with_no_platform_edits_the_shared_command(qtbot):
    dialog = EmulatorDialog(None, [""], {"emulator_command": "shared {path}"})
    qtbot.addWidget(dialog)
    dialog._fields[""].setText("shared2 {path}")

    assert dialog.changes() == {"emulator_command": "shared2 {path}"}


def test_run_starts_the_emulator_of_the_platform_the_build_is_for(qtbot, tmp_path, monkeypatch):
    dialog, key, _menu = _run_action_menu(
        qtbot, tmp_path, {"emulator_command.3ds": "emu3 {path}", "emulator_command.switch": "emus {path}"}, ["switch"])
    started, directories = [], []

    class FakeProcess:
        @staticmethod
        def startDetached(program, arguments, working_dir=""):
            started.append([program, *arguments])
            directories.append(working_dir)
            return True, 7

    monkeypatch.setattr(window, "QProcess", FakeProcess)
    dialog._action_platform[key] = "switch"

    dialog._on_action_done(key, "run", "/games/out/patch.nsp")

    assert started == [["emus", "/games/out/patch.nsp"]]


def test_build_runs_the_plugin_target_into_the_project_build_folder(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    dialog._start_action(project, "patch", "build")

    qtbot.waitUntil(lambda: dialog._action_text.get(key, "").startswith("Built:"), timeout=10000)
    built = dialog._action_text[key].split("Built: ", 1)[1]
    assert built.endswith(os.path.join("build", "patch", "patch.bin"))
    assert os.path.isfile(built)

def test_choosing_the_game_fills_the_project_name_until_the_user_types_one(qtbot):
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    assert wizard._name.text() == "Fake game"

    qtbot.keyClicks(wizard._name, " UA")
    wizard._game.addItem("Other game", "fake")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)

    assert wizard._name.text() == "Fake game UA"


def test_many_files_get_the_dlc_role_at_once_and_dlc_may_repeat(qtbot, tmp_path):
    paths = []
    for name in ("base.bin", "dlc1.bin", "dlc2.bin", "dlc3.bin"):
        (tmp_path / name).write_bytes(b"x")
        paths.append(str(tmp_path / name))
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard.add_paths(paths)
    qtbot.waitUntil(lambda: wizard._batch_role.count() > 0, timeout=10000)
    assert "Two files have the role Base game" in wizard._files_problems.text()

    for position in (1, 2, 3):
        wizard._files_tree.topLevelItem(position).setSelected(True)
    wizard._batch_role.setCurrentIndex(wizard._batch_role.findData("dlc"))
    wizard._apply_role.click()

    assert wizard._files_problems.text() == ""
    assert wizard._sources(wizard._file_choices()) == {
        "base": paths[0], "dlc": paths[1], "dlc_2": paths[2], "dlc_3": paths[3]}


def test_a_file_the_game_cannot_read_blocks_next_and_says_to_add_the_folder(qtbot, tmp_path, monkeypatch):
    from core.project_library import plugin_facts

    image = tmp_path / "game.nsz"
    image.write_bytes(b"x")
    folder = tmp_path / "unpacked"
    folder.mkdir()
    monkeypatch.setattr(plugin_facts.images, "identify", lambda path: (
        {"kind": "switch", "title_id": "0100C0000CEEA000", "title_kind": "base", "encrypted": True}
        if str(path).endswith(".nsz") else None))
    wizard = ProjectWizard(None, lambda name: BaseGameRules(), lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard._show_page(1)
    wizard.add_paths([str(image)])
    qtbot.waitUntil(lambda: "cannot read a Nintendo Switch file" in wizard._files_problems.text(), timeout=10000)
    assert not wizard._next.isEnabled()
    assert wizard._files_tree.topLevelItem(0).text(3) == "Cannot read: add its folder"

    wizard._files_tree.topLevelItem(0).setSelected(True)
    wizard._remove_selected()
    wizard.add_paths([str(folder)])
    qtbot.waitUntil(lambda: wizard._files_tree.topLevelItem(0).text(3) == "Folder", timeout=10000)
    assert wizard._next.isEnabled()


def test_a_missing_key_offers_its_button_and_the_chosen_key_clears_the_problem(qtbot, tmp_path, monkeypatch):
    from core.project_library import key_source
    from test_core.test_n3ds_image import build_cci, build_ncch
    from ui.project_manager import wizard as wizard_module
    from utils import constants

    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "data")
    key_source.set_config(enabled=False)   # the default source has its own tests: this one keeps the file button first
    key_file = tmp_path / "keys.txt"
    key_file.write_bytes(b"placeholder")
    locked = tmp_path / "locked.cci"
    locked.write_bytes(build_cci(build_ncch(encrypted=True)))

    class FakeDialog:
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return str(key_file), ""

    monkeypatch.setattr(wizard_module, "QFileDialog", FakeDialog)
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)
    wizard._show_page(1)
    wizard.add_paths([str(locked)])
    qtbot.waitUntil(lambda: "is encrypted" in wizard._files_problems.text(), timeout=10000)
    assert not wizard._next.isEnabled()
    button = wizard._key_bar.itemAt(0).widget()
    assert button.text() == "Add the key file for Nintendo 3DS..."

    button.click()

    assert wizard._files_problems.text() == ""
    assert wizard._next.isEnabled()
    assert wizard._ask_key_files(wizard._file_choices()) == {"3ds": str(key_file)}


def test_the_file_name_column_takes_the_free_width(qtbot):
    from PyQt6.QtWidgets import QHeaderView

    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    header = wizard._files_tree.header()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert {header.sectionResizeMode(c) for c in (1, 2, 3)} == {QHeaderView.ResizeMode.ResizeToContents}


def test_the_location_step_suggests_a_folder_from_the_project_name(qtbot):
    from pathlib import Path

    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    wizard._name.setText('Zelda: "Twilight" Princess')

    wizard._show_page(2)

    assert Path(wizard._folder.text()) == Path.home() / "Documents" / "Picoripi" / "Zelda Twilight Princess"
    wizard._folder.setText("my_projects/mine")
    wizard._show_page(1)
    wizard._show_page(2)
    assert wizard._folder.text() == "my_projects/mine"      # a folder the user typed is kept
