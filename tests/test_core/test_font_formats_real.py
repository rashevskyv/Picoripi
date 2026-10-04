"""The plugins' font descriptors against the real game files on the developer's disk (skipped elsewhere).

Unedited fonts must pack back byte-exact; the descriptors must put each character on its glyph.
"""
import json
import os
import struct
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.containers import ContainerManager
from core.font_formats import sources
from plugins.common.n64_rom import compute_crc
from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic

ROOT = Path(__file__).resolve().parents[2]
ZELDA = Path(r"E:\Emulators\RomHacking\ZELDA")
SWITCH = Path(r"D:\Downloads\switch")
OOT_ROM = ZELDA / "OOT64_UA" / "rom" / "Legend of Zelda, The - Ocarina of Time (USA).z64"
MM_ROM = ZELDA / "MM64_UA" / "rom" / "Legend of Zelda, The - Majora's Mask (USA).z64"
HWDE_UI = ZELDA / "HWDE_UA" / "romfs" / "data" / "ui"
AOC_FONT = ZELDA / "HWAOC_UA" / "source" / "font" / "latin.g1n"
WW_FILES = ZELDA / "WW_UA" / "ISO" / "ENG" / "files"
TP_FONTS = ZELDA / "TP_UA" / "ISO" / "ENG" / "root" / "res" / "Fontus"
COH_SOURCE = ZELDA / "COH_UA" / "source"
NX_FONTS = [
    SWITCH / "Cadence of Hyrule [NSP]" / "Russian Language Mod (30.09.2020)" / "atmosphere" / "contents"
    / "01000B900D8B0000" / "romfs" / "fonts_bin" / "PixelMPlus.bffnt",
    SWITCH / "Pokemon Scarlet and Violet [NSP]" / "Russian Machine Translation (24.05.2025)" / "atmosphere"
    / "contents" / "01008F6008C5E000" / "romfs" / "appli" / "font" / "bin" / "font_bmp_title_90_01.bffnt",
]


def _descriptor(plugin, index=0):
    return json.loads((ROOT / "plugins" / plugin / "font_sources.json").read_text(encoding="utf-8"))[index]


def _need(path):
    if not Path(path).exists():
        pytest.skip(f"{path} is not on this machine")
    return Path(path).read_bytes()


