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


def test_the_plugin_names_the_3ds_key_and_the_source_folder():
    rules = GameRules(None)
    assert rules.unpack_key_consoles() == ["3ds"]
    assert rules.get_source_subfolder() == "source/romfs"


def test_a_folder_source_is_left_to_the_wizard(tmp_path):
    folder = tmp_path / "game"
    folder.mkdir()
    assert GameRules(None).unpack_sources({"base": str(folder)}, str(tmp_path / "out"),
                                          lambda *_: None, lambda: False) is None


def test_a_3ds_image_is_identified_as_a_base_game_and_other_files_are_not(monkeypatch):
    from types import SimpleNamespace

    from plugins.luigis_mansion_2 import rules as rules_module

    fake = SimpleNamespace(KIND_3DS="3ds", identify=lambda path: {"kind": "3ds", "title_id": "0004000000076500"})
    monkeypatch.setattr(rules_module, "images", fake)
    assert GameRules(None).identify_source("game.cia") == {"role": "base", "platform": "3ds"}
    monkeypatch.setattr(rules_module, "images", SimpleNamespace(KIND_3DS="3ds", identify=lambda path: None))
    assert GameRules(None).identify_source("notes.txt") is None
