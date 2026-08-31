"""Tests for TP message window kinds (INF1 fuki_kind) and type-aware preview styles."""
import pytest

from plugins.zelda_bmg.window_kinds import (
    decode_message_attributes, window_style_for_kind, window_kind_name,
    layout_for_kind, load_window_layouts,
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
    # signs: wooden (2) and stone (6), no per-character halo
    wood = window_style_for_kind(2)
    assert wood["kind_name"] == "Wooden sign"
    assert wood["frame"]["style"] == "wood"
    assert "halo" not in wood
    stone = window_style_for_kind(6)
    assert stone["kind_name"] == "Stone sign"
    assert stone["frame"]["style"] == "stone"

    # kind 15 is Talk visuals with kanban pagination — not a wooden sign
    kanban_talk = window_style_for_kind(15)
    assert kanban_talk["kind_name"] == "Dialogue (kanban)"
    assert kanban_talk["frame"]["style"] == "talk"
    assert kanban_talk["halo"]["color"] == "#e1d26e"
    assert kanban_talk["screen_class"] == "talk"

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
    assert window_style_for_kind(99)["kind_name"] == "Dialogue (kind 99)"
    assert window_style_for_kind(None)["frame"]["style"] == "talk"


def test_window_kind_names():
    assert window_kind_name(12) == "Location name"
    assert window_kind_name(19) == "Boss name"
    assert window_kind_name(17) == "Howling stone"
    assert window_kind_name(7) == "Staff credits"
    assert window_kind_name(0) == "Dialogue"


def test_original_game_fonts_follow_window_kind():
    layouts = load_window_layouts()
    assert layout_for_kind(layouts, 0)["font_file"] == "rodan_b_24_22.bfn"
    assert layout_for_kind(layouts, 12)["font_file"] == "reishotai_24_22.bfn"
    assert layout_for_kind(layouts, 19)["font_file"] == "reishotai_24_22.bfn"


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


def test_boss_names_are_excluded_from_automatic_story_matching(bmg_rules):
    bmg_rules.last_loaded_bmg = _FakeBmg([
        _FakeMsg(_info(fuki_kind=19)),
        _FakeMsg(_info(fuki_kind=0)),
    ])

    assert not bmg_rules.should_auto_match_story_context(0, 0)
    assert bmg_rules.should_auto_match_story_context(0, 1)

    boss_context = bmg_rules.get_translation_context_for_string(0, 0)
    # The plugin owns both the role and what it means: the engine only carries
    # has_speaker and role_instruction through without interpreting them.
    assert boss_context["window_type"] == "Boss name"
    assert boss_context["content_role"] == "BossName"
    assert boss_context["glossary_section"] == "Boss Names"
    assert boss_context["force_glossary"] is True
    assert boss_context["has_speaker"] is False
    assert "boss title/name card" in boss_context["role_instruction"]
    assert bmg_rules.get_translation_context_for_string(0, 1) == {
        "window_type": "Dialogue",
    }


@pytest.mark.parametrize("kind, warn, max_width, lines", [
    (0, 410, 435, 4),    # talk default
    (1, 460, 480, 4),    # subtitles / jimaku getLineMax
    (5, 460, 480, 4),
    (2, 340, 360, 7),    # wooden sign (kanban pagination)
    (6, 340, 360, 7),    # stone sign
    (15, 410, 435, 7),   # Dialogue (kanban): Talk widths, kanban lines
    (7, 400, 420, 10),   # staff credits
    (9, 340, 360, 4),    # item window
    (16, 410, 435, 6),   # descriptions / save
    (12, 420, 440, 4),   # location name
    (19, 420, 440, 4),   # boss name
    (17, 300, 320, 4),   # howling
])
def test_rules_string_layout_uses_json_defaults_per_window_kind(
        bmg_rules, kind, warn, max_width, lines):
    bmg_rules.last_loaded_bmg = _FakeBmg([_FakeMsg(_info(fuki_kind=kind))])

    layout = bmg_rules.get_string_layout(0, 0)

    assert layout["warn_width"] == warn
    assert layout["max_width"] == max_width
    assert layout["lines_per_page"] == lines


def test_message_0x02a5_forces_item_window(bmg_rules):
    bmg_rules.last_loaded_bmg = _FakeBmg([
        _FakeMsg(_info(msg_id=0x02A5, fuki_kind=0)),
    ])
    style = bmg_rules.get_preview_window_style(0, 0)
    layout = bmg_rules.get_string_layout(0, 0)
    assert style["kind_name"] == "Item get"
    assert style["frame"]["style"] == "item"
    assert layout["max_width"] == 360


class _PreviewDS:
    def __init__(self, json_path="a.bmg", edited_json_path=None):
        self.physical_block_idx = 0
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.json_path = json_path
        self.edited_json_path = edited_json_path


def _wire_preview_mw(bmg_rules, msg):
    bmg_rules.last_loaded_bmg = _FakeBmg([msg])
    bmg_rules.mw.data_store = _PreviewDS()
    bmg_rules.mw.active_game_plugin = "zelda_bmg"
    bmg_rules.mw.current_game_rules = bmg_rules
    bmg_rules.mw.preview_enabled = True
    bmg_rules.mw.preview_bg_image_path = ""
    bmg_rules.mw.preview_bg_scale = 100
    bmg_rules.mw.preview_bg_offset_x = 0
    bmg_rules.mw.preview_bg_offset_y = 0
    bmg_rules.mw.preview_bg_hidden = False
    bmg_rules.mw.preview_line_spacing = 10
    bmg_rules.mw.preview_text_rect = [40, 30, 280, 110]
    bmg_rules.mw.preview_text_color = "#ffffff"
    bmg_rules.mw.preview_shadow_enabled = False
    bmg_rules.mw.preview_glow_enabled = False
    bmg_rules.mw.preview_fix_font_scale = False
    bmg_rules.mw.preview_fixed_font_scale = 1.0
    bmg_rules.mw.preview_char_spacing = 0
    bmg_rules.mw.all_bfn_fonts = {}
    bmg_rules.mw.default_font_file = None
    bmg_rules.mw.project_manager = None
    bmg_rules.mw.string_metadata = {}
    return bmg_rules.mw


def test_manual_preview_override_does_not_mutate_bmg_info(qapp, bmg_rules):
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    info = bytearray(_info(msg_id=0x100, fuki_kind=0))
    msg = _FakeMsg(bytes(info))
    _wire_preview_mw(bmg_rules, msg)

    widget = BfnPreviewWidget(bmg_rules.mw)
    before = bytes(msg.info)
    widget.cycle_window_preset(1)  # Dialogue explicit
    widget.cycle_window_preset(1)  # Wooden sign
    assert bytes(msg.info) == before
    assert decode_message_attributes(msg.info)["fuki_kind"] == 0
    assert widget._get_game_window_style()["frame"]["style"] == "wood"
    # Auto still resolves from the unchanged message attrs
    widget._window_preset_override = None
    assert widget._get_game_window_style()["frame"]["style"] == "talk"


def test_preview_override_resets_when_file_path_changes(qapp, bmg_rules):
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    msg = _FakeMsg(_info(msg_id=0x100, fuki_kind=0))
    _wire_preview_mw(bmg_rules, msg)
    widget = BfnPreviewWidget(bmg_rules.mw)
    widget.cycle_window_preset(1)
    widget.cycle_window_preset(1)  # Wooden sign
    assert widget._window_preset_override == 2

    # Same block index, different loaded file -> override returns to Auto
    bmg_rules.mw.data_store.json_path = "other_file.bmg"
    widget._sync_window_preset_scope()
    assert widget._window_preset_override is None
    assert widget._get_game_window_style()["frame"]["style"] == "talk"


def test_manual_override_beats_0x02a5_in_preview_only(qapp, bmg_rules):
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    info = bytearray(_info(msg_id=0x02A5, fuki_kind=0))
    msg = _FakeMsg(bytes(info))
    _wire_preview_mw(bmg_rules, msg)
    widget = BfnPreviewWidget(bmg_rules.mw)

    assert widget._resolve_auto_window_style()["frame"]["style"] == "item"
    assert bmg_rules.get_string_layout(0, 0)["max_width"] == 360

    widget.cycle_window_preset(1)
    widget.cycle_window_preset(1)  # Wooden sign override
    assert widget._get_game_window_style()["frame"]["style"] == "wood"
    # Layout / Auto still force Item from message id; INF1 untouched
    assert bmg_rules.get_string_layout(0, 0)["max_width"] == 360
    assert widget._resolve_auto_window_style()["kind_name"] == "Item get"
    assert decode_message_attributes(msg.info)["message_id"] == 0x02A5
    assert decode_message_attributes(msg.info)["fuki_kind"] == 0
    assert bytes(msg.info) == bytes(info)


def test_talk_and_item_styles_carry_blo_text_metrics():
    talk = window_style_for_kind(0)
    metrics = talk["geometry"]["text_metrics"]
    assert metrics["font_y"] == 22.0
    assert metrics["line_space"] == 23.0
    assert metrics["char_space"] == 1.0
    item = window_style_for_kind(9)
    assert item["geometry"]["text_metrics"]["font_y"] == 23.0
    wood = window_style_for_kind(2)
    assert wood["geometry"]["text_metrics"]["font_x"] == 25.0


def test_textbox_height_center_centers_used_lines():
    from plugins.zelda_bmg.window_frame_loader import textbox_height_center

    # Talk mg_e4lin 114px, fontY 22, lineSpace 23, 4-line box, 2-line page.
    two = textbox_height_center(114.0, 22.0, 23.0, 4, 2)
    four = textbox_height_center(114.0, 22.0, 23.0, 4, 4)
    used_h = 22.0 + 23.0  # two lines
    assert abs(two - (114.0 - used_h) / 2.0) < 1e-6
    assert four < two
    # Game formula is equivalent to centering the used block.
    assert two > 30.0


def test_talk_fade_is_translucent_not_a_solid_bar(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPainter, QColor
    from plugins.zelda_bmg.window_frame_loader import _paint_talk_like

    fade = QImage(32, 32, QImage.Format.Format_ARGB32)
    fade.fill(QColor(180, 180, 180, 180))
    kado = QImage(16, 16, QImage.Format.Format_ARGB32)
    kado.fill(QColor(255, 255, 255, 200))
    textures = {
        "message_window_base_112_8i_02": fade,
        "message_window_base_8_01": fade,
        "tt_message_win_kado_216_01": kado,
    }
    canvas = QImage(608, 448, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    try:
        _paint_talk_like(painter, (29.5, 273.5, 551.0, 117.0), textures, item=False)
    finally:
        painter.end()
    sample = canvas.pixelColor(305, 332)
    assert 20 < sample.alpha() < 240, sample.alpha()
    assert sample.red() < 40 and sample.green() < 40 and sample.blue() < 40


def test_unknown_kind_shows_number_and_json_can_name_it():
    unknown = window_style_for_kind(42)
    assert unknown["kind_name"] == "Dialogue (kind 42)"
    assert unknown["frame"]["style"] == "talk"

    named = window_style_for_kind(42, {"name": "Item info", "lines_per_page": 10})
    assert named["kind_name"] == "Item info"
    assert named["lines_per_page"] == 10


def test_save_window_kind_16():
    assert window_kind_name(16) == "Descriptions / save"
    assert window_style_for_kind(16)["frame"]["style"] == "talk"


def test_bmg_block_resolution_is_cached(bmg_rules):
    """Hot-path safety: repeated layout lookups must not re-resolve the BMG."""
    bmg_rules.last_loaded_bmg = _FakeBmg([_FakeMsg(_info(fuki_kind=6))])

    first, _, _ = bmg_rules._get_bmg_for_block(0)
    assert first is bmg_rules.last_loaded_bmg
    # cached entry is reused (same object, no re-resolution inside TTL)
    second, _, _ = bmg_rules._get_bmg_for_block(0)
    assert second is first
    assert 0 in bmg_rules._bmg_block_resolve_cache

    # many repeated calls are cheap dict hits
    for _ in range(200):
        assert bmg_rules.get_string_layout(0, 0) is not None


def test_resolve_width_limits_priority(bmg_rules):
    from utils.utils import resolve_width_limits

    bmg_rules.last_loaded_bmg = _FakeBmg([_FakeMsg(_info(fuki_kind=6))])

    # plugin window-kind JSON defaults beat globals
    warn, max_w = resolve_width_limits({}, bmg_rules, 0, 0, 999, 999)
    assert (warn, max_w) == (340, 360)

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


def test_global_window_layout_mode_uses_legacy_shared_rules(bmg_rules):
    from utils.utils import resolve_width_limits

    bmg_rules.last_loaded_bmg = _FakeBmg([_FakeMsg(_info(fuki_kind=9))])
    bmg_rules.mw.use_per_window_layouts = False
    bmg_rules.mw.lines_per_page = 3

    assert bmg_rules.get_string_layout(0, 0) is None
    warn, max_width = resolve_width_limits({}, bmg_rules, 0, 0, 410, 435)
    assert (warn, max_width) == (410, 435)
    assert bmg_rules.get_preview_window_style(0, 0)["lines_per_page"] == 3


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


def test_item_get_uses_four_line_text_pane():
    from plugins.zelda_bmg.window_frame_loader import _text_pane_rect
    box = (29.5, 273.5, 551.0, 117.0)
    icon = (58.0, 286.0, 100.0, 100.0)
    text = _text_pane_rect("item", box, icon)
    assert text[2] == 400.0
    assert text[3] == 95.0
    # 4 game lines in 95px; a 5th line would need ~119px.
    assert text[3] / 4 < 28
    assert text[0] >= icon[0] + icon[2]


def test_talk_text_pane_is_inset_from_window():
    from plugins.zelda_bmg.window_frame_loader import _text_pane_rect
    box = (29.5, 283.5, 551.0, 117.0)
    text = _text_pane_rect("talk", box, None)
    assert text[2] == 443.0
    assert text[3] == 114.0
    assert text[0] > box[0] + 40
    assert text[0] + text[2] < box[0] + box[2] - 40


def test_subtitles_do_not_load_talk_dump_frame():
    from plugins.zelda_bmg.window_frame_loader import screen_class_for_kind
    from plugins.zelda_bmg.window_kinds import window_style_for_kind
    assert screen_class_for_kind(1, window_style_for_kind(1)) is None
    assert screen_class_for_kind(5, window_style_for_kind(5)) is None
    assert screen_class_for_kind(2, window_style_for_kind(2)) == "wood"
    assert screen_class_for_kind(9, window_style_for_kind(9)) == "item"


def test_gx_i8_decode_writes_luma_pixels():
    from plugins.zelda_bmg.gx_texture import decode_gx
    from PyQt6.QtGui import QImage

    # One 8x4 I8 tile of 0x80.
    img = decode_gx(bytes([0x80] * 32), 8, 4, 1)
    assert img.width() == 8 and img.height() == 4
    c = img.pixelColor(0, 0)
    assert c.red() == 128 and c.alpha() == 128


def test_dump_talk_frame_loads_when_msgres_present(qapp, tmp_path):
    pytest.importorskip("PyQt6")
    from plugins.zelda_bmg.window_frame_loader import (
        find_layout_root, load_window_frame, _CACHE, _LAYOUT_ROOT,
    )
    import plugins.zelda_bmg.window_frame_loader as loader

    layout = find_layout_root()
    if layout is None:
        from pathlib import Path
        known = Path(r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\ENG\root\res\Layout")
        if not (known / "msgres01.arc").is_file():
            pytest.skip("retail Layout dump not available")
        loader._LAYOUT_ROOT = known
    loader._CACHE.pop("talk", None)
    frame = load_window_frame("talk")
    assert frame is not None
    assert not frame.image.isNull()
    assert frame.screen[0] >= 600
    assert frame.box[2] > 200 and frame.box[3] > 50
    # Fade / ornaments exist, but the talk band is not a solid bar.
    sample = 0
    img = frame.image
    for y in range(0, img.height(), 8):
        for x in range(0, img.width(), 8):
            if img.pixelColor(x, y).alpha() > 40:
                sample += 1
    assert sample > 20
    cx = int(frame.box[0] + frame.box[2] / 2)
    cy = int(frame.box[1] + frame.box[3] / 2)
    mid = img.pixelColor(max(0, min(img.width() - 1, cx)),
                         max(0, min(img.height() - 1, cy)))
    assert 20 < mid.alpha() < 250, mid.alpha()
