"""Dialogue window preview of Lunar: pages, portraits, glyph font and the window. Synthetic bytes only."""
import struct
import zlib

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from PIL import Image

from plugins.lunar_sssc import dialogue_preview as dp


def _face_member(ids, fill=1):
    """A TIZ member as on disc: a 32-byte header (ids at 0x10) and raw deflate of five 64x64 frames (index ``fill + n``)."""
    header = bytearray(32)
    header[0:4] = b"FACE"
    for i, value in enumerate(ids):
        header[0x10 + i] = value
    frames = bytearray()
    for frame in range(5):
        frames += bytes([fill + frame]) * dp.FRAME_BYTES
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    return bytes(header) + packer.compress(bytes(frames)) + packer.flush()


def _palette():
    values = [0] * 256
    values[1] = 0x001F            # red
    values[2] = 0x03E0            # green
    values[3] = 0x7C00            # blue
    return struct.pack("<256H", *values)


def test_parse_pages_splits_lines_and_pages_and_sets_the_portrait():
    layout = dp.parse_pages("{FA:6E}First line\nSecond{page}{FA:38}Third{end}")
    assert len(layout.pages) == 2
    first, second = layout.pages
    assert [line.text for line in first] == ["First line", "Second"]
    assert first[0].face == 0x6E
    assert [line.text for line in second] == ["Third"]
    assert second[0].face == 0x38
    assert layout.problems == []


def test_parse_pages_reports_too_many_lines_and_wide_lines():
    layout = dp.parse_pages("a\nb\nc\nd")
    assert layout.problems == ["page 1: 4 lines, the window shows 3"]
    wide = dp.parse_pages("W" * 60)
    assert any("wider" in problem for problem in wide.problems)


def test_fa_zero_removes_the_portrait_and_other_tags_take_no_room():
    layout = dp.parse_pages("{FA:6E}Hi{F8:1E}{FA:00}there")
    line = layout.pages[0][0]
    assert line.text == "Hithere"
    assert line.face == 0


def test_index_faces_maps_each_id_to_its_frame():
    files = {"FACE_001.TIZ": _face_member([1, 2, 3, 4, 5]), "FACE_022.TIZ": _face_member([0x6A, 0x6B, 0x6C, 0x6D, 0x6E])}
    index = dp.index_faces(files)
    assert index[3] == ("FACE_001.TIZ", 2)
    assert index[0x6E] == ("FACE_022.TIZ", 4)


def test_face_picture_uses_the_frame_and_keeps_index_zero_transparent():
    files = {"FACE_022.TIZ": _face_member([0x6A, 0x6B, 0x6C, 0x6D, 0x6E], fill=1)}
    palette = dp.palette_from_file(_palette())
    picture = dp.face_picture(files, dp.index_faces(files), 0x6A, palette)
    assert picture.size == (64, 64)
    assert picture.getpixel((0, 0)) == (palette[1][0], palette[1][1], palette[1][2], 255)
    frame_four = dp.face_picture(files, dp.index_faces(files), 0x6E, palette)
    assert frame_four.getpixel((10, 10)) == (palette[5][0], palette[5][1], palette[5][2], 255)
    assert dp.face_picture(files, dp.index_faces(files), 0x99, palette) is None


def test_palette_from_file_expands_5_bit_colours():
    palette = dp.palette_from_file(_palette())
    assert palette[1] == (255, 0, 0)
    assert palette[2] == (0, 255, 0)
    assert palette[3] == (0, 0, 255)
    try:
        dp.palette_from_file(b"\x00" * 10)
    except ValueError:
        pass
    else:
        raise AssertionError("a short palette must be refused")


def test_decode_glyphs_reads_16_rows_big_endian_from_the_font_place():
    offset = int(dp.FONT["params"]["offset"], 0)
    count = int(dp.FONT["params"]["count"])
    slus = bytearray(offset + count * 32)
    index_of_a = dp.FONT["params"]["chars"].index("A")
    struct.pack_into(">16H", slus, offset + index_of_a * 32, *([0x8000] * 16))
    glyphs = dp.decode_glyphs(bytes(slus))
    assert glyphs["A"] == [0x8000] * 16
    assert glyphs[" "] == [0] * 16


def test_render_page_places_the_window_portrait_and_text():
    glyphs = {"A": [0x8000] * 16}
    portrait = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    picture = dp.render_page([dp.Line("A")], glyphs, portrait)
    assert picture.size == (320, 240)
    assert picture.getpixel((dp.PORTRAIT_X + 1, dp.PORTRAIT_Y + 1)) == (255, 0, 0, 255)
    assert picture.getpixel((dp.TEXT_X, dp.TEXT_Y)) == (255, 255, 255, 255)
    assert picture.getpixel((dp.TEXT_X + 1, dp.TEXT_Y)) != (255, 255, 255, 255)


def test_text_width_and_speaker_name():
    assert dp.text_width("") == 0
    assert dp.text_width("  ") == 2 * dp.SPACE_WIDTH
    assert dp.speaker_name(0x6E) == "Nall"
    assert dp.speaker_name(0x6A) is None
