"""Wind Waker HD on the game's own files (skipped where the workspace is not on this machine): every MSBT,
every font and every listed texture goes back byte for byte, and an edit keeps the archives' layout."""
import json
import struct
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.containers import sarc, yaz0
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.zelda_ww.rules import GameRules

WORKSPACE = Path(r"E:\Emulators\RomHacking\Zelda\Wind Waker\HD - Wii U")
SOURCE = WORKSPACE / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "zelda_ww"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _project(translation: Path) -> dict:
    return {"source_path": str(SOURCE), "translation_path": str(translation), "is_directory_mode": True}


def test_every_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "Message").glob("*.msbt"))
    assert len(files) == 68
    rules, lines = GameRules(), 0
    for path in files:
        raw = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(raw)
        lines += sum(len(block) for block in blocks)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name
    assert lines == 5040


def test_every_font_opens_and_packs_back_and_the_button_font_takes_an_edit():
    _need(SOURCE / "Font" / "CKingPic.bffnt")
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, _project(Path("")))
    assert [source.name for source in found] == [f"CKing{n}.bffnt" for n in ("Msg", "Main", "MainL", "Pic", "Ruby", "Zelda")]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name
    pic = found[3].read_original()
    metadata, sheets = font_formats.extract("bffnt_wiiu", pic)
    sheets[0].putpixel((3, 3), (10, 200, 30, 255))
    edited = font_formats.pack("bffnt_wiiu", metadata, sheets, pic)
    assert len(edited) == len(pic)
    assert font_formats.extract("bffnt_wiiu", edited)[1][0].getpixel((3, 3)) == (10, 200, 30, 255)


def _starts(archive: bytes):
    parsed = sarc.Sarc(archive)
    return [(name, start) for name, start, _end in parsed._nodes]


def test_listed_textures_read_back_and_an_edit_keeps_the_layout(tmp_path):
    _need(SOURCE / "Layout" / "Title_00.szs")
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, _project(tmp_path))
    assert len(found) >= 100
    assert {s.pixel_format for s in found} >= {"A8", "BC1_SRGB", "BC3_SRGB", "BC4A", "BC5LA", "RGBA8_SRGB"}
    for source in found[:20]:
        data, _ = texture_sources.unwrap(Path(source.source_path).read_bytes(), source.member, source.params)
        assert texture_formats.write("bflim", data, {0: source.read_original().image}) == data, source.key

    logo = next(s for s in found if s.member == "timg/TitleLogoZelda_00^l.bflim")
    image = logo.read_original().image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 40, 20), fill=(255, 0, 0, 255))
    (tmp_path / "Layout").mkdir()
    assert logo.write(image)
    before, after = (SOURCE / "Layout" / "Title_00.szs").read_bytes(), (tmp_path / "Layout" / "Title_00.szs").read_bytes()
    assert after[8:16] == before[8:16] == struct.pack(">II", 0x2000, 0)      # Wii U Yaz0 data alignment
    assert _starts(yaz0.decompress(after)) == _starts(yaz0.decompress(before))
    assert logo.read_current().image.getpixel((5, 5)) == (255, 0, 0, 255)


def test_every_layout_image_of_the_game_round_trips():
    """All 1 683 BFLIM of the pack and Common/Layout (11 pixel format / tile mode pairs) read and write back."""
    files = [_need(SOURCE / "Pack" / "permanent_2d_UsEnglish.pack"), *sorted((SOURCE / "Layout").glob("*.szs"))]
    count = 0
    for path in files:
        plain, _ = texture_sources._decompress(path.read_bytes())
        for member in texture_sources.list_members(plain, "{*.bflim,*.szs/timg/*.bflim}"):
            data, _ = texture_sources._read_member(plain, member)
            image = texture_formats.read("bflim", data)[0].image
            assert texture_formats.write("bflim", data, {0: image}) == data, f"{path.name}/{member}"
            count += 1
    assert count == 1683
