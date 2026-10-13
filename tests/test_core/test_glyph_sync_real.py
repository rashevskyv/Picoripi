"""The two Wind Waker copies of the name entry font against the real game files (skipped elsewhere).

Each copy must read and write back byte-exact. A glyph drawn in one copy must reach the other copy by its
code, and nothing else may change: the test copies an existing glyph (cell and width) to another code, then
checks the linked copy in a temporary translation folder. The game's source folder must not change.
"""
import json
from pathlib import Path

import pytest

from core.font_formats import char_map
from core.font_formats import glyph_sync
from core.font_formats.sources import resolve
from tools.bfn_editor.bfn_engine import read_bfn_model, write_bfn_model
from tools.bfn_editor.io_format_mixin import sync_on_save

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r"E:\Emulators\RomHacking\Zelda\Wind Waker\GC\source")
NAME_ENTRY = "Name entry font"
FILE_SELECT = "File select font (a copy of the name entry font)"
MEMBER = "font/rock_24_20_ia4_e.bfn"


@pytest.fixture
def copies(tmp_path):
    """(name entry, file select) font sources, their translation folder under ``tmp_path``."""
    if not SOURCE.exists():
        pytest.skip(f"{SOURCE} is not on this machine")
    descriptors = [entry for entry in json.loads((ROOT / "plugins" / "zelda_tww" / "font_sources.json")
                                                 .read_text(encoding="utf-8"))
                   if entry["label"] in (NAME_ENTRY, FILE_SELECT)]
    found = resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path / "translation"),
                                  "is_directory_mode": True})
    if len(found) != 2:
        pytest.skip("the two font copies are not on this machine")
    return found[0], found[1]


def test_both_copies_decode_and_encode_back_byte_exact(copies):
    for source in copies:
        data = source.read_original()
        metadata, sheets = read_bfn_model(data)
        gly = metadata["GLY1"][0]
        assert len(data) == 148064
        assert (gly["start_glyph"], gly["end_glyph"]) == (0, 224)
        assert (gly["cell_width"], gly["cell_height"]) == (24, 24)
        assert (gly["glyph_horizontal_count"], gly["glyph_vertical_count"]) == (5, 5)
        assert (gly["texture_format"], gly["texture_width"], gly["texture_height"]) == (2, 128, 128)
        assert len(sheets) == 9 and sheets[0].size == (128, 128)
        assert write_bfn_model(metadata, sheets) == data


def test_the_two_copies_are_identical_candidates(copies):
    name, select = copies
    assert glyph_sync.identical(read_bfn_model(name.read_original()), read_bfn_model(select.read_original()),
                                name.format, select.format)


def test_a_changed_glyph_is_copied_to_the_other_copy_on_save(copies, tmp_path):
    name, select = copies
    metadata, sheets = read_bfn_model(name.read_original())
    loaded = glyph_sync.glyph_hashes((metadata, sheets))
    codes = char_map(metadata)
    box_a, box_b = glyph_sync._cell_box(metadata, codes["A"]), glyph_sync._cell_box(metadata, codes["B"])
    cell_b = sheets[box_b[0]].crop((box_b[1], box_b[2], box_b[1] + box_b[3], box_b[2] + box_b[4]))
    sheets[box_a[0]].paste(cell_b, (box_a[1], box_a[2]))               # the name copy's 'A' takes the 'B' pixels
    edited = write_bfn_model(metadata, sheets)
    edited_bytes, partner_bytes, taken, given, _deferred = sync_on_save(name, select, edited, loaded,
                                                            str(tmp_path / glyph_sync.STATE_FILE), now=1.0)
    assert given == ["A"] and taken == []
    partner_model = read_bfn_model(partner_bytes)
    assert glyph_sync.glyph_hashes(partner_model)["A"] == glyph_sync.glyph_hashes((metadata, sheets))["A"]


