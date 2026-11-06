"""Lunar SSS Remastered preview: the BMFont atlas glyphs, the packed PS1 program and the shared tag names (synthetic data)."""
import pytest
from PIL import Image

from core.containers.image_files import ImageError
from plugins.lunar_sssc.rules import tag_mappings
from plugins.lunar_sssc_remastered import atlas, preview, unpack

FNT = """info face="Test" size=64
common lineHeight=64 base=56 scaleW=128 scaleH=64 pages=1
page id=0 file="test_00.png"
chars count=2
char id=12354 x=0 y=0 width=32 height=64 xoffset=0 yoffset=0 xadvance=64 page=0 chnl=15
char id=32 x=0 y=0 width=0 height=0 xoffset=0 yoffset=0 xadvance=16 page=0 chnl=15
"""


def _font(folder):
    """A one-glyph font: 'あ' is the left half of the cell, inked in the alpha channel."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / atlas.FONT_FILE).write_text(FNT, encoding="utf-8")
    sheet = Image.new("RGBA", (128, 64), (255, 255, 255, 0))
    sheet.paste((255, 255, 255, 255), (0, 0, 32, 64))
    sheet.save(folder / "test_00.png")


def test_parse_reads_the_size_pages_and_chars():
    font = atlas.parse(FNT)
    assert font["size"] == 64 and font["pages"] == {0: "test_00.png"}
    assert font["chars"][12354]["width"] == 32


def test_glyphs_scale_the_atlas_cell_to_sixteen_rows(tmp_path):
    _font(tmp_path)
    assert atlas.glyphs(tmp_path) == {"あ": [0xFF00] * 16}
    assert atlas.glyphs(tmp_path, skip="あ") == {}
    assert atlas.glyphs(tmp_path / "missing") == {}


def test_read_sources_without_the_ps1_disc_uses_the_remastered_font(tmp_path):
    _font(tmp_path.joinpath(*unpack.FONT_FOLDER.split("/")))
    sources = preview.read_sources(str(tmp_path))
    assert list(sources["glyphs"]) == ["あ"] and sources["files"] == {}


def test_read_sources_without_any_font_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        preview.read_sources(str(tmp_path))


def test_unpack_exe_expands_literals_and_back_references():
    # flags 0xFF: eight literals; flags 0x02: a short copy (4 bytes from 8 back), then the end mark
    packed = b"PS-X EXE".ljust(0x1000, b"\0") + b"\xffPS-X EXE" + bytes([0x02, (2 << 6) | 56, 0, 0, 0])
    assert unpack.unpack_exe(packed) == b"PS-X EXEPS-X"
    with pytest.raises(ImageError):
        unpack.unpack_exe(b"MZ" + bytes(0x1000))


def test_the_ps1_members_include_the_portraits_and_palette():
    names = ["TEXT001.DAT", "FACE_012.TIZ", "PEO.PAL", "SYSTEM.DAT"]
    assert [n for n in names if unpack.PS1_MEMBERS_RE.match(n)] == names[:3]


def test_raw_window_controls_have_readable_names():
    mappings = tag_mappings()
    assert mappings["{New window}"] == "{raw:01}" and mappings["{Wait for button}"] == "{raw:04}"
