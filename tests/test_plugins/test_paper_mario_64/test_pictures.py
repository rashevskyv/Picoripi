"""Paper Mario (N64) pictures from the port's archive: the raw source files open and write back byte for byte,
and the picture source list names every file with its format (skipped where the workspace is not here)."""
import json
from pathlib import Path

import pytest

from core import texture_formats

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "paper_mario_64"
SOURCE = Path(r"E:\Emulators\RomHacking\Paper Mario\Paper Mario 64\N64-PC-port with ISO\source\texture")


def _sources():
    return json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))


def test_texture_sources_name_seven_pictures_in_their_formats():
    entries = _sources()
    assert len(entries) == 7
    formats = {e["params"]["pixel_format"] for e in entries}
    assert formats == {"n64:RGBA16", "n64:RGBA32", "n64:IA8"}
    assert all(e["format"] == "raw" for e in entries)


@pytest.mark.parametrize("entry", _sources(), ids=lambda e: e["path"])
def test_real_picture_round_trips_byte_exact(entry):
    path = SOURCE / Path(entry["path"]).name
    if not path.is_file():
        pytest.skip("the Paper Mario workspace is not on this machine")
    data = path.read_bytes()
    params = dict(entry["params"])
    textures = texture_formats.read("raw", data, params)
    assert textures[0].image.size == (params["width"], params["height"])
    assert texture_formats.write("raw", data, {0: textures[0].image}, params) == data
