"""Xenoblade Chronicles 2 on the user's own unpacked workspace (skipped without it): every English text table
saves back byte for byte, rebuilds byte for byte and takes an edit; every font packs back unchanged and the
Latin fonts lack only the 8 Ukrainian-specific letters; the layout textures write back unchanged and both title
logos take an edit; the workspace build hides a changed file in the archive index."""
import importlib
import json
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import wilay
from plugins.common import bdat_legacy as bdat
from plugins.xenoblade_2.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Xenoblade\Chronicles 2")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UKRAINIAN_ONLY = "ҐЄІЇґєії"


def _source() -> Path:
    if not (WS / "source" / "bdat" / "gb" / "common_ms.bdat").is_file():
        pytest.skip("Xenoblade Chronicles 2 not unpacked")
    return WS / "source"


def test_every_text_table_saves_back_byte_for_byte_and_takes_an_edit():
    paths = sorted((_source() / "bdat" / "gb").glob("*.bdat"))
    assert len(paths) == 4537
    lines, tables = 0, 0
    for path in paths:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        lines += len(blocks[0])
        for start, end in bdat._tables(raw):                       # a forced rebuild gives the game's own bytes
            table = bdat._Table(raw[start:end])
            assert bdat._rebuild(table, table.texts()) == raw[start:end], (path, start)
            tables += 1
    assert lines == 83323 and tables == 4660
    raw = (_source() / "bdat/gb/common_ms.bdat").read_bytes()
    texts = bdat.read(raw)
    index = texts.index("Press any button")
    texts[index] = "НАТИСНІТЬ БУДЬ-ЯКУ КНОПКУ, ЩОБ ПОЧАТИ"
    out = bdat.write(raw, texts)
    assert bdat.read(out) == texts and len(out) > len(raw)


@pytest.mark.parametrize("name", ["standard", "subtitle", "mincho", "chapter", "staff_name", "standard_kr",
                                  "chinese_simple", "chinese_original"])
def test_every_font_packs_back_unchanged_and_the_latin_fonts_lack_the_ukrainian_letters(name):
    raw = (_source() / "menu" / "font" / f"{name}.wifnt").read_bytes()
    assert font_formats.detect(raw) == "laft"
    metadata, sheets = font_formats.extract("laft", raw, {})
    assert font_formats.pack("laft", metadata, sheets, raw, {}) == raw
    chars = font_formats.char_map(metadata)
    missing = [letter for letter in UKRAINIAN if letter not in chars]
    assert "".join(missing) == (UKRAINIAN_ONLY if name in ("standard", "subtitle", "mincho") else UKRAINIAN)
    if name == "standard":
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


def test_every_layout_texture_writes_back_and_the_logos_take_an_edit():
    paths = sorted((_source() / "menu" / "image").glob("*.wilay"))
    assert len(paths) == 6115
    formats, count = set(), 0
    for path in paths[::61]:
        raw = path.read_bytes()
        textures = wilay.read(raw, {})
        formats.update(t.pixel_format for t in textures)
        count += len(textures)
        assert wilay.write(raw, {i: t.image for i, t in enumerate(textures)}, {}) == raw, path
    assert {"BC1", "BC3"} <= formats and count > 100
    for name, size in (("mnu001_titlelogo_us", (800, 312)), ("dlc3_mnu001_titlelogo_us", (800, 368))):
        raw = (_source() / "menu" / "image" / f"{name}.wilay").read_bytes()
        textures = wilay.read(raw, {})
        logo = max(range(len(textures)), key=lambda i: textures[i].image.width)
        assert textures[logo].image.size == size
        image = textures[logo].image.copy()
        ImageDraw.Draw(image).rectangle((20, 20, 200, 80), fill=(10, 10, 10, 255))
        out = wilay.write(raw, {logo: image}, {})
        assert len(out) == len(raw) and out != raw
        pixel = wilay.read(out, {})[logo].image.getpixel((100, 50))
        assert pixel[3] > 200 and max(pixel[:3]) < 60


def test_the_build_hides_changed_files_in_the_archive_indexes():
    _source()
    if not (WS / "romfs").is_dir() or not (WS / "reports" / "archives.json").is_file():
        pytest.skip("workspace indexes missing")
    sys.path.insert(0, str(SCRIPTS))
    xc3 = importlib.import_module("zt.xc3")
    manifest = json.loads((WS / "reports" / "archives.json").read_text(encoding="utf-8"))
    for path, tid in (("/bdat/gb/common_ms.bdat", "0100E95004038000"), ("/bdat/gb/bf11010100_ms.bdat", "0100E95004039001")):
        assert manifest[path]["in"] == [tid]
        original = next((WS / "romfs" / tid).glob("*.arh")).read_bytes()
        arh = xc3.Arh(original)
        hidden = arh.hidden([path])
        assert len(hidden) == len(original) and hidden != original
        after = xc3.Arh(hidden)
        assert path not in after.paths and len(after.paths) == len(arh.paths) and after.entries == arh.entries
    assert manifest["/bdat/gb/qst610101_ms.bdat"]["in"] == ["0100E95004039002"]      # a loose DLC file: no index
    raw = (WS / "source/bdat/gb/common_ms.bdat").read_bytes()
    packed = xc3.xbc1_pack(raw, "common_ms.bdat", version=1)
    assert xc3.is_xbc1(packed) and xc3.xbc1_unpack(packed) == raw
