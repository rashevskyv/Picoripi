"""Paper Mario: The Origami King on the user's own unpacked game (skipped without it): every text file saves back
byte for byte (also fully re-encoded from the editor form), every font packs back unchanged and BC4 / BC5 fonts
take a glyph edit, every UI texture writes back unchanged and one texture per pixel format takes an edit, and the
workspace build puts textures back into their BFRES (the English one into both English slots)."""
import importlib
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import bntx
from plugins.common.msbt import Msbt
from plugins.paper_mario_ok.rules import GameRules
from plugins.paper_mario_ok.tags import from_editor

WS = Path(r"E:\Emulators\RomHacking\Paper Mario\Origami King")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
pytestmark = pytest.mark.skipif(not (WS / "source" / "msg" / "EU_English" / "global.msbt").is_file(),
                                reason="Paper Mario: The Origami King not unpacked")
# Pure-Python ASTC decoding takes minutes for these two (an 8640x8640 ASTC 10x10 chart, ~150 ASTC 8x8 museum
# pictures); ASTC 10x10 / 8x8 encoding is covered by tests/test_core/test_texture_formats.py.
SLOW = {"W4G1_Charts.bfres.bntx", "museum.bntx"}


def test_every_message_file_saves_back_byte_for_byte():
    files = sorted((WS / "source" / "msg" / "EU_English").glob("*.msbt"))
    assert len(files) == 59
    count = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        assert Msbt(raw).build([from_editor(text) for text in blocks[0]]) == raw, path
        assert not any("{tag:" in text for text in blocks[0]), path       # every tag has its MSBP name
        count += len(blocks[0])
    assert count == 9708


def test_every_font_packs_back_unchanged():
    files = sorted((WS / "source" / "font").glob("*.bffnt"))
    assert len(files) == 12
    for path in files:
        raw = path.read_bytes()
        metadata, sheets = font_formats.extract("bffnt", raw, {})
        assert metadata["header"]["textures_editable"], path
        assert font_formats.pack("bffnt", metadata, sheets, raw, {}) == raw, path


# FOT-PopJoyStd-B: BC4; MARIO-Outline: BC5 whose red reaches past its green (packs back only when unchanged
# blocks are left alone); MARIO-OutlineL: BC5 opened with a spare sheet.
@pytest.mark.parametrize("name, params", [("FOT-PopJoyStd-B.bffnt", {}), ("MARIO-Outline.bffnt", {}),
                                          ("MARIO-OutlineL.bffnt", {"min_sheets": 6})])
def test_fonts_take_a_glyph_edit(name, params):
    raw = (WS / "source" / "font" / name).read_bytes()
    metadata, sheets = font_formats.extract("bffnt", raw, params)
    assert font_formats.pack("bffnt", metadata, sheets, raw, params) == raw
    grid = metadata["GLY1"][0]
    cell = font_formats.char_map(metadata)["T"]
    per_sheet = grid["glyph_horizontal_count"] * grid["glyph_vertical_count"]
    sheet, slot = divmod(cell, per_sheet)
    row, column = divmod(slot, grid["glyph_horizontal_count"])
    x, y = column * grid["cell_width"], row * grid["cell_height"]
    ImageDraw.Draw(sheets[sheet]).rectangle((x + 3, y + 8, x + 20, y + 30), fill=(255, 255, 255, 255))
    edited = font_formats.pack("bffnt", metadata, sheets, raw, params)
    assert edited != raw and len(edited) == len(raw)
    _again, sheets2 = font_formats.extract("bffnt", edited, params)
    assert font_formats.coverage(sheets2[sheet]).getpixel((x + 10, y + 20)) > 200


def test_the_ui_uses_eight_pixel_formats_all_supported():
    files = sorted((WS / "source" / "ui").rglob("*.bntx"))
    assert len(files) == 255
    found = {bntx.FORMATS.get(t["format"], hex(t["format"])) for path in files for t in bntx._textures(path.read_bytes())}
    assert found == {"BC1", "BC3", "BC4", "BC5", "BC7", "RGBA8", "ASTC8x8", "ASTC10x10"}


@pytest.mark.parametrize("folder", ["battle", "cmn", "event", "field", "itemicon", "menu", "title", "."])
def test_every_ui_texture_writes_back_and_each_format_takes_an_edit(folder):
    edited_formats = set()
    for path in sorted((WS / "source" / "ui" / folder).glob("*.bntx")):
        if path.name in SLOW:
            continue
        data = path.read_bytes()
        textures = bntx.read(data, {})
        assert bntx.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
        for index, texture in enumerate(textures):
            already_red = texture.image.crop((8, 8, 24, 24)).getcolors(1)
            if texture.pixel_format in edited_formats or min(texture.image.size) < 32 \
                    or (already_red and already_red[0][1][:3] == (255, 0, 0)):
                continue
            image = texture.image.copy()
            ImageDraw.Draw(image).rectangle((8, 8, 23, 23), fill=(255, 0, 0, 255))
            back = bntx.read(bntx.write(data, {index: image}, {}), {})[index].image
            assert back.tobytes() != texture.image.tobytes(), (path, texture.name)
            if texture.pixel_format != "BC4":                    # one channel: the red box is ink there
                assert back.getpixel((16, 16))[0] > 200 and back.getpixel((16, 16))[1] < 60, (path, texture.name)
            edited_formats.add(texture.pixel_format)
    assert edited_formats


def _pmok():
    if not (SCRIPTS / "zt" / "pmok.py").is_file():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("zt.pmok")
    finally:
        sys.path.remove(str(SCRIPTS))


def test_the_build_puts_textures_back_into_their_bfres():
    from compression import zstd
    pmok = _pmok()
    original = zstd.decompress((WS / "romfs" / "ui" / "cmn" / "HP.bfres.zst").read_bytes())
    spans = pmok.bntx_spans(original)
    for rel in ("ui/cmn/HP.bfres.bntx", "ui/cmn/HP.bfres.en.bntx"):            # unchanged: byte for byte
        built = pmok.pack_file(WS, rel, (WS / "source" / rel).read_bytes())
        assert list(built) == ["ui/cmn/HP.bfres.zst"]
        assert zstd.decompress(built["ui/cmn/HP.bfres.zst"]) == original
    # An edited English texture lands in en-GB and en-US; every other language and the shared texture stay.
    data = (WS / "source" / "ui" / "cmn" / "HP.bfres.en.bntx").read_bytes()
    textures = bntx.read(data, {})
    image = textures[0].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 15, 15), fill=(255, 0, 0, 255))
    edited = bntx.write(data, {0: image}, {})
    rebuilt = zstd.decompress(pmok.pack_file(WS, "ui/cmn/HP.bfres.en.bntx", edited)["ui/cmn/HP.bfres.zst"])
    for name, (at, size) in spans.items():
        if name in ("HP.en-GB", "HP.en-US"):
            assert rebuilt[at:at + size] == edited.replace(b"HP.en-GB\0", f"{name}\0".encode()), name
        else:
            assert rebuilt[at:at + size] == original[at:at + size], name
    text = pmok.pack_file(WS, "msg/EU_English/ui.msbt", b"x")
    assert sorted(text) == ["msg/EU_English/ui.msbt", "msg/US_English_Final/ui.msbt"]
    assert sorted(pmok.pack_file(WS, "font/MARIO-Solid.bffnt", b"x")) == ["font/MARIO-Solid.bffnt.zst"]
    assert sorted(pmok.pack_file(WS, "ui/ItemIcon.bntx", b"x")) == ["ui/ItemIcon.bntx.zst"]
