"""Vagrant Story text: codec, string tables, scripts, files edited in place, program strings, the font."""
import struct

import pytest

from core import font_formats
from core.font_formats import vagrant as vsfont
from plugins.vagrant_story import codec, formats, program
from plugins.vagrant_story import doc as docs

from .samples import area_file, event_file, help_file, item_names, program_file, room_file, table


def test_codec_reads_letters_tags_and_both_spaces():
    data = bytes((0xFB, 0x68, 0xFA, 0x0C, 0x0D, 0x32, 0x31, 0x96, 0x37, 0xFA, 0x06, 0x1C, 0x8F, 0x90, codec.NEWLINE,
                  0xF8, 0x00, 0xB6, 0x03, 0xE6, 0xFA, 0xFC, 0x99, 0x77))
    assert codec.decode(data) == "{down 13}{>12}Don't S !\n{speed 0}{Lv}3{wait}{<4}=Ð"
    assert codec.encode(codec.decode(data)) == data.replace(b"\xfa\x06", b"\x8f")


@pytest.mark.parametrize("text", ["{color 1}Iron Key{color 0}", "{center}YES", "{italic}x{regular}", "{num 2} HP",
                                  "{str 0}'s", "{xE9}{xEC:B8}", "a｛b｝", "{page}"])
def test_codec_round_trips_every_tag(text):
    assert codec.decode(codec.encode(text)) == text


def test_unknown_tag_and_missing_letters():
    with pytest.raises(ValueError):
        codec.encode("{nonsense}")
    missing = set()
    assert codec.encode("Ж", missing=missing) == bytes((codec.CODES["?"],)) and missing == {"Ж"}
    assert codec.encode("Ж", {"Ж": 0x44}) == b"\x44"


def test_reader_makes_lookalike_words_cyrillic_only_in_ukrainian_lines():
    reader = codec.Reader({0x46: "И", 0x5E: "и", 0x64: "н"}, {"B": "В", "i": "і", "C": "С", "a": "а", "H": "Н",
                                                             "P": "Р"})
    ukrainian = codec.encode("Bë знaйшли Ciдні? a HP", {"ë": 0x5E, "з": 0x5D, "й": 0x5F, "ш": 0x3E, "л": 0x61,
                                                        "д": 0x59, "н": 0x64, "і": 0x24 + 8})
    assert reader(ukrainian).startswith("Ви")
    assert reader(ukrainian).endswith(" а HP")              # a capital abbreviation stays Latin
    assert reader(codec.encode("Base camp")) == "Base camp"  # no Ukrainian letter: English as it is


def test_table_rebuilds_inside_its_region_and_shares_equal_strings():
    data = bytearray(table(["Yes", "No", "Yes"]) + bytes(8))
    parsed = formats.read_table(bytes(data), 0)
    assert parsed.count == 3 and [codec.decode(s[:-1]) for s in parsed.strings(bytes(data))] == ["Yes", "No", "Yes"]
    parsed.region_end = len(data)
    formats.write_table(data, parsed, [codec.encode(t) + b"\xe7" for t in ("Так", "Ні", "Так")], "t")
    again = formats.read_table(bytes(data), 0, min_letters=0)
    assert again.offsets[0] == again.offsets[2]
    with pytest.raises(formats.FormatError, match="more bytes"):
        formats.write_table(data, parsed, [codec.encode("x" * 40) + b"\xe7"] * 3, "t")


