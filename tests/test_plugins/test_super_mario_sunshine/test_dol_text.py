"""The executable's strings: read as a document, written into their rooms, refused when they do not fit.

The plugin keeps only digests of the retail text; the ``synthetic_strings`` fixture (conftest) swaps in the digests of
``synthetic_text``, so no game text is in the tests either."""
import json
import struct

import pytest

from plugins.super_mario_sunshine import dol_patch
from plugins.super_mario_sunshine.dol_text import STRINGS, DolText, apply_document, document_of

pytestmark = pytest.mark.usefixtures("synthetic_strings")


def synthetic_text(ident: str, room: int) -> bytes:
    """Bytes that fill ``room`` minus the NUL; the first error line starts with 0x99 (the trademark sign in cp1252)."""
    body = (b"\x99" if ident == "disc_error_1" else b"") + (ident.encode("ascii") + b"\n") * room
    return body[:room - 1]


def retail_dol(size: int = 0x3F0000) -> bytes:
    """A synthetic executable: a DOL header and the synthetic strings at the retail offsets. No game data."""
    data = bytearray(size)
    data[0:4] = b"\x00\x00\x01\x00"
    struct.pack_into(">I", data, 0xE0, 0x80003100)
    for ident, offset, room, _digest in STRINGS:
        data[offset:offset + room - 1] = synthetic_text(ident, room)
    return bytes(data)


def edited(dol: bytes, **texts: str) -> bytes:
    """``dol`` with the given strings replaced in the document (ids as keywords)."""
    document = json.loads(document_of(dol).decode("utf-8"))
    for row in document["strings"]:
        if row["id"] in texts:
            row["text"] = texts[row["id"]]
    return json.dumps(document).encode("utf-8")


def test_the_retail_executable_is_recognised_and_another_is_not():
    dol = retail_dol()
    assert DolText.can_handle(dol)
    first = STRINGS[0][1]
    assert not DolText.can_handle(dol[:first] + b"x" + dol[first + 1:])
    assert not DolText.can_handle(b"")


def test_the_document_holds_each_string_in_order():
    rows = json.loads(document_of(retail_dol()).decode("utf-8"))["strings"]
    assert [row["id"] for row in rows] == [ident for ident, _o, _r, _e in STRINGS]
    assert [row["text"] for row in rows] == [synthetic_text(i, r).decode("cp1252") for i, _o, r, _e in STRINGS]
    assert [row["room"] for row in rows] == [room for _i, _o, room, _e in STRINGS]
    assert rows[5]["text"].startswith("™")   # byte 0x99 of the executable is ™ in cp1252


def test_the_plugin_keeps_digests_not_text():
    assert all(isinstance(digest, str) and len(digest) == 64 for _i, _o, _r, digest in STRINGS)


def test_an_executable_whose_string_differs_is_refused():
    dol = bytearray(retail_dol())
    dol[STRINGS[1][1]:STRINGS[1][1] + 3] = b"Nei"
    with pytest.raises(ValueError, match="not the expected"):
        DolText(bytes(dol))


def test_a_shorter_text_is_padded_with_zeros_inside_its_room_only():
    dol = retail_dol()
    patched = apply_document(dol, edited(dol, yes="OK"))
    yes_at = next(offset for ident, offset, _r, _e in STRINGS if ident == "yes")
    assert len(patched) == len(dol)
    assert patched[yes_at:yes_at + 4] == b"OK\0\0"
    rooms = [(offset, offset + room) for _i, offset, room, _e in STRINGS]
    changed = {i for i in range(len(dol)) if dol[i] != patched[i]}
    assert changed <= {i for start, end in rooms if start == yes_at for i in range(start, end)}


def test_a_text_longer_than_its_room_is_refused():
    dol = retail_dol()
    with pytest.raises(ValueError, match="room"):
        apply_document(dol, edited(dol, yes="Yes!!"))


def test_a_character_that_is_not_one_byte_is_refused():
    dol = retail_dol()
    with pytest.raises(ValueError, match="one byte"):
        apply_document(dol, edited(dol, yes="Так"))


def test_an_unknown_string_id_is_refused():
    dol = retail_dol()
    document = json.loads(document_of(dol).decode("utf-8"))
    document["strings"].append({"id": "new_string", "text": "x", "room": 2})
    with pytest.raises(ValueError, match="unknown string"):
        apply_document(dol, json.dumps(document).encode("utf-8"))


def test_the_speech_fix_words_are_outside_every_string_room():
    rooms = [(offset, offset + room) for _i, offset, room, _e in STRINGS]
    for at, _retail, _patched, _site in dol_patch.PATCHES:
        assert not any(start <= at < end for start, end in rooms)


def test_document_of_a_non_retail_executable_is_refused():
    with pytest.raises(ValueError):
        document_of(b"\x00" * 0x200)
