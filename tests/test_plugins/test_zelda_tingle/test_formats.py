"""Tingle Tuner formats: GBA LZ77, the message file and its text codes, the client's tile font."""
import random
import struct

import pytest

from core import font_formats
from core.containers import lz10
from core.font_formats import gba_tiles
from plugins.zelda_tingle import tuner

from .samples import GLYPHS, PARAMS, PROGRAM_ADDRESS, client, message_file, program


def _references(stream):
    """(length, distance) of every back reference of an LZ77 stream."""
    size, pos, done, out = int.from_bytes(stream[1:4], "little"), 4, 0, []
    while done < size:
        flags = stream[pos]
        pos += 1
        for bit in range(8):
            if done >= size:
                break
            if flags & (0x80 >> bit):
                token = stream[pos] << 8 | stream[pos + 1]
                out.append(((token >> 12) + 3, (token & 0xFFF) + 1))
                done += (token >> 12) + 3
                pos += 2
            else:
                done += 1
                pos += 1
    return out


def test_lz10_round_trip_and_vram_safety():
    rng = random.Random(5)
    data = bytes(rng.choice(b"\x11\x11\x1f\xf1\xff") for _ in range(5000)) + b"\x00" * 300 + bytes(range(256)) * 3
    for vram in (False, True):
        packed = lz10.compress(data, vram)
        assert len(packed) % 4 == 0 and lz10.decompress(packed)[0] == data
        if vram:
            assert all(distance >= 2 for _length, distance in _references(packed))
    assert len(lz10.compress(b"\x11" * 4000)) < 600
    with pytest.raises(ValueError):
        lz10.decompress(b"\x11\x00\x00\x00")
    with pytest.raises(ValueError):
        lz10.decompress(b"\x10\x10\x00\x00\x80\x00\x05")        # reference before the start


@pytest.mark.parametrize("halfwords", [False, True])
def test_message_file_round_trip_and_sharing(halfwords):
    parsed = tuner.parse(message_file(halfwords))
    assert parsed.halfword_offsets == halfwords and len(parsed.messages) == 5
    assert tuner.decode(parsed.messages[0]) == "{anim:13}{color:4}Tingle Bomb\n{color:0}For {color:2}10 Rupees{color:0}!"
    unpacked = tuner.build(parsed)
    offsets = struct.unpack_from("<5H", unpacked, 2)
    assert offsets[1] == offsets[2]                     # identical messages share their bytes
    assert len(unpacked) % 4 == 0
    if halfwords:
        assert all(unpacked[12 + 2 * o - 1] == 0xFF for o in offsets if o)


def test_message_file_limits():
    big = tuner.MessageFile([tuner.encode(f"Message {i:04} " * 4 + "abcdefghij") for i in range(1086)], True)
    with pytest.raises(ValueError, match="too long"):
        tuner.pack(big)
    assert tuner.parse(tuner.pack(big, "msg_LZ1.bin"))           # German room is bigger
    with pytest.raises(tuner.FormatError):
        tuner.parse(lz10.compress(b"\x08\x00\x10\x00\x20\x00\x30\x00"))


def test_text_codes():
    text = "{color:2}Пане Феє{color:0}, ґанок і їжак!\n{icon:1} {wait:30}{fb}{x3F}"
    raw = tuner.encode(text)
    assert raw[:2] == b"\xfc\x02" and bytes([0xFE]) in raw and raw.endswith(b"\xf9\x1e\xfb\x3f")
    assert tuner.decode(raw) == text
    assert tuner.decode(tuner.encode("Тато")) == "Тато"          # look-alikes only: no Cyrillic-only letter
    assert tuner.decode(tuner.encode("Тато ж")) == "Тато ж"
    assert tuner.decode(tuner.encode("Game Boy і ж")) == "Game Воу і ж"
    missing = set()
    assert tuner.encode("Ы", missing=missing) == b"\x59" and missing == {"Ы"}
    assert tuner.decode(bytes([0x41]), usa=False) == "{x41}"       # no Ukrainian codes in the European text
    assert tuner.line_width("{color:2}Hello{icon:3}") == 5 * 6 + 24
    assert tuner.line_width("A" * 16) == tuner.LINE_WIDTH


