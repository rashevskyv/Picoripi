"""Level-5 G4 formats of the Switch Yo-kai Watch sequels: G4TX textures and G4 fonts (synthetic files)."""
import struct
import zlib

from PIL import Image

from core import font_formats
from core.font_formats import g4font
from core.font_formats.sources import FontSource, join_pair, split_pair
from core.texture_formats import g4tx, surface, tegra, pixels


# -- builders ---------------------------------------------------------------------------------


def make_g4tx(image: Image.Image, block_log2: int = 1, name: str = "tex") -> bytes:
    """One RGBA8 texture in block-linear layout, laid out like the games' files."""
    width, height = image.size
    codec = pixels.codec("RGBA8")
    offsets = tegra.block_addresses(width, height, 4, 1 << block_log2)
    size = max(offsets) + 4
    size += -size % (512 << block_log2)
    texels = bytearray(size)
    surface.write(texels, 0, codec, width, height, image, offsets, force=True)
    nxtch = bytearray(0x100)
    nxtch[:8] = b"NXTCH000"
    struct.pack_into("<I", nxtch, 0x08, size)
    struct.pack_into("<II", nxtch, 0x14, width, height)
    struct.pack_into("<II", nxtch, 0x24, 0x25, 1)
    struct.pack_into("<I", nxtch, 0x74, block_log2)
    area = bytes(nxtch) + bytes(texels)
    head = bytearray(0x60)
    head[:4] = b"G4TX"
    struct.pack_into("<HH", head, 0x20, 1, 1)
    struct.pack_into("<I", head, 0x2C, len(area))
    entry = struct.pack("<III", 0, 0, len(area)) + bytes(0x24)
    names = struct.pack("<I", zlib.crc32(name.encode())) + b"\0" + b"\0" * 3 + struct.pack("<H", 2) + name.encode() + b"\0"
    tables = bytes(head) + entry
    tables += b"\0" * (-len(tables) % 16) + names
    tables = bytearray(tables + b"\0" * (-len(tables) % 16))
    struct.pack_into("<I", tables, 0x0C, len(tables) - 0x60)
    return bytes(tables) + area


