"""Final Fantasy Tactics A2 plugin: text codes, message packs, font and effect textures; real-data round trips."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.font_formats import ffta2 as ffta2_font
from core.font_formats.sources import join_pair, split_pair
from core.texture_formats import ffta2_efx
from plugins.ffta2 import a2text
from plugins.ffta2.rules import A2PakContainer
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "ffta2"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / "ffta2"
WS = Path(r"E:\Emulators\RomHacking\Final Fantasy\Tactics A2")
SOURCE = WS / "source"
needs_data = pytest.mark.skipif(not (SOURCE / "event" / "rom" / "ev_msg0.a2msg").is_file(),
                                reason="Final Fantasy Tactics A2 workspace not on disk")


def _table(*strings: bytes) -> bytes:
    head, body = bytearray(struct.pack("<H", len(strings))), bytearray()
    for raw in strings:
        head += struct.pack("<IIH", len(raw), 2 + 10 * len(strings) + len(body), 1)
        body += raw
    out = head + body
    return bytes(out + bytes(-len(out) % 32))


def _pack(kind: str, members) -> bytes:
    index, pak = a2text.pack_members(list(members))
    return a2text.join_file(kind, index, pak)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_codes_become_text_and_tags_and_back():
    raw = bytes([0x09, 0x20, 0x01, 0x88, 0x89, 0xC0, 0x00, 0xCA, 0x01, 0x96, 0x56, 0xC3, 0x00, 0xC1, 0x00])
    text = a2text.to_editor(raw)
    assert text == "He ［］\n[CA:01][x96]é[page]"
    assert a2text.from_editor(text, a2text.split_tail(raw)[1]) == raw


def test_the_hidden_ending_is_kept():
    for raw in (b"\x02\x00", b"\x02\xc1\x00", b"\x02\xc1\x00\x00", b"\x02"):
        body, tail = a2text.split_tail(raw)
        assert body == b"\x02" and a2text.from_editor(a2text.to_editor(raw), tail) == raw


def test_a_character_the_font_lacks_is_refused():
    with pytest.raises(a2text.FormatError):
        a2text.from_editor("Привіт")


def test_line_count_is_the_most_lines_on_a_page():
    assert a2text.line_count(a2text.from_editor("a\nb[end]c[end]", b"")) == 2


def test_a_pack_lays_out_its_members_again():
    data = _pack("T", [_table(b"\x02\x00", b"\x03\x00"), None, _table(b"\x04\x00")])
    pack = a2text.Pack(data)
    assert pack.groups == [[b"\x02\x00", b"\x03\x00"], [], [b"\x04\x00"]]
    assert pack.build({}) == data
    again = a2text.Pack(pack.build({(0, 1): a2text.from_editor("UA TEST")}))
    assert again.groups[0][1] == a2text.from_editor("UA TEST") and again.groups[2] == [b"\x04\x00"]


def test_the_plugin_saves_only_what_changed():
    data = _pack("T", [_table(b"\x02\x00", b"\x03\x00")])
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["A", "B"]]
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][1] = "UA TEST"
    saved = a2text.Pack(rules.save_data_to_json_obj(blocks, names))
    assert saved.groups[0] == [b"\x02\x00", a2text.from_editor("UA TEST")]


def test_the_menu_picture_pack_opens_as_an_archive():
    data = _pack("P", [b"abcd", None, b"efgh" * 3])
    container = A2PakContainer(data)
    assert A2PakContainer.can_handle(data) and container.list_files() == ["#0", "#2"]
    container.write_file("#2", b"ijkl")
    again = A2PakContainer(container.pack())
    assert again.read_file("#2") == b"ijkl" and again.read_file("#0") == b"abcd"


def _font() -> bytes:
    glyphs = [bytes((4, 0xFF, 0, 0)), bytes((8, 0x33, 1, 0)) + struct.pack("<I", 0b01011101)]
    head = 2 + 4 * len(glyphs)
    offsets, body = [], b""
    for record in glyphs:
        offsets.append(head + len(body))
        body += record
    image = struct.pack("<H2I", 2, *offsets) + body
    return join_pair(image + bytes(-len(image) % 16), struct.pack("<H", 2) + bytes((4, 6)))


def test_the_font_packs_back_and_takes_a_new_glyph():
    data = _font()
    metadata, sheets = font_formats.extract("ffta2", data, {})
    assert font_formats.pack("ffta2", metadata, sheets, data, {}) == data
    assert font_formats.char_map(metadata)["A"] == 1
    sheets[0].paste(Image.new("RGBA", (3, 5), (255, 255, 255, 255)), (16 * 2 + 1, 4))
    metadata["MAP1"][0] = font_formats.map_entries([(32, 0), (65, 1), (font_formats.char_code("Ж"), 2)])
    packed = font_formats.pack("ffta2", metadata, sheets, data, {})
    image, widths = split_pair(packed)
    assert struct.unpack_from("<H", image)[0] == 3 and struct.unpack_from("<H", widths)[0] == 3
    again, again_sheets = font_formats.extract("ffta2", packed, {})
    assert again_sheets[0].crop((32, 0, 48, 16)).getbbox() == (1, 4, 4, 9)
    assert font_formats.char_map(again)["B"] == 2       # glyph 2 is text code 3


def _efx() -> bytes:
    palette = struct.pack("<8H", 0, 0x7FFF, 0x001F, 0x03E0, 0x7C00, 0, 0, 0)
    texels = bytes((31 << 3 | i % 8) for i in range(16))
    chunk = struct.pack("<III", 0x20 + len(palette) + len(texels), 0x0B000100, 0) + bytes((0, 0, 0x52, 1))
    chunk += struct.pack("<8H", 6, 8, 4, 4, 4, 4, 0, 0) + palette + texels
    return ffta2_efx.MAGIC + struct.pack("<fI", 1.0, 0x10 + len(chunk)) + chunk


def test_effect_textures_read_and_write():
    data = _efx()
    textures = texture_formats.read("ffta2_efx", data)
    assert len(textures) == 1 and textures[0].image.size == (4, 4) and textures[0].pixel_format == "A5I3"
    assert texture_formats.write("ffta2_efx", data, {0: textures[0].image}) == data
    image = textures[0].image.copy()
    image.putpixel((0, 0), (255, 0, 0, 255))
    written = texture_formats.write("ffta2_efx", data, {0: image})
    assert texture_formats.read("ffta2_efx", written)[0].image.getpixel((0, 0)) == (255, 0, 0, 255)


# -- real data ---------------------------------------------------------------------------------------------------


@needs_data
def test_every_pack_and_string_round_trips_byte_exact():
    total = 0
    for path in SOURCE.rglob("*.a2msg"):
        data = path.read_bytes()
        pack = a2text.Pack(data)
        kind, index, pak = a2text.split_file(data)
        assert a2text.pack_members(pack.members, index, pack.pak_unit) == (index, pak)
        for group in pack.groups:
            for raw in group:
                assert a2text.from_editor(a2text.to_editor(raw), a2text.split_tail(raw)[1]) == raw
                total += 1
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(data)
        assert rules.save_data_to_json_obj(blocks, names) == data
    assert total == 33198


@needs_data
def test_the_font_and_every_listed_picture_write_back_unchanged():
    load_rules(PLUGIN)
    from core.texture_formats.sources import resolve
    meta = {"source_path": str(SOURCE), "translation_path": "", "is_directory_mode": True}
    entries = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    sources = resolve(entries, meta)
    assert len(sources) > 40
    for source in sources:
        texture = source.read_original()
        raw = Path(source.source_path).read_bytes()
        from core.texture_formats.sources import unwrap
        data, rewrap = unwrap(raw, source.member, source.params)
        assert rewrap(texture_formats.write(source.format, data, {source.index: texture.image}, source.params)) == raw
    font = join_pair((SOURCE / "menu/font/UseMoji_image.bin").read_bytes(),
                     (SOURCE / "menu/font/FontWidthTable.bin").read_bytes())
    metadata, sheets = font_formats.extract("ffta2", font, {})
    assert font_formats.pack("ffta2", metadata, sheets, font, {}) == font
    assert len(font_formats.char_map(metadata)) == len(ffta2_font.CHARACTERS)
