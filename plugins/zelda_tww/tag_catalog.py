"""Wind Waker (GameCube) BMG escape-tag catalogue, from the zeldaret/tww decompilation.

Source: ``include/f_op/f_op_msg_mng.h`` (enum MsgControlCodes) and
``fopMsgM_msgDataProc_c::stringSet`` / ``stringLength`` in ``src/f_op/f_op_msg_mng.cpp``.
Icons are 24x24 ``font_NN.bti`` textures from ``res/Msg/menures.arc``, tinted with
``fopMsgM_buttonW``; arrows, the heart and the starburst take the current text color.

Widths are in font units of ``rock_24_20_4i_usa.bfn`` (cell 24): the game draws the
font at 23 px, so a glyph is ``WID1 x 23/24`` px and an icon, one font size wide, is
24 units.  Runtime values preview as the English text the game itself inserts:
the suffixes (" Rupees", " bombs"...) are hard-coded in the executable, not in BMG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugins.common.escape_catalog import EscapeCatalog, EscapeTagSpec

ICON_TAG_WIDTH = 24
ICON_TEXTURE_DIR = Path(__file__).resolve().parent / "icons"

# color.bmc (CLT1) for ordinary boxes; indices 9-255 are white and never chosen.
COLOR_TABLE = {
    0: None,        # white (default)
    1: "#ff6400",   # red-orange
    2: "#00ff00",   # green
    3: "#7878ff",   # blue
    4: "#ffff3c",   # yellow
    5: "#00ffff",   # cyan
    6: "#ff00ff",   # magenta
    7: "#828282",   # grey
    8: "#ff8000",   # orange
}
COLOR_NAMES = {0: "white", 1: "red", 2: "green", 3: "blue", 4: "yellow",
               5: "cyan", 6: "magenta", 7: "grey", 8: "orange"}

GLYPH = "#c8c8c8"
TEXT = "#ffffff"  # icons tinted with the current text color: white by default


def _icon(kind: str, label: str, color: str, texture: str, *, rot: int = 0,
          flip_y: bool = False) -> dict[str, Any]:
    spec: dict[str, Any] = {"kind": kind, "label": label, "color": color, "fg": "#ffffff",
                            "width": ICON_TAG_WIDTH,
                            "texture": str(ICON_TEXTURE_DIR / texture), "tint": color}
    if rot:
        spec["rot"] = rot
    if flip_y:
        spec["flip_y"] = True
    return spec


_STICK = "font_07_01.png"
_ARROW = "font_10.png"

# (code, name, meaning, render, preview text, icon, arg format)
_GROUP_0 = [
    (0x00, "PLAYER_NAME", "Player name", "dynamic", "Link", None, ""),
    (0x01, "INSTANT_ON", "Show the following text at once instead of typing it", "control", "", None, ""),
    (0x02, "INSTANT_OFF", "Resume typing the text", "control", "", None, ""),
    (0x03, "AUTOCLOSE", "Close the box by itself after a frame count", "control", "", None, "frames16"),
    (0x04, "AUTOCLOSE_NOSKIP", "Close the box by itself after a frame count; cannot be skipped", "control", "", None, "frames16"),
    (0x05, "HANDCLOSE", "Close the box on A/B, or by itself after a frame count", "control", "", None, "frames16"),
    (0x06, "DUMMY", "Ignored by the game", "control", "", None, ""),
    (0x07, "WAIT", "Pause typing for a frame count", "control", "", None, "frames16"),
    (0x08, "SELECT_TWO", "Two-way vertical choice: the next lines are the options", "control", "", None, ""),
    (0x09, "SELECT_THREE", "Three-way vertical choice: the next lines are the options", "control", "", None, ""),
    (0x0A, "A_BUTTON", "GameCube A button", "icon", "", _icon("circle", "A", "#00ffb4", "font_00.png"), ""),
    (0x0B, "B_BUTTON", "GameCube B button", "icon", "", _icon("circle", "B", "#ff3232", "font_01.png"), ""),
    (0x0C, "C_STICK", "GameCube C-stick", "icon", "", _icon("stick", "C", "#ffc832", "font_09.png"), ""),
    (0x0D, "L_BUTTON", "GameCube L trigger", "icon", "", _icon("trigger", "L", GLYPH, "font_04.png"), ""),
    (0x0E, "R_BUTTON", "GameCube R trigger", "icon", "", _icon("trigger", "R", GLYPH, "font_05.png"), ""),
    (0x0F, "X_BUTTON", "GameCube X button", "icon", "", _icon("circle", "X", GLYPH, "font_02.png"), ""),
    (0x10, "Y_BUTTON", "GameCube Y button", "icon", "", _icon("circle", "Y", GLYPH, "font_03.png"), ""),
    (0x11, "Z_BUTTON", "GameCube Z button", "icon", "", _icon("trigger", "Z", "#c896ff", "font_06.png"), ""),
    (0x12, "DPAD", "GameCube D-pad", "icon", "", _icon("dpad", "", GLYPH, "font_08.png"), ""),
    (0x13, "MAIN_STICK", "Control Stick", "icon", "", _icon("stick", "", GLYPH, _STICK), ""),
    (0x14, "ARROW_LEFT", "Left arrow", "icon", "", _icon("char", "◄", TEXT, _ARROW, rot=90), ""),
    (0x15, "ARROW_RIGHT", "Right arrow", "icon", "", _icon("char", "►", TEXT, _ARROW, rot=270), ""),
    (0x16, "ARROW_UP", "Up arrow", "icon", "", _icon("char", "▲", TEXT, _ARROW, flip_y=True), ""),
    (0x17, "ARROW_DOWN", "Down arrow", "icon", "", _icon("char", "▼", TEXT, _ARROW), ""),
    (0x18, "MAIN_STICK_UP", "Control Stick up", "icon", "", _icon("stick_direction", "↑", GLYPH, _STICK), ""),
    (0x19, "MAIN_STICK_DOWN", "Control Stick down", "icon", "", _icon("stick_direction", "↓", GLYPH, _STICK), ""),
    (0x1A, "MAIN_STICK_LEFT", "Control Stick left", "icon", "", _icon("stick_direction", "←", GLYPH, _STICK), ""),
    (0x1B, "MAIN_STICK_RIGHT", "Control Stick right", "icon", "", _icon("stick_direction", "→", GLYPH, _STICK), ""),
    (0x1C, "MAIN_STICK_UP_DOWN", "Control Stick up and down", "icon", "", _icon("stick_direction", "↕", GLYPH, _STICK), ""),
    (0x1D, "MAIN_STICK_LEFT_RIGHT", "Control Stick left and right", "icon", "", _icon("stick_direction", "↔", GLYPH, _STICK), ""),
    # The horizontal choice reserves one icon cell for the cursor arrow.
    (0x1E, "SELECT_YOKO_LEFT", "Horizontal choice: left option", "control", "",
     _icon("char", "►", "#ff5050", _ARROW, rot=270), ""),
    (0x1F, "SELECT_YOKO_RIGHT", "Horizontal choice: right option", "control", "",
     _icon("char", "►", "#ff5050", _ARROW, rot=270), ""),
    (0x20, "CANNON_HITS", "Cannon-game hit count", "dynamic", "5", None, ""),
    (0x21, "VASE_PAYMENT", "Rupees owed for a broken vase", "dynamic", "20 Rupees", None, ""),
    (0x22, "AUCTION_CHARACTER", "Name of an auction bidder", "dynamic", "⟨bidder name⟩", None, ""),
    (0x23, "AUCTION_ITEM", "Name of the auctioned item", "dynamic", "⟨item name⟩", None, ""),
    (0x24, "AUCTION_BID", "Current auction bid", "dynamic", "100 Rupees", None, ""),
    (0x25, "AUCTION_START_BID", "Starting auction bid", "dynamic", "100 Rupees", None, ""),
    (0x26, "BID_INPUT", "Three-digit bid input", "dynamic", "000 Rupees", None, ""),
    (0x27, "FLASHING_A_BUTTON", "Flashing A button", "icon", "", _icon("circle", "A", "#00ffb4", "font_12.png"), ""),
    (0x28, "ORCA_BLOWS", "Hits landed on Orca", "dynamic", "100 blows", None, ""),
    (0x29, "PIRATE_PASSWORD", "Pirate ship password (a message of its own)", "dynamic", "Plankton", None, ""),
    (0x2A, "STARBURST", "Starburst targeting icon", "icon", "", _icon("reticle", "", TEXT, "font_15.png"), ""),
    (0x2B, "LETTER_GAME_COUNT", "Letters sorted in the post-office game", "dynamic", "25", None, ""),
    (0x2C, "LETTER_GAME_REWARD", "Post-office game reward", "dynamic", "50 Rupees", None, ""),
    (0x2D, "POSTBOX_LETTERS", "Letters waiting in the postbox", "dynamic", "2 letters", None, ""),
    (0x2E, "KOROKS_LEFT", "Koroks still to find", "dynamic", "5", None, ""),
    (0x2F, "FOREST_WATER_TIME", "Forest Water time left", "dynamic", "19:59", None, ""),
    (0x30, "FLIGHT_DISTANCE", "Flight Control Platform distance", "dynamic", "100 yards", None, ""),
    (0x31, "FLIGHT_RECORD", "Flight Control Platform record", "dynamic", "100 yards", None, ""),
    (0x32, "BEEDLE_POINTS", "Beedle's shop points", "dynamic", "100 points", None, ""),
    (0x33, "JOY_PENDANTS_OWNED", "Joy Pendants owned", "dynamic", "20", None, ""),
    (0x34, "JOY_PENDANTS_GIVEN", "Joy Pendants given to Mrs. Marie", "dynamic", "20", None, ""),
    (0x35, "PIG_GAME_TIME", "Pig-catching time", "dynamic", "1:30", None, ""),
    (0x36, "SAILING_REWARD", "Sailing-game reward", "dynamic", "50 Rupees", None, ""),
    (0x37, "BOMB_CAPACITY", "Bomb capacity", "dynamic", "60 bombs", None, ""),
    (0x38, "ARROW_CAPACITY", "Arrow capacity", "dynamic", "99 arrows", None, ""),
    (0x39, "HEART", "Heart icon", "icon", "", _icon("char", "♥", TEXT, "font_13.png"), ""),
    (0x3A, "MUSIC_NOTE", "Music note icon", "icon", "", _icon("char", "♪", "#ffffff", "font_14.png"), ""),
    (0x3B, "LETTER_GAME_RECORD", "Post-office game record", "dynamic", "25", None, ""),
    (0x3C, "FISHMAN_HITS", "Fishman game hit count", "dynamic", "10", None, ""),
    (0x3D, "FISHMAN_REWARD", "Fishman game reward", "dynamic", "100 Rupees", None, ""),
    (0x3E, "SELL_BOKO_SEEDS", "Boko Baba Seeds to sell", "dynamic", "10 seeds", None, ""),
    (0x3F, "SELL_SKULL_NECKLACES", "Skull Necklaces to sell", "dynamic", "10 necklaces", None, ""),
    (0x40, "SELL_CHU_JELLY", "Chu Jelly to sell", "dynamic", "10", None, ""),
    (0x41, "SELL_JOY_PENDANTS", "Joy Pendants to sell", "dynamic", "10 necklaces", None, ""),
    (0x42, "SELL_GOLDEN_FEATHERS", "Golden Feathers to sell", "dynamic", "10 feathers", None, ""),
    (0x43, "SELL_KNIGHTS_CRESTS", "Knight's Crests to sell", "dynamic", "10 crests", None, ""),
    (0x44, "BEEDLE_OFFER", "Rupees Beedle offers", "dynamic", "100 Rupees", None, ""),
    (0x45, "INPUT_BOKO_SEEDS", "Two-digit input: Boko Baba Seeds", "dynamic", "00 seeds", None, ""),
    (0x46, "INPUT_SKULL_NECKLACES", "Two-digit input: Skull Necklaces", "dynamic", "00 necklaces", None, ""),
    (0x47, "INPUT_CHU_JELLY", "Two-digit input: Chu Jelly", "dynamic", "00", None, ""),
    (0x48, "INPUT_JOY_PENDANTS", "Two-digit input: Joy Pendants", "dynamic", "00 pendants", None, ""),
    (0x49, "INPUT_GOLDEN_FEATHERS", "Two-digit input: Golden Feathers", "dynamic", "00 feathers", None, ""),
    (0x4A, "INPUT_KNIGHTS_CRESTS", "Two-digit input: Knight's Crests", "dynamic", "00 crests", None, ""),
]

ESCAPE_TAGS: dict[tuple[int, int], EscapeTagSpec] = {
    (0, code): EscapeTagSpec(0, code, name, meaning, render, preview, icon, arg)
    for code, name, meaning, render, preview, icon, arg in _GROUP_0
}
ESCAPE_TAGS[(255, 0)] = EscapeTagSpec(255, 0, "COLOR", "Change text color", "color", arg="color8")
ESCAPE_TAGS[(255, 1)] = EscapeTagSpec(
    255, 1, "SCALE", "Change text size; above 100% a line takes two line slots", "scale", arg="scale16")
ESCAPE_TAGS[(255, 2)] = EscapeTagSpec(
    255, 2, "RUBY", "Furigana; ignored by the US and European games", "ruby", arg="ruby")

WW_CATALOG = EscapeCatalog(
    ESCAPE_TAGS,
    color_names=COLOR_NAMES,
    group_fallbacks={
        1: ("SOUND_{code}", "Play message sound effect {code} at the speaker", "sound"),
        2: ("CAMERA_{code}", "Talk camera {code}; 1-10 focus a speaker slot, often a change of speaker", "camera"),
        3: ("ANIMATION_{code}", "Speaking NPC animation or expression {code}", "anim"),
    },
    controller_groups={
        0: ("GC", {
            "A_BUTTON": "A", "B_BUTTON": "B", "L_BUTTON": "L", "R_BUTTON": "R",
            "X_BUTTON": "X", "Y_BUTTON": "Y", "Z_BUTTON": "Z", "C_STICK": "C-stick", "DPAD": "D-pad", "MAIN_STICK": "stick",
            "MAIN_STICK_UP": "stick ↑", "MAIN_STICK_DOWN": "stick ↓",
            "MAIN_STICK_LEFT": "stick ←", "MAIN_STICK_RIGHT": "stick →",
            "MAIN_STICK_UP_DOWN": "stick ↕", "MAIN_STICK_LEFT_RIGHT": "stick ↔",
            "FLASHING_A_BUTTON": "A★",
        }, False),
    },
    name_aliases={"PLAYER_NAME": "{F:Link}"},
    icon_width=ICON_TAG_WIDTH,
)
