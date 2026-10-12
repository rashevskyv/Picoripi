"""The Font Editor's suggestion action (tools/bfn_editor/glyph_width_suggest.py) on a synthetic font, through the undo stack."""
from PyQt6 import QtGui
from PIL import Image

from core.font_formats import map_entries
from tools.bfn_editor.glyph_width_suggest import suggest_advances


class FakeViewer:
    def __init__(self, metadata, sheets):
        self.metadata = metadata
        self.sheet_images = [pil_to_qimage(sheet) for sheet in sheets]
        self.first_code = 0
        self.cell_w = 10
        self.undo_stack = QtGui.QUndoStack()

    def get_selected_glyph_index(self):
        return -1

    def update_simulation(self):
        pass

    def refresh_table_row(self, *args, **kwargs):
        pass

    def _set_dirty(self, value):
        self.dirty = value


def pil_to_qimage(image):
    rgba = image.convert("RGBA")
    data = rgba.tobytes()
    qimage = QtGui.QImage(data, rgba.width, rgba.height, rgba.width * 4, QtGui.QImage.Format.Format_RGBA8888)
    return qimage.copy()


def synthetic():
    sheet = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for glyph in (0, 1, 2):
        for x in range(6):
            for y in range(5):
                sheet.putpixel((glyph * 10 + x, y), (255, 255, 255, 255))
    metadata = {
        "GLY1": [{"cell_width": 10, "cell_height": 10, "glyph_horizontal_count": 4, "glyph_vertical_count": 2}],
        "MAP1": [map_entries([(ord("A"), 0), (ord("B"), 1), (ord("П"), 2)])],
        "WID1": [{"packets": [{"kerning": 0, "width": 5}, {"kerning": 0, "width": 5},
                              {"kerning": -2, "width": 35}], "glyph_widths": [6, 6, 6]}],
    }
    return metadata, [sheet]


def test_suggestion_is_pushed_as_one_undoable_change():
    metadata, sheets = synthetic()
    viewer = FakeViewer(metadata, sheets)
    assert suggest_advances(viewer, [0, 1, 2]) == 1           # only the Cyrillic glyph changes
    assert metadata["WID1"][0]["packets"][2]["width"] == 7
    viewer.undo_stack.undo()
    assert metadata["WID1"][0]["packets"][2]["width"] == 35   # Undo restores the old width
    viewer.undo_stack.redo()
    assert metadata["WID1"][0]["packets"][2]["width"] == 7
