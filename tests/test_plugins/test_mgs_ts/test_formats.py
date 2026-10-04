"""Twin Snakes formats: text codec, GCX string tables and languages, subtitle records, the font."""
import pytest

from core import font_formats
from plugins.mgs_ts import gcx, subtitles, textcodec

from .samples import JAPANESE, LINES, codec_file, demo_container, font_file, gcx_file, subs_file

MAP = {"Б": "Å", "і": "Í", "ї": "Î", "є": "Ï", "ґ": "Ì"}


def test_codec_reads_escapes_newlines_and_raw_bytes():
    raw = b"Caf\x1f\x0f!\x80|Line\nTwo\x02"
    assert textcodec.decode(raw) == "Café!\nLine\nTwo{x02}"
    assert textcodec.newline_of(raw) == textcodec.SUB_LF
    assert textcodec.encode("Café!\nTwo{x02}", textcodec.LF) == b"Caf\x1f\x0f!\nTwo\x02"


def test_codec_maps_ukrainian_letters_to_font_slots_and_back():
    reverse = {v: k for k, v in MAP.items()}
    encoded = textcodec.encode("Біїєґ’", translation_map=MAP)
    # Å Í Î Ï Ì ’ are font codes 0x81 0xEA 0xEB 0xEC 0xED 0xD5: escape 1F + code - 0x7F
    assert encoded == b"\x1f\x02\x1f\x6b\x1f\x6c\x1f\x6d\x1f\x6e\x1f\x56"
    assert textcodec.decode(encoded, reverse) == "Біїєґ’"
    missing = set()
    assert textcodec.encode("Ж", missing=missing) == b"?" and missing == {"Ж"}


def test_languages_of_a_table_are_found_in_runs():
    section = gcx.read_sections(gcx_file())[0]
    assert section.table.langs == [lang for lang in range(6) for _ in range(3)]
    assert section.table.english == [0, 1, 2]


def test_voice_clips_settle_the_language_of_unreadable_lines():
    strings = [b"Hm.\n", b"Hm?\n", b"Hm!\n"] * 5 + [JAPANESE] * 3
    speakers = [(i, "campbell") for i in range(18)]
    data = gcx_file(strings, speakers=speakers, clips=True)
    section = gcx.read_sections(data)[0]
    assert section.table.english == [0, 1, 2]
    assert section.speakers[0] == gcx.strcode24("campbell")


def test_table_keeps_its_size_and_takes_room_from_foreign_strings():
    data = gcx_file()
    section = gcx.read_sections(data)[0]
    assert section.table.build({}) == section.table.raw
    longer = b"A much, much longer English line that needs the room of the French ones.\n" * 2
    built = section.table.build({0: longer})
    assert len(built) == section.table.size
    again = gcx.TextTable.read(built, 0)
    assert again.strings[0] == longer and again.strings[1:3] == LINES["E"][1:]
    assert again.strings[15:] == [JAPANESE] * 3                  # Japanese is never touched
    assert b"" in again.strings[3:15]                             # some foreign lines gave their room


def test_table_that_cannot_fit_raises():
    section = gcx.read_sections(gcx_file())[0]
    with pytest.raises(gcx.FormatError):
        section.table.build({0: b"x" * 5000})


def test_codec_file_sections_and_rebuild():
    data = codec_file()
    sections = gcx.read_sections(data)
    assert len(sections) == 3 and sections[0].table.raw == sections[2].table.raw
    out = gcx.rebuild(data, sections, {1: {0: b"Druhyi dzvinok.\n"}})
    assert len(out) == len(data)
    assert gcx.read_sections(out)[1].table.strings[0] == b"Druhyi dzvinok.\n"


def test_subtitle_records_round_trip_and_grow_into_padding():
    container = demo_container()
    records = subtitles.scan(container)
    assert [r.lang for r in records] == [1, 2, 7, 1, 3]
    assert records[0].entries[1].text == b"I should have known\x80|it was you."
    assert records[3].entries[0].speaker == gcx.strcode24("enemy")
    assert all(r.build([e.text for e in r.entries]) == r.raw for r in records)
    assert subtitles.read(subtitles.write(records)) == records
    raws, notes = subtitles.rebuild(records, {0: [b"Short.", b"Two."]})
    assert subtitles.Record.parse(raws[0]).entries[0].text == b"Short." and not notes


def test_subtitles_take_room_from_foreign_records_then_give_up():
    records = subtitles.scan(demo_container())
    room = records[0].slot_end - records[0].data_end
    length = room
    while len(records[0].build([b"x" * length, b""])) - records[0].original_size <= room:
        length += 4                                     # just too long for the padding alone
    raws, notes = subtitles.rebuild(records, {0: [b"x" * length, b""]})
    assert notes and subtitles.Record.parse(raws[1]).entries[0].text == b""
    with pytest.raises(subtitles.FormatError):
        subtitles.rebuild(records, {0: [b"x" * (room + 2000), b""]})


def test_subs_file_carries_its_kind():
    assert subtitles.kind_of(subs_file("voice")) == "voice"
    with pytest.raises(subtitles.FormatError):
        subtitles.kind_of(b"not subs")


PARAMS = {"height": 6, "first_code": 0x20, "upper_codepage": "mac_roman", "columns": 4}


def test_font_round_trips_and_widths_change_the_layout():
    data = font_file()
    metadata, sheets = font_formats.extract("mgs", data, PARAMS)
    assert [p["width"] for p in metadata["WID1"][0]["packets"]] == [4, 5, 7]
    assert font_formats.pack("mgs", metadata, sheets, data, PARAMS) == data
    metadata["WID1"][0]["packets"][1]["width"] = 9
    grown = font_formats.pack("mgs", metadata, sheets, data, PARAMS)
    again, _sheets = font_formats.extract("mgs", grown, PARAMS)
    assert [p["width"] for p in again["WID1"][0]["packets"]] == [4, 9, 7]
    assert grown[-2:] == b"\0\0" and grown[8 + 4 * 2 + 2:8 + 4 * 2 + 4] == data[8 + 4 * 2 + 2:8 + 4 * 2 + 4]


def test_font_rejects_other_files():
    with pytest.raises(ValueError):
        font_formats.extract("mgs", b"\x00\x20\xaf\x30" + bytes(12), PARAMS)