def test_ukrainian_codes_are_free_and_complete():
    assert set(tuner.UKRAINIAN_CODES).isdisjoint(tuner.GAME_CHARS)
    alphabet = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
    table = tuner.encoder()
    assert all(c in table and c.lower() in table for c in alphabet)
    assert set(tuner.SLOT_TILES) == {c for c in tuner.UKRAINIAN_CODES if c >= 0x68}
    assert 0x4F not in tuner.UKRAINIAN_CODES                     # the + icon draws glyph 0x4F


def test_program_strings_in_place():
    prog = bytearray(tuner.PROGRAM_SIZE)
    for address, room in tuner.PROGRAM_STRINGS:
        at = address - tuner.PROGRAM_ADDRESS
        prog[at:at + 4] = b"\x03\x1b\x26\xff"
    strings = tuner.program_strings(bytes(prog))
    assert [tuner.decode(s) for s in strings] == ["Cal", "Cal"]
    new = tuner.write_program_strings(bytes(prog), [tuner.encode("Дзвоню..."), strings[1]])
    assert tuner.decode(tuner.program_strings(new)[0]) == "Дзвоню..." and len(new) == len(prog)
    with pytest.raises(ValueError):
        tuner.write_program_strings(bytes(prog), [b"\x01" * 12, b""])
    assert tuner.program_strings(b"\x00" * 10) is None


def test_tile_font_extract_and_unedited_pack():
    data = client()
    metadata, sheets = font_formats.extract("gba_tiles", data, PARAMS)
    assert font_formats.char_map(metadata) == {"A": 1, "Б": 5}
    assert sheets[0].size == (128, 16)
    assert font_formats.pack("gba_tiles", metadata, sheets, data, PARAMS) == data
    assert font_formats.font_map(metadata)["A"]["width"] == 6


def test_tile_font_edit_writes_letters_two_tone_and_slots():
    data = client()
    metadata, sheets = font_formats.extract("gba_tiles", data, PARAMS)
    sheet = sheets[0]
    for x in range(40, 46):                       # glyph 5 (Б), a grey stroke
        sheet.putpixel((x, 3), (200, 200, 200, 160))
    out = font_formats.pack("gba_tiles", metadata, [sheet], data, PARAMS)
    prog = gba_tiles.read_program(out, PARAMS)
    tiles = lz10.decompress(prog, 0x100)[0]
    glyph5 = tiles[5 * 32:6 * 32]
    assert set(glyph5) <= {0x11, 0x1F, 0xF1, 0xFF} and glyph5[12] == 0xFF
    assert tiles[6 * 32:7 * 32] == b"\x11" * 32                  # the slot range's accent is blank
    assert prog[0x700:0x702] == bytes([0x05, 0x00])              # code 0x03 -> tile 5, no accent offset
    assert tiles[2 * 32:3 * 32] == bytes(range(32))              # the icon keeps its colours
    again, sheets2 = font_formats.extract("gba_tiles", out, PARAMS)
    assert font_formats.pack("gba_tiles", again, sheets2, out, PARAMS) == out


def test_program_growth_moves_the_tail():
    data = client()
    rng = random.Random(1)
    prog = bytearray(program())
    prog[0x200:0x600] = bytes(rng.randrange(256) for _ in range(0x400))      # no longer compresses
    out = gba_tiles.replace_program(data, bytes(prog), PARAMS)
    start, end = struct.unpack_from("<I", out, 0x190)[0] - 0x02000000, struct.unpack_from("<I", out, 0x198)[0]
    assert len(out) > len(data) and start % 4 == 0 and out[start:] == b"TAIL" * 8
    assert end - 0x02000000 == len(out)
    assert gba_tiles.read_program(out, PARAMS) == bytes(prog)
    with pytest.raises(ValueError):
        gba_tiles.replace_program(data, bytes(prog), dict(PARAMS, program_address=hex(0x02000400)))
    assert GLYPHS and PROGRAM_ADDRESS
