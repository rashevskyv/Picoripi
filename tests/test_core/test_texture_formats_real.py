"""Texture formats on the games' own files (skipped where the files are not on this machine).

Reading a texture and writing the same image back must give the game file byte for byte; an edit must
keep the file size and read back as drawn.
"""
import glob
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import texture_formats
from core.texture_formats import sources

ZELDA = Path(r"E:\Emulators\RomHacking\ZELDA")
ROOT = Path(__file__).resolve().parents[2]


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _first(pattern: str) -> Path:
    found = sorted(glob.glob(pattern))
    if not found:
        pytest.skip(f"nothing matches {pattern}")
    return Path(found[0])


def _round_trip(fmt: str, data: bytes, params=None):
    textures = texture_formats.read(fmt, data, params)
    assert textures
    supported = [i for i, t in enumerate(textures) if "not supported" not in t.pixel_format]
    assert texture_formats.write(fmt, data, {i: textures[i].image for i in supported}, params) == data
    index = supported[0]
    edited = textures[index].image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, min(15, edited.width - 1), min(7, edited.height - 1)),
                                     fill=(255, 255, 255, 255))
    new = texture_formats.write(fmt, data, {index: edited}, params)
    assert len(new) == len(data)
    assert texture_formats.read(fmt, new, params)[index].image.getpixel((1, 1))[3] > 200
    return textures


@pytest.mark.parametrize("member", ["timg/press_start.bti", "timg/logo_zelda_main.bti", "timg/c_nintendo_e.bti"])
def test_wind_waker_title_textures(member):
    archive = _need(ZELDA / "WW_UA" / "source" / "files" / "res" / "Object" / "TlogoE.arc").read_bytes()
    data, _ = sources.unwrap(archive, member, {})
    _round_trip("bti", data)


def test_link_between_worlds_banner_and_logo():
    banner = _need(ZELDA / "ALBW_UA" / "romfs" / "EU_English" / "Layout" / "Finish_00.bflim").read_bytes()
    assert _round_trip("bflim", banner)[0].image.size == (256, 64)
    archive = _need(ZELDA / "ALBW_UA" / "romfs" / "Archive" / "Lyt_Menu.arc").read_bytes()
    logo, _ = sources.unwrap(archive, "timg/TitleLogoUSEU_00.bflim", {})
    _round_trip("bflim", logo)


def test_tri_force_heroes_billboards():
    data = _need(ZELDA / "TFH_UA" / "romfs" / "Common" / "Icon" / "billboardCommon.ctpk").read_bytes()
    assert _round_trip("ctpk", data)[0].name == "Arena1st.tga"


def test_wind_waker_hd_sea_chart_label():
    pack = _need(ZELDA / "WWHD_UA" / "source" / "Pack" / "permanent_2d_UsEnglish.pack").read_bytes()
    data, _ = sources.unwrap(pack, "Map_00.szs/timg/MapFontHairal_00^t.bflim", {})
    assert _round_trip("bflim", data)[0].pixel_format == "BC5LA"


def test_cadence_title_logo_in_the_zlib_pack():
    pack = _need(ZELDA / "COH_UA" / "romfs" / "textures_bin" / "texture_pack.bin")
    descriptor = next(d for d in json.loads((ROOT / "plugins" / "zelda_coh" / "texture_sources.json")
                                            .read_text(encoding="utf-8")) if d["label"].startswith("Title"))
    data, _ = sources.unwrap(pack.read_bytes(), "", descriptor["params"])
    assert _round_trip("bntx", data)[0].name == "TitleLogo"


def test_hyrule_warriors_title_card():
    path = _first(str(ZELDA / "_textures" / "_work" / "kt" / "hwde_romfs" / "data" / "ui" / "still_event_text"
                      / "event_text_*_ENG.g1t.gz"))
    assert _round_trip("g1t", path.read_bytes())[0].pixel_format == "BC7"


def test_majoras_mask_item_names_in_their_yar():
    rom = _first(str(ZELDA / "MM64_UA" / "source" / "*.z64")).read_bytes()
    params = {"compression": "yar", "pixel_format": "n64:IA4", "width": 128, "height": 16,
              "textures": [{"name": "Ocarina", "offset": "0x0"}]}
    data, rewrap = sources.unwrap(rom, "#17", params)
    assert rewrap(data) == rom
    image = texture_formats.read("raw", data, params)[0].image
    assert image.size == (128, 16) and image.getbbox() is not None


def test_ocarina_boss_card():
    rom = _first(str(ZELDA / "OOT64_UA" / "source" / "*.z64")).read_bytes()
    params = {"pixel_format": "n64:IA8", "width": 128, "height": 80, "textures": [{"name": "card", "offset": "0x1230"}]}
    data, rewrap = sources.unwrap(rom, "#620", params)
    _round_trip("raw", data, params)
    assert rewrap(data) == rom


def test_plugin_texture_lists_find_their_textures():
    roots = {"zelda_tww": ZELDA / "WW_UA" / "source", "zelda_oot64": ZELDA / "OOT64_UA" / "source",
             "zelda_mm64": ZELDA / "MM64_UA" / "source"}
    checked = 0
    for plugin, root in roots.items():
        if not root.is_dir():
            continue
        descriptors = json.loads((ROOT / "plugins" / plugin / "texture_sources.json").read_text(encoding="utf-8"))
        found = sources.resolve(descriptors, {"source_path": str(root), "translation_path": ""})
        assert len(found) >= len(descriptors), plugin
        assert all(s.size[0] > 0 for s in found)
        checked += 1
    if not checked:
        pytest.skip("no workspace on this machine")


def test_a_decoded_texture_is_an_rgba_image():
    data = _need(ZELDA / "ALBW_UA" / "romfs" / "EU_English" / "Layout" / "TheEnd_00.bflim").read_bytes()
    image = texture_formats.read("bflim", data)[0].image
    assert isinstance(image, Image.Image) and image.mode == "RGBA"


def test_majoras_mask_3d_boss_card_through_lzs_and_gar():
    path = _need(ZELDA / "MM3D_UA" / "romfs" / "actors" / "zelda2_boss01.gar.lzs")
    raw = path.read_bytes()
    data, rewrap = sources.unwrap(raw, "tex/boss_name_odoruwa_euen.ctxb", {})
    assert rewrap(data) == raw
    assert _round_trip("ctxb", data)[0].image.size == (256, 64)


def test_wii_home_menu_labels_in_tpl_inside_u8():
    path = _first(str(ZELDA / "TPWII_UA" / "source" / "files" / "res" / "HomeBtn" / "homeBtn_ENG.arc"))
    raw = path.read_bytes()
    data, rewrap = sources.unwrap(raw, "arc/timg/tx_btn_00.tpl", {})
    assert rewrap(data) == raw
    _round_trip("tpl", data)
