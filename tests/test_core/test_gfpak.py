"""GFLXPACK reader on a synthetic pack: the table, stored and Oodle-coded files, names and refused inputs."""
import struct

import pytest

from core.containers import gfpak


def make_pack(files):
    """A pack of ``(path hash, kind, raw, packed)`` files; ``packed`` is what the table stores."""
    count = len(files)
    table = 0x40
    hashes = table + 24 * count
    out = bytearray((hashes + 8 * count + 15) // 16 * 16)
    out[0:8] = gfpak.MAGIC
    struct.pack_into("<IIiiQQ", out, 8, 4096, 0, count, 0, table, hashes)
    for index, (path_value, kind, raw, packed) in enumerate(files):
        offset = len(out)
        out += packed + b"\0" * (-len(packed) % 16)
        struct.pack_into("<2xHII4xQ", out, table + 24 * index, kind, len(raw), len(packed), offset)
        struct.pack_into("<Q", out, hashes + 8 * index, path_value)
    return bytes(out)


def test_stored_and_oodle_files_decode_in_table_order():
    raw_a, raw_b = b"A" * 40, b"BCD" * 9
    pack = make_pack([(1, gfpak.KIND_STORED, raw_a, raw_a),
                      (2, gfpak.KIND_OODLE, raw_b, raw_b[::-1])])
    seen = []

    def decompress(packed, size):
        seen.append(size)
        return packed[::-1]

    assert gfpak.decode(pack, decompress) == [raw_a, raw_b]
    assert seen == [len(raw_b)]


def test_path_hash_is_the_game_freak_fnv_of_the_path():
    assert gfpak.path_hash("") == 0xCBF29CE484222645        # the offset basis itself
    assert gfpak.path_hash("a") != gfpak.path_hash("b")


def test_file_names_take_the_layout_name_from_the_path_hash():
    layout = b"SARC" + b"\0" * 8 + b"blyt/battle_menu_00.bflyt"
    named = gfpak.path_hash("bin/appli/battle_menu/bin/battle_menu_00_eng.arc")
    assert gfpak.file_names([layout, b"\x01\x02"], [named, 7]) == ["00_battle_menu_00_eng.arc", "01.bin"]


def test_a_layout_with_no_known_path_keeps_its_own_layout_name():
    layout = b"SARC" + b"\0" * 8 + b"blyt/fieldinfo_zninfo_00.bflyt"
    assert gfpak.file_names([layout], [0]) == ["00_fieldinfo_zninfo_00.arc"]


def test_unknown_compression_and_wrong_magic_are_refused():
    pack = make_pack([(1, gfpak.KIND_STORED, b"x", b"x")])
    bad_kind = bytearray(pack)
    struct.pack_into("<H", bad_kind, 0x40 + 2, 5)
    with pytest.raises(gfpak.GfpakError):
        gfpak.read_entries(bytes(bad_kind))
    with pytest.raises(gfpak.GfpakError):
        gfpak.read_entries(b"NOTAPACK" + pack[8:])


def test_replace_stored_stores_the_changed_entry_and_keeps_the_others():
    pack = make_pack([(1, gfpak.KIND_STORED, b"AAAA", b"AAAA"),
                      (2, gfpak.KIND_OODLE, b"BBBBBBBB", b"BBBBBBBB"[::-1])])
    out = gfpak.replace_stored(pack, {0: b"CCCCCCCCC"})
    entries = gfpak.read_entries(out)
    assert [e.kind for e in entries] == [gfpak.KIND_STORED, gfpak.KIND_OODLE]
    assert entries[0].packed == b"CCCCCCCCC" and entries[0].size == 9
    assert entries[1].packed == b"BBBBBBBB"[::-1] and entries[1].size == 8
    assert gfpak.decode(out, lambda packed, size: packed[::-1]) == [b"CCCCCCCCC", b"BBBBBBBB"]
