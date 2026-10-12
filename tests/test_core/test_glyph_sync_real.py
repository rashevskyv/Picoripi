"""The two Wind Waker copies of the name entry font against the real game files (skipped elsewhere).

Each copy must read and write back byte-exact. A glyph drawn in one copy must reach the other copy by its
code, and nothing else may change: the test copies an existing glyph (cell and width) to another code, then
checks the linked copy in a temporary translation folder. The game's source folder must not change.
"""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from core.font_formats import char_map
from core.font_formats.glyph_sync import copy_glyphs
from core.font_formats.sources import resolve
from core.texture_formats.sources import open_container
from tools.bfn_editor.bfn_engine import read_bfn_model, write_bfn_model
from tools.bfn_editor.io_format_mixin import sync_linked_bfn

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


def _glyph(model, index):
    """(cell pixels, kerning, width) of a glyph of a decoded model."""
    metadata, sheets = model
    gly = metadata["GLY1"][0]
    columns, rows = gly["glyph_horizontal_count"], gly["glyph_vertical_count"]
    sheet, cell = divmod(index - gly["start_glyph"], columns * rows)
    width, height = gly["cell_width"], gly["cell_height"]
    x, y = (cell % columns) * width, (cell // columns) * height
    packet = metadata["WID1"][0]["packets"][index - metadata["WID1"][0]["first_code_included"]]
    return sheets[sheet].crop((x, y, x + width, y + height)).tobytes(), packet["kerning"], packet["width"]


def _leaves(raw, prefix=""):
    """{path: bytes} of every file in an archive, going into nested RARC archives."""
    if raw[:4] != b"RARC":
        return {prefix: raw}
    container, found = open_container(raw), {}
    for name in container.list_files():
        found.update(_leaves(container.read_file(name), f"{prefix}/{name}" if prefix else name))
    return found


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def test_the_unedited_copies_give_nothing_to_copy(copies):
    name, select = copies
    edited_original = read_bfn_model(name.read_original())
    other_original = read_bfn_model(select.read_original())
    copied, report = copy_glyphs(edited_original, edited_original, other_original, other_original)
    assert copied is None
    assert report.shared == 224 and report.copied == [] and report.conflicts == [] and report.skipped == {}


def test_a_glyph_copied_to_the_name_entry_copy_reaches_the_file_select_copy(copies, tmp_path):
    name, select = copies
    assert name.sync_partner is select and select.sync_partner is name
    sources_before = {path: _sha(path) for path in (name.source_path, select.source_path)}

    pristine = read_bfn_model(name.read_original())
    metadata, sheets = read_bfn_model(name.read_original())
    original = read_bfn_model(select.read_original())
    codes = char_map(metadata)
    glyph_a, glyph_b = codes["A"], codes["B"]
    # The mark: the glyph of 'A' (cell and width) is put on the code 'B' in the name entry copy.
    cell_a, kerning_a, width_a = _glyph(pristine, glyph_a)
    gly = metadata["GLY1"][0]
    per_sheet = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    sheet, index = divmod(glyph_b - gly["start_glyph"], per_sheet)
    x, y = (index % gly["glyph_horizontal_count"]) * 24, (index // gly["glyph_horizontal_count"]) * 24
    sheets[sheet].paste(Image.frombytes("RGBA", (24, 24), cell_a), (x, y))
    metadata["WID1"][0]["packets"][glyph_b]["width"] = width_a
    metadata["WID1"][0]["packets"][glyph_b]["kerning"] = kerning_a
    edited = write_bfn_model(metadata, sheets)

    name.write(edited)
    report = sync_linked_bfn(name, select, edited)

    assert report.copied == ["B"] and report.conflicts == [] and report.skipped == {}
    result = read_bfn_model(select.read_current())
    assert _glyph(result, glyph_b) == (cell_a, kerning_a, width_a)
    for char, glyph in codes.items():
        if char != "B":
            assert _glyph(result, glyph) == _glyph(original, glyph), char
    # The other members of both archives are byte-exact; only the font member changed.
    for source, translated in ((name, name.translation_path), (select, select.translation_path)):
        before = _leaves(Path(source.source_path).read_bytes())
        after = _leaves(Path(translated).read_bytes())
        assert before.keys() == after.keys()
        changed = [path for path in before if before[path] != after[path]]
        assert [path.rsplit("/", 1)[-1] for path in changed] == ["rock_24_20_ia4_e.bfn"]
    assert {path: _sha(path) for path in sources_before} == sources_before
