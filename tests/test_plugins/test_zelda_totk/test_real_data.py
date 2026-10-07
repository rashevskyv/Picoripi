"""TotK 1.4.0 on the developer's disk (E:\\...\\TOTK_UA\\romfs, made by 1_unpack.bat); skipped elsewhere."""
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import bfotf
from core.containers import sarc
from plugins.zelda_totk import event_flow, font_glyphs, restbl
from plugins.common.msbt import Msbt, Tag
from plugins.zelda_totk.tags import from_editor, to_editor

ROMFS = Path(r"E:\Emulators\RomHacking\Zelda\Tears of the Kingdom\romfs")
pytestmark = pytest.mark.skipif(not (ROMFS / "Pack" / "ZsDic.pack.zs").is_file(), reason="no TotK romfs on disk")


@pytest.fixture(autouse=True)
def dictionaries(monkeypatch):
    pytest.importorskip("compression.zstd")
    monkeypatch.setattr(sarc, "dictionary_dirs", lambda: [ROMFS])


def _archive(name):
    return sarc.SarcContainer((ROMFS / name).read_bytes())


def test_every_english_message_round_trips_through_the_editor():
    container = _archive("Mals/USen.Product.140.sarc.zs")
    raw_tags, count = set(), 0
    for member in container.list_files():
        data = container.read_file(member)
        msbt = Msbt(data)
        messages = [from_editor(to_editor(tokens)) for tokens in msbt.messages]
        assert msbt.build(messages) == data, member
        count += len(messages)
        raw_tags |= {(t.group, t.type) for tokens in msbt.messages for t in tokens
                     if isinstance(t, Tag) and to_editor([t]).startswith("{tag:")}
    assert count == 47799
    assert raw_tags == {(1, 2)}          # the only tag whose meaning the data does not show


def test_an_unchanged_archive_is_written_back_as_the_same_bytes():
    raw = (ROMFS / "Mals" / "USen.Product.140.sarc.zs").read_bytes()
    plain = sarc.decompress(raw)[0]
    assert sarc.Sarc(plain).build() == plain
    assert sarc.SarcContainer(raw).pack() is raw or sarc.SarcContainer(raw).pack() == raw


def test_the_size_table_rule_matches_every_text_and_font_archive():
    table = restbl.Restbl(sarc.decompress(next((ROMFS / "System" / "Resource").glob("*.rsizetable.zs")).read_bytes())[0])
    for path in sorted((ROMFS / "Mals").glob("*.sarc.zs")) + sorted((ROMFS / "Font").glob("*.bfarc.zs")):
        key = f"{path.parent.name}/{path.name[:-3]}"
        kind = ".bfarc" if path.name.endswith(".bfarc.zs") else ".sarc"
        assert table.size(key) == restbl.required_size(len(sarc.decompress(path.read_bytes())[0]), kind), key


def test_every_font_opens_and_packs_back_byte_exact():
    container = _archive("Font/Font.Nin_NX_NVN.bfarc.zs")
    fonts = [name for name in container.list_files() if name.endswith(".bfotf")]
    assert len(fonts) == 10
    for name in fonts:
        data = container.read_file(name)
        assert font_formats.detect(data) == "bfotf"
        metadata, sheets = font_formats.extract("bfotf", data, {"size": 24})
        assert font_formats.char_map(metadata), name
        assert font_formats.pack("bfotf", metadata, sheets, data, {"size": 24}) == data


def test_the_ukrainian_letters_are_added_once_and_render():
    container = _archive("Font/Font.Nin_NX_NVN.bfarc.zs")
    plain, _key = bfotf.decrypt(container.read_file("scft/nintendo_NTLG-DB_DH_002.bfotf"))
    patched, added = font_glyphs.add_ukrainian(plain)
    assert added == ["Ґ", "ґ"]
    assert font_glyphs.add_ukrainian(patched)[1] == []
    font = bfotf.OpenType(patched)
    assert {ord("Ґ"), ord("ґ")} <= set(font.cmap())
    width, contours = font_glyphs.outline(font_glyphs.Cff(patched[font.table("CFF "):]), font.cmap()[ord("Ґ")])
    assert width > 0 and len(contours) >= 2      # Г plus the upturn


