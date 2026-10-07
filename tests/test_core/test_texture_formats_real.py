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

ZELDA = Path(r"E:\Emulators\RomHacking\Zelda")
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
    archive = _need(ZELDA / "Wind Waker" / "GC" / "source" / "files" / "res" / "Object" / "TlogoE.arc").read_bytes()
    data, _ = sources.unwrap(archive, member, {})
    _round_trip("bti", data)


def test_link_between_worlds_banner_and_logo():
    banner = _need(ZELDA / "A Link Between Worlds" / "romfs" / "EU_English" / "Layout" / "Finish_00.bflim").read_bytes()
    assert _round_trip("bflim", banner)[0].image.size == (256, 64)
    archive = _need(ZELDA / "A Link Between Worlds" / "romfs" / "Archive" / "Lyt_Menu.arc").read_bytes()
    logo, _ = sources.unwrap(archive, "timg/TitleLogoUSEU_00.bflim", {})
    _round_trip("bflim", logo)


def test_tri_force_heroes_billboards():
    data = _need(ZELDA / "Tri Force Heroes" / "romfs" / "Common" / "Icon" / "billboardCommon.ctpk").read_bytes()
    assert _round_trip("ctpk", data)[0].name == "Arena1st.tga"


def test_wind_waker_hd_sea_chart_label():
    pack = _need(ZELDA / "Wind Waker" / "HD - Wii U" / "source" / "Pack" / "permanent_2d_UsEnglish.pack").read_bytes()
    data, _ = sources.unwrap(pack, "Map_00.szs/timg/MapFontHairal_00^t.bflim", {})
    assert _round_trip("bflim", data)[0].pixel_format == "BC5LA"


def test_cadence_title_logo_in_the_zlib_pack():
    pack = _need(ZELDA / "Cadence of Hyrule" / "romfs" / "textures_bin" / "texture_pack.bin")
    descriptor = next(d for d in json.loads((ROOT / "plugins" / "zelda_coh" / "texture_sources.json")
                                            .read_text(encoding="utf-8")) if d["label"].startswith("Title"))
    data, _ = sources.unwrap(pack.read_bytes(), "", descriptor["params"])
    assert _round_trip("bntx", data)[0].name == "TitleLogo"


def test_hyrule_warriors_title_card():
    path = _first(str(ZELDA.parent / "_shared" / "textures" / "_work" / "kt" / "hwde_romfs" / "data" / "ui" / "still_event_text"
                      / "event_text_*_ENG.g1t.gz"))
    assert _round_trip("g1t", path.read_bytes())[0].pixel_format == "BC7"


def test_majoras_mask_item_names_in_their_yar():
    rom = _first(str(ZELDA / "Majoras Mask" / "N64" / "source" / "*.z64")).read_bytes()
    params = {"compression": "yar", "pixel_format": "n64:IA4", "width": 128, "height": 16,
              "textures": [{"name": "Ocarina", "offset": "0x0"}]}
    data, rewrap = sources.unwrap(rom, "#17", params)
    assert rewrap(data) == rom
    image = texture_formats.read("raw", data, params)[0].image
    assert image.size == (128, 16) and image.getbbox() is not None


def test_ocarina_boss_card():
    rom = _first(str(ZELDA / "Ocarina of Time" / "N64" / "source" / "*.z64")).read_bytes()
    params = {"pixel_format": "n64:IA8", "width": 128, "height": 80, "textures": [{"name": "card", "offset": "0x1230"}]}
    data, rewrap = sources.unwrap(rom, "#620", params)
    _round_trip("raw", data, params)
    assert rewrap(data) == rom


