"""Xenoblade Chronicles X: Definitive Edition on the user's own unpacked workspace (skipped without it): every
English text table and the credits roll save back byte for byte and take an edit, every font packs back unchanged
(the four text fonts have Cyrillic but lack Ґ Є І Ї ґ є і ї), every layout texture format writes back unchanged
and the title logo takes an edit, and the workspace build puts a changed file under romfs/mod with the loader."""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import wilay
from plugins.common import bdat
from plugins.xenoblade_x_de import crt
from plugins.xenoblade_x_de.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Xenoblade\Chronicles X\DE - Switch")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _source() -> Path:
    if not (WS / "source" / "bdat" / "us" / "common_ms.bdat").is_file():
        pytest.skip("Xenoblade Chronicles X DE not unpacked")
    return WS / "source"


def test_every_text_file_saves_back_byte_for_byte_and_takes_an_edit():
    paths = sorted((_source() / "bdat").rglob("*.bdat")) + [_source() / "ui/credit/endroll.crt"]
    assert len(paths) == 1802
    lines = 0
    for path in paths:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        lines += len(blocks[0])
    assert lines == 122497
    raw = (_source() / "bdat/us/common_ms.bdat").read_bytes()
    texts = bdat.read(raw)
    index = texts.index("Press Any Button")
    texts[index] = "НАТИСНІТЬ БУДЬ-ЯКУ КНОПКУ"
    out = bdat.write(raw, texts)
    assert bdat.read(out) == texts and len(out) > len(raw)
    raw = (_source() / "ui/credit/endroll.crt").read_bytes()
    texts = crt.read(raw)
    assert texts[0] == "JAPANESE VOICE CAST" and len(texts) == 654
    texts[0] = "ЯПОНСЬКІ АКТОРИ ОЗВУЧЕННЯ"
    assert crt.read(crt.write(raw, texts)) == texts


@pytest.mark.parametrize("name", ["standard", "caption", "numeric", "unique", "standard_kr", "standard_tw"])
def test_every_font_packs_back_unchanged_and_lacks_the_ukrainian_only_letters(name):
    raw = (_source() / "ui" / "font" / f"{name}.wifnt").read_bytes()
    assert font_formats.detect(raw) == "laft"
    metadata, sheets = font_formats.extract("laft", raw, {"free_rows": 0})
    assert font_formats.pack("laft", metadata, sheets, raw, {}) == raw
    chars = font_formats.char_map(metadata)
    missing = [letter for letter in UKRAINIAN if letter not in chars]
    if name in ("numeric", "unique"):
        assert len(missing) == len(UKRAINIAN)
    else:
        assert "".join(missing) == "ҐЄІЇґєії"
        grid = metadata["GLY1"][0]
        assert grid["glyph_horizontal_count"] * grid["glyph_vertical_count"] - metadata["header"]["glyph_count"] == 99


def test_every_layout_texture_writes_back_and_the_logo_takes_an_edit():
    layouts = sorted((_source() / "ui" / "image").glob("*.wilay"))
    streams = sorted((_source() / "ui" / "stream" / "us").glob("*.wilay"))
    assert len(layouts) == 6208 and len(streams) == 227
    formats, count = set(), 0
    for path in layouts[::97] + streams[::19]:
        raw = path.read_bytes()
        textures = wilay.read(raw, {})
        formats.update(t.pixel_format for t in textures)
        count += len(textures)
        assert wilay.write(raw, {i: t.image for i, t in enumerate(textures)}, {}) == raw, path
    assert {"BC7", "JPEG"} <= formats and count > 60
    raw = (_source() / "ui/stream/us/strm_title_thumb001.wilay").read_bytes()
    textures = wilay.read(raw, {})
    assert len(textures) == 1 and textures[0].image.size == (1584, 616)
    assert textures[0].image.getpixel((700, 200))[0] > 150                 # the white "Xenoblade" letters
    image = textures[0].image.copy()
    ImageDraw.Draw(image).rectangle((20, 20, 200, 80), fill=(10, 10, 10, 255))
    out = wilay.write(raw, {0: image}, {})
    assert len(out) == len(raw) and out != raw
    pixel = wilay.read(out, {})[0].image.getpixel((100, 50))
    assert pixel[3] > 200 and max(pixel[:3]) < 60


def test_the_build_puts_changed_files_under_the_mod_folder_with_the_loader(tmp_path):
    source = _source()
    if not (WS / "reports" / "archives.json").is_file():
        pytest.skip("workspace manifest missing")
    sys.path.insert(0, str(SCRIPTS))
    xc3 = importlib.import_module("zt.xc3")
    arh = xc3.open_arh((WS / "romfs" / "0100453019AA8000" / "sts.arh").read_bytes())
    assert isinstance(arh, xc3.Arh2) and len(arh.paths) == 104824
    assert arh.entry("/bdat/us/common_ms.bdat")[2] > arh.entry("/bdat/us/common_ms.bdat")[1] > 0
    assert sum(1 for p in arh.paths if p.startswith("/.unmapped/")) == 129
    ws = tmp_path / "ws"
    (ws / "reports").mkdir(parents=True)
    (ws / "zt_game.txt").write_text("XENOBLADE_X_DE", encoding="utf-8")
    (ws / "reports" / "archives.json").write_bytes((WS / "reports" / "archives.json").read_bytes())
    for rel in ("bdat/us/common_ms.bdat", "ui/credit/endroll.crt"):
        (ws / "source" / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / "source" / rel).write_bytes((source / rel).read_bytes())
    raw = (source / "bdat/us/common_ms.bdat").read_bytes()
    texts = bdat.read(raw)
    texts[texts.index("Press Any Button")] = "UA TEST"
    (ws / "translation" / "bdat" / "us").mkdir(parents=True)
    (ws / "translation" / "bdat/us/common_ms.bdat").write_bytes(bdat.write(raw, texts))
    result = subprocess.run([sys.executable, str(SCRIPTS / "zt.py"), str(ws), "build"], capture_output=True, text=True,
                            env=dict(os.environ, ZT_NOPAUSE="1"))
    assert result.returncode == 0, result.stdout + result.stderr
    mod = ws / "build" / "atmosphere" / "contents" / "0100453019AA8000"
    assert (mod / "romfs" / "mod" / "bdat" / "us" / "common_ms.bdat").read_bytes() == bdat.write(raw, texts)
    assert (mod / "exefs" / "subsdk9").stat().st_size > 50000 and (mod / "exefs" / "main.npdm").is_file()
    assert not (mod / "romfs" / "sts.arh").exists()
