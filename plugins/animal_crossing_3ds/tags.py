"""MSBT control tags of the two 3DS Animal Crossing games: one catalogue per game and a codec for each.

The games' project files (``Script/CTR_GardenPlus.msbp``, ``Script/CTR_Takumi.msbp``) name only the text colours,
so each catalogue was built from the English text itself: for every tag (group, type) a game uses, the first
argument layout that reads and writes back every use byte for byte. Only the System group (0) has standard LMS
names (``Ruby``, ``Font``, ``Size``, ``Color``, ``PageBreak``); every other tag is ``G<group>_<type>`` with its
arguments, so a translator sees ``{G5_0:3:0}`` and keeps it. The same (group, type) often has different arguments
in the two games (New Leaf ``{G5_0}`` has none, Happy Home Designer's has two u16), which is why the catalogues
are separate; ``rules.py`` picks, per file, the codec that names more of its tags. Colours show by the project
files' names (``{Color:NPC}`` ... ``{Color:Reset}``).
"""
import json
from pathlib import Path

from plugins.common.lms_tags import COLOR_RESET, TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API


def _codec(name: str) -> TagCodec:
    data = json.loads(Path(__file__).with_name(name).read_text(encoding="utf-8"))
    tags = {(t["group"], t["type"]): (t["name"], tuple(t["args"]),
                                      f"{data['groups'].get(str(t['group']), 'Group ' + str(t['group']))} tag {t['type']}"
                                      + (f" ({', '.join(t['args'])})" if t["args"] else ""))
            for t in data["tags"]}
    value_names = {("Color", 0): {**dict(enumerate(data["colors"])), COLOR_RESET: "Reset"}}
    return TagCodec(tags, value_names)


CODECS = {"new_leaf": _codec("tags_new_leaf.json"), "happy_home": _codec("tags_happy_home.json")}
CODEC = CODECS["new_leaf"]
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
parse_tag = CODEC.parse_tag