def test_event_round_trips_and_grows_into_its_zero_tail():
    data = event_file(["Don't move, Sydney!", "I've a bowgun\naimed at your heart!"], boxes=((13, 3), (14, 4)))
    parsed = docs.parse(data, "EVENT/0004.EVT")
    assert parsed.kind == "event" and parsed.names == {"0": "Event dialog"}
    lines = parsed.groups[0].lines
    assert [line.box.chars_per_line for line in lines] == [13, 14] and lines[1].box.line_count == 4
    texts = parsed.texts()
    assert docs.build(data, parsed, texts) == data
    texts[0][0] = "Ні з місця, Сідні! " * 3
    out = docs.build(data, parsed, texts, {c: 0x40 for c in "НізмсцСдн"})
    assert len(out) == formats.EVENT_SIZE
    sec_len, text, block1, block2 = struct.unpack_from("<4H", out, 0)
    assert block1 > struct.unpack_from("<H", data, 4)[0] and (block1 - text) % 2 == 0
    assert out[block1:block1 + 8] == b"\x11" * 8 and out[block2:block2 + 4] == b"\x22" * 4
    assert docs.parse(out).texts()[0][1] == texts[0][1]


def test_event_that_cannot_hold_the_text_raises():
    data = event_file(["Hi."])
    parsed = docs.parse(data)
    with pytest.raises(formats.FormatError):
        docs.build(data, parsed, [["x" * 7000]])


def test_room_grows_its_script_and_moves_the_sections_after_it():
    data = room_file(["Have you found Sydney?", "Not yet, sir."])
    parsed = docs.parse(data, "MAP/MAP001.MPD")
    assert parsed.kind == "room"
    texts = parsed.texts()
    assert docs.build(data, parsed, texts) == data
    texts[0][1] = "Ще ні, сер." * 10
    out = docs.build(data, parsed, texts, {c: 0x41 for c in "Щеінср"})
    old, new = formats.mpd_header(data), formats.mpd_header(out)
    grow = new[2][1] - old[2][1]
    assert grow > 0 and len(out) == len(data) + grow
    assert [o for o, _l in new[3:]] == [o + grow for o, _l in old[3:]]
    assert out[new[3][0]:new[3][0] + 12] == b"\x0d" * 12
    assert docs.parse(out).texts()[0][0] == texts[0][0]
    with pytest.raises(formats.FormatError, match="file can hold"):
        docs.build(data, parsed, [[texts[0][0], "x" * 3000]])


def test_fixed_fields_take_shorter_and_refuse_longer_names():
    data = item_names(["Battle Knife", "Dirk"])
    parsed = docs.parse(data)
    assert parsed.kind == "items" and parsed.texts() == [["Battle Knife", "Dirk"]]
    out = docs.build(data, parsed, [["Бойовий ніж", "Dirk"]], {c: 0x42 for c in "Бойвижн"})
    assert len(out) == len(data) and out[48:] == data[48:]
    with pytest.raises(formats.FormatError, match="needs 25 bytes"):
        docs.build(data, parsed, [["x" * 24, "Dirk"]])


def test_help_page_area_map_and_plain_table():
    help_data = help_file(["BASIC CONTROLS", "Press the {color 1}○{color 0} button."])
    parsed = docs.parse(help_data)
    assert parsed.kind == "help" and parsed.texts()[0][1] == "Press the {color 1}○{color 0} button."
    assert docs.build(help_data, parsed, [["ОСНОВИ", parsed.texts()[0][1]]], {c: 0x43 for c in "ОСНВИ"}) != help_data
    area = area_file([(9, 1, "Entrance to Darkness"), (9, 2, "Room of Cheap Red Wine")])
    parsed = docs.parse(area)
    assert parsed.kind == "areas" and parsed.texts() == [["{speed 0}{center}{regular}Entrance to Darkness",
                                                          "{speed 0}{center}{regular}Room of Cheap Red Wine"]]


def test_program_strings_are_found_by_shape_and_edited_in_place():
    data = program_file(["Fireball", "Heal Panel", "x7q"], ["SIMPLE MAP", "Select options for the map.", "YES"])
    parsed = docs.parse(data)
    assert parsed.kind == "program"
    assert parsed.names == {"0": f"Table {parsed.groups[0].table.start:#06x}", "1": "Strings"}
    assert parsed.texts()[1] == ["Fireball", "Heal Panel"]
    known = {}
    docs.remember(data, parsed, known)
    out = docs.build(data, parsed, [parsed.texts()[0], ["Вогонь", "Heal Panel"]], {c: 0x44 for c in "Вогнь"})
    assert len(out) == len(data)
    # the translation copy has no English left where the name was: it is read with the source's layout
    again = docs.parse(out, known=known)
    assert again.groups[1].lines[0].place == parsed.groups[1].lines[0].place


