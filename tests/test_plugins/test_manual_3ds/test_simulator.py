"""The 3DS manual simulator: the BCLYT reader, the viewer's line wrap, the window frames, the contents reader, the
screen composition and the defect finder, on synthetic data; then one real page against a console screenshot.

The real-data test needs the owner's repo_manual folder (PICORIPI_ROMHACKING) and the screenshot folder
(PICORIPI_3DS_CALIB, the folder that holds shots_r17b); it skips without them.
"""
import os
import struct
from pathlib import Path

import pytest
from PIL import Image

import romhacking_root
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import sim_screens as ss
from plugins.manual_3ds import simulator

_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")
CALIB_ENV = "PICORIPI_3DS_CALIB"


# -- a synthetic font and layout ------------------------------------------------------------------


class _Sheets:
    cell_width = 24
    cell_height = 30
    baseline = 25


class _Font:
    """A bcfnt.Font stand-in: every code point is glyph 0 with a 10-unit advance, except the space (5)."""

    def __init__(self):
        self.finf = bytes([1, 30, 0, 0, 0, 24, 24, 1]) + bytes(12) + bytes([30, 25, 25, 0])
        self.sheets = _Sheets()
        self.widths = [(1, 8, 10), (0, 0, 5)]
        self.cmap = {code: (1 if code == 0x20 else 0) for code in range(0x20, 0x500)}


class _Bcfnt:
    @staticmethod
    def glyph_rows(font, code):
        return [[15 if 2 <= x < 10 and 5 <= y < 25 else 0 for x in range(24)] for y in range(30)]


def _section(magic: bytes, body: bytes) -> bytes:
    size = 8 + len(body)
    size += -size % 4
    return magic + struct.pack("<I", size) + body + b"\0" * (size - 8 - len(body))


def _pane_head(name: str, origin: int, x: float, y: float, w: float, h: float) -> bytes:
    return (struct.pack("<BBBB", 1, origin, 255, 0) + name.encode("ascii").ljust(0x18, b"\0")
            + struct.pack("<fff", x, y, 0.0) + struct.pack("<fff", 0.0, 0.0, 0.0) + struct.pack("<ff", 1.0, 1.0)
            + struct.pack("<ff", w, h))


def _txt1(name, x, y, w, h, text, size=(16.67, 20.0), char_space=0.5, material=0):
    encoded = (text + "\0").encode("utf-16-le")
    body = _pane_head(name, 0, x, y, w, h)
    body += struct.pack("<HHHH", len(encoded), len(encoded), material, 0)
    body += struct.pack("<BBH", 0, 0, 0) + struct.pack("<I", 0x74)
    body += bytes((60, 60, 60, 255)) + bytes((60, 60, 60, 255))
    body += struct.pack("<ffff", size[0], size[1], char_space, 0.0) + encoded
    return _section(b"txt1", body)


def _wnd1(name, x, y, w, h, colour, frames, material=0):
    body = _pane_head(name, 0, x, y, w, h) + struct.pack("<ffff", 0, 0, 0, 0)
    body += struct.pack("<BBH", len(frames), 0, 0)
    content_off = 0x68
    frames_off = content_off + 16 + 4
    body += struct.pack("<II", content_off, frames_off)
    body += bytes(colour) * 4 + struct.pack("<HBB", material, 0, 0)
    table = frames_off + 4 * len(frames)
    body += b"".join(struct.pack("<I", table + 4 * index) for index in range(len(frames)))
    body += b"".join(struct.pack("<HBB", mat, flip, 0) for mat, flip in frames)
    return _section(b"wnd1", body)


def _mat1(materials):
    """materials: [(name, texture index or None)]"""
    bodies = []
    for name, texture in materials:
        body = name.encode("ascii").ljust(0x14, b"\0") + bytes(4) + bytes(24)
        if texture is None:
            body += struct.pack("<I", 0)
        else:
            body += struct.pack("<I", 0x15) + struct.pack("<HBB", texture, 4, 4) + bytes(0x18)
        bodies.append(body)
    head = struct.pack("<I", len(bodies))
    offsets = []
    at = 8 + 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(at)
        at += len(body)
    return _section(b"mat1", head + b"".join(struct.pack("<I", o) for o in offsets) + b"".join(bodies))


def _txl1(names):
    head = struct.pack("<I", len(names))
    table = b""
    strings = b""
    at = 4 * len(names)
    for name in names:
        table += struct.pack("<I", at)
        encoded = name.encode("ascii") + b"\0"
        strings += encoded
        at += len(encoded)
    return _section(b"txl1", head + table + strings)


