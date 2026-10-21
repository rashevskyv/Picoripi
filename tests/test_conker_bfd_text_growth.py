"""Conker's Bad Fur Day text growth: containers, pages, bank relayout, BPS and the plugin's table format.

Every ROM here is synthetic (made-up strings, a 64 MiB cartridge image with a small bank table). No game data.
"""
import json
import struct

import pytest

from plugins.conker_bfd import book_pages, book_text, bps, containers as ct, n64_archive as na, rom_layout
from plugins.conker_bfd.rules import FORMAT_ID, LEGACY_FORMAT_ID, GameRules

ROM_SIZE = 0x4000000
BANKS = 0x1E
TABLE = na.US_ASSET_TABLE


def _page(text: bytes, codes: bytes = b"") -> bytes:
    return book_pages.Page(text=text, codes=codes).payload()


def _entry(pages):
    """A bank 0x1A entry: a container whose slots hold the given page payloads (None = empty slot)."""
    slots = [ct.empty_slot() if p is None else ct.raw_slot(p, 0) for p in pages]
    return ct.build_container(slots)


def _holder(subs):
    """A bank 0x1C holder: a container of four sub-tables, each a NUL-separated list of strings."""
    slots = [ct.rzip_slot(b"\x00".join(strings), 0) for strings in subs]
    return ct.build_container(slots)


def make_rom(banks):
    """A synthetic cartridge: outer table at the real offset, banks in index order, filler elsewhere."""
    rom = bytearray(b"\xff") * ROM_SIZE
    pos = TABLE + 8 * BANKS
    for index in range(BANKS):
        content = banks.get(index, bytes(range(16)))
        rom[pos:pos + len(content)] = content
        flags = 8 if index == 0x1D else 0
        struct.pack_into(">II", rom, TABLE + 8 * index, pos - TABLE, len(content) | (flags << 28))
        pos += ct_align(len(content))
    struct.pack_into(">I", rom, TABLE, 8 * BANKS)
    return bytes(rom)


def ct_align(value):
    return (value + 7) & ~7


def synthetic_rom(extra_pages=None):
    book = [_entry([_page(b"Alpha beta gamma.\x00\x00"), None, _page(b"Delta.\x00"), _page(b"E.\x00"),
                    _page(b"F.\x00"), _page(b"G.\x00"), _page(b"H.\x00")]),
            _entry([_page(b"One.\x00")])]
    holder = _holder([[b"CONTINUE", b"", b"RESTART GAME"], [b"ON", b"OFF"], [b"Solo"], [b"A", b"B", b"C"]])
    banks = {0x1A: ct.build_container([ct.raw_slot(book[0], 0), ct.raw_slot(book[1], 0)]),
             0x1C: ct.build_container([ct.raw_slot(holder, 0)])}
    return make_rom(banks)


def test_container_rebuilds_the_same_bytes_and_keeps_empty_slot_flags():
    blob = _entry([None, _page(b"Hi.\x00")])
    slots = ct.parse_container(blob)
    assert ct.build_container(slots) == blob
    assert slots[0].empty and slots[0].flags == 0 and not slots[1].empty
    flagged = ct.build_container([ct.empty_slot(0x80), ct.raw_slot(b"abc", 0)])
    assert ct.parse_container(flagged)[0].flags == 0x80
    assert ct.parse_container(flagged)[1].stored == b"abc"


def test_empty_slot_offset_is_the_next_write_position():
    data = ct.build_container([ct.raw_slot(b"12345678", 0), ct.empty_slot(), ct.raw_slot(b"ab", 0)])
    assert struct.unpack_from(">II", data, 8) == (0x18 + 8, 0)     # empty slot 1: after the first blob
    assert struct.unpack_from(">II", data, 16) == (0x18 + 8, 2)    # slot 2 starts there too


def test_page_layout_follows_the_header_formula():
    payload = _page(b"Text here.\x00\x00", codes=b"\x00\xab\x00\xac")
    assert struct.unpack_from(">IIII", payload, 0) == (0x10, 12, 0x10 + 16, 0x80000004)
    page = book_pages.parse_page(payload)
    assert page.text == b"Text here.\x00\x00" and page.codes == b"\x00\xab\x00\xac"
    assert page.payload() == payload


def test_malformed_pages_are_not_pages():
    good = _page(b"Ok.\x00")
    assert book_pages.parse_page(good[:8]) is None
    assert book_pages.parse_page(good[:0x10] + b"Ok.!" + good[0x14:]) is None   # text does not end in NUL
    bad_start = bytearray(good)
    struct.pack_into(">I", bad_start, 0, 0x20)
    assert book_pages.parse_page(bytes(bad_start)) is None


