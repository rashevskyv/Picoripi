"""Twin Snakes stage.dat as an archive: its texture packs read and written through the Textures pipeline."""
import random
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from core.containers import ContainerManager
from core.texture_formats import bti, pixels, sources
from plugins.mgs_ts.stage_dat import SECTOR, StageDatContainer

WORKSPACE = Path(r"E:\Emulators\RomHacking\Metal Gear\Twin Snakes")


def picture(width, height, seed=1):
    return Image.frombytes("RGBA", (width, height),
                           bytes((i * seed * 37 + i // 4) & 0xFF for i in range(width * height * 4)))


def make_tpl(images):
    """``[(gx format id, image)]`` (sizes in whole blocks, no palettes) -> a TPL."""
    heads_at = 0x0C + 8 * len(images)
    data_at = heads_at + 0x24 * len(images)
    data_at += -data_at % 0x20
    heads, blobs, table = b"", b"", b""
    for fmt, image in images:
        table += struct.pack(">II", heads_at + len(heads), 0)
        heads += struct.pack(">HHII", image.height, image.width, fmt, data_at + len(blobs)) + bytes(0x24 - 12)
        blobs += pixels.codec(f"gx:{bti.FORMATS[fmt]}").encode(image)
    body = b"\x00\x20\xaf\x30" + struct.pack(">II", len(images), 0x0C) + table + heads
    return body + bytes(data_at - len(body)) + blobs


def _pack(tpl, count=2):
    """An ext 0x13 texture pack: u32 count at 0x10, u32 TPL offset at 0x18, 0x80-byte records, the TPL."""
    head = bytearray(0x20 + 0x80 * count)
    struct.pack_into(">III", head, 0x10, count, 4, len(head))
    return bytes(head) + tpl


def _stage(folders):
    """One stage: ``folders`` = [(folder word, [(file word, bytes)])], each folder a zlib stream at a sector."""
    ents, body = [], bytearray()
    for word, files in folders:
        blob, table = bytearray(), []
        for k, (fword, data) in enumerate(files):
            table.append((fword, len(blob)))
            blob += data + (bytes(-len(data) % 0x20) if k + 1 < len(files) else b"")
        packed = zlib.compress(bytes(blob), 6)
        ents += [(word, len(blob)), (0x7E000000 | len(packed), len(body))] + table + [(0x7F000000, len(blob))]
        body += packed + bytes(-len(packed) % SECTOR)
    head = struct.pack(">I", len(ents)) + b"".join(struct.pack(">II", *e) for e in ents)
    return head + bytes(-len(head) % SECTOR) + bytes(body)


def _stage_dat(stages):
    """``stages`` = [(name, stage bytes)] -> stage.dat (header, table, each stage at a sector)."""
    head = bytearray(struct.pack(">IHHHHI", 0x401D1141, 1, 1, len(stages), 0xCCCC, 0x1234))
    body, sector = bytearray(), 1
    for name, data in stages:
        head += name.encode().ljust(8, b"\0") + struct.pack(">I", sector + len(body) // SECTOR)
        body += data + bytes(-len(data) % SECTOR)
    return bytes(head) + bytes(SECTOR - len(head)) + bytes(body) + bytes(SECTOR)     # trailing padding


@pytest.fixture
def stage_dat():
    tpl = make_tpl([(14, picture(16, 8)), (6, picture(8, 8, seed=2))])     # CMPR, RGBA8
    first = _stage([(0x7F000002, [(0x13ABCDEF, _pack(tpl)), (0x06180720, b"script" * 9)]),
                    (0x7F000004, [(0x11383C45, b"font" * 40)])])
    second = _stage([(0x7F000002, [(0x13ABCDEF, _pack(tpl)), (0x0A000001, b"other" * 7)])])
    return _stage_dat([("n_title", first), ("r_cmmn", second)]), tpl


def test_lists_and_reads_the_texture_packs_as_tpl(stage_dat):
    data, tpl = stage_dat
    assert StageDatContainer.can_handle(data) and not StageDatContainer.can_handle(tpl + bytes(SECTOR))
    archive = StageDatContainer(data)
    assert archive.list_files() == ["n_title/13abcdef.tpl", "n_title/06180720.bin", "n_title/11383c45.bin",
                                    "r_cmmn/13abcdef.tpl", "r_cmmn/0a000001.bin"]
    assert archive.read_file("n_title/13abcdef.tpl") == tpl
    assert archive.read_file("n_title/11383c45.bin") == b"font" * 40
    with pytest.raises(KeyError):
        archive.read_file("n_title/00000000.bin")


def test_unchanged_or_rewritten_with_the_same_bytes_packs_to_the_original(stage_dat):
    data, tpl = stage_dat
    archive = StageDatContainer(data)
    assert archive.pack() is data
    archive.write_file("n_title/13abcdef.tpl", tpl)
    assert not archive.has_pending_changes() and archive.pack() == data


def test_a_written_texture_reads_back_and_the_other_stage_stays_in_place(stage_dat):
    data, tpl = stage_dat
    archive = StageDatContainer(data)
    pack_head = archive._stored(archive._key("n_title/13abcdef.tpl"))[:0x120]
    new_tpl = tpl[:-64] + bytes(range(64))
    archive.write_file("n_title/13abcdef.tpl", new_tpl)
    out = archive.pack()
    assert len(out) == len(data)
    again = StageDatContainer(out)
    assert again.read_file("n_title/13abcdef.tpl") == new_tpl
    assert again._stored(again._key("n_title/13abcdef.tpl"))[:0x120] == pack_head     # the pack records stay
    for name in ("n_title/06180720.bin", "n_title/11383c45.bin", "r_cmmn/13abcdef.tpl", "r_cmmn/0a000001.bin"):
        assert again.read_file(name) == archive.read_file(name)
    assert out[0x18:0x1C] == data[0x18:0x1C] and out[0x24:0x28] == data[0x24:0x28]      # nothing moved


def test_a_stage_that_grows_pushes_the_next_one_and_the_table_follows(stage_dat):
    data, _tpl = stage_dat
    archive = StageDatContainer(data)
    noise = random.Random(1).randbytes(3 * SECTOR)       # does not compress
    archive.write_file("n_title/06180720.bin", noise)
    out = archive.pack()
    again = StageDatContainer(out)
    assert again.read_file("n_title/06180720.bin") == noise
    assert again.read_file("r_cmmn/0a000001.bin") == b"other" * 7
    assert struct.unpack_from(">I", out, 0x24)[0] > struct.unpack_from(">I", data, 0x24)[0]


def test_texture_sources_open_a_stage_file_and_write_the_translation_copy(stage_dat, tmp_path):
    data, _tpl = stage_dat
    ContainerManager.register(StageDatContainer)
    source, translation = tmp_path / "source", tmp_path / "translation"
    (source / "texture").mkdir(parents=True)
    (source / "texture" / "n_title.stage").write_bytes(data)
    descriptor = {"label": "Menu", "format": "tpl", "path": "texture/n_title.stage",
                  "member": "n_title/13abcdef.tpl", "params": {"texture": "{0,1}"}}
    found = sources.resolve([descriptor], {"source_path": str(source), "translation_path": str(translation)})
    assert [s.key for s in found] == ["texture/n_title.stage/n_title/13abcdef.tpl#0",
                                      "texture/n_title.stage/n_title/13abcdef.tpl#1"]
    one = sources.resolve([dict(descriptor, params={"texture": "{1}"})],
                          {"source_path": str(source), "translation_path": str(translation)})
    assert [s.name for s in one] == ["1"]
    white = Image.new("RGBA", found[1].size, (255, 255, 255, 255))
    assert sources.write_many([(found[1], white)]) == [found[1]]
    assert (source / "texture" / "n_title.stage").read_bytes() == data
    assert found[1].read_current().image.getpixel((3, 3)) == (255, 255, 255, 255)
    assert sources.write_many([(found[1], None)])
    written = StageDatContainer((translation / "texture" / "n_title.stage").read_bytes())
    assert written.read_file("n_title/13abcdef.tpl") == StageDatContainer(data).read_file("n_title/13abcdef.tpl")


def test_the_game_files_round_trip_byte_for_byte():
    path = WORKSPACE / "source" / "disc1" / "files" / "stage.dat"
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    data = path.read_bytes()
    archive = StageDatContainer(data)
    member = "n_title/13984557.tpl"
    tpl = archive.read_file(member)
    assert tpl[:4] == b"\x00\x20\xaf\x30"
    archive.write_file(member, tpl)
    assert archive.pack() is data


def test_a_grid_font_in_a_texture_pack_opens_packs_back_and_takes_a_glyph(stage_dat, tmp_path):
    from core import font_formats
    from core.font_formats import sources as font_sources
    data, _tpl = stage_dat
    ContainerManager.register(StageDatContainer)
    source, translation = tmp_path / "source", tmp_path / "translation"
    (source / "texture").mkdir(parents=True)
    (source / "texture" / "n_title.stage").write_bytes(data)
    descriptor = {"label": "Grid", "format": "texture_grid", "path": "texture/n_title.stage",
                  "member": "13abcdef.tpl", "params": {"image": 0, "cell": [8, 8], "first_code": 0x41}}
    font = font_sources.resolve([descriptor], {"source_path": str(source), "translation_path": str(translation)})[0]
    assert font.member == "n_title/13abcdef.tpl"
    original = font.read_original()
    metadata, sheets = font_formats.extract("texture_grid", original, font.params)
    assert font_formats.char_map(metadata)["B"] == 1 and metadata["WID1"][0]["packets"][1]["width"] == 8
    assert font_formats.pack("texture_grid", metadata, sheets, original, font.params) == original
    sheets[0].paste((255, 255, 255, 255), (8, 0, 16, 8))           # glyph "B" becomes a box
    font.write(font_formats.pack("texture_grid", metadata, sheets, original, font.params))
    again = font_formats.extract("texture_grid", font.read_current(), font.params)[1][0]
    assert again.crop((8, 0, 16, 8)).getcolors() == [(64, (255, 255, 255, 255))]
    assert (source / "texture" / "n_title.stage").read_bytes() == data
    written = StageDatContainer((translation / "texture" / "n_title.stage").read_bytes())
    assert written.read_file("r_cmmn/0a000001.bin") == StageDatContainer(data).read_file("r_cmmn/0a000001.bin")


@pytest.mark.skipif(not (WORKSPACE / "source" / "text" / "texture" / "r_cmmn.stage").is_file(),
                    reason="Twin Snakes texture stages not unpacked here")
def test_every_real_font_source_opens_and_packs_back_byte_for_byte():
    import json
    from core import font_formats
    from core.font_formats import sources as font_sources
    ContainerManager.register(StageDatContainer)
    descriptors = json.loads((Path(__file__).parents[3] / "plugins" / "mgs_ts" / "font_sources.json")
                             .read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(WORKSPACE / "source" / "text")})
    assert len(found) == len(descriptors)
    for font in found:
        original = font.read_original()
        metadata, sheets = font_formats.extract(font.format, original, font.params)
        assert metadata["GLY1"][0]["end_glyph"] + 1 >= 10, font.label
        assert font_formats.pack(font.format, metadata, sheets, original, font.params) == original, font.label
