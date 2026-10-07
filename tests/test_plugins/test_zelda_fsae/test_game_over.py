"""GAME OVER of Four Swords Anniversary Edition: the word, letter table and places in the ARM9."""
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.testing import load_rules
from plugins.zelda_fsae import game_over

FSAE = Path(r"E:\Emulators\RomHacking\Zelda\Four Swords Anniversary")
LETTERS = "GAMEOVR"


def _arm9() -> bytes:
    data = bytearray(game_over.PLACES + game_over.PLACE_STRIDE * 10 + 0x100)
    for slot in range(10):
        at = game_over.WORDS + game_over.WORD_SIZE * slot
        data[at:at + 16] = "GAMEOVER".encode("utf-16-le")
        struct.pack_into("<8I", data, game_over.PLACES + game_over.PLACE_STRIDE * slot, 20, 47, 73, 103, 135, 161, 187, 211)
    for index, char in enumerate(LETTERS):
        struct.pack_into("<3I", data, game_over.LETTERS + 12 * index, ord(char), 16 * index, 0x80000000)
    return bytes(data)


def test_read_and_unchanged_write():
    data = _arm9()
    texts = game_over.read(data)
    assert texts[0] == "GAMEOVER"
    assert texts[1].splitlines() == [f"{c} {16 * i} 32x32" for i, c in enumerate(LETTERS)]
    assert texts[2] == "20 47 73 103 135 161 187 211"
    assert game_over.write(data, texts) == data


def test_a_new_letter_in_the_free_slot_and_a_narrow_one():
    data = _arm9()
    word, letters, _places = game_over.read(data)
    letters += "\nЖ 112 32x32\nІ 120 8x32"
    out = game_over.write(data, ["ЖІGAME", letters, "0 30 40 70 100 130"])
    assert game_over.read(out) == ["ЖІGAME", letters, "0 30 40 70 100 130"]
    entry = struct.unpack_from("<3I", out, game_over.LETTERS + 12 * 8)
    assert entry == (ord("І"), 120, 0x40008000)                 # tall shape, size 1: 8x32
    untouched = game_over.WORDS + game_over.WORD_SIZE      # the other language slots stay
    assert out[untouched:untouched + 0x20] == data[untouched:untouched + 0x20]


@pytest.mark.parametrize("texts, message", [
    (["GAMEOVERX", None, "1 2 3 4 5 6 7 8 9"], "without a sprite"),
    (["GAMEOVER", None, "1 2 3"], "one x"),
    (["GAMEOVER", "G 120 32x32", "1 2 3 4 5 6 7 8"], "does not fit"),
    (["GAMEOVER", "G 0 24x32", "1 2 3 4 5 6 7 8"], "8, 16, 32 or 64"),
])
def test_wrong_texts_are_refused_with_a_reason(texts, message):
    data = _arm9()
    current = game_over.read(data)
    texts = [current[i] if t is None else t for i, t in enumerate(texts)]
    with pytest.raises(game_over.FormatError, match=message):
        game_over.write(data, texts)


def test_plugin_block_load_and_save():
    data = _arm9()
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(data)
    assert names == {"0": "GAME OVER (ARM9)"} and blocks[0][0] == "GAMEOVER"
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][2] = "21 47 73 103 135 161 187 211"
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([data])))
    saved = rules.save_data_to_json_obj(blocks, names)
    assert game_over.read(saved)[2].startswith("21 ")


def test_real_arm9():
    path = FSAE / "source" / "main.arm9"
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    data = path.read_bytes()
    texts = game_over.read(data)
    assert texts[0] == "GAMEOVER" and texts[2] == "20 47 73 103 135 161 187 211"
    assert texts[1].splitlines()[0] == "G 0 32x32" and len(texts[1].splitlines()) == 7
    assert game_over.write(data, texts) == data
