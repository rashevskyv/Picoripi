"""Dragon Quest IX plugin: GPC2 archives, cfg / nat tables, the fi+fd fonts, pac and spr pictures; real data."""
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.containers import level5
from core.font_formats import char_map, char_code, map_entries
from core.font_formats.sources import join_pair
from plugins.dq9 import dqtext
from plugins.dq9.gpc2 import Gpc2
from plugins.dq9.pac import PacContainer
from plugins.dq9.rules import parse_file
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "dq9"
WS = Path(r"E:\Emulators\RomHacking\Dragon Quest\Dragon Quest IX")
SOURCE = WS / "source"
needs_data = pytest.mark.skipif(not (SOURCE / "data" / "pack_lv5" / "fi_me.bin").is_file(),
                                reason="Dragon Quest IX workspace not on disk")


def _cfg(*strings: bytes) -> bytes:
    """A cfg table: one entry per string (id, 2 arguments: an integer and the string)."""
    entries, pool, offsets = bytearray(), bytearray(), []
    for text in strings:
        offsets.append(len(pool))
        pool += text + b"\0"
    for n, offset in enumerate(offsets):
        entries += struct.pack("<HBB", n, 2, 0b0001) + struct.pack("<II", n, offset)
    head = 16 + len(entries)
    pool_at = head + -head % 16
    data = struct.pack("<4I", len(strings), pool_at, len(pool), len(strings)) + entries + b"\xff" * (pool_at - head)
    data += pool
    return data + b"\xff" * (-len(data) % 16)


def _nat(*pairs) -> bytes:
    """A nat table: records (id, name pointer, plural pointer, flags)."""
    pool, records = bytearray(), bytearray()
    for n, (one, many) in enumerate(pairs):
        a = len(pool)
        pool += one + b"\0"
        b = len(pool)
        pool += many + b"\0"
        records += struct.pack("<4I", 100 + n, a, b, 0x41)
    return struct.pack("<I", len(pool) << 12 | len(pairs)) + records + pool


