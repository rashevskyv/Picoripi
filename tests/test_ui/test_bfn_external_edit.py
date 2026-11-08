"""Font editor: external image editors (the editor list, the BMP round trip, the watcher and undo)."""
import io
import os

import numpy as np
import pytest
from PIL import Image
from PyQt6 import QtGui

from core.bfn_core import BfnCore
from core.i18n import tr
from tools.bfn_editor import external_edit
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow

EDITOR = {"name": "Fake", "path": "fake.exe", "args": "{file}"}


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(external_edit, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(external_edit, "YYCHR_CANDIDATES", [])
    return tmp_path


@pytest.fixture
def launched(monkeypatch):
    calls = []

    def fake_launch(editor, path):
        calls.append((editor["name"], path))
        return True

    monkeypatch.setattr(external_edit, "launch", fake_launch)
    return calls


def _bfn_bytes():
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    bfn.inf1 = [{"encoding": 0, "ascent": 20, "descent": 2, "width": 12, "leading": 2, "fallback_code": 63,
                 "unk1": 0}]
    bfn.gly1 = [{"texture_format": 0, "glyph_width": 12, "glyph_height": 12, "texture_width": 128,
                 "texture_height": 128, "cell_width": 12, "cell_height": 12, "page_data_size": 8192,
                 "glyph_horizontal_count": 10, "glyph_vertical_count": 10, "start_glyph": 0, "end_glyph": 100,
                 "sheets": [b"\x00" * 8192]}]
    bfn.map1 = [{"mapping_type": 2, "first_char": 32, "last_char": 34, "mapping_entry_count": 2, "entries": [0, 1]}]
    bfn.wid1 = [{"first_code_included": 32, "last_code_included": 34,
                 "packets": [{"kerning": 0, "width": 8}, {"kerning": 1, "width": 10}]}]
    return bfn.save()


@pytest.fixture
def window(qtbot, settings_dir, launched):
    editor = BfnEditorWindow()
    editor.load_bfn_bytes(_bfn_bytes(), "font.bfn")
    sheet = editor.sheet_images[0]
    sheet.setPixelColor(0, 0, QtGui.QColor(255, 255, 255, 128))
    sheet.setPixelColor(1, 0, QtGui.QColor(255, 255, 255, 255))
    yield editor
    editor.stop_external_edits()
    editor.undo_stack.clear()
    editor._set_dirty(False)        # closing a dirty window would ask to save
    editor.close()
    editor.deleteLater()


def _open(path):
    """The BMP as an image in memory: a PIL image mapped from the file would block the next save on Windows."""
    return Image.open(io.BytesIO(open(path, "rb").read()))


def _rgba(qimg, x, y):
    colour = qimg.pixelColor(x, y)
    return colour.red(), colour.green(), colour.blue(), colour.alpha()


def test_editor_list_defaults_to_found_yychr_and_saves_in_order(settings_dir, monkeypatch):
    exe = settings_dir / "YYCHR.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(external_edit, "YYCHR_CANDIDATES", [str(settings_dir / "missing.exe"), str(exe)])
    assert external_edit.load_editors() == [{"name": "YY-CHR", "path": str(exe), "args": "{file}"}]

    external_edit.save_editors([EDITOR, {"name": "Paint", "path": "mspaint.exe", "args": ""}])
    assert [e["name"] for e in external_edit.load_editors()] == ["Fake", "Paint"]
    external_edit.save_editors([])
    assert external_edit.load_editors() == []       # a saved empty list is not replaced by the defaults


def test_editors_dialog_reorders_and_drops_rows_without_a_program(qtbot):
    dialog = external_edit.ExternalEditorsDialog([EDITOR, {"name": "Paint", "path": "mspaint.exe", "args": ""}])
    qtbot.addWidget(dialog)
    dialog.add_editor({"name": "Empty", "path": "", "args": ""})
    dialog.table.selectRow(1)
    dialog.make_current_default()
    assert [e["name"] for e in dialog.editors()] == ["Paint", "Fake"]
    dialog.table.selectRow(0)
    dialog.remove_current()
    assert dialog.editors() == [EDITOR]


def test_editor_arguments_fill_the_file_into_the_template():
    assert external_edit.editor_arguments({"args": '-open "{file}"'}, r"C:\a b\s.bmp") == ["-open", r"C:\a b\s.bmp"]
    assert external_edit.editor_arguments({"args": "-x"}, "s.bmp") == ["-x", "s.bmp"]
    assert external_edit.editor_arguments({}, "s.bmp") == ["s.bmp"]


def test_truecolor_bmp_maps_colours_back_to_the_sheet_rgba(tmp_path):
    pixels = np.zeros((4, 300, 4), np.uint8)
    pixels[..., :3] = 255
    pixels[..., 3] = np.arange(300) % 256      # 256 alphas over 300 pixels plus a red one: more than 256 colours
    pixels[0, 0] = (255, 0, 0, 255)
    pixels[1, 0] = (0, 255, 0, 255)
    reference = Image.fromarray(pixels, "RGBA")
    path = tmp_path / "s.bmp"
    assert external_edit.write_bmp(reference, path) is None
    assert _open(path).mode == "RGB"
    assert np.array_equal(np.asarray(external_edit.read_bmp(path.read_bytes(), None, reference)), pixels)

    edited = _open(path).convert("RGB")
    edited.putpixel((0, 0), (10, 20, 30))
    edited.save(path)
    result = np.asarray(external_edit.read_bmp(path.read_bytes(), None, reference))
    assert tuple(result[0, 0]) == (10, 20, 30, 255)
    with pytest.raises(external_edit.SizeMismatchError):
        external_edit.read_bmp(path.read_bytes(), None, reference.crop((0, 0, 10, 4)))


def test_saved_sheet_is_applied_as_one_undoable_edit(qtbot, window, launched):
    original = window.sheet_images[0].copy()
    path = window.send_to_external_editor(0, editor=EDITOR)
    assert launched == [("Fake", path)]
    entry = next(iter(window.external_edits()._entries.values()))
    palette = entry["palette"]
    assert palette[0] == (0, 0, 0, 0)               # the transparent background is index 0
    white = palette.index((255, 255, 255, 255))
    edited = _open(path)
    assert edited.mode == "P"
    edited.putpixel((5, 5), white)                  # the external editor draws one pixel and saves in place
    edited.save(path)

    qtbot.waitUntil(lambda: window.undo_stack.count() == 1, timeout=5000)
    assert _rgba(window.sheet_images[0], 5, 5) == (255, 255, 255, 255)
    assert _rgba(window.sheet_images[0], 0, 0) == (255, 255, 255, 128)   # alpha survives the BMP
    assert window._dirty
    assert window.status.currentMessage() == tr("Took the changes from {0}.", "sheet_0.bmp")

    window.undo_stack.undo()
    assert window.sheet_images[0] == original
    qtbot.wait(external_edit.DEBOUNCE_MS * 2)       # a late notification of the same save is not applied again
    assert window.undo_stack.index() == 0


def test_saved_glyph_cell_by_replace_and_size_mismatch(qtbot, window, launched):
    path = window.send_to_external_editor(0, cell=(0, 0), editor=EDITOR)
    entry = next(iter(window.external_edits()._entries.values()))
    white = entry["palette"].index((255, 255, 255, 255))
    edited = _open(path)
    assert edited.size == (12, 12)
    edited.putpixel((2, 3), white)
    temporary = path + ".new"
    edited.save(temporary, "BMP")
    os.replace(temporary, path)                     # many editors save by replacing the file

    qtbot.waitUntil(lambda: window.undo_stack.count() == 1, timeout=5000)
    assert _rgba(window.sheet_images[0], 2, 3) == (255, 255, 255, 255)

    edited.resize((8, 8)).save(path)                # a cell of the wrong size is reported, not applied
    mismatch = tr("{0} is {1}x{2}, expected {3}x{4}: not applied.", os.path.basename(path), 8, 8, 12, 12)
    qtbot.waitUntil(lambda: window.status.currentMessage() == mismatch, timeout=5000)
    assert window.undo_stack.count() == 1

    folder = window.external_edits().directory
    window.clear_temp()                             # the font closes
    assert not os.path.exists(folder)
    assert window.external_edits()._watcher.files() == []


def test_double_click_without_an_editor_asks_for_one_in_the_status_bar(window, launched):
    assert window.send_to_external_editor(0) == ""
    assert launched == []
    assert window.status.currentMessage() == tr("No external editor yet: add one with External Editors...")
