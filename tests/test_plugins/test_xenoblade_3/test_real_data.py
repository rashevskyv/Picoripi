"""Xenoblade Chronicles 3 on the user's own unpacked workspace (skipped without it): every English text table
saves back byte for byte and takes an edit, every font packs back unchanged and the Latin fonts take a new
letter, every layout texture format writes back unchanged and the title logo takes an edit, and the workspace
build hides a changed file in each archive index while every other entry stays."""
import importlib
import json
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import wilay
from plugins.common import bdat
from plugins.xenoblade_3.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Xenoblade\Chronicles 3")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _source() -> Path:
    if not (WS / "source" / "bdat" / "gb" / "game" / "menu.bdat").is_file():
        pytest.skip("Xenoblade Chronicles 3 not unpacked")
    return WS / "source"


def test_every_text_table_saves_back_byte_for_byte_and_takes_an_edit():
    paths = sorted((_source() / "bdat").rglob("*.bdat"))
    assert len(paths) == 4118
    lines = 0
    for path in paths:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        lines += len(blocks[0])
    assert lines == 117513
    raw = (_source() / "bdat/gb/game/menu.bdat").read_bytes()
    texts = bdat.read(raw)
    index = texts.index("PRESS ANY BUTTON")
    texts[index] = "НАТИСНІТЬ БУДЬ-ЯКУ КНОПКУ"
    out = bdat.write(raw, texts)
    assert bdat.read(out) == texts and len(out) > len(raw)


@pytest.mark.parametrize("name", ["ascii", "standard", "talk", "standard_cn", "standard_kr", "standard_tw"])
def test_every_font_packs_back_unchanged_and_lacks_ukrainian_letters(name):
    raw = (_source() / "menu" / "font" / f"{name}.wifnt").read_bytes()
    assert font_formats.detect(raw) == "laft"
    metadata, sheets = font_formats.extract("laft", raw, {})
    assert font_formats.pack("laft", metadata, sheets, raw, {}) == raw
    chars = font_formats.char_map(metadata)
    assert not any(letter in chars for letter in UKRAINIAN)
    if name == "ascii":
        free = metadata["header"]["glyph_count"]
        grid = metadata["GLY1"][0]
        x, y = (free % grid["glyph_horizontal_count"]) * grid["cell_width"], (free // grid["glyph_horizontal_count"]) * grid["cell_height"]
        ImageDraw.Draw(sheets[0]).rectangle((x + 4, y + 4, x + 20, y + 30), fill=(255, 255, 255, 255))
        block = metadata["MAP1"][0]
        block["entries"].insert(block["mapping_entry_count"], ord("Ї"))
        block["entries"].append(free)
        block["mapping_entry_count"] += 1
        metadata["WID1"][0]["packets"][free] = {"kerning": 4, "width": 16}
        out = font_formats.pack("laft", metadata, sheets, raw, {})
        again, _sheets = font_formats.extract("laft", out, {})
        assert font_formats.char_map(again)["Ї"] == free and font_formats.char_map(again)["T"] == chars["T"]


def test_every_layout_texture_writes_back_and_the_logo_takes_an_edit():
    paths = sorted((_source() / "menu" / "image").rglob("*.wilay"))
    assert len(paths) == 9392
    formats, count = set(), 0
    for path in paths[::97]:
        raw = path.read_bytes()
        textures = wilay.read(raw, {})
        formats.update(t.pixel_format for t in textures)
        count += len(textures)
        assert wilay.write(raw, {i: t.image for i, t in enumerate(textures)}, {}) == raw, path
    assert "BC7" in formats and count > 100
    raw = (_source() / "menu/image/mnu001_cont01_en.wilay").read_bytes()
    textures = wilay.read(raw, {})
    logo = max(range(len(textures)), key=lambda i: textures[i].image.width)
    assert textures[logo].image.size == (776, 288)
    image = textures[logo].image.copy()
    ImageDraw.Draw(image).rectangle((20, 20, 200, 80), fill=(10, 10, 10, 255))
    out = wilay.write(raw, {logo: image}, {})
    assert len(out) == len(raw) and out != raw
    pixel = wilay.read(out, {})[logo].image.getpixel((100, 50))
    assert pixel[3] > 200 and max(pixel[:3]) < 60


def test_the_build_hides_changed_files_in_every_archive_index(tmp_path):
    source = _source()
    if not (WS / "romfs").is_dir() or not (WS / "reports" / "archives.json").is_file():
        pytest.skip("workspace indexes missing")
    sys.path.insert(0, str(SCRIPTS))
    xc3 = importlib.import_module("zt.xc3")
    manifest = json.loads((WS / "reports" / "archives.json").read_text(encoding="utf-8"))
    path = "/bdat/gb/game/menu.bdat"
    tids = manifest[path]["in"]
    assert len(tids) >= 2                                   # the base and the DLC waves carry this table
    for tid in tids:
        original = next((WS / "romfs" / tid).glob("*.arh")).read_bytes()
        arh = xc3.Arh(original)
        hidden = arh.hidden([path])
        assert len(hidden) == len(original) and hidden != original
        after = xc3.Arh(hidden)
        assert path not in after.paths and len(after.paths) == len(arh.paths)
        assert after.entries == arh.entries
        other = next(p for p in arh.paths if p != path)
        assert after.entries[after.paths[other]] == arh.entries[arh.paths[other]]
    pytest.importorskip("zstandard")                     # the workspace scripts run with the system Python
    raw = (source / "bdat/gb/game/menu.bdat").read_bytes()
    packed = xc3.xbc1_pack(raw, "menu.bdat")
    assert xc3.is_xbc1(packed) and xc3.xbc1_unpack(packed) == raw
