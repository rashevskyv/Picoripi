"""Yo-kai Watch fonts and textures through the plugin's source lists, on the game's own files."""
import json
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "yokai_watch"
WORKSPACES = Path(r"E:\Emulators\RomHacking\Yo-kai Watch")
SOURCE = WORKSPACES / "Yo-kai Watch" / "3DS" / "source"
SOURCE_3 = WORKSPACES / "Yo-kai Watch 3" / "source"


def _project(source, tmp_path):
    return {"source_path": str(source), "translation_path": str(tmp_path), "is_directory_mode": True}


def _needs(source):
    if not (source / "fnt/ft_nrm.xf").is_file():
        pytest.skip(f"needs the workspace {source.parent}")


@pytest.mark.parametrize("source", [SOURCE, SOURCE_3], ids=["yw1", "yw3"])
def test_every_game_font_opens_and_packs_back_unchanged(source, tmp_path):
    _needs(source)
    found = font_sources.resolve(json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8")),
                                 _project(source, tmp_path))
    assert sorted(s.name for s in found) == sorted(p.name for p in (source / "fnt").glob("*.xf"))
    for font in found:
        raw = font.read_original()
        metadata, sheets = font_formats.extract(font.format, raw)
        assert font_formats.pack(font.format, metadata, sheets, raw) == raw, font.label


# Resolving decodes every texture: YW1's 594 take over a minute, YW3's 5817 about seven, writing back twice that.
@pytest.mark.performance
@pytest.mark.timeout(3600)
@pytest.mark.parametrize("source, listing, least, formats", [
    (SOURCE, "texture_sources.json", 594, {"RGBA8", "RGBA4", "ETC1", "ETC1A4"}),
    (SOURCE_3, "yw3_texture_sources.json", 5817,
     {"ETC1A4", "RGBA4", "ETC1", "RGB565", "RGBA8", "L8", "A8", "LA8", "LA4", "RGB8"}),
], ids=["yw1", "yw3"])
def test_every_text_texture_reads_and_writes_back_unchanged(source, listing, least, formats, tmp_path):
    _needs(source)
    found = texture_sources.resolve(json.loads((PLUGIN / listing).read_text(encoding="utf-8")),
                                    _project(source, tmp_path))
    assert len(found) >= least
    seen = set()
    for texture_source in found:
        texture = texture_source.read_original()
        seen.add(texture.pixel_format)
        assert texture_source.write(texture.image) is False, texture_source.label
    assert formats <= seen
    assert not any(tmp_path.iterdir())


def test_each_game_has_its_own_texture_list(tmp_path, monkeypatch):
    from plugins.yokai_watch.rules import GameRules
    rules = GameRules()
    (tmp_path / "data/txt/ev/en").mkdir(parents=True)
    monkeypatch.setattr(GameRules, "_source_root", lambda self: tmp_path)
    assert rules.get_texture_sources()[0]["path"] == "data/menu/title_*_en.xa"
    monkeypatch.setattr(GameRules, "_source_root", lambda self: None)
    assert rules.get_texture_sources()[0]["path"] == "data/menu/skill_telop/en/*.xi"
