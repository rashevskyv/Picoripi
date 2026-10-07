"""Paper Mario TTYD (Switch) on the user's own unpacked game (skipped without it): every text file saves back byte for
byte (also with every message re-encoded from the editor form), every font packs back unchanged and takes an
edit (BC4, BC5 outline fonts, bfotf), every UI texture writes back unchanged and one texture per pixel format
takes an edit, and the workspace build puts an unchanged texture back into its BFRES byte for byte."""
import importlib
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import bntx
from plugins.common.msbt import Msbt
from plugins.paper_mario_nx.rules import GameRules
from plugins.paper_mario_nx.tags import from_editor

WS = Path(r"E:\Emulators\RomHacking\Paper Mario\Thousand-Year Door\Switch")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
pytestmark = pytest.mark.skipif(not (WS / "source" / "msg" / "EU_English" / "global.msbt").is_file(),
                                reason="Paper Mario TTYD (Switch) not unpacked")


def test_every_message_file_saves_back_byte_for_byte():
    files = sorted((WS / "source" / "msg" / "EU_English").glob("*.msbt"))
    assert len(files) == 46
    count = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        assert Msbt(raw).build([from_editor(text) for text in blocks[0]]) == raw, path
        assert not any("{tag:" in text for text in blocks[0]), path       # every tag has its MSBP name
        count += len(blocks[0])
    assert count > 14000


@pytest.mark.parametrize("name", ["FOT-PopJoy_Std.bffnt", "MARIO-OutlineL.bffnt", "YoshiFont_EN.bfotf"])
def test_fonts_pack_back_unchanged_and_take_a_glyph_edit(name):
    raw = (WS / "source" / "font" / name).read_bytes()
    fmt = font_formats.detect(raw)
    params = {"size": 45} if fmt == "bfotf" else {}
    metadata, sheets = font_formats.extract(fmt, raw, params)
    assert metadata["header"]["textures_editable"]
    assert font_formats.pack(fmt, metadata, sheets, raw, params) == raw
    grid = metadata["GLY1"][0]
    cell = font_formats.char_map(metadata)["T"]
    per_sheet = grid["glyph_horizontal_count"] * grid["glyph_vertical_count"]
    sheet, slot = divmod(cell, per_sheet)
    row, column = divmod(slot, grid["glyph_horizontal_count"])
    x, y = column * grid["cell_width"], row * grid["cell_height"]
    ImageDraw.Draw(sheets[sheet]).rectangle((x + 3, y + 8, x + 20, y + 30), fill=(255, 255, 255, 255))
    edited = font_formats.pack(fmt, metadata, sheets, raw, params)
    assert edited != raw
    _again, sheets2 = font_formats.extract(fmt, edited, params)
    assert font_formats.coverage(sheets2[sheet]).getpixel((x + 10, y + 20)) > 200


def test_the_ui_uses_six_pixel_formats_all_supported():
    files = sorted((WS / "source" / "ui").rglob("*.bntx"))
    assert len(files) == 260
    found = {bntx.FORMATS.get(t["format"], hex(t["format"])) for path in files for t in bntx._textures(path.read_bytes())}
    assert found == {"BC1", "BC3", "BC4", "BC5", "BC7", "ASTC8x8"}


@pytest.mark.parametrize("folder", ["battle", "cmn", "demo", "event", "gallery", "icon", "menu", "shop", "tutorial"])
def test_every_ui_texture_writes_back_and_each_format_takes_an_edit(folder):
    edited_formats = set()
    for path in sorted((WS / "source" / "ui" / folder).glob("*.bntx")):
        data = path.read_bytes()
        textures = bntx.read(data, {})
        assert bntx.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
        for index, texture in enumerate(textures):
            if texture.pixel_format in edited_formats or min(texture.image.size) < 32:
                continue
            image = texture.image.copy()
            ImageDraw.Draw(image).rectangle((8, 8, 23, 23), fill=(255, 0, 0, 255))
            back = bntx.read(bntx.write(data, {index: image}, {}), {})[index].image
            assert back.tobytes() != texture.image.tobytes(), (path, texture.name)
            if texture.pixel_format != "BC4":                    # one channel: the red box is ink there
                assert back.getpixel((16, 16))[0] > 200 and back.getpixel((16, 16))[1] < 60, (path, texture.name)
            edited_formats.add(texture.pixel_format)
    assert edited_formats


def test_the_build_puts_an_unchanged_texture_back_into_its_bfres_byte_for_byte():
    if not (SCRIPTS / "zt" / "ttydnx.py").is_file():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    try:
        ttydnx = importlib.import_module("zt.ttydnx")
    finally:
        sys.path.remove(str(SCRIPTS))
    from compression import zstd
    rel = "ui/demo/Title_Logo.bfres.bntx"
    built = ttydnx.pack_file(WS, rel, (WS / "source" / rel).read_bytes())
    assert list(built) == ["ui/demo/Title_Logo.bfres.zst"]
    original = zstd.decompress((WS / "romfs" / "ui" / "demo" / "Title_Logo.bfres.zst").read_bytes())
    assert zstd.decompress(built["ui/demo/Title_Logo.bfres.zst"]) == original
    text = ttydnx.pack_file(WS, "msg/EU_English/ui.msbt", b"x")
    assert sorted(text) == ["msg/EU_English/ui.msbt", "msg/US_English_Final/ui.msbt"]
