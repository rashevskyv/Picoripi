"""The *SK_ASC* decoder of Eternal Darkness, on two streams made by the workspace tools' encoder (the vectors below)."""
import struct

import pytest

from core.containers import edasc

# The vectors are the encoder's output for these inputs (a u32 size, then the payload), made once with the
# encoder of the workspace's tools; no game bytes.
TEXT = b"Eternal Darkness: Sanity's Requiem. Eternal Darkness, again. abcabcabc!"
SMALL = bytes.fromhex(
    "2a534b5f4153432a0006c9c41444acdbc3decc65ca00b046e38417839770ed1b123b52ad5f961f30689191e12ff1bdb6cb6c302e6d9ce175d5ce0000")
LONG = b"A" * 70000
BIG = bytes.fromhex("2a534b5f4153432a001bea09b69551c7f707fa27d800bb1050d87e0000")


def test_decodes_text_with_matches():
    assert edasc.decompress(SMALL) == struct.pack(">I", len(TEXT)) + TEXT


def test_decodes_a_long_match_run():
    assert edasc.decompress(BIG) == struct.pack(">I", len(LONG)) + LONG


def test_cancel_stops_after_the_output_threshold():
    assert edasc.decompress(BIG, is_cancelled=lambda: True) is None
    assert edasc.decompress(BIG, is_cancelled=lambda: False) == struct.pack(">I", len(LONG)) + LONG


def test_rejects_a_file_without_the_magic():
    with pytest.raises(ValueError, match="not an \\*SK_ASC\\* file"):
        edasc.decompress(b"RmTxt00\0" + SMALL[8:])
