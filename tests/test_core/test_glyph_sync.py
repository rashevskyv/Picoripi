"""Glyph sync between two identical copies of a bitmap font: change-based, opt-in (synthetic fonts, no game data)."""
from pathlib import Path

from PIL import Image

from core.font_formats import glyph_sync as gs
from core.font_formats import map_entries


def font(fill=(255, 255, 255, 255), cell=(10, 10), codes=("A", "B"), kerning=0, width=6, glyph_count=None):
    """Two glyphs on one sheet: 'A' is glyph 0, 'B' glyph 1; ``fill`` paints the top-left 6x5 of each cell."""
    cw, ch = cell
    sheet = Image.new("RGBA", (cw * 4, ch * 2), (0, 0, 0, 0))
    for glyph in range(len(codes)):
        for x in range(6):
            for y in range(5):
                sheet.putpixel((glyph * cw + x, y), fill)
    metadata = {
        "GLY1": [{"start_glyph": 0, "end_glyph": 7, "cell_width": cw, "cell_height": ch,
                  "glyph_horizontal_count": 4, "glyph_vertical_count": 2, "texture_format": 2}],
        "MAP1": [map_entries([(ord(c), i) for i, c in enumerate(codes)])],
        "WID1": [{"first_code_included": 0, "last_code_included": 7,
                  "packets": [{"kerning": kerning, "width": width} for _ in range(8)],
                  "glyph_widths": [6] * 8}],
    }
    return metadata, [sheet]


def painted(model, char, colour):
    """``model`` with only the 6x5 ink box of ``char`` painted ``colour`` (in place)."""
    metadata, sheets = model
    glyph = gs.char_map(metadata)[char]
    sheet, x, y, _w, _h = gs._cell_box(metadata, glyph)
    for xx in range(6):
        for yy in range(5):
            sheets[sheet].putpixel((x + xx, y + yy), colour)
    return model


def blank_glyph(model, char):
    """Erase the cell of ``char`` in place (a revert to nothing)."""
    metadata, sheets = model
    glyph = gs.char_map(metadata)[char]
    sheet, x, y, w, h = gs._cell_box(metadata, glyph)
    sheets[sheet].paste((0, 0, 0, 0), (x, y, x + w, y + h))


def test_copies_are_identical_only_with_format_size_and_layout():
    a = font()
    assert gs.identical(a, font(fill=(0, 0, 0, 255)), "bfn", "bfn")         # pixels may differ
    assert not gs.identical(a, font(cell=(12, 10)), "bfn", "bfn")          # a different cell size is not a candidate
    assert not gs.identical(a, a, "bfn", "bfn_other")                       # a different format is not either
    assert not gs.identical(a, font(codes=("B", "A")), "bfn", "bfn")       # a different layout is not either


def test_pairs_are_off_by_default():
    pairs = {}
    assert gs.pair_enabled(pairs, "name entry", "file select") is False
    gs.set_pair(pairs, "name entry", "file select", True)
    assert gs.pair_enabled(pairs, "file select", "name entry") is True     # the pair, in either order


def test_a_change_is_copied_to_the_other_copy():
    loaded_a = gs.glyph_hashes(font())
    a = painted(font(), "A", (0, 0, 0, 255))              # A's 'A' glyph was drawn dark
    state = gs.new_state()
    gs.record_changes(state, "A", gs.dirty_codes(loaded_a, a), gs.glyph_hashes(a), now=10.0)
    b = font()
    b, copied = gs.carry(state, "A", a, "B", b)
    assert copied == ["A"]
    assert gs.glyph_hashes(b)["A"] == gs.glyph_hashes(a)["A"]
    assert gs.glyph_hashes(b)["B"] == gs.glyph_hashes(font())["B"]        # nothing else moved


def test_a_revert_is_a_change_and_propagates():
    original = font()
    loaded = gs.glyph_hashes(original)
    state = gs.new_state()
    drawn = painted(font(), "A", (0, 0, 0, 255))
    gs.record_changes(state, "A", gs.dirty_codes(loaded, drawn), gs.glyph_hashes(drawn), now=1.0)
    b, _ = gs.carry(state, "A", drawn, "B", font())
    # A reverts the drawing: the copy saved last is the drawing, the revert is a new change
    reverted = font()
    blank_glyph(reverted, "A")
    loaded_after_save = gs.glyph_hashes(drawn)
    changed = gs.dirty_codes(loaded_after_save, reverted)
    assert changed == ["A"]
    gs.record_changes(state, "A", changed, gs.glyph_hashes(reverted), now=2.0)
    b, copied = gs.carry(state, "A", reverted, "B", b)
    assert copied == ["A"]
    assert gs.glyph_hashes(b)["A"] == gs.glyph_hashes(reverted)["A"]


def test_a_stale_copy_with_no_change_of_its_own_does_not_bring_back_an_old_drawing():
    original = font()
    drawn = painted(font(), "A", (0, 0, 0, 255))
    state = gs.new_state()
    gs.record_changes(state, "A", ["A"], gs.glyph_hashes(drawn), now=1.0)
    # B was opened while it still had the drawing; A then reverted and saved (latest change: A, the original)
    reverted = font()
    gs.record_changes(state, "A", ["A"], gs.glyph_hashes(reverted), now=2.0)
    stale_b = drawn                                      # B's memory: the old drawing, no change of its own
    assert gs.dirty_codes(gs.glyph_hashes(drawn), stale_b) == []
    stale_b, copied = gs.carry(state, "A", reverted, "B", stale_b, skip=[])
    assert copied == ["A"]                              # the newer revert from A replaces the stale drawing
    assert gs.glyph_hashes(stale_b)["A"] == gs.glyph_hashes(original)["A"]


def test_the_latest_change_wins_in_both_directions():
    state = gs.new_state()
    a_draw = painted(font(), "A", (0, 0, 0, 255))
    b_draw = painted(font(), "A", (128, 128, 128, 255))
    gs.record_changes(state, "A", ["A"], gs.glyph_hashes(a_draw), now=1.0)
    gs.record_changes(state, "B", ["A"], gs.glyph_hashes(b_draw), now=2.0)   # B changed it later
    assert state["latest"]["A"]["font"] == "B"
    untouched = font()
    _, copied_to_b = gs.carry(state, "A", a_draw, "B", untouched)
    assert copied_to_b == []                             # A's older change does not overwrite B's newer one
    _, copied_to_a = gs.carry(state, "B", b_draw, "A", font())
    assert copied_to_a == ["A"]


def test_own_changes_are_not_copied_over_by_the_partner():
    state = gs.new_state()
    a_draw = painted(font(), "A", (0, 0, 0, 255))
    gs.record_changes(state, "A", ["A"], gs.glyph_hashes(a_draw), now=1.0)
    _, copied = gs.carry(state, "A", a_draw, "B", font(), skip=["A"])
    assert copied == []


def test_the_state_file_round_trips(tmp_path: Path):
    state = gs.new_state()
    gs.record_changes(state, "A", ["A"], {"A": "abc"}, now=3.5)
    path = tmp_path / gs.STATE_FILE
    gs.save_state(path, state)
    loaded = gs.load_state(path)
    assert loaded["latest"]["A"] == {"font": "A", "time": 3.5, "hash": "abc"}
    assert gs.load_state(tmp_path / "missing.json")["latest"] == {}
