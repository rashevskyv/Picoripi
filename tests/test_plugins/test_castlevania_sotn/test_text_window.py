"""The cutscene window of Symphony of the Night: placement, cell drawing and the strip's end (synthetic sheet)."""
from PIL import Image

from plugins.castlevania_sotn import codec, text_window
from plugins.castlevania_sotn.text_preview import page_codes


def _sheet() -> Image.Image:
    """A 128 x 128 grid sheet where cell 1 is opaque white and every other cell is transparent."""
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    sheet.paste((255, 255, 255, 255), (8, 0, 16, 8))      # cell 1: column 1, row 0
    return sheet


def test_the_first_line_starts_at_start_x_plus_4_and_start_y_plus_20():
    assert text_window.Place(52, 44).line_origin(0) == (56, 64)


def test_each_line_is_12_pixels_below_the_one_before():
    place = text_window.Place(0, 0)
    assert [place.line_origin(row)[1] for row in range(4)] == [20, 32, 44, 56]


def test_a_cell_is_drawn_where_the_line_origin_says_and_nothing_else_is():
    frame = text_window.render_page([[1, 1]], _sheet(), text_window.Place(10, 20))
    assert frame.size == text_window.CANVAS
    inked = [(x, y) for x in range(320) for y in range(240) if frame.getpixel((x, y))[3]]
    assert inked and min(inked) == (14, 40) and max(inked) == (29, 47)
    assert len(inked) == 2 * 8 * 8


def test_the_strip_ends_after_24_cells():
    frame = text_window.render_page([[1] * 30], _sheet(), text_window.Place(0, 0))
    assert frame.getpixel((4 + 23 * 8, 20))[3] == 255
    assert frame.getpixel((4 + 24 * 8, 20))[3] == 0


def test_only_four_lines_are_drawn():
    frame = text_window.render_page([[1]] * 6, _sheet(), text_window.Place(0, 0))
    assert frame.getpixel((4, 20 + 4 * 12))[3] == 0


def test_zoom_is_whole_number_and_nearest():
    frame = Image.new("RGBA", (4, 2), (1, 2, 3, 255))
    zoomed = text_window.scale_nearest(frame, 3)
    assert zoomed.size == (12, 6) and zoomed.getpixel((11, 5)) == (1, 2, 3, 255)


def test_tags_are_not_drawn_and_each_line_is_a_list_of_cells():
    codes = page_codes("{WAIT 30}AB\nC")
    assert codes == [list(codec.encode_cells("AB")), list(codec.encode_cells("C"))]
