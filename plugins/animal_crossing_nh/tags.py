"""Animal Crossing: New Horizons MSBT control tags: the catalogue in ``tags.json`` and the editor codec.

The game's ``Message/App.msbp`` names only the text colours, not the tags, so ``tags.json`` was built from the
text itself: for every tag (group, type) the US English messages use, the first argument layout that reads and
writes back every use byte for byte. Names are the group's role as seen in the text plus the type number:
``System`` (Ruby, Font, Size, Color, PageBreak), ``Speech`` (pauses, speed and cues inside dialogue), ``Motion``
(character animation), ``Var`` / ``VarSp`` (inserted names: player, island, villagers, items), ``Item`` (an item
or word in its article / gender / plural form: ``{Item7:He:She}``, ``{Item8:0:items:item:items}``), ``Choice``,
``Number``, ``Emotion``, ``Player``, ``Name``, ``Word`` and so on. Colours show by their App.msbp names
(``{Color:Npc}`` ... ``{Color:Reset}``). Two rare tags with mixed layouts stay raw (``{tag:60:21:hex}``).
"""
import json
from pathlib import Path

from plugins.common.lms_tags import COLOR_RESET, TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

_DATA = json.loads(Path(__file__).with_name("tags.json").read_text(encoding="utf-8"))
TAGS = {(t["group"], t["type"]): (t["name"], tuple(t["args"]),
                                  f"{_DATA['groups'].get(str(t['group']), 'Group ' + str(t['group']))} tag {t['type']}"
                                  + (f" ({', '.join(t['args'])})" if t["args"] else ""))
        for t in _DATA["tags"]}
VALUE_NAMES = {("Color", 0): {**dict(enumerate(_DATA["colors"])), COLOR_RESET: "Reset"}}
CODEC = TagCodec(TAGS, VALUE_NAMES)
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
parse_tag = CODEC.parse_tag