def _entry(name: str, values) -> bytes:
    n = len(values)
    head = struct.pack("<IB", zlib.crc32(name.encode()), n) + bytes([0x55] * ((n + 3) // 4))
    return head + b"\xff" * (-len(head) % 4) + struct.pack(f"<{n}i", *values)


def make_font_table(chars) -> bytes:
    """INF, a CHR per ``(char, x, y, w, ox, advance, channel)``, KERNINF, END; box height 8."""
    rows = [("INF", [0, 6, 8, 2, len(chars), 64, 16, 0])]
    for char, x, y, w, ox, advance, channel in chars:
        rows.append(("CHR", [0, ord(char), int.from_bytes(char.encode(), "big"), x, y, w, ox, advance, channel]))
    rows += [("KERNINF", [0, 0]), ("END", [])]
    body = bytearray(16) + b"".join(_entry(n, v) for n, v in rows)
    start = len(body) + (-len(body) % 16)
    body += b"\xff" * (start - len(body))
    names = ["INF", "CHR", "KERNINF", "END"]
    blob = b"".join(n.encode() + b"\0" for n in names)
    keys = struct.pack("<4I", 0, len(names), 16 + 8 * len(names), len(blob))
    at = 0
    for n in names:
        keys += struct.pack("<Ii", zlib.crc32(n.encode()), at)
        at += len(n) + 1
    keys += blob
    keys += b"\0" * (-len(keys) % 16)
    out = body + keys + b"\x01t2b\xfe\x01\x01\x00\x01\x00" + b"\0" * 6
    struct.pack_into("<4I", out, 0, len(rows), start, 0, 0)
    return bytes(out)


def make_font() -> bytes:
    atlas = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    atlas.paste((255, 0, 0, 0), (1, 1, 4, 9))        # 'A' in the red layer
    atlas.paste((0, 255, 0, 0), (6, 1, 8, 9))        # 'B' in the green layer
    table = make_font_table([("A", 1, 1, 3, 0, 4, 0), ("B", 6, 1, 2, 1, 4, 1)])
    return join_pair(table, make_g4tx(atlas))


# -- G4TX ------------------------------------------------------------------------------------------


def test_g4tx_reads_its_texture_and_writes_back_unchanged_then_an_edit():
    image = Image.new("RGBA", (16, 16), (10, 20, 30, 255))
    image.paste((200, 100, 50, 255), (4, 4, 9, 12))
    data = make_g4tx(image)
    assert g4tx.detect(data)
    (texture,) = g4tx.read(data, {})
    assert texture.name == "tex" and texture.pixel_format == "RGBA8" and texture.image.tobytes() == image.tobytes()
    assert g4tx.write(data, {0: texture.image}, {}) == data
    edited = texture.image.copy()
    edited.putpixel((0, 0), (1, 2, 3, 4))
    out = g4tx.write(data, {0: edited}, {})
    assert len(out) == len(data) and g4tx.read(out, {})[0].image.tobytes() == edited.tobytes()


# -- G4 fonts --------------------------------------------------------------------------------------


def test_g4font_opens_and_an_unedited_model_packs_to_the_same_bytes():
    data = make_font()
    metadata, sheets = font_formats.extract("g4font", data, {"font": 0})
    assert set(font_formats.char_map(metadata)) == {"A", "B"}
    assert metadata["GLY1"][0]["cell_height"] == 8
    assert font_formats.pack("g4font", metadata, sheets, data, {"font": 0}) == data


def test_g4font_new_letter_in_a_spare_cell_becomes_a_sorted_character_and_an_edit_stays_in_its_box():
    data = make_font()
    metadata, sheets = font_formats.extract("g4font", data, {"font": 0})
    gly = metadata["GLY1"][0]
    cw, ch = gly["cell_width"], gly["cell_height"]
    sheet = sheets[0].copy()
    sheet.paste((0, 0, 0, 0), (0, 0, cw, ch))
    sheet.paste((255, 255, 255, 255), (0, 2, 2, 6))                  # 'A' redrawn smaller
    sheet.paste((255, 255, 255, 255), (2 * cw, 0, 2 * cw + 3, 7))    # cell 2: a new letter
    codes = [(font_formats.char_code(c), g) for c, g in font_formats.char_map(metadata).items()]
    metadata["MAP1"] = [font_formats.map_entries(codes + [(font_formats.char_code("Ї"), 2)])]
    metadata["WID1"][0]["packets"][2]["width"] = 5
    out = font_formats.pack("g4font", metadata, [sheet], data, {"font": 0})
    table, texture = split_pair(out)
    font = g4font._parse(out, {"font": 0})
    assert [g4font._char(r) for r in font["records"]] == ["A", "B", "Ї"]          # sorted by UTF-8
    assert font["entries"][font["info"]][2][4] == 3
    added = font["records"][2]
    assert (added["w"], added["advance"]) == (3, 5)
    assert (font["records"][0]["x"], font["records"][0]["y"]) == (1, 1)            # redrawn in its own box
    again, again_sheets = font_formats.extract("g4font", out, {"font": 0})
    cell = font_formats.coverage(again_sheets[0]).crop((2 * cw, 0, 3 * cw, ch))
    assert cell.getbbox() == (0, 0, 3, 7)
    assert len(texture) == len(split_pair(data)[1])


def test_font_source_with_a_companion_reads_and_writes_both_files(tmp_path):
    source, translation = tmp_path / "source", tmp_path / "translation"
    (source / "t").mkdir(parents=True)
    (source / "t/font.cfg.bin").write_bytes(b"table")
    (source / "t/font.g4tx").write_bytes(b"texture")
    from core.font_formats import sources
    (found,) = sources.resolve([{"label": "f", "format": "g4font", "path": "t/font.cfg.bin",
                                 "companion": "t/font.g4tx"}],
                               {"source_path": str(source), "translation_path": str(translation)})
    assert isinstance(found, FontSource)
    assert split_pair(found.read_current()) == (b"table", b"texture")
    found.write(join_pair(b"table", b"edited"))
    assert (translation / "t/font.g4tx").read_bytes() == b"edited"
    assert split_pair(found.read_current()) == (b"table", b"edited")
    assert split_pair(found.read_original()) == (b"table", b"texture")
