"""Senran Kagura Burst plugin: synthetic TAMS files, the executable's string pool, the .bin pack and its compression;
and, skipped where the workspace is not on this machine, the real game files (432 message files, 2,629 strings of
code.bin, the layout packs with their pictures, the five CFNA fonts)."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.containers.darc import DarcContainer
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.senran_kagura_burst import binpack, pool, tams
from plugins.senran_kagura_burst.rules import GameRules
from plugins.testing import check_loads, check_validator

PLUGIN_NAME = "senran_kagura_burst"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN_NAME
WS = Path(r"E:\Emulators\RomHacking\Senran Kagura\Burst\3DS")
SOURCE = WS / "source"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def make_tams(texts, records=b"\x01\0\0\0\0\0\x00\x00"):
    """A TAMS file: two script records (the records bytes) and the messages."""
    nmsg = len(texts)
    nrec = 2
    table_end = 12 + 2 * (nmsg + 2) + 2 * nrec
    rec_at = table_end
    text_at = rec_at + len(records)
    blobs = [t.encode("utf-16-le") + b"\0\0" for t in texts]
    offsets, at = [], text_at
    for blob in blobs:
        offsets.append(at)
        at += len(blob)
    head = b"TAMS" + struct.pack("<HHI", 0x200, nrec, nmsg)
    table_a = struct.pack(f"<{nmsg + 2}H", rec_at, text_at, *offsets)
    table_b = struct.pack("<2H", rec_at, rec_at + 6)
    return head + table_a + table_b + records + b"".join(blobs)


# -- TAMS ------------------------------------------------------------------------------------------


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN_NAME)
    check_validator(PLUGIN_NAME)


def test_tams_round_trips_and_a_text_may_grow():
    raw = make_tams(['I walk.\n\x07v02001"Hi!"\u25bd', "Second \x07cff0000ffred\x07r.\u25a1"])
    t = tams.Tams(raw)
    assert len(t.messages) == 2 and t.build(t.messages) == raw
    assert tams.to_editor(t.messages[0]) == 'I walk.\n{v02001}"Hi!"\u25bd'
    assert tams.from_editor(tams.to_editor(t.messages[1])) == t.messages[1]
    longer = list(t.messages)
    longer[0] = "A much longer translation of the first message that does not fit before."
    out = tams.Tams(t.build(longer))
    assert out.messages == longer and out.prefix == t.prefix and out.text_start == t.text_start
    assert struct.unpack_from("<H", out.raw, 12 + 6)[0] == out.text_start + len(longer[0]) * 2 + 2


def test_tams_refuses_what_the_u16_offsets_cannot_hold():
    t = tams.Tams(make_tams(["a", "b"]))
    with pytest.raises(tams.FormatError):
        t.build(["x" * 40000, "y"])
    with pytest.raises(tams.FormatError):
        t.build(["only one"])
    with pytest.raises(tams.FormatError):
        tams.Tams(b"NOPE" + bytes(20))


def test_plugin_load_and_save_use_the_editor_form_of_the_tags():
    raw = make_tams(['\x07v02001"Hi!"\u25bd', "plain"])
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks == [['{v02001}"Hi!"\u25bd', "plain"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "Простий текст"
    assert tams.Tams(rules.save_data_to_json_obj(blocks, {})).messages[1] == "Простий текст"


def test_the_tag_manager_knows_the_game_codes():
    rules = GameRules()
    manager = rules.tag_manager_class(rules) if hasattr(rules, "tag_manager_class") else None
    assert manager is not None
    for tag in ("{v02001}", "{b008}", "{s022}", "{cff0000ff}", "{r}"):
        assert manager.is_tag_legitimate(tag)
    assert not manager.is_tag_legitimate("{x}")


# -- the executable's strings ------------------------------------------------------------------------


def make_code(strings):
    raw = bytearray(0x10000)
    at = 0x1000
    for text in strings:
        blob = text.encode("utf-16-le") + b"\0\0"
        raw[at:at + len(blob)] = blob
        at += len(blob)
    return bytes(raw)


def test_the_pool_finds_strings_and_writes_them_in_place():
    strings = [f"Mission number {i} briefing text" for i in range(30)] + ["Hello\nthere world"]
    raw = make_code(strings)
    p = pool.Pool(raw)
    assert [s for b in p.texts() for s in b] == strings
    assert p.rebuild(p.texts()) == raw
    blocks = [list(b) for b in p.texts()]
    blocks[0][0] = "Коротко"
    out = p.rebuild(blocks)
    assert len(out) == len(raw) and pool.Pool(out).texts()[0][0] == "Коротко"
    blocks[0][0] = "x" * 80
    with pytest.raises(pool.PoolError):
        p.rebuild(blocks)


def test_the_pool_skips_file_names_and_identifiers():
    strings = ["rom:/font/font.bcfna", "rom:/ui/lyt_menu_hanzo.bin"] + [f"Real text number {i} of the game" for i in range(25)]
    p = pool.Pool(make_code(strings))
    assert [s for b in p.texts() for s in b] == strings[2:]


# -- the .bin pack ---------------------------------------------------------------------------------------


def lz_literals(plain: bytes) -> bytes:
    """A compressed pack that holds only literals (flag bytes of zeros)."""
    out = bytearray(struct.pack("<II", len(plain), 0))
    for k in range(0, len(plain), 8):
        out.append(0)
        out += plain[k:k + 8]
    return bytes(out)


def test_the_pack_builds_lists_changes_and_reads_back():
    files = [b"darc" + bytes(60), b"CGFX" + bytes(10), b"hello"]
    plain = binpack.build_plain(files)
    assert len(plain) % 0x80 == 0 and binpack.is_plain(plain)
    c = binpack.PackContainer(plain)
    assert c.list_files() == ["0.darc", "1.bcres", "2.bin"]
    assert [c.read_file(n) for n in c.list_files()] == files and c.pack() == plain
    c.write_file("2.bin", b"changed!!")
    again = binpack.PackContainer(c.pack())
    assert again.read_file("2.bin") == b"changed!!" and again.read_file("0.darc") == files[0]


def test_a_compressed_pack_is_read_and_a_change_is_compressed_again():
    plain = binpack.build_plain([b"darc" + bytes(40), b"data" * 20])
    packed = lz_literals(plain)
    assert binpack.is_compressed(packed) and not binpack.is_plain(packed)
    c = binpack.PackContainer(packed)
    assert c.pack() == packed and c.read_file("1.bin") == b"data" * 20
    c.write_file("1.bin", b"new")
    again = c.pack()
    assert binpack.is_compressed(again) and binpack.PackContainer(again).read_file("1.bin") == b"new"
    assert len(again) < len(plain)


def test_the_compressor_round_trips_runs_patterns_and_noise():
    import random
    rng = random.Random(3)
    data = bytes(rng.randrange(256) for _ in range(3000)) + bytes(70000) + b"abcd" * 500 + bytes(range(256)) * 3
    packed = binpack.lz_compress(data)
    assert binpack.lz_decompress(packed) == data and len(packed) < len(data) // 2


def test_the_decoder_follows_copies_and_the_long_form():
    # literals "ab", a copy of 4 bytes from 2 back (b0 0xFE, b1 3), then b1 == 0 with the u16 299: 300 bytes
    # copied from 1 back (b0 0xFF)
    stream = bytes([0b00110000, ord("a"), ord("b"), 0xFE, 3, 0xFF, 0, 0x2B, 0x01])
    plain = binpack.lz_decompress(struct.pack("<II", 2 + 4 + 300, 0) + stream)
    assert plain == b"ab" + b"abab" + b"b" * 300


# -- real game files -------------------------------------------------------------------------------------


def test_every_real_scenario_file_round_trips():
    files = sorted(_need(SOURCE / "romfs" / "scenario").rglob("*.bin"))
    assert len(files) == 432
    total = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        assert not any("\x07" in text for text in blocks[0]), path.name
        total += len(blocks[0])
    assert total == 3759


def test_the_real_executable_strings_round_trip_and_an_edit_lands():
    raw = _need(SOURCE / "exefs" / "code.bin").read_bytes()
    p = pool.Pool(raw)
    texts = p.texts()
    assert sum(len(b) for b in texts) == 2629
    assert p.rebuild(texts) == raw
    where = next((b, i) for b, block in enumerate(texts) for i, t in enumerate(block) if t.startswith("Preparing game data"))
    edited = [list(b) for b in texts]
    edited[where[0]][where[1]] = "Preparing."
    assert pool.Pool(p.rebuild(edited)).texts()[where[0]][where[1]] == "Preparing."


def test_the_real_fonts_open_and_an_edit_lands_in_the_packed_file():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 5
    for source in found:
        data = source.read_original()
        assert font_formats.detect(data) == "cfna"
        metadata, sheets = font_formats.extract("cfna", data)
        assert font_formats.pack("cfna", metadata, sheets, data) == data, source.label
    data = _need(SOURCE / "romfs" / "font" / "font.bcfna").read_bytes()
    metadata, sheets = font_formats.extract("cfna", data)
    edited = [s.copy() for s in sheets]
    edited[0].putpixel((1, 1), (255, 255, 255, 255))
    edited[0].putpixel((2, 1), (0, 0, 0, 0))
    out = font_formats.pack("cfna", metadata, edited, data)
    assert out != data and out[:4] == b"CFNA" and struct.unpack_from("<I", out, 0x0C)[0] == len(out)
    _meta, back = font_formats.extract("cfna", out)
    assert back[0].tobytes() == edited[0].tobytes() and back[1].tobytes() == sheets[1].tobytes()
    with pytest.raises(ValueError):
        font_formats.pack("cfna", {**metadata, "MAP1": metadata["MAP1"] + [font_formats.map_entries([(0x0490, 0)])]},
                          sheets, data)


def test_the_real_layout_packs_rebuild_and_a_picture_edit_lands():
    ui = _need(SOURCE / "romfs" / "ui")
    plain = packed = 0
    for path in sorted(ui.glob("lyt_*.bin")):
        raw = path.read_bytes()
        assert binpack.PackContainer.can_handle(raw), path.name
        c = binpack.PackContainer(raw)
        plain += not c._compressed
        packed += c._compressed
        if c._compressed or path.stat().st_size < 400000:
            assert binpack.build_plain([c.read_file(n) for n in c.list_files()]) == c._plain, path.name
    assert plain + packed == 38 and packed == 20
    # one picture of the title layout through the plugin's own texture sources: write and read back
    descriptors = [d for d in json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
                   if d["label"] == "Title and common layouts"]
    descriptors[0] = dict(descriptors[0], path="romfs/ui/lyt_title_bt.bin")
    import tempfile
    GameRules()    # registers the pack and darc containers
    with tempfile.TemporaryDirectory() as tmp:
        found = texture_sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": tmp,
                                                      "is_directory_mode": True})
        assert len(found) == 29
        source = next(s for s in found if s.name == "mui_title_00_bt" or s.key.endswith("mui_title_00_bt.bclim"))
        before = source.read_original()
        image = before.image.copy()
        image.paste(Image.new("RGBA", (16, 16), (255, 0, 255, 255)), (0, 0))
        assert source.write(image) is True
        after = source.read_current().image
        assert after.getpixel((3, 3))[0] > 235 and after.getpixel((3, 3))[1] < 20 and after.getpixel((3, 3))[2] > 235
        out = Path(tmp) / "romfs" / "ui" / "lyt_title_bt.bin"
        assert binpack.is_plain(out.read_bytes())    # the title pack was plain
        names = binpack.PackContainer(out.read_bytes()).list_files()
        assert names == ["0.darc"] and len(DarcContainer(binpack.PackContainer(out.read_bytes()).read_file("0.darc")).list_files()) > 100


def test_real_ctpk_pictures_round_trip():
    files = sorted(_need(SOURCE / "romfs" / "logo").glob("*.ctpk"))
    assert len(files) == 2
    for path in files:
        data = path.read_bytes()
        textures = texture_formats.read("ctpk", data)
        assert texture_formats.write("ctpk", data, {i: t.image for i, t in enumerate(textures)}) == data


def test_a_real_compressed_pack_is_changed_and_compressed_again():
    raw = _need(SOURCE / "romfs" / "ui" / "lyt_prologue_hebijo.bin").read_bytes()
    c = binpack.PackContainer(raw)
    assert c._compressed and c.pack() == raw
    name = c.list_files()[0]
    darc = DarcContainer(c.read_file(name))
    member = next(n for n in darc.list_files() if n.endswith(".bclim"))
    blob = darc.read_file(member)
    tex = texture_formats.read("bflim", blob)[0]
    image = tex.image.copy()
    image.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (0, 0))
    darc.write_file(member, texture_formats.write("bflim", blob, {0: image}))
    c.write_file(name, darc.pack())
    out = c.pack()
    assert binpack.is_compressed(out) and len(out) < len(raw) * 1.2
    again = DarcContainer(binpack.PackContainer(out).read_file(name))
    assert texture_formats.read("bflim", again.read_file(member))[0].image.getpixel((2, 2))[:3] >= (240, 0, 0)
