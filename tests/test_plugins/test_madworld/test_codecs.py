"""MadWorld codecs on synthetic data: GX C4 / IA8 pixels, one-picture TPLs, font grids, message tables, atlases,
containers, U8 archives and LZ77 streams. No game file is read here."""
import random
import struct

from plugins.madworld import archives, gx, messages


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def test_c4_pixels_round_trip_on_a_partial_block_grid():
    w, h = 13, 11                                       # not a multiple of the 8x8 block
    idx = bytearray(_rng(1).randrange(16) for _ in range(w * h))
    assert gx.c4_decode(gx.c4_encode(idx, w, h), w, h) == idx


def test_ia8_pixels_round_trip():
    w, h = 9, 6
    a = bytearray(_rng(2).randrange(256) for _ in range(w * h))
    i = bytearray(_rng(3).randrange(256) for _ in range(w * h))
    assert gx.ia8_decode(gx.ia8_encode(a, i, w, h), w, h) == (a, i)


def test_tpl_with_palette_is_read_back_and_sized():
    palette = bytes(range(32))
    data = gx.tpl(gx.C4, 8, 8, gx.c4_encode(bytearray(64), 8, 8), palette=palette, pal_fmt=0)
    image = gx.tpl_image(data)
    assert (image["format"], image["width"], image["height"]) == (gx.C4, 8, 8)
    assert image["palette"] == palette
    assert gx.tpl_size(data) == len(data)
    assert gx.tpl_size(b"not a texture") is None


def test_font_grid_round_trip_keeps_each_cell():
    cell = (5, 6)
    glyphs = []
    for n in range(5):
        w, h = 3 + n % 3, 2 + n % 4
        alpha = bytes(_rng(10 + n).randrange(256) for _ in range(w * h))
        inten = bytes(_rng(20 + n).randrange(256) for _ in range(w * h))
        glyphs.append((w, h, alpha, inten))
    glyphs.insert(2, None)                              # an empty cell
    back = gx.grid_read_ia(gx.grid_write_ia(glyphs, cell, 4), cell, 4, len(glyphs))
    for n, g in enumerate(glyphs):
        cw, ch, a, i = back[n]
        assert (cw, ch) == cell
        if g is None:
            assert not any(a)
            continue
        w, h, alpha, inten = g
        for r in range(h):
            assert a[r * cw:r * cw + w] == alpha[r * w:(r + 1) * w]
            assert i[r * cw:r * cw + w] == inten[r * w:(r + 1) * w]


def test_message_table_round_trip_and_padding():
    msgs = [(3, [0x1000, 0x1001, 0x8000, 0x8001, 0x8002]), (9, [0x8010, 0x64, 0x1002, 0x8002])]
    table = messages.msd_build(0xFFFFFFFF, msgs, size=0x80)
    assert len(table) == 0x80
    assert messages.msd_parse(table) == (0xFFFFFFFF, msgs)


def test_words_and_text_map_both_ways_with_tags():
    chars = {0: ("H", "subtitle"), 1: ("i", "subtitle")}
    words = [0x8010, 0x64, 0x1000, 0x1001, 0x8001, 0x8094, 0x0003, 0x8000, 0x1001, 0x8002]
    text, ends = messages.words_to_text(words, 0x1000, chars)
    assert text == "<8010:0064>Hi <8094><#0003>\ni" and ends
    by = {"H": 0x1000, "i": 0x1001}
    assert messages.text_to_words(text, ends, by.__getitem__) == words


def _atlas(palette: bytes, glyphs: dict) -> dict:
    """An atlas body from glyph cells, through the same builder the rebuild uses."""
    old = {"first": 0x1000, "pages": [(16, 16, bytearray(256), palette)], "whead": (0, 0), "size": 0}
    return messages.mtd_parse(messages.mtd_build(old, glyphs))


def test_atlas_build_then_parse_keeps_the_glyph_pixels():
    palette = bytes(v for k in range(16) for v in (k * 17, 255 - k * 16))
    glyphs = {}
    for n in range(3):
        cell = bytes(((n + y + x) % 16) for y in range(4) for x in range(3))
        glyphs[n] = (3, 4, cell, 4, 4.0)
    atlas = _atlas(palette, glyphs)
    assert atlas["first"] == 0x1000 and set(atlas["glyphs"]) == {0, 1, 2}
    for n, g in glyphs.items():
        got = atlas["glyphs"][n]
        assert (got[0], got[1]) == (3, 4)
        assert bytes(got[2]) == g[2]


