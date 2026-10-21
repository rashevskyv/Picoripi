"""MadWorld on a synthetic Wii disc: an encrypted ISO built here (fake keys, fake files), then the wizard's unpack and
build paths on it, and the in-place partition writer. The reads go through Picoripi's own Wii reader."""
import hashlib
import json
import struct

import pytest
from Crypto.Cipher import AES

from core.containers import wii_disc
from core.project_library import build as lb
from core.project_library import console_keys, images
from plugins.madworld import archives, messages
from plugins.madworld import wii_patch
from plugins.madworld.rules import GameRules
from .test_codecs import _u8_bytes

MAGIC = 0x5D1C9EA3
PART, TMD_AT, TMD_SIZE, H3_AT, DATA_AT = 0x50000, 0x2C0, 0x208, 0x8000, 0x20000
DOL_AT, FST_AT, FILES_AT = 0x3000, 0x8000, 0x10000
CLUSTER_DATA = 0x7C00
TITLE_ID = b"00010000"
COMMON = bytes(range(16))
TITLE = bytes(range(100, 116))


def _encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def _fst(paths: dict) -> bytes:
    """The file system table of the files ``{path: (offset, size)}``: a folder entry per folder, then the files."""
    tree: dict = {}
    for path in paths:
        node = tree
        parts = path.split("/")
        for folder in parts[:-1]:
            node = node.setdefault(folder, {})
        node[parts[-1]] = path
    entries = [[1 << 24, 0, 0]]
    names = bytearray(b"\0")

    def name_at(text: str) -> int:
        at = len(names)
        names.extend(text.encode("ascii") + b"\0")
        return at

    def emit(folder: dict, parent: int) -> None:
        for key in sorted(folder):
            value = folder[key]
            if isinstance(value, dict):
                index = len(entries)
                entries.append([1 << 24 | name_at(key), parent, 0])
                emit(value, index)
                entries[index][2] = len(entries)
            else:
                offset, size = paths[value]
                entries.append([name_at(key), offset >> 2, size])

    emit(tree, 0)
    entries[0][2] = len(entries)
    table = b"".join(struct.pack(">III", *e) for e in entries)
    return table + bytes(names) + bytes(-(len(table) + len(names)) % 4)


