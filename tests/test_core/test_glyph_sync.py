"""Glyph sync between two copies of a font (core/font_formats/glyph_sync.py), on synthetic font models."""
from PIL import Image

from core.font_formats.glyph_sync import copy_glyphs, storable
from core.font_formats.sources import resolve


def font(values=None, widths=None, codes="AB", cell=(4, 4), grid=(2, 2), texture_format=2, entries=None):
    """A font model. Glyph i draws ``values[i]`` over its whole cell (default 17 * (i + 1)); its width is 5."""
    columns, rows = grid
    per_sheet = columns * rows
    sheet_count = (len(codes) + per_sheet - 1) // per_sheet
    sheets = [Image.new("RGBA", (columns * cell[0], rows * cell[1]), (0, 0, 0, 0)) for _ in range(sheet_count)]
    for glyph in range(len(codes)):
        value = (values or {}).get(glyph, 17 * (glyph + 1))
        sheet, index = divmod(glyph, per_sheet)
        x, y = (index % columns) * cell[0], (index // columns) * cell[1]
        sheets[sheet].paste((value, value, value, value), (x, y, x + cell[0], y + cell[1]))
    codes_entries = entries if entries is not None else list(range(len(codes)))
    metadata = {
        "GLY1": [{"start_glyph": 0, "end_glyph": len(codes) - 1, "cell_width": cell[0], "cell_height": cell[1],
                  "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_format": texture_format}],
        "MAP1": [{"mapping_type": 2, "first_char": ord(codes[0]), "last_char": ord(codes[0]) + len(codes_entries) - 1,
                  "entries": codes_entries}],
        "WID1": [{"first_code_included": 0,
                  "packets": [{"kerning": 0, "width": (widths or {}).get(glyph, 5)} for glyph in range(len(codes))]}],
    }
    return metadata, sheets


def pixel(model, glyph, grid=(2, 2), cell=(4, 4)):
    """The value of a glyph's top-left pixel."""
    columns, rows = grid
    sheet, index = divmod(glyph, columns * rows)
    x, y = (index % columns) * cell[0], (index // columns) * cell[1]
    return model[1][sheet].getpixel((x, y))[0]


def width_of(model, glyph):
    return model[0]["WID1"][0]["packets"][glyph]["width"]


def test_an_edited_glyph_is_copied_to_the_other_copy_by_code():
    original = font()
    copied, report = copy_glyphs(font(values={0: 68}), original, font(), original)
    assert pixel(copied, 0) == 68
    assert pixel(copied, 1) == 34                      # code 'B' was not edited: unchanged
    assert report.copied == ["A"] and report.conflicts == [] and report.skipped == {}
    assert report.shared == 2


def test_a_width_only_edit_travels_with_the_glyph():
    original = font()
    copied, report = copy_glyphs(font(widths={1: 9}), original, font(), original)
    assert width_of(copied, 1) == 9
    assert width_of(copied, 0) == 5
    assert pixel(copied, 1) == 34
    assert report.copied == ["B"]


def test_a_change_only_in_the_other_copy_is_left_alone():
    original = font()
    copied, report = copy_glyphs(original, original, font(values={0: 102}), original)
    assert copied is None
    assert report.copied == [] and report.conflicts == []


def test_both_copies_changed_the_same_code_differently_the_edited_copy_wins_and_is_reported():
    original = font()
    copied, report = copy_glyphs(font(values={0: 68}), original, font(values={0: 102}), original)
    assert pixel(copied, 0) == 68
    assert report.copied == ["A"] and report.conflicts == ["A"]


def test_both_copies_changed_the_same_code_the_same_way_nothing_is_copied():
    original = font()
    copied, report = copy_glyphs(font(values={0: 68}), original, font(values={0: 68}), original)
    assert copied is None
    assert report.copied == [] and report.conflicts == []


def test_a_cell_of_another_size_is_skipped_with_the_sizes_named():
    original = font()
    copied, report = copy_glyphs(font(values={0: 68}), original, font(cell=(6, 6)), font(cell=(6, 6)))
    assert copied is None
    assert report.skipped["A"] == "cell size 4x4 differs from the other copy's 6x6; no lossless mapping"


def test_a_glyph_lands_in_the_other_copy_layout_at_its_own_cell():
    # The other copy has one column and two rows: code 'B' is the glyph in its second row.
    copied, report = copy_glyphs(font(values={1: 85}), font(), font(grid=(1, 2)), font(grid=(1, 2)))
    assert pixel(copied, 1, grid=(1, 2)) == 85
    assert pixel(copied, 0, grid=(1, 2)) == 17
    assert report.copied == ["B"]


def test_a_glyph_that_another_code_shares_in_the_other_copy_is_skipped():
    shared = font(entries=[0, 0])                      # 'A' and 'B' both point at glyph 0 in the other copy
    copied, report = copy_glyphs(font(values={0: 68}), font(), shared, font(entries=[0, 0]))
    assert copied is None
    assert report.skipped["A"] == "the other copy's glyph is shared by 2 codes"


def test_pixels_the_other_texture_format_cannot_hold_are_not_copied():
    copied, report = copy_glyphs(font(values={0: 5}), font(), font(), font())
    assert copied is None
    assert report.skipped["A"] == "the other copy's texture format cannot hold these pixels exactly"


def test_a_code_only_one_copy_has_is_not_shared():
    copied, report = copy_glyphs(font(values={0: 68}), font(), font(codes="A"), font(codes="A"))
    assert report.shared == 1
    assert report.copied == ["A"]


def test_storable_follows_each_texture_format():
    def solid(value, alpha=None):
        return Image.new("RGBA", (2, 2), (value, value, value, value if alpha is None else alpha))

    assert storable(solid(34), 2) and storable(solid(0), 0)     # IA4 and I4 hold multiples of 17
    assert not storable(solid(5), 2) and not storable(solid(5), 0)
    assert storable(solid(5), 1)                                  # I8: any intensity, alpha equal to it
    assert not storable(solid(5, alpha=7), 1)
    assert storable(solid(5, alpha=7), 3)                         # IA8: any intensity and alpha
    assert storable(solid(34, alpha=68), 2)                       # IA4 keeps its own alpha
    assert not storable(solid(34), 9)                             # a format this check does not know


def test_linked_descriptors_are_paired_by_their_label_and_file_name(tmp_path):
    for name in ("a/font.bfn", "b/font.bfn", "c/other.bfn"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"x")
    descriptors = [
        {"label": "Copy one", "format": "bfn", "path": "a/font.bfn", "sync_glyphs_with": "Copy two"},
        {"label": "Copy two", "format": "bfn", "path": "b/font.bfn", "sync_glyphs_with": "Copy one"},
        {"label": "Loose", "format": "bfn", "path": "c/other.bfn", "sync_glyphs_with": "Copy one"},
    ]
    found = resolve(descriptors, {"source_path": str(tmp_path), "translation_path": str(tmp_path / "tr"),
                                  "is_directory_mode": True})
    one, two, loose = found
    assert one.sync_partner is two and two.sync_partner is one
    assert loose.sync_partner is None                   # no file of the linked descriptor has its name
