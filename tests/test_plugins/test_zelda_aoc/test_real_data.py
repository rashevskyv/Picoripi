"""Age of Calamity on the developer's own game files (skipped where they are not on this machine).

Unchanged text bundles, fonts and textures must come back byte for byte; an edited texture or font must reach
the mod as a loose asset file that the RDB index points at (``_shared\\scripts\\zt\\aoc.py``, what 2_build runs).
"""
import json
import struct
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.zelda_aoc.aoctext import TextBundle

ROOT = Path(__file__).resolve().parents[3]
RH = Path(r"E:\Emulators\RomHacking")
WS = RH / "Zelda" / "Hyrule Warriors Age of Calamity"
SOURCE = WS / "source"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _descriptors(name: str):
    return json.loads((ROOT / "plugins" / "zelda_aoc" / name).read_text(encoding="utf-8"))


def _zt():
    scripts = _need(RH / "_shared" / "scripts" / "zt" / "aoc.py").parents[1]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from zt import aoc
    return aoc


def test_every_text_bundle_rebuilds_byte_exact():
    bundles = sorted(_need(SOURCE / "text").glob("*.bin")) + sorted(_need(SOURCE / "battle").glob("*.bin"))
    assert len(bundles) == 213
    lines = 0
    for path in bundles:
        data = path.read_bytes()
        bundle = TextBundle(data)
        lines += len(bundle.texts())
        assert bundle.build(bundle.texts()) == data, path.name
    assert lines == 18262


def test_linkdata_rebuilds_byte_exact_and_unchanged_bundles_change_nothing():
    aoc = _zt()
    link = aoc.read_link(_need(WS / "romfs" / "data"))
    assert link.build({}) == (link.info, link.data)
    _info, _data, changed = aoc.pack_text(link, [p.read_bytes() for p in sorted(SOURCE.glob("text/*.bin"))[:20]])
    assert changed == 0


def test_every_font_source_opens_and_packs_back():
    found = font_sources.resolve(_descriptors("font_sources.json"),
                                 {"source_path": str(_need(SOURCE / "font").parent), "translation_path": "",
                                  "is_directory_mode": True})
    assert len(found) == 59
    checked = set()
    for source in found:
        if source.name != "latin.g1n" and source.params["font"]:
            continue  # one size per big CJK file keeps the test quick
        data = source.read_current()
        metadata, sheets = font_formats.extract("g1n", data, source.params)
        assert font_formats.pack("g1n", metadata, sheets, data, source.params) == data
        assert "Ж" not in font_formats.char_map(metadata)       # no game font has Cyrillic
        checked.add(source.name)
    assert len(checked) == 5


def test_every_text_texture_opens_and_an_edit_reads_back():
    found = texture_sources.resolve(_descriptors("texture_sources.json"),
                                    {"source_path": str(_need(SOURCE / "texture").parent), "translation_path": ""})
    assert len({s.source_path for s in found}) == 33
    assert {s.pixel_format for s in found} == {"BC1", "BC3"}
    for path in sorted({s.source_path for s in found}):
        data = Path(path).read_bytes()
        textures = texture_formats.read("g1t", data, {})
        index = max(range(len(textures)), key=lambda i: textures[i].image.width * textures[i].image.height)
        edited = textures[index].image.copy()
        ImageDraw.Draw(edited).rectangle((0, 0, 15, 3), fill=(255, 255, 255, 255))
        new = texture_formats.write("g1t", data, {index: edited}, {})
        assert len(new) == len(data) and new != data
        assert texture_formats.read("g1t", new, {})[index].image.getpixel((1, 1)) == (255, 255, 255, 255)


def test_build_writes_edited_font_and_texture_as_loose_files(tmp_path):
    aoc = _zt()
    asset = _need(WS / "romfs" / "asset")
    translation = tmp_path / "translation"
    for rel, data in (("font/latin.g1n", (SOURCE / "font" / "latin.g1n").read_bytes() + b"\0"),
                      ("texture/0x2633f291.g1t", (SOURCE / "texture" / "0x2633f291.g1t").read_bytes()[:-1] + b"\1")):
        (translation / rel).parent.mkdir(parents=True, exist_ok=True)
        (translation / rel).write_bytes(data)
    out = tmp_path / "asset"
    done = aoc.pack_assets(asset, translation, ["font/latin.g1n", "texture/0x2633f291.g1t", "text/x.bin"], out)
    assert done == ["font/latin.g1n", "texture/0x2633f291.g1t"]
    for rdb_name, ktid, rel in (("RRPreview", 0x825A22F1, "font/latin.g1n"),
                                ("ScreenLayout", 0x2633F291, "texture/0x2633f291.g1t")):   # a DLC-part texture
        rdb = aoc.Rdb((out / f"{rdb_name}.rdb").read_bytes())
        info = aoc.Rdb.fields(rdb.entries[rdb.find(ktid)])
        assert (info["flags"], info["location"]) == (0x10000, "")
        loose = (out / "data" / f"0x{ktid:08x}.file").read_bytes()
        assert aoc.read_fdata(loose) == (translation / rel).read_bytes()
        assert struct.unpack_from("<I", loose, 0x24)[0] == ktid