def _usd1(entries):
    """entries: [(name, [ints])]. Records (12 bytes each) hold offsets from the record's own start to the name
    (after the records) and to the values (after the names)."""
    head = struct.pack("<I", len(entries))
    record_len = 12 * len(entries)
    names_len = sum(len(name) + 1 for name, _ in entries)
    data_start = 4 + record_len + names_len
    records = b""
    names = b""
    values = b""
    for index, (name, ints) in enumerate(entries):
        record_at = 4 + 12 * index
        name_rel = (4 + record_len + len(names)) - record_at
        data_rel = (data_start + len(values)) - record_at
        records += struct.pack("<IIHB", name_rel, data_rel, len(ints), 1) + b"\0"
        names += name.encode("ascii") + b"\0"
        values += struct.pack(f"<{len(ints)}i", *ints)
    return _section(b"usd1", head + records + names + values)


def _bclyt(sections, width=320.0, height=260.0):
    lyt = _section(b"lyt1", struct.pack("<Iff", 1, width, height))
    root = _section(b"pan1", _pane_head("RootPane", 4, 0.0, 0.0, width, height))
    body = [lyt] + sections[:1] + [root, _section(b"pas1", b"")] + sections[1:] + [_section(b"pae1", b"")]
    count = len(body)
    header = b"CLYT" + struct.pack("<HHIIHH", 0xFEFF, 0x14, 0x02020000, 0, count, 0)
    data = header + b"".join(body)
    return data[:0x0C] + struct.pack("<I", len(data)) + data[0x10:]


def _renderer(textures=None):
    return cr.PageRenderer(cr.Textures(textures or {}), cr.Glyphs(_Font(), _Bcfnt()))


# -- tests --------------------------------------------------------------------------------------


def test_parse_adds_group_positions_and_reads_text_fields():
    data = _bclyt([_mat1([("m", None)]), _section(b"pan1", _pane_head("Group", 0, 8.0, -10.0, 300.0, 100.0)),
                   _section(b"pas1", b""), _txt1("Line", 7.3, -5.0, 321.3, 40.0, "abc", char_space=0.4),
                   _section(b"pae1", b"")])
    layout = cr.parse(data)
    line = next(p for p in layout.panes if p.name == "Line")
    assert (line.abs_x, line.abs_y) == pytest.approx((15.3, -15.0))
    assert line.text == "abc" and line.font_size == (pytest.approx(16.67), 20.0) and line.char_space == pytest.approx(0.4)
    assert layout.height == 260.0


def test_wrap_breaks_a_line_at_the_last_space_that_fits():
    renderer = _renderer()
    scale = 16.67 / 25
    # 10 units an ink glyph, 5 a space, scale 0.667: "aaaa bbbb" is 56.7 px, the whole line 86.7 px.
    lines = renderer._wrap("aaaa bbbb cccc", 60.0, scale, 0.0)
    assert [text for text, _ in lines] == ["aaaa bbbb", "cccc"]
    assert [wrapped for _, wrapped in lines] == [False, True]
    assert renderer._wrap("aaaa bbbb cccc", 100.0, scale, 0.0) == [("aaaa bbbb cccc", False)]


def test_wrap_uses_the_pane_width_less_the_slack():
    width = 16.67 / 25 * 10 * 5   # "aaaaa" exactly
    roomy = _bclyt([_mat1([("m", None)]), _txt1("A", 0.0, 0.0, width + cr.WRAP_SLACK + 0.5, 20.0, "aaaaa bb", char_space=0.0)])
    renderer = _renderer()
    renderer.render([roomy])
    assert [run.text for run in renderer.runs] == ["aaaaa", "bb"]
    assert renderer.runs[1].wrapped and renderer.runs[1].top == pytest.approx(-20.0)
    # A box only 1 px wider than the word: within the slack, so the viewer breaks inside the word.
    tight = _bclyt([_mat1([("m", None)]), _txt1("A", 0.0, 0.0, width + 1.0, 20.0, "aaaaa bb", char_space=0.0)])
    renderer = _renderer()
    renderer.render([tight])
    assert [run.text for run in renderer.runs] == ["aaaa", "a bb"]


def test_text_line_lands_at_its_pane_and_advances_with_char_space():
    data = _bclyt([_mat1([("m", None)]), _txt1("A", 7.3, -10.0, 300.0, 40.0, "ab", char_space=0.5)])
    renderer = _renderer()
    image = renderer.render([data])
    run = renderer.runs[0]
    assert (run.x, run.top) == pytest.approx((7.3, -10.0))
    assert run.width == pytest.approx(2 * 10 * 16.67 / 25 + 0.5)
    # Ink appears in the column where the first glyph's cell is: row 204 + 10, x 7.3 + left bearing.
    assert image.getpixel((int(7.3 + 1 + 4), 204 + 10 + 10))[3] > 0
    assert image.getpixel((200, 204 + 100))[3] == 0


