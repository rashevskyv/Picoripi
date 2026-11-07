"""Ocarina of Time (Switch 2): the tag catalogue of its UTF-8 text, and page breaks in the editor."""
from plugins.common.msbt import Tag
from plugins.zelda_oot_switch2 import tags
from plugins.zelda_oot_switch2.rules import GameRules


def test_the_game_tags_read_by_name_and_encode_back_to_the_same_bytes():
    cases = {
        Tag(4, 0, b"\x05\x00Think\x00"): "{voice:Think:0}",
        Tag(3, 0, b"\x0f\x01\x00"): "{emotion:15:1:0}",
        Tag(2, 12, b"\x10\x00SimpleShop_Price\xff\xff"): "{value12:SimpleShop_Price:-1}",
        Tag(2, 1, b"\x05\x00Price\xff\xff\x01"): "{value1:Price:-1:1}",
    }
    for tag, text in cases.items():
        assert tags.to_editor([tag], True, True) == text
        assert tags.from_editor(text, True, True) == [tag]


def test_text_saved_with_the_old_names_or_raw_tags_still_reads():
    tag = Tag(2, 12, b"\x10\x00SimpleShop_Price\xff\xff")
    assert tags.from_editor("{string12:SimpleShop_Price:-1}", True, True) == [tag]
    assert tags.from_editor("{tag:4:0:05005468696e6b00}", True, True) == [Tag(4, 0, b"\x05\x00Think\x00")]


def test_a_page_break_ends_its_editor_line_and_the_data_keeps_no_line_break():
    rules = GameRules()
    data = "Hello.{pageBreak}Next page\nsecond line"
    shown = rules.get_text_representation_for_editor(data)
    assert shown == "Hello.{pageBreak}\nNext page\nsecond line"
    assert rules.convert_editor_text_to_data(shown) == data
    assert rules.get_shift_enter_char() == "{pageBreak}\n"
