"""Tests for the Twilight Princess (dusklight) text layout port in BfnCore
and the zelda_bmg preview color-tag processing."""
import struct
import pytest

from core.bfn_core import BfnCore


def _build_bfn(ascent=20, descent=4, def_width=12, leading=26,
               cell_w=24, cell_h=24, widths=None):
    """Build a minimal synthetic BFN binary.

    MAP1 type 0 maps char codes 32..42 linearly to glyph indices 0..10.
    `widths` is a list of (kerning, width) pairs for glyph indices 0..N-1.
    """
    if widths is None:
        widths = [(0, 10)] * 10

    header = struct.pack('>8sII', b'FFNT1bnd', 0, 4) + b'\x00' * 16

    inf1 = (struct.pack('>4sI', b'INF1', 32)
            + struct.pack('>HHHHHH', 1, ascent, descent, def_width, leading, 0)
            + struct.pack('>I', 0) + b'\x00' * 8)

    gly1 = (struct.pack('>4sI', b'GLY1', 32)
            + struct.pack('>HHHHIHHHHH', 0, 10, cell_w, cell_h, 0, 0, 5, 5, 120, 120)
            + b'\x00' * 2)

    map1 = (struct.pack('>4sI', b'MAP1', 32)
            + struct.pack('>HHHH', 0, 32, 42, 0) + b'\x00' * 16)

    wid_body = struct.pack('>HH', 0, len(widths))
    for kerning, width in widths:
        wid_body += bytes([kerning & 0xFF, width])
    pad = (-len(wid_body) - 8) % 32
    wid1 = struct.pack('>4sI', b'WID1', 8 + len(wid_body) + pad) + wid_body + b'\x00' * pad

    bfn = BfnCore()
    bfn.load(header + inf1 + gly1 + map1 + wid1)
    return bfn


def test_space_advance_uses_wid1_width():
    # space (code 32) -> glyph 0, '!' (33) -> glyph 1
    bfn = _build_bfn(widths=[(0, 6), (0, 20)] + [(0, 10)] * 8)
    glyphs, total_w, _ = bfn.layout_text("! !", line_spacing=0)

    # space is a real glyph with WID1 width, not a hardcoded half-cell
    assert [g["char"] for g in glyphs] == ["!", " ", "!"]
    xs = [g["draw_x"] for g in glyphs]
    assert xs[1] - xs[0] == 20   # advance of '!'
    assert xs[2] - xs[1] == 6    # advance of space from WID1
    assert total_w == 20 + 6 + 20


def test_kerning_shifts_draw_position_but_not_advance():
    # glyph 1 ('!') has kerning 3
    bfn = _build_bfn(widths=[(0, 6), (3, 20)] + [(0, 10)] * 8)
    glyphs, _, _ = bfn.layout_text("!!", line_spacing=0)

    # first glyph starts at pad(15) shifted left by kerning
    assert glyphs[0]["draw_x"] == 15 - 3
    # advance between characters is the WID1 width, kerning does not accumulate
    assert glyphs[1]["draw_x"] - glyphs[0]["draw_x"] == 20


def test_line_advance_uses_leading_plus_spacing_and_baseline():
    bfn = _build_bfn(ascent=20, descent=4, leading=26)
    glyphs, _, total_h = bfn.layout_text("!\n!", line_spacing=10)

    # both glyphs drawn at baseline - ascent; baseline step = leading + spacing
    assert glyphs[1]["draw_y"] - glyphs[0]["draw_y"] == 26 + 10
    assert total_h > 0


def test_char_spacing_added_to_advance():
    bfn = _build_bfn(widths=[(0, 6), (0, 20)] + [(0, 10)] * 8)
    glyphs, _, _ = bfn.layout_text("!!", line_spacing=0, char_spacing=4)
    assert glyphs[1]["draw_x"] - glyphs[0]["draw_x"] == 24


def test_colors_alignment_across_newlines():
    bfn = _build_bfn(widths=[(0, 6), (0, 20)] + [(0, 10)] * 8)
    text = "!\n!"
    colors = ["#f07878", None, "#aadc8c"]
    glyphs, _, _ = bfn.layout_text(text, colors=colors)
    assert glyphs[0]["color"] == "#f07878"
    assert glyphs[1]["color"] == "#aadc8c"


def test_unmapped_char_advances_default_width():
    bfn = _build_bfn(def_width=12)
    glyphs, total_w, _ = bfn.layout_text("Я", line_spacing=0)  # not in 32..42 map
    assert len(glyphs) == 1
    assert glyphs[0]["is_fallback"] is True
    assert total_w == 12


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


