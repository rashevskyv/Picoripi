"""Paper Mario: Color Splash MSBT control tags, named from the game's own project file ``messages/gojika.msbp``.

``gojika_msbp.json`` is that file read by ``python -m plugins.common.msbp`` (tag groups System, control,
layout, option, scroll, sound, text, window, chr; their tags and parameter types). A tag shows as
``{name:arg:arg}`` (``{Color:255:0:0:255:Red}``, ``{icon:BtnA:0:0:0:0}``, ``{wait:30}``) only when that form
encodes back to the same bytes; anything else stays ``{tag:G:T:hex}``, so a file always round-trips.
A list parameter (``align``, ``DJB``) is one byte: its item names come from the project file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

_PROJECT = json.loads(Path(__file__).with_name("gojika_msbp.json").read_text(encoding="utf-8"))
_TYPES = {"list": "u8"}

TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {}
VALUE_NAMES: Dict[Tuple[str, int], Dict[int, str]] = {}
for _group in _PROJECT["tag_groups"]:
    for _index, _tag in enumerate(_group["tags"]):
        _params = _tag["params"]
        TAGS[(_group["id"], _index)] = (
            _tag["name"], tuple(_TYPES.get(p["type"], p["type"]) for p in _params),
            f"{_group['name']} tag '{_tag['name']}'" + (f" ({', '.join(p['name'] for p in _params)})" if _params else ""))
        for _arg, _param in enumerate(_params):
            if _param["type"] == "list":
                VALUE_NAMES[(_tag["name"], _arg)] = dict(enumerate(_param["items"]))

CODEC = TagCodec(TAGS, VALUE_NAMES)
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
