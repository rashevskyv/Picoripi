"""The World Ends with You plugin: message codec, pack archive, font backend; real-data round trips."""
import json
import struct
import sys
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.containers import ContainerManager, lz10
from core.containers.twewy_pack import TwewyPack, build, slots
from core.font_formats import twewy as twewy_font
from core.texture_formats.sources import unwrap
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.twewy import mestxt, textures

PLUGIN = "twewy"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / "twewy"
WS = Path(r"E:\Emulators\RomHacking\The World Ends With You")
SOURCE = WS / "source"
TEXT = SOURCE / "Apl_Fuk" / "mestxt.mes"
FONT = SOURCE / "Apl_Fuk" / "Grp_Font.bin"
needs_data = pytest.mark.skipif(not TEXT.is_file(), reason="The World Ends with You workspace not on disk")


def _codes(*codes: int) -> bytes:
    return struct.pack(f"<{len(codes)}H", *codes)


def _pack(members) -> bytes:
    """A pack with a descriptor, ``members`` and the end block."""
    count = len(members) + 2
    head = b"pack" + struct.pack("<I", count) + bytes(24) + bytes(8 * count)
    stored = [struct.pack("<II", len(members) + 1, 0) + bytes(24), *members, bytes(32)]
    return build(head, stored)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_codes_become_text_and_tags_and_back():
    raw = _codes(0x28, 0x45, 0xFFFE, 0xFFBC, 0x21, 0xFFBE, 0x00, 0xFFD0, 0x196, 0x11C, 0x226, 0xFFC4, 0xFFFF)
    text = mestxt.to_editor(raw)
    assert text == "He\n[color:4]A[/color] [num]é—[g:226][c:FFC4]"
    assert mestxt.from_editor(text) == raw


def test_square_brackets_of_the_font_never_read_as_tags():
    raw = _codes(0x3B, 0x41, 0x3D, 0xFFFF)
    assert mestxt.to_editor(raw) == "［a］"
    assert mestxt.from_editor("［a］") == raw


def test_a_character_the_font_lacks_is_refused():
    with pytest.raises(mestxt.FormatError):
        mestxt.from_editor("Привіт")


def test_message_file_split_join_and_index():
    data = _codes(0x21, 0xFFFF, 0x22, 0xFFFE, 0x23, 0xFFFF, 0)
    messages = mestxt.split(data)
    assert len(messages) == 2 and mestxt.join(messages) == data
    assert mestxt.table(data) == struct.pack("<4I", 0, 4, 4, 8)


def test_other_files_are_not_taken_for_messages():
    for data in (b"pack" + bytes(60), _codes(0x21, 0xFFFF, 0x2000, 0xFFFF, 0), _codes(0x21, 0xFFFF)):
        with pytest.raises(mestxt.FormatError):
            mestxt.split(data)


def test_the_plugin_saves_only_what_changed():
    data = _codes(0x21, 0xFFFF, 0x22, 0xFFFF, 0)
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["A", "B"]] and names == {"0": "Messages 0-1"}
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][1] = "UA TEST"
    saved = mestxt.split(rules.save_data_to_json_obj(blocks, names))
    assert saved[0] == _codes(0x21, 0xFFFF) and mestxt.to_editor(saved[1]) == "UA TEST"


def test_a_pack_member_is_read_plain_and_written_back_as_stored():
    plain = bytes(range(64)) * 8
    data = _pack([lz10.compress(plain, vram=True), b"raw member"])
    pack = TwewyPack(data)
    assert pack.list_files() == ["#0", "#1", "#2", "#3"]
    assert pack.read_file("#1") == plain and pack.read_file("#2") == b"raw member"
    pack.write_file("#1", plain)
    assert pack.pack() == data
    pack.write_file("#1", plain[::-1])
    pack.write_file("#2", b"a longer raw member than before")
    out = pack.pack()
    again = TwewyPack(out)
    assert again.read_file("#1") == plain[::-1] and again.read_file("#2") == b"a longer raw member than before"
    assert again.read_file("#3") == bytes(32)
    assert struct.unpack_from("<I", out, 8)[0] == len(out) - (0x20 + 8 * 4) == struct.unpack_from("<I", out, 0x44)[0]


