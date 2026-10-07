"""Twilight Princess on Wii and Wii U (HD): the zelda_bmg plugin reads and saves their message files
byte for byte, knows the HD-only Wii U control tags, and the BFN code reads the HD fonts (I8 sheets,
seven MAP1 blocks with (code, glyph) pairs).

The real-file tests use the owner's workspaces and skip where they are absent.
"""
import struct
from pathlib import Path

import pytest

from core.bfn_core import BfnCore, char_to_glyph, map_lists_to_pairs, map_pairs_to_lists
from core.containers import ContainerManager, yaz0
from plugins.zelda_bmg.bmg_tool import BMGFile
from plugins.zelda_bmg.rules import GameRules
from plugins.zelda_bmg.tag_catalog import TP_CATALOG, fixed_escape_widths
from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic

ZELDA = Path(r"E:\Emulators\RomHacking\Zelda")
WII_MSG = ZELDA / "Twilight Princess" / "_archive" / "Wii workspace (agent 2026-10-04)" / "source" / "files" / "res" / "Msgus"
HD_MSG = ZELDA / "Twilight Princess" / "_reference" / "HD RU 1.0 (Zelda64Rus)" / "_TP_HD_Kruptar+Fonts_(EN)_(PAL)" / "Original" / "Msguk"
HD_FONTS = ZELDA / "Twilight Princess" / "HD - Wii U" / "source" / "content" / "res" / "Fonteu"


# ------------------------------------------------------------------ Wii U control tags

@pytest.mark.parametrize("raw, alias", [
    ("{escape:7:0006}", "{U:ZL}"),
    ("{escape:7:0001}", "{U:L stick}"),
    ("{escape:7:000d}", "{U:NFC}"),
])
def test_hd_wii_u_tags_read_as_named_icons_one_font_size_wide(raw, alias):
    assert TP_CATALOG.editor_alias(raw) == alias
    assert fixed_escape_widths()[raw]["width"] == 24
    assert "targeting" in TP_CATALOG.describe(7, "0006")


def test_the_gamecube_and_wii_tags_keep_their_aliases():
    assert TP_CATALOG.editor_alias("{escape:0:000a}") == "{GC:A}"
    assert TP_CATALOG.editor_alias("{escape:3:0014}") == "{W:Nunchuk Z}"


def test_an_hd_line_measures_its_icons_and_round_trips_through_the_editor():
    rules = GameRules()
    raw = "Press {escape:7:0006} to target."
    assert rules.convert_editor_text_to_data(rules.get_text_representation_for_editor(raw)) == raw
    assert rules.calculate_string_width_override(raw, {}) == \
        rules.calculate_string_width_override("Press  to target.", {}) + 24


# ------------------------------------------------------------------ BFN: I8 sheets and split maps

def _bfn_i8() -> bytes:
    """A two-glyph I8 font (8x4 sheet) with a type-2 and a type-3 map, laid out like the HD fonts."""
    def chunk(magic, body):
        data = bytearray(magic + b"\0\0\0\0" + body)
        data += bytes(-len(data) % 32)
        struct.pack_into(">I", data, 4, len(data))
        return bytes(data)

    inf = chunk(b"INF1", struct.pack(">HHHHHHI", 0, 3, 1, 4, 4, 0, 0))
    sheet = bytes(range(0, 256, 8))                                     # 8x4 texels, one tile
    gly = chunk(b"GLY1", struct.pack(">HHHHIHHHHH", 0, 1, 4, 4, len(sheet), 1, 2, 1, 8, 4) + b"\0\0" + sheet)
    map2 = chunk(b"MAP1", struct.pack(">HHHH", 2, 65, 65, 1) + struct.pack(">H", 0))
    map3 = chunk(b"MAP1", struct.pack(">HHHH", 3, 32, 66, 2) + struct.pack(">4H", 65, 1, 66, 1))
    wid = chunk(b"WID1", struct.pack(">HH", 0, 2) + bytes([1, 3, 0, 4]))
    body = inf + gly + map2 + map3 + wid
    return struct.pack(">8sII", b"FONTbfn1", 32 + len(body), 5) + bytes(16) + body


