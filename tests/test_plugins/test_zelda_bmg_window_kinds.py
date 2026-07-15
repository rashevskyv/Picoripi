"""Tests for TP message window kinds (INF1 fuki_kind) and type-aware preview styles."""
import pytest

from plugins.zelda_bmg.window_kinds import (
    decode_message_attributes, window_style_for_kind, window_kind_name,
)


def _info(msg_id=0, fuki_kind=0, se_speaker=0, output_type=0, pos_type=0,
          se_mood=0, camera=0, base_anm=0, face_anm=0):
    """Build INF1 attribute bytes (msg.info layout, JMSMesgEntry_c from +4)."""
    data = bytearray(16)
    data[0] = (msg_id >> 8) & 0xFF
    data[1] = msg_id & 0xFF
    data[4] = se_speaker
    data[5] = fuki_kind
    data[6] = output_type
    data[7] = pos_type
    data[10] = se_mood
    data[11] = camera
    data[12] = base_anm
    data[13] = face_anm
    return bytes(data)


def test_decode_message_attributes():
    attrs = decode_message_attributes(_info(msg_id=0x192, fuki_kind=6, se_speaker=7,
                                            output_type=1, pos_type=2, se_mood=3,
                                            camera=4, base_anm=5, face_anm=9))
    assert attrs["message_id"] == 0x192
    assert attrs["fuki_kind"] == 6
    assert attrs["se_speaker"] == 7
    assert attrs["output_type"] == 1
    assert attrs["fuki_pos_type"] == 2
    assert attrs["se_mood"] == 3
    assert attrs["camera_id"] == 4
    assert attrs["base_anm_id"] == 5
    assert attrs["face_anm_id"] == 9


def test_decode_message_attributes_tolerates_short_info():
    attrs = decode_message_attributes(b"\x00\x01")
    assert attrs["message_id"] == 1
    assert attrs["fuki_kind"] == 0
    assert decode_message_attributes(None)["fuki_kind"] == 0


def test_window_styles_per_kind():
    # signs: wooden (2, 15) and stone (6), no per-character halo
    wood = window_style_for_kind(2)
    assert wood["kind_name"] == "Wooden sign"
    assert wood["frame"]["style"] == "wood"
    assert "halo" not in wood
    assert window_style_for_kind(15)["frame"]["style"] == "wood"
    stone = window_style_for_kind(6)
    assert stone["kind_name"] == "Stone sign"
    assert stone["frame"]["style"] == "stone"

    # item-get window: item icon slot + indented text
    item = window_style_for_kind(9)
    assert item["kind_name"] == "Item get"
    assert item["frame"]["style"] == "item"
    assert item["item_icon"]["size"] == 48.0

    # cutscene subtitles: no frame at all
    jimaku = window_style_for_kind(1)
    assert jimaku["kind_name"] == "Subtitles"
    assert jimaku["frame"] is None
    assert window_style_for_kind(5)["frame"] is None

    # Midna's window: cyan default text, blue halo (dMsgScrnLight type 1)
    midna = window_style_for_kind(13)
    assert midna["kind_name"] == "Midna"
    assert midna["default_text_color"] == "#82e6e6"
    assert midna["halo"]["color"] == "#286eb4"

    # light spirit: bright yellow halo (dMsgScrnLight type 2)
    spirit = window_style_for_kind(8)
    assert spirit["halo"]["color"] == "#ffff6e"
    assert spirit["halo"]["alpha"] == 210

    # unknown/default kinds are the normal talk box with golden halo
    talk = window_style_for_kind(0)
    assert talk["frame"]["style"] == "talk"
    assert talk["halo"]["color"] == "#e1d26e"
    assert window_style_for_kind(99)["frame"]["style"] == "talk"
    assert window_style_for_kind(None)["frame"]["style"] == "talk"


def test_window_kind_names():
    assert window_kind_name(12) == "Location name"
    assert window_kind_name(19) == "Boss name"
    assert window_kind_name(17) == "Howling stone"
    assert window_kind_name(7) == "Staff credits"
    assert window_kind_name(0) == "Dialogue"


class _FakeMsg:
    def __init__(self, info):
        self.info = info
        self.id = 0
        self.parts = ["x"]


class _FakeBmg:
    def __init__(self, messages):
        self.messages = messages
        self.other_sections = {}


