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
    assert len(entries) == 21
    for entry in entries:
        data = (SOURCE / entry["path"]).read_bytes()
        image = texture_formats.read(entry["format"], data, entry["params"])[0].image
        assert texture_formats.write(entry["format"], data, {0: image}, entry["params"]) == data, entry["label"]
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
        title = disc.read(entries["TITLE.MAP"].lba, entries["TITLE.MAP"].size)
        logo, end = zt.kos_decompress(title, zt.LOGO[1])
        assert len(zt.kos_compress(logo)) <= end - zt.LOGO[1]


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