def _gpc2(members: dict) -> bytes:
    names = bytearray()
    name_at = {}
    for name in members:
        name_at[name] = len(names)
        names += name.encode() + b"\0"
    names += bytes(-len(names) % 4)
    body, table = bytearray(), bytearray()
    for n, (name, data) in enumerate(members.items()):
        blob = level5.compress(data)
        table += struct.pack("<3I", n, len(body) // 4 | (name_at[name] & 0xFF) << 24, len(blob) | (name_at[name] >> 8) << 24)
        body += blob + bytes(-len(blob) % 4)
    packed_table = level5.compress(bytes(table), level5.STORED)
    packed_table += bytes(-len(packed_table) % 4)
    packed_names = level5.compress(bytes(names), level5.STORED)
    packed_names += bytes(-len(packed_names) % 4)
    names_at = 0x14 + len(packed_table)
    data_at = names_at + len(packed_names)
    head = b"GPC2" + struct.pack("<6HI", len(members), 5, names_at // 4, data_at // 4, len(table) // 4,
                                 len(names) // 4, len(body) // 4)
    return head + packed_table + packed_names + bytes(body)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_tags_and_line_breaks_become_editor_text_and_back():
    raw = b"*: Hello<,> <HERO>!\\nI<1>m here.<PAGE>\x83}"
    text = dqtext.to_editor(raw)
    assert text == "*: Hello{,} {HERO}!\nI{1}m here.{PAGE}[x83][x7D]"
    assert dqtext.from_editor(text) == raw


def test_a_cfg_table_grows_and_keeps_its_entries():
    data = _cfg(b"Welcome.", b"Goodbye.")
    table = dqtext.parse_cfg(data)
    assert table.strings == [b"Welcome.", b"Goodbye."] and table.build() == data
    again = dqtext.parse_cfg(table.build([b"UA TEST: a much longer welcome line", b"Goodbye."]))
    assert again.strings == [b"UA TEST: a much longer welcome line", b"Goodbye."]


def test_a_nat_table_finds_its_pointer_columns_and_grows():
    data = _nat((b"copper sword", b"copper swords"), (b"rapier", b"rapiers"))
    table = dqtext.parse_nat(data)
    assert table.pointers == [8, 24, 12, 28] or sorted(table.pointers) == [8, 12, 24, 28]
    grown = dqtext.parse_nat(table.build([b"a much longer copper sword", b"copper swords", b"rapier", b"rapiers"]))
    assert grown.strings[0] == b"a much longer copper sword" and grown.strings[3] == b"rapiers"


def test_a_gpc2_archive_repacks_only_the_edited_member():
    archive = _gpc2({"talk_en.bin": _cfg(b"Hello."), "talk_de.bin": _cfg(b"Hallo.")})
    parsed = Gpc2(archive)
    assert parsed.build() == archive and parsed.names == ["talk_en.bin", "talk_de.bin"]
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(archive)
    assert blocks == [["Hello."]]
    blocks[0][0] = "UA TEST: Hello there, a longer line."
    saved = rules.save_data_to_json_obj(blocks, names)
    again = Gpc2(saved)
    assert dqtext.parse_cfg(again.read("talk_en.bin")).strings == [b"UA TEST: Hello there, a longer line."]
    assert again.read("talk_de.bin") == parsed.read("talk_de.bin")


def _font() -> bytes:
    glyphs = [("A", 5), ("e", 4), ("<1>", 2)]
    names = b"".join(n.encode() + b"\0" for n, _w in glyphs)
    table_at = 24
    names_at = table_at + 8 * len(glyphs)
    table, at, x = bytearray(), names_at, 0
    for name, width in glyphs:
        table += struct.pack("<IBBH", at, width, 1, x)
        at += len(name) + 1
        x += width + 1
    fi = b"1.1\0" + struct.pack("<5I", len(glyphs), 0, 24, table_at, names_at) + table + names
    strip = bytearray(2 * 12)
    strip[3 * 2] = 0b11111000                                # a row of 'A'
    fd = b"1.0\0" + struct.pack("<HHII", 16, 12, len(strip), 16) + bytes(strip)
    return join_pair(fi, fd)


def test_the_font_packs_back_and_takes_a_new_letter():
    blob = _font()
    metadata, sheets = font_formats.extract("dq9", blob, {"spare": 4})
    assert font_formats.pack("dq9", metadata, sheets, blob, {"spare": 4}) == blob
    assert char_map(metadata) == {"A": 0, "e": 1}
    entries = metadata["MAP1"][0]["entries"]
    half = len(entries) // 2
    metadata["MAP1"] = [map_entries(list(zip(entries[:half], entries[half:])) + [(char_code("Ї"), 3)])]
    ImageDraw.Draw(sheets[0]).rectangle((3 * 16 + 1, 2, 3 * 16 + 2, 10), fill=(255, 255, 255, 255))
    packed = font_formats.pack("dq9", metadata, sheets, blob, {"spare": 4})
    again, _sheets = font_formats.extract("dq9", packed, {"spare": 3})
    assert char_map(again)["Ї"] == 3


def test_a_pac_member_is_replaced_in_place():
    char = b"CHAR" + struct.pack("<HHHBBI", 0, 1, 1, 0, 0, 32) + bytes(range(32))
    head = b"tiles.bncg".ljust(0x40, b"\0") + struct.pack("<3I", 0x50, len(char), 0x50 + len(char)) + bytes(4)
    pack = head + char + bytes(0x50)
    container = PacContainer(pack)
    assert container.list_files() == ["tiles.bncg"] and container.pack() == pack
    container.write_file("tiles.bncg", char[:16] + bytes(32))
    assert PacContainer(container.pack()).read_file("tiles.bncg") == char[:16] + bytes(32)


def test_an_spr_picture_writes_back():
    head = struct.pack("<5H", 1, 3, 8, 2, 0) + bytes(6)
    pixels = bytes([0x21] * 8)
    palette = struct.pack("<16H", 0x7C1F, 0x7FFF, 0x001F, *([0] * 13))
    data = head + pixels + palette + b"tail"
    texture = texture_formats.read("dq9_spr", data)[0]
    assert texture.image.size == (8, 2)
    assert texture_formats.write("dq9_spr", data, {0: texture.image}) == data
    image = texture.image.copy()
    image.putpixel((0, 0), (255, 0, 0, 255))
    assert texture_formats.write("dq9_spr", data, {0: image})[16] & 0x0F == 2


# -- real data -------------------------------------------------------------------------------------------------


@needs_data
def test_every_english_table_of_the_workspace_saves_back_byte_for_byte():
    rules = load_rules(PLUGIN)
    files = strings = 0
    for path in sorted(SOURCE.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        count = sum(len(block) for block in blocks)
        if count:
            files += 1
            strings += count
            assert rules.save_data_to_json_obj(blocks, names) == data, path
    assert files > 1500 and strings > 60000


@needs_data
def test_a_talk_line_grows_inside_its_archive():
    data = (SOURCE / "data" / "bin" / "menu" / "str_op.gp2").read_bytes()
    text = parse_file(data)
    member, table = text.members[0]
    new = [list(t.strings) for _n, t in text.members]
    new[0][3] = b"UA TEST: " + new[0][3]
    again = parse_file(text.build(new))
    assert again.members[0][1].strings[3].startswith(b"UA TEST: ") and again.members[0][0] == member


@needs_data
def test_both_fonts_pack_back_unchanged():
    for name in ("me", "s7"):
        blob = join_pair((SOURCE / "data" / "pack_lv5" / f"fi_{name}.bin").read_bytes(),
                         (SOURCE / "data" / "pack_lv5" / f"fd_{name}.bin").read_bytes())
        metadata, sheets = font_formats.extract("dq9", blob, {"spare": 66})
        assert font_formats.pack("dq9", metadata, sheets, blob, {"spare": 66}) == blob
        assert {"A", "z", "0"} <= set(char_map(metadata))


@needs_data
def test_the_title_logo_reads_and_writes_back():
    from core.containers import ContainerManager
    from core.texture_formats.sources import unwrap
    from plugins.dq9.gpc2 import Gpc2Container
    ContainerManager.register(Gpc2Container)
    ContainerManager.register(PacContainer)
    raw = (SOURCE / "data" / "menu" / "bg_up.gp2").read_bytes()
    entry = next(e for e in __import__("json").loads(
        (Path(__file__).parents[3] / "plugins" / "dq9" / "texture_sources.json").read_text(encoding="utf-8"))
        if e["path"] == "data/menu/bg_up.gp2")
    data, rewrap = unwrap(raw, entry["member"], entry["params"])
    texture = texture_formats.read("tiles", data, entry["params"])[0]
    assert isinstance(texture.image, Image.Image) and texture.image.size == (256, 192)
    assert rewrap(texture_formats.write("tiles", data, {0: texture.image}, entry["params"])) == raw
