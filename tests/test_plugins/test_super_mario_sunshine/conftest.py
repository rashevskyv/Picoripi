"""Synthetic executable text: the plugin keeps only digests of the retail strings, so tests swap in their own."""
import hashlib

import pytest

from plugins.super_mario_sunshine import dol_text

from .test_dol_text import synthetic_text


@pytest.fixture
def synthetic_strings(monkeypatch):
    """``dol_text.STRINGS`` with the retail offsets and rooms and the digests of ``synthetic_text``."""
    table = tuple((ident, offset, room, hashlib.sha256(synthetic_text(ident, room) + b"\0").hexdigest())
                  for ident, offset, room, _digest in dol_text.STRINGS)
    monkeypatch.setattr(dol_text, "STRINGS", table)
    return table
