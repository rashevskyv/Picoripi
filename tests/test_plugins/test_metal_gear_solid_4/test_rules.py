"""Metal Gear Solid 4 (Master Collection) plugin: real data from the workspace when it is on this machine."""
from pathlib import Path

import pytest

from plugins.metal_gear_solid_4 import loc
from plugins.common import mgmc_launcher

SOURCE = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid 4\Switch\source")


def _need(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    return path.read_bytes()


@pytest.mark.parametrize("kind", ["codec", "lang", "demo", "movie", "spc"])
def test_localization_file_is_byte_exact_and_takes_an_edit(kind):
    data = _need(SOURCE / "localization" / kind / f"{kind}_en.mgs4")
    blocks = loc.texts(loc.parse(data))
    assert loc.dump(loc.parse(data)) == data
    assert loc.build(data, blocks) == data
    edited = [[text + " X" for text in block] for block in blocks]
    again = loc.texts(loc.parse(loc.build(data, edited)))
    assert again == edited


def test_launcher_text_is_byte_exact_and_takes_an_edit():
    path = SOURCE / "launcher" / "text" / "defaultlocalgroup_assets_module" / "textdata"
    files = sorted(path.glob("textdata_ui*.mctext"))
    if not files:
        pytest.skip("launcher text is not unpacked on this machine")
    data = files[0].read_bytes()
    lines = [text for _path, text in mgmc_launcher.lines(data)]
    assert mgmc_launcher.build(data, lines) == data
    assert [t for _p, t in mgmc_launcher.lines(mgmc_launcher.build(data, [t + " X" for t in lines]))] == [
        t + " X" for t in lines]
