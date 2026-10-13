"""The English v1.0 DX ROM on this machine (skipped where it is missing). No ROM bytes are stored in the repo.

Set PICORIPI_LADX_DX_ROM to a .gbc file, or keep the default zip next to the Zelda workspace.
"""
import os
import zipfile
from pathlib import Path

import pytest

from plugins.zelda_ladx import rom, text

DEFAULT_ZIP = Path(
    r"reference_roms"
    r"\Legend of Zelda, The - Link's Awakening DX (USA, Europe) (SGB Enhanced) (GB Compatible).zip"
)


def _load():
    env = os.environ.get("PICORIPI_LADX_DX_ROM")
    if env and Path(env).is_file():
        return Path(env).read_bytes()
    if DEFAULT_ZIP.is_file():
        with zipfile.ZipFile(DEFAULT_ZIP) as archive:
            return archive.read(archive.namelist()[0])
    pytest.skip("the English DX ROM is not on this machine")


def test_real_rom_is_identified():
    rom.identify(_load())


def test_every_dialog_rewrites_unchanged():
    raw = _load()
    refs = rom.read_dialog_refs(raw)
    assert len(refs) == rom.DIALOG_COUNT
    out = bytearray(raw)
    for ref in refs:
        run = raw[ref.rom : ref.rom + text.span_length(raw, ref.rom)]
        text.write_text(out, ref, text.to_markup(run))
    assert bytes(out) == raw


def test_no_dialog_uses_an_unnamed_code():
    raw = _load()
    for ref in rom.read_dialog_refs(raw):
        seg = raw[ref.rom : ref.rom + text.span_length(raw, ref.rom)]
        assert "{" not in text.decode_bytes(seg)


def test_first_dialog_reads_as_english():
    raw = _load()
    assert text.read_text(raw, rom.read_dialog_refs(raw)[0]).startswith("Whoa, boy! Where")
