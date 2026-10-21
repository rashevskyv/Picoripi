"""The g_MenuStr table of Symphony of the Night: pointer reading, slot lookup, traced places (synthetic DRA)."""
import struct

from PIL import Image

from plugins.castlevania_sotn import menu_screens as ms
from plugins.castlevania_sotn import menu_strings as mt


def _dra_with_table(offsets) -> bytes:
    """A fake DRA.BIN: the 110 pointers at the table offset, each pointing at DRA_BASE + its string offset."""
    data = bytearray(mt.TABLE_OFFSET + 4 * mt.TABLE_SIZE + 64)
    for i, off in enumerate(offsets):
        struct.pack_into("<I", data, mt.TABLE_OFFSET + 4 * i, mt.DRA_BASE + off)
    return bytes(data)


def test_the_table_is_read_as_string_offsets_from_the_dra_load_address():
    offsets = [0x3FF44 + 8 * i for i in range(mt.TABLE_SIZE)]
    table = mt.read_table(_dra_with_table(offsets))
    assert table == offsets


def test_a_short_file_has_no_table():
    assert mt.read_table(b"\x00" * 100) is None


def test_a_string_offset_finds_its_slot_and_an_unknown_one_finds_none():
    offsets = [0x1000 + 16 * i for i in range(mt.TABLE_SIZE)]
    table = mt.read_table(_dra_with_table(offsets))
    assert mt.slot_for_offset(table, 0x1000 + 16 * 92) == 92
    assert mt.slot_for_offset(table, 0x9999) is None


def test_the_command_and_popup_places_use_their_fitted_origins():
    assert mt.placement(92) == ("command", mt.COMMAND_ORIGIN[0] + 18, mt.COMMAND_ORIGIN[1] + 4)
    assert mt.placement(34) == ("popup", mt.POPUP_ORIGIN[0] + 4, mt.POPUP_ORIGIN[1] + 20)
    assert mt.placement(0) == ("status", 128, 40)
    assert mt.placement(200) is None


def _glyphs() -> ms.Glyphs:
    block = Image.new("L", (8, 8), ms.INK)
    return ms.Glyphs(mask_of=lambda cell: block, cell_of=lambda ch: ord(ch))


def test_the_command_highlight_sits_on_the_slot_row():
    canvas = ms.new_canvas()
    ms.command_frame(canvas, mt.COMMAND_ORIGIN, 2)               # Relics is row 2 (slot 94)
    x, y = mt.COMMAND_ORIGIN
    top = y - 2 + 4 + 2 * 16
    assert canvas.getpixel((x, top)) == ms.HIGHLIGHT
    assert canvas.getpixel((x, top - 1)) != ms.HIGHLIGHT


def test_a_menu_word_is_drawn_at_its_place_with_its_cells():
    canvas = ms.new_canvas()
    screen, x, y = mt.placement(12)                              # HP on the status screen
    ms.draw_cells(canvas, _glyphs(), [1, 2], x, y)
    assert canvas.getpixel((x, y)) != (0, 0, 0, 0)
    assert canvas.getpixel((x + 8, y)) != (0, 0, 0, 0)
