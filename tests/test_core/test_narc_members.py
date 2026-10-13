"""NARC members (core/containers/narc_members.py): table order, padding dropped, and refusal of other data."""
import pytest

from core.containers.narc_members import narc_members
from nds_rom import narc


def test_members_come_back_in_table_order_without_padding():
    members = [b"abc", b"", b"12345678", b"x"]
    assert narc_members(narc(members)) == members


def test_data_that_is_not_a_narc_raises():
    with pytest.raises(ValueError):
        narc_members(b"NOPE" + bytes(32))
