"""The translation import's view of a STRG file: editor texts, record ids, and a build that keeps the bytes."""
import pytest

from plugins.metroid_prime_trilogy.rules import GameRules
from plugins.metroid_prime_trilogy.strg import Strg

from .test_strg import _table


@pytest.mark.parametrize("version", [0, 1, 3])
def test_unchanged_texts_build_the_original_bytes(version):
    raw = _table(version)
    table = GameRules().parse_table(raw)
    assert table.build(table.texts()) == raw


def test_texts_are_editor_forms_and_ids_are_record_numbers():
    table = GameRules().parse_table(_table(3))
    assert table.texts() == ["{push}{main-color=#FF0000}Hello{pop}", "World"]
    assert table.ids() == ["1", "2"]


def test_a_translation_keeps_cyrillic_and_its_tags():
    table = GameRules().parse_table(_table(1))
    raw = table.build(["{push}{main-color=#FF0000}Привіт{pop}", "Світ"])
    assert Strg(raw).english == ["&push;&main-color=#FF0000;Привіт&pop;", "Світ"]
    assert GameRules().parse_table(raw).texts() == ["{push}{main-color=#FF0000}Привіт{pop}", "Світ"]


@pytest.mark.parametrize("raw", [b"", b"not a string table at all"])
def test_bytes_that_are_not_a_string_table_are_not_a_table(raw):
    assert GameRules().parse_table(raw) is None
