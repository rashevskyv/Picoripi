"""Tri Force Heroes MSBT control tags, named by the game's own message project.

Catalogue: ``msbp.json`` = ``Common/Message/Alice.msbp`` from ``Archive/EU/RegionBoot.szs``
(``python -m plugins.common.msbp Alice.msbp msbp.json``):
  ``{PlayerName}`` ``{InsertMark:0}``          runtime values -- stay tags
  ``{Color:Name}`` ... ``{Color:Reset}``       palette colour (Name = blue, Attention = red)
  ``{CostumeName:EightBit:No}`` ``{ItemName:...}`` ``{FieldName:...}``   a fixed name from the game's lists
  ``{IntNumberN:0:0:-1:Person}`` ``{ChoiceN:2}`` ``{AutoForward:60}`` ``{Size:130}`` ...
Anything the catalogue cannot reproduce byte for byte stays raw ``{tag:G:T:hex}``.
"""
from __future__ import annotations

import json
from pathlib import Path

from plugins.common.lms_tags import TAG_RE, TagCodec, catalogue_from_msbp  # noqa: F401 - TAG_RE is this module's API

PROJECT = json.loads(Path(__file__).with_name("msbp.json").read_text(encoding="utf-8"))
TAGS, VALUE_NAMES = catalogue_from_msbp(PROJECT)
# The MSBP declares Ruby as (rt: str); the files store the base length first (2 Japanese leftovers use it).
TAGS[(0, 0)] = ("Ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text")

CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
