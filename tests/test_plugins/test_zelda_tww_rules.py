"""The Wind Waker GameCube plugin: tag catalogue, INF1 attributes, layout and a byte-exact BMG round trip."""
import struct

import pytest

from plugins.zelda_bmg.bmg_tool import BMGFile
from plugins.zelda_tww.rules import (
    ITEM_GET_WIDTH,
    TALK_WARN_WIDTH,
    TALK_WIDTH,
    GameRules,
    decode_ww_attributes,
)
from plugins.zelda_tww.tag_catalog import WW_CATALOG


def _info(msg_id, textbox_type=0, lines=4, price=0):
    """The 20 INF1 bytes of a Wind Waker entry after its DAT1 offset."""
    return (struct.pack(">HhHH", msg_id, price, 0, 0x60)
            + bytes([textbox_type, 0, 0, 0xFF, 0, 0, 0, 0, 0, 0, lines, 0]))


def _pad(data: bytearray) -> bytearray:
    while len(data) % 32:
        data.append(0)
    return data


def _ww_bmg(entries):
    """A retail-shaped zel_00.bmg: INF1 + DAT1 only, cp1252, 0x18-byte entries.

    ``entries`` is a list of (info, text bytes or None); None points the entry at
    DAT1 offset 0, the shared null the retail files use for empty messages.
    """
    dat = bytearray(b"\0")
    inf = bytearray(16)
    for info, text in entries:
        if text is None:
            offset = 0
        else:
            offset = len(dat)
            dat += text + b"\0"
        inf += struct.pack(">I", offset) + info
    _pad(inf)
    struct.pack_into(">4sIHHI", inf, 0, b"INF1", len(inf), len(entries), 0x18, 0)
    dat1 = _pad(bytearray(8) + dat)
    struct.pack_into(">4sI", dat1, 0, b"DAT1", len(dat1))
    body = bytes(inf + dat1)
    header = struct.pack(">8sIIB3I", b"MESGbmg1", 0x20 + len(body), 2, 1, 0, 0, 0).ljust(0x20, b"\0")
    return header + body


SAMPLE = _ww_bmg([
    (_info(1), None),
    (_info(2000), b"Hello, \x1a\x05\x00\x00\x00! Press \x1a\x05\x00\x00\x0a."),
    (_info(2001), b"\x1a\x06\xff\x00\x00\x01Red\x1a\x06\xff\x00\x00\x00 text\x1a\x07\x00\x00\x07\x00\x1e"),
    (_info(101, textbox_type=9, lines=4), b"You got the \x1a\x06\xff\x00\x00\x01Telescope\x1a\x06\xff\x00\x00\x00!"),
    (_info(2002), b"\x1a\x05\x01\x00\x02Ahh\x1a\x05\x02\x00\x15!\x1a\x05\x03\x00\x05"),
])


@pytest.fixture
def rules():
    game = GameRules()
    blocks, _ = game.load_data_from_json_obj(SAMPLE)
    game.loaded_texts = blocks[0]
    return game


