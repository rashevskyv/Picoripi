"""Tomodachi Life and Miitopia plugin (3DS, EU English): MSBT text, Miitopia's fonts and the layout pictures.

Both games are MSBT games with the engine of ``plugins.zelda_albw.rules.GameRules``, which this subclasses with
their tags (Tomodachi Life's message project, ``tags.py``), file roles and no width model. ``1_unpack.bat``
(``zt/mii3ds.py``) writes each archive as a folder of its members at the path a LayeredFS mod replaces one
member with; ``2_build.bat`` rebuilds the archive around the changed members:

- Tomodachi Life: ``romfs/message/<Set>/<Set>_EU_English_LZ.bin/ArcBase/*.msbt`` is the shown text and
  ``.../ArcVoice/*.msbt`` the same messages as the console's text-to-speech voice reads them (one block each);
  ``romfs/layout/*_LZ.bin[.en]/timg/*.bclim`` are the menu pictures (``texture_sources.json``). The text font is
  the console's shared font, not a game file.
- Miitopia: ``romfs/eu/svn_message/EU_English.sarc/**/*.msbt`` (``LayoutMsg/`` holds the interface labels),
  ``romfs/eu/svn_font/EU_English.sarc/*.bffnt`` (``font_sources.json``; the dialogue font is the shared font too)
  and ``romfs/cmn/lyt/*.arc.szs/timg/*.bflim``.

The shared font has no width map here, so messages get no width limit; an unedited file saves byte for byte.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Set

from plugins.zelda_albw.rules import GameRules as _AlbwRules
from utils.logging_utils import log_debug

from . import tags
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

ARCHIVE_SUFFIXES = ("_lz.bin", "_lz.bin.en", ".sarc", ".szs")
VOICE_FOLDER = "ArcVoice"      # Tomodachi Life: what the text-to-speech voice reads
LAYOUT_FOLDER = "LayoutMsg"    # Miitopia: labels filled into layout text boxes
NAME_FILES = {"Food_Name": ("Items", "Food name"), "Equip_Name": ("Items", "Interior / equipment name"),
              "Special_Name": ("Items", "Special item name"), "Tool_Name": ("Items", "Tool name"),
              "Treasure_Name": ("Items", "Treasure name"), "Etc_Name": ("Items", "Item name"),
              "Location": ("Places", "Place name"),
              "dish_name": ("Items", "Dish name"), "weapon": ("Items", "Weapon name"), "armor": ("Items", "Armour name"),
              "enemy": ("Characters", "Monster name"), "npc": ("Characters", "Character name"),
              "stage": ("Places", "Area name"), "world_mii": ("Places", "Place name")}
ROLES = {"Food_Name": "Food name", "Food_Desc": "Food description", "Equip_Name": "Interior / equipment name",
         "Equip_Desc": "Interior / equipment description", "Special_Name": "Special item name",
         "Special_Desc": "Special item description", "Tool_Name": "Tool name", "Tool_Desc": "Tool description",
         "Treasure_Name": "Treasure name", "Treasure_Desc": "Treasure description", "System": "System message",
         "Load": "Save data message", "Location": "Place name", "StaffRoll": "Staff credits",
         "dish_name": "Dish name", "dish_desc": "Dish description", "weapon": "Weapon name", "armor": "Armour name",
         "enemy": "Monster name", "npc": "Character name", "skill": "Skill name", "skillExplain": "Skill description",
         "stage": "Area name", "title": "Title screen / save message", "staff_roll": "Staff credits",
         "common": "System message", "medal": "Medal name and description"}


class GameRules(_AlbwRules):
    """Tomodachi Life and Miitopia (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tags = tags
    layout_prefixes = ()
    name_files = NAME_FILES
    roles = ROLES

    def get_display_name(self) -> str:
        return "Tomodachi Life / Miitopia (3DS)"

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """File, archive folder, label and English text of one message; ``voice`` for a text-to-speech file."""
        rel_path, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        path = Path(rel_path)
        archive = next((part for part in path.parts if part.lower().endswith(ARCHIVE_SUFFIXES)), "")
        return {"path": rel_path, "file": path.name, "stem": path.stem, "archive": archive,
                "label": msbt.labels.get(index, ""), "text": self.tags.to_editor(msbt.messages[index], msbt.little),
                "layout": path.parent.name == LAYOUT_FOLDER, "voice": path.parent.name == VOICE_FOLDER}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        if found["voice"]:
            return {"content_role": "Spoken text: read aloud by the console's text-to-speech voice, not shown "
                                    f"(the shown form is the same message in ArcBase/{found['file']})",
                    "has_speaker": False}
        return super().get_translation_context_for_string(block_idx, string_idx)

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """No width model: the text is drawn with the console's shared font."""
        log_debug("mii_3ds: no width model for the shared font")
        return None

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        return None

    def get_dynamic_name_tags(self) -> dict:
        return {}
