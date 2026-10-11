"""Paper Mario (N64) logo pictures: the RGBA16 source files open and write back byte for byte, and the
picture source list names every file (skipped where the workspace is not on this machine)."""
import json
from pathlib import Path

import pytest

from core import texture_formats

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "paper_mario_64"
SOURCE = Path(r"E:\Emulators\RomHacking\Paper Mario\Paper Mario 64\N64-PC-port with ISO\source\texture")


def _sources():
    return json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))


def test_texture_sources_name_three_rgba16_pictures():
    entries = _sources()
    assert len(entries) == 3
    assert all(e["format"] == "raw" and e["params"]["pixel_format"] == "n64:RGBA16" for e in entries)


@pytest.mark.parametrize("entry", _sources(), ids=lambda e: e["path"])
def test_real_logo_round_trips_byte_exact(entry):
    path = SOURCE / Path(entry["path"]).name
    if not path.is_file():
        pytest.skip("the Paper Mario workspace is not on this machine")
    data = path.read_bytes()
    params = dict(entry["params"])
    textures = texture_formats.read("raw", data, params)
    assert textures[0].image.size == (params["width"], params["height"])
    assert texture_formats.write("raw", data, {0: textures[0].image}, params) == data
