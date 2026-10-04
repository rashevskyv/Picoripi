"""The Textures window end to end: list a project's textures in a real worker thread, export, import,
revert, the status file, opening a file directly, and closing while a job runs."""
import json
import struct
import threading
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from PyQt6 import QtWidgets

from core.texture_formats import pixels, sources
from ui import texture_window as texture_window_module
from ui.texture_window import TextureWindow
from utils import app_mode


def _bti(image):
    """An RGB5A3 BTI of ``image`` (size a multiple of 4)."""
    head = struct.pack(">BBHHBBBBHI", 5, 0, image.width, image.height, 0, 0, 0, 0, 0, 0) + bytes(8)
    head += bytes([1, 0, 0, 0]) + struct.pack(">I", 0x20)
    return head + pixels.codec("gx:RGB5A3").encode(image)


def _card(colour):
    image = Image.new("RGBA", (32, 8), colour)
    ImageDraw.Draw(image).rectangle((2, 2, 10, 5), fill=(255, 255, 255, 255))
    return image


@pytest.fixture
def project(tmp_path):
    source, translation, project_dir = tmp_path / "source", tmp_path / "translation", tmp_path / "project"
    for folder in (source, translation, project_dir):
        folder.mkdir()
    (source / "a_title.bti").write_bytes(_bti(_card((200, 0, 0, 255))))
    (source / "b_menu.bti").write_bytes(_bti(_card((0, 0, 200, 255))))
    rules = SimpleNamespace(get_texture_sources=lambda: [{"label": "Card", "format": "bti", "path": "*.bti"}])
    manager = SimpleNamespace(project=SimpleNamespace(metadata={"source_path": str(source),
                                                                 "translation_path": str(translation)}),
                              project_dir=str(project_dir))
    return SimpleNamespace(mw=SimpleNamespace(current_game_rules=rules, project_manager=manager),
                           source=source, translation=translation, project_dir=project_dir, tmp=tmp_path)


def _settle(qtbot, window):
    qtbot.waitUntil(lambda: not window.busy(), timeout=20000)


def test_list_export_import_and_revert_in_a_worker_thread(qtbot, project, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    window = TextureWindow(project.mw)
    qtbot.addWidget(window)
    window.load_project()
    _settle(qtbot, window)
    assert window.tree.topLevelItemCount() == 2
    assert set(window.images) == {"a_title.bti", "b_menu.bti"}
    assert window.translated_view._image is not None and not window.tree.topLevelItem(0).icon(0).isNull()

    folder = project.tmp / "png"
    window.export_to(list(window.sources), str(folder))
    _settle(qtbot, window)
    assert sorted(p.name for p in folder.iterdir()) == ["a_title.bti.png", "b_menu.bti.png"]

    redrawn = Image.open(folder / "a_title.bti.png").convert("RGBA")
    ImageDraw.Draw(redrawn).rectangle((0, 0, 31, 7), fill=(0, 200, 0, 255))
    redrawn.resize((64, 16)).save(folder / "a_title.bti.png")      # another size: resized on import
    window.import_from(str(folder))
    _settle(qtbot, window)
    title = next(s for s in window.sources if s.key == "a_title.bti")
    assert title.read_current().image.getpixel((5, 5))[1] > 150
    assert (project.translation / "a_title.bti").is_file() and not (project.translation / "b_menu.bti").exists()
    assert window.status == {"a_title.bti": "redrawn"}
    assert json.loads((project.project_dir / "textures" / "status.json").read_text(encoding="utf-8")) == \
        {"a_title.bti": "redrawn"}
    assert "1" in window.statusBar().currentMessage()

    monkeypatch.setattr(texture_window_module.QtWidgets.QMessageBox, "question",
                        lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)
    window.tree.clearSelection()
    window._item("a_title.bti").setSelected(True)
    window.revert_selected()
    _settle(qtbot, window)
    assert (project.translation / "a_title.bti").read_bytes() == (project.source / "a_title.bti").read_bytes()
    assert window.status.get("a_title.bti") == ""
    assert sources.load_status(str(project.project_dir)) == {}


def test_the_status_combo_marks_the_selected_textures(qtbot, project):
    window = TextureWindow(project.mw)
    qtbot.addWidget(window)
    window.load_project()
    window.tree.selectAll()
    window.status_combo.setCurrentIndex(window.status_combo.findData("checked"))
    window._status_chosen(window.status_combo.currentIndex())
    assert sources.load_status(str(project.project_dir)) == {"a_title.bti": "checked", "b_menu.bti": "checked"}
    assert window._item("b_menu.bti").text(4) == "Checked in game"


def test_import_one_png_asks_before_resizing(qtbot, project, monkeypatch):
    window = TextureWindow(project.mw)
    qtbot.addWidget(window)
    window.load_project()
    window.tree.setCurrentItem(window._item("b_menu.bti"))
    png = project.tmp / "new.png"
    Image.new("RGBA", (16, 4), (0, 255, 0, 255)).save(png)
    monkeypatch.setattr(texture_window_module.QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(png), ""))
    asked = []
    monkeypatch.setattr(texture_window_module.QtWidgets.QMessageBox, "question",
                        lambda *a, **k: asked.append(a) or QtWidgets.QMessageBox.StandardButton.No)
    window.import_png()
    assert asked and not (project.translation / "b_menu.bti").exists()
    monkeypatch.setattr(texture_window_module.QtWidgets.QMessageBox, "question",
                        lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)
    window.import_png()
    menu = next(s for s in window.sources if s.key == "b_menu.bti")
    assert menu.read_current().image.getpixel((20, 4))[:3] == (0, 255, 0)


