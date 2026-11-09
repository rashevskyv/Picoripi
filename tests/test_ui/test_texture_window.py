"""The Textures window end to end: list a project's textures in a real worker thread, export, import,
revert, the status file, opening a file directly, closing while a job runs, and Image AI (a fake provider:
the canvas rule, the key, Accept writing like an imported PNG, Cancel dropping a late answer, an error)."""
import io
import json
import struct
import sys
import threading
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from PyQt6 import QtCore, QtWidgets

from core import texture_formats
from core.texture_formats import image_ai, pixels, sources
from ui import texture_window as texture_window_module
from ui.texture_window import ImageAISetupDialog, TextureWindow
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
    assert window.statusBar().currentMessage() == "Saved 1 textures (1 resized)"

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


def test_a_missing_numpy_is_named_with_the_install_command(qtbot, tmp_path, monkeypatch):
    """Without numpy the window names the package and the command that installs it, not a bare ImportError."""
    path = tmp_path / "picture.bti"
    path.write_bytes(_bti(_card((10, 20, 30, 255))))
    monkeypatch.setitem(sys.modules, "numpy", None)  # deslop: ignore[module-mocking] a None entry makes the import fail like a missing package; no product module is patched
    monkeypatch.delitem(sys.modules, "core.texture_formats.gim", raising=False)
    monkeypatch.delattr(texture_formats, "gim", raising=False)
    warned = []
    monkeypatch.setattr(texture_window_module.QtWidgets.QMessageBox, "warning", lambda *a, **k: warned.append(a))
    window = TextureWindow(None)
    qtbot.addWidget(window)
    window.open_path(str(path))
    assert warned, "the window did not show the error"
    text = warned[0][2]
    assert "numpy" in text and "python -m pip install -r requirements.txt" in text
    assert "No module named" not in text


def test_decoded_pairs_and_the_list_are_cached_and_follow_file_changes(project, monkeypatch):
    from core.texture_formats import cache
    cache_dir = str(project.tmp / "cache")
    metadata = {"source_path": str(project.source), "translation_path": str(project.translation)}
    descriptors = [{"label": "Card", "format": "bti", "path": "*.bti"}]
    found = cache.resolve(descriptors, metadata, cache_dir)
    assert len(found) == 2 and (project.tmp / "cache" / "list.pickle").is_file()
    monkeypatch.setattr(sources, "resolve", lambda *a: pytest.fail("the list was read again"))
    assert [s.key for s in cache.resolve(descriptors, metadata, cache_dir)] == [s.key for s in found]

    monkeypatch.setattr(cache, "POOL_MIN", 1)       # two textures are enough to use the process pool
    first = {s.key: pair for s, pair in cache.read_pairs(found, cache_dir, lambda: False)}
    assert set(first) == {"a_title.bti", "b_menu.bti"} and all(p[2] == "" for p in first.values())
    assert len(list((project.tmp / "cache" / "decoded").iterdir())) == 4
    monkeypatch.setattr(cache, "_decode", lambda s: pytest.fail("a cached texture was decoded again"))
    again = cache.read_pair(found[0], cache_dir)
    assert list(again[0].getdata()) == list(first[found[0].key][0].getdata())

    (project.source / "a_title.bti").write_bytes(_bti(_card((0, 200, 0, 255))))      # the game file changed
    assert cache._pair_base(found[0], cache_dir) != cache._pair_base(found[1], cache_dir)
    with pytest.raises(pytest.fail.Exception):
        cache.read_pair(found[0], cache_dir)


def _green_answer(config, key, png, prompt, canvas, cancelled=None):
    """A fake image model: the canvas it was sent, painted green where the texture is not transparent."""
    with Image.open(io.BytesIO(png)) as sent:
        assert sent.size == canvas
        answer = Image.new("RGBA", canvas, (0, 200, 0, 255))
        answer.putalpha(sent.getchannel("A"))
    buffer = io.BytesIO()
    answer.save(buffer, "PNG")
    return buffer.getvalue()


def test_fit_puts_a_wide_texture_on_the_wide_canvas_and_cuts_it_back():
    texture = Image.new("RGBA", (64, 8), (255, 0, 0, 255))
    sheet, box = image_ai.to_canvas(texture, "fit")
    assert sheet.size == (1536, 1024) and box == (0, 416, 1536, 608)
    assert sheet.getpixel((10, 10))[3] == 0 and sheet.getpixel((10, 500)) == (255, 0, 0, 255)
    back = image_ai.from_canvas(sheet.resize((768, 512)), sheet.size, box, texture.size)
    assert back.size == (64, 8) and back.getpixel((30, 4))[0] > 240
    assert image_ai.to_canvas(Image.new("RGBA", (16, 64)), "stretch")[1] == (0, 0, 1024, 1536)