def test_glyph_key_ignores_the_position_of_the_ink():
    left = bytes([9, 9, 0, 0, 0, 0, 0, 0])               # 4 x 2, ink in the left two columns
    right = bytes([0, 0, 9, 9, 0, 0, 0, 0])              # the same shape moved right
    other = bytes([9, 0, 0, 0, 9, 0, 0, 0])              # a different shape
    assert messages.glyph_key(4, 2, left) == messages.glyph_key(4, 2, right)
    assert messages.glyph_key(4, 2, left) != messages.glyph_key(4, 2, other)


def test_idpac_sections_round_trip():
    head = bytes(range(0x20))
    sections = [[b"MSD\0", b"abcdef"], [b"MTD\0", b"xyz"]]
    blob = messages.idpac_build(head, sections)
    assert blob[:0x20] == head
    assert messages.idpac_sections(blob) == sections


def test_pictures_finds_a_tpl_inside_another_file():
    picture = gx.tpl(gx.IA8, 4, 4, gx.ia8_encode(bytes(16), bytes(16), 4, 4))
    blob = b"\x00" * 0x40 + b"TEX\x00" + bytes(12) + picture + b"tail"
    assert messages.pictures(blob) == [(0x50, len(picture))]
    assert messages.pictures(picture) == [(0, len(picture))]


def _u8_bytes(tree: dict) -> bytes:
    """A U8 archive of nested dicts (folders) and bytes (files), the layout the reader walks."""
    nodes, names, blobs = [], bytearray(), []           # node: [kind, name offset, offset, size]

    def name(text: str) -> int:
        at = len(names)
        names.extend(text.encode("ascii") + b"\0")
        return at

    def walk(folder: dict) -> None:
        for key, value in folder.items():
            if isinstance(value, dict):
                index = len(nodes)
                nodes.append([1, name(key), 0, 0])
                walk(value)
                nodes[index][3] = len(nodes)            # a folder's size is the index after its last child
            else:
                nodes.append([0, name(key), 0, len(value)])
                blobs.append((len(nodes) - 1, value))

    nodes.append([1, 0, 0, 0])                          # the root folder
    walk(tree)
    nodes[0][3] = len(nodes)
    table = b"".join(struct.pack(">III", kind << 24 | name_at, off, size) for kind, name_at, off, size in nodes)
    names_at = 0x20 + len(table)
    data_at = names_at + len(names)
    data_at += -data_at % 0x20
    data = bytearray()
    for index, blob in blobs:
        nodes[index][2] = data_at + len(data)
        data += blob + bytes(-len(data + blob) % 0x20)
    table = b"".join(struct.pack(">III", kind << 24 | name_at, off, size) for kind, name_at, off, size in nodes)
    head = b"\x55\xaa\x38\x2d" + struct.pack(">III", 0x20, len(table) + len(names), data_at)
    body = head + bytes(0x20 - len(head)) + table + bytes(names)
    return body + bytes(data_at - len(body)) + bytes(data)


def test_u8_archive_round_trip_keeps_names_and_contents():
    tree = {"layout": {"a.tpl": b"A" * 40, "sub": {"b.csv": b"x,y\n1,2\n"}}, "home.csv": b"h"}
    flat = {"layout/a.tpl": b"A" * 40, "layout/sub/b.csv": b"x,y\n1,2\n", "home.csv": b"h"}
    raw = _u8_bytes(tree)
    assert archives.U8(raw).files == flat
    assert archives.U8(archives.U8(raw).build()).files == flat


def test_lz77_round_trip_and_nested_member_replace_and_explode():
    payload = bytes(_rng(5).randrange(4) for _ in range(900))          # repetitive: back references
    assert archives.lz_decompress(archives.lz_compress(payload)) == payload
    wrapped = archives.lz_compress(_u8_bytes({"Font": {"picture.brfnt": b"font"}, "home.csv": b"a,b\n"}))
    new = archives.replace(wrapped, "home.csv", b"c,d\n")
    assert archives.U8(archives.unwrap(new)[0]).files["home.csv"] == b"c,d\n"
    found = {}
    archives.explode(wrapped, "hbm/x.arc", lambda rel, blob: found.__setitem__(rel, blob))
    assert found == {"hbm/x.arc/Font/picture.brfnt": b"font", "hbm/x.arc/home.csv": b"a,b\n"}
