"""Donkey Kong Country: Tropical Freeze big-endian RFRM packages (``core.containers.dktf_pak``)."""
import struct

import pytest

from core.containers import dktf_pak as dp

GUID = bytes(range(16))


def _chunk(kind: bytes, body: bytes, unk: int = 1) -> bytes:
    return dp.CHUNK.pack(kind, len(body), unk, 0) + body


def _msbt_form(text: bytes) -> bytes:
    """An MSBT asset with one ``USEN`` child (a chunk), as in the game's package."""
    return dp.build_form(b"MSBT", [dp.Child("USEN", dp.CHUNK.pack(b"USEN", 0, 0, 0), text)], 5, 5)


def _package(form: bytes) -> bytes:
    """A one-asset package: PACK form, TOCC with an ADIR chunk, then the asset."""
    adir = _chunk(b"ADIR", struct.pack(">I", 1) + struct.pack(">4s16sQQ", b"MSBT", GUID, 0, len(form)))
    asset_at = dp.FORM.size * 2 + len(adir)
    adir = _chunk(b"ADIR", struct.pack(">I", 1) + struct.pack(">4s16sQQ", b"MSBT", GUID, asset_at, len(form)))
    toc = dp.FORM.pack(b"RFRM", len(adir), 0, b"TOCC", 1, 1) + adir
    head = dp.FORM.pack(b"RFRM", len(toc) + len(form), 0, b"PACK", 1, 1)
    return head + toc + form


def test_reads_directory_and_children():
    form = _msbt_form(b"hello")
    pak = dp.Pak(_package(form))
    assert [a.type for a in pak.assets] == ["MSBT"]
    assert pak.assets[0].guid == GUID
    (child,) = pak.children(pak.assets[0])
    assert child.tag == "USEN" and child.body == b"hello"


def test_unchanged_package_is_byte_identical():
    data = _package(_msbt_form(b"hello"))
    pak = dp.Pak(data)
    assert dp.write(pak, {}) == data
    assert dp.build_form(b"MSBT", pak.children(pak.assets[0]), 5, 5) == pak.raw(pak.assets[0])


def test_replaced_asset_reads_back_and_rest_is_kept():
    data = _package(_msbt_form(b"hello"))
    pak = dp.Pak(data)
    new_form = _msbt_form(b"a longer Ukrainian line")
    out = dp.write(pak, {GUID: new_form})
    again = dp.Pak(out)
    assert again.children(again.assets[0])[0].body == b"a longer Ukrainian line"
    old = pak.assets[0]
    assert out[old.offset:old.offset + old.size] == data[old.offset:old.offset + old.size]   # old copy stays
    assert struct.unpack_from(">Q", out, 4)[0] == len(out) - dp.FORM.size


def test_unknown_guid_is_refused():
    pak = dp.Pak(_package(_msbt_form(b"x")))
    with pytest.raises(KeyError):
        dp.write(pak, {bytes(16): _msbt_form(b"y")})


def test_other_packages_are_refused():
    data = bytearray(_package(_msbt_form(b"x")))
    data[20:24] = b"MSBT"          # a form of another kind is not a PACK
    with pytest.raises(ValueError):
        dp.Pak(bytes(data))
