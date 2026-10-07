"""Metroid Prime Remastered on the user's own dump (skipped without it): the packages repack byte for byte, every
English table saves back byte for byte, every font page packs back unchanged and keeps an edited glyph, every
texture format writes back and keeps an edit, and an unpacked texture goes back into its package."""
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.containers import retro_pak as rp
from core.texture_formats import txtr
from plugins.metroid_prime_remastered.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Metroid\Prime Remastered")


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


@pytest.mark.parametrize("rel", ["MiscData.pak", "Preload/MPRT/PreloadFrontEndMPT.pak"])
def test_game_package_repacks_byte_for_byte(rel, tmp_path):
    source = _need(WS / "romfs" / rel)
    pak = rp.Pak(source)
    assert pak.toc_version == 3 and pak.entry_size == 52
    rp.repack(source, tmp_path / "copy.pak", {})
    assert (tmp_path / "copy.pak").read_bytes() == source.read_bytes()


def test_every_english_table_saves_back_byte_for_byte():
    files = sorted(_need(WS / "source" / "text").glob("*.msbt"))
    assert len(files) == 27
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        messages += len(blocks[0])
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
    assert messages == 3132


def test_an_edited_message_keeps_its_tags_and_labels():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(_need(WS / "source" / "text" / "TEXT_MPT_FrontEnd.msbt").read_bytes())
    index = next(i for i, label in rules._msbt.labels.items() if label == "FE_PressStart")
    assert blocks[0][index] == "PRESS {icon:61} TO START"
    blocks[0][index] = "UA TEST {icon:61}"
    again = GameRules()
    assert again.load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0][0][index] == "UA TEST {icon:61}"
    assert again._msbt.labels == rules._msbt.labels


@pytest.mark.parametrize("name, pages", [("FONT_Geneva", 1), ("FONT_Deface", 5), ("FONT_Deface_PreloadFrontEndMPT", 5)])
def test_font_pages_pack_back_and_keep_an_edit(name, pages):
    data = _need(WS / "source" / "font" / f"{name}.rfont").read_bytes()
    assert font_formats.detect(data) == "retro_font"
    for page in range(pages):
        metadata, sheets = font_formats.extract("retro_font", data, {"page": page})
        assert font_formats.pack("retro_font", metadata, sheets, data, {"page": page}) == data
    metadata, sheets = font_formats.extract("retro_font", data, {"page": 0})
    gly = metadata["GLY1"][0]
    glyph = font_formats.char_map(metadata)["E"]
    columns = gly["glyph_horizontal_count"]
    x, y = (glyph % columns) * gly["cell_width"], (glyph // columns) * gly["cell_height"]
    ImageDraw.Draw(sheets[0]).rectangle((x, y, x + 3, y + 3), fill=(255, 255, 255, 255))
    edited = font_formats.pack("retro_font", metadata, sheets, data, {"page": 0})
    assert edited != data and len(edited) == len(data)
    _metadata, again = font_formats.extract("retro_font", edited, {"page": 0})
    assert again[0].getpixel((x + 1, y + 1))[3] == 255


def _one_of_each_format():
    seen = {}
    for path in sorted(_need(WS / "source" / "texture").rglob("*.txtr")):
        data = path.read_bytes()
        head = txtr._Txtr(data)
        small = 8 <= head.width and 8 <= head.height and head.width * head.height <= 512 * 512
        if head.layers == 1 and head.format not in seen and small:
            seen[head.format] = data
    return seen


def test_every_texture_format_writes_back_and_keeps_an_edit():
    formats = _one_of_each_format()
    assert {13, 28, 54, 58, 69, 72, 84} <= set(formats)   # L8: the font pages
    for fmt, data in formats.items():
        image = texture_formats.read("txtr", data)[0].image
        assert texture_formats.write("txtr", data, {0: image}) == data, fmt
        edited = image.copy()
        ImageDraw.Draw(edited).rectangle((0, 0, 7, 7), fill=(255, 255, 255, 255))
        new = texture_formats.write("txtr", data, {0: edited})
        back = texture_formats.read("txtr", new)[0].image
        channels = 2 if txtr.FORMATS.get(fmt) == "BC5" else 3      # BC5 holds red and green only
        assert back.getpixel((2, 2))[:channels] == (255,) * channels, fmt
        if fmt in txtr.ASTC:
            assert txtr._Txtr(new).format == txtr.ASTC_TO[fmt]


def test_an_unpacked_texture_goes_back_into_its_package(tmp_path):
    source = _need(WS / "romfs" / "Preload" / "MPRT" / "PreloadFrontEndMPT.pak")
    pak = rp.Pak(source)
    asset = pak.find("TXTR", "btn_A")[0]
    form = rp.unpack_texture(pak.read_stored(asset), pak.meta[asset.guid])
    assert form == _need(WS / "source" / "texture" / "PreloadFrontEndMPT" / "btn_A.txtr").read_bytes()
    rp.repack(source, tmp_path / "new.pak", {asset.guid: form}, {asset.guid: rp.texture_meta(form, pak.meta[asset.guid])})
    new = rp.Pak(tmp_path / "new.pak")
    placed = new.by_guid(asset.guid)
    assert rp.unpack_texture(new.read_stored(placed), new.meta[asset.guid]) == form
