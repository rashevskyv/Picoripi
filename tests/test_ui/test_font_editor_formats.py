"""The font editor on fonts a game plugin describes: G1T and BFN in an archive, opened from a project,
edited, saved into the translation copy, with the widths written for the width checks."""
import json
import struct
from types import SimpleNamespace

from PIL import Image, ImageDraw
from PyQt6 import QtGui, QtWidgets

from core import font_formats
from core.bfn_core import BfnCore
from core.font_formats import sources
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow

G1T_PARAMS = dict(cell_width=16, cell_height=16, columns=4, first_cell=4, first_code=0xC0, last_code=0xC3,
                  spacing=2, ink_threshold=64)


def _g1t():
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    for index in range(4):
        x, y = (4 + index) % 4 * 16, (4 + index) // 4 * 16
        ImageDraw.Draw(image).rectangle((x + 2, y + 3, x + 4 + index, y + 12), fill=(255, 255, 255, 255))
    entry = bytes([0x10, 0x5B, 6 | 6 << 4, 0, 0, 0, 0, 0])
    data = bytearray(b"GT1G0600" + struct.pack("<IIIII", 0, 0x20, 1, 0x10, 0) + bytes(4) + struct.pack("<I", 4)
                     + entry + image.tobytes("bcn", 3))
    struct.pack_into("<I", data, 8, len(data))
    return bytes(data)


def _u8(name: str, payload: bytes) -> bytes:
    """A U8 archive with one file."""
    names = b"\x00" + name.encode() + b"\x00"
    nodes_size = 24 + len(names)
    data_at = (0x20 + nodes_size + 31) & ~31
    nodes = struct.pack(">HHII", 0x0100, 0, 1, 2) + struct.pack(">HHII", 0, 1, data_at, len(payload))
    head = struct.pack(">IIII", 0x55AA382D, 0x20, nodes_size, data_at) + bytes(16) + nodes + names
    return head + bytes(data_at - len(head)) + payload + bytes(-len(payload) % 32)


def _bfn():
    bfn = BfnCore()
    bfn.signature = "FONTbfn1"
    bfn.inf1 = [{"encoding": 0, "ascent": 6, "descent": 2, "width": 8, "leading": 8, "fallback_code": 0x41, "unk1": 0}]
    bfn.gly1 = [{"start_glyph": 0, "end_glyph": 1, "cell_width": 8, "cell_height": 8, "page_data_size": 64,
                 "texture_format": 0, "glyph_horizontal_count": 2, "glyph_vertical_count": 1,
                 "texture_width": 16, "texture_height": 8, "sheets_binary": [bytes(64)]}]
    bfn.map1 = [{"mapping_type": 2, "first_char": 0x41, "last_char": 0x42, "mapping_entry_count": 2, "entries": [0, 1]}]
    bfn.wid1 = [{"first_code_included": 0, "last_code_included": 2,
                 "packets": [{"kerning": 0, "width": 6}, {"kerning": 0, "width": 7}]}]
    return bfn.save()


class _Rules:
    def __init__(self, descriptors):
        self.descriptors = descriptors

    def get_font_sources(self):
        return self.descriptors


class _MainWindow(QtWidgets.QMainWindow):
    """What the editor reads from Picoripi's main window."""

    def __init__(self, tmp_path, descriptors):
        super().__init__()
        self.active_game_plugin = None
        self.fonts_dir_path = None
        self.current_game_rules = _Rules(descriptors)
        metadata = {"source_path": str(tmp_path / "source"), "translation_path": str(tmp_path / "mod"),
                    "is_directory_mode": True}
        self.project_manager = SimpleNamespace(project=SimpleNamespace(metadata=metadata),
                                               project_dir=str(tmp_path / "project"))
        (tmp_path / "project").mkdir(exist_ok=True)


def _open(window, label):
    editor = BfnEditorWindow(parent=window)
    editor.scan_fonts_directories()
    info = editor.font_sources[label]
    assert info["type"] == "plugin"
    editor.load_font_source(info["font_source"])
    return editor


