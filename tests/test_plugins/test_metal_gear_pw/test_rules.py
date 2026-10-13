"""Peace Walker (Master Collection) plugin: real data from the workspace when it is on this machine."""
import romhacking_root

import pytest

from plugins.metal_gear_pw import olang

SOURCE = romhacking_root.under('Metal Gear\\Peace Walker\\Switch\\source\\text')


@pytest.mark.parametrize("name", ["lang_start_nx.olang", "olangWw_nx.olang"])
def test_olang_is_byte_exact_and_takes_an_edit(name):
    path = SOURCE / name
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    data = path.read_bytes()
    lines = olang.lines(data)
    assert olang.build(data, lines) == data
    edited = olang.build(data, [text + " X" for text in lines])
    assert olang.lines(edited) == [text + " X" for text in lines]
