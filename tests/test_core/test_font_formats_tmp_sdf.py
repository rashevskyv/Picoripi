"""TextMesh Pro SDF fonts (tmp_sdf), PNG textures and plain OpenType fonts in the bfotf backend."""
import io
import json

from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.font_formats import bfotf, tmp_sdf
from core.font_formats.sources import join_pair, split_pair


def _font() -> bytes:
    """Two glyphs, 'A' at the bottom left of a 64x32 atlas (TMP counts y from the bottom) and 'B' next to it."""
    tree = {"m_Name": "test", "m_AtlasPadding": 2, "m_FaceInfo": {"m_PointSize": 32, "m_LineHeight": 40.0},
            "m_GlyphTable": [
                {"m_Index": 1, "m_Metrics": {"m_HorizontalAdvance": 10.5}, "m_GlyphRect": {"m_X": 2, "m_Y": 2, "m_Width": 8, "m_Height": 10}},
                {"m_Index": 2, "m_Metrics": {"m_HorizontalAdvance": 9.25}, "m_GlyphRect": {"m_X": 20, "m_Y": 2, "m_Width": 6, "m_Height": 10}}],
            "m_CharacterTable": [{"m_Unicode": 65, "m_GlyphIndex": 1}, {"m_Unicode": 66, "m_GlyphIndex": 2}]}
    atlas = Image.new("L", (64, 32), 0)
    ImageDraw.Draw(atlas).rectangle((2, 32 - 12, 9, 32 - 3), fill=200)        # 'A' rect, top-down rows
    out = io.BytesIO()
    atlas.save(out, "PNG")
    return join_pair(tmp_sdf.dump(tree), out.getvalue())


def test_tmp_sdf_reads_glyph_rects_and_packs_back_unchanged():
    data = _font()
    metadata, sheets = font_formats.extract("tmp_sdf", data, {})
    chars = font_formats.char_map(metadata)
    assert set(chars) == {"A", "B"}
    assert [p["width"] for p in metadata["WID1"][0]["packets"]] == [10, 9]
    assert sheets[0].getpixel((5, 5))[3] == 200            # the 'A' cell shows the atlas rect (padding 2)
    assert font_formats.pack("tmp_sdf", metadata, sheets, data, {}) == data


def test_tmp_sdf_writes_a_redrawn_cell_and_a_width():
    data = _font()
    metadata, sheets = font_formats.extract("tmp_sdf", data, {})
    cell_w = metadata["GLY1"][0]["cell_width"]
    ImageDraw.Draw(sheets[0]).rectangle((cell_w + 2, 2, cell_w + 7, 11), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][0]["width"] = 12
    tree_bytes, atlas_bytes = split_pair(font_formats.pack("tmp_sdf", metadata, sheets, data, {}))
    tree = json.loads(tree_bytes)
    assert tree["m_GlyphTable"][0]["m_Metrics"]["m_HorizontalAdvance"] == 12.0
    assert tree["m_GlyphTable"][1]["m_Metrics"]["m_HorizontalAdvance"] == 9.25
    atlas = Image.open(io.BytesIO(atlas_bytes))
    assert atlas.getpixel((22, 32 - 6)) == 255             # inside 'B' (x 20..25, rows 20..29)
    assert atlas.getpixel((5, 32 - 6)) == 200              # 'A' untouched


def test_png_texture_round_trip_and_edit():
    image = Image.new("RGBA", (8, 4), (10, 20, 30, 255))
    raw = io.BytesIO()
    image.save(raw, "PNG")
    data = raw.getvalue()
    assert texture_formats.detect(data) == "png"
    texture = texture_formats.read("png", data)[0]
    assert texture_formats.write("png", data, {0: texture.image}) == data
    edited = texture.image.copy()
    edited.putpixel((1, 1), (255, 0, 0, 255))
    again = texture_formats.read("png", texture_formats.write("png", data, {0: edited}))[0].image
    assert again.getpixel((1, 1)) == (255, 0, 0, 255)


def test_bfotf_takes_a_plain_opentype_font_as_it_is():
    plain = b"OTTO" + bytes(60)
    assert bfotf.decrypt(plain) == (plain, None)
    assert bfotf.encrypt(plain, None) == plain
