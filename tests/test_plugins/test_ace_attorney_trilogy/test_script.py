"""Ace Attorney Trilogy (3DS): the script codec, the BCH texture backend and the real game files (skipped without them)."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import texture_formats
from plugins.ace_attorney_trilogy import gsscript

CODE = {c: k for k, c in gsscript.CHARS.items()}


def _words(text):
    return gsscript.encode(text)


def _script(sections):
    """A script file of ``n`` = len(sections) + 2 table words (the last two are flags)."""
    n = len(sections) + 2
    header = 4 + 4 * n
    blobs = [struct.pack(f"<{len(s)}H", *s) for s in sections]
    offsets, pos = [], header
    for blob in blobs:
        offsets.append(pos)
        pos += len(blob)
    return struct.pack(f"<{n + 1}I", n, *offsets, 0x540002, 0x700002) + b"".join(blobs)


def test_codec_round_trips_text_and_tags():
    text = "Wright!\nOh, {wait:20}hiya.{page}Chief {x1a0}"
    assert gsscript.decode(_words(text)) == text


def test_script_finds_messages_between_commands_and_rebuilds():
    # [command 0x30 (no args), "Hi", newline, "there", page, "Ok", command 0x1e + 3 args, "Bye"]
    section = [0x30, *_words("Hi"), 1, *_words("there"), 2, *_words("Ok"), 0x1E, 0x7, 0xEC, 0xED, *_words("Bye")]
    raw = _script([section, [0x30, *_words("Second")]])
    script = gsscript.Script(raw)
    assert script.texts() == ["Hi\nthere{page}Ok", "Bye", "Second"]
    assert script.rebuild(script.texts()) == raw
    longer = script.rebuild(["Hello\nthere everyone{page}Ok", "Bye", "Second"])
    again = gsscript.Script(longer)
    assert again.texts() == ["Hello\nthere everyone{page}Ok", "Bye", "Second"]
    assert len(longer) > len(raw)
    # the second section moved: its offset in the table follows the longer first section
    assert struct.unpack_from("<I", longer, 8)[0] > struct.unpack_from("<I", raw, 8)[0]


def test_arguments_above_0x80_are_not_text():
    section = [0x1E, 0xC, 0xEC, 0xED, *_words("A")]
    assert gsscript.Script(_script([section])).texts() == ["A"]


def _bch(width, height, fmt, payload):
    """A one-texture BCH: header, empty contents, GPU commands for texture unit 0, then the data block."""
    gpu = struct.pack("<8I", (width << 16) | height, 0x000F0082, 0, 0x000F0085, fmt, 0x000F008E, 0, 0)
    contents, strings = 0x3C, 0x3C
    gpu_at = 0x40
    data_at = gpu_at + len(gpu)
    head = (b"BCH\0" + bytes([0x20, 0x20]) + struct.pack("<H", 0xA046)
            + struct.pack("<5I", contents, strings, gpu_at, data_at, data_at + len(payload))
            + struct.pack("<5I", 4, 0, len(gpu), len(payload), 0))
    return head.ljust(gpu_at, b"\0") + gpu + payload


def test_bch_textures_read_and_write_back():
    payload = bytes(range(256)) * 4         # 16x16 RGBA8 is 1024 bytes
    raw = _bch(16, 16, 0, payload)
    assert texture_formats.detect(raw) == "bch"
    (texture,) = texture_formats.read("bch", raw)
    assert texture.image.size == (16, 16) and texture.pixel_format == "RGBA8"
    assert texture_formats.write("bch", raw, {0: texture.image}) == raw
    image = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    changed = texture_formats.write("bch", raw, {0: image})
    assert changed != raw and len(changed) == len(raw)
    assert texture_formats.read("bch", changed)[0].image.getpixel((3, 3)) == (255, 0, 0, 255)


ROOT = Path(r"E:\Emulators\RomHacking\Ace Attorney\Trilogy\3DS\source")


@pytest.mark.skipif(not (ROOT / "script").is_dir(), reason="the game is not unpacked")
def test_every_real_script_round_trips_byte_for_byte():
    files = sorted((ROOT / "script").glob("s*.bin"))
    assert len(files) == 37
    total = 0
    for path in files:
        raw = path.read_bytes()
        script = gsscript.Script(raw)
        texts = script.texts()
        total += len(texts)
        assert script.rebuild(texts) == raw
    assert total > 20000


@pytest.mark.skipif(not (ROOT / "texture").is_dir(), reason="the game is not unpacked")
def test_real_pictures_open_and_round_trip():
    for path in sorted((ROOT / "texture").glob("*.bch"))[:40]:
        raw = path.read_bytes()
        textures = texture_formats.read("bch", raw)
        assert textures
        assert texture_formats.write("bch", raw, {i: t.image for i, t in enumerate(textures)}) == raw


def test_switch_codes_are_detected_and_round_trip():
    # "Hi, a." in the Switch font codes (H 0xFFA8, i 0xFFC9, comma, space, a, full stop)
    section = [0x30, 0xFFA8, 0xFFC9, 0xFF8C, 0x3080, 0xFFC1, 0xFF8E]
    raw = _script([section])
    script = gsscript.Script(raw)
    assert script.chars is gsscript.SWITCH_CHARS
    assert script.texts() == ["Hi, a."]
    assert script.rebuild(["Hi, ok."]) == _script([[0x30, 0xFFA8, 0xFFC9, 0xFF8C, 0x3080, 0xFFCF, 0xFFCB, 0xFF8E]])


SWITCH = Path(r"E:\Emulators\RomHacking\Ace Attorney\Trilogy\Switch\source\romfs\Data\StreamingAssets")


@pytest.mark.skipif(not SWITCH.is_dir(), reason="the Switch game is not unpacked")
def test_every_real_switch_script_round_trips():
    files = sorted(SWITCH.rglob("*_u.mdt"))
    assert len(files) == 106
    total = 0
    for path in files:
        raw = path.read_bytes()
        script = gsscript.Script(raw)
        total += len(script.texts())
        assert script.rebuild(script.texts()) == raw
    assert total > 100000
