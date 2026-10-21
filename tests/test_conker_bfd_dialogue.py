"""Conker's Bad Fur Day dialogue (bank 0x06): nested containers, text leaves, pages and growth.

Every ROM here is synthetic (invented strings, a 64 MiB cartridge image with a small bank table). No game data.
"""
import json
import struct

from plugins.conker_bfd import containers as ct, dialogue, n64_archive as na, rom_layout
from plugins.conker_bfd.rules import GameRules

ROM_SIZE = 0x4000000
BANKS = 0x1E
TABLE = na.US_ASSET_TABLE
BANK = 0x06


def _align(value):
    return (value + 7) & ~7


def make_rom(banks):
    """A synthetic cartridge: outer table at the real offset, banks in index order, filler elsewhere."""
    rom = bytearray(b"\xff") * ROM_SIZE
    pos = TABLE + 8 * BANKS
    for index in range(BANKS):
        content = banks.get(index, bytes(range(16)))
        rom[pos:pos + len(content)] = content
        flags = 8 if index == 0x1D else 0
        struct.pack_into(">II", rom, TABLE + 8 * index, pos - TABLE, len(content) | (flags << 28))
        pos += _align(len(content))
    struct.pack_into(">I", rom, TABLE, 8 * BANKS)
    return bytes(rom)


def _entry(leaves):
    """A bank 0x06 entry: one slot per scene, each slot a container of leaves (RZIP, like the ROM)."""
    scenes = [ct.rzip_slot(ct.build_container([ct.rzip_slot(leaf, 0) if leaf is not None else ct.empty_slot()
                                               for leaf in scene]), 0) for scene in leaves]
    return ct.build_container(scenes)


TEXT = b"alpha beta\n   gamma . . .\xbddelta epsilon,\xbdzeta press \xa9\x00\x00\x00"
BINARY = b"\x00\x00\x00\x08\x80\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"
PAGES_BEFORE = [b"alpha beta\n   gamma . . .", b"delta epsilon,", b"zeta press \xa9", b"eta .", b"theta !"]


def synthetic_rom():
    entry = _entry([[TEXT, None, BINARY], [b"eta .\xbdtheta !\x00"]])
    return make_rom({BANK: ct.build_container([ct.raw_slot(entry, 0)])})


def _table(rom):
    return {t.name: t for t in dialogue.extract(rom)}["bank_06/entry_0000"]


def test_text_leaves_become_pages_and_binary_leaves_are_skipped():
    table = _table(synthetic_rom())
    assert [(p.path, p.index, p.nul, p.text) for p in table.pages] == [
        ((0, 0), 0, 3, PAGES_BEFORE[0]),
        ((0, 0), 1, 3, PAGES_BEFORE[1]),
        ((0, 0), 2, 3, PAGES_BEFORE[2]),
        ((1, 0), 0, 1, PAGES_BEFORE[3]),
        ((1, 0), 1, 1, PAGES_BEFORE[4]),
    ]


def test_binary_leaf_is_not_dialogue():
    assert dialogue.is_text_leaf(TEXT.rstrip(b"\x00"))
    assert not dialogue.is_text_leaf(BINARY.rstrip(b"\x00"))
    assert not dialogue.is_text_leaf(b"ab\x00cd efgh")  # a NUL inside the body


def test_unchanged_rom_gives_no_rebuild():
    rom = synthetic_rom()
    assert dialogue.rebuild(rom, dialogue.extract(rom)) == {}


def test_json_round_trip_keeps_pages():
    table = _table(synthetic_rom())
    again = dialogue.table_from_json(json.loads(json.dumps(dialogue.table_to_json(table, {"map": "00"}))))
    assert [(p.path, p.index, p.nul, p.text) for p in again.pages] == [(p.path, p.index, p.nul, p.text)
                                                                      for p in table.pages]


def test_edited_page_grows_the_bank_and_keeps_the_other_pages():
    rom = synthetic_rom()
    table = _table(rom)
    longer = b"a much longer line that the translator wrote for this bubble, more than before"
    table.pages[1].text = longer
    changed = dialogue.rebuild(rom, [table])
    assert set(changed) == {BANK}
    grown = rom_layout.relayout_banks(rom, changed)
    assert len(grown) == len(rom)
    edited = _table(grown)
    assert [p.text for p in edited.pages] == [PAGES_BEFORE[0], longer, PAGES_BEFORE[2], PAGES_BEFORE[3],
                                              PAGES_BEFORE[4]]
    assert [p.nul for p in edited.pages] == [3, 3, 3, 1, 1]   # NUL padding per leaf is kept


def test_shorter_page_keeps_every_offset():
    rom = synthetic_rom()
    table = _table(rom)
    table.pages[3].text = b"hi"                  # second scene, first leaf: a shorter blob
    changed = dialogue.rebuild(rom, [table])
    before = {b.index: b for b in na.parse_banks(rom)}[BANK]
    assert len(changed[BANK]) == before.end - before.start
    assert [p.text for p in _table(rom_layout.relayout_banks(rom, changed)).pages][3] == b"hi"


def test_binary_slot_next_to_text_is_untouched_after_edit():
    rom = synthetic_rom()
    table = _table(rom)
    table.pages[3].text = b"hi !"                        # second scene, first leaf
    grown = rom_layout.relayout_banks(rom, dialogue.rebuild(rom, [table]))
    bank = {b.index: b for b in na.parse_banks(grown)}[BANK]
    entry = na.parse_entries(grown, bank)[0]
    scenes = ct.parse_container(na.read_entry(grown, entry))
    first = ct.parse_container(scenes[0].payload())
    assert first[2].payload() == BINARY


def test_page_with_separator_or_nul_is_rejected():
    rom = synthetic_rom()
    table = _table(rom)
    table.pages[0].text = b"bad\xbdpage"
    try:
        dialogue.rebuild(rom, [table])
    except ValueError:
        pass
    else:
        raise AssertionError("a separator inside a page must not rebuild")


def test_plugin_loads_and_saves_dialogue_json():
    rom = synthetic_rom()
    obj = dialogue.table_to_json(_table(rom), {"map": "00", "glyphs": []})
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(obj)
    assert names == {"0": "bank_06/entry_0000"}
    assert blocks[0][0] == "alpha beta\n   gamma . . ."
    assert rules.get_text_fit_problems_for_string(0, 2, "fine\n") == []
    assert rules.get_text_fit_problems_for_string(0, 2, "bad\xbdpage") != []
    values = [[None, "NEW ONE", None, "NEW TWO", None]]
    saved = rules.save_data_to_json_obj(values, names)
    assert saved["items"][1]["text"] == "NEW ONE"
    assert saved["items"][3]["text"] == "NEW TWO"
    assert saved["items"][0]["text"] == "alpha beta\n   gamma . . ."
