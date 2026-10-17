"""The BDSP dialogue preview: the measured facts, and the efigs TMP face drawn at them (real font when on disk)."""
import json

import pytest
import romhacking_root
from PIL import Image

from plugins.common import flyt_message as fm
from plugins.pokemon_bdsp import dialogue_preview as dp

FONT = romhacking_root.under("Pokemon") / "Brilliant Diamond and Shining Pearl" / "source" / "font" / "efigs_font"


def _tiny_face():
    asset = {
        "m_FaceInfo": {"m_PointSize": 32, "m_Scale": 1.0, "m_LineHeight": 40.0, "m_AscentLine": 30.0},
        "m_GlyphTable": [{"m_Index": 1,
                          "m_Metrics": {"m_Width": 10.0, "m_Height": 10.0, "m_HorizontalBearingX": 0.0,
                                        "m_HorizontalBearingY": 10.0, "m_HorizontalAdvance": 12.0},
                          "m_GlyphRect": {"m_X": 5, "m_Y": 5, "m_Width": 10, "m_Height": 10},
                          "m_Scale": 1.0, "m_AtlasIndex": 0}],
        "m_CharacterTable": [{"m_Unicode": 65, "m_GlyphIndex": 1, "m_Scale": 1.0}],
        "m_AtlasPadding": 0,
    }
    atlas = Image.new("L", (32, 32), 0)
    atlas.paste(255, (5, 17, 15, 27))
    return fm.TmpFace(asset, atlas)


def test_the_measured_facts_are_stored():
    facts = dp.load_facts()
    assert facts["px"] == 45.5
    assert facts["pen_x"] == 485.5
    assert facts["baseline_y"] == 855.0


def test_a_character_the_font_lacks_is_reported_not_drawn():
    image, missing = dp.render_line(_tiny_face(), "AB", dp.load_facts())
    assert missing == ["B"]
    assert image.size == dp.CANVAS


@pytest.mark.skipif(not (FONT / "efigs_font.json").exists(), reason="the BDSP workspace is not on disk")
def test_the_real_n_glyph_is_35_px_high_at_the_measured_size():
    asset = json.loads((FONT / "efigs_font.json").read_text(encoding="utf-8"))
    face = fm.TmpFace(asset, Image.open(FONT / "efigs_font.png"))
    image, missing = dp.render_line(face, "N", dp.load_facts(), background=(0, 0, 0, 0))
    left, top, right, bottom = image.getchannel("A").point(lambda v: 255 if v >= 128 else 0).getbbox()
    assert missing == []
    assert bottom - top == 35          # the frame's N: rows 821 to 855, 35 rows
    # The canvas origin is y 800: the render's N is rows 20 to 54 (the frame's rows 21 to 55). 1 px high on the frame.
    assert (top, bottom) == (20, 55)
