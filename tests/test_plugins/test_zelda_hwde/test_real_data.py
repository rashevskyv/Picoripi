"""Hyrule Warriors DE on the game's own files (skipped where the workspace is not on this machine).

Every text file rebuilds byte for byte; an edit reaches the file; every text texture the plugin names
resolves in the workspace's source folder and writes back to the translation folder.
"""
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.texture_formats import sources
from plugins.zelda_hwde.textfile import TextFile

WORKSPACE = Path(r"E:\Emulators\RomHacking\Zelda\Hyrule Warriors DE")
SOURCE = WORKSPACE / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "zelda_hwde"


def _text_files():
    files = sorted(p for p in (SOURCE / "data").rglob("*.bin")) if SOURCE.is_dir() else []
    if not files:
        pytest.skip(f"{SOURCE} is not on this machine")
    return files


def test_every_text_file_rebuilds_byte_exact():
    files = _text_files()
    lines = 0
    for path in files:
        data = path.read_bytes()
        text = TextFile(data)
        texts = text.texts()
        lines += sum(len(block) for block in texts)
        assert text.build(texts) == data, path.name
    assert len(files) == 259 and lines == 53103


def test_an_edit_reaches_the_file():
    path = next(p for p in _text_files() if p.name == "msgdata.bin")
    data = path.read_bytes()
    texts = TextFile(data).texts()
    texts[0][0] = "UA TEST"
    assert TextFile(TextFile(data).build(texts)).texts()[0][0] == "UA TEST"


def test_every_text_texture_resolves_and_writes_back(tmp_path):
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    if not (SOURCE / "data" / "ui" / "title_ENG.g1t.gz").is_file():
        pytest.skip("the workspace has no textures in source (tools/texture_source.py)")
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path),
                                          "is_directory_mode": True})
    assert len(found) == 952
    formats = {f"{s.format} {s.pixel_format}" for s in found}
    assert formats == {"g1t BC1", "g1t BC3", "g1t BC7", "g1t BGRA8", "bntx BC3"}
    picked = {}
    for source in found:
        picked.setdefault(f"{source.format} {source.pixel_format}", source)
    for source in picked.values():
        png = tmp_path / "png" / source.export_name                # export, redraw outside, import
        png.parent.mkdir(exist_ok=True)
        source.read_original().image.save(png)
        with Image.open(png) as exported:
            image = exported.convert("RGBA")
        ImageDraw.Draw(image).rectangle((0, 0, 15, 7), fill=(255, 0, 0, 255))
        assert sources.write_many([(source, image)]) == [source]
        target = Path(source.translation_path)
        assert target.is_relative_to(tmp_path) and target.stat().st_size == Path(source.source_path).stat().st_size
        red, green = source.read_current().image.getpixel((2, 2))[:2]
        assert red > 240 and green < 16                      # BC7 may round 255 to 254
