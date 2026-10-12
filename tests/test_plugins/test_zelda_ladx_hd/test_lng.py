"""Unit tests for the Link's Awakening DX HD language file parser (no Qt)."""
import os
from pathlib import Path

import pytest

from plugins.zelda_ladx_hd import lng
from plugins.zelda_ladx_hd.xnb_font import parse_sprite_font


SYNTHETIC = (
    "// header comment\r\n"
    "main_menu_new_game New Game\r\n"
    "\r\n"
    "empty_value \r\n"
    "double  spaces   kept here\r\n"
    "no_space_line\r\n"
    "dialog_1 Hello [NAME],\\nwelcome.\\fBye\r\n"
    "last_line Ends without newline"
)


def test_round_trip_is_byte_exact_for_synthetic_text():
    raw = SYNTHETIC.encode("utf-8")
    parsed = lng.parse(raw)
    assert lng.serialize_bytes(parsed) == raw


def test_bom_and_lf_only_round_trip():
    raw = b"\xef\xbb\xbfa 1\nb 2\n"
    parsed = lng.parse(raw)
    assert parsed.bom is True
    assert [e.key for e in parsed.entries()] == ["a", "b"]
    assert lng.serialize_bytes(parsed) == raw


def test_comments_blank_and_skipped_lines_are_not_entries():
    parsed = lng.parse(SYNTHETIC.encode("utf-8"))
    kinds = [line.kind for line in parsed.lines]
    assert kinds[0] == lng.KIND_COMMENT
    assert lng.KIND_BLANK in kinds
    assert lng.KIND_OTHER in kinds
    keys = [e.key for e in parsed.entries()]
    assert keys == ["main_menu_new_game", "empty_value", "double", "dialog_1", "last_line"]


def test_value_keeps_repeated_spaces_and_empty_value():
    parsed = lng.parse(SYNTHETIC.encode("utf-8"))
    by_key = {e.key: e.value for e in parsed.entries()}
    assert by_key["empty_value"] == ""
    assert by_key["double"] == " spaces   kept here"


def test_values_are_replaced_in_entry_order():
    parsed = lng.parse(b"a 1\r\n// c\r\nb 2\r\n")
    out = lng.serialize(parsed, ["one", "two"])
    assert out == "a one\r\n// c\r\nb two\r\n"


def test_wrong_number_of_values_is_refused():
    parsed = lng.parse(b"a 1\r\nb 2\r\n")
    with pytest.raises(ValueError):
        lng.serialize(parsed, ["only one"])


def test_lone_carriage_return_is_refused():
    with pytest.raises(ValueError):
        lng.parse(b"a one\rtwo\r\n")


def test_duplicate_keys_across_two_files_are_found():
    eng = lng.parse(b"a 1\r\nb 2\r\n")
    dialog = lng.parse(b"b 3\r\nc 4\r\n")
    assert lng.duplicate_keys([eng, dialog]) == ["b"]
    assert lng.duplicate_keys([eng]) == []


def test_tags_and_escapes():
    value = "Hi [NAME], [itemShopPrice]!\\n\\f ±"
    assert lng.tags(value) == ["[NAME]", "[itemShopPrice]"]
    assert lng.escapes(value) == ["\\n", "\\f"]


def test_missing_characters_reported_once_in_order():
    assert lng.missing_characters("Жж abc Ж", set("abc ")) == ["Ж", "ж"]


def test_xnb_rejects_compressed_and_wrong_files():
    with pytest.raises(ValueError):
        parse_sprite_font(b"not xnb at all")
    compressed = bytearray(b"XNBw\x05\x80" + b"\x00" * 20)
    with pytest.raises(ValueError):
        parse_sprite_font(bytes(compressed))


def _real_root():
    root = os.environ.get("PICORIPI_ROMHACKING", "").strip()
    if not root:
        return None
    folder = Path(root) / "_new" / "Links Awakening DX HD"
    return folder if folder.is_dir() else None


@pytest.fixture
def real_folder():
    folder = _real_root()
    if folder is None:
        pytest.skip("PICORIPI_ROMHACKING is not set or the Links Awakening DX HD folder is missing")
    return folder


def test_real_language_files_round_trip_byte_exact(real_folder):
    for name in ("eng.lng", "dialog_eng.lng"):
        raw = (real_folder / "Data" / "Languages" / name).read_bytes()
        parsed = lng.parse(raw)
        assert lng.serialize_bytes(parsed) == raw, name


def test_real_english_keys_are_unique_across_both_files(real_folder):
    eng = lng.parse((real_folder / "Data" / "Languages" / "eng.lng").read_bytes())
    dialog = lng.parse((real_folder / "Data" / "Languages" / "dialog_eng.lng").read_bytes())
    assert lng.duplicate_keys([eng, dialog]) == []


def test_real_sprite_font_maps_latin_and_has_no_cyrillic(real_folder):
    font = parse_sprite_font((real_folder / "Content" / "Fonts" / "newHeaderFont.xnb").read_bytes())
    assert font.exact is True
    assert "A" in font.characters and "z" in font.characters
    assert not any("Ѐ" <= ch <= "ӿ" for ch in font.characters)
    assert font.default_character is None
