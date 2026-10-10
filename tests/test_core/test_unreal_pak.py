"""Unreal ``.pak`` version 8 (core/unreal/pak.py): a written pak reads back; the real Bravely Default II pak (skipped
where the NSP or the extracted files are not on this machine) gives the same bytes for the English entries."""
from pathlib import Path

import pytest

from core.unreal import pak

NSP = Path(r"E:\Emulators\RomHacking\Bravely\Default II\Switch\ISO\Bravely Default II [01006DC010326000][v0].nsp")
EXTRACTED = Path(r"E:\Emulators\RomHacking\Bravely\Default II\Switch\source\pak")


def test_written_pak_reads_back(tmp_path):
    files = {"Game/Content/a.uasset": b"\xc1\x83\x2a\x9e" + b"x" * 300, "Game/Content/b.txt": b"hello"}
    target = tmp_path / "patch_P.pak"
    pak.write_pak(target, files)
    opened = pak.open_path(target)
    assert opened.version == 8
    assert sorted(opened.names()) == sorted(files)
    for entry in opened.entries:
        assert opened.data(entry) == files[entry.name]


def test_bad_footer_is_refused(tmp_path):
    target = tmp_path / "not_a_pak.bin"
    target.write_bytes(b"\x00" * 400)
    with pytest.raises(pak.PakError):
        pak.open_path(target)


def test_english_entries_match_the_extracted_files():
    if not NSP.is_file() or not EXTRACTED.is_dir():
        pytest.skip("Bravely Default II NSP or extracted files are not on this machine")
    scripts = Path(r"E:\Emulators\RomHacking\_shared\scripts")
    if not scripts.is_dir():
        pytest.skip("the RomHacking workspace scripts are not on this machine")
    import sys
    pytest.importorskip("cryptography")  # the workspace's NCA decryption needs it (the system Python has it)
    sys.path.insert(0, str(scripts))
    from zt import hwde_extract as hx  # the Switch NSP and key reader of the workspace scripts
    keys = Path(r"C:\Users\Administrator\.switch\prod.keys")
    if not keys.is_file():
        pytest.skip("prod.keys is not on this machine")
    hx.Keys.load(str(keys))
    base, _ = hx.open_program(NSP)
    rom = hx.RomFs(lambda o, s: base.read_ctr(1, o, s), base.romfs_level_offset(1))
    pak_off, pak_size = next((o, s) for p, o, s in rom.walk() if p.lower().endswith(".pak"))
    opened = pak.open_pak(lambda o, n: rom.read(pak_off + o, n), pak_size)
    sample = [e for e in opened.entries if e.name.startswith("Sunrise-E/Content/DataTable/Scenario/20_sub/")][:5]
    assert sample
    for entry in sample:
        assert opened.data(entry) == (EXTRACTED / entry.name).read_bytes()
