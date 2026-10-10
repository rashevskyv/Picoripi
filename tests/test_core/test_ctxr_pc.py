"""PC .ctxr ("TXTR" version 7) pictures: synthetic files, no game data needed."""
import struct

from core.texture_formats import ctxr


def _txtr(width: int, height: int, fmt: int, payload: bytes, mips: int = 1) -> bytes:
    head = bytearray(0x80)
    struct.pack_into(">I", head, 0, 0x54585452)          # "TXTR"
    struct.pack_into(">I", head, 4, 7)                   # version
    struct.pack_into(">HH", head, 8, width, height)
    struct.pack_into(">H", head, 16, fmt)
    head[0x26] = mips
    body = struct.pack(">I", len(payload)) + payload
    return bytes(head[:0x80]) + body


def test_detect_and_read_bgra_top_level():
    width, height = 4, 4
    pixels = bytes((x * 13 + y * 7) % 256 for x in range(width) for y in range(height) for _ in range(4))
    data = _txtr(width, height, 0x0, pixels)
    assert ctxr.detect_pc(data)
    texture = ctxr.read(data, {})[0]
    assert texture.pixel_format == "BGRA8"
    assert texture.image.size == (width, height)


def test_unchanged_image_writes_the_same_bytes():
    width, height = 8, 8
    payload = bytes(range(256)) * ((width * height * 4) // 256)
    data = _txtr(width, height, 0x0, payload)
    image = ctxr.read(data, {})[0].image
    assert ctxr.write(data, {0: image}, {}) == data


def test_one_edited_pixel_changes_only_its_bytes():
    width, height = 8, 8
    payload = bytes([128]) * (width * height * 4)
    data = _txtr(width, height, 0x0, payload)
    image = ctxr.read(data, {})[0].image.convert("RGBA")
    image.putpixel((2, 3), (255, 0, 0, 255))
    out = ctxr.write(data, {0: image}, {})
    assert len(out) == len(data)
    changed = [i for i in range(len(data)) if out[i] != data[i]]
    assert changed, "the edit must reach the file"
    assert all(0x84 <= i < 0x84 + len(payload) for i in changed)
