"""The menu screens of Symphony of the Night: positions, right-aligned numbers, highlight, border (synthetic glyphs)."""
from PIL import Image

from plugins.castlevania_sotn import menu_screens as ms


def _glyphs() -> ms.Glyphs:
    """Every cell is a solid 8x8 block; the cell number is the character code (synthetic font)."""
    block = Image.new("L", (8, 8), ms.INK)
    return ms.Glyphs(mask_of=lambda cell: block, cell_of=lambda ch: ord(ch))


def _ink(canvas: Image.Image, x: int, y: int) -> bool:
    return canvas.getpixel((x, y))[3] > 0


def test_numbers_are_right_aligned_on_the_given_x():
    canvas = ms.new_canvas()
    ms.draw_int(canvas, _glyphs(), 47, 308, 80)
    assert _ink(canvas, 308, 80) and _ink(canvas, 300, 80)      # units at 308, tens at 300
    assert not _ink(canvas, 316, 80)                             # nothing to the right of the units cell


def test_a_fixed_digit_time_pads_with_zero_cells():
    canvas = ms.new_canvas()
    ms.draw_time(canvas, _glyphs(), 7, 288, 192, 2)
    assert _ink(canvas, 288, 192) and _ink(canvas, 280, 192)    # two cells, the tens cell is drawn too


def test_the_equip_overview_puts_the_names_at_their_traced_rows():
    canvas = ms.new_canvas()
    ms.equip_overview(canvas, _glyphs(), "Cloak", [("STR", 7, 4), ("CON", 6, 10), ("INT", 6, None), ("LCK", 6, None)],
                      ["Alucard sword", "Alucard shield"], (47, 0), 40)
    assert _ink(canvas, 112, 30)                                 # first name row
    assert _ink(canvas, 112, 43)                                 # second name row (30 + 13)
    assert not _ink(canvas, 112, 40)                             # between the rows (8 px cells, 13 px pitch)
    assert _ink(canvas, 12, 70) and _ink(canvas, 12, 82)         # STR and CON labels
    assert _ink(canvas, 8, 40)                                   # the category label


def test_the_highlight_is_the_static_dark_red_of_the_menu_rect():
    canvas = ms.new_canvas()
    ms.highlight(canvas, 2, 10, 20, 50, 12, 4)                   # row 2 at y 20 + 2 * 16
    assert canvas.getpixel((10, 52)) == ms.HIGHLIGHT
    assert canvas.getpixel((59, 63)) == ms.HIGHLIGHT
    assert canvas.getpixel((10, 51)) == (0, 0, 0, 0)


def test_the_window_border_is_one_white_pixel_on_each_side():
    canvas = ms.new_canvas()
    ms.frame_lines(canvas, 5, 5, 20, 10)
    assert canvas.getpixel((5, 5)) == ms.BORDER
    assert canvas.getpixel((24, 14)) == ms.BORDER
    assert canvas.getpixel((10, 10)) == (0, 0, 0, 0)


def test_the_info_bar_line_is_laid_out_by_the_bios_rules():
    full = b"\xff" * 30
    image, missing = ms.info_bar_strip(b"Ab", lambda code: full)
    assert missing == 0
    assert image.size == (24, 16)                                # two full glyphs: 6 bytes (12 px) each


def test_the_sound_popup_highlights_the_chosen_item():
    canvas = ms.new_canvas()
    ms.sound_popup(canvas, _glyphs(), 170, 114, mono=True)
    assert canvas.getpixel((173, 116 + 16)) == ms.HIGHLIGHT       # Mono row: y + 2 + 16
    assert canvas.getpixel((173, 117)) != ms.HIGHLIGHT            # Stereo row is not highlighted