class _MockMW:
    def __init__(self):
        self.data_store = self
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.newline_display_symbol = "↵"


@pytest.fixture
def bmg_rules(qapp):
    from plugins.zelda_bmg.rules import GameRules
    return GameRules(_MockMW())


def test_rules_message_attributes_and_style(bmg_rules):
    bmg_rules.last_loaded_bmg = _FakeBmg([
        _FakeMsg(_info(msg_id=0x100, fuki_kind=0)),   # talk
        _FakeMsg(_info(msg_id=0x101, fuki_kind=6)),   # stone sign
        _FakeMsg(_info(msg_id=0x102, fuki_kind=9)),   # item get
        _FakeMsg(_info(msg_id=0x103, fuki_kind=13)),  # Midna
    ])

    attrs = bmg_rules.get_message_attributes(0, 1)
    assert attrs["fuki_kind"] == 6 and attrs["message_id"] == 0x101

    assert bmg_rules.get_preview_window_style(0, 0)["frame"]["style"] == "talk"
    assert bmg_rules.get_preview_window_style(0, 1)["frame"]["style"] == "stone"
    assert bmg_rules.get_preview_window_style(0, 2)["item_icon"]["size"] == 48.0
    assert bmg_rules.get_preview_window_style(0, 3)["default_text_color"] == "#82e6e6"

    # out of range / unresolvable -> default talk style, no crash
    assert bmg_rules.get_preview_window_style(0, 99)["frame"]["style"] == "talk"
    assert bmg_rules.get_preview_window_style(None, None)["frame"]["style"] == "talk"
    assert bmg_rules.get_message_attributes(0, "bad") is None


def test_rules_string_layout_from_json(bmg_rules):
    bmg_rules.last_loaded_bmg = _FakeBmg([
        _FakeMsg(_info(fuki_kind=0)),    # talk -> global widths
        _FakeMsg(_info(fuki_kind=6)),    # stone sign
        _FakeMsg(_info(fuki_kind=9)),    # item window
        _FakeMsg(_info(fuki_kind=12)),   # location plate
    ])

    talk = bmg_rules.get_string_layout(0, 0)
    assert talk.get("warn_width") is None  # null -> use globals
    assert talk["lines_per_page"] == 4

    sign = bmg_rules.get_string_layout(0, 1)
    assert (sign["warn_width"], sign["max_width"]) == (260, 280)

    item = bmg_rules.get_string_layout(0, 2)
    assert (item["warn_width"], item["max_width"]) == (230, 250)

    plate = bmg_rules.get_string_layout(0, 3)
    assert plate["lines_per_page"] == 1

    # preview style carries the pagination setting
    assert bmg_rules.get_preview_window_style(0, 3)["lines_per_page"] == 1
    assert bmg_rules.get_preview_window_style(0, 0)["lines_per_page"] == 4


def test_resolve_width_limits_priority(bmg_rules):
    from utils.utils import resolve_width_limits

    bmg_rules.last_loaded_bmg = _FakeBmg([_FakeMsg(_info(fuki_kind=6))])

    # plugin window-kind layout beats globals
    warn, max_w = resolve_width_limits({}, bmg_rules, 0, 0, 280, 300)
    assert (warn, max_w) == (260, 280)

    # explicit per-string override beats everything
    warn, max_w = resolve_width_limits({"width": 111}, bmg_rules, 0, 0, 280, 300)
    assert (warn, max_w) == (111, 111)

    # no rules / no layout -> globals
    warn, max_w = resolve_width_limits({}, None, 0, 0, 280, 300)
    assert (warn, max_w) == (280, 300)

    # broken hook results (e.g. mocks) fall back to globals safely
    class _Broken:
        def get_string_layout(self, b, s):
            return object()
    warn, max_w = resolve_width_limits({}, _Broken(), 0, 0, 280, 300)
    assert (warn, max_w) == (280, 300)


