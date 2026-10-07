"""Lunar: Silver Star Harmony on the developer's own files (skipped where they are not on this machine).

Every script and text table saves back byte for byte; every interface picture writes back unchanged and keeps an
edit; the workspace script (``_shared\\scripts\\zt\\lunarssh.py``, what 1_unpack / 2_build run) unpacks exactly what
``source`` holds and puts edited files back into the game's packs.
"""
import json
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import texture_formats
from core.texture_formats import sources as texture_sources
from plugins.lunar_ssh import ltcv
from plugins.lunar_ssh.rules import GameRules

ROOT = Path(__file__).resolve().parents[3]
RH = Path(r"E:\Emulators\RomHacking")
WS = RH / "Lunar" / "Silver Star Harmony"
SOURCE = WS / "source"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _zt():
    scripts = _need(RH / "_shared" / "scripts" / "zt" / "lunarssh.py").parents[1]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from zt import lunarssh, umd
    return lunarssh, umd


def _iso():
    return next(iter(sorted(_need(WS / "ISO" / "EN").glob("*.iso"))), None) or pytest.skip("no USA image")


def test_every_script_and_table_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "ScriptPack").glob("*.dat")) + sorted(_need(SOURCE / "TEXT_US").glob("*.TXT"))
    assert len(files) == 70
    kinds = {"message": 0, "choice": 0}
    lines = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        lines += len(blocks[0])
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name
        if raw[:4] == ltcv.MAGIC:
            for span in ltcv.parse(raw).spans:
                kinds[span.kind] += 1
    assert kinds == {"message": 11837, "choice": 164}
    assert lines == 13936


def test_an_edited_script_reads_back_and_keeps_its_code():
    raw = _need(SOURCE / "ScriptPack" / "TEXT001.dat").read_bytes()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks[0][0].startswith("{speaker:56}You know, Alex\n")
    edited = [["{speaker:56}UA TEST\nUA TEST{wait}" if i == 0 else s for i, s in enumerate(blocks[0])]]
    new = rules.save_data_to_json_obj(edited, names)
    assert GameRules().load_data_from_json_obj(new)[0] == edited
    assert rules.save_data_to_json_obj(blocks, names) == raw


def test_every_interface_picture_writes_back_and_keeps_an_edit():
    descriptors = json.loads((ROOT / "plugins" / "lunar_ssh" / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 105
    assert {s.pixel_format for s in found} == {"I8", "RGBA8888"}
    for path in sorted({s.source_path for s in found}):
        data = Path(path).read_bytes()
        textures = texture_formats.read("gim", data)
        assert texture_formats.write("gim", data, {i: t.image for i, t in enumerate(textures)}) == data
        index = max(range(len(textures)), key=lambda i: textures[i].image.width * textures[i].image.height)
        image = textures[index].image.copy()
        ImageDraw.Draw(image).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
        new = texture_formats.write("gim", data, {index: image})
        assert len(new) == len(data)
        assert texture_formats.read("gim", new)[index].image.getpixel((1, 1))[3] == 255


def test_unpack_gives_the_source_folder_and_build_packs_edits_back():
    lunarssh, umd = _zt()
    image = umd.Umd(_iso())
    files = lunarssh.source_files(image)
    assert len(files) == 75
    for rel, data in files.items():
        assert (_need(SOURCE / rel)).read_bytes() == data, rel
    for pack in lunarssh.PACKS:
        old = image.read(f"{lunarssh.DATA}PACK/{pack}.dat")
        assert lunarssh.rebuild_pack(old, dict(enumerate(lunarssh.pack_members(old)))) == old
    script = files["ScriptPack/TEXT001.dat"]
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(script)
    blocks[0][0] = "UA TEST" + blocks[0][0]
    edited = rules.save_data_to_json_obj(blocks, names)
    title = files["StationedPack/TITLEGIM.FCHA"]
    picture = texture_formats.read("gim", title)[2].image.copy()
    ImageDraw.Draw(picture).rectangle((0, 0, 9, 9), fill=(255, 0, 255, 255))
    title_edit = texture_formats.write("gim", title, {2: picture})
    table = files["TEXT_US/SYSMENU.TXT"][:-6] + "UA".encode("utf-16-le") + files["TEXT_US/SYSMENU.TXT"][-6:]
    out = lunarssh.image_files(image, {"ScriptPack/TEXT001.dat": edited, "StationedPack/TITLEGIM.FCHA": title_edit,
                                       "TEXT_US/SYSMENU.TXT": table})
    assert out[f"{lunarssh.DATA}TEXT_US/SYSMENU.TXT"] == table
    scripts = [lunarssh.unzip(m) for m in lunarssh.pack_members(out[f"{lunarssh.DATA}PACK/ScriptPack.dat"])]
    assert edited in scripts and script not in scripts
    pictures = [lunarssh.unzip(m) for m in lunarssh.pack_members(out[f"{lunarssh.DATA}PACK/StationedPack.dat"])]
    assert title_edit in pictures and title not in pictures
