"""Lunar: Silver Star Story Complete plugin: codec, scripts, name tables, font and TIM pictures.

The real-data tests read the workspace's ``source`` folder (1_unpack.bat) and skip when it is missing.
"""
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from plugins.lunar_sssc import codec, doc, script, strings
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "lunar_sssc"
SOURCE = Path(r"E:\Emulators\RomHacking\Lunar\Silver Star Story\source")
needs_data = pytest.mark.skipif(not (SOURCE / "SLUS_006.28").is_file(), reason="Lunar SSSC not unpacked here")
TEXT_FONT = {"offset": "0xA197C", "count": 91, "chars": "".join(chr(c) for c in range(0x20, 0x7B))}


def _message(text: str) -> bytes:
    raw = b"\x02\x00" + codec.Encoder().message(text)
    return raw + bytes(len(raw) & 1)


def sample_script() -> bytes:
    """Labels 1-3: a message, an instruction with a 4-aligned argument (op 28), a choice, a return."""
    code = bytearray(_message("Hello, Alex!\nThe White Dragon{page}{FA:39}Bye."))
    code += b"\x1c\x00\x00\x00" if (0x800 + len(code)) % 4 == 0 else b"\x1c\x00\x00\x00\x00\x00"
    code += struct.pack("<I", 200)
    choice_at = len(code)
    choice = b"\x07\x00\x03\x00\x00\x00" + codec.Encoder().string("Yes") + codec.Encoder().string("No")
    code += choice + bytes(len(choice) & 1)
    end_at = len(code)
    code += b"\x05\x00"
    labels = [0] * script.LABELS
    labels[1], labels[2], labels[3] = 0x400, (0x800 + choice_at) // 2, (0x800 + end_at) // 2
    return struct.pack(f"<{script.LABELS}H", *labels) + bytes(code)


def sample_tables() -> bytes:
    """Fourteen tables, two strings, then 8 bytes of data at a fixed place."""
    offsets = [0] * (strings.TABLES * strings.SLOTS)
    first = codec.Encoder().string("Herb")
    second = codec.Encoder().string("{FC:03}Burg{FC:00}")
    offsets[0], offsets[strings.SLOTS + 5] = strings.HEADER, strings.HEADER + len(first)
    body = first + second
    body += bytes(-len(body) % 4)
    return struct.pack(f"<{len(offsets)}H", *offsets) + body + b"DATADATA"


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_a_script_survives_load_and_save():
    check_round_trip(PLUGIN, sample_script())
    blocks, _ = doc.read(sample_script())
    assert blocks == [["Hello, Alex!\nThe White Dragon{page}{FA:39}Bye.", "Yes", "No"]]


def test_a_longer_message_moves_the_code_and_the_labels():
    data = sample_script()
    blocks, _ = doc.read(data)
    blocks[0][0] = "A much longer line of text than before{wait}\nand a second one."
    blocks[0][2] = "Nope"
    out = doc.write(data, blocks, set())
    assert doc.read(out)[0] == blocks
    old_labels, new_labels = script.labels(data), script.labels(out)
    shift = len(out) - len(data)
    assert shift % 4 == 0 and shift > 0
    assert new_labels[3] * 2 == old_labels[3] * 2 + shift
    assert out[new_labels[3] * 2:new_labels[3] * 2 + 2] == b"\x05\x00"
    texts = script.parse(out)
    assert out[texts[1].start:texts[1].start + 2] == b"\x07\x00"


def test_an_unchanged_file_is_rebuilt_byte_for_byte():
    data = sample_script()
    assert doc.write(data, doc.read(data)[0], set()) == data
    tables = sample_tables()
    assert doc.write(tables, doc.read(tables)[0], set()) == tables


def test_name_tables_keep_the_data_behind_them():
    data = sample_tables()
    blocks, names = doc.read(data)
    assert names == {"0": "Party names", "1": "Monsters"}
    blocks[0][0] = "Leaf"
    out = doc.write(data, blocks, set())
    assert out.endswith(b"DATADATA") and len(out) == len(data)
    assert doc.read(out)[0][0] == ["Leaf"]
    blocks[0][0] = "A name far too long for the room"
    with pytest.raises(ValueError):
        doc.write(data, blocks, set())


