"""Pokémon generation IV message window (``plugins.pokemon_gen4.message_preview``): the page layout, the glyph
pixels of a Gen 4 font bin, and (real data, skipped without the workspace) the Platinum box drawn with the game's font."""
import struct

import pytest

import romhacking_root
from core.font_formats import gen4_glyphs
from plugins.pokemon_gen4 import message_preview as mp


def test_a_page_has_two_lines_and_a_page_break_says_more_follows():
    lines, more = mp.page_lines("Hello\\nWorld\\rNext page")
    assert ["".join(line) for line in lines] == ["Hello", "World"]
    assert more is True


def test_a_third_line_on_the_page_says_more_follows_and_is_not_shown():
    lines, more = mp.page_lines("one\\ntwo\\nthree")
    assert ["".join(line) for line in lines] == ["one", "two"]
    assert more is True


def test_a_short_message_has_nothing_more():
    lines, more = mp.page_lines("Just this")
    assert ["".join(line) for line in lines] == ["Just this"]
    assert more is False


def test_tags_take_no_width_and_a_player_tag_shows_the_player_name():
    lines, _more = mp.page_lines("{COLOR 1}Hi {STRVAR_01 3,0}!{COLOR 0}")
    assert "".join(lines[0]) == "Hi PLAYER!"


def _font_bin(glyphs, widths):
    """A Gen 4 font bin of ``glyphs`` (lists of 2-bit levels, 16 x 16 each) with the given advance widths."""
    count = len(glyphs)
    glyph_size = 16 * 2 * 2
    widths_at = 16 + count * glyph_size
    head = struct.pack("<IIIBBBB", 16, widths_at, count, 0, 0, 2, 2)
    body = bytearray()
    for levels in glyphs:
        cells = bytearray(glyph_size)
        for tile in range(4):
            tx, ty = tile % 2, tile // 2
            for row in range(8):
                for x in range(8):
                    level = levels[ty * 8 + row][tx * 8 + x]
                    at = tile * 16 + row * 2 + (1 if x < 4 else 0)
                    shift = 6 - 2 * (x % 4)
                    cells[at] |= level << shift
        body += cells
    return bytes(head) + bytes(body) + bytes(widths)


def test_glyph_levels_read_back_the_pixels_of_a_glyph():
    blank = [[0] * 16 for _ in range(16)]
    marked = [[0] * 16 for _ in range(16)]
    marked[0][0] = 3
    marked[15][15] = 2
    data = _font_bin([blank, marked], [4, 9])
    assert gen4_glyphs.glyph_widths(data) == [4, 9]
    levels = gen4_glyphs.glyph_levels(data, 1)
    assert levels[0][0] == 3 and levels[15][15] == 2
    assert levels[0][1] == 0
    with pytest.raises(ValueError):
        gen4_glyphs.glyph_levels(data, 2)


def test_windows_name_the_font_and_box_of_each_game_and_nothing_else():
    assert mp.WINDOWS["CPUE"] == mp.Window("graphic/pl_font.narc", 1, 216)
    assert mp.WINDOWS["IPKE"].font_narc == "a/0/1/6"
    assert mp.WINDOWS["ADAE"].box_px == 216
    assert "BOGUS" not in mp.WINDOWS
    assert mp.LINES_PER_PAGE == 2 and mp.WIDEST_BOX_PX == 216


def _project(tmp_path, code: bytes):
    """A source folder with only the ROM header the window read needs: the game code at 0x0C."""
    root = tmp_path / "src"
    (root / "rom").mkdir(parents=True)
    (root / "rom" / "base.nds").write_bytes(b"\0" * 0x0C + code + b"\0" * 8)
    return root


def test_the_resolver_reads_the_window_of_a_game_on_a_worker(qtbot, tmp_path):
    root = _project(tmp_path, b"CPUE")
    worker = mp.WindowResolver(str(root))
    with qtbot.waitSignal(worker.resolved, timeout=5000) as blocker:
        worker.start()
    folder, resolved = blocker.args[0]
    assert folder == str(root)
    assert resolved.window == mp.WINDOWS["CPUE"]
    assert resolved.font is None                      # no unpacked font in this folder
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)