def _has_ink(metadata, sheets, char):
    glyph = font_formats.char_map(metadata)[char]
    gly = metadata["GLY1"][0]
    per = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    sheet, cell = divmod(glyph, per)
    x, y = (cell % gly["glyph_horizontal_count"]) * gly["cell_width"], (cell // gly["glyph_horizontal_count"]) * gly["cell_height"]
    return sheets[sheet].getchannel("A").crop((x, y, x + gly["cell_width"], y + gly["cell_height"])).getbbox() is not None


def test_every_plugin_font_descriptor_is_well_formed():
    files = sorted((ROOT / "plugins").glob("*/font_sources.json"))
    assert files
    for path in files:
        for entry in json.loads(path.read_text(encoding="utf-8")):
            assert entry["label"] and entry["path"], path
            assert entry["format"] == "bfn" or font_formats.is_supported(entry["format"]), path


@pytest.mark.parametrize("plugin,rom,a_width", [("zelda_oot64", OOT_ROM, 12), ("zelda_mm64", MM_ROM, 12)])
def test_n64_descriptor_matches_the_rom(plugin, rom, a_width):
    data = _need(rom)
    params = _descriptor(plugin)["params"]
    metadata, sheets = font_formats.extract("n64", data, params)
    assert font_formats.font_map(metadata)["A"] == {"width": a_width}
    assert font_formats.font_map(metadata)["i"] == {"width": 4}
    assert _has_ink(metadata, sheets, "A") and _has_ink(metadata, sheets, "é")
    assert font_formats.pack("n64", metadata, sheets, data, params) == data


def test_n64_edit_writes_a_rom_with_a_valid_crc():
    data = _need(OOT_ROM)
    params = _descriptor("zelda_oot64")["params"]
    metadata, sheets = font_formats.extract("n64", data, params)
    glyph = font_formats.char_map(metadata)["Ä"]
    metadata["WID1"][0]["packets"][glyph]["width"] = 11
    ImageDraw.Draw(sheets[0]).point((glyph % 16 * 16 + 1, glyph // 16 * 16 + 1), fill=(255, 255, 255, 255))
    edited = font_formats.pack("n64", metadata, sheets, data, params)
    assert struct.unpack_from(">II", edited, 0x10) == compute_crc(edited)
    again, _sheets = font_formats.extract("n64", edited, params)
    assert again["WID1"][0]["packets"][glyph]["width"] == 11
    assert again["MAP1"] == metadata["MAP1"]


@pytest.mark.parametrize("name,index", [("font_eu.g1t.gz", 0), ("font_eu_p.g1t.gz", 1)])
def test_hwde_g1t_descriptor_matches_the_atlas(name, index):
    data = _need(HWDE_UI / name)
    params = _descriptor("zelda_hwde", index)["params"]
    metadata, sheets = font_formats.extract("g1t", data, params)
    assert len(font_formats.char_map(metadata)) == 224
    assert _has_ink(metadata, sheets, "A") and _has_ink(metadata, sheets, "é")
    assert font_formats.pack("g1t", metadata, sheets, data, params) == data


@pytest.mark.parametrize("index", range(7))
def test_aoc_g1n_descriptor_round_trips(index):
    data = _need(AOC_FONT)
    params = _descriptor("zelda_aoc", index)["params"]
    metadata, sheets = font_formats.extract("g1n", data, params)
    assert _has_ink(metadata, sheets, "A") and _has_ink(metadata, sheets, "é")
    assert "Ж" not in font_formats.char_map(metadata)          # no Cyrillic in the game's Latin font
    assert font_formats.pack("g1n", metadata, sheets, data, params) == data


def _lz4_block(src: bytes, size: int) -> bytes:
    out, at = bytearray(), 0

    def length(value):
        nonlocal at
        if value == 15:                  # 15 means: more length bytes follow, until one below 255
            while True:
                value += src[at]
                at += 1
                if src[at - 1] != 255:
                    break
        return value

    while at < len(src):
        token = src[at]
        at += 1
        literal = length(token >> 4)
        out += src[at:at + literal]
        at += literal
        if at >= len(src):
            break
        back = src[at] | src[at + 1] << 8
        at += 2
        for _ in range(length(token & 15) + 4):
            out.append(out[-back])
    assert len(out) == size
    return bytes(out)


def _nso_image(data: bytes) -> bytes:
    """The executable as loaded: the three segments of an NSO at their memory offsets, decompressed."""
    assert data[:4] == b"NSO0"
    flags = struct.unpack_from("<I", data, 0x0C)[0]
    image = bytearray()
    for index in range(3):
        file_offset, memory_offset, size, _ = struct.unpack_from("<4I", data, 0x10 + 16 * index)
        stored = data[file_offset:file_offset + struct.unpack_from("<I", data, 0x60 + 4 * index)[0]]
        segment = _lz4_block(stored, size) if flags >> index & 1 else stored
        image[len(image):] = bytes(memory_offset - len(image)) + segment
    return bytes(image)


def test_hwde_width_tables_are_the_executables():
    """The advances the game draws with: f32 tables in exefs/main, named by its build id."""
    data = _need(HWDE_UI.parents[2] / "exefs" / "main")
    image = _nso_image(data)
    build = data[0x40:0x60].hex().upper()                                     # patch files are named by it
    for index in (0, 1):
        table = _descriptor("zelda_hwde", index)["params"]["widths"]
        (address,) = [address for rel, address in table["patches"].items() if Path(rel).stem == build]
        values = table["values"]
        assert list(struct.unpack_from(f"<{len(values)}f", image, int(address, 0))) == values


def test_hwde_translation_map_covers_the_cyrillic_slots():
    mapping = json.loads((ROOT / "plugins" / "zelda_hwde" / "translation_map.json").read_text(encoding="utf-8"))
    assert len(mapping) == 67                     # 66 Ukrainian letters and №; no Russian-only letters
    assert mapping["А"] == "À" and mapping["і"] == "³" and mapping["ґ"] == "´" and mapping["№"] == "¹"


@pytest.mark.parametrize("path", NX_FONTS, ids=lambda p: p.name)
def test_switch_bffnt_round_trip_and_edit(path):
    data = _need(path)
    metadata, sheets = font_formats.extract("bffnt", data, {})
    assert metadata["header"]["textures_editable"]
    assert _has_ink(metadata, sheets, "A") and not _has_ink(metadata, sheets, " ")
    assert font_formats.pack("bffnt", metadata, sheets, data, {}) == data
    glyph = font_formats.char_map(metadata)["A"]
    metadata["WID1"][0]["packets"][glyph]["width"] += 2
    edited = font_formats.pack("bffnt", metadata, sheets, data, {})
    again, again_sheets = font_formats.extract("bffnt", edited, {})
    assert again["WID1"][0]["packets"][glyph]["width"] == metadata["WID1"][0]["packets"][glyph]["width"]
    assert [s.tobytes() for s in again_sheets] == [s.tobytes() for s in sheets]


def test_cadence_of_hyrule_fonts_round_trip_through_the_plugin_sources():
    _need(COH_SOURCE / "fonts_bin" / "LoveBug.bffnt")
    descriptors = json.loads((ROOT / "plugins" / "zelda_coh" / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(COH_SOURCE), "translation_path": ""})
    assert len(found) == 6
    for source in found:
        data = source.read_original()
        assert font_formats.pack("bffnt", *font_formats.extract("bffnt", data, source.params), data,
                                 source.params) == data, source.name


def test_cadence_of_hyrule_text_font_gets_ukrainian_letters_on_a_new_sheet():
    """LoveBug has no Cyrillic and 5 free cells: the second sheet (``min_sheets``) takes the alphabet."""
    data = _need(COH_SOURCE / "fonts_bin" / "LoveBug.bffnt")
    params = _descriptor("zelda_coh")["params"]
    metadata, sheets = font_formats.extract("bffnt", data, params)
    gly = metadata["GLY1"][0]
    per_sheet = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    pairs = [(font_formats.char_code(c), g) for c, g in font_formats.char_map(metadata).items()]
    for index, char in enumerate("ЄІЇҐєіїґ"):
        pairs.append((ord(char), per_sheet + index))
        metadata["WID1"][0]["packets"][per_sheet + index] = {"kerning": 0, "width": 8}
        x, y = index * gly["cell_width"], 0
        ImageDraw.Draw(sheets[1]).rectangle((x + 1, y + 1, x + 6, y + 10), fill=(255, 255, 255, 255))
    metadata["MAP1"] = [font_formats.map_entries(pairs)]
    grown = font_formats.pack("bffnt", metadata, sheets, data, params)
    again, again_sheets = font_formats.extract("bffnt", grown, params)
    assert len(again_sheets) == 2 and font_formats.font_map(again)["Ї"] == {"width": 8}
    assert font_formats.font_map(again)["A"] == font_formats.font_map(metadata)["A"]
    assert _has_ink(again, again_sheets, "ґ") and _has_ink(again, again_sheets, "A")
    assert font_formats.pack("bffnt", again, again_sheets, grown, params) == grown


def _bfn_round_trip(data, folder):
    """What the editor does: extract, expand a linear map to a table, save the folder, repack."""
    folder = str(folder)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "f.bfn"), "wb") as stream:
        stream.write(data)
    extract_bfn_logic(os.path.join(folder, "f.bfn"), folder)
    with open(os.path.join(folder, "data.json")) as stream:
        metadata = json.load(stream)
    for block in metadata["MAP1"]:
        if block["mapping_type"] == 0:
            block["linear_count"] = block["mapping_entry_count"]
            block["mapping_type"] = 2
            block["mapping_entry_count"] = block["last_char"] - block["first_char"] + 1
            block["entries"] = list(range(block["mapping_entry_count"]))
    with open(os.path.join(folder, "data.json"), "w") as stream:
        json.dump(metadata, stream)
    repack_bfn_logic(folder, os.path.join(folder, "out.bfn"))
    with open(os.path.join(folder, "out.bfn"), "rb") as stream:
        return stream.read()


@pytest.mark.parametrize("archive", [WW_FILES / "res" / "Msg" / "fontres.arc", WW_FILES / "res" / "Msg" / "rubyres.arc",
                                     TP_FONTS / "fontres.arc", TP_FONTS / "rubyres.arc"], ids=lambda p: f"{p.parts[-6]}-{p.name}")
def test_wind_waker_and_twilight_princess_bfn_round_trip(archive, tmp_path):
    container = ContainerManager.open(_need(archive))
    names = [name for name in container.list_files() if name.endswith(".bfn")]
    assert names
    for name in names:
        data = container.read_file(name)
        assert _bfn_round_trip(data, tmp_path / name) == data, name


def test_wind_waker_descriptor_finds_the_fonts_in_a_project():
    _need(WW_FILES / "res" / "Msg" / "fontres.arc")
    descriptors = json.loads((ROOT / "plugins" / "zelda_tww" / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(WW_FILES), "translation_path": "", "is_directory_mode": True})
    assert [source.name for source in found] == ["rock_24_20_4i_usa.bfn", "hyrule.bfn", "rock_24_20_ia4_e.bfn",
                                                 "kanfont_fix16.bfn"]
    assert all(source.read_current()[:8] == b"FONTbfn1" for source in found)   # the name font is Yaz0 in its archive


# -- 3DS (Ocarina of Time 3D, Majora's Mask 3D, A Link Between Worlds, Tri Force Heroes) ---------

def _ctr_fonts(archive):
    """The FFNT files inside a Yaz0 SARC (found by magic; the names are hashed in ALBW)."""
    from core.containers import yaz0
    data = yaz0.decompress(_need(archive))
    fonts, at = [], data.find(b"FFNT\xff\xfe")
    while at >= 0:
        fonts.append(data[at:at + struct.unpack_from("<I", data, at + 0x0C)[0]])
        at = data.find(b"FFNT\xff\xfe", at + 4)
    return fonts


THREE_DS = [  # (file or archive, format, characters per font)
    (ZELDA / "OOT3D_UA" / "romfs" / "message" / "eu" / "ltn16.qbf", "qbf", [199]),
    (ZELDA / "OOT3D_UA" / "romfs" / "message" / "sys8.qbf", "qbf", [288]),
    (ZELDA / "OOT3D_UA" / "RU" / "romfs" / "message" / "eu" / "ltn16.qbf", "qbf", [265]),
    (ZELDA / "MM3D_UA" / "romfs" / "message" / "ltn16.gzf", "gzf", [468]),
    (ZELDA / "ALBW_UA" / "romfs" / "EU" / "RegionBoot.szs", "bcfnt", [49, 687]),
    (ZELDA / "TFH_UA" / "romfs" / "Archive" / "EU" / "RegionBoot.szs", "bcfnt", [49, 740]),
]


@pytest.mark.parametrize("path,fmt,counts", THREE_DS, ids=lambda v: v.parts[-4] + "-" + v.name if isinstance(v, Path) else None)
def test_3ds_fonts_show_every_character_and_pack_back_unchanged(path, fmt, counts):
    fonts = _ctr_fonts(path) if path.suffix == ".szs" else [_need(path)]
    assert sorted(len(font_formats.char_map(font_formats.extract(fmt, data)[0])) for data in fonts) == counts
    for data in fonts:
        assert font_formats.detect(data) == fmt
        metadata, sheets = font_formats.extract(fmt, data)
        assert font_formats.pack(fmt, metadata, sheets, data) == data



def test_aoc_descriptors_find_the_font_in_the_workspace_source():
    _need(AOC_FONT)
    descriptors = json.loads((ROOT / "plugins" / "zelda_aoc" / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(AOC_FONT.parents[1]), "translation_path": "",
                                          "is_directory_mode": True})
    assert len(found) == 7 and {source.name for source in found} == {"latin.g1n"}
    assert font_formats.detect(found[0].read_current()) == "g1n"
