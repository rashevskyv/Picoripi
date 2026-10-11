"""PNG textures (pret decompilations): read, write back unchanged, keep the grey depth; texture_grid over a PNG."""
import io

from PIL import Image, ImageDraw

from core import font_formats, texture_formats


def _grey_png(levels=(0, 85, 170, 255)) -> bytes:
    image = Image.new("L", (16, 8), 255)
    for x, level in enumerate(levels):
        image.putpixel((x, 0), level)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_png_reads_and_writes_back_the_same_bytes():
    data = _grey_png()
    assert texture_formats.detect(data, "x.png") == "png"
    texture = texture_formats.read("png", data)[0]
    assert texture.image.size == (16, 8) and texture.pixel_format == "png:L"
    assert texture_formats.write("png", data, {0: texture.image}) == data


def test_png_edit_snaps_to_the_grey_levels_of_its_depth():
    data = _grey_png()
    image = texture_formats.read("png", data)[0].image
    image.putpixel((5, 5), (100, 100, 100, 255))
    image.putpixel((6, 5), (0, 0, 0, 0))                 # transparent turns white
    new = Image.open(io.BytesIO(texture_formats.write("png", data, {0: image})))
    assert new.mode == "L" and new.getpixel((5, 5)) == 85 and new.getpixel((6, 5)) == 255


def test_texture_grid_font_over_png_with_empty_cells():
    data = _grey_png()
    params = {"texture": "png", "cell": [8, 8], "chars": ["A", ""]}
    metadata, sheets = font_formats.extract("texture_grid", data, params)
    assert font_formats.char_map(metadata) == {"A": 0}
    assert font_formats.pack("texture_grid", metadata, sheets, data, params) == data
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((8, 0, 15, 7), fill=(0, 0, 0, 255))
    packed = font_formats.pack("texture_grid", metadata, [sheet], data, params)
    assert Image.open(io.BytesIO(packed)).getpixel((12, 4)) == 0


def test_an_indexed_png_edit_keeps_mode_palette_depth_and_every_other_index():
    from core.texture_formats import png as png_format

    # 4-bit palette picture with a repeated colour and a transparent index 0
    palette = [0, 0, 0, 255, 0, 0, 255, 0, 0, 255, 0, 0, 0, 0, 255] + [9, 9, 9] * 11
    image = Image.new("P", (8, 2))
    image.putpalette(palette)
    image.putdata([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
    image.info["transparency"] = 0
    out = io.BytesIO()
    image.save(out, format="PNG")
    data = out.getvalue()
    assert data[24] == 4
    original = Image.open(io.BytesIO(data))
    rgba = original.convert("RGBA")
    rgba.putpixel((7, 1), (255, 0, 0, 255))                # index 15 -> the colour of index 1
    written = png_format.write(data, {0: rgba}, {})
    edited = Image.open(io.BytesIO(written))
    assert edited.mode == "P" and written[24] == 4
    assert edited.getpalette()[:len(original.getpalette())] == original.getpalette()
    assert list(edited.getdata())[:15] == list(original.getdata())[:15]
    assert list(edited.getdata())[15] == 1


def test_a_4_bit_greyscale_png_keeps_its_depth_after_an_edit():
    from core.texture_formats import png as png_format

    data = png_format._packed_png((4, 1), 4, 0, [0, 5, 10, 15], [])
    texture = texture_formats.read("png", data)[0]
    assert list(texture.image.convert("L").getdata()) == [0, 85, 170, 255]
    texture.image.putpixel((1, 0), (0, 0, 0, 255))
    written = texture_formats.write("png", data, {0: texture.image})
    assert written[24] == 4
    again = Image.open(io.BytesIO(written))
    assert list(again.getdata()) == [0, 0, 170, 255]
