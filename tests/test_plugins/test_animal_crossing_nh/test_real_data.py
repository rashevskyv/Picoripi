"""Animal Crossing: New Horizons on the user's own unpacked game (skipped without it): every text file saves back
byte for byte (also fully re-encoded), the keyboard text too, every font packs back unchanged and the text fonts
(TrueType and CFF) take a glyph edit, every texture format in the layouts and models reads, writes back and takes
an edit, and the workspace scripts build the mod and turn an NSZ into the original NCAs."""
import hashlib
import importlib
import os
import struct
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.containers import sarc, yaz0
from core.font_formats import sources as font_sources
from core.texture_formats import bntx
from plugins.animal_crossing_nh.rules import GameRules
from plugins.animal_crossing_nh.tags import from_editor
from plugins.common.msbt import Msbt

WS = Path(r"E:\Emulators\RomHacking\Animal Crossing\New Horizons")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
SOURCE = WS / "source"
needs_game = pytest.mark.skipif(not (SOURCE / "Message" / "String_USen.sarc.zs").is_file(),
                                reason="Animal Crossing: New Horizons not unpacked")
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _zt(name):
    if not (SCRIPTS / "zt" / f"{name}.py").is_file():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module(f"zt.{name}")
    finally:
        sys.path.remove(str(SCRIPTS))


def _cell_box(metadata, char):
    grid = metadata["GLY1"][0]
    cell = font_formats.char_map(metadata)[char]
    sheet, slot = divmod(cell, grid["glyph_horizontal_count"] * grid["glyph_vertical_count"])
    row, column = divmod(slot, grid["glyph_horizontal_count"])
    x, y = column * grid["cell_width"], row * grid["cell_height"]
    return sheet, (x, y, x + grid["cell_width"], y + grid["cell_height"])


@needs_game
def test_every_message_file_saves_back_byte_for_byte():
    archives = sorted((SOURCE / "Message").glob("*_USen.sarc.zs"))
    assert len(archives) == 11
    files = messages = raw_tags = 0
    for archive in archives:
        data, _ = sarc.decompress(archive.read_bytes())
        parsed = sarc.Sarc(data)
        assert parsed.build() == data, archive
        for name, raw in parsed.files.items():
            rules = GameRules()
            blocks, names = rules.load_data_from_json_obj(raw)
            assert rules.save_data_to_json_obj(blocks, names) == raw, (archive.name, name)
            assert Msbt(raw).build([from_editor(text) for text in blocks[0]]) == raw, (archive.name, name)
            files += 1
            messages += len(blocks[0])
            raw_tags += sum(text.count("{tag:") for text in blocks[0])
    assert (files, messages) == (3086, 120498)
    assert raw_tags == 10                           # two rare tags with mixed layouts stay raw


@needs_game
def test_the_keyboard_text_saves_back_and_takes_an_edit():
    for path in sorted((SOURCE / "Swkbd" / "message" / "USen").glob("*.msbt.szs")):
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        blocks[0][2] = "UA TEST"
        edited = Msbt(yaz0.decompress(rules.save_data_to_json_obj(blocks, names)))
        assert edited.messages[2] == ["UA TEST"]


def _fonts(tmp_path):
    rules = GameRules()
    meta = {"source_path": str(SOURCE), "translation_path": str(tmp_path), "is_directory_mode": True}
    return font_sources.resolve(rules.get_font_sources(), meta)


@needs_game
def test_every_font_opens_and_packs_back_unchanged(tmp_path):
    fonts = _fonts(tmp_path)
    assert len(fonts) == 15
    for font in fonts:
        data = font.read_original()
        metadata, sheets = font_formats.extract(font.format, data, font.params)
        assert font_formats.pack(font.format, metadata, sheets, data, font.params) == data, font.label


@pytest.mark.parametrize("name", ["nintendoP_Seurat-B.bfttf", "nintendoP_RodinNTLG-EB_003_Park.bfotf"])
@needs_game
def test_the_text_fonts_have_every_ukrainian_letter_and_take_a_glyph_edit(tmp_path, name):
    font = next(f for f in _fonts(tmp_path) if f.name == name)
    data = font.read_original()
    metadata, sheets = font_formats.extract(font.format, data, font.params)
    assert set(UKRAINIAN) <= set(font_formats.char_map(metadata))
    sheet, box = _cell_box(metadata, "S")
    ImageDraw.Draw(sheets[sheet]).rectangle((box[0] + 3, box[1] + 6, box[0] + 26, box[1] + 30),
                                            fill=(255, 255, 255, 255))
    font.write(font_formats.pack(font.format, metadata, sheets, data, font.params))
    again, again_sheets = font_formats.extract(font.format, font.read_current(), font.params)
    assert font_formats.coverage(again_sheets[sheet]).getpixel((box[0] + 14, box[1] + 18)) > 200
    a_sheet, a_box = _cell_box(again, "A")
    original_a = font_formats.extract(font.format, data, font.params)[1][a_sheet].crop(a_box)
    assert again_sheets[a_sheet].crop(a_box).tobytes() == original_a.tobytes()


def _bntx_files():
    for path in sorted(list((SOURCE / "Layout").glob("*.zs")) + list((SOURCE / "Model").glob("*.zs"))):
        data, _ = sarc.decompress(path.read_bytes())
        for name, member in sarc.Sarc(data).files.items():
            if member[:4] == b"SARC":
                for inner, blob in sarc.Sarc(member).files.items():
                    if blob[:4] == b"BNTX":
                        yield f"{path.name}/{name}/{inner}", blob
            elif member[:4] in (b"BNTX", b"FRES"):
                yield f"{path.name}/{name}", member


