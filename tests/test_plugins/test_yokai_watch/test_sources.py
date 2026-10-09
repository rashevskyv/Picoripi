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
SOURCE_NX = WORKSPACES / "Yo-kai Watch" / "Switch" / "source"
SOURCE_2 = WORKSPACES / "Yo-kai Watch 2" / "source"


def _project(source, tmp_path):
    return {"source_path": str(source), "translation_path": str(tmp_path), "is_directory_mode": True}


def _needs(source):
    if not (source / "fnt/ft_nrm.xf").is_file():
        pytest.skip(f"needs the workspace {source.parent}")


@pytest.mark.parametrize("source", [SOURCE, SOURCE_2, SOURCE_3, SOURCE_NX], ids=["yw1", "yw2", "yw3", "ywnx"])
def test_every_game_font_opens_and_packs_back_unchanged(source, tmp_path):
    _needs(source)
    found = font_sources.resolve(json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8")),
                                 _project(source, tmp_path))
    assert sorted(s.name for s in found) == sorted(p.name for p in (source / "fnt").glob("*.xf"))
    for font in found:
        raw = font.read_original()
        metadata, sheets = font_formats.extract(font.format, raw)
        assert font_formats.pack(font.format, metadata, sheets, raw) == raw, font.label


# Resolving decodes every texture: YW1's 594 take over a minute, YW3's 5817 about seven, YW2's 2683 about five,
# writing back twice that.
@pytest.mark.performance
@pytest.mark.timeout(3600)
@pytest.mark.parametrize("source, listing, least, formats", [
    (SOURCE, "texture_sources.json", 594, {"RGBA8", "RGBA4", "ETC1", "ETC1A4"}),
    (SOURCE_3, "yw3_texture_sources.json", 5817,
     {"ETC1A4", "RGBA4", "ETC1", "RGB565", "RGBA8", "L8", "A8", "LA8", "LA4", "RGB8"}),
    (SOURCE_NX, "ywnx_texture_sources.json", 679, {"RGBA8", "RGBA4", "BC3"}),
    (SOURCE_2, "yw2_texture_sources.json", 2683,
     {"RGBA8", "RGBA4", "ETC1A4", "LA8", "RGB565", "LA4", "ETC1", "RGB8", "L8", "A8", "L4"}),
], ids=["yw1", "yw3", "ywnx", "yw2"])
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
    (tmp_path / "data/txt/ev/en").rmdir()
    (tmp_path / "data/res/text").mkdir(parents=True)
    (tmp_path / "data/res/text/system_text_ja.cfg.bin").write_bytes(b"")
    assert rules.get_texture_sources()[0]["path"] == "data/menu/*.xa"
    monkeypatch.setattr(GameRules, "_source_root", lambda self: None)
    assert rules.get_texture_sources()[0]["path"] == "data/menu/skill_telop/en/*.xi"


SOURCE_YW4 = WORKSPACES / "Yo-kai Watch 4" / "source"
SOURCE_YAY = WORKSPACES / "Yo-kai Academy Y" / "source"


@pytest.mark.parametrize("source, listing, count", [
    (SOURCE_YW4, "yw4_font_sources.json", 4), (SOURCE_YAY, "yay_font_sources.json", 7)], ids=["yw4", "yay"])
def test_g4_fonts_open_pack_back_unchanged_and_save_both_files(source, listing, count, tmp_path):
    """Yo-kai Watch 4++ / Academy Y: font.cfg.bin with its font.g4tx (the companion) in one model."""
    if not (source / "data/common/font/font/font_ja/font.cfg.bin").is_file():
        pytest.skip(f"needs the workspace {source.parent}")
    found = font_sources.resolve(json.loads((PLUGIN / listing).read_text(encoding="utf-8")),
                                 _project(source, tmp_path))
    assert len(found) == count and all(s.companion_source for s in found)
    for font in found:
        raw = font.read_original()
        metadata, sheets = font_formats.extract(font.format, raw, font.params)
        assert font_formats.pack(font.format, metadata, sheets, raw, font.params) == raw, font.label
    main = found[0]
    raw = main.read_original()
    metadata, sheets = font_formats.extract(main.format, raw, main.params)
    gly = metadata["GLY1"][0]
    glyph = font_formats.char_map(metadata)["A"]
    x, y = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"], (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    sheet = sheets[0].copy()
    sheet.paste((255, 255, 255, 255), (x + 6, y + 10, x + 16, y + 30))
    main.write(font_formats.pack(main.format, metadata, [sheet], raw, main.params))
    assert Path(main.companion_translation).is_file() and Path(main.translation_path).is_file()
    again, again_sheets = font_formats.extract(main.format, main.read_current(), main.params)
    cell = (x, y, x + gly["cell_width"], y + gly["cell_height"])
    assert font_formats.coverage(again_sheets[0]).crop(cell).tobytes() == font_formats.coverage(sheet).crop(cell).tobytes()


# Resolving decodes every listed texture (985 / 721 files, BC7 and RGBA8 up to 4096x2048).
@pytest.mark.performance
@pytest.mark.timeout(3600)
@pytest.mark.parametrize("source, listing, least", [
    (SOURCE_YW4, "yw4_texture_sources.json", 985), (SOURCE_YAY, "yay_texture_sources.json", 721)], ids=["yw4", "yay"])
def test_g4tx_text_textures_read_and_write_back_unchanged(source, listing, least, tmp_path):
    if not (source / "data/nx/menu").is_dir():
        pytest.skip(f"needs the workspace {source.parent}")
    found = texture_sources.resolve(json.loads((PLUGIN / listing).read_text(encoding="utf-8")),
                                    _project(source, tmp_path))
    assert len({s.source_path for s in found}) >= least
    seen = set()
    for texture_source in found:
        texture = texture_source.read_original()
        seen.add(texture.pixel_format)
        assert texture_source.write(texture.image) is False, texture_source.label
    assert {"RGBA8", "BC7"} <= seen
    assert not any(tmp_path.iterdir())


def test_switch_sequels_have_their_own_font_and_texture_lists(tmp_path, monkeypatch):
    from plugins.yokai_watch.rules import GameRules
    rules = GameRules()
    monkeypatch.setattr(GameRules, "_source_root", lambda self: tmp_path)
    (tmp_path / "data/common/text/ja").mkdir(parents=True)
    assert rules.get_font_sources()[0]["companion"] == "data/nx/font/font_ja/font.g4tx"
    assert len(rules.get_font_sources()) == 4
    assert rules.get_texture_sources()[0]["format"] == "g4tx"
    (tmp_path / "data/common/font/font/font_ja2").mkdir(parents=True)
    assert len(rules.get_font_sources()) == 7
