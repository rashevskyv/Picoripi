"""Rock N' Roll Racing (SNES, USA) on the owner's ROM zip (skipped without it): the text table reads, an unchanged build is the
same ROM, the codec round-trips every string, and the Europe ROM is not taken as the target."""
import os
import zipfile

import pytest

from plugins.rock_n_roll_racing import rom_text as rt

ISO_DIR = r"E:\Emulators\RomHacking\Rock N Roll Racing\ISO"
USA_ZIP = os.path.join(ISO_DIR, "Rock N' Roll Racing (USA).zip")
EUROPE_ZIP = os.path.join(ISO_DIR, "Rock 'N' Roll Racing (Europe).zip")

pytestmark = pytest.mark.skipif(not os.path.isfile(USA_ZIP), reason="owner's USA ROM zip is not on disk")


def _member(path: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        name = next(info.filename for info in archive.infolist() if info.filename.lower().endswith(".sfc"))
        return archive.read(name)


def test_usa_table_has_its_223_strings_and_each_one_round_trips():
    data = _member(USA_ZIP)
    assert rt.is_usa_rom(data)
    bank = rt.extract(data)
    strings = rt.strings_of(bank)
    assert len(strings) == 223
    assert sum(s["budget"] for s in strings) == 4597
    for string in strings:
        raw = bytes.fromhex(string["raw"])
        assert rt.encode(rt.decode(raw)) == raw


def test_unchanged_build_is_the_same_rom():
    data = _member(USA_ZIP)
    assert rt.build(data, rt.extract(data)) == data


def test_europe_rom_is_not_the_target():
    if not os.path.isfile(EUROPE_ZIP):
        pytest.skip("owner's Europe ROM zip is not on disk")
    assert not rt.is_usa_rom(_member(EUROPE_ZIP))