def test_zelda_bmg_preview_color_tags(bmg_rules):
    text = "Hi {COLOR_RED}Wolf{COLOR_DEFAULT} ok"
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text(text)
    assert clean == "Hi Wolf ok"
    assert colors is not None
    assert colors[:3] == [None, None, None]
    # "Wolf" is red (TP color table index 1: #f07878)
    assert colors[3:7] == ["#f07878"] * 4
    assert colors[7:] == [None, None, None]


def test_zelda_bmg_preview_lowercase_color_tags(bmg_rules):
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text("{color:yellow}Rupee")
    assert clean == "Rupee"
    assert colors == ["#dcdc82"] * 5


def test_zelda_bmg_preview_dynamic_names_substituted(bmg_rules):
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text("Hey {PLAYER} and {escape:0:0022}!")
    assert clean == "Hey Link and Epona!"
    assert colors is None


def test_zelda_bmg_preview_unknown_tags_stripped(bmg_rules):
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text("A{escape:1:02}B")
    assert clean == "AB"
    assert colors is None


def test_zelda_bmg_preview_raw_escape_color_tags(bmg_rules):
    # raw BMG form as stored in data: {escape:255:0000XX}
    text = "Go {escape:255:000003}north{escape:255:000000} now"
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text(text)
    assert clean == "Go north now"
    assert colors[3:8] == ["#a0b4dc"] * 5  # blue (index 3)
    assert colors[8:] == [None] * 4


def test_zelda_bmg_preview_escape_color_index7_is_white(bmg_rules):
    # game color table index 7 is white, not gray (getFontCCColorTable)
    clean, colors, _, _ = bmg_rules.prepare_preview_glyph_text("{escape:255:000007}Hi")
    assert clean == "Hi"
    assert colors is None


def test_zelda_bmg_preview_scale_tags_raw_and_friendly(bmg_rules):
    # MSGTAG_SCALE raw form: u16 percent (0x0096 = 150%)
    clean, _, scales, _ = bmg_rules.prepare_preview_glyph_text("A{escape:255:00010096}B")
    assert clean == "AB"
    assert scales == [1.0, 1.5]

    clean, _, scales, _ = bmg_rules.prepare_preview_glyph_text("A{scale:50}B")
    assert clean == "AB"
    assert scales == [1.0, 0.5]


def test_zelda_bmg_preview_scale_resets_on_newline(bmg_rules):
    # game rule: enlarged text (scale > 1.0) reverts to 1.0 at end of line
    clean, _, scales, _ = bmg_rules.prepare_preview_glyph_text("{scale:150}A\nB")
    assert clean == "A\nB"
    assert scales == [1.5, 1.5, 1.0]

    # but shrunk text (< 1.0) persists across lines
    clean, _, scales, _ = bmg_rules.prepare_preview_glyph_text("{scale:50}A\nB")
    assert scales == [0.5, 0.5, 0.5]


def test_zelda_bmg_preview_icon_tags(bmg_rules):
    # {escape:0:000a} = MSGTAG_ABTN -> inline icon placeholder + drawing spec
    clean, _, _, icons = bmg_rules.prepare_preview_glyph_text("Press {escape:0:000a} now")
    assert clean == "Press ￼ now"
    assert icons is not None and 6 in icons
    spec = icons[6]
    assert spec["kind"] == "circle"
    assert spec["label"] == "A"
    assert spec["width"] == 24  # game do_outfont icon size


def test_zelda_bmg_preview_icon_via_alias(bmg_rules):
    # aliases resolve through mw.default_tag_mappings before parsing
    bmg_rules.mw.default_tag_mappings = {"{(A)}": "{escape:0:000a}"}
    clean, _, _, icons = bmg_rules.prepare_preview_glyph_text("{(A)}!")
    assert clean == "￼!"
    assert icons and icons[0]["label"] == "A"


def test_layout_icon_advance_is_game_24px():
    bfn = _build_bfn(widths=[(0, 6), (0, 20)] + [(0, 10)] * 8)
    icons = {1: {"kind": "circle", "label": "A", "color": "#62a32e", "width": 24}}
    glyphs, total_w, _ = bfn.layout_text("!￼!", line_spacing=0, icons=icons)
    assert glyphs[1].get("icon") and glyphs[1]["icon"]["label"] == "A"
    # icon advances the cursor by its 24px width
    assert glyphs[2]["draw_x"] - glyphs[1]["draw_x"] == 24
    assert total_w == 20 + 24 + 20


def test_layout_scale_affects_advance_and_size():
    bfn = _build_bfn(widths=[(0, 6), (0, 20)] + [(0, 10)] * 8)
    glyphs, total_w, _ = bfn.layout_text("!!", line_spacing=0, scales=[1.5, 1.0])
    # first glyph advance is scaled (20 * 1.5 = 30), second is normal
    assert glyphs[1]["draw_x"] - glyphs[0]["draw_x"] == 30
    assert glyphs[0]["scale"] == 1.5
    assert glyphs[1]["scale"] == 1.0
    assert total_w == 30 + 20
    # scaled glyph is vertically centered on the normal line box
    assert glyphs[0]["draw_y"] < glyphs[1]["draw_y"]


