r"""Menu and option strings of the Silent Hill (PlayStation, USA 1.1) overlays VIN\OPTION.BIN and VIN\SAVELOAD.BIN.

Each string is NUL-terminated at a fixed offset of the USA file, and the file keeps its size, so the
offset is the string's identity: an edited (translated) string stays in its slot. The English text is
also the key the PC port reads from its language pack (``MENU.<text>``); the pack build reads the English
from the source file and the translation from the translation file at the same offset.

Walk/Run Control is left out: its disc bytes carry kerning codes (0x01), which the editor does not show.
The title menu comes from 1ST\BODYPROG.BIN (see doc.py).
"""
from typing import List, Optional, Tuple

OPTION_SIZE = 19968                 # USA VIN\OPTION.BIN
SAVELOAD_SIZE = 20736               # USA VIN\SAVELOAD.BIN

OPTION_LAYOUT: Tuple[Tuple[str, int], ...] = (
    ("On", 1088), ("Off", 1092), ("Stereo", 1480), ("Monaural", 1488), ("Switch", 1036),
    ("Press", 1028), ("Reverse", 1080), ("Normal", 1044), ("Green", 1052), ("Violet", 1060),
    ("Black", 1068), ("Self_View", 1096), ("Exit", 404), ("Brightness_Level", 412),
    ("Controller_Config", 432), ("Screen_Position", 452), ("Vibration", 468), ("Auto_Load", 480),
    ("Sound", 492), ("BGM_Volume", 500), ("SE_Volume", 512), ("Weapon_Control", 224),
    ("Blood_Color", 240), ("View_Control", 252), ("Retreat_Turn", 268), ("Auto_Aiming", 316),
    ("View_Mode", 328), ("Bullet_Adjust", 340),
)

SAVELOAD_LAYOUT: Tuple[Tuple[str, int], ...] = (
    ("Next_fear", 4), ("Child's_room", 16), ("Nowhere", 32), ("Sewer", 40), ("Lighthouse", 48),
    ("Motel", 60), ("Bridge", 68), ("Boat", 76), ("Theme_park", 84), ("Antique_shop", 96),
    ("Pool_hall", 112), ("Jewelry_shop", 124), ("Director's", 140), ("Room_302", 152),
    ("Reception", 164), ("Police", 176), ("Garage", 184), ("Church", 192), ("Gordon", 200),
    ("Doghouse", 208), ("Infirmary", 220), ("Store", 232), ("Bus", 240), ("Cafe", 244),
    ("Anywhere", 252), ("SLOT1", 272), ("SLOT2", 280), ("FILE", 288),
)


def menu_group(data: bytes) -> Optional[Tuple[str, List[int]]]:
    """(label, string starts) when ``data`` is one of the two menu overlays; None otherwise."""
    if len(data) == OPTION_SIZE:
        label, layout = "options", OPTION_LAYOUT
    elif len(data) == SAVELOAD_SIZE:
        label, layout = "save and load", SAVELOAD_LAYOUT
    else:
        return None
    # every slot starts after a NUL (the end of the string before it)
    starts = [offset for _, offset in layout if offset > 0 and data[offset - 1] == 0]
    return label, starts


def pack_key(text: str) -> str:
    """The PC port's pack key of a menu text: ``MENU.`` + the text with '=' written as '-'."""
    return "MENU." + text.replace("=", "-")
