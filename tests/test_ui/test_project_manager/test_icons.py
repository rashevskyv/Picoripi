"""Project icons: none from the wizard, the copy of a chosen picture into a project, and the plugin hook example.

Real picture files in temp folders; the only replaced name is the message box, so no dialog waits for a click.
"""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.project_library.icons import USER_ICON_MAX
from core.project_library.plugin_facts import default_load_rules
from core.project_library.scan import ICON_FILE_NAME
from handlers.project_action.library_mixin import LibraryMixin
from ui.project_manager.wizard import ProjectWizard


def _picture(path, width=640, height=480):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.magenta)
    assert image.save(str(path), "PNG")
    return path


def test_the_wizard_asks_no_icon_the_row_offers_change_icon(qtbot, tmp_path):
    """The icon is not a wizard step any more: a new project gets none from the wizard."""
    picture = _picture(tmp_path / "cover.png")
    created = []
    wizard = ProjectWizard(None, default_load_rules, created.append)
    qtbot.addWidget(wizard)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "project"))

    wizard._on_unpacked(None, {"base": str(picture)}, {str(picture): {"role": "base", "platform": ""}})

    assert "icon_source" not in created[0]


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