class TestCatalogue:
    @pytest.mark.parametrize("raw, alias", [
        ("{escape:0:0000}", "{F:Link}"),
        ("{escape:0:000a}", "{GC:A}"),
        ("{escape:0:0013}", "{GC:stick}"),
        ("{escape:0:0014}", "{icon:arrow-left}"),
        ("{escape:0:0007001e}", "{wait:30f}"),
        ("{escape:0:00040078}", "{autoclose-noskip:120f}"),
        ("{escape:255:000003}", "{color:blue}"),
        ("{escape:255:00010096}", "{scale:150%}"),
        ("{escape:1:0002}", "{sound:2}"),
        ("{escape:2:0015}", "{camera:21}"),
        ("{escape:3:0005}", "{anim:5}"),
        ("{escape:0:0021}", "{value:vase-payment}"),
    ])
    def test_every_kind_of_tag_reads_as_a_named_alias(self, raw, alias, rules):
        assert WW_CATALOG.editor_alias(raw) == alias
        assert rules.convert_editor_text_to_data(rules.get_text_representation_for_editor(raw)) == raw

    def test_all_75_control_codes_are_known(self):
        assert all((0, code) in WW_CATALOG.tags for code in range(0x4B))

    def test_descriptions_carry_the_argument(self):
        assert WW_CATALOG.describe(0, "0007001e") == "WAIT: Pause typing for a frame count — 30 frames"
        assert "color index 1" in WW_CATALOG.describe(255, "000001")

    def test_icons_are_one_font_size_wide_and_controls_none(self):
        widths = WW_CATALOG.fixed_widths()
        assert widths["{GC:A}"]["width"] == 24
        assert widths["{ctrl:instant-on}"]["width"] == 0
        assert "{escape:0:0007}" not in widths  # WAIT carries an argument

    def test_the_icon_textures_ship_with_the_plugin(self):
        from pathlib import Path
        assert all(Path(spec["texture"]).is_file() for spec in WW_CATALOG.icon_specs.values())

    def test_the_shipped_font_map_matches_the_catalogue(self):
        import json
        from pathlib import Path
        shipped = json.loads((Path("plugins") / "zelda_tww" / "font_map.json").read_text(encoding="utf-8"))
        assert shipped == WW_CATALOG.fixed_widths()


class TestMessages:
    def test_a_retail_shaped_file_saves_back_byte_for_byte(self, rules):
        assert rules.save_data_to_json_obj([rules.loaded_texts], {}) == SAMPLE

    def test_an_edited_file_stays_a_two_section_file(self, rules):
        texts = list(rules.loaded_texts)
        texts[1] = "Hi, {escape:0:0000}!"
        out = BMGFile()
        out.load(rules.save_data_to_json_obj([texts], {}))
        assert out.section_order == ["INF1", "DAT1"]
        assert out.messages[0].shares_null and out.messages[1].parts == ["Hi, ", out.messages[1].parts[1], "!"]

    def test_inf1_attributes_are_decoded(self, rules):
        attrs = rules.get_message_attributes(0, 3)
        assert attrs["message_id"] == 101 and attrs["textbox_type"] == 9 and attrs["lines_per_page"] == 4
        assert decode_ww_attributes(b"\0" * 19) is None

    def test_an_item_get_box_is_narrower_than_a_talk_box(self, rules):
        assert rules.get_string_layout(0, 1) == {"max_width": TALK_WIDTH, "warn_width": TALK_WARN_WIDTH,
                                                 "lines_per_page": 4}
        assert rules.get_string_layout(0, 3)["max_width"] == ITEM_GET_WIDTH

    def test_the_box_kind_reaches_the_preview_and_the_translator(self, rules):
        assert rules.get_preview_window_style(0, 3) == {"kind_name": "Item get", "lines_per_page": 4}
        assert rules.get_translation_context_for_string(0, 1) == {"window_type": "Talk"}

    def test_the_preview_uses_the_wind_waker_colors_and_icons(self, rules):
        text, colors, _scales, icons = rules.prepare_preview_glyph_text(rules.loaded_texts[2])
        assert text.startswith("Red text")
        assert colors[0] == "#ff6400" and colors[4] is None
        clean, _, _, icons = rules.prepare_preview_glyph_text(rules.loaded_texts[1])
        assert clean == "Hello, Link! Press ￼."
        assert icons[len("Hello, Link! Press ")]["width"] == 24

    def test_sound_camera_and_animation_tags_take_no_width(self, rules):
        assert rules.calculate_string_width_override(rules.loaded_texts[4], {}) == \
            rules.calculate_string_width_override("Ahh!", {})

    def test_the_language_model_sees_link(self, rules):
        assert rules.replace_runtime_names_for_ai("Hi, {escape:0:0000}.") == "Hi, Link."

    def test_item_get_windows_seed_the_glossary(self, rules):
        class Store:
            data = [rules.loaded_texts]

        class Window:
            data_store = Store()

        rules.mw = Window()
        seeds = rules.get_glossary_seed_entries()
        assert [(s["term"], s["section"]) for s in seeds] == [("Telescope", "Items")]
