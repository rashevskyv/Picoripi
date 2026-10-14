"""BMG files with and without the leading NUL in DAT1. Super Mario Sunshine's dolpic1.bmg starts DAT1 with text (offset 0);
the save keeps each file's own choice, so an unchanged file is byte-identical and an edited one loads back."""
import struct

import pytest

from plugins.zelda_bmg import bmg_tool


def _pad(data: bytearray) -> bytes:
    while len(data) % 32:
        data.append(0)
    return bytes(data)


def bmg(texts, leading_nul: bool, info: bytes = b"\0\0\0\0") -> bytes:
    """A BMG with INF1 (8-byte entries: string offset and four attribute bytes) and DAT1 (NUL-terminated texts)."""
    dat = bytearray(b"DAT1\0\0\0\0")
    if leading_nul:
        dat += b"\0"
    offsets = []
    for text in texts:
        offsets.append(len(dat) - 8)
        dat += text.encode("cp1252") + b"\0"
    dat = bytearray(_pad(dat))                 # a section's length includes its padding, as in the game's files
    struct.pack_into(">I", dat, 4, len(dat))
    inf = bytearray(b"INF1" + b"\0" * 12)
    struct.pack_into(">HH", inf, 8, len(texts), 8)
    for offset in offsets:
        inf += struct.pack(">I", offset) + info
    inf = bytearray(_pad(inf))
    struct.pack_into(">I", inf, 4, len(inf))
    body = bytes(inf) + bytes(dat)
    head = bytearray(0x20)
    head[:8] = b"MESGbmg1"
    struct.pack_into(">II", head, 8, 0x20 + len(body), 2)
    return bytes(head) + body


@pytest.mark.parametrize("leading_nul", [True, False])
def test_an_unchanged_bmg_is_saved_byte_for_byte(leading_nul):
    data = bmg(["Hello", "Second line"], leading_nul)
    tool = bmg_tool.BMGFile()
    tool.load(data)
    assert tool.dat1_leading_null is leading_nul
    assert tool.save() == data


def test_an_edited_text_first_bmg_loads_back_with_its_new_text():
    data = bmg(["Hello", "Second line"], leading_nul=False)
    tool = bmg_tool.BMGFile()
    tool.load(data)
    tool.messages[0].parts = ["Changed text, longer than before"]
    reloaded = bmg_tool.BMGFile()
    reloaded.load(tool.save())
    texts = ["".join(p for p in m.parts if isinstance(p, str)) for m in reloaded.messages]
    assert texts == ["Changed text, longer than before", "Second line"]
    assert reloaded.dat1_leading_null is False
