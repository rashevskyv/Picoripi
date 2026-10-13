"""Sly Cooper level files (.brx): text spans are found, replaced and found again, byte for byte.

The synthetic tests need no game data. The real-data tests read the level files of the Sly data folder when it is
on this machine (environment variable SLY1_WORLDS, or the default torrent folder); they skip otherwise.
"""
import os
import struct
from pathlib import Path

import pytest

from plugins.sly_cooper.brx import TextSpan, is_text, replace_spans, scan_text

DEFAULT_WORLDS = Path("sly_cooper_switch/switch/ProjectCane/Worlds")
WORLDS = Path(os.environ.get("SLY1_WORLDS", str(DEFAULT_WORLDS)))
PARIS = WORLDS / "Paris" / "Paris.brx"
real = pytest.mark.skipif(not PARIS.exists(), reason="Sly data folder not on this machine")


def u16_text(text: bytes) -> bytes:
    return struct.pack("<H", len(text)) + text


def make_level(*texts: bytes) -> bytes:
    """Two header words, binary noise with pixel-like runs, then each text with its u16 length."""
    noise = bytes(range(0, 256, 7)) + b"zzzzzzzz" + b"GDGD" + b"from_hub"
    body = b"".join(u16_text(t) + b"\x00\x01\x02\xff" for t in texts)
    return b"\x17\x00\x1b\x00" + b"\x00\x00\x00\x00" + noise + body


SENTENCES = [b"Sly! I did a cross analysis of the metal.", b"Really?", b"Bummer. You can't open this vault."]


def test_scan_finds_sentences_and_skips_identifiers_and_noise():
    spans = scan_text(make_level(*SENTENCES, b"from_hub", b"GDGD"))
    assert [s.text.encode("ascii") for s in spans] == SENTENCES


def test_is_text_rules():
    assert is_text(b"Hunh?")
    assert is_text(b"Press &2O&. to enter the vault code.")
    assert not is_text(b"from_hub")
    assert not is_text(b"meet_JLo")
    assert not is_text(b"GDGD")
    assert not is_text(b"zzzzzzzz")
    assert not is_text(b"Ufff")
    assert not is_text(b"abc")  # shorter than four bytes


def test_replacing_nothing_returns_the_same_bytes():
    data = make_level(*SENTENCES)
    assert replace_spans(data, []) == data


def test_a_longer_and_a_shorter_text_are_found_again_in_order():
    data = make_level(*SENTENCES)
    spans = scan_text(data)
    edits = [(spans[0], "UA TEST: a much longer Ukrainian-style line for the length check."), (spans[1], "Okay.")]
    new = replace_spans(data, edits)
    assert (len(new) - len(data)) % 16 == 0  # the texture block after the text keeps its alignment
    assert [s.text.rstrip(" ") for s in scan_text(new)] == [edits[0][1], edits[1][1], SENTENCES[2].decode()]
    assert replace_spans(new, [(s, s.text) for s in scan_text(new)]) == new


def test_new_text_is_padded_so_the_length_change_is_a_multiple_of_16():
    data = make_level(SENTENCES[0])
    span = scan_text(data)[0]
    for new in ["Short.", "Twenty three letters here.", "A line a few characters longer than the original one, yes!"]:
        out = replace_spans(data, [(span, new)])
        assert (len(out) - len(data)) % 16 == 0
        assert scan_text(out)[0].text.rstrip(" ") == new


def test_an_edit_against_a_different_original_is_refused():
    data = make_level(*SENTENCES)
    stale = TextSpan(scan_text(data)[0].offset, "Something else.")
    with pytest.raises(ValueError):
        replace_spans(data, [(stale, "x Test line.")])


def test_non_ascii_and_control_bytes_are_refused():
    data = make_level(*SENTENCES)
    span = scan_text(data)[0]
    for bad in ["Привіт, Сліз.", "tab\there now", ""]:
        with pytest.raises(ValueError):
            replace_spans(data, [(span, bad)])


def test_text_after_an_edit_is_still_found():
    # Strings after an edit move, the bytes between them do not change.
    data = make_level(*SENTENCES) + b"\x99" * 40
    new = replace_spans(data, [(scan_text(data)[0], "Changed.")])
    assert new.endswith(b"\x99" * 40)
    assert scan_text(new)[1].text == SENTENCES[1].decode()


@real
def test_real_level_round_trips_byte_exact_with_no_edits():
    data = PARIS.read_bytes()
    assert replace_spans(data, []) == data


@real
def test_real_level_one_edit_changes_only_its_own_span():
    data = PARIS.read_bytes()
    spans = scan_text(data)
    assert len(spans) > 50
    target = spans[7]
    new = replace_spans(data, [(target, "UA TEST line, longer than the original one for the length check.")])
    assert (len(new) - len(data)) % 16 == 0
    found = scan_text(new)
    assert len(found) == len(spans)
    assert found[7].text.startswith("UA TEST line")
    assert [s.text for i, s in enumerate(found) if i != 7] == [s.text for i, s in enumerate(spans) if i != 7]
