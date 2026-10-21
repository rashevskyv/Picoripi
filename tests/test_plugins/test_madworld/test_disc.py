"""MadWorld on a synthetic Wii disc (``tests/synthetic_wii.py``): the wizard's unpack and build paths on it, and the
writer's in-place changes. The reads go through Picoripi's own Wii reader."""
import hashlib
import json

import pytest

from core.containers import wii_writer
from core.project_library import build as lb
from core.project_library import console_keys, images
from plugins.madworld import archives, messages
from plugins.madworld.rules import GameRules
from synthetic_wii import COMMON, make_disc, read_disc
from .test_codecs import _u8_bytes


def _keyfile(tmp_path) -> str:
    """A fake keys.bin with the common key at 0x114 (the layout ``load_common_key`` reads)."""
    path = tmp_path / "keys.bin"
    blob = bytearray(0x400)
    blob[0x114:0x124] = COMMON
    path.write_bytes(bytes(blob))
    return str(path)


def _atlas_body(glyphs: dict, palette: bytes) -> bytes:
    old = {"first": 0x1000, "pages": [(16, 16, bytearray(256), palette)], "whead": (0, 0), "size": 0}
    return messages.mtd_build(old, glyphs)


def _unit_files() -> tuple:
    """A message unit of three glyphs 'A', 'B', 'C' (fake pictures), its atlas, and the other fixed files."""
    palette = bytes(v for k in range(16) for v in (k * 17, 255 - k * 16))
    glyphs = {}
    for n in range(3):
        glyphs[n] = (3, 4, bytes(((n + y + x) % 16) for y in range(4) for x in range(3)), 4, 4.0)
    atlas = _atlas_body(glyphs, palette)
    msgs = [(0, [0x1000, 0x1001, 0x8002]), (1, [0x1002, 0x1000, 0x8002])]
    msd = messages.msd_build(1, msgs)
    labels = {messages.glyph_key(3, 4, bytes(palette[2 * i] for i in g[2])): [ch, "subtitle"]
              for (ch, g) in zip("ABC", glyphs.values())}
    files = {"subscr/MessSubscr002_us.msd": msd, "subscr/subscr002_us.mtd": atlas,
             "etc/font.tpl": b"system font", "hbm/HomeButton2/home.csv": b"a,b\n",
             "hbm/HomeButton2/home_nosave.csv": b"c,d\n",
             "hbm/HomeButton2/homeBtn_ENG.arc": archives.lz_compress(_u8_bytes({"Font": {"x.brfnt": b"font"}})),
             "opening.bnr": _u8_bytes({"meta": {"banner.tpl": b"banner"}})}
    return files, labels


def _keys(monkeypatch, keyfile: str) -> None:
    monkeypatch.setattr(console_keys, "path_for", lambda console: keyfile if console == "wii" else None)


def _provider(keyfile: str):
    return lambda console: keyfile if console == "wii" else None


def test_identify_recognises_the_synthetic_wii_disc(tmp_path):
    files, _labels = _unit_files()
    iso = make_disc(tmp_path / "game.iso", files)
    found = images.identify(iso)
    assert found["kind"] == images.KIND_WII and found["game_id"] == "RZZP8P"
    assert GameRules(None).identify_source(iso) == {"role": "base", "platform": "wii"}


def _patch(iso: str, changes: dict) -> None:
    with open(iso, "r+b") as stream:
        wii_writer.write_changes(stream, COMMON, changes)


def test_patch_grows_and_shrinks_files_and_the_disc_reads_back(tmp_path):
    big = bytes(range(256)) * 200
    iso = make_disc(tmp_path / "patch.iso", {"a.bin": b"old", "sub/b.dat": big})
    changed = bytearray(big)
    changed[1000:1010] = b"0123456789"
    _patch(iso, {"files/a.bin": b"a much longer replacement " * 40, "files/sub/b.dat": bytes(changed)})
    got = read_disc(iso)
    assert got["a.bin"] == b"a much longer replacement " * 40
    assert got["sub/b.dat"] == bytes(changed)


def test_patch_refuses_a_new_file_and_a_file_that_is_not_on_the_disc(tmp_path):
    iso = make_disc(tmp_path / "refuse.iso", {"a.bin": b"x"})
    with pytest.raises(ValueError, match="not a file of the disc"):
        _patch(iso, {"files/new.bin": b"y"})


