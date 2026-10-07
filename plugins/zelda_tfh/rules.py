"""Tri Force Heroes plugin: the MSBT text of the 3DS game (EU English), its fonts and images with text.

The same engine as A Link Between Worlds: this is ``plugins.zelda_albw.rules.GameRules`` with the game's own
message project (``tags.py``), file roles and dialogue width. ``1_unpack.bat`` writes each archive as a
folder of its members, at the path a LayeredFS mod replaces one member with (``2_build.bat`` repacks it):

- ``romfs/Archive/EU/EUen/LanguageGame.szs/EU/Message/EUen/*.msbt`` -- dialogue, signs, credits (66 files);
- ``romfs/Archive/EU/RegionBoot.szs/EU/Message/EUen/*.msbt`` -- menus, items, costumes, system (34 files);
- ``romfs/Archive/EU/RegionBoot.szs/EU/Font/*.bffnt`` -- the fonts (``font_sources.json``);
- CTPK, layout BFLIM, the boss title cards in ``Telop.ptcl`` and the title logo in ``PictureStory_EU.bch``
  (``texture_sources.json``).

Layout texts (``Layout*`` files) are filled into BFLYT text boxes by the game code; their messages carry no
style, so they get no width limit; neither do the files in ``OWN_BOX``. Dialogue keeps to the message window
(MSBP style ``MsgWindow``); ``{Size:90}`` text is measured at 90 %.
"""
from typing import Any, Dict, Optional

from plugins.zelda_albw.rules import FONT_FILE
from plugins.zelda_albw.rules import GameRules as _AlbwRules

from . import tags
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# Message files shown in their own boxes, not the message window: the opening storybook, the credits, error
# and news screens. They get no width limit.
OWN_BOX = ("Opening", "StaffCredit", "ErrorApplet", "Live")


class GameRules(_AlbwRules):
    """The Legend of Zelda: Tri Force Heroes (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tags = tags
    layout_prefixes = ("Layout", "TrialLayout")
    dialogue_width = 344   # MSBP style MsgWindow: 344 px, 3 lines
    name_files = {"ItemName": ("Items", "Item name"), "MaterialName": ("Items", "Material name"),
                  "CostumeName": ("Items", "Outfit name"), "LocationName": ("Places", "Place name"),
                  "FieldName": ("Places", "Place name")}
    roles = {"ItemName": "Item name", "MaterialName": "Material name", "MaterialNameGet": "Material get message",
             "MaterialNameTalk": "Material name inside a sentence", "MaterialDetail": "Material description",
             "CostumeName": "Outfit name", "CostumeShortName": "Outfit name (short)",
             "CostumeDetail": "Outfit description", "CostumeFunction": "Outfit effect",
             "LocationName": "Place name", "FieldName": "Area name", "StaffCredit": "Staff credits",
             "SystemFlow": "System message", "ErrorApplet": "System message", "Action": "Action button label",
             "GetItem": "Item get message", "ItemExplanation": "Item description"}

    def get_display_name(self) -> str:
        return "Zelda: Tri Force Heroes"

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._message(block_idx, string_idx)
        if found and found["stem"] in OWN_BOX:
            return {"font_file": FONT_FILE}
        return super().get_string_layout(block_idx, string_idx)