@needs_game
def test_every_texture_format_reads_writes_back_and_takes_an_edit():
    found, edited = set(), set()
    for name, blob in _bntx_files():
        at, size = bntx._span(blob)
        formats = [bntx.FORMATS[t["format"]] for t in bntx._textures(blob[at:at + size])]
        found.update(formats)
        if set(formats) <= edited:
            continue
        textures = bntx.read(blob, {})
        assert bntx.write(blob, {i: t.image for i, t in enumerate(textures)}, {}) == blob, name
        for index, texture in enumerate(textures):
            if texture.pixel_format in edited or min(texture.image.size) < 32:
                continue
            image = texture.image.copy()
            ImageDraw.Draw(image).rectangle((8, 8, 23, 23), fill=(255, 0, 0, 255))
            back = bntx.read(bntx.write(blob, {index: image}, {}), {})[index].image
            assert back.tobytes() != texture.image.tobytes(), (name, texture.name)
            if texture.pixel_format not in ("BC4", "L8"):                # one channel: the box is ink there
                assert back.getpixel((16, 16))[0] > 200, (name, texture.name, texture.pixel_format)
            edited.add(texture.pixel_format)
    assert found == {"BC1", "BC3", "BC4", "BC5", "L8", "LA8", "RGB565", "ASTC4x4", "ASTC5x4", "ASTC5x5", "ASTC6x5",
                     "ASTC6x6", "ASTC8x8", "ASTC12x12"}
    assert found - edited <= {"LA8", "RGB565"} or edited == found       # tiny textures of a format may be skipped


@needs_game
def test_the_build_puts_changed_archives_into_the_mod(tmp_path):
    acnh = _zt("acnh")
    rel = "Message/LayoutMsg_USen.sarc.zs"
    (tmp_path / "source" / "Message").mkdir(parents=True)
    (tmp_path / "translation" / "Message").mkdir(parents=True)
    original = (SOURCE / rel).read_bytes()
    (tmp_path / "source" / rel).write_bytes(original)
    (tmp_path / "translation" / rel).write_bytes(original)               # unchanged: not in the mod
    acnh.build(tmp_path, {})
    mod = tmp_path / "build" / "atmosphere" / "contents" / acnh.TID / "romfs"
    assert mod.is_dir() and not any(mod.iterdir())
    container = sarc.SarcContainer(original)
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(container.read_file("Title.msbt"))
    blocks[0] = [text.replace("Press", "UA TEST") for text in blocks[0]]
    container.write_file("Title.msbt", rules.save_data_to_json_obj(blocks, names))
    (tmp_path / "translation" / rel).write_bytes(container.pack())
    acnh.build(tmp_path, {})
    built = sarc.SarcContainer((mod / rel).read_bytes()).read_file("Title.msbt")
    assert any(text.startswith("UA TEST") for text in GameRules().load_data_from_json_obj(built)[0][0])


@needs_game
def test_unreadable_update_files_are_told_from_readable_ones():
    acnh = _zt("acnh")
    good = (SOURCE / "Font" / "BmpFont_US.sarc.zs").read_bytes()
    assert acnh.readable("/Font/BmpFont_US.sarc.zs", good)
    assert not acnh.readable("/Font/BmpFont_US.sarc.zs", bytes(b ^ 0x5A for b in good))
    assert acnh.readable("/a.szs", b"Yaz0....") and not acnh.readable("/a.szs", b"junk")


def test_an_nsz_becomes_the_original_ncas(tmp_path):
    """Two zstd frames in one NCZ stream, a first section inside the 0x4000-byte header, an AES-CTR section
    (re-encrypted when the ``cryptography`` package is there, as with the system Python the .bat files use)."""
    from compression import zstd
    ncz = _zt("ncz")
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        Cipher = None
    key, counter = os.urandom(16), os.urandom(8) + bytes(8)
    body = os.urandom(0x3000) + bytes(0x5000)                         # 0x4000..0xC000
    first, second = (0xC00, 0x7400, 1), (0x8000, 0x4000, 3 if Cipher else 1)
    nca = bytearray(os.urandom(0x4000) + body)
    plain = bytes(nca)
    if Cipher:
        enc = Cipher(algorithms.AES(key), modes.CTR(counter[:8] + (0x8000 >> 4).to_bytes(8, "big"))).encryptor()
        nca[0x8000:0xC000] = enc.update(plain[0x8000:0xC000])
    name = hashlib.sha256(nca).hexdigest()[:32].upper()
    sections = b"".join(struct.pack("<QQQQ", o, s, t, 0) + (key if t == 3 else bytes(16))
                        + (counter if t == 3 else bytes(16)) for o, s, t in (first, second))
    stream = zstd.compress(plain[0x4000:0x6000]) + zstd.compress(plain[0x6000:])
    entry = bytes(nca[:0x4000]) + b"NCZSECTN" + struct.pack("<Q", 2) + sections + stream
    names = f"{name}.ncz\0".encode() + b"\0" * 4
    pfs = (b"PFS0" + struct.pack("<II", 1, len(names)) + bytes(4) + struct.pack("<QQII", 0, len(entry), 0, 0)
           + names + entry)
    (tmp_path / "game.nsz").write_bytes(pfs)
    ncz.convert(tmp_path / "game.nsz", tmp_path / "game.nsp", lambda _text: None)
    out = (tmp_path / "game.nsp").read_bytes()
    count, strings = struct.unpack_from("<II", out, 4)
    offset, size, _name_at = struct.unpack_from("<QQI", out, 0x10)
    start = 0x10 + 0x18 * count + strings
    assert out[0x10 + 0x18:0x10 + 0x18 + 36] == f"{name.lower()}.nca".encode()
    assert out[start + offset:start + offset + size] == bytes(nca)