def test_slice_page_splits_render_data():
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    text = "L1\nL2\nL3\nL4\nL5\nL6"
    colors = ["#f07878"] * len(text)
    scales = [1.0] * len(text)
    icons = {0: {"kind": "char"}, 9: {"kind": "circle"}}  # L1 and L4 positions

    page0, c0, s0, i0, pages = BfnPreviewWidget._slice_page(text, colors, scales, icons, 3, 0)
    assert pages == 2
    assert page0 == "L1\nL2\nL3"
    assert len(c0) == len(page0)
    assert 0 in i0 and 9 not in i0

    page1, c1, s1, i1, _ = BfnPreviewWidget._slice_page(text, colors, scales, icons, 3, 1)
    assert page1 == "L4\nL5\nL6"
    assert len(c1) == len(page1)
    assert i1 == {0: {"kind": "circle"}}  # L4's icon re-keyed to page start

    # page index out of range is clamped
    last, _, _, _, _ = BfnPreviewWidget._slice_page(text, None, None, None, 3, 99)
    assert last == "L4\nL5\nL6"


@pytest.mark.parametrize("kind, expected_hue", [
    (2, "wood"),    # wooden sign: brownish frame pixels
    (6, "stone"),   # stone sign: gray frame pixels
    (9, "item"),    # item window: teal item placeholder
])
def test_preview_widget_renders_window_kind_frames(qapp, kind, expected_hue):
    """Smoke: each frame style paints without errors and leaves its pixels."""
    from unittest.mock import MagicMock
    from ui.components.bfn_preview_widget import BfnPreviewWidget
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import Qt
    from core.bfn_core import BfnCore

    def _make_renderable_bfn():
        bfn = BfnCore()
        bfn.inf1 = [{"encoding": 1, "ascent": 20, "descent": 4, "width": 12,
                     "leading": 24, "fallback_code": 0, "unk1": 0}]
        bfn.gly1 = [{"start_glyph": 0, "end_glyph": 95, "cell_width": 24, "cell_height": 24,
                     "page_data_size": 0, "texture_format": 0,
                     "glyph_horizontal_count": 5, "glyph_vertical_count": 5,
                     "texture_width": 120, "texture_height": 120, "sheets_binary": []}]
        bfn.map1 = [{"mapping_type": 2, "first_char": 32, "last_char": 127,
                     "mapping_entry_count": 96, "entries": list(range(96))}]
        bfn.wid1 = [{"first_code_included": 0, "last_code_included": 95,
                     "packets": [{"kerning": 0, "width": 20}] * 95}]
        sheets = []
        for _ in range(4):
            img = QImage(120, 120, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.white)
            sheets.append(img)
        bfn._qimages_cache = sheets
        return bfn

    mw = MagicMock()
    mw.active_game_plugin = "zelda_bmg"
    rules = MagicMock()
    rules.get_preview_window_style.return_value = window_style_for_kind(kind)
    rules.prepare_preview_glyph_text.return_value = ("AB", None, None, None)
    mw.current_game_rules = rules
    mw.data_store.current_block_idx = -1
    mw.data_store.current_string_idx = -1
    mw.default_font_file = None
    mw.all_bfn_fonts = {"tp.bfn": _make_renderable_bfn()}
    mw.project_manager = None
    mw.preview_bg_image_path = ""
    mw.preview_bg_scale = 100
    mw.preview_bg_offset_x = 0
    mw.preview_bg_offset_y = 0
    mw.preview_bg_hidden = False
    mw.preview_line_spacing = 10
    mw.preview_text_rect = [40, 30, 280, 110]
    mw.preview_text_color = "#ffffff"
    mw.preview_shadow_enabled = False
    mw.preview_glow_enabled = False
    mw.preview_fix_font_scale = False
    mw.preview_fixed_font_scale = 1.0
    mw.preview_char_spacing = 0

    widget = BfnPreviewWidget(mw)
    widget.resize(420, 220)
    widget.text = "AB"
    widget.show()
    try:
        image = widget.grab().toImage()
    finally:
        widget.hide()

    brown = gray = teal = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if r > 70 and r > g > b and (r - b) > 30:
                brown += 1
            elif 80 < r < 170 and abs(r - g) < 10 and abs(g - b) < 12 and r > b:
                gray += 1
            elif g > 150 and b > 120 and g > r + 30:
                teal += 1

    if expected_hue == "wood":
        assert brown > 200, "wooden sign frame not painted"
    elif expected_hue == "stone":
        assert gray > 200, "stone sign frame not painted"
    else:
        assert teal > 20, "item placeholder not painted"