def test_g1t_font_from_a_project_is_edited_saved_and_reopened(qtbot, tmp_path):
    font = tmp_path / "source" / "data" / "font.g1t"
    font.parent.mkdir(parents=True)
    font.write_bytes(_g1t())
    descriptors = [{"label": "Text font", "format": "g1t", "path": "data/font.g1t", "font_map": "game.json",
                    "params": G1T_PARAMS}]
    window = _MainWindow(tmp_path, descriptors)
    qtbot.addWidget(window)
    (tmp_path / "project" / "translation_map.json").write_text(json.dumps({"Ж": "Á"}), encoding="utf-8")

    editor = _open(window, "Text font")
    assert editor.font_format == "g1t" and len(editor.sheet_images) == 1
    glyph_b = font_formats.char_map(editor.metadata)["Á"]
    editor.sheet_images[0].setPixelColor(1, 1, QtGui.QColor(255, 255, 255, 255))   # cell 0
    editor.metadata["WID1"][0]["packets"][glyph_b]["width"] = 11
    editor.save_changes(silent=True)

    assert font.read_bytes() == _g1t()                           # the source stays the game's
    written = (tmp_path / "mod" / "data" / "font.g1t").read_bytes()
    assert written != font.read_bytes()
    widths = json.loads((tmp_path / "project" / "font_maps" / "game.json").read_text(encoding="utf-8"))
    assert widths["Á"] == {"width": 11} and widths["Ж"] == {"width": 11}

    again = _open(window, "Text font")                           # reads the translation copy
    assert again.sheet_images[0].pixelColor(1, 1).alpha() == 255
    assert again.metadata["WID1"][0]["packets"][glyph_b]["width"] == 11      # G1T stores no widths: kept in the map
    assert again.original_font_metadata is not None                          # the game's font for comparison


def test_bfn_font_inside_an_archive_is_written_back_into_the_archive(qtbot, tmp_path):
    archive = tmp_path / "source" / "res" / "fontres.arc"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(_u8("main.bfn", _bfn()))
    descriptors = [{"label": "Message font", "format": "bfn", "path": "res/fontres.arc", "member": "*.bfn"}]
    window = _MainWindow(tmp_path, descriptors)
    qtbot.addWidget(window)

    editor = _open(window, "Message font: main.bfn")
    assert editor.font_format == "bfn" and editor.font_source is not None
    editor.metadata["WID1"][0]["packets"][1]["width"] = 5
    editor.save_changes(silent=True)

    (source,) = sources.resolve(descriptors, window.project_manager.project.metadata)
    assert source.read_original() == _bfn()
    saved = BfnCore()
    saved.load(source.read_current())
    assert saved.wid1[0]["packets"][1]["width"] == 5
    widths = json.loads((tmp_path / "project" / "font_maps" / "main.json").read_text(encoding="utf-8"))
    assert widths["B"] == {"width": 5}


def test_font_jobs_run_in_a_worker_thread_one_after_another(qtbot, monkeypatch):
    from PyQt6.QtCore import QThread
    from utils import app_mode
    monkeypatch.setattr(app_mode, "headless", False)
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    main_thread = QThread.currentThread()
    seen = []

    def work(value):
        return value, QThread.currentThread() is not main_thread

    editor.run_font_job(lambda: work(1), lambda result, error: seen.append((result, error)))
    editor.run_font_job(lambda: 1 / 0, lambda result, error: seen.append((result, error)))
    editor.run_font_job(lambda: work(3), lambda result, error: seen.append((result, error)))
    qtbot.waitUntil(lambda: len(seen) == 3, timeout=5000)
    assert seen[0] == ((1, True), "") and seen[2] == ((3, True), "")
    assert seen[1][0] is None and "division" in seen[1][1]
    qtbot.waitUntil(lambda: editor._font_job is None, timeout=5000)