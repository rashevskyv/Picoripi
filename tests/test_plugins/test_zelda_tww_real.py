"""Real Wind Waker (GameCube, USA) data: every text file, font and text texture the plugins list opens, and an
unedited save gives the game's bytes back. Skips without the workspace."""
import json
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import texture_formats
from core.containers import ContainerManager
from core.font_formats import sources as font_sources
from core.texture_formats import sources
from plugins.zelda_tingle.rules import GameRules as TingleRules
from plugins.zelda_tww.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Zelda\Wind Waker\GC")
SOURCE = WS / "source"
META = {"source_path": str(SOURCE), "translation_path": "", "is_directory_mode": True}
TEXT_FILES = [("files/res/Msg/bmgres.arc", "zel_00.bmg", 4411), ("files/res/Msg/bmgresh.arc", "zel_01.bmg", 15),
              ("sys/main.dol", "disc_errors.bmg", 6), ("files/opening.bnr", "", 5)]

pytestmark = pytest.mark.skipif(not (SOURCE / "sys" / "main.dol").is_file(), reason="no Wind Waker workspace")


@pytest.mark.parametrize("path, member, count", TEXT_FILES)
def test_every_text_file_loads_and_saves_byte_for_byte(path, member, count):
    rules = GameRules()
    raw = (SOURCE / path).read_bytes()
    data = ContainerManager.open(raw).read_file(member) if member else raw
    blocks, names = rules.load_data_from_json_obj(data)
    assert len(blocks[0]) == count
    if path.endswith(".bnr"):
        rules.prepare_save_context(type("Context", (), {"relative_path": path, "existing_versions": lambda self: iter([raw])})())
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_every_font_is_found_including_nested_and_executable_ones():
    found = font_sources.resolve(GameRules().get_font_sources(), META)
    assert len(found) == 6
    for source in found:
        assert source.read_original()[:8] == b"FONTbfn1", source.label


def test_every_text_texture_writes_back_unchanged_and_one_of_each_format_takes_an_edit():
    found = sources.resolve(GameRules().get_texture_sources(), META)
    assert len(found) >= 154
    edited = set()
    for source in found:
        raw = Path(source.source_path).read_bytes()
        data, rewrap = sources.unwrap(raw, source.member, source.params)
        texture = texture_formats.read(source.format, data, source.params)[source.index]
        assert texture_formats.write(source.format, data, {source.index: texture.image}, source.params) == data
        if source.pixel_format in edited:
            continue
        edited.add(source.pixel_format)
        image = texture.image.copy()
        ImageDraw.Draw(image).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
        new = rewrap(texture_formats.write(source.format, data, {source.index: image}, source.params))
        back_data, _ = sources.unwrap(new, source.member, source.params)
        back = texture_formats.read(source.format, back_data, source.params)[source.index].image
        assert back.getpixel((1, 1))[3] > 200 and min(back.getpixel((1, 1))[:3]) > 200, source.key
    assert {"IA4", "C4", "C8", "I4", "CMPR", "RGB5A3", "IA8"} <= edited


def test_tingle_tuner_graphics_open_and_write_back_unchanged():
    meta = {"source_path": str(SOURCE / "files" / "res" / "Gba"), "translation_path": "", "is_directory_mode": True}
    found = sources.resolve(TingleRules().get_texture_sources(), meta)
    assert [s.size for s in found] == [(256, 128), (256, 64), (128, 40)]
    raw = Path(found[0].source_path).read_bytes()
    params = found[0].params
    images = {i: t.image for i, t in enumerate(texture_formats.read("gba", raw, params))}
    assert texture_formats.write("gba", raw, images, params) == raw
    assert json.loads(json.dumps(params)) == params


def test_fonts_in_main_dol_and_in_the_file_select_archive_save_into_the_translation(tmp_path):
    meta = dict(META, translation_path=str(tmp_path))
    found = {s.label: s for s in font_sources.resolve(GameRules().get_font_sources(), meta)}
    for label in ("Disc error font (in main.dol): disc_error_font.bfn",
                  "File select font (a copy of the name entry font): rock_24_20_ia4_e.bfn"):
        source = found[label]
        original = source.read_original()
        edited = original[:-64] + bytes(b ^ 0xFF for b in original[-64:])
        source.write(edited)
        assert source.read_current() == edited and source.read_original() == original
    dol = found["Disc error font (in main.dol): disc_error_font.bfn"]
    assert Path(dol.translation_path).stat().st_size == Path(dol.source_path).stat().st_size
