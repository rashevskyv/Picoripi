"""Paper Mario: Color Splash on the game's own files (skipped where the workspace is not on this machine): every
MSBT, font and UI texture goes back byte for byte; an edited message, glyph and texture read back."""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.common import msbp
from plugins.paper_mario_cs.rules import GameRules

WORKSPACE = Path(r"E:\Emulators\RomHacking\Paper Mario\Color Splash")
SOURCE = WORKSPACE / "source" / "content"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "paper_mario_cs"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _project(translation: Path) -> dict:
    return {"source_path": str(SOURCE), "translation_path": str(translation), "is_directory_mode": True}


def test_every_msbt_saves_back_byte_for_byte_and_an_edit_reads_back():
    files = sorted(_need(SOURCE / "messages" / "EU_English").glob("*.msbt"))
    assert len(files) == 48
    rules, lines = GameRules(), 0
    for path in files:
        raw = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(raw)
        lines += sum(len(block) for block in blocks)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name
        assert "{tag:" not in "".join(blocks[0]) or path.name == "Global.msbt", path.name
    assert lines == 6940
    raw = (SOURCE / "messages" / "EU_English" / "Global.msbt").read_bytes()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks[0][2] == "Go to the world map?{select:0:1:0:300:yesno}"
    blocks[0][2] = "UA TEST {wait:30}Їжак?{select:0:1:0:300:yesno}"
    edited = rules.save_data_to_json_obj(blocks, names)
    assert GameRules().load_data_from_json_obj(edited)[0][0][2] == blocks[0][2]


def test_the_project_file_names_every_tag_group():
    project = msbp.read(_need(SOURCE / "messages" / "gojika.msbp").read_bytes())   # TGG2 without group ids
    assert [group["name"] for group in project["tag_groups"]] == [
        "System", "control", "layout", "option", "scroll", "sound", "text", "window", "chr"]
    assert project["tag_groups"] == json.loads((PLUGIN / "gojika_msbp.json").read_text(encoding="utf-8"))["tag_groups"]


def test_every_font_opens_packs_back_and_a_bc5_glyph_takes_an_edit():
    _need(SOURCE / "fonts" / "mario.bffnt")
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, _project(Path("")))
    assert [source.name for source in found] == ["mario.bffnt", "marioL.bffnt", "pop.bffnt", "popL.bffnt", "popO.bffnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name
    mario = found[0].read_original()                       # BC5 sheets: R = letter, G = the shape behind it
    metadata, sheets = font_formats.extract("bffnt_wiiu", mario)
    sheets[0].paste((255, 255, 255, 255), (8, 8, 24, 24))
    edited = font_formats.pack("bffnt_wiiu", metadata, sheets, mario)
    assert len(edited) == len(mario) and edited != mario
    assert sum(a != b for a, b in zip(edited, mario)) <= 16 * 36     # only the touched 4x4 blocks
    assert font_formats.extract("bffnt_wiiu", edited)[1][0].getpixel((16, 16)) == (255, 255, 255, 255)


def test_every_ui_texture_writes_back_and_an_edit_reads_back(tmp_path):
    _need(SOURCE / "Graphics" / "UI" / "Title" / "Title.EUR_en.bfres")
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, _project(tmp_path))
    assert len(found) == 320
    assert {source.pixel_format for source in found} == {"BC1", "BC3", "BC4", "BC5", "RGBA8"}
    for path in sorted(SOURCE.glob("Graphics/UI/*/*.EUR_en.bfres")):
        data = path.read_bytes()
        textures = texture_formats.read("bfres", data)
        assert texture_formats.write("bfres", data, {i: t.image for i, t in enumerate(textures)}) == data, path.name
    logo = next(source for source in found if source.name == "lg_UI_Title_Logo")
    image = logo.read_original().image.copy()
    image.paste((255, 0, 0, 255), (96, 96, 304, 200))
    assert logo.write(image)
    written = Path(logo.translation_path).read_bytes()
    assert len(written) == Path(logo.source_path).stat().st_size
    assert logo.read_current().image.getpixel((150, 150)) == (255, 0, 0, 255)
    star = next(source for source in found if source.name == "lg_UI_Star_GetLittleStar")
    assert star.mipmaps == 11
