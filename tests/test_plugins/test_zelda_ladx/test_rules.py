"""The DX plugin's load and save on the real English v1.0 ROM (skipped where the ROM is missing)."""
from collections import Counter

import pytest

from plugins.zelda_ladx import rom, text
from plugins.zelda_ladx.rules import GameRules

from .test_real_rom import _load


class _Context:
    """Stands in for core.formats.SaveContext: existing versions, newest first."""

    def __init__(self, *versions: bytes):
        self._versions = list(versions)

    def existing_versions(self):
        return iter(self._versions)


def _rules_and_data():
    raw = _load()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    return raw, rules, blocks, names


def _save(rules, blocks, *versions):
    rules.prepare_save_context(_Context(*versions))
    return rules.save_data_to_json_obj(blocks, {})


def test_blocks_hold_every_dialog():
    _raw, _rules, blocks, names = _rules_and_data()
    assert [len(block) for block in blocks] == [256, 256, 176]
    assert set(names) == {"0", "1", "2"}


def test_unchanged_save_gives_the_source_bytes():
    raw, rules, blocks, _names = _rules_and_data()
    assert _save(rules, blocks, raw) == raw


def test_edited_line_is_written_and_checksums_stay_valid():
    raw, rules, blocks, _names = _rules_and_data()
    blocks[0][0] = blocks[0][0].replace("Whoa, boy!", "Hi, boy!", 1)
    out = _save(rules, blocks, raw)
    assert out != raw
    assert rom.header_checksum(out) == out[0x14D]
    assert rom.global_checksum(out) == (out[0x14E] << 8) | out[0x14F]
    reread = GameRules()
    reread_blocks, _ = reread.load_data_from_json_obj(out)
    assert reread_blocks[0][0].startswith("Hi, boy!")


def test_reverting_a_text_restores_the_source_bytes():
    raw, rules, blocks, _names = _rules_and_data()
    original = blocks[0][0]
    blocks[0][0] = original.replace("Whoa, boy!", "Hi, boy!", 1)
    edited = _save(rules, blocks, raw)
    blocks[0][0] = original
    assert _save(rules, blocks, edited, raw) == raw


def test_edit_keeps_a_newer_change_elsewhere_in_the_rom():
    raw, rules, blocks, _names = _rules_and_data()
    newer = bytearray(raw)
    newer[0x0100] ^= 0x01  # a byte outside every dialog, like a texture or font edit in the newest version
    blocks[0][0] = blocks[0][0].replace("Whoa, boy!", "Hi, boy!", 1)
    out = _save(rules, blocks, bytes(newer), raw)
    assert out[0x0100] == newer[0x0100]


def test_too_long_row_is_refused_with_the_dialog_name():
    raw, rules, blocks, _names = _rules_and_data()
    blocks[0][0] = "A" * 17 + "\nx"
    with pytest.raises(ValueError, match=r"Dialog000: row 1 has 17 characters"):
        _save(rules, blocks, raw)


def test_all_refusals_are_reported_together():
    raw, rules, blocks, _names = _rules_and_data()
    blocks[0][0] = "A" * 17
    blocks[0][1] = "B" * 17
    with pytest.raises(ValueError) as error:
        _save(rules, blocks, raw)
    assert "Dialog000" in str(error.value) and "Dialog001" in str(error.value)


def test_text_that_does_not_fit_its_place_is_refused():
    raw, rules, blocks, _names = _rules_and_data()
    first = next(ref for ref in rom.read_dialog_refs(raw) if ref.index == 0)
    room = text.span_length(raw, first.rom)
    too_many_rows = "\n".join(["Hi"] * (room // 16 + 2))
    blocks[0][0] = too_many_rows
    with pytest.raises(ValueError, match="do not fit"):
        _save(rules, blocks, raw)


def test_dialogs_sharing_one_place_must_match():
    raw, rules, blocks, _names = _rules_and_data()
    refs = rom.read_dialog_refs(raw)
    counts = Counter(ref.rom for ref in refs)
    place = next(ref.rom for ref in refs if counts[ref.rom] > 1)
    first, second = [ref for ref in refs if ref.rom == place][:2]
    block, position = divmod(first.index, 256)
    blocks[block][position] = "Hi"
    with pytest.raises(ValueError, match=f"{first.name}"):
        _save(rules, blocks, raw)
    assert second.index != first.index
