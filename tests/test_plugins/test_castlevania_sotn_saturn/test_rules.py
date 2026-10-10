"""Castlevania: Symphony of the Night (Saturn) plugin: codec, string banks, fonts and dialogue pictures; real-data
round trips through the workspace scripts (skipped when the workspace is not on disk)."""
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from plugins.castlevania_sotn_saturn import codec
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "castlevania_sotn_saturn"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / PLUGIN
WS = Path(r"E:\Emulators\RomHacking\Castlevania\Symphony of the Night\Saturn")
SOURCE = WS / "source"
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
needs_data = pytest.mark.skipif(not (SOURCE / "text" / "GAME.PRG.sotnstext").is_file()
                                or not (SCRIPTS / "zt" / "sotnsat.py").is_file(),
                                reason="Symphony of the Night (Saturn) workspace not on disk")


def _bank(strings):
    return {"format": "sotn-saturn-text", "file": "TEST.PRG",
            "strings": [{"o": o, "e": e, "hex": raw.hex()} for o, e, raw in strings]}


def _zt():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from zt import sotnsat
    return sotnsat


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_both_encodings_become_text_and_tags_and_back():
    assert codec.decode("a", b"Necromancy\x01Laboratory\x90") == "Necromancy\nLaboratory[x90]"
    assert codec.encode("a", "Necromancy\nLaboratory[x90]") == (b"Necromancy\x01Laboratory\x90", [])
    raw = bytes(b - 0x20 for b in b"Richter") + b"\x0a\x00\x70"
    assert codec.decode("c", raw) == "Richter\n [x70]"
    assert codec.encode("c", "Richter\n [x70]") == (raw, [])
    assert codec.encode("a", "Їжak") == (b"??ak", ["Ї", "ж"])


def test_an_untouched_string_keeps_its_bytes_and_an_edit_is_encoded():
    rules = load_rules(PLUGIN)
    bank = _bank([(0x10, "a", b"Start the game"), (0x20, "a", b"Odd\x7fbyte"),
                  (0x40, "c", bytes(b - 0x20 for b in b"Short Sword")), (0x60, "n", bytes(b - 0x20 for b in b"Maria"))])
    blocks, names = rules.load_data_from_json_obj(bank)
    assert [len(b) for b in blocks] == [2, 1, 1] and names["2"].startswith("Speakers")
    assert rules.save_data_to_json_obj(blocks, names) == bank
    blocks[0][0] = "UA TEST"
    blocks[1][0] = "Short Sword II"
    blocks[2][0] = "Mariya"                             # a speaker name keeps its glyph count
    saved = rules.save_data_to_json_obj(blocks, names)
    assert bytes.fromhex(saved["strings"][0]["hex"]) == b"UA TEST"
    assert saved["strings"][1] == bank["strings"][1]
    assert codec.decode("c", bytes.fromhex(saved["strings"][2]["hex"])) == "Short Sword II"
    assert codec.decode("n", bytes.fromhex(saved["strings"][3]["hex"])) == "Mariy"


@needs_data
def test_every_string_bank_loads_and_saves_unchanged():
    rules = load_rules(PLUGIN)
    total = 0
    for path in sorted((SOURCE / "text").glob("*.sotnstext")):
        bank = json.loads(path.read_text(encoding="utf-8"))
        blocks, names = rules.load_data_from_json_obj(bank)
        total += sum(len(b) for b in blocks)
        assert rules.save_data_to_json_obj(blocks, names) == bank, path.name
    assert total >= 1100


@needs_data
def test_every_font_packs_back_and_a_box_glyph_reads_back(tmp_path):
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) == 3
    for font in found:
        original = font.read_original()
        metadata, sheets = font_formats.extract(font.format, original, font.params)
        assert font_formats.pack(font.format, metadata, sheets, original, font.params) == original, font.label
        cell = font.params["cell"]
        sheets[0].paste(Image.new("RGBA", (cell[0], cell[1]), (255, 255, 255, 255)), (cell[0] * 1, 0))
        packed = font_formats.pack(font.format, metadata, sheets, original, font.params)
        assert packed != original and len(packed) == len(original)
        again = font_formats.extract(font.format, packed, font.params)[1][0]
        assert again.crop((cell[0], 0, cell[0] * 2, cell[1])).tobytes() == \
            sheets[0].crop((cell[0], 0, cell[0] * 2, cell[1])).tobytes()


@needs_data
def test_every_dialogue_picture_and_the_logo_write_back_unchanged_and_take_an_edit():
    entries = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    assert len(entries) == 22
    for entry in entries:
        data = (SOURCE / entry["path"]).read_bytes()
        textures = texture_formats.read(entry["format"], data, entry["params"])
        images = {i: t.image for i, t in enumerate(textures)}
        assert texture_formats.write(entry["format"], data, images, entry["params"]) == data, entry["label"]
    assert [t.image.size for t in texture_formats.read("tilemap", (SOURCE / "title/TITLE_LOGO.BIN").read_bytes(),
                                                       entries[-2]["params"])] == [(320, 256)]
    assert len(texture_formats.read("tilemap", (SOURCE / "title/TITLE_MENUS.BIN").read_bytes(), entries[-1]["params"])) == 8
    entry = entries[2]                                   # S011, the prologue
    data = (SOURCE / entry["path"]).read_bytes()
    image = texture_formats.read("tiles", data, entry["params"])[0].image.copy()
    image.paste((255, 255, 255, 255), (8, 0, 40, 2))
    edited = texture_formats.write("tiles", data, {0: image}, entry["params"])
    assert texture_formats.read("tiles", edited, entry["params"])[0].image.crop((8, 0, 40, 2)).getcolors() == \
        [(64, (255, 255, 255, 255))]