def test_one_frame_window_draws_rounded_corners_from_its_texture():
    corner = Image.new("RGBA", (4, 4), (0, 0, 255, 255))
    corner.putpixel((0, 0), (0, 0, 0, 0))   # the top-left texel is clear: a rounded corner
    textures = cr.Textures({})
    textures._images["corner.bclim"] = corner
    data = _bclyt([_txl1(["corner.bclim"]), _mat1([("content", None), ("frame", 0)]),
                   _wnd1("Pill", 10.0, -10.0, 40.0, 20.0, (0, 0, 255, 255), [(1, 0)])])
    renderer = cr.PageRenderer(textures, cr.Glyphs(_Font(), _Bcfnt()))
    image = renderer.render([data])
    top, left = 204 + 10, 10
    assert image.getpixel((left, top))[3] == 0                 # top-left corner texel
    assert image.getpixel((left + 49 - 10, top))[3] == 0       # top-right corner, mirrored
    assert image.getpixel((left, top + 19))[3] == 0            # bottom-left
    assert image.getpixel((left + 39, top + 19))[3] == 0       # bottom-right
    assert image.getpixel((left + 20, top))[:3] == (0, 0, 255)       # top edge, stretched
    assert image.getpixel((left + 20, top + 10))[:3] == (0, 0, 255)  # content


def test_stretch_edge_repeats_the_last_column_and_row():
    tex = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    tex.putpixel((1, 1), (0, 255, 0, 255))
    out = cr._stretch_edge(tex, 5, 4, "lt")
    assert out.size == (5, 4)
    assert out.getpixel((4, 3))[:3] == (0, 255, 0) and out.getpixel((0, 0))[:3] == (255, 0, 0)
    assert out.getpixel((4, 0))[:3] == (255, 0, 0) and out.getpixel((1, 3))[:3] == (0, 255, 0)


def test_read_index_gives_page_numbers_categories_and_splits():
    sections = [_mat1([("m", None)] * 4),
                _section(b"pan1", _pane_head("MetaData", 4, 0.0, 0.0, 200.0, 40.0)),
                _usd1([("PageNum", [3]), ("CategoryNum", [2]), ("SplitNumL", [1, 2, 3]), ("SplitNumS", [1, 1, 2])]),
                _txt1("PageTitle_000", 0, 0, 200, 40, "Alpha"), _txt1("PageTitle_001", 0, 0, 200, 40, "Beta"),
                _txt1("PageTitle_002", 0, 0, 200, 40, "Gamma"),
                _txt1("Category_000", 0, 0, 200, 40, "__CATEGORY_INVALID__"),
                _usd1([("IsValid", [0]), ("CategoryPageNum", [1]), ("PageID_000", [0])]),
                _txt1("Category_001", 0, 0, 200, 40, "Basics"),
                _usd1([("IsValid", [1]), ("CategoryPageNum", [2]), ("PageID_000", [1]), ("PageID_001", [2])])]
    index = cr.read_index(_bclyt(sections, 100.0, 100.0))
    assert index.titles == ["Alpha", "Beta", "Gamma"]
    assert [c.name for c in index.categories] == ["__CATEGORY_INVALID__", "Basics"]
    assert index.categories[1].pages == [1, 2] and not index.categories[0].valid
    assert index.number_of(2) == 3 and index.category_of(2) == 1 and index.category_of(0) == 0
    assert index.splits_large == [1, 2, 3] and index.splits_small == [1, 1, 2]


def test_page_files_puts_the_backdrop_first_then_the_sub_pages_in_order():
    files = {"Page_003_small_1.bclyt": b"1", "Page_003_small_0.bclyt": b"0", "Page_003_small_bg.bclyt": b"bg",
             "Page_003_small_info.bclyt": b"i", "Page_003_small_10.bclyt": b"10", "Page_004_small_0.bclyt": b"x"}
    assert cr.page_files(files, 3, "small") == [b"bg", b"0", b"1", b"10"]
    assert cr.page_files(files, 5, "small") == []
    assert cr.page_numbers(files, "small") == [3, 4]


