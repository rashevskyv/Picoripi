"""MonoGame Texture2D (.xnb) texture backend: real menu pictures round trip, and an edit is kept."""
import os
from pathlib import Path

import pytest

from core.texture_formats import xnb_texture


def _menu_dir():
    root = os.environ.get("PICORIPI_ROMHACKING", "").strip()
    folder = Path(root) / "_new" / "Links Awakening DX HD" / "Content" / "Menu" if root else None
    if folder is None or not folder.is_dir():
        pytest.skip("PICORIPI_ROMHACKING is not set or the Links Awakening DX HD menu folder is missing")
    return folder


def test_real_menu_pictures_round_trip_byte_exact():
    files = sorted(_menu_dir().glob("*.xnb"))
    assert len(files) == 4
    for path in files:
        data = path.read_bytes()
        assert xnb_texture.detect(data), path.name
        (texture,) = xnb_texture.read(data, {})
        assert xnb_texture.write(data, {0: texture.image}, {}) == data, path.name


def test_pixel_edit_is_kept_and_the_rest_stays():
    data = sorted(_menu_dir().glob("*.xnb"))[0].read_bytes()
    (texture,) = xnb_texture.read(data, {})
    image = texture.image.copy()
    image.paste((255, 0, 0, 255), (0, 0, 2, 2))
    out = xnb_texture.write(data, {0: image}, {})
    assert len(out) == len(data)
    (again,) = xnb_texture.read(out, {})
    assert again.image.getpixel((1, 1))[:3] == (255, 0, 0)


def test_a_font_file_is_not_a_texture():
    assert not xnb_texture.detect(b"XNB" + b"\x00" * 40)