def test_zelda_bmg_aliases_json_matches_game_tag_table():
    import json
    from pathlib import Path
    from plugins.zelda_bmg.rules import TP_COLOR_TABLE, _ESCAPE_COLOR_RE

    aliases_path = Path("plugins") / "zelda_bmg" / "aliases.json"
    with open(aliases_path, encoding="utf-8") as f:
        aliases = json.load(f)

    import re
    escape_re = re.compile(r'\{escape:\d+:[0-9a-fA-F]+\}')
    for alias, tag in aliases.items():
        assert escape_re.fullmatch(tag), f"Bad escape value for {alias}: {tag}"

    # every color alias must decode to a valid index of the game color table
    for alias, tag in aliases.items():
        if alias.startswith("{color:"):
            m = _ESCAPE_COLOR_RE.fullmatch(tag)
            assert m, f"Color alias {alias} has non-color escape {tag}"
            assert int(m.group(1), 16) in TP_COLOR_TABLE

    # spot-check verified mappings from dusklight d_msg_class.h (MSGTAG_*)
    assert aliases["{(A)}"] == "{escape:0:000a}"       # MSGTAG_ABTN = 10
    assert aliases["{(B)}"] == "{escape:0:000b}"       # MSGTAG_BBTN = 11
    assert aliases["{(DUP)}"] == "{escape:3:0009}"     # MSGTAG_WII_DPAD_UP = 9
    assert aliases["{*}"] == "{escape:6:000a}"         # MSGTAG_BULLET = 10
    assert aliases["{timer}"].startswith("{escape:5:0000")  # MSGTAG_TIME_INFO = 0


