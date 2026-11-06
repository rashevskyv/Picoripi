"""BMFont text fonts with DDS pages: the model, an unchanged save, a new letter, the page set as companion files."""
import struct

from core import font_formats as ff
from core.font_formats import bmfont, char_code, char_map, map_entries, sources
from core.font_formats.sources import join_files, join_pair, split_files, split_pair

FNT = ("info face=\"Test\" size=8 spacing=1,1\r\n"
       "common lineHeight=8 base=7 scaleW=16 scaleH=16 pages=1\r\n"
       "page id=0 file=\"test_00.dds\"\r\n"
       "chars count=2\r\n"
       "char id=65   x=0 y=0 width=4 height=6 xoffset=1 yoffset=1 xadvance=6 page=0 chnl=15\r\n"
       "char id=32   x=0 y=0 width=0 height=0 xoffset=0 yoffset=0 xadvance=3 page=0 chnl=15\r\n"
       "kerning first=65 second=65 amount=-1\r\n")


def _dds(size: int = 16) -> bytes:
    """A transparent BC1 page: every block has both colours 0 and index 3 (transparent black)."""
    head = bytearray(128)
    head[0:4] = b"DDS "
    struct.pack_into("<IIII", head, 4, 124, 0x1007, size, size)
    struct.pack_into("<I", head, 76, 32)
    struct.pack_into("<I", head, 80, 4)
    head[84:88] = b"DXT1"
    return bytes(head) + b"\0\0\0\0\xff\xff\xff\xff" * ((size // 4) ** 2)


def _font() -> bytes:
    page = bmfont.dds.read(_dds(), {})[0].image
    page.paste((255, 255, 255, 255), (0, 0, 4, 6))       # 'A' is a full 4x6 box
    return join_pair(FNT.encode("utf-8"), join_files([("test_00.dds", bmfont.dds.write(_dds(), {0: page}, {}))]))


def test_the_model_puts_each_glyph_at_its_offsets_in_a_cell():
    meta, sheets = ff.extract("bmfont", _font(), {})
    font = bmfont._Font(_font())
    assert (font.cell_w, font.cell_h) == (8, 8)
    assert char_map(meta)["A"] == 0 and meta["WID1"][0]["packets"][0]["width"] == 6
    ink = ff.coverage(sheets[0])
    assert ink.crop((0, 0, 8, 8)).getbbox() == (1, 1, 5, 7)
    assert ff.pack("bmfont", meta, sheets, _font(), {}) == _font()


def test_a_new_letter_gets_free_page_space_and_a_char_line():
    data = _font()
    meta, sheets = ff.extract("bmfont", data, {})
    spare = 2
    sheets[0].paste((255, 255, 255, 255), (spare * 8 + 2, 1, spare * 8 + 4, 7))   # a 2x6 stroke
    meta["MAP1"] = [map_entries(sorted([(char_code("A"), 0), (char_code(" "), 1), (char_code("і"), spare)]))]
    meta["WID1"][0]["packets"][spare]["width"] = 4
    meta["WID1"][0]["packets"][0]["width"] = 7
    out = ff.pack("bmfont", meta, sheets, data, {})
    fnt = split_pair(out)[0].decode("utf-8")
    assert "chars count=3" in fnt and "kerning first=65 second=65 amount=-1" in fnt
    assert "char id=1110 x=5 y=0 width=2 height=6 xoffset=2 yoffset=1 xadvance=4 page=0 chnl=15" in fnt
    assert "xadvance=7" in fnt.splitlines()[4]
    again, again_sheets = ff.extract("bmfont", out, {})
    glyph = char_map(again)["і"]
    assert ff.coverage(again_sheets[0]).crop((glyph * 8, 0, glyph * 8 + 8, 8)).getbbox() == (2, 1, 4, 7)


def test_a_companion_glob_reads_every_page_and_writes_only_the_changed_one(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    (source / "font").mkdir(parents=True)
    (source / "font" / "test.fnt").write_bytes(b"fnt")
    for name in ("test_00.dds", "test_01.dds"):
        (source / "font" / name).write_bytes(name.encode())
    found = sources.resolve([{"label": "Font", "format": "bmfont", "path": "font/test.fnt",
                              "companion": "font/test_*.dds"}],
                            {"source_path": str(source), "translation_path": str(translation)})[0]
    main, pages = split_pair(found.read_current())
    assert main == b"fnt" and split_files(pages) == [("test_00.dds", b"test_00.dds"), ("test_01.dds", b"test_01.dds")]
    found.write(join_pair(b"new", join_files([("test_00.dds", b"test_00.dds"), ("test_01.dds", b"changed")])))
    assert sorted(p.name for p in (translation / "font").iterdir()) == ["test.fnt", "test_01.dds"]
    assert split_files(split_pair(found.read_current())[1])[1] == ("test_01.dds", b"changed")


def test_the_dds_helper_page_is_transparent():
    assert bmfont.dds.read(_dds(), {})[0].image.getchannel("A").getextrema() == (0, 0)
