"""Luigi's Mansion: Dark Moon wizard unpack: the .dict / .data pairs become the source folder (synthetic pairs only)."""
import struct
import zlib

import pytest

from core.texture_formats import nlg_tex
from plugins.luigis_mansion_2 import unpack
from plugins.luigis_mansion_2.rules import GameRules


def make_pair(members, packed=False):
    """A ``.dict`` / ``.data`` pair holding ``members`` in order, the layout of the real files."""
    count = len(members)
    data, entries = bytearray(), []
    for blob in members:
        raw = zlib.compress(blob) if packed else blob
        entries.append((len(data), len(blob), len(raw) if packed else 0, 0))
        data += raw
    table = 0x2C + count
    head = bytearray(table + 16 * count)
    struct.pack_into("<I", head, 0, unpack.DICT_MAGIC)
    head[6] = 1 if packed else 0
    struct.pack_into("<I", head, 8, count)
    for index, entry in enumerate(entries):
        struct.pack_into("<IIII", head, table + 16 * index, *entry)
    return bytes(head), bytes(data)


def write_pair(romfs, rel, members, packed=False):
    dict_bytes, data = make_pair(members, packed)
    path = romfs.joinpath(*rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".dict").write_bytes(dict_bytes)
    path.with_suffix(".data").write_bytes(data)


def make_hd_pair(members):
    """A Switch HD ``.dict`` / ``.data`` pair: members on 0x200 boundaries, the entry table before the names at the end."""
    data, entries = bytearray(), []
    for blob in members:
        data += bytes((-len(data)) % 0x200)
        entries.append((len(data), len(blob), 0, 0))
        data += blob
    head = bytearray(0x2C + len(members))
    struct.pack_into("<I", head, 0, unpack.DICT_MAGIC)
    struct.pack_into("<I", head, 8, len(members))
    table = b"".join(struct.pack("<IIII", *entry) for entry in entries)
    return bytes(head) + table + unpack.HD_NAMES, bytes(data)


def write_hd_pair(romfs, rel, members):
    dict_bytes, data = make_hd_pair(members)
    path = romfs.joinpath(*rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".dict").write_bytes(dict_bytes)
    path.with_suffix(".data").write_bytes(data)


HEADER = b"\x00" * 12
NLOC = b"NLOC" + bytes(range(60))
TABLE = b"\x50\x43\xe9\x97" + bytes(44)
PIXELS = bytes(range(256)) * 4


@pytest.mark.parametrize("packed", [False, True])
def test_a_text_table_becomes_strings_nloc(tmp_path, packed):
    romfs = tmp_path / "romfs"
    write_pair(romfs, "art/fe/english", [HEADER, HEADER, TABLE, NLOC], packed)
    unpack.expand_pairs(tmp_path)
    assert (tmp_path / "source" / "romfs" / "art" / "fe" / "english.data" / "strings.nloc").read_bytes() == NLOC
    assert (romfs / "art" / "fe" / "english.data").is_file()   # the raw data file stays where it was


def test_a_bundle_joins_its_table_and_pixels_as_nlgb(tmp_path):
    write_pair(tmp_path / "romfs", "art/fe/febundleFonts_res", [HEADER, HEADER, TABLE, PIXELS])
    unpack.expand_pairs(tmp_path)
    bundle = tmp_path / "source" / "romfs" / "art" / "fe" / "febundlefonts_res.data" / "bundle.nlgb"
    assert bundle.read_bytes() == nlg_tex.join(TABLE, PIXELS)
    assert nlg_tex.split(bundle.read_bytes()) == (TABLE, PIXELS)


def test_the_staff_roll_is_renamed_to_credits(tmp_path):
    (tmp_path / "romfs" / "art" / "fe").mkdir(parents=True)
    (tmp_path / "romfs" / "art" / "fe" / "credits.txt").write_bytes(b"staff\n")
    unpack.expand_pairs(tmp_path)
    assert (tmp_path / "source" / "romfs" / "art" / "fe" / "credits.credits").read_bytes() == b"staff\n"


def test_a_file_that_is_not_a_pair_table_is_refused(tmp_path):
    path = tmp_path / "romfs" / "art" / "fe" / "english.dict"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a table" * 8)
    path.with_suffix(".data").write_bytes(b"")
    with pytest.raises(ValueError):
        unpack.expand_pairs(tmp_path)


def test_the_plugin_names_the_3ds_and_switch_keys_and_the_source_folder():
    rules = GameRules(None)
    assert rules.unpack_key_consoles() == ["3ds", "switch"]
    assert rules.get_source_subfolder() == "source/romfs"


def test_a_switch_image_writes_only_the_pair_folder_and_the_staff_roll():
    assert unpack.switch_pairs_only("romfs/art/fe/english.dict")
    assert unpack.switch_pairs_only("romfs/art/fe/credits.txt")
    assert not unpack.switch_pairs_only("romfs/exefs/main")
    assert not unpack.switch_pairs_only("romfs/art/other.dict")


def test_a_folder_source_is_left_to_the_wizard(tmp_path):
    folder = tmp_path / "game"
    folder.mkdir()
    assert GameRules(None).unpack_sources({"base": str(folder)}, str(tmp_path / "out"),
                                          lambda *_: None, lambda: False) is None


def test_a_3ds_image_is_identified_as_a_base_game_and_other_files_are_not(monkeypatch):
    from types import SimpleNamespace

    from plugins.luigis_mansion_2 import rules as rules_module

    fake = SimpleNamespace(KIND_3DS="3ds", KIND_SWITCH="switch",
                           identify=lambda path: {"kind": "3ds", "title_id": "0004000000076500"})
    monkeypatch.setattr(rules_module, "images", fake)
    assert GameRules(None).identify_source("game.cia") == {"role": "base", "platform": "3ds"}
    monkeypatch.setattr(rules_module, "images", SimpleNamespace(KIND_3DS="3ds", KIND_SWITCH="switch",
                                                                identify=lambda path: None))
    assert GameRules(None).identify_source("notes.txt") is None


def test_the_switch_hd_base_game_is_identified_and_another_switch_title_is_not(monkeypatch):
    from types import SimpleNamespace

    from plugins.luigis_mansion_2 import rules as rules_module

    monkeypatch.setattr(rules_module, "images", SimpleNamespace(
        KIND_3DS="3ds", KIND_SWITCH="switch",
        identify=lambda path: {"kind": "switch", "title_id": "010048701995E000"}))
    assert GameRules(None).identify_source("hd.nsp") == {"role": "base", "platform": "switch"}
    monkeypatch.setattr(rules_module, "images", SimpleNamespace(
        KIND_3DS="3ds", KIND_SWITCH="switch", identify=lambda path: {"kind": "switch", "title_id": "0100ABCD00000000"}))
    assert GameRules(None).identify_source("other.nsp") is None


def test_a_switch_hd_pair_gives_strings_nloc_and_a_nlgh_bundle(tmp_path):
    romfs = tmp_path / "romfs"
    write_hd_pair(romfs, "art/fe/ukenglish", [HEADER, HEADER, TABLE, NLOC])
    write_hd_pair(romfs, "art/fe/febundleFonts_res", [HEADER, HEADER, TABLE, PIXELS])
    unpack.expand_pairs(tmp_path, hd=True)
    fe = tmp_path / "source" / "romfs" / "art" / "fe"
    assert (fe / "ukenglish.data" / "strings.nloc").read_bytes() == NLOC
    assert (fe / "febundlefonts_res.data" / "bundle.nlgh").read_bytes() == b"NLGH" + TABLE
    assert not (fe / "febundlefonts_res.data" / "bundle.nlgb").exists()