def test_bps_round_trip_and_crc_checks():
    source = bytes((i * 7) & 0xFF for i in range(4096))
    target = source[:1000] + b"NEW DATA HERE" + source[1000:3000] + b"\xff" * 300
    patch = bps.make_bps(source, target)
    assert bps.apply_bps(source, patch) == target
    with pytest.raises(na.RomError):
        bps.apply_bps(source + b"\x00", patch)
    damaged = bytearray(patch)
    damaged[len(damaged) // 2] ^= 0x55
    with pytest.raises(na.RomError):
        bps.apply_bps(source, bytes(damaged))


def test_relayout_without_changes_is_the_same_rom():
    rom = synthetic_rom()
    assert rom_layout.relayout_banks(rom, {}) == rom
    banks = na.parse_banks(rom)
    same = rom_layout.relayout_banks(rom, {0x1A: bytes(rom[banks[0x1A].start:banks[0x1A].end])})
    assert same == rom


def test_growing_a_page_moves_the_later_banks_and_keeps_the_size():
    rom = synthetic_rom()
    tables = book_text.extract(rom)
    page = next(i for i in tables[0].items if i.kind == book_text.KIND_PAGE)
    page.text = page.text + b" More words here, a longer page than before." * 4
    changed = book_text.rebuild(rom, tables)
    assert set(changed) == {0x1A}
    new_rom = rom_layout.relayout_banks(rom, changed)
    assert len(new_rom) == len(rom)
    back = book_text.extract(new_rom)
    assert [t.name for t in back] == [t.name for t in tables]
    assert next(i for i in back[0].items if i.kind == book_text.KIND_PAGE).text == page.text
    assert [(i.kind, i.text, i.codes, i.raw) for t in back[1:] for i in t.items] == \
        [(i.kind, i.text, i.codes, i.raw) for t in tables[1:] for i in t.items]
    assert book_text.rebuild(new_rom, back) == {}


def test_menu_strings_grow_and_a_nul_is_refused():
    rom = synthetic_rom()
    tables = book_text.extract(rom)
    menu = next(t for t in tables if t.name.endswith("sub_0000"))
    menu.items[0].text = b"A MUCH LONGER OPTION NAME THAN BEFORE"
    changed = book_text.rebuild(rom, [menu])
    new_rom = rom_layout.relayout_banks(rom, changed)
    grown = next(t for t in book_text.extract(new_rom) if t.name == menu.name)
    assert grown.items[0].text == b"A MUCH LONGER OPTION NAME THAN BEFORE"
    assert [i.text for i in grown.items[1:]] == [i.text for i in menu.items[1:]]
    menu.items[1].text = b"BAD\x00SPLIT"
    with pytest.raises(ValueError):
        book_text.rebuild(rom, [menu])


def test_table_json_round_trip_is_exact():
    rom = synthetic_rom()
    for table in book_text.extract(rom):
        obj = book_text.table_to_json(table, {"map": "00", "glyphs": []})
        assert obj["format"] == FORMAT_ID
        back = book_text.table_from_json(json.loads(json.dumps(obj)))
        assert [(i.kind, i.text, i.nul, i.codes, i.raw, i.flags) for i in back.items] == \
               [(i.kind, i.text, i.nul, i.codes, i.raw, i.flags) for i in table.items]


def test_plugin_loads_saves_and_flags_only_characters_for_grow_able_tables():
    rom = synthetic_rom()
    obj = book_text.table_to_json(book_text.extract(rom)[0], None)
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(obj)
    assert names == {"0": "bank_1A/entry_0000"}
    assert rules.save_data_to_json_obj(blocks, names) == obj
    blocks[0][0] = blocks[0][0] + " a longer line of text that the old table could not hold"
    assert rules.get_text_fit_problems_for_string(0, 0, blocks[0][0]) == []
    assert rules.get_text_fit_problems_for_string(0, 0, "café") == ["CBFD_CHARACTER_NOT_IN_TEXT"]
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["items"][0]["text"] == blocks[0][0]


def test_legacy_text_files_still_open_and_do_not_build():
    legacy = {"format": LEGACY_FORMAT_ID, "source": "bank_1A/entry_0000", "bytes": 3,
              "segments": [{"kind": "text", "text": "Alpha beta."}], "font": {"map": "00", "glyphs": []}}
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(legacy)
    assert blocks == [["Alpha beta."]] and names == {"0": "bank_1A/entry_0000"}
    assert rules.save_data_to_json_obj(blocks, names)["format"] == LEGACY_FORMAT_ID


def test_reference_rom_strings_map_to_project_blocks_by_position(tmp_path):
    rom = synthetic_rom()
    tables = book_text.extract(rom)
    edited = next(t for t in tables if t.name == "bank_1A/entry_0000")
    first_page = next(i for i in edited.items if i.kind == book_text.KIND_PAGE)
    first_page.text = b"Reference text, made up, longer than the original page."
    ref = rom_layout.relayout_banks(rom, book_text.rebuild(rom, [edited]))
    ref_file = tmp_path / "reference.z64"
    ref_file.write_bytes(b"\x80\x37\x12\x40" + ref[4:])  # z64 byte order, as a real cartridge image has
    rules = GameRules()
    found = rules.load_multi_reference(str(ref_file), {"0": "bank_1A/entry_0000"})
    (column,) = found.values()
    assert column[(0, 0)] == "Reference text, made up, longer than the original page."
    assert len(column) == len(book_text.text_items(edited))
    assert rules.load_multi_reference(str(ref_file), {"0": "bank_1C/sub_0009"}) == {}  # no such table
    assert rules.load_multi_reference(str(ref_file), {"0": "bank_1C/sub_0000"}) == {}  # count differs from US


def test_reference_accepts_a_rom_and_refuses_patch_files(tmp_path):
    rules = GameRules()
    rom_file = tmp_path / "patched.z64"
    rom_file.write_bytes(b"x")
    assert rules.unpack_reference(str(rom_file), str(tmp_path), None, lambda: False) is None
    with pytest.raises(ValueError):
        rules.unpack_reference(str(tmp_path / "fan.xdelta"), str(tmp_path), None, lambda: False)
    assert rules.reference_worker_rules()[1] is None