def test_talks_and_cutscene_voices_name_their_speakers():
    def talks(name):
        data = sarc.decompress((ROMFS / "Event" / "EventFlow" / f"{name}.bfevfl.zs").read_bytes())[0]
        return [talk for chart in event_flow.flowcharts(data) for talk in chart["talks"]]

    assert ("Npc_EventStarter", "EventTalk", "EventFlowMsg/Npc_Goron018:Talk_00") in talks("Npc_Goron018")
    assert ("Npc_Zelda_Opening", "EventStartVoice", "EventFlowMsg/DmT_OP_GanonWakeUp:DmT_OP_GanonWakeUp_Text_000_b") \
        in talks("DmT_OP_GanonWakeUp_PreRender")


def test_every_layout_texture_decodes_and_writes_back_byte_exact():
    from core.texture_formats import astc, bntx
    for name in ("Boot", "Common", "Title"):
        raw = sarc.decompress((ROMFS / f"UI/LayoutArchive/{name}.Product.140.Nin_NX_NVN.blarc.zs").read_bytes())[0]
        assert sarc.Sarc(raw).build() == raw, name     # every file keeps its alignment (BNTX at 0x1000)
        data = sarc.Sarc(raw).files["timg/__Combined.bntx"]
        textures = bntx.read(data, {})
        assert not [t.pixel_format for t in textures if "not supported" in t.pixel_format], name
        assert not [t.name for t in textures if t.pixel_format.startswith("ASTC")
                    and astc.ERROR in t.image.getdata()], name
        assert bntx.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data, name


def test_the_english_logos_open_in_the_textures_window_and_an_edit_saves(tmp_path):
    import json
    from PIL import ImageDraw
    from core.texture_formats import sources
    source = ROMFS.parent / "source"
    if not (source / "UI" / "LayoutArchive").is_dir():
        pytest.skip("source has no UI/LayoutArchive")
    descriptors = json.loads((Path(__file__).parents[3] / "plugins" / "zelda_totk" / "texture_sources.json")
                             .read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(source), "translation_path": str(tmp_path)})
    assert len(found) == 9                                    # large logo (Common), small logo (Common, Title)
    assert {t.pixel_format for t in found} == {"ASTC4x4", "BC4"}
    logo = next(t for t in found if t.name == "Logo_EN_L_Full_00^w")
    image = logo.read_original()
    assert not logo.write(image.image)                        # unchanged: nothing written
    edited = image.image.copy()
    ImageDraw.Draw(edited).rectangle((8, 8, 71, 39), fill=(255, 0, 0, 255))
    assert logo.write(edited)
    again = logo.read_current().image
    assert again.crop((8, 8, 72, 40)).getcolors() == [(64 * 32, (255, 0, 0, 255))]
    assert again.crop((100, 100, 300, 300)).tobytes() == image.image.crop((100, 100, 300, 300)).tobytes()


def test_a_redrawn_glyph_and_a_new_width_save_into_the_scalable_font():
    from PIL import ImageDraw
    data = _archive("Font/Font.Nin_NX_NVN.bfarc.zs").read_file("scft/ninP_RodinNTLG-B_DH_003_subset.bfotf")
    params = {"size": 45}
    metadata, sheets = font_formats.extract("bfotf", data, params)
    cells = font_formats.char_map(metadata)
    grid = metadata["GLY1"][0]
    sheet, slot = divmod(cells["p"], 32 * grid["glyph_vertical_count"])
    x0, y0 = slot % 32 * grid["cell_width"], slot // 32 * grid["cell_height"]
    base = metadata["header"]["baseline"]
    draw = ImageDraw.Draw(sheets[sheet])
    draw.rectangle((x0, y0, x0 + grid["cell_width"] - 1, y0 + grid["cell_height"] - 1), fill=(0, 0, 0, 0))
    draw.rectangle((x0 + 3, y0 + base - 30, x0 + 24, y0 + base - 1), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][cells["q"]]["width"] += 10
    packed = font_formats.pack("bfotf", metadata, sheets, data, params)
    again, again_sheets = font_formats.extract("bfotf", packed, params)
    box = again_sheets[sheet].crop((x0 + 4, y0 + base - 29, x0 + 24, y0 + base - 1)).getchannel("A")
    assert box.getextrema() == (255, 255)                         # the drawn square, as an outline
    packets = again["WID1"][0]["packets"]
    assert packets[cells["q"]]["width"] == metadata["WID1"][0]["packets"][cells["q"]]["width"]
    assert font_formats.pack("bfotf", again, again_sheets, packed, params) == packed
