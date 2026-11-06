"""texture_grid ``tiles``: a cell is a stack of texture tiles (SNES tall glyphs whose halves are anywhere, or shared)."""
import pytest

from core import font_formats

TEXTURE = {"pixel_format": "snes:2bpp", "offset": 0, "width": 16, "height": 16}     # 4 tiles, 2 a row
PARAMS = {"texture": "raw", "cell": [8, 16], "tile": [8, 8], "columns": 2, "chars": ["G", "C"],
          "tiles": [[0, 2], [1, 2]], "texture_params": TEXTURE}
DATA = bytes(range(16)) + bytes(range(16, 32)) + bytes([0xFF] * 8 + [0] * 8) + bytes([0x0F] * 16)


def _tile(sheet, x, y):
    return sheet.crop((x, y, x + 8, y + 8)).tobytes()


def _texture(data):
    return font_formats.extract("texture_grid", data, {**PARAMS, "tiles": [0, 1, 2, 3], "cell": [8, 8],
                                                      "chars": ["a", "b", "c", "d"]})[1][0]


def test_a_cell_is_its_tiles_top_to_bottom_and_an_unedited_sheet_packs_back_the_same():
    meta, (sheet,) = font_formats.extract("texture_grid", DATA, PARAMS)
    texture = _texture(DATA)
    assert sheet.size == (16, 16)
    assert _tile(sheet, 0, 0) == _tile(texture, 0, 0) and _tile(sheet, 0, 8) == _tile(texture, 0, 8)   # tiles 0, 2
    assert _tile(sheet, 8, 0) == _tile(texture, 8, 0) and _tile(sheet, 8, 8) == _tile(texture, 0, 8)   # tiles 1, 2
    assert font_formats.pack("texture_grid", meta, [sheet], DATA, PARAMS) == DATA


def test_an_edit_goes_to_its_tile_and_a_shared_tile_cannot_take_two_different_edits():
    meta, (sheet,) = font_formats.extract("texture_grid", DATA, PARAMS)
    edited = sheet.copy()
    edited.putpixel((7, 15), (255, 255, 255, 255))                 # the bottom of G: tile 2, the C's bottom too
    out = font_formats.pack("texture_grid", meta, [edited], DATA, PARAMS)
    assert out[:32] == DATA[:32] and out[48:] == DATA[48:] and out[32:48] != DATA[32:48]
    _meta, (again,) = font_formats.extract("texture_grid", out, PARAMS)
    assert _tile(again, 8, 8) == _tile(edited, 0, 8)
    edited.putpixel((8, 15), (255, 255, 255, 255))                 # the C's bottom edited another way
    with pytest.raises(ValueError):
        font_formats.pack("texture_grid", meta, [edited], DATA, PARAMS)
