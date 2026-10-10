"""MSBT control tags of the two 3DS Animal Crossing games: one catalogue per game and a codec for each.

The games' project files (``Script/CTR_GardenPlus.msbp``, ``Script/CTR_Takumi.msbp``) name only the text colours,
so each catalogue (``tags_new_leaf.json``, ``tags_happy_home.json``) was built from the English text itself: for
every tag (group, type) a game uses, the first argument layout that reads and writes back every use byte for byte,
and a name and description from what the tag does in the text (``{playerName}``, ``{catchphrase}``,
``{delay:8}``, ``{menu0:0:0}`` ...). New Leaf's names are then laid over by the public New Leaf config of
AeonSake's MSBT Editor (``ACNL.gcf``, gitlab.com/AeonSake/msbt-editor, GPL-3.0; read by ``plugins.common.gcf``):
``ruby``, ``size``, ``color``, ``pageBreak``, ``anim<N>``, ``delay``, ``wordInfo``. The argument layouts stay the
verified ones (the config gives ``delay`` a u16; every real one is 4 bytes).

Old names still read (``{G5_7}``, ``{Color:NPC}``, ``{PageBreak}``): text saved before the names changed loads.
The same (group, type) often has different arguments in the two games, which is why the catalogues are separate;
``rules.py`` picks, per file, the codec that names more of its tags. Colours show by the project files' names
(``{color:NPC}`` ... ``{color:Reset}``).
"""
import json
from pathlib import Path
from typing import Dict, Tuple

from plugins.common import gcf
from plugins.common.lms_tags import COLOR_RESET, TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

_HERE = Path(__file__).parent


def _codec(name: str, config: str = "") -> TagCodec:
    data = json.loads((_HERE / name).read_text(encoding="utf-8"))
    tags = {}
    aliases: Dict[str, Tuple[int, int]] = {}
    for t in data["tags"]:
        key = (t["group"], t["type"])
        group = data["groups"].get(str(t["group"]), f"Group {t['group']}")
        args = f" ({', '.join(t['args'])})" if t["args"] else ""
        tags[key] = (t.get("name") or f"G{key[0]}_{key[1]}", tuple(t["args"]),
                     f"{group}: {t.get('desc') or 'tag ' + str(t['type'])}{args}")
        aliases[f"G{key[0]}_{key[1]}"] = key
    for old, key in (("Ruby", (0, 0)), ("Font", (0, 1)), ("Size", (0, 2)), ("Color", (0, 3)), ("PageBreak", (0, 4))):
        aliases[old] = key
    names = {(tags[(0, 3)][0], 0): {**dict(enumerate(data["colors"])), COLOR_RESET: "Reset"}}
    if config:
        tags, names, renamed = gcf.overlay(tags, names, gcf.load(_HERE / config))
        aliases.update(renamed)
    return TagCodec(tags, names, {old: key for old, key in aliases.items() if key in tags})


CODECS = {"new_leaf": _codec("tags_new_leaf.json", "ACNL.gcf"), "happy_home": _codec("tags_happy_home.json")}
CODEC = CODECS["new_leaf"]
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
parse_tag = CODEC.parse_tag