def test_a_file_opened_directly_is_listed_and_edited_in_place(qtbot, tmp_path):
    path = tmp_path / "loose.bti"
    path.write_bytes(_bti(_card((10, 20, 30, 255))))
    window = TextureWindow(None)
    qtbot.addWidget(window)
    window.load_project()
    assert "No project" in window.statusBar().currentMessage()
    window.open_path(str(path))
    assert [s.key for s in window.sources] == ["loose.bti"]
    window.write_images([(window.sources[0], Image.new("RGBA", (32, 8), (255, 255, 255, 255)))], "redrawn")
    assert sources.open_file(str(path))[0].read_current().image.getpixel((0, 0)) == (255, 255, 255, 255)
    assert window.status == {"loose.bti": "redrawn"}


def test_a_failing_file_is_reported_not_raised(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "broken.bti"
    path.write_bytes(b"\x05" + bytes(10))
    warned = []
    monkeypatch.setattr(texture_window_module.QtWidgets.QMessageBox, "warning", lambda *a, **k: warned.append(a))
    window = TextureWindow(None)
    qtbot.addWidget(window)
    window.open_path(str(path))
    assert warned and "Could not load" in window.statusBar().currentMessage()


def test_closing_cancels_a_running_job_and_waits_for_it(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    window = TextureWindow(None)
    qtbot.addWidget(window)
    started, stopped = threading.Event(), threading.Event()

    def slow(progress, cancelled):
        started.set()
        while not cancelled():
            threading.Event().wait(0.01)
        stopped.set()
        return None

    window.run_job(slow)
    window.run_job(lambda progress, cancelled: pytest.fail("a queued job must not start after close"))
    assert started.wait(5)
    job = window._job
    window.close()
    assert stopped.is_set() and job.isFinished() and not window.busy()


def test_tools_menu_action_opens_one_window(qtbot, project):
    from ui.main_window.actions.tools_mixin import MainWindowToolsActionsMixin
    host = QtWidgets.QWidget()
    qtbot.addWidget(host)
    host.current_game_rules = project.mw.current_game_rules
    host.project_manager = project.mw.project_manager
    actions = SimpleNamespace(mw=host)
    first = MainWindowToolsActionsMixin.open_texture_window(actions)
    assert first.tree.topLevelItemCount() == 2
    assert MainWindowToolsActionsMixin.open_texture_window(actions) is first
    first.close()
