"""Jak and Daxter level texture file (.fr3): a synthetic payload round trip (RGBA and BC1 records) and, when the
port's extracted levels are on this machine, a real-data no-op write and one changed texture."""
import os
import struct
from pathlib import Path

import pytest
from PIL import Image

from core.texture_formats import fr3

# A scratch build output (PICORIPI_SCRATCH), not the RomHacking workspace.
REAL = Path(os.environ.get("PICORIPI_SCRATCH", "scratch"), "ready-jak", "jak-project-switch", "out", "jak2", "fr3",
            "atoll.fr3")


def _str(text: str) -> bytes:
    raw = text.encode("latin-1")
    return struct.pack("<Q", len(raw)) + raw


def _record(w: int, h: int, name: str, fmt: int, words: bytes, bcn: bytes, mips: list) -> bytes:
    return (struct.pack("<HHI", w, h, 7) + struct.pack("<Q", len(words) // 4) + words + _str(name) + _str("common")
            + bytes([1, fmt]) + struct.pack("<Q", len(bcn)) + bcn + struct.pack("<Q", len(mips))
            + struct.pack(f"<{len(mips)}I", *mips))


def _file(payload: bytes) -> bytes:
    from compression import zstd
    return struct.pack("<Q", len(payload)) + zstd.compress(payload, level=1)


def _synthetic() -> bytes:
    rgba = bytes(v for _ in range(4) for v in (10, 20, 30, 255))          # 2x2 RGBA, one word per pixel
    bc1_block = bytes(8)                                                   # one 4x4 block, black
    payload = (struct.pack("<H", 44) + _str("synthetic") + struct.pack("<Q", 2)
               + _record(2, 2, "solid", 0, rgba, b"", [])
               + _record(4, 4, "black", 1, bc1_block, bc1_block, [0]))
    return _file(payload + b"tail-kept-as-is")


def test_synthetic_file_reads_both_formats():
    textures = fr3.read(_synthetic(), {})
    assert [t.name for t in textures] == ["solid", "black"]
    assert textures[0].pixel_format == "RGBA8" and textures[0].image.getpixel((1, 1)) == (10, 20, 30, 255)
    assert textures[1].pixel_format == "BC1" and textures[1].image.size == (4, 4)


def test_no_op_write_returns_the_same_bytes():
    data = _synthetic()
    textures = fr3.read(data, {})
    assert fr3.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data


def test_changed_rgba_texture_reads_back_and_keeps_the_others():
    data = _synthetic()
    textures = fr3.read(data, {})
    red = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    again = fr3.read(fr3.write(data, {0: red}, {}), {})
    assert again[0].image.tobytes() == red.tobytes()
    assert again[1].image.tobytes() == textures[1].image.tobytes()


def _record_v43(w: int, h: int, name: str, words: bytes) -> bytes:
    return (struct.pack("<HHI", w, h, 7) + struct.pack("<Q", len(words) // 4) + words + _str(name)
            + _str("common") + bytes([1]))


def _synthetic_v43() -> bytes:
    solid = bytes(v for _ in range(4) for v in (10, 20, 30, 255))            # 2x2 RGBA
    dot = bytes((200, 100, 50, 255))                                          # 1x1 RGBA
    payload = (struct.pack("<H", 43) + _str("synthetic") + struct.pack("<Q", 2)
               + _record_v43(2, 2, "solid", solid) + _record_v43(1, 1, "dot", dot))
    return _file(payload + b"level-data-kept-as-is")


def test_v43_file_reads_rgba_records():
    textures = fr3.read(_synthetic_v43(), {})
    assert [t.name for t in textures] == ["solid", "dot"]
    assert textures[0].pixel_format == "RGBA8" and textures[0].image.getpixel((1, 1)) == (10, 20, 30, 255)
    assert textures[1].image.getpixel((0, 0)) == (200, 100, 50, 255)


def test_v43_no_op_write_returns_the_same_bytes():
    data = _synthetic_v43()
    textures = fr3.read(data, {})
    assert fr3.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data


def test_v43_changed_texture_reads_back_and_keeps_the_other():
    data = _synthetic_v43()
    textures = fr3.read(data, {})
    red = Image.new("RGBA", (1, 1), (255, 0, 0, 255))
    again = fr3.read(fr3.write(data, {1: red}, {}), {})
    assert again[1].image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert again[0].image.tobytes() == textures[0].image.tobytes()


@pytest.mark.skipif(not REAL.is_file(), reason="Jak 2 level files not extracted on this machine")
def test_real_level_no_op_and_one_edit():
    data = REAL.read_bytes()
    textures = fr3.read(data, {})
    assert textures
    assert fr3.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data
    idx = next(i for i, t in enumerate(textures) if t.image.size[0] >= 8)
    edited = fr3.write(data, {idx: Image.new("RGBA", textures[idx].image.size, (0, 255, 0, 255))}, {})
    assert fr3.read(edited, {})[idx].image.getpixel((0, 0)) == (0, 255, 0, 255)
