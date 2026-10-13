"""Code Name: S.T.E.A.M. plugin: message archive round trip and BCH textures on synthetic data, then on the real
EU game files (skipped where the workspace is not on this machine)."""
import romhacking_root
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from plugins.code_name_steam.archive import Archive, FormatError, archive_or_none
from plugins.code_name_steam.tag_manager import TAG_RE, TagManager


def _archive(messages, shared=()):
    """A message archive: header, UTF-16 texts from 0x20 (no name), the table, the labels."""
    region = bytearray()
    offsets = []
    for text in messages:
        offsets.append(len(region))
        region += text.encode("utf-16-le") + b"\0\0"
        region += bytes(-len(region) % 4)
    for index in shared:                 # a message that reuses the text of an earlier one
        offsets.append(offsets[index])
    labels = bytearray()
    table = bytearray()
    for i, off in enumerate(offsets):
        table += struct.pack("<II", off, len(labels))
        labels += f"MID_{i}".encode() + b"\0"
    out = bytearray(0x20) + region + table + labels
    struct.pack_into("<IIII", out, 0, len(out), len(region), 0, len(offsets))
    return bytes(out)


def test_archive_reads_texts_and_labels():
    raw = _archive(["Hello", "A\nB", ""])
    archive = Archive(raw)
    assert archive.texts == ["Hello", "A\nB", ""]
    assert archive.labels == ["MID_0", "MID_1", "MID_2"]
    assert archive.build(archive.texts) == raw


def test_archive_growth_and_shared_text():
    raw = _archive(["One", "Two"], shared=(0,))
    archive = Archive(raw)
    assert archive.texts == ["One", "Two", "One"]
    grown = Archive(archive.build(["Один і ще", "Two", "One"]))
    assert grown.texts[0] == "Один і ще" and grown.texts[2] == "Один і ще" and grown.texts[1] == "Two"
    assert Archive(grown.build(grown.texts)).texts == grown.texts


def test_not_an_archive():
    assert archive_or_none(b"\0" * 8) is None
    with pytest.raises(FormatError):
        Archive(b"\x40\0\0\0" + bytes(0x1C))


def test_tags():
    assert TAG_RE.findall("Press $Ap$Ｌアイコン, to jump to %USER's turn $Arg$0,") == [
        "$Ap$Ｌアイコン,", "%USER", "$Arg$0,"]
    manager = TagManager()
    assert manager.is_tag_legitimate("$Ap$ギア,") and not manager.is_tag_legitimate("$Ap$")


WS = romhacking_root.under('Code Name STEAM')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "code_name_steam"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_real_messages_save_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs/mess/EU_English").glob("*.bin"))
    assert len(files) == 76
    total = 0
    for path in files:
        raw = path.read_bytes()
        archive = Archive(raw)
        assert archive.build(archive.texts) == raw, path.name
        total += len(archive.texts)
    assert total == 4406


def test_real_fonts_open_and_pack_back_unchanged():
    from core import font_formats
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    for item in descriptors:
        data = _need(SOURCE / item["path"]).read_bytes()
        metadata, sheets = font_formats.extract(item["format"], data)
        assert font_formats.pack(item["format"], metadata, sheets, data) == data, item["path"]


def test_real_bch_pictures_read_and_write_back():
    from core import texture_formats
    found = sorted(_need(SOURCE / "romfs/arc/EU_English.arc").rglob("*.bch"))
    assert len(found) == 93
    formats = set()
    count = 0
    for path in found[::6]:
        data = path.read_bytes()
        textures = texture_formats.read("bch", data)
        formats.update(t.pixel_format for t in textures)
        count += len(textures)
        assert texture_formats.write("bch", data, {i: t.image for i, t in enumerate(textures)}) == data, path.name
    assert count and {"ETC1A4"} <= formats


def test_bch_edit_changes_only_that_texture():
    from core import texture_formats
    path = _need(SOURCE / "romfs/arc/EU_English.arc/ui/title_lower.bch")
    data = path.read_bytes()
    textures = texture_formats.read("bch", data)
    image = Image.new("RGBA", textures[1].image.size, (255, 255, 255, 255))
    edited = texture_formats.write("bch", data, {1: image})
    again = texture_formats.read("bch", edited)
    assert len(edited) == len(data) and again[1].image.getpixel((3, 3))[0] > 200
    assert again[0].image.tobytes() == textures[0].image.tobytes()
