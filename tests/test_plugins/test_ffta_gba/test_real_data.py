"""Final Fantasy Tactics Advance (GBA, USA) on the owner's ROM (skipped without it): every table reads, every
editable string reads back byte for byte, an unchanged build is the same ROM, the font packs back unchanged, and an
edited event string is reached through the moved table."""
import struct

import romhacking_root
from core import font_formats
from plugins.ffta_gba import rom_text, rules

ROM = ("Final Fantasy", "Tactics Advance", "GBA", "source", "Final Fantasy Tactics Advance.gba")
pytestmark = romhacking_root.needs(ROM)


def _rom() -> bytes:
    return romhacking_root.path(*ROM).read_bytes()


def test_text_reads_and_builds_back_unchanged():
    data = _rom()
    banks = rom_text.extract(data)
    count = sum(len(block["strings"]) for bank in banks.values() for block in bank["blocks"])
    assert count >= 9500
    for bank in banks.values():
        for block in bank["blocks"]:
            for string in block["strings"]:
                raw = bytes.fromhex(string["raw"])
                text = rom_text.tbl_text(raw) if block["kind"] == "offsets" else rom_text.abs_text(raw)
                assert isinstance(text, str)
    assert rom_text.build(data, banks.values()) == data


def test_font_packs_back_unchanged():
    data = _rom()
    font = data[rom_text.FONT_START:rom_text.FONT_END]
    params = rules.font_descriptors()[0]["params"]
    metadata, sheets = font_formats.extract("cells", font, params)
    assert font_formats.char_map(metadata)["A"] == 0xB0
    assert font_formats.pack("cells", metadata, sheets, font, params) == font


def test_edited_event_string_is_reached_through_the_event_tree():
    data = _rom()
    banks = rom_text.extract(data)
    block = next(b for b in banks["events"]["blocks"] if b["id"] == "9C1580")
    first = block["strings"][0]
    new = rom_text.tbl_encode("UA TEST[clear]", bytes.fromhex(first["raw"]))
    first["raw"] = new.hex()
    out = rom_text.build(data, banks.values())
    entry = rom_text.EVENT_BASE + 4                       # event entry 1 is table 9C1580
    table = rom_text.EVENT_BASE + struct.unpack_from("<I", out, entry)[0]
    assert table >= len(data)
    offset = rom_text.table_entries(out, table)[0]
    assert rom_text.tbl_text(rom_text.string_slices(out, table)[offset]) == "UA TEST[clear]"