def test_the_codec_uses_dictionary_words_and_marks_missing_characters():
    encoder = codec.Encoder()
    plain = encoder.message("the the the")
    assert len(plain) < len("the the the") + 2
    assert codec.decode_message(plain, 0, len(plain)) == "the the the"
    encoder.message("Привіт")
    assert encoder.missing == set("Привіт")
    ended = encoder.message("Ow{end}")
    assert ended.endswith(b"\xff") and codec.decode_message(ended, 0, len(ended)) == "Ow{end}"


def test_tim_pictures_read_and_write_back():
    clut = struct.pack("<16H", 0, 0x7FFF, 0x001F, *range(3, 16))
    pixels = bytes([0x21, 0x10] * 8)
    data = (b"\x10\0\0\0" + struct.pack("<I", 8) + struct.pack("<IHHHH", 12 + 32, 0, 0, 16, 1) + clut
            + struct.pack("<IHHHH", 12 + len(pixels), 0, 0, 2, 4) + pixels)
    texture = texture_formats.read("tim", data)[0]
    assert texture.image.size == (8, 4) and texture.pixel_format == "PSX 4-bit"
    assert texture_formats.write("tim", data, {0: texture.image}) == data
    image = texture.image.copy()
    image.putpixel((0, 0), (255, 0, 0, 255))
    out = texture_formats.write("tim", data, {0: image})
    assert texture_formats.read("tim", out)[0].image.getpixel((0, 0)) == (255, 0, 0, 255)


def test_the_glyph_table_font_packs_back():
    data = bytes(64) + bytes(range(32)) * 2 + bytes(32)
    params = {"offset": 64, "count": 3, "chars": "ABC"}
    metadata, sheets = font_formats.extract("lunar", data, params)
    assert font_formats.pack("lunar", metadata, sheets, data, params) == data
    ImageDraw.Draw(sheets[0]).rectangle((32, 0, 47, 15), fill=(255, 255, 255, 255))
    out = font_formats.pack("lunar", metadata, sheets, data, params)
    assert out[64 + 64:64 + 96] == b"\xff" * 32 and out[:128] == data[:128]


# ---------------------------------------------------------------- real data

@needs_data
def test_every_script_and_table_rebuilds_byte_for_byte_and_takes_edits():
    rules = load_rules(PLUGIN)
    files = sorted((SOURCE / "LUNADATA").glob("TEXT*.DAT")) + [SOURCE / "LUNADATA" / "SYSTEM.DAT" / "00_0001.bin"]
    total = 0
    for path in files:
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        total += sum(map(len, blocks))
        assert rules.save_data_to_json_obj(blocks, names) == data, path.name
        if path.suffix == ".DAT":
            edited = [[(s.replace("{end}", "") + " UA TEST" + ("{end}" if s.endswith("{end}") else "")) if i % 4 == 0
                       else s for i, s in enumerate(block)] for block in blocks]
            assert doc.read(doc.write(data, edited, set()))[0] == edited, path.name
    assert total > 9000


@needs_data
def test_the_game_font_and_pictures_round_trip():
    exe = (SOURCE / "SLUS_006.28").read_bytes()
    for params in (TEXT_FONT, {"offset": "0x9FB5C", "count": 241}):
        metadata, sheets = font_formats.extract("lunar", exe, params)
        assert font_formats.pack("lunar", metadata, sheets, exe, params) == exe
    pictures = sorted((SOURCE / "LUNADATA").glob("*/*.tim"))
    assert len(pictures) == 15
    for path in pictures:
        data = path.read_bytes()
        image = texture_formats.read("tim", data)[0].image
        assert texture_formats.write("tim", data, {0: image}) == data, path.name
        assert isinstance(image, Image.Image)
