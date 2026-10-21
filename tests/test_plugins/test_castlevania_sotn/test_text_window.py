"""The cutscene window of Symphony of the Night: placement, cell drawing and the strip's end (synthetic sheet)."""
from PIL import Image

from plugins.castlevania_sotn import codec, script, text_window
from plugins.castlevania_sotn.text_preview import page_codes


def _sheet() -> Image.Image:
    """A 128 x 128 grid sheet where cell 1 is opaque white and every other cell is transparent."""
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    sheet.paste((255, 255, 255, 255), (8, 0, 16, 8))      # cell 1: column 1, row 0
    return sheet


def test_the_first_line_starts_at_the_fitted_offset_from_the_place():
    assert text_window.Place(52, 44).line_origin(0) == (64, 49)


def test_each_line_is_12_pixels_below_the_one_before():
    place = text_window.Place(0, 0)
    assert [place.line_origin(row)[1] for row in range(4)] == [5, 17, 29, 41]


def test_a_cell_is_drawn_where_the_line_origin_says_and_nothing_else_is():
    frame = text_window.render_page([[1, 1]], _sheet(), text_window.Place(10, 20))
    assert frame.size == text_window.CANVAS
    inked = [(x, y) for x in range(320) for y in range(240) if frame.getpixel((x, y))[3]]
    assert inked and min(inked) == (22, 25) and max(inked) == (37, 32)
    assert len(inked) == 2 * 8 * 8


def test_the_strip_ends_after_24_cells():
    frame = text_window.render_page([[1] * 30], _sheet(), text_window.Place(0, 0))
    assert frame.getpixel((12 + 23 * 8, 5))[3] == 255
    assert frame.getpixel((12 + 24 * 8, 5))[3] == 0


def test_only_four_lines_are_drawn():
    frame = text_window.render_page([[1]] * 6, _sheet(), text_window.Place(0, 0))
    assert frame.getpixel((12, 5 + 4 * 12))[3] == 0


def test_zoom_is_whole_number_and_nearest():
    frame = Image.new("RGBA", (4, 2), (1, 2, 3, 255))
    zoomed = text_window.scale_nearest(frame, 3)
    assert zoomed.size == (12, 6) and zoomed.getpixel((11, 5)) == (1, 2, 3, 255)


def test_a_line_takes_the_place_of_the_last_pos_command_before_it():
    ops = [script.Op(0, 7, bytes([7, 52, 44])), script.Op(3, -1, b"A"), script.Op(4, 7, bytes([7, 60, 40])),
           script.Op(7, -1, b"B")]
    assert script.place_before(ops, 1) == (52, 44)
    assert script.place_before(ops, 0) == ()
    assert script.place_before(ops, 3) == (60, 40)


def test_tags_are_not_drawn_and_each_line_is_a_list_of_cells():
    codes = page_codes("{WAIT 30}AB\nC")
    assert codes == [list(codec.encode_cells("AB")), list(codec.encode_cells("C"))]


def test_the_speaker_name_is_drawn_at_x_56_and_12_px_above_the_place():
    frame = text_window.render_dialogue([1], [], _sheet(), text_window.Place(10, 20))
    inked = [(x, y) for x in range(320) for y in range(240) if frame.getpixel((x, y))[3]]
    assert min(inked) == (56, 8)
