"""FARC version 5 packs (``core.containers.farc``): the member list, a replace that keeps the other members, a member
that grows, and the placeholder names. A small synthetic pack stands in for the game's message pack."""
import struct

import pytest

from core.containers import farc


def _pack(blobs):
    """A FARC v5 pack of ``{name: bytes}``: the header at 0x20, the table at 0x80, the members padded to 16 bytes."""
    names = sorted(blobs, key=farc.name_hash)
    table = b"".join(struct.pack("<III", farc.name_hash(n), 0, 0) for n in names)
    fat = b"SIR0" + struct.pack("<III", 0x10 + len(table), 0, 0) + table + struct.pack("<III", 0x10, len(names), 1)
    fat += bytes(-len(fat) % 16)
    head = bytearray(b"FARC" + bytes(0x1C) + struct.pack("<5I", 5, 0x80, len(fat), 0, 0) + bytes(0x80 - 0x34)) + fat
    head += bytes(-len(head) % 0x80)
    struct.pack_into("<I", head, 0x2C, len(head))
    body = bytearray()
    for index, name in enumerate(names):
        struct.pack_into("<II", head, 0x80 + 0x10 + index * 12 + 4, len(body), len(blobs[name]))
        body += blobs[name] + bytes(-len(blobs[name]) % 16)
    struct.pack_into("<I", head, 0x30, len(head) + len(body) - 0x80 - len(fat))
    return bytes(head) + bytes(body)


def test_members_list_every_name_with_its_bytes():
    data = _pack({"a.bin": bytes(16), "b.bin": b"\1" * 32})
    got = farc.member_bytes(data)
    assert got == {farc.name_hash("a.bin"): bytes(16), farc.name_hash("b.bin"): b"\1" * 32}


def test_replace_with_nothing_changed_gives_the_same_bytes():
    data = _pack({"a.bin": bytes(16), "b.bin": b"\1" * 32})
    assert farc.replace(data, {}) == data


def test_a_member_that_grows_keeps_the_others():
    data = _pack({"a.bin": bytes(16), "b.bin": b"\1" * 32})
    grown = farc.replace(data, {farc.name_hash("a.bin"): b"\2" * 48})
    got = farc.member_bytes(grown)
    assert got[farc.name_hash("a.bin")] == b"\2" * 48
    assert got[farc.name_hash("b.bin")] == b"\1" * 32


def test_a_hash_the_pack_does_not_hold_is_refused():
    data = _pack({"a.bin": bytes(16)})
    with pytest.raises(farc.FarcError):
        farc.replace(data, {farc.name_hash("zz.bin"): b"\3"})


def test_not_a_farc_pack_is_refused():
    with pytest.raises(farc.FarcError):
        farc.members(b"SIR0" + bytes(0x40))


def test_placeholder_name_is_its_hash():
    assert farc.name_hash("#0104E3C3.bin") == 0x0104E3C3
