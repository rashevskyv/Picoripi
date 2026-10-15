"""Final Fantasy Tactics Advance (GBA) ROM text on a synthetic ROM: unpack lists the strings, an unchanged build gives
the same bytes, an edited pointer-table string and an edited offset-table string are written after the ROM's end
with their pointers moved, and the plugin's project hooks (identify, unpack, load, save, build) work together."""
import json
import struct

import pytest

from plugins.ffta_gba import rom_text, rules

SB_AT, DB_AT = 0x600000, 0x600010
CODE_TABLE, CODE_LITERAL, LONE_TABLE = 0x497418, 0x1000, 0x4B83A0


def make_rom() -> bytes:
    rom = bytearray(rom_text.EVENT_BASE + 0x100)
    rom[0xAC:0xB0] = b"AFXE"
    rom[SB_AT:SB_AT + 4] = bytes((1, 0xBD, 0xD3, 0))                       # "Mi", single-byte
    rom[DB_AT:DB_AT + 5] = bytes.fromhex("80b080b100")                       # "AB"
    struct.pack_into("<3I", rom, 0x5567F0, 0x08000000 + SB_AT, 0x08000000 + DB_AT, 0x08000000 + SB_AT)
    plain = bytes.fromhex("2000" "80b0406300")                               # window 2, "A[clear]"
    body = bytes.fromhex("80b180b2406300" "00")                              # "BC[clear]", padded
    packed = bytes.fromhex("2218") + struct.pack(">I", len(body)) + bytes((0x40 | len(body) - 1,)) + body
    table = struct.pack("<3H", 6, 6 + len(plain) + 1, 0xFFFF) + plain + b"\0" + packed
    rom[CODE_TABLE:CODE_TABLE + len(table)] = table
    struct.pack_into("<I", rom, CODE_LITERAL, 0x08000000 + CODE_TABLE)
    lone = struct.pack("<H", 2) + bytes.fromhex("1000" "80b000")
    rom[LONE_TABLE:LONE_TABLE + len(lone)] = lone
    rom[rom_text.FONT_START:rom_text.FONT_END] = bytes(range(256)) * ((rom_text.FONT_END - rom_text.FONT_START) // 256) \
        + bytes((rom_text.FONT_END - rom_text.FONT_START) % 256)
    return bytes(rom)


@pytest.fixture(scope="module")
def rom() -> bytes:
    return make_rom()


@pytest.fixture(scope="module")
def banks(rom):
    return rom_text.extract(rom)


def strings_of(banks, block_id):
    block = next(b for bank in banks.values() for b in bank["blocks"] if b["id"] == block_id)
    return {s["id"]: bytes.fromhex(s["raw"]) for s in block["strings"]}


def edited(banks, sid, raw):
    out = json.loads(json.dumps(list(banks.values())))
    for bank in out:
        for block in bank["blocks"]:
            for string in block["strings"]:
                if string["id"] == sid:
                    string["raw"] = raw.hex()
    return out


def test_extract_lists_each_string_once(banks):
    assert set(strings_of(banks, "5567F0")) == {"5567F0-0", "5567F0-1"}           # entry 2 shares entry 0
    table = strings_of(banks, "497418")
    assert rom_text.tbl_text(table["497418-0"]) == "A[clear]"
    assert rom_text.tbl_text(table["497418-1"]) == "BC[clear]"                       # LZSS, read through


def test_unchanged_build_is_byte_for_byte(rom, banks):
    assert rom_text.build(rom, banks.values()) == rom


def test_edited_pointer_string_moves_with_every_pointer_to_it(rom, banks):
    raw = rom_text.abs_encode("Мі", strings_of(banks, "5567F0")["5567F0-0"])
    assert raw[0] == 1                                                             # stays single-byte
    out = rom_text.build(rom, edited(banks, "5567F0-0", raw))
    first, second, third = struct.unpack_from("<3I", out, 0x5567F0)
    assert first == third and first - 0x08000000 >= len(rom) and second == 0x08000000 + DB_AT
    at = first - 0x08000000
    assert out[at:at + len(raw)] == raw and out[SB_AT:SB_AT + 4] == rom[SB_AT:SB_AT + 4]


def test_edited_table_string_moves_the_table_and_its_pointer(rom, banks):
    raw = rom_text.tbl_encode("Привіт[clear]", strings_of(banks, "497418")["497418-1"])
    assert struct.unpack_from("<H", raw)[0] == 0x1820                              # LZSS bit off, window kept
    out = rom_text.build(rom, edited(banks, "497418-1", raw))
    table = struct.unpack_from("<I", out, CODE_LITERAL)[0] - 0x08000000
    assert table >= len(rom) and table % 4 == 0
    offsets = rom_text.table_entries(out, table)
    assert offsets[2] == 0xFFFF and all(o % 2 == 0 for o in offsets[:2])
    slices = rom_text.string_slices(out, table)
    assert rom_text.tbl_text(slices[offsets[1]]) == "Привіт[clear]"
    assert rom_text.tbl_text(slices[offsets[0]]) == "A[clear]"
    assert out[CODE_TABLE:CODE_TABLE + 32] == rom[CODE_TABLE:CODE_TABLE + 32]      # the old table stays


def test_table_without_pointers_is_refused(rom, banks):
    raw = rom_text.tbl_encode("B", strings_of(banks, "4B83A0")["4B83A0-0"])
    with pytest.raises(rom_text.BuildError, match="4B83A0"):
        rom_text.build(rom, edited(banks, "4B83A0-0", raw))


def test_font_is_written_and_a_wrong_size_refused(rom, banks):
    font = bytes(rom_text.FONT_END - rom_text.FONT_START)
    assert rom_text.build(rom, banks.values(), font)[rom_text.FONT_START:rom_text.FONT_END] == font
    with pytest.raises(rom_text.BuildError):
        rom_text.build(rom, banks.values(), b"short")


def test_plugin_unpacks_edits_and_builds(tmp_path, rom):
    source_rom = tmp_path / "game.gba"
    source_rom.write_bytes(rom)
    game = rules.GameRules()
    assert game.identify_source(str(source_rom)) == {"role": "base", "platform": "gba"}
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    game.unpack_sources({"base": str(source_rom)}, str(unpacked), lambda *_: None, lambda: False)
    assert (unpacked / "fonts" / "font.bin").read_bytes() == rom[rom_text.FONT_START:rom_text.FONT_END]
    bank = json.loads((unpacked / "text" / "system.fftatext").read_text(encoding="utf-8"))
    blocks, names = game.load_data_from_json_obj(bank)
    assert blocks[0] == ["Mi", "AB"] and names["0"] == "Menus, commands and abilities"
    with pytest.raises(ValueError, match="'Ы'"):
        game.save_data_to_json_obj([["Ы", "AB"]] + blocks[1:], names)
    saved = game.save_data_to_json_obj([["Mi", "Тест"]] + blocks[1:], names)
    assert saved["blocks"][0]["strings"][0]["raw"] == bank["blocks"][0]["strings"][0]["raw"]   # untouched
    translation = tmp_path / "translation" / "text"
    translation.mkdir(parents=True)
    (translation / "system.fftatext").write_text(json.dumps(saved), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    path = game.build_target("gba_rom", str(unpacked), str(tmp_path / "translation"), str(out),
                             lambda *_: None, lambda: False)
    built = (out / rules.OUTPUT_NAME).read_bytes()
    assert path == str(out / rules.OUTPUT_NAME) and len(built) > len(rom)
    at = struct.unpack_from("<I", built, 0x5567F0 + 4)[0] - 0x08000000
    assert rom_text.abs_text(built[at:at + 9]) == "Тест"
