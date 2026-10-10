"""Monster Hunter 3DS plugin: GMD, lmd and quest text, MT TEX textures, GFD/lfd fonts; real-data round trips."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.font_formats import char_map, map_entries
from core.font_formats import mt_font
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.monster_hunter_3ds import mttext
from plugins.monster_hunter_3ds.rules import GameRules
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "monster_hunter_3ds"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / PLUGIN
MH = Path(r"E:\Emulators\RomHacking\Monster Hunter")
GAMES = [MH / "3 Ultimate" / "3DS", MH / "4 Ultimate", MH / "Stories" / "3DS"]
UKRAINIAN_ONLY = set("ҐЄІЇґєії")


def _gmd(*strings: str, labels=("A_LABEL",)) -> bytes:
    name = b"Test"
    label_block = b"".join(label.encode() + b"\0" for label in labels)
    body = b"".join(s.encode() + b"\0" for s in strings)
    head = b"GMD\0" + struct.pack("<7I", 0x10201, 1, len(labels), len(strings), len(label_block), len(body), len(name))
    entries = b"".join(struct.pack("<II", i, 0x12345678) for i in range(len(labels)))
    return head + name + b"\0" + entries + label_block + body


def _lmd(*strings: str) -> bytes:
    n = len(strings)
    table_a = b"".join(struct.pack("<II", i, 0x400000 | i * 12) for i in range(n))
    table_b = b"".join(struct.pack("<III", 1, i, 0x16) for i in range(n))
    oa = 0x24
    ob, oc = oa + len(table_a), oa + len(table_a) + len(table_b)
    out = bytearray(b"lmd\0" + struct.pack("<I", 0x10F) + struct.pack("<7I", n, n, n, oa, ob, oc, 0))
    out += table_a + table_b + bytes(12 * n)
    for i, text in enumerate(strings):
        raw = text.encode("utf-16-le")
        struct.pack_into("<III", out, oc + 12 * i, len(out), len(raw) // 2, len(raw) // 2)
        out += raw + b"\0\0"
        out += bytes(-len(out) % 4)
    struct.pack_into("<I", out, 0x20, len(out))
    return bytes(out + b"Test\0")


def _qtds(titles) -> bytes:
    out = bytearray(b"QTDS" + struct.pack("<I", 5))
    for field, gap in zip(range(5), (2, 24, 6, 0, None)):
        for lang in range(5):
            raw = f"{titles[field]} {lang}".encode()
            out += struct.pack("<I", len(raw)) + raw
        out += bytes(gap or 0)
    return bytes(out + b"\x01\x02tail")


def _mib(strings) -> bytes:
    data = bytearray(0x100)
    data[4:8] = b"v005"
    tables = []
    for lang in range(5):
        at = []
        for text in strings:
            at.append(len(data))
            data += f"{text}{lang}".encode("utf-16-le") + b"\0\0"
        data += bytes(-len(data) % 4)
        tables.append(len(data))
        data += struct.pack("<7I", *at)
    data += bytes(64)                      # room the original layout leaves
    struct.pack_into("<I", data, 0xBC, len(data))
    data += struct.pack("<5I", *tables) + b"rest of the quest"
    return bytes(data)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_gmd_keeps_bytes_and_grows_with_crlf():
    data = _gmd("Potion", "Line one\r\nline two", "<COLO 1>Red</COL>")
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Potion", "Line one\nline two", "<COLO 1>Red</COL>"]]
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][1] = "Рядок один\nрядок два, довший"
    saved = mttext.parse(rules.save_data_to_json_obj(blocks, names))
    assert saved.strings[1] == "Рядок один\r\nрядок два, довший" and saved.labels[0] == "A_LABEL"


def test_lmd_keeps_bytes_and_grows():
    data = _lmd("New Game", "Start a new game.\nNow.")
    text = mttext.parse(data)
    assert text.build(text.strings) == data
    grown = mttext.parse(text.build(["Нова гра — довше", text.strings[1]]))
    assert grown.strings == ["Нова гра — довше", "Start a new game.\nNow."]


def test_mh3u_quest_edits_only_the_english_slot():
    data = _qtds(["Title", "Goal", "Fail", "Client", "Text"])
    text = mttext.parse(data)
    assert text.strings == ["Title 0", "Goal 0", "Fail 0", "Client 0", "Text 0"] and text.build(text.strings) == data
    new = mttext.parse(text.build(["Назва", "Goal 0", "", "Client 0", "Text 0"]))
    assert new.strings == ["Назва", "Goal 0", "", "Client 0", "Text 0"]
    assert b"Title 1" in text.build(["Назва", "Goal 0", "", "Client 0", "Text 0"])


def test_mh4u_quest_relays_english_and_keeps_other_languages_while_they_fit():
    data = _mib(["T", "G", "F", "D", "M", "C", "S"])
    text = mttext.parse(data)
    assert text.strings == ["T0", "G0", "F0", "D0", "M0", "C0", "S0"] and text.build(text.strings) == data
    longer = text.build(["Довша назва", "G0", "F0", "D0", "M0", "C0", "S0"])
    assert len(longer) == len(data) and longer.endswith(b"rest of the quest")
    assert mttext.parse(longer).strings[0] == "Довша назва"
    with pytest.raises(mttext.FormatError):
        text.build(["x" * 400] + text.strings[1:])


def _tex(image: Image.Image) -> bytes:
    from core.texture_formats import pixels, surface
    codec = pixels.codec("pica:RGBA8")
    out = bytearray(b"TEX\0" + struct.pack("<III", 0x200000A5, 1 | image.width << 6 | image.height << 19, 0x10301))
    out += struct.pack("<I", 0) + bytes(surface.surface_bytes(codec, image.width, image.height))
    surface.write(out, 0x14, codec, image.width, image.height, image, force=True)
    return bytes(out)


def test_mt_tex_reads_writes_and_keeps_unchanged_bytes():
    image = Image.new("RGBA", (16, 8), (10, 20, 30, 255))
    data = _tex(image)
    assert texture_formats.detect(data, "x.tex") == "mt_tex"
    read = texture_formats.read("mt_tex", data)[0]
    assert read.pixel_format == "RGBA8" and read.image.getpixel((3, 3)) == (10, 20, 30, 255)
    assert texture_formats.write("mt_tex", data, {0: read.image}) == data
    edited = read.image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 3, 3), fill=(255, 0, 0, 255))
    again = texture_formats.read("mt_tex", texture_formats.write("mt_tex", data, {0: edited}))[0]
    assert again.image.getpixel((1, 1)) == (255, 0, 0, 255)


# -- real data (skipped when the workspaces are not on disk) ---------------------------------

def _need(ws: Path) -> Path:
    if not (ws / "source" / "romfs").is_dir():
        pytest.skip(f"{ws} is not on this machine")
    return ws / "source"


@pytest.mark.parametrize("ws", GAMES, ids=["mh3u", "mh4u", "stories"])
def test_real_text_files_round_trip_byte_exact(ws):
    source = _need(ws)
    files = [p for p in source.rglob("*") if p.suffix in (".gmd", ".lmd", ".quest", ".mib")]
    assert files
    for path in files:
        data = path.read_bytes()
        text = mttext.parse(data)
        assert text.build(text.strings) == data, path


@pytest.mark.parametrize("ws", GAMES, ids=["mh3u", "mh4u", "stories"])
def test_real_fonts_open_pack_back_and_lack_only_the_ukrainian_letters(ws):
    source = _need(ws)
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(source), "translation_path": ""})
    assert found
    for font in found:
        data = font.read_original()
        metadata, sheets = font_formats.extract(font.format, data, font.params)
        assert font_formats.pack(font.format, metadata, sheets, data, font.params) == data, font.label
        letters = mt_font.letters(data)
        if "main font" in font.label:
            assert "Ж" in letters and not (UKRAINIAN_ONLY & letters), font.label


def test_real_font_gets_a_new_letter():
    source = _need(GAMES[1])
    table = source / "romfs/loc/lyt/font/font_loc.lfd"
    data = font_sources.join_pair(table.read_bytes(), (source / "romfs/loc/lyt/font/font_loc_00_AM_NOMIP.tex").read_bytes())
    metadata, sheets = font_formats.extract("mt_font", data, {})
    spare = max(char_map(metadata).values()) + 1
    entries = metadata["MAP1"][0]["entries"]
    half = len(entries) // 2
    metadata["MAP1"] = [map_entries(list(zip(entries[:half], entries[half:])) + [(ord("Ї"), spare)])]
    gly = metadata["GLY1"][0]
    x, y = (spare % gly["glyph_horizontal_count"]) * gly["cell_width"], (spare // gly["glyph_horizontal_count"]) * gly["cell_height"]
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((x, y + 2, x + 4, y + 12), fill=(255, 255, 255, 255))
    packed = font_formats.pack("mt_font", metadata, [sheet], data, {})
    assert "Ї" in mt_font.letters(packed)
    assert "Ї" in char_map(font_formats.extract("mt_font", packed, {})[0])


@pytest.mark.parametrize("ws", GAMES, ids=["mh3u", "mh4u", "stories"])
def test_real_textures_resolve_and_write_back_byte_exact(ws):
    source = _need(ws)
    descriptor = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))[0]
    files = sorted(source.glob(descriptor["path"]))
    assert len(files) > 200
    one = dict(descriptor, path=files[0].relative_to(source).as_posix())
    assert texture_sources.resolve([one], {"source_path": str(source), "translation_path": ""})
    for path in files[::40]:                  # a sample: decoding every ETC1 texture takes minutes
        data = path.read_bytes()
        image = texture_formats.read("mt_tex", data)[0].image
        assert texture_formats.write("mt_tex", data, {0: image}) == data, path
