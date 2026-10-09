"""Animal Crossing: New Leaf and Happy Home Designer on the user's own unpacked games (skipped without them): every
UMSBT and the keyboard MSBT save back byte for byte with every tag named, every font packs back unchanged and takes a
glyph edit, every layout picture format reads, writes back and takes an edit, the layout archives rebuild byte for
byte, and the workspace build puts a changed file and a rebuilt archive into the Luma mod."""
import hashlib
import importlib

import shutil
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.texture_formats import flim
from plugins.animal_crossing_3ds.rules import GameRules, umsbt_split

ROOT = Path(r"E:\Emulators\RomHacking\Animal Crossing")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
GAMES = {"New Leaf": (3299, 87425, 5, 4851), "Happy Home Designer": (507, 57737, 2, 8833)}
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _source(game):
    source = ROOT / game / "source" / "romfs"
    if not (source / "Script").is_dir():
        pytest.skip(f"{game} not unpacked")
    return source


def _zt(name):
    if not (SCRIPTS / "zt" / f"{name}.py").is_file():
        pytest.skip("workspace scripts not found")
    pytest.importorskip("Crypto")                   # the 3DS scripts decrypt with pycryptodome
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module(f"zt.{name}")
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize("game", list(GAMES))
def test_every_text_file_saves_back_byte_for_byte_with_every_tag_named(game):
    source = _source(game)
    files = messages = raw_tags = 0
    for path in sorted((source / "Script").rglob("*.umsbt")) + [source / "Layout/Swkbd/message/EU_English/swkbd.msbt"]:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        files += 1
        messages += len(blocks[0])
        raw_tags += sum(text.count("{tag:") for text in blocks[0])
    assert (files - 1, messages - 126) == GAMES[game][:2]
    assert raw_tags == 0


@pytest.mark.parametrize("game", list(GAMES))
def test_an_edit_changes_only_the_english_language(game):
    path = next(iter(sorted((_source(game) / "Script" / "Talk").glob("*.umsbt"))))
    raw = path.read_bytes()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    blocks[0][0] = "UA TEST " + blocks[0][0]
    before, after = umsbt_split(raw), umsbt_split(rules.save_data_to_json_obj(blocks, names))
    assert before[1:] == after[1:] and len(before) == 5
    assert after[0] != before[0] and "UA TEST " in rules.load_data_from_json_obj(after[0])[0][0][0]


@pytest.mark.parametrize("game", list(GAMES))
def test_every_font_packs_back_and_takes_a_glyph_edit(game):
    fonts = sorted((_source(game) / "Font").iterdir())
    assert len(fonts) == GAMES[game][2]
    for path in fonts:
        raw = path.read_bytes()
        fmt = font_formats.detect(raw)
        assert fmt == "bcfnt", path
        metadata, sheets = font_formats.extract(fmt, raw)
        assert font_formats.pack(fmt, metadata, sheets, raw) == raw, path
        if "msg_size16" in path.name:                 # the text font: every Ukrainian letter but ҐЄІЇґєії is there
            missing = [c for c in UKRAINIAN if c not in font_formats.char_map(metadata)]
            assert "".join(missing) == "ҐЄІЇґєії"
            ink = 255 if sheets[0].mode == "L" else (255, 255, 255, 255)
            ImageDraw.Draw(sheets[0]).rectangle((0, 0, 7, 7), fill=ink)
            edited = font_formats.pack(fmt, metadata, sheets, raw)
            assert edited != raw and font_formats.extract(fmt, edited)[1][0].getpixel((2, 2)) == sheets[0].getpixel((2, 2))


@pytest.mark.parametrize("game", list(GAMES))
def test_every_layout_picture_reads_writes_back_and_takes_an_edit(game):
    source = _source(game)
    pictures = [p for p in source.rglob("*") if p.suffix.lower() in (".bclim", ".bflim")]
    assert len(pictures) == GAMES[game][3]
    formats, edited_formats, checked = set(), set(), set()
    for index, path in enumerate(pictures):
        raw = path.read_bytes()
        name = flim._info(raw)["name"]                      # the footer names the pixel format: cheap for all
        formats.add(name)
        if name in checked and index % 40:                 # every format and every 40th picture decodes and writes back
            continue
        checked.add(name)
        textures = texture_formats.read("bflim", raw)
        assert len(textures) == 1 and textures[0].pixel_format == name
        assert texture_formats.write("bflim", raw, {0: textures[0].image}) == raw, path
        if name not in edited_formats and textures[0].image.size[0] >= 8:
            image = textures[0].image.copy()
            ImageDraw.Draw(image).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
            rebuilt = texture_formats.write("bflim", raw, {0: image})
            assert texture_formats.read("bflim", rebuilt)[0].image.size == image.size
            edited_formats.add(name)
    assert formats == edited_formats


