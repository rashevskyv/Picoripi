"""A Link Between Worlds MSBT control tags, named by the game's own message project.

Catalogue: ``msbp.json`` = ``World/Message/CTRJack.msbp`` from ``EU/RegionBoot.szs``
(``python -m plugins.common.msbp CTRJack.msbp msbp.json``): every tag by its MSBP name, list parameters by
their item names, Color by the palette's names:
  ``{PlayerName}``                       Link's (save file) name -- stays a tag (user decision)
  ``{Color:Name}`` ... ``{Color:Reset}``  palette colour (Name = blue, Attention = red, YugaTalking)
  ``{ItemName:hammer:Yes:No}``   an ItemName.msbt entry (Which, Coloring, ToUpper)
  ``{Wait:30}`` ``{ChoiceN:2}`` ``{IntNumberN:2:0:-1:None}`` ``{Size:150}`` ...
Anything the catalogue cannot reproduce byte for byte stays raw ``{tag:G:T:hex}``.
"""
from __future__ import annotations

import json
from pathlib import Path

from plugins.common.lms_tags import TAG_RE, TagCodec, catalogue_from_msbp  # noqa: F401 - TAG_RE is this module's API

PROJECT = json.loads(Path(__file__).with_name("msbp.json").read_text(encoding="utf-8"))
TAGS, VALUE_NAMES = catalogue_from_msbp(PROJECT)

CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