@needs_data
def test_the_dialogue_and_logo_compression_round_trips_and_packs_no_larger():
    zt = _zt()
    with zt.Disc(zt.WORKSPACE / "ISO" / "Dracula_X_Ultimate_v1.1.bin") as disc:
        entries = disc.entries()
        for name in zt.dialogue_files(entries, disc):
            packed_original = disc.read(entries[name].lba, entries[name].size)
            pictures, end = zt.kos_decompress(packed_original)
            assert end == len(packed_original)
            assert pictures == (SOURCE / "dialogue" / (name[:-4] + ".BIN")).read_bytes()
            if name in ("S011.CHR", "EVENT020.CHR", "SWATA.CHR"):      # packing all 20 takes 30 s
                packed = zt.kos_compress(pictures)
                assert zt.kos_decompress(packed)[0] == pictures and len(packed) <= len(packed_original), name


@needs_data
def test_the_title_chunks_unpack_and_an_edited_logo_and_menu_bank_pack_into_a_table_the_game_can_follow():
    zt = _zt()
    with zt.Disc(zt.WORKSPACE / "ISO" / "Dracula_X_Ultimate_v1.1.bin") as disc:
        entries = disc.entries()
        title = disc.read(entries["TITLE.MAP"].lba, entries["TITLE.MAP"].size)
        prg = disc.read(entries["TITLE.PRG"].lba, entries["TITLE.PRG"].size)
    chunks = zt.title_chunks(prg, len(title))
    assert [s for _a, s, _n in chunks][:4] == [0x5000, 0x8383, 0x7F40, 0x897A] and len(chunks) == 20
    parts = zt.title_unpack(title, chunks)
    by = {start: streams for start, _size, streams, _end in parts}
    logo_map, logo_cells, menu_cells = by[zt.LOGO_MAP][0][0], by[zt.LOGO_CELLS][0][0], by[zt.MENU_CELLS][0][0]
    assert (SOURCE / "title" / "TITLE_LOGO.BIN").read_bytes() == logo_map + logo_cells
    assert (SOURCE / "title" / "TITLE_MENUS.BIN").read_bytes() == title[:zt.MENU_MAP] + menu_cells
    assert len(logo_cells) == 30464 and len(menu_cells) == 27584 and logo_map[:4] == b"\0\x28\0\x20"
    cells = bytearray(menu_cells)
    cells[5 * 32 + 3] ^= 0x77
    logo = bytearray(logo_cells) + bytes(64 * 3)                 # a changed cell, and the logo bank grown
    logo[100 * 64 + 7] ^= 0x33
    new_title, table = zt.title_pack(title, chunks, {zt.MENU_CELLS: bytes(cells), zt.LOGO_CELLS: bytes(logo)})
    new_prg = zt.patch_title_table(prg, chunks, table)
    again = zt.title_unpack(new_title, zt.title_chunks(new_prg, len(new_title)))
    assert len(again) == len(parts)
    for (start, size, streams, _end), (new_start, new_size, new_streams, _new_end) in zip(parts, again):
        assert (new_start, new_size) == table[start] and len(new_streams) == len(streams)
        if start in (zt.MENU_CELLS, zt.LOGO_CELLS):
            assert new_streams == [({zt.MENU_CELLS: bytes(cells), zt.LOGO_CELLS: bytes(logo)}[start], True)], hex(start)
        else:                                     # every other byte of the file only moves, by a multiple of 64
            new_end = _new_end if new_size is None else new_start + new_size
            assert new_title[new_start:new_end] == title[start:_end if size is None else start + size], hex(start)
            assert (new_start - start) % 64 == 0, hex(start)
    assert new_title[:zt.MENU_MAP] == title[:zt.MENU_MAP]
    assert zt.title_pack(title, chunks, {})[0] == title                  # nothing to pack: the file as it is
    changed = {i for i in range(0, len(prg), 4) if prg[i:i + 4] != new_prg[i:i + 4]}
    assert 0x73C0 in changed and changed <= {at + k for at, _s, _n in chunks for k in (0, 4)}   # table words only
    # a seeded stream copies from the bytes decoded before it and reads back through the same window
    seeded = zt.kos_compress(logo_cells[4096:8192], seed=logo_cells[:4096])
    assert len(seeded) < len(zt.kos_compress(logo_cells[4096:8192]))
    window = bytearray(logo_cells[:4096])
    assert zt._lz_stream(seeded, 0, None, window) == (len(seeded), True) and bytes(window) == logo_cells[:8192]


@needs_data
def test_an_empty_translation_changes_nothing_and_a_longer_string_moves_its_pool(tmp_path):
    zt = _zt()
    with zt.Disc(zt.WORKSPACE / "ISO" / "Dracula_X_Ultimate_v1.1.bin") as disc:
        entries = disc.entries()
        assert zt.changes(tmp_path, disc, entries) == {}
        title = disc.read(entries["TITLE.PRG"].lba, entries["TITLE.PRG"].size)
    edits = {0x1358: b"UA TEST: select the", 0x14DD: b"Delete it?"}
    new = zt.apply_text("TITLE.PRG", title, edits)
    assert len(new) == len(title)
    for s in zt.extract("TITLE.PRG", title):
        for at in s["ptrs"]:
            target = int.from_bytes(new[at:at + 4], "big") - 0x060A5000
            assert new[target:new.index(b"\0", target)] == edits.get(s["o"], s["raw"])
    with pytest.raises(zt.Fail):
        zt.apply_text("TITLE.PRG", title, {0x1358: b"x" * 400})
    mirrored, placed, runs = zt.mirror(title, new, b"head" + title + b"tail")
    assert placed == runs and mirrored == b"head" + new + b"tail"
