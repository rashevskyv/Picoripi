"""The TextMesh Pro atlas face of the shared renderer: metrics, the glyph's place and the SDF threshold (synthetic), and the
owner's efigs font atlas when the workspace is on disk (skipped otherwise)."""
import json

import romhacking_root
import pytest
from PIL import Image

from plugins.common import flyt_message as fm

FONT_JSON = romhacking_root.under("Pokemon") / "Brilliant Diamond and Shining Pearl" / "source" / "font" / "efigs_font"


def _asset():
    return {
        "m_FaceInfo": {"m_PointSize": 32, "m_Scale": 1.0, "m_LineHeight": 40.0, "m_AscentLine": 30.0},
        "m_GlyphTable": [{"m_Index": 1,
                          "m_Metrics": {"m_Width": 10.0, "m_Height": 10.0, "m_HorizontalBearingX": 2.0,
                                        "m_HorizontalBearingY": 10.0, "m_HorizontalAdvance": 12.0},
                          "m_GlyphRect": {"m_X": 5, "m_Y": 5, "m_Width": 10, "m_Height": 10},
                          "m_Scale": 1.0, "m_AtlasIndex": 0}],
        "m_CharacterTable": [{"m_Unicode": 65, "m_GlyphIndex": 1, "m_Scale": 1.0}],
        "m_AtlasPadding": 0,
    }


def _atlas():
    # The atlas origin is bottom-left: the glyph at X 5..14, Y 5..14 is rows 17..26 from the top.
    image = Image.new("L", (32, 32), 0)
    image.paste(255, (5, 17, 15, 27))
    return image


def test_a_tmp_glyph_has_its_metrics_scaled_to_the_pixel_size():
    face = fm.TmpFace(_asset(), _atlas())
    assert face.has("A") and not face.has("B")
    assert face.advance("A", 64.0) == pytest.approx(24.0)    # 12 units at 64 px over a 32 pt face
    assert face.ascent(64.0) == pytest.approx(60.0)


def test_a_tmp_glyph_is_drawn_where_its_bearing_puts_it_and_thresholded():
    face = fm.TmpFace(_asset(), _atlas())
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    face.draw(image, "A", 0.0, 40.0, 64.0, (255, 0, 0, 255))
    # 2 * (bearing X 2, top at bearing Y 10): the 20 px glyph covers x 4..24 and y 20..40
    assert image.getpixel((14, 30))[3] == 255
    assert image.getpixel((14, 30))[:3] == (255, 0, 0)
    assert image.getpixel((1, 1))[3] == 0
    assert image.getpixel((40, 30))[3] == 0


def test_a_tmp_atlas_below_the_edge_draws_nothing():
    face = fm.TmpFace(_asset(), Image.new("L", (32, 32), 100))
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    face.draw(image, "A", 0.0, 40.0, 64.0, (0, 0, 0, 255))
    assert image.getbbox() is None


@pytest.mark.skipif(not (FONT_JSON / "efigs_font.json").is_file(), reason="needs the owner's Brilliant Diamond workspace font")
def test_the_owner_efigs_atlas_draws_a_capital_a():
    asset = json.loads((FONT_JSON / "efigs_font.json").read_text(encoding="utf-8"))
    face = fm.TmpFace(asset, Image.open(FONT_JSON / "efigs_font.png"))
    assert face.has("A")
    image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    face.draw(image, "A", 10.0, 100.0, 72.0, (0, 0, 0, 255))
    assert image.getbbox() is not None
