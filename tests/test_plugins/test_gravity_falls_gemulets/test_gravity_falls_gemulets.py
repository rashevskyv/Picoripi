"""Gravity Falls: Legend of the Gnome Gemulets plugin: the localisation file format on synthetic data, the UbiArt
texture and font formats, and (skipped where the workspace is not on this machine) the real game files."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.font_formats.sources import join_pair
from plugins.gravity_falls_gemulets import loc8
from plugins.gravity_falls_gemulets.rules import GameRules
from plugins.gravity_falls_gemulets.tag_manager import TAG_RE
from plugins.testing import check_loads, check_validator

PLUGIN_NAME = "gravity_falls_gemulets"
WS = Path(r"E:\Emulators\RomHacking\Gravity Falls Legend of the Gnome Gemulets")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN_NAME


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _simple(ident: int, text: str) -> bytes:
    blob = text.encode("utf-8")
    return struct.pack(">II", ident, len(blob)) + blob


def _complex(speaker: int, ident: int, text: str, variant: int = 2, following: int = 0xFFFFFFFF) -> bytes:
    blob = text.encode("utf-8")
    return struct.pack(">III", speaker, ident, len(blob)) + blob + struct.pack(">III", 0xFFFFFFFF, variant, following)


def _section(language: int, simple, complex_) -> bytes:
    return (struct.pack(">III", 7, language, len(simple)) + b"".join(_simple(*s) for s in simple)
            + b"".join(_complex(*c) for c in complex_))


SAMPLE = (bytes(8) + _section(0, [(21, "Game title"), (22, "Yes")], [(0xFFFFFFFF, 50, "Hello [C:FF1D337A]Dipper[C:]\nthere"),
                                                                    (0xAB8E74A4, 51, "Stand")])
          + bytes(12) + _section(1, [(21, "Titre"), (22, "Oui")], [(0xFFFFFFFF, 50, "Salut"), (0xAB8E74A4, 51, "Debout")])
          + bytes(16))


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN_NAME)
    check_validator(PLUGIN_NAME)


def test_loc8_sections_round_trip_and_grow():
    file = loc8.Loc8(SAMPLE)
    assert [s.language for s in file.sections] == [0, 1]
    assert file.texts()[0] == ["Game title", "Yes", "Hello [C:FF1D337A]Dipper[C:]\nthere", "Stand"]
    assert file.build(file.texts()) == SAMPLE
    texts = file.texts()
    texts[0][2] = "Привіт, Діппер! ґ є ї і"
    again = loc8.Loc8(file.build(texts))
    assert again.texts() == texts
    assert again.raw.startswith(bytes(8)) and again.raw.endswith(bytes(16))


def test_plugin_load_and_save_round_trip():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert len(blocks) == 2 and names == {"0": "English", "1": "French"}
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[1][0] = "Titre modifié"
    assert loc8.Loc8(rules.save_data_to_json_obj(blocks, names)).texts()[1][0] == "Titre modifié"


def test_tags_are_recognised():
    assert [m.group() for m in TAG_RE.finditer("a [C:FF1D337A]b[C:] [s:1.5]c[s:] [!TR] [actor:x/y.act]")] == [
        "[C:FF1D337A]", "[C:]", "[s:1.5]", "[s:]", "[!TR]", "[actor:x/y.act]"]


def _tex(width: int, height: int, fmt: int, body: bytes) -> bytes:
    head = struct.pack(">IIIIIII", 0x17, 0x54455800, 0x34, width * height * 4, width << 16 | height, 0x12000, width * height * 4)
    head += bytes(0x34 - len(head))
    gpu = struct.pack("<4I", width, height, fmt, 1)
    return head + gpu + bytes(0x74 - 0x34 - len(gpu)) + body


def test_ubiart_texture_reads_upright_and_writes_back():
    raw = _tex(16, 16, 0x1021, bytes(16 * 16))      # 4 blocks of 8 + 8 bytes: ETC1A4 is 1 byte per pixel
    textures = texture_formats.read("ubiart_tex", raw)
    assert textures[0].image.size == (16, 16) and textures[0].pixel_format == "ETC1A4"
    assert texture_formats.write("ubiart_tex", raw, {0: textures[0].image}) == raw
    marked = textures[0].image.copy()
    marked.paste((255, 0, 0, 255), (0, 0, 8, 8))
    out = texture_formats.write("ubiart_tex", raw, {0: marked})
    assert out != raw and len(out) == len(raw)
    assert texture_formats.read("ubiart_tex", out)[0].image.getpixel((2, 2))[:3] != texture_formats.read("ubiart_tex", raw)[0].image.getpixel((2, 2))[:3]


def _font() -> bytes:
    records = [(0x20, 0, 0, 1, 1, 0, 50, 25), (0x41, 2, 2, 12, 14, 1, 10, 14), (0x42, 20, 2, 12, 14, 1, 10, 14)]
    table = struct.pack(">I", 1) + bytes(0x60 - 4) + struct.pack(">I", len(records))
    for code, x, y, w, h, left, top, adv in records:
        table += struct.pack(">11I", 0x28, code, x, y, w, h, left, top, adv, 0, 0x0F)
    return join_pair(table, _tex(64, 64, 0x1021, bytes(64 * 64)))


def test_ubiart_font_round_trips_and_adds_a_glyph():
    raw = _font()
    meta, sheets = font_formats.extract("ubiart_tfn", raw)
    assert font_formats.pack("ubiart_tfn", meta, sheets, raw) == raw
    chars = font_formats.char_map(meta)
    assert set(chars) == {" ", "A", "B"}
    gl = meta["GLY1"][0]
    sheet = sheets[0].copy()
    spare = len(chars)
    x, y = (spare % gl["glyph_horizontal_count"]) * gl["cell_width"], (spare // gl["glyph_horizontal_count"]) * gl["cell_height"]
    sheet.paste(Image.new("RGBA", (10, 12), (255, 255, 255, 255)), (x, y))
    pairs = [(font_formats.char_code(c), g) for c, g in chars.items()] + [(0x416, spare)]
    meta["MAP1"] = [font_formats.map_entries(pairs)]
    out = font_formats.pack("ubiart_tfn", meta, [sheet], raw)
    assert "Ж" in font_formats.char_map(font_formats.extract("ubiart_tfn", out)[0])


def test_real_localisation_round_trips():
    raw = _need(SOURCE / "romfs" / "enginedata" / "localisation" / "localisation.loc8").read_bytes()
    file = loc8.Loc8(raw)
    assert [s.name for s in file.sections] == ["English", "French", "Japanese", "German", "Spanish", "Italian"]
    assert all(len(s.simple) == 373 and len(s.complex) == 1169 for s in file.sections)
    assert file.build(file.texts()) == raw
    forced = bytearray()
    at = 0
    for section, texts in zip(file.sections, file.texts()):
        forced += raw[at:section.start] + section.serialise(texts)
        at = section.end
    assert bytes(forced) + raw[at:] == raw


def test_real_fonts_and_pictures():
    _need(SOURCE)
    for source in json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8")):
        path = SOURCE / source["path"]
        data = path.read_bytes()
        if "companion" in source:
            data = join_pair(data, (SOURCE / source["companion"]).read_bytes())
        meta, sheets = font_formats.extract(source["format"], data)
        assert font_formats.pack(source["format"], meta, sheets, data) == data, path.name
    files = sorted((SOURCE / "romfs" / "bundle_ctr.ipk").rglob("*.tga.ckd"))
    assert len(files) > 500
    for path in files[::60]:
        data = path.read_bytes()
        textures = texture_formats.read("ubiart_tex", data)
        assert texture_formats.write("ubiart_tex", data, {0: textures[0].image}) == data, path.name
