"""Mystery Dungeon 3DS: the game titles, the pack names of a Super Mystery Dungeon FARC, and the mod built from a
translated pack member and a loose file (``plugins.pokemon_md_3ds.unpack`` and ``build``). A synthetic pack and
message file stand in for the game, so the test needs no game files."""
import struct
from pathlib import Path

from core.containers import farc
from plugins.pokemon_md_3ds import build as build_mod
from plugins.pokemon_md_3ds import unpack


def _pack(blobs):
    names = sorted(blobs, key=farc.name_hash)
    table = b"".join(struct.pack("<III", farc.name_hash(n), 0, 0) for n in names)
    fat = b"SIR0" + struct.pack("<III", 0x10 + len(table), 0, 0) + table + struct.pack("<III", 0x10, len(names), 1)
    fat += bytes(-len(fat) % 16)
    head = bytearray(b"FARC" + bytes(0x1C) + struct.pack("<5I", 5, 0x80, len(fat), 0, 0) + bytes(0x80 - 0x34)) + fat
    head += bytes(-len(head) % 0x80)
    struct.pack_into("<I", head, 0x2C, len(head))
    body = bytearray()
    for index, name in enumerate(names):
        struct.pack_into("<II", head, 0x80 + 0x10 + index * 12 + 4, len(body), len(blobs[name]))
        body += blobs[name] + bytes(-len(blobs[name]) % 16)
    struct.pack_into("<I", head, 0x30, len(head) + len(body) - 0x80 - len(fat))
    return bytes(head) + bytes(body)


def test_the_two_titles_are_the_two_games():
    assert unpack.game_of("00040000000BA900") == "gti"
    assert unpack.game_of("0004000000174400") == "psmd"
    assert unpack.game_of("0004000000055d00") is None


def test_a_pack_member_gets_its_name_from_the_list_or_its_hash():
    data = _pack({"known.bin": b"abc", "other.bin": b"defg"})
    names = {farc.name_hash("known.bin"): "known.bin"}
    got = unpack.pack_members(data, names)
    assert got == {"known.bin": b"abc", f"#{farc.name_hash('other.bin'):08X}.bin": b"defg"}


def test_pack_names_read_the_name_list(tmp_path):
    top = {"message_en.lst": lambda: b"message/one.bin\nmessage/two.bin\n", "message_en.bin": lambda: b""}
    names = unpack.pack_names(top, "message_en.bin")
    assert names[farc.name_hash("one.bin")] == "one.bin" and names[farc.name_hash("two.bin")] == "two.bin"


def test_build_writes_a_longer_member_into_the_pack_and_a_loose_file(tmp_path):
    source = tmp_path / "source"
    pack = _pack({"a.bin": b"\1" * 16, "b.bin": b"\2" * 32})
    original = source / "garc_original" / "0004000000174400" / "romfs"
    original.mkdir(parents=True)
    (original / "message_en.bin").write_bytes(pack)
    (source / "romfs" / "font").mkdir(parents=True)
    (source / "romfs" / "font" / "f.dic").write_bytes(b"old")
    trans = tmp_path / "translation"
    (trans / "romfs" / "message_en.bin").mkdir(parents=True)
    (trans / "romfs" / "message_en.bin" / "a.bin").write_bytes(b"\3" * 48)
    (trans / "romfs" / "font").mkdir(parents=True)
    (trans / "romfs" / "font" / "f.dic").write_bytes(b"new")
    out = tmp_path / "out"
    result = build_mod.build(source, trans, out, lambda p, w: None, lambda: False)
    assert result == out
    mod_romfs = out / "titles" / "0004000000174400" / "romfs"
    assert (mod_romfs / "font" / "f.dic").read_bytes() == b"new"
    got = farc.member_bytes((mod_romfs / "message_en.bin").read_bytes())
    assert got[farc.name_hash("a.bin")][:48] == b"\3" * 48
    assert got[farc.name_hash("b.bin")][:32] == b"\2" * 32
