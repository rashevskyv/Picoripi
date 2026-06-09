import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from tools.bfn_editor.bfn_widgets import ImageView, SimImageView, RenderFontDialog, ScaleSliderWidget
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow

@pytest.fixture
def dummy_bfn_bytes():
    from core.bfn_core import BfnCore
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    bfn.inf1 = [{
        "encoding": 0,
        "ascent": 20,
        "descent": 2,
        "width": 12,
        "leading": 2,
        "fallback_code": 63,
        "unk1": 0
    }]
    bfn.gly1 = [{
        "texture_format": 0,
        "glyph_width": 12,
        "glyph_height": 12,
        "texture_width": 128,
        "texture_height": 128,
        "cell_width": 12,
        "cell_height": 12,
        "page_data_size": 8192,
        "glyph_horizontal_count": 10,
        "glyph_vertical_count": 10,
        "start_glyph": 0,
        "end_glyph": 100,
        "sheets": [b"\x00" * 8192]
    }]
    bfn.map1 = [{
        "mapping_type": 2,
        "first_char": 32,
        "last_char": 34,
        "mapping_entry_count": 2,
        "entries": [0, 1]
    }]
    bfn.wid1 = [{
        "first_code_included": 32,
        "last_code_included": 34,
        "packets": [
            {"kerning": 0, "width": 8},
            {"kerning": 1, "width": 10}
        ]
    }]
    return bfn.save()

def test_image_view_zoom(qapp):
    """Test zoom-in and zoom-out behaviors in ImageView."""
    view = ImageView()
    view.set_scale(1.0)
    assert view._scale == 1.0
    
    # Test wheel zoom in (positive angleDelta)
    # We mock wheel event
    event_zoom_in = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, 120), # positive delta
        QtCore.QPoint(0, 120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    view.wheelEvent(event_zoom_in)
    assert view._scale > 1.0
    
    # Test wheel zoom out (negative angleDelta)
    scale_before = view._scale
    event_zoom_out = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, -120), # negative delta
        QtCore.QPoint(0, -120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    view.wheelEvent(event_zoom_out)
    assert view._scale < scale_before
    
    # Test min/max scale boundaries
    view.set_scale(0.1) # below min (0.5) via wheel event logic
    event_zoom_out = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, -120),
        QtCore.QPoint(0, -120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    # Set to boundary value to test clamping
    view._scale = 0.51
    view.wheelEvent(event_zoom_out)
    assert view._scale >= 0.5
    
    view._scale = 19.9
    event_zoom_in = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, 120),
        QtCore.QPoint(0, 120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    view.wheelEvent(event_zoom_in)
    assert view._scale <= 20.0

def test_sim_image_view_zoom(qapp):
    """Test zoom-in and zoom-out behaviors in SimImageView."""
    view = SimImageView()
    view.set_scale(1.0)
    assert view._scale == 1.0
    
    event_zoom_in = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, 120),
        QtCore.QPoint(0, 120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    view.wheelEvent(event_zoom_in)
    assert view._scale > 1.0
    
    scale_before = view._scale
    event_zoom_out = QtGui.QWheelEvent(
        QtCore.QPointF(50, 50),
        QtCore.QPointF(50, 50),
        QtCore.QPoint(0, -120),
        QtCore.QPoint(0, -120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False
    )
    view.wheelEvent(event_zoom_out)
    assert view._scale < scale_before
    
    view._scale = 0.21
    view.wheelEvent(event_zoom_out)
    assert view._scale >= 0.2
    
    view._scale = 14.9
    view.wheelEvent(event_zoom_in)
    assert view._scale <= 15.0

def test_render_font_dialog_preview_and_scaling(qapp, dummy_bfn_bytes):
    """Test RenderFontDialog preview rendering, horizontal and vertical scaling controls."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    preview_list = [{"char": "A", "img": QtGui.QImage(12, 12, QtGui.QImage.Format.Format_ARGB32), "idx": 0}]
    dialog = RenderFontDialog(editor, cell_w=12, cell_h=12, has_selected_glyph=True, preview_list=preview_list)
    
    # Change horizontal scale
    dialog.scale_h.setValue(150)
    assert dialog.scale_h.value() == 150
    
    # Change vertical scale
    dialog.scale_v.setValue(80)
    assert dialog.scale_v.value() == 80
    
    # Verify values returned by get_params()
    params = dialog.get_params()
    assert params["h_scale"] == 150
    assert params["v_scale"] == 80
    
    # Check that preview updates without crashing
    dialog._update_preview()
    assert dialog.lbl_preview_new.pixmap() is not None
    
    editor.clear_temp()
    editor.close()
