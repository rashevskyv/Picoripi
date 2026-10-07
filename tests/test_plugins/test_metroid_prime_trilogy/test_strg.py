"""STRG tables of the three versions and the tag forms, on tables built here (no game data needed)."""
import struct

import pytest

from plugins.metroid_prime_trilogy.rules import GameRules
from plugins.metroid_prime_trilogy.strg import MAGIC, Strg
from plugins.metroid_prime_trilogy.tags import from_editor, to_editor

LANGS = ["ENGL", "FREN"]
TEXTS = {"ENGL": ["&push;&main-color=#FF0000;Hello&pop;", "World"], "FREN": ["Bonjour", "Monde"]}


def _utf16_block(texts):
    data, offsets = bytearray(), []
    for text in texts:
        offsets.append(4 * len(texts) + len(data))
        data += text.encode("utf-16-be") + b"\0\0"
    return struct.pack(f">{len(texts)}I", *offsets) + data


def _table(version: int) -> bytes:
    head = struct.pack(">IIII", MAGIC, version, len(LANGS), 2)
    names = struct.pack(">II", 1, 8 + 4) + struct.pack(">II", 8, 0) + b"one\0"
    if version == 3:
        data, tables = bytearray(), []
        for lang in LANGS:
            offsets = []
            for text in TEXTS[lang]:
                offsets.append(len(data))
                raw = text.encode() + b"\0"
                data += struct.pack(">I", len(raw)) + raw
            tables.append(offsets)
        body = b"".join(struct.pack(">I2I", 0, *t) for t in tables)
        return head + names + b"".join(lang.encode() for lang in LANGS) + body + data
    blocks = [_utf16_block(TEXTS[lang]) for lang in LANGS]
    if version == 0:
        blocks = [struct.pack(">I", len(b)) + b for b in blocks]
        table = b"".join(lang.encode() + struct.pack(">I", sum(map(len, blocks[:i]))) for i, lang in enumerate(LANGS))
        return head + table + b"".join(blocks)
    table = b"".join(lang.encode() + struct.pack(">II", sum(map(len, blocks[:i])), len(blocks[i]))
                     for i, lang in enumerate(LANGS))
    return head + table + names + b"".join(blocks)


@pytest.mark.parametrize("version", [0, 1, 3])
def test_reads_every_language_and_builds_shared_text(version):
    raw = _table(version)
    table = Strg(raw)
    assert table.strings == TEXTS
    assert table.build(table.english) == raw
    built = Strg(table.build(["Привіт", "World"]))
    assert built.strings == {"ENGL": ["Привіт", "World"], "FREN": ["Привіт", "World"]}
    if version:
        assert built.names == table.names


def test_rules_show_tags_in_curly_braces_and_save_them_back():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(_table(3))
    assert blocks[0][0] == "{push}{main-color=#FF0000}Hello{pop}"
    blocks[0][0] = "{push}{main-color=#FF0000}Привіт{pop}"
    assert Strg(rules.save_data_to_json_obj(blocks, names)).strings["FREN"][0] == "&push;&main-color=#FF0000;Привіт&pop;"


def test_tag_forms_convert_both_ways():
    text = "&just=center;PRESS &image=0x1BBAADC0DFC5D6F4; TO START\n[ On ]"
    assert to_editor(text) == "{just=center}PRESS {image=0x1BBAADC0DFC5D6F4} TO START\n[ On ]"
    assert from_editor(to_editor(text)) == text
