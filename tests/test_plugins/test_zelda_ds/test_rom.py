"""NitroFS rebuild of the DS Zelda ROMs: an unchanged ROM comes back identical; a grown file reads back.

The real-data tests read the clean USA dumps from the scratch folder (never copied into the repository); they skip
when the folder is missing.
"""
import struct
from pathlib import Path

import pytest

from plugins.zelda_ds import rom
from plugins.zelda_ds.bmg import Bmg, build

SCRATCH = Path(r"D:\RomHacking_tmp\zelda_ds\rom_clean")
PH = SCRATCH / "ph_usa.nds"
ST = SCRATCH / "st_usa.nds"


def _header_crc_ok(data: bytes) -> bool:
    return struct.unpack_from("<H", data, 0x15E)[0] == rom._crc16(data[:0x15E])


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_phantom_hourglass_rebuild_without_changes_is_identical():
    data = PH.read_bytes()
    assert rom.rebuild(data, {}) == data


@pytest.mark.skipif(not ST.is_file(), reason="clean Spirit Tracks ROM not in the scratch folder")
def test_spirit_tracks_rebuild_without_changes_is_identical():
    data = ST.read_bytes()
    assert rom.rebuild(data, {}) == data


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_grown_text_file_reads_back_and_other_files_stay():
    data = PH.read_bytes()
    before = rom.nitro_files(data)
    name = "English/Message/mainselect.bmg"
    edited = build(before[name], {12: "[tag:01:14000000]UA TEST Enter a name, please, now."})
    assert len(edited) > len(before[name])
    out = rom.rebuild(data, {name: edited})
    after = rom.nitro_files(out)
    assert after[name] == edited
    assert Bmg(after[name]).texts()[12].endswith("Enter a name, please, now.")
    assert all(after[k] == before[k] for k in before if k != name)
    assert _header_crc_ok(out)
    assert struct.unpack_from("<I", out, 0x80)[0] <= len(out)


def test_unknown_file_is_refused():
    with pytest.raises(rom.RomError):
        rom.rebuild(b"\x00" * 0x200, {"no/such/file.bmg": b"x"})