def test_plugin_texture_lists_find_their_textures():
    roots = {"zelda_tww": ZELDA / "Wind Waker" / "GC" / "source", "zelda_oot64": ZELDA / "Ocarina of Time" / "N64" / "source",
             "zelda_mm64": ZELDA / "Majoras Mask" / "N64" / "source",
             "zelda_oot3d": ZELDA / "Ocarina of Time" / "3D - 3DS" / "source",
             "zelda_mm3d": ZELDA / "Majoras Mask" / "3D - 3DS" / "source"}
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
    data = _need(ZELDA / "A Link Between Worlds" / "romfs" / "EU_English" / "Layout" / "TheEnd_00.bflim").read_bytes()
    image = texture_formats.read("bflim", data)[0].image
    assert isinstance(image, Image.Image) and image.mode == "RGBA"


def test_ocarina_3d_every_listed_texture_writes_back_through_its_archive():
    """CTXB files, CTXB members of scene/actor ZARs and the textures of the CMB models (SOLD OUT, title)."""
    root = _need(ZELDA / "Ocarina of Time" / "3D - 3DS" / "source")
    descriptors = json.loads((ROOT / "plugins" / "zelda_oot3d" / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(root), "translation_path": ""})
    assert len(found) >= 130
    assert {"RGBA4", "RGBA8", "LA8", "ETC1A4"} <= {s.pixel_format for s in found}
    assert any(s.member.endswith(".cmb") for s in found)
    for source in found:
        raw = Path(source.source_path).read_bytes()
        data, rewrap = sources.unwrap(raw, source.member, source.params)
        textures = texture_formats.read("ctxb", data)
        assert texture_formats.write("ctxb", data, {i: t.image for i, t in enumerate(textures)}) == data, source.key
        assert rewrap(data) == raw
    card = next(s for s in found if s.member.endswith("spot00_euen.ctxb"))
    data, rewrap = sources.unwrap(Path(card.source_path).read_bytes(), card.member, {})
    _round_trip("ctxb", data)
    white = Image.new("RGBA", card.size, (255, 255, 255, 255))
    archive = rewrap(texture_formats.write("ctxb", data, {0: white}))       # the scene ZAR repacked
    again, _ = sources.unwrap(archive, card.member, {})
    assert texture_formats.read("ctxb", again)[0].image.getpixel((5, 5))[3] == 255


def test_majoras_mask_3d_boss_card_through_lzs_and_gar():
    path = _need(ZELDA / "Majoras Mask" / "3D - 3DS" / "romfs" / "actors" / "zelda2_boss01.gar.lzs")
    raw = path.read_bytes()
    data, rewrap = sources.unwrap(raw, "tex/boss_name_odoruwa_euen.ctxb", {})
    assert rewrap(data) == raw
    assert _round_trip("ctxb", data)[0].image.size == (256, 64)


def test_majoras_mask_3d_every_listed_texture_writes_back_through_its_archive():
    """Loose CTXB, CTXB in GAR and in LzS GAR, the title logo CMB (v10 header) and the copyright CMAB."""
    root = _need(ZELDA / "Majoras Mask" / "3D - 3DS" / "source")
    descriptors = json.loads((ROOT / "plugins" / "zelda_mm3d" / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(root), "translation_path": ""})
    assert len(found) >= 129
    assert {"ETC1", "ETC1A4", "RGBA4", "RGBA8", "LA8", "L8", "RGB565"} <= {s.pixel_format for s in found}
    for source in found:
        raw = Path(source.source_path).read_bytes()
        data, rewrap = sources.unwrap(raw, source.member, source.params)
        textures = texture_formats.read("ctxb", data)
        assert texture_formats.write("ctxb", data, {i: t.image for i, t in enumerate(textures)}) == data, source.key
        assert rewrap(data) == raw
    for member, name in (("Model/title_logo.cmb", "title_sub_00"), ("Misc/title_logo_tex_pt.cmab", "copy_nintendo_GREZZO")):
        data, rewrap = sources.unwrap((root / "romfs" / "actors" / "zelda2_mag.gar.lzs").read_bytes(), member, {})
        textures = texture_formats.read("ctxb", data)
        index = [t.name for t in textures].index(name)
        assert textures[index].image.getpixel((0, 0))[3] < 255           # decoded at the right offset: clear margin
        white = Image.new("RGBA", textures[index].image.size, (255, 255, 255, 255))
        again, _ = sources.unwrap(rewrap(texture_formats.write("ctxb", data, {index: white})), member, {})
        assert texture_formats.read("ctxb", again)[index].image.getpixel((5, 5))[:3] == (255, 255, 255)