def test_a_game_without_window_facts_resolves_to_none(qtbot, tmp_path):
    root = _project(tmp_path, b"BOGU")
    worker = mp.WindowResolver(str(root))
    with qtbot.waitSignal(worker.resolved, timeout=5000) as blocker:
        worker.start()
    assert blocker.args[0] == (str(root), None)
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)


def test_the_widget_takes_only_its_own_folder_and_draws_the_text_with_the_font(qtbot, tmp_path):
    blank = [[0] * 16 for _ in range(16)]
    font = _font_bin([blank] * 509, [20] * 509)     # every charmap code has a width, so a long line overflows
    widget = mp.MessageWindowPreview(str(tmp_path))
    qtbot.addWidget(widget)
    widget.receive((str(tmp_path / "other"), mp.Resolved(mp.WINDOWS["CPUE"], font, mp.charmap_for(""))))
    assert widget._face is None
    widget.receive((str(tmp_path), mp.Resolved(mp.Window("x", 1, 192), font, mp.charmap_for(""))))
    assert widget._face is not None and widget._box_px == 192
    widget.update_preview_text("A line that is far too long for a box this narrow, so it runs past its edge")
    assert widget._overflow is True
    widget.shutdown()


def test_real_platinum_box_is_drawn_with_the_game_font(qtbot):
    source = romhacking_root.path("Pokemon", "Platinum", "source")
    reason = romhacking_root.missing("Pokemon", "Platinum", "source", "graphic", "pl_font.narc")
    if reason:
        pytest.skip(reason)
    # The zt-made folder has no rom/base.nds, so the game code is not read here: the window is given by hand.
    font = mp.load_font(str(source), "graphic/pl_font.narc", 1)
    assert font is not None and gen4_glyphs.is_font_bin(font)
    resolved = mp.Resolved(mp.WINDOWS["CPUE"], font, mp.charmap_for(str(source)))
    widget = mp.MessageWindowPreview(str(source))
    qtbot.addWidget(widget)
    widget.receive((str(source), resolved))
    widget.update_preview_text("Hello there!\\nWelcome.\\r")
    assert widget._overflow is False
    widget.update_preview_text("A line that is far too long for the box, so it runs past the right edge of it")
    assert widget._overflow is True
    widget.shutdown()


class _Gen5Stub:
    """Only what ``_Gen5Face`` reads: the code map, the cell width and 12 x 16 two-bit glyphs (48 bytes each)."""

    cell_width = 12

    def __init__(self, glyphs):
        self.glyphs = glyphs

    def codes(self):
        return {ord("A"): 0, ord("i"): 1, ord(" "): 2, ord(","): 3}


def _gen5_glyph(left: int, width: int, advance: int, ink_row1_col0: int = 0) -> bytes:
    """Row 0 holds (left, width, advance), one byte each; row 1 column 0 may carry ink."""
    value = left << 376 | width << 368 | advance << 360
    value |= ink_row1_col0 << (384 - 2 * (12 + 1))
    return value.to_bytes(48, "big")


def test_gen5_row_zero_gives_the_advance_and_the_left_offset_of_each_glyph():
    glyphs = [_gen5_glyph(0, 6, 6, ink_row1_col0=3), _gen5_glyph(0, 2, 3), _gen5_glyph(4, 0, 4),
              _gen5_glyph(1, 3, 5)]
    face = mp._Gen5Face(_Gen5Stub(glyphs))
    assert face.advance("A") == 6 and face.advance("i") == 3 and face.advance(" ") == 4
    assert face.advance(",") == 5 and face.shift(",") == 1 and face.shift("A") == 0
    assert face.shift(" ") == 4 and face.advance("Q") is None and face.shift("Q") == 0
    levels = face.levels("A")
    assert len(levels) == 16 and all(len(row) == 12 for row in levels)
    assert levels[0] == [0] * 12                        # row 0 is the widths, not drawn
    assert levels[1][0] == 3                            # row 1 is ink
