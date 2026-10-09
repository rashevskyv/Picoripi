"""Tomodachi Life / Miitopia MSBT control tags, named by Tomodachi Life's own message project.

Catalogue: ``msbp.json`` = ``Game.msbp`` from ``romfs/message/Game/Game_EU_English_LZ.bin`` (every Tomodachi Life
message project declares the same tag groups, or only its ``System`` group; ``python -m plugins.common.msbp``):
  ``{PageBreak}`` ``{Size:90}`` ``{Color:0:0:0:255}``                      System (the same group in Miitopia's files)
  ``{Nickname:...}`` ``{Firstname:...}`` ``{Speaker:...}`` ``{Lovers:...}``  a Mii's name or role, inserted at run time
  ``{Food:0:Name:Singular}`` ``{Treasure:...}`` ``{Island:...}``          item, place and player references
  ``{SingularPluralFood:0:Plural:is:are}`` ``{GenderItem:...}``           a word that follows the item's number / gender
  ``{Def}`` ``{Indef}`` ``{InitialCap}`` ``{Elision:...}``                 articles and grammar helpers
  ``{CS_Rate:...}`` ``{CS_Pause:...}`` ``{Preset:...}`` ``{Echo:...}``     text-to-speech controls (ArcVoice files)
Anything the catalogue cannot reproduce byte for byte stays raw ``{tag:G:T:hex}`` (Miitopia's own tags do).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from plugins.common.lms_tags import TAG_RE, TagCodec, catalogue_from_msbp  # noqa: F401 - TAG_RE is this module's API

PROJECT = json.loads(Path(__file__).with_name("msbp.json").read_text(encoding="utf-8"))


def _unique_names(project: dict) -> dict:
    """The project with every tag name unique: Item, Food, Body... exist in four groups (Reference, Gender,
    SingularPlural, GenderSingularPlural); a repeat gets its group's name in front (``SingularPluralFood``)."""
    renamed = copy.deepcopy(project)
    seen = set()
    for group in renamed["tag_groups"]:
        for tag in group["tags"]:
            if tag["name"] in seen:
                tag["name"] = group["name"] + tag["name"]
            seen.add(tag["name"])
    return renamed


TAGS, VALUE_NAMES = catalogue_from_msbp(_unique_names(PROJECT))
# The files store Color as four bytes (red, green, blue, alpha), not a palette index.
TAGS[(0, 3)] = ("Color", ("u8", "u8", "u8", "u8"), "Text colour: red, green, blue, alpha (0-255)")
VALUE_NAMES.pop(("Color", 0), None)

CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
