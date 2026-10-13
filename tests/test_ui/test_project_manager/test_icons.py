"""Project icons: the wizard's icon field, the copy of a chosen picture into a new project, and the plugin hook example.

Real picture files in temp folders; the only replaced name is the message box, so no dialog waits for a click.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.project_library.icons import USER_ICON_MAX
from core.project_library.plugin_facts import default_load_rules
from core.project_library.scan import ICON_FILE_NAME
from handlers.project_action.library_mixin import LibraryMixin
from ui.project_manager import wizard as wizard_module
from ui.project_manager.wizard import ProjectWizard


def _picture(path, width=640, height=480):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.magenta)
    assert image.save(str(path), "PNG")
    return path


def test_wizard_previews_a_picture_and_refuses_a_file_that_is_not_one(qtbot, tmp_path, monkeypatch):
    picture = _picture(tmp_path / "cover.png")
    text = tmp_path / "notes.txt"
    text.write_text("not a picture", encoding="utf-8")
    warnings = []
    monkeypatch.setattr(wizard_module.QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args[2]))
    wizard = ProjectWizard(None, default_load_rules, lambda info: None)
    qtbot.addWidget(wizard)

    wizard.set_icon(str(picture))
    qtbot.waitUntil(lambda: not wizard._icon_preview.pixmap().isNull(), timeout=10000)
    assert wizard._icon_path == str(picture)

    wizard.set_icon(str(text))
    qtbot.waitUntil(lambda: wizard._icon_path == "", timeout=10000)
    assert warnings  # the user is told why the picture is not used
    assert wizard._icon_preview.pixmap() is None or wizard._icon_preview.pixmap().isNull()


def test_wizard_hands_the_chosen_icon_to_the_new_project_info(qtbot, tmp_path):
    picture = _picture(tmp_path / "cover.png")
    created = []
    wizard = ProjectWizard(None, default_load_rules, created.append)
    qtbot.addWidget(wizard)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "project"))
    wizard._icon_path = str(picture)

    wizard._on_unpacked(None, {"base": str(picture)}, {str(picture): {"role": "base", "platform": ""}})

    assert created[0]["icon_source"] == str(picture)


def test_copy_project_icon_writes_a_scaled_png_beside_the_project_file(qtbot, tmp_path):
    picture = _picture(tmp_path / "big.png", width=1200, height=900)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    handler = LibraryMixin()

    handler.copy_project_icon(str(project_dir), str(picture))

    target = project_dir / ICON_FILE_NAME
    qtbot.waitUntil(target.exists, timeout=10000)
    stored = QImage(str(target))
    assert not stored.isNull()
    assert max(stored.width(), stored.height()) == USER_ICON_MAX
    assert not any(p.name.endswith(".tmp") for p in project_dir.iterdir())


def test_the_plain_text_example_returns_a_banner_beside_the_project(tmp_path):
    rules = default_load_rules("plain_text")
    assert rules.project_icon(str(tmp_path)) is None

    (tmp_path / "banner.png").write_bytes(b"\x89PNG-example")

    assert rules.project_icon(str(tmp_path)) == b"\x89PNG-example"
    assert Path(tmp_path / "banner.png").exists()
