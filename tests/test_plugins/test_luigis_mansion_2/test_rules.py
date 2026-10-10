"""Luigi's Mansion: Dark Moon (3DS) plugin: NLOC tables, font and texture bundles (synthetic and the real game's
files when they are unpacked here)."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.texture_formats import nlg_tex
from plugins.luigis_mansion_2 import nloc
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "luigis_mansion_2"
SOURCE = Path(r"E:\Emulators\RomHacking\Luigi's Mansion\2\3DS\source\romfs\art\fe")


def make_nloc(strings, keys=None) -> bytes:
    keys = keys or [0x1000 + 7 * i for i in range(len(strings))]
    order = sorted(range(len(strings)), key=lambda i: keys[i])
    offsets, at = [], 0
    for text in strings:
        offsets.append(at)
        at += len(text) + 1
    head = b"NLOC" + struct.pack("<III", 1, 0xABCD, len(strings))
    head += b"".join(struct.pack("<II", offsets[i], keys[i]) for i in order)
    return head + struct.pack("<I", 7) + "".join(t + "\0" for t in strings).encode("utf-16-le")


SAMPLE = make_nloc(["{tp:0.01}Hey, {clr:51E949}Luigi{clr:pop}!{p}Careful.{/tp}", "Heart Drop acquired!", ""],
                   keys=[0x30, 0x10, 0x20])


def make_bundle(width=16, height=16, fmt=13):
    table = struct.pack("<IIII", 0xE977D350, 0x11111111, width * height, 0x11111111) + bytes(8)
    table += struct.pack("<HH", width, height) + bytes(3) + bytes([0x11]) + bytes(0x14) + bytes([fmt]) + bytes(3)
    return nlg_tex.join(table, bytes(width * height))


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".nloc" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_nloc_texts_follow_the_file_and_rebuild():
    table = nloc.Table(SAMPLE)
    assert table.texts() == ["{tp:0.01}Hey, {clr:51E949}Luigi{clr:pop}!{p}Careful.{/tp}", "Heart Drop acquired!", ""]
    assert table.ids() == ["00000030", "00000010", "00000020"]
    assert table.build(table.texts()) == SAMPLE
    grown = nloc.Table(table.build(["short", "A much longer replacement line of text " * 10, "filled"]))
    assert grown.texts()[0] == "short" and grown.texts()[2] == "filled"
    assert [e[1] for e in grown.entries] == [0x10, 0x20, 0x30]      # entries keep the hash order of the file
    offsets = {key: at for at, key in grown.entries}               # offsets count characters from the first string
    assert offsets[0x30] == 0 and offsets[0x10] == len("short") + 1
    with pytest.raises(ValueError):
        table.build(["too few"])


def test_texture_bundle_reads_and_writes_in_place():
    bundle = make_bundle()
    textures = texture_formats.read("nlg_tex", bundle, {})
    assert len(textures) == 1 and textures[0].image.size == (16, 16)
    assert texture_formats.write("nlg_tex", bundle, {0: textures[0].image}, {}) == bundle
    painted = textures[0].image.copy()
    painted.paste((255, 0, 255, 255), (0, 0, 8, 8))
    changed = texture_formats.write("nlg_tex", bundle, {0: painted}, {})
    assert changed != bundle and len(changed) == len(bundle)
    r, g, b = texture_formats.read("nlg_tex", changed, {})[0].image.getpixel((1, 1))[:3]
    assert r > 240 and g < 24 and b > 240
    assert texture_formats.detect(bundle) == "nlg_tex"


def font_bundle():
    glyph_lines = "".join(f"Glyph {c} Width 8 9 0\r\n" for c in "ABC")
    text = ("NLG Font Description File\r\nVersion 1.1\r\nFont \"T\" 18 color 255 255 255\r\n"
            "PageSize 16 PageCount 1 TextType color Distribution english\r\n"
            "Height 5 RenderHeight 8 Ascent 6 RenderAscent 5 IL 0\r\nCharSpacing 0 LineHeight 0\r\n"
            + glyph_lines + "END\r\n   ").encode("latin-1")
    base = make_bundle(16, 16)
    table, pixel_member = nlg_tex.split(base)
    table += b"\xf6\xbc\x27\x00\x01\x02\x03\x04" + text + struct.pack("<I", 0x11111111)
    return nlg_tex.join(table, pixel_member)


def test_nlg_font_model_and_pack():
    data = font_bundle()
    metadata, sheets = font_formats.extract("nlg_font", data, {})
    assert len(metadata["WID1"][0]["packets"]) == 3
    assert font_formats.pack("nlg_font", metadata, sheets, data, {}) == data
    sheet = sheets[0].copy()
    sheet.paste((255, 255, 255, 255), (0, 0, 4, 4))
    edited = font_formats.pack("nlg_font", metadata, [sheet], data, {})
    assert edited != data and len(edited) == len(data)
    assert font_formats.extract("nlg_font", edited, {})[1][0].getpixel((1, 1))[3] == 255
    metadata["WID1"][0]["packets"][0]["width"] = 12
    assert b"Glyph A Width 12 9" in font_formats.pack("nlg_font", metadata, sheets, data, {})


@pytest.mark.skipif(not SOURCE.is_dir(), reason="Luigi's Mansion 2 (3DS) is not unpacked here")
def test_real_game_tables_fonts_and_textures_round_trip():
    for name in ("english", "ukenglish", "russian"):
        raw = (SOURCE / f"{name}.data" / "strings.nloc").read_bytes()
        table = nloc.Table(raw)
        assert table.count == 1935 and table.build(table.texts()) == raw
    for name in ("febundlefonts_res", "febundlefontsru_res"):
        data = (SOURCE / f"{name}.data" / "bundle.nlgb").read_bytes()
        metadata, sheets = font_formats.extract("nlg_font", data, {})
        assert font_formats.pack("nlg_font", metadata, sheets, data, {}) == data
        textures = texture_formats.read("nlg_tex", data, {})
        assert texture_formats.write("nlg_tex", data, {i: t.image for i, t in enumerate(textures)}, {}) == data
    assert isinstance(Image.new("RGBA", (1, 1)), Image.Image)


def test_credits_script_lines():
    raw = b"\r\n@align left\r\n\r\n/h1:Design\r\n@indent 30\r\nBryce Holliday\r\nCaf\xe9\r\n"
    table = nloc.Credits(raw)
    assert table.texts() == ["/h1:Design", "Bryce Holliday", "Caf\u00e9"]
    assert table.build(table.texts()) == raw
    changed = nloc.Credits(table.build(["/h1:Дизайн", "Bryce Holliday", "Cafe"]))
    assert changed.texts()[1:] == ["Bryce Holliday", "Cafe"]
    assert b"@align left" in changed.raw
