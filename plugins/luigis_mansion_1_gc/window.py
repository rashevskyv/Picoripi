"""The message window of Luigi's Mansion (GameCube), read from main.dol (GLME01 rev 0) and the event scripts.

``fn_800433B4`` draws every message window in a 640x480 layout. The event script picks it: ``<WINDOW>(w)`` the
window, ``<COLOR>(c)`` the speaker, then ``<SPEAK>(n)`` shows message n (0-based record of ``messageNN.csv``).

- Window 2 is E. Gadd's call on the Game Boy Horror: ``m_window5.bti`` (tail on the right) at (19, 353). The other
  windows use ``m_window4.bti`` (tail at the bottom) at (28, 21). Both are 480x120 (``fn_80041DB8`` sets the places).
- The picture is grey ink (I8: alpha = ink, 238 at most), modulated by the speaker colour (table at 0x80305180,
  index c) with vertex alpha 255 at the top and 32 at the bottom.
- Speaker icon ``kawano/dmman/pressed/<name>`` (32x32, table at 0x803054A8, index c - 1 for 1 <= c <= 19) at
  (x + 18, y + 24).
- Text: J2DPrint with ``FX[27] FY[27] SV[28]`` (dialogue font 32 px, ascent 22, scaled by 0.85), first baseline at
  (x + 56, y + 45), a black copy at +2, +2 under it, scissor (x, y + 27, 480, 90). Two lines rest in the window;
  the third baseline (y + 101) is the scroll lane: ``fn_8004225C`` moves the text up 3 px a frame for one line
  (28 px), then drops the top line. 502 font pixels (424 x 32 / 27) reach the scissor edge.

``frame_image`` composes the window as the game draws it; ``speakers`` reads the script.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image, ImageChops

SCREEN = (640, 480)
CALL_WINDOW = 2
PLACE = {CALL_WINDOW: (19, 353)}            # any other window: DEFAULT_PLACE
DEFAULT_PLACE = (28, 21)
PICTURE = {CALL_WINDOW: "m_window5.bti"}    # any other window: m_window4.bti
WINDOW_SIZE = (480, 120)
TOP_ALPHA, BOTTOM_ALPHA = 255, 32
ICON_AT = (18, 24)
TEXT_X, BASELINE_Y, TEXT_W = 56, 45, 424
FONT_Y, LINE_SPACE, ASCENT, CELL = 27, 28, 22, 32
SHADOW = 2
TEXTURE_DIRS = ("files/Game/game_usa.szp/kawano/dmman", "files/Game/game.szp/kawano/dmman")

COLOURS = (   # lbl_80305180, RGB of COLOR(c)
    (185, 40, 187), (110, 160, 212), (240, 200, 16), (108, 225, 95), (166, 86, 255), (215, 0, 0), (20, 35, 232),
    (255, 100, 100), (10, 130, 20), (10, 130, 20), (10, 130, 20), (10, 130, 20), (10, 130, 20), (10, 130, 20),
    (10, 130, 20), (10, 130, 20), (60, 180, 195), (60, 180, 195), (10, 130, 20), (10, 130, 20), (255, 166, 215))
ICONS = (     # lbl_803054A8, icon of COLOR(c) is ICONS[c - 1]
    "hakase_icon", "obake_icon", "luigi_icon", "teresa_icon", "kuppa_icon", "baby_icon", "mario_icon", "mama_icon",
    "uranai_icon", "piano_icon", "baba_icon", "futago_icon", "art_icon", "girl_icon", "situji_icon", "kino_icon",
    "kino_ri", "tubo_icon", "yuki_icon")

TEXT_COLOURS = (   # 0x80339C48, RGB of <COLOR>(n) inside a message; fn_800628AC reads n >= 8 as 0
    (255, 255, 255), (50, 255, 50), (255, 50, 50), (255, 180, 90), (0, 0, 0), (180, 180, 255), (50, 255, 255),
    (255, 255, 0))

_COMMAND = re.compile(r"<(WINDOW|COLOR|SPEAK)>\((\d+)\)")


def speakers(script: str) -> Dict[int, Tuple[int, int]]:
    """Message number -> (window, colour) of its first ``<SPEAK>`` in an event script (text order)."""
    window = colour = 0
    found: Dict[int, Tuple[int, int]] = {}
    for match in _COMMAND.finditer(script):
        value = int(match.group(2))
        if match.group(1) == "WINDOW":
            window = value
        elif match.group(1) == "COLOR":
            colour = value
        else:
            found.setdefault(value, (window, colour))
    return found


def place(window: int) -> Tuple[int, int]:
    return PLACE.get(window, DEFAULT_PLACE)


def geometry(window: int) -> dict:
    """Preview geometry in the 640x480 layout: the text box is the two resting lines, from the first glyph top."""
    x, y = place(window)
    top = BASELINE_Y - ASCENT * FONT_Y / CELL
    return {"screen": list(SCREEN), "box": [x, y, *WINDOW_SIZE], "text": [x + TEXT_X, y + top, TEXT_W, LINE_SPACE * 2],
            "asset_frame": True, "text_metrics": {"font_y": FONT_Y, "line_space": LINE_SPACE, "char_space": 0}}


def _find(roots: Iterable[Path], name: str) -> Optional[Path]:
    return next((root / folder / name for root in roots for folder in TEXTURE_DIRS
                 if (root / folder / name).is_file()), None)


def frame_image(window: int, colour: int, roots: Iterable[Path], read) -> Optional[Image.Image]:
    """The window (and the speaker icon) on a 640x480 RGBA canvas; None when the textures are not under ``roots``.

    ``read(path) -> PIL image`` decodes a .bti file.
    """
    roots = list(roots)
    path = _find(roots, PICTURE.get(window, "m_window4.bti"))
    if path is None:
        return None
    ink = read(path).convert("RGBA").resize(WINDOW_SIZE)
    rgb = COLOURS[colour] if 0 <= colour < len(COLOURS) else (255, 255, 255)
    # TEV: texture x vertex colour; vertex alpha runs from TOP_ALPHA to BOTTOM_ALPHA down the window
    ramp = Image.linear_gradient("L").resize(WINDOW_SIZE)
    ramp = ramp.point(lambda v: round(TOP_ALPHA + (BOTTOM_ALPHA - TOP_ALPHA) * v / 255))
    body = ImageChops.multiply(ink.convert("RGB"), Image.new("RGB", WINDOW_SIZE, rgb)).convert("RGBA")
    body.putalpha(ImageChops.multiply(ink.getchannel("A"), ramp))
    canvas = Image.new("RGBA", SCREEN)
    x, y = place(window)
    canvas.alpha_composite(body, (x, y))
    icon = _find(roots, f"pressed/{ICONS[colour - 1]}.bti") if 1 <= colour <= len(ICONS) else None
    if icon is not None:
        canvas.alpha_composite(read(icon).convert("RGBA"), (x + ICON_AT[0], y + ICON_AT[1]))
    return canvas