def test_an_i8_font_with_split_maps_extracts_and_repacks_byte_for_byte(tmp_path):
    data = _bfn_i8()
    (tmp_path / "f.bfn").write_bytes(data)
    extract_bfn_logic(str(tmp_path / "f.bfn"), str(tmp_path / "x"))
    repack_bfn_logic(str(tmp_path / "x"), str(tmp_path / "o.bfn"))
    assert (tmp_path / "o.bfn").read_bytes() == data


def test_split_maps_resolve_like_the_game_first_block_wins():
    core = BfnCore()
    core.load(_bfn_i8())
    assert char_to_glyph(core.map1) == {65: 0, 66: 1}            # 'A' stays with the type-2 block
    assert set(core.to_font_map()) == {"A", "B"}
    assert core.map1[1]["entries"] == [65, 66, 1, 1]            # codes, then glyphs
    assert map_lists_to_pairs(map_pairs_to_lists([65, 1, 66, 1])) == [65, 1, 66, 1]
    assert len(core.get_sheets_qimages()) == 1


# ------------------------------------------------------------------ real files

def _bmgs(folder: Path, pattern: str):
    if not folder.is_dir():
        pytest.skip(f"{folder} is not on this machine")
    for path in sorted(folder.glob(pattern)):
        container = ContainerManager.open(path.read_bytes())
        for member in container.list_files():
            if member.endswith(".bmg"):
                yield path, container, member


@pytest.mark.parametrize("folder, pattern", [(WII_MSG, "bmgres*.arc"), (HD_MSG, "bmgres*.rarc")],
                         ids=["wii", "hd"])
def test_every_message_file_saves_back_byte_for_byte(folder, pattern):
    count = 0
    for _path, container, member in _bmgs(folder, pattern):
        raw = container.read_file(member)
        rules = GameRules()
        blocks, _ = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, member
        count += 1
    assert count == 10


def test_a_wii_archive_with_its_own_files_written_back_is_unchanged():
    for path, container, member in _bmgs(WII_MSG, "bmgres*.arc"):
        container.write_file(member, container.read_file(member))
        assert yaz0.decompress(container.pack()) == yaz0.decompress(path.read_bytes()), path.name


def test_an_hd_archive_repacks_with_every_member_intact():
    # The HD archives on this machine come from the Kruptar project, which leaves data after the
    # last file; the game's own archives are not here, so only the members are compared.
    for path, container, member in _bmgs(HD_MSG, "bmgres*.rarc"):
        before = {name: container.read_file(name) for name in container.list_files()}
        container.write_file(member, container.read_file(member))
        again = ContainerManager.open(container.pack())
        assert {name: again.read_file(name) for name in again.list_files()} == before, path.name


def test_hd_message_ids_match_the_gamecube_ones():
    first = next(_bmgs(HD_MSG, "bmgres.rarc"))
    bmg = BMGFile()
    bmg.load(first[1].read_file("zel_00.bmg"))
    assert [getattr(m, "id", None) for m in bmg.messages[:3]] == [1, 2, 3]
    assert len(bmg.messages) == 5000


@pytest.mark.parametrize("name", ["fontres.arc", "rubyres.arc"])
def test_hd_fonts_round_trip_and_map_every_glyph(tmp_path, name):
    path = HD_FONTS / name
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    container = ContainerManager.open(path.read_bytes())
    data = container.read_file(container.list_files()[0])
    (tmp_path / "f.bfn").write_bytes(data)
    extract_bfn_logic(str(tmp_path / "f.bfn"), str(tmp_path / "x"))
    repack_bfn_logic(str(tmp_path / "x"), str(tmp_path / "o.bfn"))
    assert (tmp_path / "o.bfn").read_bytes() == data
    core = BfnCore()
    core.load(data)
    assert core.gly1[0]["texture_format"] == 1 and len(core.map1) == 7
    assert len(core.to_font_map()) == core.gly1[0]["end_glyph"] + 1
