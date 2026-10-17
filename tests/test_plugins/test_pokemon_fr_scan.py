"""The C-text scanner of the Generation III facts: which source lines the image builds, and why a missing literal is missing."""
import json

from plugins.pokemon_fr import rom_text
from tools import pokemon_fr_c_texts as scan


def _reasons(text, variant="RUBY", revision=0):
    return scan.conditional_reasons(text, variant, revision)


SOURCE = "\n".join([
    "a",
    "#if DEBUG",
    "b",
    "#endif",
    "#if REVISION >= 1",
    "c",
    "#else",
    "d",
    "#endif",
    "#ifdef SAPPHIRE",
    "e",
    "#endif",
])


def test_debug_and_revision_branches_are_left_out_of_the_retail_image():
    assert _reasons(SOURCE) == ["", "debug", "debug", "", "revision", "revision", "", "", "", "other_language",
                                "other_language", ""]


def test_a_revision_one_image_builds_the_revision_branch():
    reasons = _reasons(SOURCE, revision=1)
    assert reasons[5] == ""           # c: REVISION >= 1 holds
    assert reasons[7] == "revision"   # d: the else branch of REVISION >= 1 is left out


def test_a_version_macro_selects_its_own_branch():
    assert _reasons(SOURCE, variant="SAPPHIRE")[10] == ""
    assert _reasons(SOURCE, variant="RUBY")[10] == "other_language"


def test_an_expression_with_a_size_suffix_is_read():
    text = "#if __STDC_VERSION__ < 202311L\nx\n#endif"
    assert _reasons(text) == ["", "", ""]     # an undefined name is 0, so 0 < 202311L holds and the block is built


def test_defined_selects_the_version_branch():
    text = "#if defined(FIRERED)\na\n#elif defined(LEAFGREEN)\nb\n#endif"
    assert _reasons(text, variant="FIRERED") == ["", "", "other_language", "other_language", ""]
    assert _reasons(text, variant="LEAFGREEN") == ["other_language", "other_language", "", "", ""]


def test_missing_literals_are_classed_by_their_cause():
    assert scan.missing_class("debug", "POS:") == "debug_build"
    assert scan.missing_class("revision", "A test line") == "other_revision"
    assert scan.missing_class("", "{COLOR WHITE}{HIGHLIGHT TRANSPARENT}      ") == "fill"
    assert scan.missing_class("", "CHERRY") == "missing"


def test_english_messages_are_text_and_graphics_bytes_are_not():
    assert scan.english_message("A test line.\\nAnother test line.")
    assert scan.english_message("SEND OUT")
    assert not scan.english_message("iAA:igA:YiC ")
    assert not scan.english_message("zjAURh\u00e9")


def test_item_descriptions_are_c_strings_named_by_their_item(tmp_path):
    (tmp_path / "src" / "data").mkdir(parents=True)
    (tmp_path / scan.ITEMS_JSON).write_text(json.dumps({"items": [
        {"itemId": "ITEM_TM01", "description_english": 'A "hit".\\nfoe.'}]}), encoding="utf-8")
    assert scan.item_descriptions(tmp_path) == [
        'static const u8 gItemDescription_ITEM_TM01[] = _("A \\"hit\\".\\nfoe.");']


def test_a_message_in_code_data_is_a_unit_and_graphics_data_is_not():
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / "charmap_gen3.json")
    text = charmap.encode("A test line.")
    rom = bytearray(b"\xff" * 0x200)
    rom[0x10:0x10 + len(text)] = text
    covered = bytearray(len(rom))
    sections = [(scan.BASE, 0x100, "src/item.o"), (scan.BASE + 0x100, 0x100, "graphics/x.o")]
    units, counts = scan.rom_messages(bytes(rom), charmap, covered, sections, {})
    assert units == [["rom_10", 0x10, len(text)]]
    assert counts["skipped_object"] == 1
    assert covered[0x10] == 1


def test_a_message_under_a_picture_symbol_is_not_a_unit():
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / "charmap_gen3.json")
    text = charmap.encode("A test line.")
    rom = bytearray(b"\xff" * 0x200)
    rom[0x10:0x10 + len(text)] = text
    sections = [(scan.BASE, 0x100, "src/graphics.o")]
    units, counts = scan.rom_messages(bytes(rom), charmap, bytearray(len(rom)), sections,
                                      {"gMonIcon_Espeon": scan.BASE})
    assert units == []
    assert counts["data_symbol"] == 1
