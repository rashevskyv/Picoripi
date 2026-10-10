"""Metal Gear Solid 2 / 3 Master Collection (Switch): plugin save path, the text font and the pictures.

The plugin tests run anywhere. The real-data tests read the Switch workspace's source files and skip when they are
missing (the workspace is not part of the repository).
"""
from pathlib import Path

import pytest

from core import font_formats
from core.texture_formats import ctxr
from plugins.metal_gear_solid_23_mc.rules import GameRules

SOURCE = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid 2\Switch\source")
FONT = SOURCE / "font" / "MGS_Font_nht.raw"
PICTURE = SOURCE / "texture" / "Misc" / "loading" / "_nx" / "loading.ctxr"


class _Context:
    """What the host gives ``prepare_save_context``: the file's versions, newest first."""

    relative_path = "text/codec.json"

    def __init__(self, data: bytes):
        self._data = data

    def existing_versions(self):
        yield self._data


def _document(lines):
    return {"format": "mgs23mc-text", "version": 1, "game": "MGS2", "group": "codec", "files": 1,
            "blocks": [{"name": "eu/codec/_bp/a.sdt", "lines": lines}]}


def test_text_document_saves_the_edited_lines_and_keeps_the_rest():
    raw = (b'{"format": "mgs23mc-text", "version": 1, "game": "MGS2", "group": "codec", "files": 1, '
           b'"blocks": [{"name": "eu/codec/_bp/a.sdt", "lines": ["Hello, Snake.", "Ok."]}]}')
    rules = GameRules()
    data, names = rules.load_data_from_json_obj(_document(["Hello, Snake.", "Ok."]))
    assert data == [["Hello, Snake.", "Ok."]]
    rules.prepare_save_context(_Context(raw))
    saved = rules.save_data_to_json_obj([["Hi, Snake.", "Ok."]], names)
    assert saved["format"] == "mgs23mc-text"
    assert saved["group"] == "codec"
    assert saved["blocks"] == [{"name": "eu/codec/_bp/a.sdt", "lines": ["Hi, Snake.", "Ok."]}]


@pytest.mark.skipif(not FONT.is_file(), reason="MGS2 Switch workspace not unpacked")
def test_text_font_packs_back_byte_exact():
    raw = FONT.read_bytes()
    metadata, sheets = font_formats.extract("mgs_nht", raw, {})
    assert font_formats.pack("mgs_nht", metadata, sheets, raw, {}) == raw


@pytest.mark.skipif(not PICTURE.is_file(), reason="MGS2 Switch workspace not unpacked")
def test_picture_reads_and_writes_back_byte_exact():
    data = PICTURE.read_bytes()
    image = ctxr.read(data, {})[0].image
    assert ctxr.write(data, {0: image}, {}) == data
