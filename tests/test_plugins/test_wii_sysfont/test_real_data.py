"""Real-data checks of the workspace script ``_shared\\scripts\\zt\\wii_sysfont.py`` on the Wii system fonts
(the Rabbids disc copies); skipped when the script or the fonts are not on this machine."""
import importlib
import struct
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
FONTS = Path(r"E:\Emulators\RomHacking\Raving Rabbids Party Collection\source\files\fonts")
UA = "ЄІЇєіїҐґ"


@pytest.fixture(scope="module")
def tool():
    if not (SCRIPTS / "zt" / "wii_sysfont.py").is_file() or not (FONTS / "wbf1.brfna").is_file():
        pytest.skip("Wii system fonts / workspace scripts are not on this machine")
    sys.path.insert(0, str(SCRIPTS))
    try:
        yield importlib.import_module("zt.wii_sysfont")
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize("name", ["wbf1.brfna", "wbf2.brfna"])
def test_unchanged_font_rebuilds_byte_for_byte(tool, name):
    data = (FONTS / name).read_bytes()
    assert tool.assemble(tool.parse(data)) == data


@pytest.mark.parametrize("name", ["wbf1.brfna", "wbf2.brfna"])
def test_ukrainian_letters_get_cells_and_the_result_is_stable(tool, name):
    data = (FONTS / name).read_bytes()
    before = tool.char_map(tool.parse(data))
    assert not any(ord(c) in before for c in UA)
    new, slots = tool.add_ukrainian(data)
    parts = tool.parse(new)
    codes = tool.char_map(parts)
    assert [chr(c) for c in slots] == sorted(UA, key=ord) and all(codes[c] == g for c, g in slots.items())
    assert codes[ord("І")] == before[ord("I")] and codes[ord("ї")] == before[ord("ï")]
    cells = struct.unpack_from(">HH", parts["cwdh"][0], 8)
    assert cells[1] == max(before.values()) + 4 == codes[ord("ґ")]
    assert tool.assemble(parts) == new and tool.add_ukrainian(new) == (new, slots)