def test_font_pages_decode_and_encode_the_same_nibbles():
    raw = bytes((i * 37) & 0xFF for i in range(twewy_font.PAGE_BYTES))
    assert twewy_font.encode_page(twewy_font.decode_page(raw)) == raw


# -- real data ---------------------------------------------------------------------------------------------------


@needs_data
def test_every_message_round_trips_byte_exact():
    data = TEXT.read_bytes()
    messages = mestxt.split(data)
    assert len(messages) == 25233 and mestxt.join(messages) == data
    assert all(mestxt.from_editor(mestxt.to_editor(m)) == m for m in messages)
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert len(blocks) == 51 and rules.save_data_to_json_obj(blocks, names) == data


@needs_data
def test_every_game_font_packs_back_and_an_edit_reads_back():
    data = FONT.read_bytes()
    for entry in json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8")):
        metadata, sheets = font_formats.extract("twewy", data, entry["params"])
        assert font_formats.pack("twewy", metadata, sheets, data, entry["params"]) == data
    params = {"pages": 6, "widths": 2, "cell": [10, 10], "columns": 25, "chars": "main"}
    metadata, sheets = font_formats.extract("twewy", data, params)
    sheets[0].paste(Image.new("RGBA", (7, 9), (255, 255, 255, 255)), (10, 10))
    metadata["WID1"][0]["packets"][0]["width"] = 9
    packed = font_formats.pack("twewy", metadata, sheets, data, params)
    again, again_sheets = font_formats.extract("twewy", packed, params)
    assert again_sheets[0].tobytes() == sheets[0].tobytes() and again["WID1"][0]["packets"][0]["width"] == 9


@needs_data
def test_every_pack_of_the_game_lays_out_to_its_own_bytes():
    def check(data: bytes) -> int:
        spans = slots(data)
        assert build(data, [data[a:a + n] if n else None for a, n in spans]) == data
        pack = TwewyPack(data)
        inner = [pack.read_file(name) for name in pack.list_files()]
        return 1 + sum(check(member) for member in inner if member[:4] == b"pack")
    count = sum(check(path.read_bytes()) for path in SOURCE.rglob("*.bin") if path.read_bytes()[:4] == b"pack")
    assert count > 3000


@needs_data
def test_texture_list_matches_the_game_files_and_every_picture_writes_back_unchanged():
    ContainerManager.register(TwewyPack)
    entries = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    assert entries == textures.describe(SOURCE)
    for entry in entries:
        raw = (SOURCE / entry["path"]).read_bytes()
        data, rewrap = unwrap(raw, entry.get("member", ""), entry["params"])
        image = texture_formats.read(entry["format"], data, entry["params"])[0].image
        assert rewrap(texture_formats.write(entry["format"], data, {0: image}, entry["params"])) == raw, entry["label"]


@needs_data
def test_the_rom_rebuilds_byte_exact_and_the_index_is_the_games():
    scripts = WS.parent / "_shared" / "scripts"
    roms = list((WS / "ISO" / "EU").glob("*.nds"))
    if not (scripts / "zt" / "twewy.py").is_file() or len(roms) != 1:
        pytest.skip("workspace scripts or the base ROM not on disk")
    sys.path.insert(0, str(scripts))
    try:
        from zt import twewy as zt_twewy
        from zt.nds import nitro_files
    finally:
        sys.path.remove(str(scripts))
    rom = roms[0].read_bytes()
    files = nitro_files(rom)
    assert zt_twewy.rebuild_nds(rom, files) == rom
    assert zt_twewy.message_index(files["Apl_Fuk/mestxt.bin"]) == files["Apl_Fuk/mestable.bin"]
    assert mestxt.table(files["Apl_Fuk/mestxt.bin"]) == files["Apl_Fuk/mestable.bin"]