def test_wii_home_menu_labels_in_tpl_inside_u8():
    path = _first(str(ZELDA / "Twilight Princess" / "_archive" / "Wii workspace (agent 2026-10-04)" / "source" / "files" / "res" / "HomeBtn" / "homeBtn_ENG.arc"))
    raw = path.read_bytes()
    data, rewrap = sources.unwrap(raw, "arc/timg/tx_btn_00.tpl", {})
    assert rewrap(data) == raw
    _round_trip("tpl", data)


TP_RES = ZELDA / "Twilight Princess" / "GC + Wii" / "ISO" / "ENG" / "root" / "res"


def test_twilight_princess_title_logo_is_a_j3d_model_in_its_archive():
    raw = _need(TP_RES / "Object" / "Title.arc").read_bytes()
    data, rewrap = sources.unwrap(raw, "bmdr/titlelogo_r.bmd", {})
    assert rewrap(data) == raw
    names = [texture.name for texture in _round_trip("j3d", data)]
    assert {"Zelda2_R", "TwilightPrincess", "Nintendo"} <= set(names)


def test_twilight_princess_project_reads_and_writes_every_texture_format_the_game_uses():
    # The TP project's source folder is res/Msgus; the plugin's paths climb out of it.
    _need(TP_RES / "Msgus")
    descriptors = json.loads((ROOT / "plugins" / "zelda_bmg" / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(TP_RES / "Msgus"), "translation_path": ""})
    assert len(found) > 800
    first = {}
    for source in found:
        first.setdefault((source.format, source.pixel_format), source)
    assert {pixel for _fmt, pixel in first} >= {"I4", "I8", "IA4", "IA8", "RGB565", "RGB5A3", "RGBA8", "C4", "C8", "CMPR"}
    for (fmt, _pixel), source in first.items():
        data, _rewrap = sources.unwrap(Path(source.source_path).read_bytes(), source.member, source.params)
        _round_trip(fmt, data, source.params)


TPHD_RES = ZELDA / "Twilight Princess" / "HD - Wii U" / "source" / "content" / "res"


@pytest.mark.parametrize("pack", ["Layout/Title2D.pack.gz", "Layout/button.pack.gz", "CardIcon/cardicon.pack.gz"])
def test_twilight_princess_hd_gx2_textures_in_their_packs_round_trip(pack):
    raw = _need(TPHD_RES / pack).read_bytes()
    plain, _ = sources._decompress(raw)
    members = sources.list_members(plain, "*.gtx")
    assert members
    for member in members:
        data, rewrap = sources.unwrap(raw, member, {})
        assert rewrap(data) == raw
        _round_trip("gtx", data)


def test_twilight_princess_hd_project_finds_its_gx2_textures():
    _need(TPHD_RES / "Layout")
    descriptors = json.loads((ROOT / "plugins" / "zelda_bmg" / "texture_sources.json").read_text(encoding="utf-8"))
    layouts = next(d for d in descriptors if d["format"] == "gtx" and d["path"][0] == "../Layout/*.pack.gz")
    # two packs of the glob are enough to check the paths (all of them take a minute)
    layouts = dict(layouts, path=[p.replace("*.pack.gz", "[bT]*.pack.gz") for p in layouts["path"]])
    found = sources.resolve([layouts], {"source_path": str(TPHD_RES / "Msguk"), "translation_path": ""})
    assert len(found) > 20
    assert {s.pixel_format for s in found} >= {"R8", "R4G4", "R8G8", "RGBA8"}