def test_compose_places_page_y_zero_under_the_header_and_scrolls_the_column():
    glyphs = cr.Glyphs(_Font(), _Bcfnt())
    column = Image.new("RGBA", (336, 1000), (0, 0, 0, 0))
    column.paste((255, 0, 0, 255), (0, 214, 320, 215))      # page y = -10
    column.paste((0, 0, 255, 255), (0, 504, 320, 505))      # page y = -300
    column.paste((0, 255, 0, 255), (320, 604, 336, 605))    # ink past the card's edge at page y = -400
    info = ss.PageInfo(7, "Title", 3, has_previous=True, has_next=False)
    canvas = ss.compose(column, 0, info, ss.Chrome(bottom_bar={}), glyphs)
    assert canvas.size == (400, 480)
    # x 372 is on the track, right of the scroll bar: at scroll 0 that row shows page y = -100, at 300 it shows -400.
    assert canvas.getpixel((372, ss.PAGE_TOP + 100))[:3] != (0, 255, 0)
    assert ss.compose(column, 300, info, ss.Chrome(bottom_bar={}), glyphs).getpixel((372, ss.PAGE_TOP + 100))[:3] == (0, 255, 0)
    assert canvas.getpixel((200, ss.PAGE_TOP + 10))[:3] == (255, 0, 0)
    assert canvas.getpixel((200, ss.PAGE_TOP + 300))[:3] == (0, 0, 255)
    scrolled = ss.compose(column, 100, info, ss.Chrome(bottom_bar={}), glyphs)
    assert scrolled.getpixel((200, ss.PAGE_TOP + 200))[:3] == (0, 0, 255)
    assert canvas.getpixel((50, 20))[:3] == ss.BADGE_COLOURS[3]     # the badge, yellow for category 3
    top, bottom = ss.split(canvas)
    assert top.size == (400, 240) and bottom.size == (320, 240)


def test_scroll_range_stops_when_the_page_bottom_meets_the_bottom_bar():
    # A column of 2 * 204 + 600 rows: the page is 600 px; 414 of it fit between the header and the bottom bar.
    assert ss.scroll_range(2 * cr.TOP_MARGIN_ROWS + 600) == 600 - ss.VISIBLE_ROWS + ss.END_PAD
    assert ss.scroll_range(100) == 0


# -- the real page ---------------------------------------------------------------------------------


_GATE = romhacking_root.missing(*_REPO_MANUAL)


def test_an_overrun_under_half_a_pixel_is_not_a_defect():
    """The console rounds glyph positions to whole pixels: ink 0.4 px past an edge shows nothing there. Ink that
    ends short of a picture's edge is no defect either, however close: the clearance is the owner layout's job
    (Nintendo's own "/" panes end 0.4 px before the next icon)."""
    picture = cr.Pane("pic1", "Pic", True, 0, 255, 200.0, -10.0, 80.0, 60.0, abs_x=200.0, abs_y=-10.0)
    page = cr.Layout(320.0, 260.0, [], [], [], [picture])

    def kinds(ink_right):
        run = cr.TextRun("Line", "text", 10.0, -20.0, ink_right - 10.0, False, ink_right=ink_right)
        return [d.kind for d in simulator.defects_of([run], [], [page], cr.Textures({}), "m", 1, "Page_000", "small")]

    assert kinds(199.6) == []
    assert kinds(200.4) == []
    assert kinds(200.6) == ["over_picture"]
    assert kinds(simulator.LINE_LIMIT + 0.4) == ["over_picture"]
    assert kinds(simulator.LINE_LIMIT + 0.6) == ["over_edge", "over_picture"]


@pytest.mark.skipif(_GATE is not None or not os.environ.get(CALIB_ENV), reason=_GATE or f"{CALIB_ENV} is not set")
def test_home_menu_page_7_small_matches_the_console_within_antialiasing():
    """shots_r17b 2011-01-04_01-59-44.529 shows home_menu_manual page 7 (small) at scroll 0 with cand_r17."""
    repo = romhacking_root.path(*_REPO_MANUAL)
    calib = Path(os.environ[CALIB_ENV])
    top = calib / "shots_r17b" / "2011-01-04_01-59-44.529_top.bmp"
    bottom = calib / "shots_r17b" / "2011-01-04_01-59-44.529_bot.bmp"
    build = repo / "tmp" / "cand_r17"
    if not (top.is_file() and bottom.is_file() and build.is_dir()):
        pytest.skip("the shots_r17b pair or tmp/cand_r17 is not on disk")
    sim = simulator.Simulator(str(repo), build, None)
    shot = simulator.load_pair(top, bottom)
    best, render, _ = simulator.match_shot({"cand_r17": sim}, shot, "home_menu_manual", 6, ["small"], 3, False)
    assert best is not None and best.scroll == 0 and best.size == "small"
    assert best.text_diff < 3.0, best
    # Round 17 draws the second line of the first paragraph into the picture beside it (fixed in round 18).
    defects = simulator.find_defects(sim, "home_menu_manual", 6, "small")
    assert [(d.kind, d.pane) for d in defects] == [("over_picture", "TextBox_38")]
