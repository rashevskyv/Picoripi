"""Pokémon Scarlet/Violet and Legends: Z-A on the user's own unpacked games (skipped without them): every message file
saves back byte for byte (also fully re-encoded from the editor form), every font packs back unchanged, every
English layout texture writes back unchanged and the title logo takes an edit, and the workspace build's
data.trpfd no longer finds a changed file while every other file stays."""
import importlib
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.texture_formats import bntx
from core.texture_formats.sources import list_members, unwrap
from plugins.common import gfmsg
from plugins.pokemon_trinity.rules import GameRules

ROOT = Path(r"E:\Emulators\RomHacking\Pokemon")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
# workspace, text folder, message files, lines, fonts, layout archive glob, English texture count
GAMES = {
    "sv": ("Scarlet and Violet", "message/dat/English", 913, 85331, "appli/font/bin", "appli/data/*/*_eng.arc", 2386),
    "za": ("Legends Z-A", "ik_message/dat/English", 427, 76810, "ui/font/bin", "ui/data/*/*_eng.arc", 4727),
}


def _game(key):
    folder, text, *rest = GAMES[key]
    ws = ROOT / folder
    if not (ws / "source" / text).is_dir():
        pytest.skip(f"{folder} not unpacked")
    return ws, text, *rest


@pytest.mark.parametrize("key", list(GAMES))
def test_every_message_file_saves_back_byte_for_byte(key):
    ws, text, files, lines, *_rest = _game(key)
    paths = sorted((ws / "source" / text).rglob("*.dat"))
    assert len(paths) == files
    count = 0
    for path in paths:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        flags = [f for _u, f in gfmsg.read(raw)]
        assert gfmsg.write([(gfmsg.from_editor(t), f) for t, f in zip(blocks[0], flags)]) == raw, path
        count += len(blocks[0])
    assert count == lines


@pytest.mark.parametrize("key", list(GAMES))
def test_every_font_packs_back_unchanged(key):
    ws, _text, _files, _lines, fonts, *_rest = _game(key)
    paths = sorted(p for p in (ws / "source" / fonts).iterdir() if p.suffix in (".bfotf", ".bffnt"))
    assert len(paths) >= 12
    for path in paths:
        fmt = path.suffix[1:]
        raw = path.read_bytes()
        metadata, sheets = font_formats.extract(fmt, raw, {})
        assert font_formats.pack(fmt, metadata, sheets, raw, {}) == raw, path


@pytest.mark.parametrize("key", list(GAMES))
def test_every_english_layout_texture_writes_back_and_the_logo_takes_an_edit(key):
    ws, *_rest, layouts, count = _game(key)
    found, logo = 0, None
    for path in sorted((ws / "source").glob(layouts)):
        raw = path.read_bytes()
        for member in list_members(raw, "timg/*.bntx"):
            data, rewrap = unwrap(raw, member, {})
            assert rewrap(data) == raw, path
            textures = bntx.read(data, {})
            assert bntx.write(data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
            found += len(textures)
            logo = logo or next(((data, i, t) for i, t in enumerate(textures) if "title_logo" in t.name), None)
    assert found == count and logo
    data, index, texture = logo
    image = texture.image.copy()
    ImageDraw.Draw(image).rectangle((16, 16, 63, 63), fill=(255, 0, 0, 255))
    back = bntx.read(bntx.write(data, {index: image}, {}), {})[index].image
    assert back.getpixel((40, 40))[0] > 200 and back.getpixel((40, 40))[1] < 60


def _trinity():
    if not (SCRIPTS / "zt" / "trinity.py").is_file():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("zt.trinity")
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize("key", list(GAMES))
def test_the_patched_index_drops_exactly_the_changed_files(key):
    ws, text, *_rest = _game(key)
    trinity = _trinity()
    original = next((ws / "romfs").glob("*/arc/data.trpfd")).read_bytes()
    index = trinity._Fb(original)
    known = set(index.u64s(index.root(), 0))
    rels = [p.relative_to(ws / "source").as_posix() for p in sorted((ws / "source" / text).rglob("*.dat"))[:20]]
    hashes = {trinity.fnv(rel) for rel in rels}
    assert hashes <= known                       # the unpack named every file by its real path
    patched = trinity.patch_trpfd(original, hashes)
    assert len(patched) == len(original)
    left = trinity._Fb(patched).u64s(trinity._Fb(patched).root(), 0)
    assert left == sorted(left) and not hashes & set(left) and len(set(left) ^ known) == 2 * len(hashes)
