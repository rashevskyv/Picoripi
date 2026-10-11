"""Metal Gear Master Collection formats: XPR2 font, TXP texture pack, CFF rebuild with a custom Encoding."""
from pathlib import Path

import pytest

from core import font_formats, texture_formats

ROOT = Path(r"E:\Emulators\RomHacking\Metal Gear\Peace Walker\Switch\source")


def _need(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    return path.read_bytes()


@pytest.mark.parametrize("name", ["font/MLG_LOADING_FONT.xpr", "font/MLG_ORDINARY_FONT.xpr"])
def test_xpr2_font_round_trips_and_takes_a_glyph_edit(name):
    data = _need(ROOT / name)
    metadata, sheets = font_formats.extract("pw_xpr", data, {})
    assert font_formats.pack("pw_xpr", metadata, sheets, data, {}) == data
    glyph = font_formats.char_map(metadata)["A"]
    metadata["WID1"][0]["packets"][glyph]["width"] += 1
    edited = font_formats.pack("pw_xpr", metadata, sheets, data, {})
    again, _ = font_formats.extract("pw_xpr", edited, {})
    assert again["WID1"][0]["packets"][glyph]["width"] == metadata["WID1"][0]["packets"][glyph]["width"]


def test_txp_texture_pack_round_trips_and_takes_a_picture():
    from PIL import ImageDraw
    data = _need(ROOT / "texture" / "hd_font_NX.txp")
    textures = texture_formats.read("pw_txp", data, {})
    assert texture_formats.write("pw_txp", data, {i: t.image for i, t in enumerate(textures)}, {}) == data
    image = textures[1].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 60, 60), fill=(255, 0, 0, 255))
    edited = texture_formats.write("pw_txp", data, {1: image}, {})
    assert len(edited) == len(data)
    assert texture_formats.read("pw_txp", edited, {})[1].image.getpixel((30, 30)) == (255, 0, 0, 255)


def test_cff_with_custom_encoding_rebuilds_into_a_loadable_font():
    import io
    from PIL import ImageFont
    from core.font_formats import bfotf, cff
    path = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid 4\Switch\source\launcher\font"
                r"\mg_sansserif-md_otf\MG_SansSerif-Md.otf")
    plain = _need(path)
    font = bfotf.OpenType(plain)
    at, length = font.tables["CFF "]
    table = cff.Cff(plain[at:at + length])
    rebuilt = cff.rebuild_font(plain, table, font.cmap(), [], {}, None)
    ImageFont.truetype(io.BytesIO(rebuilt), 40)


ENGLISH_RAW = Path("D:/Games/MG1-2 MC/fr/stage/mg1/cache/english.raw")


def test_english_raw_split_round_trips_synthetic_bytes():
    from core import english_raw

    data = b"\x00\x00\x0bTRANSCEIVER\x00\x00\x04SEND\x00\x01\x02Hi\x00\x00\x00\x00ok text here\x00\xff"
    chunks = english_raw.split(data)
    assert english_raw.join(chunks) == data
    assert [text for is_text, text in chunks if is_text] == [b"TRANSCEIVER\x00", b"SEND\x00", b"ok text here\x00"]


def test_english_raw_split_round_trips_the_install_file():
    from core import english_raw

    data = _need(ENGLISH_RAW)
    assert english_raw.join(english_raw.split(data)) == data
