"""The four speech-balloon words of the retail executable: patched in place, reversible, refused when not retail."""
import struct

import pytest

from plugins.super_mario_sunshine import dol_patch


def _retail(size: int = 0x150480) -> bytearray:
    dol = bytearray(b"\x5a" * size)
    for at, retail, _patched, _site in dol_patch.PATCHES:
        struct.pack_into(">I", dol, at, retail)
    return dol


def test_apply_changes_only_the_four_words_and_keeps_the_size():
    dol = bytes(_retail())
    patched = dol_patch.apply(dol)
    assert len(patched) == len(dol)
    changed = {i for i in range(len(dol)) if dol[i] != patched[i]}
    expected = {at + k for at, _r, _p, _s in dol_patch.PATCHES for k in range(4)}
    assert changed <= expected
    for at, _retail_word, patched_word, _site in dol_patch.PATCHES:
        assert struct.unpack_from(">I", patched, at)[0] == patched_word


def test_revert_puts_the_retail_bytes_back():
    dol = bytes(_retail())
    assert dol_patch.revert(dol_patch.apply(dol)) == dol


def test_a_site_that_is_not_retail_is_refused():
    dol = _retail()
    at = dol_patch.PATCHES[2][0]
    struct.pack_into(">I", dol, at, 0x12345678)
    with pytest.raises(ValueError, match="not the expected instruction"):
        dol_patch.apply(bytes(dol))


def test_a_short_executable_is_refused():
    with pytest.raises(ValueError, match="too short"):
        dol_patch.apply(bytes(0x1000))