def test_the_key_comes_from_ai_translation_or_the_variable(monkeypatch):
    monkeypatch.setenv("PICORIPI_TEST_IMAGE_KEY", "from-env")
    config = image_ai.settings({"api_key_env": "PICORIPI_TEST_IMAGE_KEY"})
    translation = {"providers": {"openai": {"api_key": "from-translation"}}}
    assert image_ai.api_key(config, translation) == "from-translation"
    assert image_ai.api_key(config, {"providers": {"openai": {}}}) == "from-env"
    assert image_ai.api_key({**config, "use_translation_api_key": False}, translation) == "from-env"


def test_an_openai_call_without_a_key_names_the_variable():
    with pytest.raises(image_ai.ImageAIError, match="OPENAI_API_KEY"):
        image_ai.edit(Image.new("RGBA", (8, 8)), "x", image_ai.settings({}), "")


def _window(qtbot, project):
    project.mw.image_ai = {"model": "fake-model", "prompt": "Make it Ukrainian"}
    project.mw.translation_config = {"providers": {"openai": {"api_key": "k"}}}
    window = TextureWindow(project.mw)
    qtbot.addWidget(window)
    window.load_project()
    _settle(qtbot, window)
    window.tree.setCurrentItem(window._item("a_title.bti"))
    return window


