"""Pokémon X / Y and Omega Ruby / Alpha Sapphire message windows (``plugins/pokemon_gen6/config.json``): the facts
the shared renderer reads, and the rectangle box of the cutscene dialogue. The facts are measured on Azahar frames
(see the ``measured_on`` notes); the tests need no game files."""
from pathlib import Path

from PIL import Image

import plugins.pokemon_gen6 as gen6
from plugins.common import message_window as mw

CONFIG = Path(gen6.__file__).resolve().parent / "config.json"


def test_xy_dialogue_is_the_top_screen_box_with_its_measured_rectangle():
    facts = mw.BoxFacts.load(CONFIG, "dialogue_xy")
    assert facts.font_member == "romfs/a/1/8/5/000.bcfnt"
    assert (facts.screen_width, facts.text_x, facts.first_line_top, facts.box_lines) == (400, 42, 185, 2)
    assert facts.box_rect == (20, 173, 382, 233)
    assert (facts.scale_x, facts.scale_y, facts.line_pitch) == (0.5, 0.6, 19.2)


def test_oras_language_uses_its_own_font_and_dark_ink():
    facts = mw.BoxFacts.load(CONFIG, "language_oras")
    assert facts.font_member == "romfs/a/1/6/7/000.bcfnt"
    assert facts.ink == (16, 16, 16, 255)
    assert facts.box == (248, 248, 248, 255)


def test_oras_dialogue_is_the_top_screen_box_with_dark_text():
    facts = mw.BoxFacts.load(CONFIG, "dialogue_oras")
    assert facts.font_member == "romfs/a/1/6/7/000.bcfnt"
    assert (facts.text_x, facts.first_line_top, facts.box_lines) == (21, 185, 2)
    assert facts.box_rect == (2, 176, 397, 232) and facts.ink == (2, 2, 2, 255)


def test_xy_language_box_covers_the_bottom_screen():
    facts = mw.BoxFacts.load(CONFIG, "language_xy")
    assert facts.box_rect is None and facts.draw_box is True
    assert (facts.text_x, facts.first_line_top) == (16, 47)


def test_box_rectangle_leaves_the_rest_of_the_screen_clear():
    sheet = Image.new("RGBA", (12, 4), (0, 0, 0, 0))
    sheet.paste((255, 255, 255, 255), (0, 0, 3, 4))
    font = mw.BoxFont(sheets=[sheet], cell=(6, 4), grid=(2, 1), cmap={ord("a"): 0}, advances=[3, 5])
    facts = mw.BoxFacts("", 2, 2, 6.0, 0, 1, 400, True, 1.0, 1.0, box_rect=(10, 10, 30, 30))
    img = mw.render_page([("a", "white")], font, facts)
    assert img.getpixel((0, 0))[3] == 0          # outside the rectangle: nothing drawn
    assert img.getpixel((20, 20))[3] > 0          # inside: the box fill