@pytest.mark.parametrize("game", list(GAMES))
def test_every_layout_archive_rebuilds_byte_for_byte(game):
    sos3ds = _zt("sos3ds")
    romfs = ROOT / game / "romfs"
    archives = [a for a in romfs.rglob("*.arc") if any(p.lower().endswith((".bclim", ".bflim")) for p in sos3ds.layout_files(a.read_bytes()))]
    assert len(archives) >= 79
    for archive in archives:
        raw = archive.read_bytes()
        assert sos3ds.layout_replace(raw, {}) == raw, archive
    # a grown member moves the others and keeps them whole
    raw = archives[0].read_bytes()
    members = sos3ds.layout_files(raw)
    name = next(p for p in members if p.lower().endswith((".bclim", ".bflim")))
    rebuilt = sos3ds.layout_replace(raw, {name: members[name] + bytes(0x100)})
    after = sos3ds.layout_files(rebuilt)
    assert after[name] == members[name] + bytes(0x100)
    assert {k: v for k, v in after.items() if k != name} == {k: v for k, v in members.items() if k != name}


@pytest.mark.parametrize("game", list(GAMES))
def test_the_workspace_build_puts_changed_files_into_the_luma_mod(game, tmp_path):
    acnl3ds = _zt("acnl3ds")
    ws = ROOT / game
    if not (ws / "exheader.bin").is_file():
        pytest.skip("workspace not unpacked")
    copy = tmp_path / "ws"
    for name in ("exheader.bin", "zt_game.txt"):
        copy.mkdir(exist_ok=True)
        shutil.copy2(ws / name, copy / name)
    (copy / "romfs").mkdir()
    talk = next(iter(sorted((ws / "source" / "romfs" / "Script" / "Talk").glob("*.umsbt"))))
    rel_talk = talk.relative_to(ws / "source")
    picture = next(p for p in (ws / "source" / "romfs" / "Layout" / "Title").rglob("*") if p.suffix.lower() in (".bclim", ".bflim"))
    rel_pic = picture.relative_to(ws / "source")
    archive_rel = Path(acnl3ds._split(rel_pic.as_posix())[0])
    for rel in (rel_talk, rel_pic):
        (copy / "source" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ws / "source" / rel, copy / "source" / rel)
        (copy / "translation" / rel).parent.mkdir(parents=True, exist_ok=True)
    (copy / archive_rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ws / archive_rel, copy / archive_rel)
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(talk.read_bytes())
    blocks[0][0] = "UA TEST " + blocks[0][0]
    (copy / "translation" / rel_talk).write_bytes(rules.save_data_to_json_obj(blocks, names))
    (copy / "translation" / rel_pic).write_bytes(picture.read_bytes())            # unchanged: must not reach the mod
    tid = f"{int.from_bytes((ws / 'exheader.bin').read_bytes()[0x200:0x208], 'little'):016X}"
    acnl3ds.build(copy, {})
    mod = copy / "build" / "luma" / "titles" / tid
    assert sorted(p.relative_to(mod).as_posix() for p in mod.rglob("*") if p.is_file()) == [rel_talk.as_posix()]
    assert umsbt_split((mod / rel_talk).read_bytes())[1:] == umsbt_split(talk.read_bytes())[1:]
    # a changed picture (first pixel byte flipped) rebuilds its archive around it
    (copy / "translation" / rel_pic).write_bytes(bytes([picture.read_bytes()[0] ^ 0xFF]) + picture.read_bytes()[1:])
    acnl3ds.build(copy, {})
    sos3ds = _zt("sos3ds")
    members = sos3ds.layout_files((mod / archive_rel).read_bytes())
    member = rel_pic.relative_to(archive_rel).as_posix()
    assert members[member] == (copy / "translation" / rel_pic).read_bytes()
    original = sos3ds.layout_files((ws / archive_rel).read_bytes())
    assert {k: hashlib.sha1(v).hexdigest() for k, v in members.items() if k != member} == \
        {k: hashlib.sha1(v).hexdigest() for k, v in original.items() if k != member}
