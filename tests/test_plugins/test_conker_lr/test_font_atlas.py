"""Conker: Live & Reloaded font atlas: the .gpu section is a 256 x 240 grey texture, PNG export and import are exact.

Every file here is synthetic (built in the test); no disc data is in the repository.
"""
import struct
import zlib

import pytest

from plugins.conker_lr import caff_text, font_atlas


def _bank(pixels: bytes, data_size: int = 0x100) -> bytes:
    """A CAFF font bank: a header with a .data section and a .gpu section after it, then the texture bytes."""
    head = bytearray(b"CAFF".ljust(0x180, b"\x00"))
    struct.pack_into("<I", head, 0x34, data_size)
    for index, (name, size) in enumerate([(b".data", data_size), (b".gpu", font_atlas.ATLAS_BYTES)]):
        at = font_atlas.SECTION_ENTRY + font_atlas.SECTION_ENTRY_SIZE * index
        head[at:at + len(name)] = name
        struct.pack_into("<I", head, at + font_atlas.SIZE_FIELD, size)
    data = bytes((i * 3) & 0xFF for i in range(data_size))
    return bytes(head) + data + pixels


def _pixels() -> bytes:
    return bytes((x * 7 + y * 13) & 0xFF for y in range(font_atlas.ATLAS_HEIGHT)
                 for x in range(font_atlas.ATLAS_WIDTH))


def _png(width: int, height: int, rows: bytes, filters=None) -> bytes:
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (font_atlas.PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9))
            + chunk(b"IEND", b""))


def _filtered_rows(pixels: bytes, kinds) -> bytes:
    """Encode the rows with the given PNG filter type per row (0-4), as a PNG encoder would."""
    stride = font_atlas.ATLAS_WIDTH
    out = bytearray()
    prev = bytes(stride)
    for y in range(font_atlas.ATLAS_HEIGHT):
        row = pixels[y * stride:(y + 1) * stride]
        kind = kinds[y % len(kinds)]
        out.append(kind)
        for x in range(stride):
            left = row[x - 1] if x else 0
            up = prev[x]
            upleft = prev[x - 1] if x else 0
            pred = {0: 0, 1: left, 2: up, 3: (left + up) >> 1, 4: font_atlas._paeth(left, up, upleft)}[kind]
            out.append((row[x] - pred) & 0xFF)
        prev = row
    return bytes(out)


def test_the_atlas_is_the_gpu_section_after_the_data_section():
    bank = _bank(_pixels())
    assert font_atlas.gpu_range(bank) == (0x180 + 0x100, font_atlas.ATLAS_BYTES)
    assert font_atlas.atlas_pixels(bank) == _pixels()


def test_a_png_written_from_the_atlas_reads_back_to_the_same_bytes():
    pixels = _pixels()
    png = font_atlas.encode_png(pixels)
    assert png.startswith(font_atlas.PNG_SIGNATURE)
    assert font_atlas.decode_png(png) == pixels


def test_export_and_import_leave_the_bank_byte_identical():
    bank = _bank(_pixels())
    back = font_atlas.decode_png(font_atlas.encode_png(font_atlas.atlas_pixels(bank)))
    assert font_atlas.replace_pixels(bank, back) == bank


def test_a_changed_pixel_changes_only_the_atlas_bytes():
    bank = _bank(_pixels())
    pixels = bytearray(_pixels())
    pixels[5 * font_atlas.ATLAS_WIDTH + 9] ^= 0xFF
    edited = font_atlas.replace_pixels(bank, bytes(pixels))
    changed = [i for i in range(len(bank)) if bank[i] != edited[i]]
    assert changed == [0x180 + 0x100 + 5 * font_atlas.ATLAS_WIDTH + 9]


def test_every_png_filter_type_is_read():
    pixels = _pixels()
    rows = _filtered_rows(pixels, [0, 1, 2, 3, 4])
    assert font_atlas.decode_png(_png(256, 240, rows)) == pixels


def test_a_png_of_another_size_or_colour_is_refused():
    with pytest.raises(font_atlas.AtlasError):
        font_atlas.decode_png(_png(128, 240, bytes(128 * 240 + 240)))
    with pytest.raises(font_atlas.AtlasError):
        font_atlas.decode_png(b"GIF89a")


def test_the_wrong_size_of_pixels_is_refused():
    with pytest.raises(font_atlas.AtlasError):
        font_atlas.encode_png(bytes(10))
    with pytest.raises(font_atlas.AtlasError):
        font_atlas.replace_pixels(_bank(_pixels()), bytes(10))


def test_a_bank_without_a_gpu_section_is_refused():
    bank = bytearray(_bank(_pixels()))
    bank[0x68:0x68 + 8] = b"\x00" * 8  # the second section entry no longer has a name
    with pytest.raises(font_atlas.AtlasError):
        font_atlas.gpu_range(bytes(bank))


def test_the_caff_checksum_is_not_touched_by_an_atlas_change():
    # the header checksum covers the first 0x180 bytes only; the atlas lies after the data section
    bank = bytearray(_bank(_pixels()))
    struct.pack_into("<I", bank, 0x14, caff_text.caff_hash(bytes(bank)))
    edited = font_atlas.replace_pixels(bytes(bank), bytes(font_atlas.ATLAS_BYTES))
    assert struct.unpack_from("<I", edited, 0x14)[0] == caff_text.caff_hash(edited)

