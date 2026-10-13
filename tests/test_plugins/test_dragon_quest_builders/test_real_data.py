"""Dragon Quest Builders 1 and 2 on the user's own unpacked workspaces (skipped without them): every table
saves back byte for byte and takes an edit, every Phyre texture / font and every G1T picture writes back
unchanged, and the workspace build (zt/dqb.py) puts a changed file into a copy of the archive while every other
entry stays."""
import romhacking_root
import importlib
import json
import sys
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import char_map
from plugins.dragon_quest_builders import excel
from plugins.dragon_quest_builders.rules import GameRules

B1 = romhacking_root.under('Dragon Quest\\Builders\\Switch')
B2 = romhacking_root.under('Dragon Quest\\Builders 2\\Switch')
SCRIPTS = romhacking_root.under('_shared\\scripts')


def _source(ws: Path, probe: str) -> Path:
    if not (ws / "source" / probe).exists():
        pytest.skip(f"{ws.parent.name} not unpacked")
    return ws / "source"


def _zt():
    if not SCRIPTS.is_dir():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("zt.dqb")


def _check_tables(paths):
    lines = 0
    for path in paths:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert blocks[0], path
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        if excel.is_pack(raw):
            texts = excel.pack_texts(raw)
            edited = [t + "!" if i % 5 == 0 else t for i, t in enumerate(texts)]
            out = excel.pack_write(raw, edited)
            assert excel.pack_texts(out) == edited and len(excel.unpack_tables(out)) == len(excel.unpack_tables(raw)), path
        else:
            table = excel.parse(raw)
            edited = [t + "!" if i % 5 == 0 else t for i, t in enumerate(table.texts())]
            out = excel.write(table, edited)
            again = excel.parse(out)
            assert again.texts() == edited and again.columns == table.columns, path
        lines += len(blocks[0])
    return lines


def test_builders_1_every_table_round_trips_and_takes_an_edit():
    paths = sorted((_source(B1, "excel") / "excel" / "excel").glob("*.en.bin"))
    assert len(paths) == 17
    assert _check_tables(paths) > 17000


def test_builders_1_pictures_and_fonts_write_back_unchanged():
    source = _source(B1, "build")
    pictures = sorted((source / "build" / "gra").rglob("*.phyre"))
    fonts = [p for p in pictures if ".fgen." in p.name]
    textures = [p for p in pictures if p not in fonts]
    assert len(fonts) == 4 and len(textures) >= 82
    packs = [p for p in textures if p.name.startswith(("uitex", "uiicon"))]
    assert len(packs) == 2
    for path in textures:
        raw = path.read_bytes()
        found = texture_formats.read("phyre", raw)
        assert len(found) == (345 if path.name.startswith("uitex") else 980 if path.name.startswith("uiicon") else 1)
        assert texture_formats.write("phyre", raw, {k: t.image for k, t in enumerate(found)}) == raw, path
    for path in fonts:
        raw = path.read_bytes()
        assert font_formats.detect(raw) == "phyre_bmf"
        metadata, sheets = font_formats.extract("phyre_bmf", raw)
        assert font_formats.pack("phyre_bmf", metadata, sheets, raw) == raw, path


def test_builders_2_every_table_round_trips_and_takes_an_edit():
    source = _source(B2, "LINKDATA") / "LINKDATA" / "text"
    paths = sorted(source.glob("*.dqbp"))
    assert 20 < len(paths) < 200
    assert sum(len(excel.unpack_tables(p.read_bytes())) for p in paths) > 4000
    assert _check_tables(paths) > 80000


def test_builders_2_font_pictures_and_build():
    zt = _zt()
    root = _source(B2, "LINKDATA") / "LINKDATA"
    for path in sorted((root / "texture").glob("*.g1t"))[:20] + [root / "font" / "00598.g1t"]:
        raw = path.read_bytes()
        for index, texture in enumerate(texture_formats.read("g1t", raw)):
            assert texture_formats.write("g1t", raw, {index: texture.image}) == raw, path
    sources = json.loads((Path(__file__).parents[3] / "plugins" / "dragon_quest_builders" / "font_sources.json").read_text())
    params = next(s["params"] for s in sources if s["path"].endswith("00598.g1t"))
    raw = (root / "font" / "00598.g1t").read_bytes()
    metadata, sheets = font_formats.extract("texture_grid", raw, params)
    assert font_formats.pack("texture_grid", metadata, sheets, raw, params) == raw
    assert "A" in char_map(metadata) and "z" in char_map(metadata)
    # the original archives read through the workspace script's readers
    old = zt.LinkData(B2 / "romfs" / "LINKDATA.IDX", B2 / "romfs" / "LINKDATA.BIN")
    try:
        pack = sorted((root / "text").glob("*.dqbp"))[0]
        for index, data in excel.unpack_tables(pack.read_bytes()):
            assert old.read(index) == data
        assert old.read(598) == (root / "font" / "00598.g1t").read_bytes()
    finally:
        old.close()
    arc = zt.NxArc(B1 / "romfs" / "binary" / "excel.nxarc")
    assert arc.get("excel/Text.en.bin") == (B1 / "source" / "excel" / "excel" / "Text.en.bin").read_bytes()