def _make_renderable_bfn():
    """BfnCore with ASCII map and an opaque white sheet, ready for painting."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import Qt

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


def test_preview_widget_renders_color_tags_end_to_end(qapp):
    """Full pipeline: zelda_bmg rules -> layout -> paint. Red segment must be red."""
    from unittest.mock import MagicMock
    from ui.components.bfn_preview_widget import BfnPreviewWidget
    from plugins.zelda_bmg.rules import GameRules

    mw = MagicMock()
    mw.active_game_plugin = "zelda_bmg"
    mw.current_game_rules = GameRules(_MockMW())
    mw.data_store.current_block_idx = -1
    mw.data_store.current_string_idx = -1
    mw.default_font_file = None
    mw.all_bfn_fonts = {"tp.bfn": _make_renderable_bfn()}
    mw.project_manager = None
    # concrete visual settings (avoid MagicMock leaking into QColor/QRect)
    mw.preview_bg_image_path = ""
    mw.preview_bg_scale = 100
    mw.preview_bg_offset_x = 0
    mw.preview_bg_offset_y = 0
    mw.preview_bg_hidden = False
    mw.preview_line_spacing = 10
    mw.preview_text_rect = [15, 15, 300, 120]
    mw.preview_text_color = "#ffffff"
    mw.preview_shadow_enabled = False
    mw.preview_glow_enabled = False
    mw.preview_fix_font_scale = False
    mw.preview_fixed_font_scale = 1.0
    mw.preview_char_spacing = 0

    widget = BfnPreviewWidget(mw)
    widget.resize(400, 200)
    widget.text = "AB {color:red}CD{color:white} EF"
    widget.show()
    try:
        image = widget.grab().toImage()
    finally:
        widget.hide()

    # verify the plugin hook produced colored spans
    clean, colors, _, _ = widget._prepare_render_text()
    assert clean == "AB CD EF"
    assert colors[3:5] == ["#f07878"] * 2

    # With the game window style active, text is modulated by TEV white
    # (200,200,200), so red is ~(188,94,94) and "white" is ~(200,200,200).
    red_pixels = 0
    white_pixels = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.alpha() < 200:
                continue
            r, g, b = c.red(), c.green(), c.blue()
            if r > 150 and (r - g) > 60 and abs(g - b) < 25:
                red_pixels += 1
            elif r > 180 and abs(r - g) < 15 and abs(g - b) < 15:
                white_pixels += 1

    assert red_pixels > 20, "colored segment was not rendered in TP red"
    assert white_pixels > 20, "default-colored glyphs missing"


def test_zelda_bmg_window_style_matches_game_sources(bmg_rules):
    style = bmg_rules.get_preview_window_style()
    # shadow: black +2,+2 (TP shadow pane / COutFont icon shadows)
    assert style["shadow"]["dx"] == 2.0 and style["shadow"]["dy"] == 2.0
    assert style["shadow"]["color"] == "#000000"
    # halo: golden moya light, TEV white (225,210,110) alpha 160 for the talk box
    assert style["halo"]["color"] == "#e1d26e"
    assert style["halo"]["alpha"] == 160
    # main text modulated by TEV white (200,200,200)
    assert abs(style["text_brightness"] - 200 / 255) < 1e-6
    # text offset inside the box: HIO mTextPosX = 4.5
    assert style["text_offset"] == (4.5, 0.0)
    assert isinstance(style["frame"], dict)


def test_zelda_bmg_font_map_covers_icon_aliases():
    import json
    from pathlib import Path

    plugin_dir = Path("plugins") / "zelda_bmg"
    with open(plugin_dir / "aliases.json", encoding="utf-8") as f:
        aliases = json.load(f)
    with open(plugin_dir / "font_map.json", encoding="utf-8") as f:
        font_map = json.load(f)

    # every icon-style alias (buttons etc. rendered via do_outfont) has a width;
    # group-6 marks ({(male)}, {(female)}, {(star)}, {(※)}) are font glyphs
    # inserted as text (push_word), so they take their width from the font itself
    text_glyph_aliases = {"{(male)}", "{(female)}", "{(star)}", "{(※)}"}
    icon_aliases = [a for a in aliases if a.startswith("{(") and a not in text_glyph_aliases]
    missing = [a for a in icon_aliases if a not in font_map]
    assert not missing, f"Icon aliases without width in font_map.json: {missing}"


def test_tp_escape_catalog_covers_every_documented_tag():
    from plugins.zelda_bmg.tag_catalog import ESCAPE_TAGS

    assert {code for (group, code) in ESCAPE_TAGS if group == 0} == set(range(0x40))
    assert {code for (group, code) in ESCAPE_TAGS if group == 3} == set(range(0x15))
    assert {code for (group, code) in ESCAPE_TAGS if group == 4} == set(range(0x0E))
    assert {code for (group, code) in ESCAPE_TAGS if group == 5} == {
        0x00, 0x03, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
    }
    assert {code for (group, code) in ESCAPE_TAGS if group == 6} == set(range(0x0C))
    assert {code for (group, code) in ESCAPE_TAGS if group == 255} == {0, 1, 2}


def test_tp_preview_renders_literal_and_runtime_value_tags(bmg_rules):
    clean, colors, scales, icons = bmg_rules.prepare_preview_glyph_text(
        "Cost {escape:4:0000}{escape:5:0009}"
    )

    assert clean == "Cost $⟨Rupees remaining⟩"
    assert colors is None
    assert scales is None
    assert icons is None


def test_tp_preview_understands_controls_and_genitive_names(bmg_rules):
    clean, _, _, _ = bmg_rules.prepare_preview_glyph_text(
        "{escape:0:0001}{escape:6:0000} horse is {escape:6:0001}."
    )

    assert clean == "Link's horse is Epona's."


def test_tp_preview_uses_controller_icons_for_wii_tags(bmg_rules):
    clean, _, _, icons = bmg_rules.prepare_preview_glyph_text(
        "{escape:3:000e}{escape:3:0010}{escape:3:0013}"
    )

    assert clean == "\ufffc\ufffc\ufffc"
    assert [icons[index]["kind"] for index in range(3)] == [
        "wiimote", "nunchuk", "nunchuk_button",
    ]
    assert all(icons[index]["width"] == 24 for index in range(3))


def test_tp_escape_descriptions_decode_arguments(bmg_rules):
    assert "45 frames" in bmg_rules.get_escape_tag_description("{escape:0:0007002d}")
    assert "150%" in bmg_rules.get_escape_tag_description("{escape:255:00010096}")


def test_tp_every_controller_icon_spec_can_be_drawn(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPainter
    from plugins.zelda_bmg.tag_catalog import ESCAPE_ICON_SPECS
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    for spec in ESCAPE_ICON_SPECS.values():
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            BfnPreviewWidget._draw_icon(painter, spec, 4, 4, 24)
        finally:
            painter.end()

        if spec["kind"] != "blank":
            assert any(
                image.pixelColor(x, y).alpha() > 0
                for y in range(image.height())
                for x in range(image.width())
            ), spec


def test_tp_width_measurement_uses_semantic_tag_output(bmg_rules):
    font_map = {"A": {"width": 9}, "L": {"width": 7}, "i": {"width": 3},
                "n": {"width": 6}, "k": {"width": 6}}

    assert bmg_rules.calculate_string_width_override("{escape:0:000a}", font_map) == 24
    assert bmg_rules.calculate_string_width_override("{escape:0:0001}", font_map) == 0
    assert bmg_rules.calculate_string_width_override("{escape:0:0000}", font_map) == 22
