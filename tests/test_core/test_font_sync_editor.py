"""The save of a linked font pair (tools/bfn_editor/io_format_mixin.sync_on_save) on synthetic fonts.

A font file's "bytes" are a token that stands for its model: the BFN reader and writer are replaced by a
registry, so no game data is needed. Covers the copy of a drawing on save, a revert, and a stale copy that must
not bring an old drawing back.
"""
import pytest
from PIL import Image

from core.font_formats import glyph_sync as gs
from core.font_formats import map_entries
from tools.bfn_editor import io_format_mixin as mixin

REGISTRY = {}


def token(model):
    key = b"font-%d" % len(REGISTRY)
    REGISTRY[key] = model
    return key


def font():
    sheet = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for glyph in (0, 1):
        for x in range(6):
            for y in range(5):
                sheet.putpixel((glyph * 10 + x, y), (255, 255, 255, 255))
    metadata = {
        "GLY1": [{"start_glyph": 0, "end_glyph": 7, "cell_width": 10, "cell_height": 10,
                  "glyph_horizontal_count": 4, "glyph_vertical_count": 2, "texture_format": 2}],
        "MAP1": [map_entries([(ord("A"), 0), (ord("B"), 1)])],
        "WID1": [{"first_code_included": 0, "last_code_included": 7,
                  "packets": [{"kerning": 0, "width": 6} for _ in range(8)], "glyph_widths": [6] * 8}],
    }
    return metadata, [sheet]


def paint(model, char, colour=(0, 0, 0, 255)):
    metadata, sheets = model
    glyph = gs.char_map(metadata)[char]
    sheet, x, y, _w, _h = gs._cell_box(metadata, glyph)
    for xx in range(6):
        for yy in range(5):
            sheets[sheet].putpixel((x + xx, y + yy), colour)
    return model


def blank(model, char):
    metadata, sheets = model
    glyph = gs.char_map(metadata)[char]
    sheet, x, y, w, h = gs._cell_box(metadata, glyph)
    sheets[sheet].paste((0, 0, 0, 0), (x, y, x + w, y + h))
    return model


def hashes(file_bytes):
    return gs.glyph_hashes(REGISTRY[bytes(file_bytes)])


class Copy:
    """A font file holding a token; ``sync_partner`` is the other copy of the pair."""

    def __init__(self, label, model):
        self.label, self.format, self.sync_partner = label, "bfn", None
        self.data = token(model)

    def read_current(self):
        return self.data

    def write(self, data):
        self.data = bytes(data)


@pytest.fixture(autouse=True)
def registry_reader_writer(monkeypatch):
    monkeypatch.setattr(mixin, "read_bfn_model", lambda data: REGISTRY[bytes(data)])
    monkeypatch.setattr(mixin, "write_bfn_model", lambda *model: token(model))


def save(source, partner, model, loaded, state_path, now):
    """One save of ``source`` whose edited model is ``model``, as the editor's job does it."""
    final, partner_bytes, taken, given = mixin.sync_on_save(source, partner, token(model), loaded, str(state_path), now)
    source.write(final)
    if partner_bytes is not None:
        partner.write(partner_bytes)
    return taken, given


def test_a_drawing_is_copied_on_save_and_reported(tmp_path):
    state_path = tmp_path / gs.STATE_FILE
    a, b = Copy("A", font()), Copy("B", font())
    drawn = paint(font(), "A")
    taken, given = save(a, b, drawn, hashes(a.data), state_path, now=1.0)
    assert given == ["A"] and taken == []
    assert hashes(b.data)["A"] == gs.glyph_hashes(drawn)["A"]


def test_a_revert_is_a_change_and_is_copied_too(tmp_path):
    state_path = tmp_path / gs.STATE_FILE
    a, b = Copy("A", font()), Copy("B", font())
    drawn = paint(font(), "A")
    save(a, b, drawn, hashes(a.data), state_path, now=1.0)
    reverted = blank(font(), "A")
    taken, given = save(a, b, reverted, gs.glyph_hashes(drawn), state_path, now=2.0)
    assert given == ["A"]
    assert hashes(b.data)["A"] == gs.glyph_hashes(reverted)["A"]


def test_a_stale_copy_with_no_change_does_not_bring_back_an_old_drawing(tmp_path):
    state_path = tmp_path / gs.STATE_FILE
    a, b = Copy("A", font()), Copy("B", font())
    drawn = paint(font(), "A")
    save(a, b, drawn, hashes(a.data), state_path, now=1.0)            # B's file: the drawing
    reverted = blank(font(), "A")
    save(a, b, reverted, gs.glyph_hashes(drawn), state_path, now=2.0)  # B's file: the revert
    # B was opened while it still had the drawing; it has no change of its own and saves now
    stale = Copy("B", paint(font(), "A"))
    taken, given = save(stale, a, REGISTRY[bytes(stale.data)], hashes(stale.data), state_path, now=3.0)
    assert taken == ["A"] and given == []
    assert hashes(stale.data)["A"] == gs.glyph_hashes(blank(font(), "A"))["A"]


def test_a_copy_that_saves_without_changes_gives_nothing(tmp_path):
    state_path = tmp_path / gs.STATE_FILE
    a, b = Copy("A", font()), Copy("B", font())
    before = hashes(b.data)
    taken, given = save(a, b, font(), hashes(a.data), state_path, now=1.0)
    assert taken == [] and given == []
    assert hashes(b.data) == before
