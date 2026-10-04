"""The shared Font Editor on the Tingle Tuner client font (format gba_tiles): open from a project, draw a
letter into a free cell, save into the translation copy, reopen."""
from types import SimpleNamespace

from PyQt6 import QtGui, QtWidgets

from core import font_formats
from core.containers import lz10
from core.font_formats import gba_tiles
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow

from .samples import PARAMS, client


class _Rules:
    def get_font_sources(self):
        return [{"label": "Tingle Tuner font (GBA)", "format": "gba_tiles", "path": "client_u.bin",
                 "font_map": "tingle_font.json", "params": PARAMS}]


class _MainWindow(QtWidgets.QMainWindow):
    def __init__(self, tmp_path):
        super().__init__()
        self.active_game_plugin = None
        self.fonts_dir_path = None
        self.current_game_rules = _Rules()
        metadata = {"source_path": str(tmp_path / "source"), "translation_path": str(tmp_path / "translation"),
                    "is_directory_mode": True}
        self.project_manager = SimpleNamespace(project=SimpleNamespace(metadata=metadata),
                                               project_dir=str(tmp_path / "project"))
        (tmp_path / "project").mkdir(exist_ok=True)


def _open(window):
    editor = BfnEditorWindow(parent=window)
    editor.scan_fonts_directories()
    editor.load_font_source(editor.font_sources["Tingle Tuner font (GBA)"]["font_source"])
    return editor


def test_tile_font_is_drawn_saved_and_reopened(qtbot, tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "client_u.bin").write_bytes(client())
    window = _MainWindow(tmp_path)
    qtbot.addWidget(window)

    editor = _open(window)
    assert editor.font_format == "gba_tiles"
    assert font_formats.char_map(editor.metadata)["Б"] == 5
    for x in range(41, 46):                                       # glyph 5: a bar on row 2
        editor.sheet_images[0].setPixelColor(x, 2, QtGui.QColor(255, 255, 255, 255))
    editor.save_changes(silent=True)

    assert (tmp_path / "source" / "client_u.bin").read_bytes() == client()
    written = (tmp_path / "translation" / "client_u.bin").read_bytes()
    program = gba_tiles.read_program(written, PARAMS)
    tiles = lz10.decompress(program, 0x100)[0]
    assert tiles[5 * 32 + 8:5 * 32 + 12] == bytes([0xF1, 0xFF, 0xFF, 0x11])
    assert program[0x700] == 5                                     # the slot code now draws tile 5

    again = _open(window)                                         # reads the translation copy
    assert again.sheet_images[0].pixelColor(43, 2).alpha() == 255
