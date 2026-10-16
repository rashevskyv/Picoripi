"""Brilliant Diamond / Shining Pearl: an edited picture is encoded in its texture's own format and read back the same way the
reader decodes it, and only the changed PNGs are picked up for the build. No game files: the textures are made here."""
import pytest
from PIL import Image

from core.texture_formats import pixels
from plugins.pokemon_bdsp import assets, build


def _picture(width, height, mode="RGBA"):
    image = Image.new(mode, (width, height))
    for y in range(height):
        for x in range(width):
            v = (x * 37 + y * 11) % 256
            image.putpixel((x, y), {"L": v, "RGB": (v, 90, 255 - v), "RGBA": (v, 255 - v, 90, 255)}[mode])
    return image


def test_raw_formats_round_trip_through_the_reader():
    picture = _picture(5, 3, "L")
    value = {"m_Width": 5, "m_Height": 3, "m_TextureFormat": 1, "image data": assets.encode_texture({"m_Width": 5, "m_Height": 3, "m_TextureFormat": 1}, picture)}
    assert list(assets.texture_image(None, value).getdata()) == list(picture.getdata())


def test_an_rgba_texture_keeps_its_alpha():
    picture = _picture(4, 4)
    value = {"m_Width": 4, "m_Height": 4, "m_TextureFormat": 4}
    value["image data"] = assets.encode_texture(value, picture)
    assert list(assets.texture_image(None, value).convert("RGBA").getdata()) == list(picture.getdata())


def test_a_block_texture_of_another_size_is_refused():
    value = {"m_Width": 8, "m_Height": 8, "m_TextureFormat": 50}
    with pytest.raises(assets.UnsupportedTexture):
        assets.encode_texture(value, _picture(4, 4))


def test_a_block_texture_stores_whole_blocks_and_the_picture_size_is_kept():
    # 7 x 5 is not a whole number of 6 x 6 blocks: the encoder pads it and the stored size is the block count
    picture = Image.new("RGBA", (7, 5), (90, 160, 30, 255))
    value = {"m_Width": 7, "m_Height": 5, "m_TextureFormat": 50}
    data = assets.encode_texture(value, picture)
    assert len(data) == 2 * 1 * 16
    decoded = pixels.codec("ASTC6x6").decode(data, 7, 5)
    assert decoded.size == (7, 5)


def test_only_the_pictures_that_differ_are_collected(tmp_path):
    source, translation = tmp_path / "source", tmp_path / "translation"
    same = "texture/UIs/textures/field/firstboot/a.png"
    edited = "texture/Dpr/movie/dia/logo/logo_dia_en/logo_dia_en.png"
    for root in (source, translation):
        (root / same).parent.mkdir(parents=True, exist_ok=True)
        (root / edited).parent.mkdir(parents=True, exist_ok=True)
    (source / same).write_bytes(b"same")
    (translation / same).write_bytes(b"same")
    (source / edited).write_bytes(b"old")
    (translation / edited).write_bytes(b"new")
    changed = build.changed_pictures(source, translation)
    assert changed == {"Dpr/movie/dia/logo/logo_dia_en": {edited: b"new"}}


def test_font_atlases_are_collected_by_their_bundle(tmp_path):
    source, translation = tmp_path / "source", tmp_path / "translation"
    atlas = "font/efigs_font/efigs_font.png"
    (translation / atlas).parent.mkdir(parents=True)
    (translation / atlas).write_bytes(b"edited")
    assert build._changed_pngs(source, translation, "font") == {"font/efigs_font": {atlas: b"edited"}}
