"""Wind Waker HD message attributes (MSBT ATR1): who speaks, which box, which item, the next message.

Lists and attribute layout come from the game's ``CKing.msbp`` (ATI2/ALI2): every message of
``message*.msbt`` has 23 attribute bytes -- CharacterName (list), BalloonType (list), DisplayStyle,
BalloonPlacement, Price (s16), NextNo (u16), Item, LineAlignment, SE, Camera, DemoID (s16), Animation and
two comment string offsets. Labels of those files are the GameCube message ids ("00102" = 0x0066).

Box widths: the talk box text pane is 700 px (``MsgWindowMain_00.bflyt``), the narrow ones 650 px
(``MsgWindowEvent_00`` / ``MsgWindowScroll_00``); both draw CKingMsg at 0.8 (36.8 / 46 px), so a line
holds 875 or 812 font units. Four 43.2 px lines fit the 180 px pane. The English text keeps to it: its
99th percentile is 841 units in talk boxes and 811 in signs, item and caption boxes.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Dict, Optional

CHARACTER_NAMES = (
    "- GBAWarnings Grandma Aryll PotGirl Masao-GrassCutter- Sturgeon Orca Abrill-Uncle- Rose-Aunt- Kid1-Joel- "
    "Kid2-Zill- GettingItems Narration RedLionKing-Boat- Sign ItemName PirateCharm Senzar-Pirate- Tetra "
    "ItemExplanation Door Options OptionExplanation PirateCharm-Boat- Gonzo-Pirate- Nudge-Pirate- "
    "Loot-Moneygame- SalvageCorp Zuko-Pirate- Niko-Pirate- Mako-Pirate- Beedle-Shop- Postman-Quill- DekuTree "
    "Makar-Korog- Linder Irch Elma Olivio Oakin Aldo Rown Drona Hollo Pictograph Tingle PoorMaggie-sDad "
    "RichMina-sDad Salvatore-Mini-Game1- PoorMina AuctionEvent WindWakerControls DocBantum-PotionShop- "
    "JoyPedestal RichMaggie-sDad RichMaggie Hilari-TauraPostman- Totou KillerBees Postbox Mrs-Marie CabanaDoor "
    "GCNWarnings Cannon-BombShop- GBAconnection Zunari-Auctioneer- Zunari-StallMerchant- GeneralMessage "
    "PoorMina-sFather Jabun AllPirates Password RitoChieftain Medli-Rito- Komali-Rito- Namali-Rito- "
    "Bashid-Rito- Kamoli-Rito- Zephos ZephosTablet CyclosTablet TravelingMerchantA TravelingMerchantB "
    "TravelingMerchantC Valoo Ganon KingofHyrule Zelda-Tetra- PearlStatue SageRaluto SageFodo Poster "
    "SortingRito Edmund Letter GenzoPictographer HilariRitoC Bishid-Rito- Hoskit-Rito- Sket-Rito- Gakoot-Rito- "
    "TowerofGodsBoss Korog-All- Cyclos SuperFairy-Queen- GreatFairy BirdmanContest1 BirdmanContest2 DungeonName "
    "WarpMessage Sam Gossack Garrickson HiddenBeedle Vera-Poppins Misae Minenco Lillian Linda Keebo Anton Loot "
    "Gamma Kenya Candy Danp MapScreen Salvatore-Mini-Game2- StoneStatue Fish Kameo Goose Joiner-Potof "
    "Pashli-Rito- TrophyMaker NintendoFreak Mr-HoHo CabanaSign Figurine FigurineExplanation Ganon-sTowerSign "
    "StoneTablet"
).split()
BALLOON_TYPES = ("Text Narration Sign-Wood NoBorder-BlackLetters NoBorder-WhiteLetters Subtitle Sign-Stone "
                 "Sign-Paper Telescope GettingItems Text-Centered QuestStatusScreen Text-Hylian Pictograph "
                 "WindWaker").split()
ATTRIBUTE_SIZE = 23

# CharacterName values that are not a character: (content role, glossary section).
NOT_SPEAKERS: Dict[str, tuple] = {
    "-": ("Message", None), "GBAWarnings": ("System notice", None), "GCNWarnings": ("System notice", None),
    "GBAconnection": ("Tingle Bottle and Tingle Tuner notice", None),
    "GettingItems": ("Item get message: the item's name and what it does", None),
    "Narration": ("Opening narration caption", None), "Sign": ("Text of a sign", None),
    "ItemName": ("Item name in the inventory", "Items"), "ItemExplanation": ("Item description in the inventory", None),
    "Door": ("Door notice", None), "Options": ("Menu entry", None), "OptionExplanation": ("Menu help text", None),
    "Pictograph": ("Picto Box notice", None), "AuctionEvent": ("Auction notice", None),
    "WindWakerControls": ("Wind Waker song notice", None), "JoyPedestal": ("Pedestal notice", None),
    "Postbox": ("Postbox notice", None), "CabanaDoor": ("Door notice", None),
    "GeneralMessage": ("Narration or notice", None), "Password": ("Password prompt", None),
    "ZephosTablet": ("Stone tablet text", None), "CyclosTablet": ("Stone tablet text", None),
    "PearlStatue": ("Statue notice", None), "Poster": ("Poster text", None), "Letter": ("Letter", None),
    "DungeonName": ("Dungeon name", "Places"), "WarpMessage": ("Warp prompt", None),
    "MapScreen": ("Sea chart text", None), "StoneStatue": ("Statue notice", None),
    "CabanaSign": ("Text of a sign", None), "Figurine": ("Nintendo Gallery figurine description", None),
    "FigurineExplanation": ("Nintendo Gallery figurine description", None),
    "Ganon-sTowerSign": ("Text of a sign", None), "StoneTablet": ("Stone tablet text", None),
}

# CharacterName -> the name the English game uses, where the MSBP label is a working title.
_DISPLAY = {
    "Masao-GrassCutter-": "Mesa", "Abrill-Uncle-": "Abe", "Kid1-Joel-": "Joel", "Kid2-Zill-": "Zill",
    "RedLionKing-Boat-": "King of Red Lions", "PirateCharm": "Tetra (Pirate's Charm)",
    "PirateCharm-Boat-": "Tetra (Pirate's Charm)", "Senzar-Pirate-": "Senza", "DekuTree": "Great Deku Tree",
    "PoorMaggie-sDad": "Maggie's Father", "RichMina-sDad": "Mila's Father", "PoorMina": "Mila",
    "PoorMina-sFather": "Mila's Father", "RichMaggie-sDad": "Maggie's Father", "RichMaggie": "Maggie",
    "Salvatore-Mini-Game1-": "Salvatore", "Salvatore-Mini-Game2-": "Salvatore", "DocBantum-PotionShop-": "Doc Bandam",
    "Mrs-Marie": "Mrs. Marie", "Zunari-Auctioneer-": "Zunari", "Zunari-StallMerchant-": "Zunari",
    "AllPirates": "Pirates", "RitoChieftain": "Rito Chieftain", "KingofHyrule": "King of Hyrule",
    "Zelda-Tetra-": "Princess Zelda", "SageRaluto": "Laruto", "SageFodo": "Fado", "SortingRito": "Koboli",
    "GenzoPictographer": "Lenzo", "TowerofGodsBoss": "Gohdan", "Korog-All-": "Koroks",
    "SuperFairy-Queen-": "Queen of Fairies", "GreatFairy": "Great Fairy", "HiddenBeedle": "Beedle", "Fish": "Fishman",
    "TrophyMaker": "Carlov", "Mr-HoHo": "Old Man Ho Ho", "TravelingMerchantA": "Traveling Merchant",
    "TravelingMerchantB": "Traveling Merchant", "TravelingMerchantC": "Traveling Merchant", "PotGirl": "Sue-Belle",
}


def speaker_name(label: str) -> Optional[str]:
    """The display name of a CharacterName value; None when it is not a character."""
    if label in NOT_SPEAKERS:
        return None
    if label in _DISPLAY:
        return _DISPLAY[label]
    name = re.sub(r"-([A-Za-z0-9]+)-$", "", label)          # "Medli-Rito-" -> "Medli"
    name = name.replace("-s", "'s")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)          # "TowerofGods" stays; "GreatFairy" -> "Great Fairy"


def attributes(atr1: bytes, index: int) -> Optional[Dict[str, Any]]:
    """The attributes of message ``index`` from an ATR1 section body; None when it has none."""
    if len(atr1) < 8:
        return None
    count, size = struct.unpack_from(">II", atr1, 0)
    if size != ATTRIBUTE_SIZE or not 0 <= index < count:
        return None
    raw = atr1[8 + index * size:8 + (index + 1) * size]
    character, balloon = raw[0], raw[1]
    return {
        "character": CHARACTER_NAMES[character] if character < len(CHARACTER_NAMES) else str(character),
        "balloon": BALLOON_TYPES[balloon] if balloon < len(BALLOON_TYPES) else str(balloon),
        "price": struct.unpack_from(">h", raw, 4)[0],
        "next": struct.unpack_from(">H", raw, 6)[0],
        "item": raw[8],
    }


# BalloonType -> line width in CKingMsg font units (700 px or 650 px panes at scale 0.8).
WIDE_BOX = 875
NARROW_BOX = 812
_WIDE = {"Text", "Text-Centered", "QuestStatusScreen", "Pictograph", "NoBorder-BlackLetters", "NoBorder-WhiteLetters"}
LINES_PER_PAGE = 4


def box_width(balloon: str) -> int:
    return WIDE_BOX if balloon in _WIDE else NARROW_BOX
