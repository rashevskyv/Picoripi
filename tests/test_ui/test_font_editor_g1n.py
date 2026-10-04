"""The font editor on a G1N font (Age of Calamity) opened from a project: a character the font lacks gets a glyph."""
from PyQt6 import QtGui

from core import font_formats
from test_core.test_font_formats_g1n import SAMPLE

from .test_font_editor_formats import _MainWindow, _open


def test_g1n_font_gets_a_new_glyph_for_a_character_it_lacks(qtbot, tmp_path):
    font = tmp_path / "source" / "font" / "latin.g1n"
    font.parent.mkdir(parents=True)
    font.write_bytes(SAMPLE)
    descriptors = [{"label": "Text 8 px", "format": "g1n", "path": "font/latin.g1n", "params": {"font": 0, "spare": 4}}]
    window = _MainWindow(tmp_path, descriptors)
    qtbot.addWidget(window)

    editor = _open(window, "Text 8 px")
    assert editor.font_format == "g1n"
    glyph = 3                                                    # the first empty cell after the font's glyphs
    code = editor.physical_code_for("Ж")
    assert code == font_formats.char_code("Ж")
    editor.update_char_mapping(glyph, code)
    gly = editor.metadata["GLY1"][0]
    x, y = glyph % gly["glyph_horizontal_count"] * gly["cell_width"], glyph // gly["glyph_horizontal_count"] * gly["cell_height"]
    editor.sheet_images[0].setPixelColor(x + 1, y + 2, QtGui.QColor(255, 255, 255, 255))
    editor.metadata["WID1"][0]["packets"][glyph]["width"] = 4
    editor.save_changes(silent=True)

    assert font.read_bytes() == SAMPLE
    written = (tmp_path / "mod" / "font" / "latin.g1n").read_bytes()
    metadata, sheets = font_formats.extract("g1n", written, {"font": 0, "spare": 4})
    assert font_formats.char_map(metadata)["Ж"] == glyph and metadata["WID1"][0]["packets"][glyph]["width"] == 4
    assert sheets[0].getpixel((x + 1, y + 2))[3] == 255
