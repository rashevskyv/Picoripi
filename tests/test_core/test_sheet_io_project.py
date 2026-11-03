"""The project commands of sheet_io: a font's sheets export, get edited and import through the font editor's write."""
import json
from pathlib import Path

import pytest
from PIL import Image

from core.font_formats import sheet_io
from core.font_formats.sources import resolve

REPO = Path(__file__).resolve().parents[2]
TILE = 16                                   # bytes of one 8x8 snes:2bpp tile


def _grid_descriptor(chars):
    params = {"texture": "raw", "cell": [8, 8], "chars": chars,
              "texture_params": {"pixel_format": "snes:2bpp", "offset": 0, "width": 16, "height": 8}}
    return {"label": "Test font: two cells", "format": "texture_grid", "path": "gfx/font.bin", "params": params}


def _project(tmp_path: Path, data: bytes, descriptors):
    source = tmp_path / "source"
    (source / "gfx").mkdir(parents=True)
    (source / "gfx" / "font.bin").write_bytes(data)
    translation = tmp_path / "translation"
    translation.mkdir()
    metadata = {"source_path": str(source), "translation_path": str(translation), "is_directory_mode": True}
    return metadata, translation


def test_the_super_metroid_message_font_round_trips_unchanged(tmp_path: Path):
    # The plugin's own descriptor and params: 128x128 2bpp, 256 cells. An unedited import gives the same bytes.
    descriptors = json.loads((REPO / "plugins" / "super_metroid" / "font_sources.json").read_text(encoding="utf-8"))
    descriptor = descriptors[0]
    data = bytes((i * 37 + 11) % 256 for i in range(4096))
    folder = tmp_path / "sheets"
    sheet_io.export_sheets(descriptor["format"], data, folder, "bg3_font.bin", descriptor["params"])
    out = sheet_io.import_sheets(descriptor["format"], data, folder, "bg3_font.bin", descriptor["params"])
    assert out == data


def test_an_edited_cell_is_written_and_the_other_cells_stay_as_they_were(tmp_path: Path):
    descriptor = _grid_descriptor(["A", "B"])
    data = bytes([0x0F] * 8 + [0xF0] * 8) + bytes([0x55] * 8 + [0xAA] * 8)    # tile 0 and tile 1, two planes each
    metadata, translation = _project(tmp_path, data, [descriptor])
    source = sheet_io.find_source(resolve([descriptor], metadata), "Test font: two cells")
    folder = tmp_path / "sheets"
    sheet_io.export_source(source, folder)
    clean = folder / "font_bin_sheet_0.png"
    image = Image.open(clean).convert("RGBA")
    image.putpixel((8, 0), (255, 255, 255, 255))            # a pixel of cell 1, the top-left one
    image.save(clean)
    target = sheet_io.import_source(source, folder)
    written = target.read_bytes()
    assert target == translation / "gfx" / "font.bin"
    assert written[:TILE] == data[:TILE]                    # cell 0 is untouched
    assert written[TILE:] != data[TILE:]                    # cell 1 changed
    assert written[TILE + 1] & 0x80                         # the edited pixel set in the first plane
    assert not list(translation.glob("*.bak_*"))            # nothing was there before


def test_an_overwritten_translation_copy_is_backed_up_first(tmp_path: Path):
    descriptor = _grid_descriptor(["A", "B"])
    data = bytes(TILE * 2)
    metadata, translation = _project(tmp_path, data, [descriptor])
    source = sheet_io.find_source(resolve([descriptor], metadata), "Test font: two cells")
    folder = tmp_path / "sheets"
    sheet_io.export_source(source, folder)
    sheet_io.import_source(source, folder)
    (translation / "gfx" / "font.bin").write_bytes(b"\x01" * (TILE * 2))   # an earlier edit, now to be replaced
    sheet_io.import_source(source, folder)
    backups = list((translation / "gfx").glob("font.bin.bak_*"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"\x01" * (TILE * 2)


def test_a_label_prefix_must_name_exactly_one_font(tmp_path: Path):
    descriptors = [_grid_descriptor(["A", "B"]), dict(_grid_descriptor(["C"]), label="Test font: other")]
    metadata, _ = _project(tmp_path, bytes(TILE * 2), descriptors)
    sources = resolve(descriptors, metadata)
    assert sheet_io.find_source(sources, "Test font: t").label == "Test font: two cells"
    with pytest.raises(ValueError):
        sheet_io.find_source(sources, "Test font: ")
