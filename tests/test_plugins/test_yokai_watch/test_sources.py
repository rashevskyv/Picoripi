"""Yo-kai Watch fonts and textures through the plugin's source lists, on the game's own files."""
import json
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "yokai_watch"
SOURCE = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch\3DS\source")
needs_game = pytest.mark.skipif(not (SOURCE / "fnt/ft_nrm.xf").is_file(), reason="needs the Yo-kai Watch workspace")


def _project(tmp_path):
    return {"source_path": str(SOURCE), "translation_path": str(tmp_path), "is_directory_mode": True}


@needs_game
def test_every_game_font_opens_and_packs_back_unchanged(tmp_path):
    found = font_sources.resolve(json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8")),
                                 _project(tmp_path))
    assert sorted(s.name for s in found) == sorted(p.name for p in (SOURCE / "fnt").glob("*.xf"))
    for source in found:
        raw = source.read_original()
        metadata, sheets = font_formats.extract(source.format, raw)
        assert font_formats.pack(source.format, metadata, sheets, raw) == raw, source.label


@pytest.mark.performance            # resolving the 594 textures takes over a minute
@pytest.mark.timeout(600)
@needs_game
def test_every_text_texture_reads_and_writes_back_unchanged(tmp_path):
    found = texture_sources.resolve(json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8")),
                                    _project(tmp_path))
    assert len(found) >= 594
    formats = set()
    for source in found:
        texture = source.read_original()
        formats.add(texture.pixel_format)
        assert source.write(texture.image) is False, source.label
    assert {"RGBA8", "RGBA4", "ETC1", "ETC1A4"} <= formats
    assert not any(tmp_path.iterdir())
