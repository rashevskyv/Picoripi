"""Pokémon generation IV ROM mode (``.msg`` banks): codec round trips, plugin load and save, and the real ROM banks
of the workspace when they are unpacked (the real-data test skips without them)."""
import romhacking_root
import struct
from pathlib import Path

import pytest

from plugins.common import gen4msg
from plugins.pokemon_gen4.rules import GameRules

CHARMAP = Path(__file__).resolve().parents[3] / "plugins" / "pokemon_gen4" / "charmaps" / "charmap_dp_hgss.txt"
WORKSPACE = romhacking_root.under('Pokemon\\Diamond and Pearl\\source\\text\\msgdata+msg.narc')


def _codec() -> gen4msg.Codec:
    return gen4msg.Codec(str(CHARMAP))


def _bank_bytes(codec: gen4msg.Codec, texts: list, key: int = 0x1234) -> bytes:
    lines = [codec.encode_line(t) for t in texts]
    return gen4msg.encode_bank(gen4msg.Bank(key=key, lines=lines))


def test_space_and_tags_round_trip():
    codec = _codec()
    text = "The wild {STRVAR_01 1,0} used Pound!"
    units = codec.encode_line(text)
    assert codec.decode_line(units) == text


def test_bank_bytes_round_trip_exact():
    codec = _codec()
    raw = _bank_bytes(codec, ["Hello there!", "{WAIT}", "UA TEST"])
    bank = gen4msg.decode_bank(raw)
    assert gen4msg.encode_bank(bank) == raw
    assert gen4msg.decode_all(bank, codec) == ["Hello there!", "{WAIT}", "UA TEST"]


def test_bad_bank_is_refused():
    with pytest.raises(gen4msg.BankError):
        gen4msg.decode_bank(struct.pack("<HH", 2, 5) + b"\x00" * 4)


def test_plugin_unchanged_save_is_identical_and_edit_reloads():
    codec = _codec()
    raw = _bank_bytes(codec, ["Hello there!", "My name is Rowan."])
    rules = GameRules(None)
    [lines], _ = rules.load_data_from_json_obj(raw)
    assert lines == ["Hello there!", "My name is Rowan."]
    assert rules.save_data_to_json_obj([lines]) == raw
    edited = ["Hello there!", "UA TEST"]
    out = rules.save_data_to_json_obj([edited])
    assert out != raw
    fresh = GameRules(None)
    [reloaded], _ = fresh.load_data_from_json_obj(out)
    assert reloaded == edited


def test_real_bank_of_the_workspace_round_trips():
    bank_file = WORKSPACE / "0341.msg"
    if not bank_file.is_file():
        pytest.skip("the Diamond and Pearl workspace is not unpacked here")
    raw = bank_file.read_bytes()
    assert gen4msg.encode_bank(gen4msg.decode_bank(raw)) == raw