def test_the_partition_hashes_match_the_data_after_a_patch(tmp_path):
    iso = make_disc(tmp_path / "hash.iso", {"a.bin": bytes(range(256)) * 300})
    _patch(iso, {"files/a.bin": b"\x7f" * 5000})
    with open(iso, "rb") as stream:
        part = wii_writer.Partition(stream, wii_writer.data_partition(stream),
                                    wii_writer.title_key(stream, wii_writer.data_partition(stream), COMMON))
        for g in range(0, part.clusters, wii_writer.GROUP):
            for h, d in part._load(g // wii_writer.GROUP):
                expected = b"".join(hashlib.sha1(d[i * 0x400:(i + 1) * 0x400]).digest() for i in range(31))
                assert bytes(h[0:0x26C]) == expected


def test_unpack_then_build_writes_the_translated_line_back(tmp_path, monkeypatch):
    files, labels = _unit_files()
    iso = make_disc(tmp_path / "unit.iso", files)
    keyfile = _keyfile(tmp_path)
    monkeypatch.setattr(messages, "labels", lambda: labels)
    project = tmp_path / "project"
    source = lb.run_unpack(GameRules(None), {"base": iso}, project, lambda p, t: None, lambda: False,
                           key_provider=_provider(keyfile))
    text = (project / "unpacked" / "text" / "subscr" / "MessSubscr002_us.msd.mwt")
    assert text.is_file() and str(source).endswith("unpacked")
    assert json.loads(text.read_text(encoding="utf-8"))["blocks"][0]["strings"] == ["AB", "CA"]
    assert (project / "unpacked" / "font" / "font_subtitle.tpl").is_file()
    assert (project / "unpacked" / "hbm" / "homeBtn_ENG.arc" / "Font" / "x.brfnt").read_bytes() == b"font"
    assert (project / "unpacked" / "opening.bnr" / "meta" / "banner.tpl").read_bytes() == b"banner"

    trans = project / "translation" / "text" / "subscr"
    trans.mkdir(parents=True)
    doc = json.loads(text.read_text(encoding="utf-8"))
    doc["blocks"][0]["strings"] = ["CC", "AB"]
    (trans / "MessSubscr002_us.msd.mwt").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(console_keys, "path_for", lambda console: keyfile if console == "wii" else None)
    built = lb.run_build(GameRules(None), "wii_iso", project, str(project / "unpacked"), str(project / "translation"),
                         lambda p, t: None, lambda: False)
    after = read_disc(built, common=COMMON)
    assert after["subscr/MessSubscr002_us.msd"] != files["subscr/MessSubscr002_us.msd"]
    assert after["etc/font.tpl"] == b"system font"
    flag, msgs = messages.msd_parse(after["subscr/MessSubscr002_us.msd"])
    atlas = messages.mtd_parse(after["subscr/subscr002_us.mtd"])
    chars = messages.atlas_chars(atlas, labels)
    assert [messages.words_to_text(w, atlas["first"], chars)[0] for _i, w in msgs] == ["CC", "AB"]


def test_build_without_a_translation_gives_the_same_disc(tmp_path, monkeypatch):
    files, labels = _unit_files()
    iso = make_disc(tmp_path / "same.iso", files)
    keyfile = _keyfile(tmp_path)
    monkeypatch.setattr(messages, "labels", lambda: labels)
    project = tmp_path / "project"
    lb.run_unpack(GameRules(None), {"base": iso}, project, lambda p, t: None, lambda: False,
                  key_provider=_provider(keyfile))
    (project / "translation").mkdir()
    _keys(monkeypatch, keyfile)
    built = lb.run_build(GameRules(None), "wii_iso", project, str(project / "unpacked"),
                         str(project / "translation"), lambda p, t: None, lambda: False)
    with open(iso, "rb") as a, open(built, "rb") as b:
        assert a.read() == b.read()


def test_unpack_refuses_another_wii_game(tmp_path):
    files, _labels = _unit_files()
    iso = make_disc(tmp_path / "other.iso", files, game_id=b"RSPE01")
    keyfile = _keyfile(tmp_path)
    with pytest.raises(ValueError, match="not MadWorld"):
        lb.run_unpack(GameRules(None), {"base": iso}, tmp_path / "project", lambda p, t: None, lambda: False,
                      key_provider=_provider(keyfile))