@pytest.mark.parametrize("text, english", [("Recover 50 HP", True), ("Müllenkamp Soldier", True), ("STR-down", True),
                                           ("jfjef8f7b", False), ("ùöööö", False), ("q+", False), ("rpppoß", False)])
def test_program_text_test(text, english):
    assert program.looks_like_text(text) is english


def test_program_names_lose_the_record_data_glued_in_front():
    blob = bytes(8) + codec.encode("X10Bloodsuck") + b"\xe7" + bytes(8)
    assert [(o, n) for o, n in program.scan(blob)] == [(11, 10)]


def test_japanese_leftovers_are_not_shown():
    assert codec.is_japanese(bytes((0xF7, 0x27, 0xEC, 0xB8)))
    data = event_file(["Hello there.", "￿"])
    parsed = docs.parse(data.replace(codec.encode("?") + b"\xe7", b"\xf7\x27\xe7", 1))
    assert len(parsed.groups[0].lines) == 1


def font_bytes():
    texture = bytearray(vsfont.TEXTURE)
    for y in range(2, 11):                      # an 'A'-ish block in cell 0x0A of both sets
        for half in (0, 108):
            texture[(half + y) * 128 + (0x0A % 21) * 6] = 0xFF
    widths = bytes([6] * 189 + [7] * 189)
    return vsfont.build(bytes(texture), widths)


def test_font_sets_round_trip_and_keep_the_other_set():
    data = font_bytes()
    assert font_formats.detect(data) == "vagrant"
    for which in (0, 1):
        metadata, sheets = font_formats.extract("vagrant", data, {"set": which})
        assert sheets[0].size == (252, 108)
        assert font_formats.char_map(metadata)["A"] == 0x0A and font_formats.char_map(metadata)["Å"] == 0x6B
        assert font_formats.pack("vagrant", metadata, sheets, data, {"set": which}) == data
    metadata, sheets = font_formats.extract("vagrant", data, {"set": 1})
    metadata["WID1"][0]["packets"][0x44]["width"] = 9
    sheets[0].paste((0, 0, 0, 0), (0, 0, 252, 108))
    out = font_formats.pack("vagrant", metadata, sheets, data, {"set": 1})
    assert out[16 + vsfont.TEXTURE + 189 + 0x44] == 9 and out[16 + vsfont.TEXTURE + 0x44] == 6
    assert out[16:16 + 108 * 128] == data[16:16 + 108 * 128]           # the regular set is untouched
    with pytest.raises(ValueError):
        font_formats.extract("vagrant", b"VSFN" + bytes(12), {})


def test_hud_words_are_ascii_edited_in_place():
    data = bytearray(64) + b"#WEAPON" + bytes(1) + b"$TOO   FAST!" + bytes(4) + b"UCDDD4DU" + bytes(32)
    data[:4] = bytes((0x27, 0xBD, 0xFF, 0xE8))
    parsed = docs.parse(bytes(data))
    hud = [group for group in parsed.groups if group.name == "HUD words (ASCII)"][0]
    assert [line.raw for line in hud.lines] == [b"#WEAPON", b"$TOO   FAST!"]
    index = parsed.groups.index(hud)
    texts = parsed.texts()
    assert docs.build(bytes(data), parsed, texts) == bytes(data)
    texts[index][0] = "#ARM"
    out = docs.build(bytes(data), parsed, texts)
    assert out[64:72] == b"#ARM" + bytes(4)
    texts[index][0] = "#ЗБРОЯ"
    with pytest.raises(formats.FormatError, match="ASCII only"):
        docs.build(bytes(data), parsed, texts)
