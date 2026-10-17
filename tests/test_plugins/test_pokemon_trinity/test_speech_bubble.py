"""Legends: Z-A boxes from config facts: the speech bubble (measured on an Eden frame) and the HUD message window
(layout-derived). Each becomes one text pane per line of the shared renderer.

The fake face draws a solid block per glyph, so the layout and the render are tested without game files. The real
font test reads the owner's Z-A unpack and skips without it; it checks the ink edges against the Eden frame measurement
(Eden frame, 2026-10-17) within 2 px.
"""
from types import SimpleNamespace

import romhacking_root
import pytest
from PIL import Image, ImageDraw

from plugins.common import flyt_message as fm
from plugins.common import switch_message_preview as mp
from plugins.pokemon_trinity import speech_bubble

ROOT = romhacking_root.under("Pokemon")
ZA_SOURCE = ROOT / "Legends Z-A" / "source" if ROOT else None
HAS_FONT = ZA_SOURCE is not None and (ZA_SOURCE / "ui/font/bin/UniversNextPro-Cond.bfotf").is_file()

# Frame ink boxes of the two bubble lines (frame pixels, inclusive) and the frame mapping of the 1920x1080 canvas.
FRAME_INK = [(504, 620, 111, 133), (496, 604, 145, 162)]
FRAME_ORIGIN = (120, 57)


class SolidFace:
    """A stand-in face: every glyph is a block 0.5 em wide, 0.7 em high above the baseline."""

    def has(self, ch):
        return ch != "?"

    def advance(self, ch, px):
        return px * 0.6

    def ascent(self, px):
        return px * 0.8

    def draw(self, image, ch, pen, baseline, px, colour):
        ImageDraw.Draw(image).rectangle((pen, baseline - px * 0.7, pen + px * 0.5, baseline - 1), fill=colour)


def test_the_bubble_facts_name_two_lines_inside_the_canvas_and_a_wrap_of_the_measured_first_line():
    facts = speech_bubble.load_facts()
    assert len(facts["lines"]) == 2
    x0, y0, x1, y1 = facts["box"]
    assert 0 <= x0 < x1 <= facts["canvas"][0] and 0 <= y0 < y1 <= facts["canvas"][1]
    # the measured first line is 139 px of ink at the measured size: the wrap bound must hold it on one line
    assert facts["wrap_width"] >= 139.0


def test_each_line_gets_one_pane_at_its_measured_baseline():
    facts = speech_bubble.load_facts()
    chain = fm.FontChain([SolidFace()])
    layout = mp.speech_layout(facts, chain)
    assert [pane.name for pane in layout.panes] == ["speech_0", "speech_1"]
    assert layout.window == tuple(float(v) for v in facts["box"])
    ascent = chain.faces[0].ascent(facts["em_y"])
    for pane, line in zip(layout.panes, facts["lines"]):
        assert pane.rect[0] == line["pen_x"]
        assert pane.rect[1] + ascent == pytest.approx(line["baseline_y"])
        assert pane.rect[2] - pane.rect[0] == pytest.approx(facts["wrap_width"])
        assert pane.size == (facts["x_size"], facts["em_y"])


def test_the_render_puts_each_line_of_ink_inside_its_pane_and_crops_to_the_box():
    facts = speech_bubble.load_facts()
    chain = fm.FontChain([SolidFace()])
    layout = mp.speech_layout(facts, chain)
    image = fm.render_window(layout, chain, [["Lumiose"], ["We made"]], background=(0, 0, 0, 0),
                             em_y=facts["em_y"])
    x0, y0, x1, y1 = (round(v) for v in facts["box"])
    assert image.size == (x1 - x0, y1 - y0)
    alpha = image.split()[3]
    for pane in layout.panes:
        top, bottom = round(pane.rect[1]) - y0, round(pane.rect[3]) - y0
        band = alpha.crop((0, max(0, top), image.width, min(image.height, bottom + 1)))
        assert band.getbbox() is not None, f"{pane.name} draws no ink inside its rows"


def test_the_speech_spec_has_no_archive_and_carries_the_facts_and_a_label():
    facts = speech_bubble.load_facts()
    spec = mp.speech_spec(facts)
    assert spec.arc == "" and spec.speech == facts
    assert spec.em_y == facts["em_y"] and spec.label == "Speech bubble"
    assert spec.fonts == ("UniversNextPro-Cond.bfotf",)