def test_send_in_a_worker_thread_then_accept_writes_the_texture(qtbot, project, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    calls = []
    monkeypatch.setitem(image_ai.PROVIDERS, "openai",
                        lambda *args: calls.append((args[1], args[3])) or _green_answer(*args))
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    assert dialog.prompt_edit.toPlainText() == "Make it Ukrainian"
    dialog.send()
    assert not dialog.send_button.isEnabled()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    assert calls == [("k", "Make it Ukrainian")]
    assert dialog.result.size == (32, 8) and dialog.accept_button.isEnabled()
    dialog.accept()
    _settle(qtbot, window)
    title = next(s for s in window.sources if s.key == "a_title.bti")
    red, green, _blue, _alpha = title.read_current().image.getpixel((5, 5))
    assert green > 150 and red < 30
    assert window.status == {"a_title.bti": "redrawn"}


def test_cancel_drops_a_late_answer(qtbot, project, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    release = threading.Event()
    monkeypatch.setitem(image_ai.PROVIDERS, "openai", lambda *args: release.wait(10) and _green_answer(*args))
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.send()
    dialog.reject()
    release.set()
    _settle(qtbot, window)
    assert dialog.result is None and not (project.translation / "a_title.bti").exists()


def test_a_provider_error_is_shown_in_the_dialog(qtbot, project, monkeypatch):
    def fail(*args):
        raise image_ai.ImageAIError("HTTP 400: bad model")

    monkeypatch.setitem(image_ai.PROVIDERS, "openai", fail)
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.send()
    box = dialog.findChild(QtWidgets.QMessageBox)
    assert box is not None and box.text() == "HTTP 400: bad model"
    assert "HTTP 400" not in dialog.info.text()          # the error is shown once, in the message box
    assert not dialog.accept_button.isEnabled() and dialog.send_button.isEnabled()


def test_settings_changes_the_agent_command_without_sending(qtbot, project, monkeypatch):
    calls = []
    monkeypatch.setitem(image_ai.PROVIDERS, "command", lambda *args: calls.append(args) or b"")
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.setup_button.click()
    setup = dialog.findChild(ImageAISetupDialog)
    assert setup is not None and not setup.problem.isVisible()
    setup.provider.setCurrentIndex(setup.provider.findData("command"))
    setup.agent.set_command(_copy_agent())
    setup.accept()
    assert dialog.config["command"] == _copy_agent() and project.mw.image_ai["command"] == _copy_agent()
    assert _copy_agent() in dialog.info.text() and not calls


def test_the_pictures_and_the_buttons_offer_image_ai(qtbot, project):
    window = _window(qtbot, project)
    buttons = {button.text() for button in window.findChildren(QtWidgets.QPushButton)}
    assert "Ima&ge AI..." in buttons
    for view in (window.original_view, window.translated_view):
        assert view.contextMenuPolicy() == QtCore.Qt.ContextMenuPolicy.CustomContextMenu


def _copy_agent(script: str = "shutil.copy(sys.argv[1], sys.argv[2])") -> str:
    """A fake local agent: a Python one-liner run as the agent command."""
    return f'"{sys.executable}" -c "import shutil, sys; {script}" "{{input}}" "{{output}}"'


def test_missing_names_what_each_provider_lacks():
    assert image_ai.missing(image_ai.settings({}), "") == "No OpenAI API key."
    assert image_ai.missing(image_ai.settings({}), "k") == ""
    assert image_ai.missing(image_ai.settings({"provider": "command"}), "") == "No agent command."
    assert "not installed" in image_ai.missing(image_ai.settings({"provider": "command",
                                                                  "command": "no-such-agent-xyz -p"}), "")
    assert image_ai.missing(image_ai.settings({"provider": "command", "command": _copy_agent()}), "") == ""


def test_a_local_agent_edits_the_texture_at_its_own_size():
    texture = Image.new("RGBA", (24, 8), (255, 0, 0, 255))
    config = image_ai.settings({"provider": "command", "command": _copy_agent(), "timeout": 60})
    answer = image_ai.edit(texture, "Ukrainian", config, "")
    assert answer.size == (24, 8) and answer.getpixel((3, 3)) == (255, 0, 0, 255)


def test_an_agent_that_writes_no_image_reports_its_output():
    config = image_ai.settings({"provider": "command", "command": _copy_agent("print('quota exceeded')"),
                                "timeout": 60})
    with pytest.raises(image_ai.ImageAIError, match="quota exceeded"):
        image_ai.edit(Image.new("RGBA", (8, 8)), "x", config, "")


def test_send_without_a_key_asks_for_it_then_sends(qtbot, project, monkeypatch):
    calls = []
    monkeypatch.setitem(image_ai.PROVIDERS, "openai",
                        lambda *args: calls.append(args[1]) or _green_answer(*args))
    window = _window(qtbot, project)
    project.mw.translation_config = {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.send()
    setup = dialog.findChild(ImageAISetupDialog)
    assert setup is not None and "No OpenAI API key" in setup.problem.text() and not calls
    setup.key.setText("new-key")
    setup.accept()
    _settle(qtbot, window)
    assert project.mw.translation_config["providers"]["openai"]["api_key"] == "new-key"
    assert calls == ["new-key"] and dialog.result is not None


def test_a_saved_retired_preset_becomes_the_current_one():
    """The first Codex preset passed --full-auto, which the current Codex CLI rejects (exit code 2)."""
    for old, agent in image_ai.RETIRED_PRESETS.items():
        assert image_ai.settings({"provider": "command", "command": old})["command"] == image_ai.AGENT_PRESETS[agent]
    assert image_ai.settings({"command": "my-agent --x"})["command"] == "my-agent --x"


def test_an_app_cli_outside_path_is_found_and_run(tmp_path, monkeypatch):
    """The Codex desktop app keeps codex.exe in a versioned folder, not on PATH."""
    folder = tmp_path / "OpenAI" / "Codex" / "bin" / "f71a721e"
    folder.mkdir(parents=True)
    agent = folder / "fakeagent.cmd"
    agent.write_text(f'@"{sys.executable}" -c "import shutil, sys; shutil.copy(sys.argv[1], sys.argv[2])" %1 %2\n')
    monkeypatch.setitem(image_ai.AGENT_LOCATIONS, "fakeagent", (str(tmp_path / "OpenAI/Codex/bin/*/fakeagent.cmd"),))
    config = image_ai.settings({"provider": "command", "command": 'fakeagent "{input}" "{output}"', "timeout": 60})

    assert image_ai.find_program("fakeagent") == str(agent)
    assert image_ai.missing(config, "") == ""
    answer = image_ai.edit(Image.new("RGBA", (6, 4), (0, 0, 255, 255)), "x", config, "")
    assert answer.size == (6, 4) and answer.getpixel((1, 1)) == (0, 0, 255, 255)


def test_setup_ok_stays_open_while_the_agent_is_missing(qtbot, project, monkeypatch):
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    setup = ImageAISetupDialog(dialog, project.mw, image_ai.settings({}), "No OpenAI API key.")
    setup.provider.setCurrentIndex(setup.provider.findData("command"))
    setup.agent.set_command("no-such-agent-xyz -p")
    setup.accept()
    assert setup.result() != QtWidgets.QDialog.DialogCode.Accepted
    assert "no-such-agent-xyz is not installed" in setup.problem.text()


def test_a_running_request_shows_a_busy_bar_and_the_seconds(qtbot, project, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    release = threading.Event()
    monkeypatch.setitem(image_ai.PROVIDERS, "openai", lambda *args: release.wait(30) and _green_answer(*args))
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.send()
    assert dialog.busy.isVisible() and "0 s" in dialog.info.text()
    release.set()
    _settle(qtbot, window)
    assert not dialog.busy.isVisible() and dialog.result is not None


def test_a_provider_error_also_opens_a_message_box(qtbot, project, monkeypatch):
    def fail(*args):
        raise image_ai.ImageAIError("HTTP 401: bad key")

    monkeypatch.setitem(image_ai.PROVIDERS, "openai", fail)
    window = _window(qtbot, project)
    dialog = window.image_ai_dialog()
    qtbot.addWidget(dialog)
    dialog.send()
    box = dialog.findChild(QtWidgets.QMessageBox)
    assert box is not None and "HTTP 401: bad key" in box.text()