def make_disc(path, files: dict, game_id: bytes = b"RZZP8P", common: bytes = COMMON, title: bytes = TITLE) -> str:
    """A Wii ISO with one DATA partition: ``files`` {path: bytes} in its file system, encrypted with ``title``."""
    layout, cursor = {}, FILES_AT
    for rel in sorted(files):
        layout[rel] = (cursor, len(files[rel]))
        cursor += len(files[rel]) + (-len(files[rel]) % 0x20)
    fst = _fst(layout)
    assert FST_AT + len(fst) <= FILES_AT
    clusters = -(-cursor // CLUSTER_DATA) + 8             # spare clusters at the end, as retail discs have
    plain = bytearray(clusters * CLUSTER_DATA)
    boot = bytearray(0x440)
    boot[:6] = game_id
    struct.pack_into(">I", boot, 0x18, MAGIC)
    struct.pack_into(">III", boot, 0x420, DOL_AT >> 2, FST_AT >> 2, len(fst) >> 2)
    plain[:0x440] = boot
    plain[FST_AT:FST_AT + len(fst)] = fst
    for rel, data in files.items():
        offset = layout[rel][0]
        plain[offset:offset + len(data)] = data
    data_view = bytearray(clusters * 0x8000)
    iv_zero = bytes(16)
    for c in range(clusters):
        hashes = _encrypt(title, iv_zero, bytes(0x400))
        data = _encrypt(title, hashes[0x3D0:0x3E0], bytes(plain[c * CLUSTER_DATA:(c + 1) * CLUSTER_DATA]))
        data_view[c * 0x8000:(c + 1) * 0x8000] = hashes + data
    image = bytearray(PART + DATA_AT + len(data_view))
    image[:6] = game_id
    struct.pack_into(">I", image, 0x18, MAGIC)
    struct.pack_into(">II", image, 0x40000, 1, 0x40020 >> 2)
    struct.pack_into(">II", image, 0x40020, PART >> 2, 0)
    header = PART
    image[header + 0x1BF:header + 0x1CF] = _encrypt(common, TITLE_ID + bytes(8), title)
    image[header + 0x1DC:header + 0x1E4] = TITLE_ID
    struct.pack_into(">II", image, header + 0x2A4, TMD_SIZE, TMD_AT >> 2)
    struct.pack_into(">I", image, header + 0x2B4, H3_AT >> 2)
    struct.pack_into(">I", image, header + 0x2B8, DATA_AT >> 2)
    struct.pack_into(">I", image, header + 0x2BC, (clusters * 0x8000) >> 2)
    image[PART + TMD_AT:PART + TMD_AT + TMD_SIZE] = bytes(TMD_SIZE)
    image[PART + DATA_AT:PART + DATA_AT + len(data_view)] = data_view
    with open(path, "wb") as out:
        out.write(image)
    return str(path)


def read_disc(path: str, common: bytes = COMMON) -> dict:
    with open(path, "rb") as stream:
        reader = wii_disc.WiiImage(stream, common)
        entries = {e.path[len("files/"):]: e for e in reader.entries() if e.path.startswith("files/")}
        return {rel: reader.read(entry) for rel, entry in entries.items()}


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


def test_patch_grows_and_shrinks_files_and_the_disc_reads_back(tmp_path):
    big = bytes(range(256)) * 200
    iso = make_disc(tmp_path / "patch.iso", {"a.bin": b"old", "sub/b.dat": big})
    with open(iso, "r+b") as stream:
        key = wii_patch.title_key(stream, COMMON)
    changed = bytearray(big)
    changed[1000:1010] = b"0123456789"
    wii_patch.patch_iso(iso, key, {"a.bin": b"a much longer replacement " * 40, "sub/b.dat": bytes(changed)})
    got = read_disc(iso)
    assert got["a.bin"] == b"a much longer replacement " * 40
    assert got["sub/b.dat"] == bytes(changed)


def test_patch_refuses_a_new_file_and_a_file_that_is_not_on_the_disc(tmp_path):
    iso = make_disc(tmp_path / "refuse.iso", {"a.bin": b"x"})
    with open(iso, "r+b") as stream:
        key = wii_patch.title_key(stream, COMMON)
    with pytest.raises(ValueError, match="no such file"):
        wii_patch.patch_iso(iso, key, {"new.bin": b"y"})


def test_the_partition_hashes_match_the_data_after_a_patch(tmp_path):
    iso = make_disc(tmp_path / "hash.iso", {"a.bin": bytes(range(256)) * 300})
    with open(iso, "r+b") as stream:
        key = wii_patch.title_key(stream, COMMON)
    wii_patch.patch_iso(iso, key, {"a.bin": b"\x7f" * 5000})
    with open(iso, "rb") as stream:
        part = wii_patch.Partition(stream, wii_patch.data_partition(stream), key)
        for g in range(0, part.clusters, wii_patch.GROUP):
            for h, d in part._load(g // wii_patch.GROUP):
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


def test_build_refuses_a_disc_that_is_not_an_iso(tmp_path, monkeypatch):
    from plugins.common.disc_source import write_source_mark
    from plugins.madworld import build
    rvz = tmp_path / "game.rvz"
    rvz.write_bytes(b"RVZ\x01" + bytes(0x100))
    source = tmp_path / "source"
    source.mkdir()
    write_source_mark(source, rvz)
    monkeypatch.setattr(console_keys, "path_for", lambda console: None)
    with pytest.raises(ValueError, match="Convert"):
        build.build_iso(str(source), str(tmp_path / "t"), str(tmp_path / "o"), lambda p, t: None, lambda: False)