def test_the_hud_window_facts_are_the_layout_pane_and_its_own_label():
    spec = speech_bubble.hud_box()
    facts = spec.speech
    assert spec.label == "Message window (HUD)" and spec.em_y == 30.0
    assert facts["box"] == [81.0, 621.0, 417.0, 693.0]
    assert facts["wrap_width"] == facts["box"][2] - facts["box"][0]
    # two lines at the layout's line pitch of 30 px, inside the pane
    first, second = facts["lines"]
    assert second["baseline_y"] - first["baseline_y"] == pytest.approx(30.0)
    assert facts["box"][1] < first["baseline_y"] < second["baseline_y"] < facts["box"][3]


def test_the_box_switch_lists_the_boxes_and_switches_the_spec(qtbot):
    bubble = speech_bubble.speech_box()
    hud = speech_bubble.hud_box()
    # no project folder: the widget only shows its note and never starts a read
    main_window = SimpleNamespace(project_manager=SimpleNamespace(project_dir=None))
    widget = mp.SwitchMessagePreview(main_window, mp.ZA_FIELD_BOX, alternatives=[bubble, hud])
    qtbot.addWidget(widget)
    assert widget._choice.count() == 3
    widget._choice.setCurrentIndex(1)
    assert widget._spec is bubble
    widget._choice.setCurrentIndex(2)
    assert widget._spec is hud


@pytest.mark.skipif(not HAS_FONT, reason="needs the owner's Legends: Z-A unpack (ui/font/bin)")
def test_the_real_font_render_matches_the_eden_frame_ink_within_two_pixels():
    facts = speech_bubble.load_facts()
    spec = mp.speech_spec(facts)
    chain = fm.FontChain([fm.Face.from_bfotf(path.read_bytes())
                          for path in mp.font_files(ZA_SOURCE / spec.font_dir, spec.fonts)])
    layout = mp.speech_layout(facts, chain)
    canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    for pane, text in zip(layout.panes, ["Lumiose City!", "We made it!"]):
        fm.draw_pane_x_stretched(canvas, pane, chain, [text], spec.em_y)
    alpha = canvas.split()[3]
    # map the canvas to the frame grid (1616 x 909 at x 120, y 57) and read the ink of each line back
    frame = Image.new("L", (1920, 1080), 0)
    frame.paste(alpha.resize((1616, 909), Image.BILINEAR), FRAME_ORIGIN)
    for (left, right, top, bottom), (y0, y1) in zip(FRAME_INK, [(104, 138), (138, 172)]):
        x1 = right + 6  # the page arrow sits right of line 2 (x 621 to 627): keep it out of the band
        band = frame.crop((470, y0, x1, y1))
        dark = [(x, y) for x in range(band.width) for y in range(band.height) if band.getpixel((x, y)) >= 128]
        xs = [x + 470 for x, _y in dark]
        ys = [y + y0 for _x, y in dark]
        assert abs(min(xs) - left) <= 2 and abs(max(xs) - right) <= 2
        assert abs(min(ys) - top) <= 2 and abs(max(ys) - bottom) <= 2


@pytest.mark.skipif(not HAS_FONT, reason="needs the owner's Legends: Z-A unpack (ui/font/bin)")
def test_the_worker_read_gives_the_bubble_layout_and_its_font_chain(tmp_path):
    import json

    project = tmp_path / "Legends project"
    project.mkdir()
    (project / "project.uiproj").write_text(json.dumps({"metadata": {"source_path": str(ZA_SOURCE)}}), encoding="utf-8")
    spec = speech_bubble.speech_box()
    out = []
    loader = mp.LayoutLoader(str(project), spec)
    loader.loaded.connect(out.append)
    loader.run()  # the same code the worker thread runs, here on the test thread
    (project_dir, result, loaded_spec), = out
    assert project_dir == str(project) and loaded_spec == spec
    layout, chain = result
    assert [pane.name for pane in layout.panes] == ["speech_0", "speech_1"]
    assert len(chain.faces) == 1 and chain.face_of("L") is not None
