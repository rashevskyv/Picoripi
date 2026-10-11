"""Code of Princess: the executable string pool, the FD font and RTEX picture formats (real files skip when missing)."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from plugins.code_of_princess import pool


def _u16(text):
    return text.encode("utf-16le") + b"\0\0"


def _fake_code():
    """A program with 25 strings back to back (one NUL between them) after binary junk."""
    texts = [f"Message number {i} of the game.\x08" for i in range(25)]
    body = b"".join(_u16(t) for t in texts)
    return b"\x12\x34\x56\x78" * 8 + b"\0\0\0\0" + body + b"\x01\x02\x03\x04" * 4, texts


def test_pool_finds_strings_and_rebuilds_identically():
    raw, texts = _fake_code()
    found = pool.Pool(raw)
    assert [s for block in found.texts() for s in block] == [t.replace("\x08", "{x08}") for t in texts]
    assert found.rebuild(found.texts()) == raw


def test_shorter_text_is_padded_and_longer_is_refused():
    raw, _ = _fake_code()
    found = pool.Pool(raw)
    blocks = found.texts()
    blocks[0][3] = "UA TEST{x08}"
    out = pool.Pool(found.rebuild(blocks))
    assert out.texts()[0][3] == "UA TEST{x08}" and len(out.items) == len(found.items)
    assert len(found.rebuild(blocks)) == len(raw)
    blocks[0][4] = "x" * 80
    with pytest.raises(pool.PoolError):
        found.rebuild(blocks)


def test_identifiers_and_paths_are_not_text():
    assert not pool.is_text("/chara/boy.rani")
    assert not pool.is_text("HIME_100")
    assert not pool.is_text("JobTerminateFacade::InitiateTeardown")
    assert not pool.is_text("NotificationEventManager")
    assert pool.is_text("Speed")
    assert pool.is_text("Press the X Button to Burst")


def test_fd_font_has_a_grid_of_glyphs_and_cyrillic_edit_writes_back():
    # header + 2 codes + 2 records of 8 bytes + a 1024 x 8 ETC1A4 texture stored as 8 x 1024 (one byte per pixel)
    count = 2
    head = b"FD1\x8a" + struct.pack("<IIII", 0, 0, 0x20, 0) + struct.pack("<6H", count, 8, 8, 9, 95, 0)
    head += struct.pack("<I", 0) * 2
    head = head[:0x20]
    codes = struct.pack("<2H", 0x41, 0x42).ljust(0x20, b"\0")
    recs = struct.pack("<2f", 0.0, 0.0) + struct.pack("<2f", 0.0, 9 / 1024)
    raw = bytearray(head + codes + recs + b"\xff" * 8192)
    struct.pack_into("<I", raw, 0xC, 0x20)
    metadata, sheets = font_formats.extract("cop_fnt", bytes(raw))
    assert sheets[0].size == (2 * 8, 9)
    assert font_formats.pack("cop_fnt", metadata, sheets, bytes(raw)) == bytes(raw)


def _rtex(width, height, fmt, payload):
    head = b"RTEX" + struct.pack("<I", 0) + struct.pack("<4H", width, height, width, height)
    head += struct.pack("<IIHHII", 0x20, len(payload), fmt, 0x10, width * 2, 0)
    return head + payload


def test_rtex_reads_and_writes_back():
    raw = _rtex(8, 8, 13, bytes(range(128)))
    (texture,) = texture_formats.read("rtex", raw)
    assert texture.image.size == (8, 8) and texture.pixel_format == "RGBA4"
    assert texture_formats.write("rtex", raw, {0: texture.image}) == raw
    marked = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    changed = texture_formats.write("rtex", raw, {0: marked})
    assert changed != raw and len(changed) == len(raw)


ROOT = Path(r"E:\Emulators\RomHacking\Code of Princess\3DS\source")


@pytest.mark.skipif(not (ROOT / "exefs" / "code.bin").is_file(), reason="the game is not unpacked")
def test_real_executable_text_round_trips():
    raw = (ROOT / "exefs" / "code.bin").read_bytes()
    found = pool.Pool(raw)
    assert sum(len(b) for b in found.texts()) > 1500
    assert found.rebuild(found.texts()) == raw


@pytest.mark.skipif(not (ROOT / "romfs" / "_spec_en" / "font" / "script12.fnt").is_file(), reason="the game is not unpacked")
def test_real_fonts_and_pictures_round_trip():
    for name in ("sys.fnt", "script12.fnt"):
        raw = (ROOT / "romfs" / "_spec_en" / "font" / name).read_bytes()
        assert font_formats.detect(raw) == "cop_fnt"
        metadata, sheets = font_formats.extract("cop_fnt", raw)
        assert font_formats.pack("cop_fnt", metadata, sheets, raw) == raw
    files = sorted((ROOT / "romfs" / "_spec_en" / "rtex").rglob("*.rtx"))
    assert len(files) == 233
    for path in files[:30]:
        raw = path.read_bytes()
        (texture,) = texture_formats.read("rtex", raw)
        assert texture_formats.write("rtex", raw, {0: texture.image}) == raw
