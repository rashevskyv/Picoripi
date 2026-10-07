"""Paper Mario TTYD (Switch) MSBT control tags: the catalogue and the readable ``{tags}`` the editor shows.

Catalogue source: the game's own project file ``msg/<language>/msg.msbp`` (shipped as ``msbp.json``,
``python -m plugins.common.msbp msg.msbp msbp.json``): eight tag groups (System, Control, Layout, Text,
Private, Karaoke, Article, Plural) with their parameter names and types. A tag's editor name is its MSBP
name; a name an earlier group already uses gets the group in front (``{Karaoke_wait:...}``).

The System tags store less than the MSBP lists: ``{Color:r:g:b:a}`` keeps four bytes (no name), ``{Size:n}``
only the percentage. List parameters are one byte, shown by item name ({param:Item:...}); a string
after it starts on the next even byte. The codec (``plugins.common.lms_tags``) shows a tag by
name only when its readable form encodes back to the same bytes; anything else stays ``{tag:G:T:hex}``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

_TYPES = {"u8": "u8", "u16": "u16", "u32": "u32", "s8": "s8", "s16": "s16", "s32": "s32", "f32": "f32",
          "str": "str", "list": "u8"}
# (group, type) -> argument types the files really hold, where they differ from the MSBP.
_STORED = {(0, 2): ("u16",), (0, 3): ("u8", "u8", "u8", "u8")}


def _catalogue(msbp_json: Path, stored=None):
    """``(tags, value names)`` of a ``msbp.json``: list parameters show their MSBP item names."""
    project = json.loads(msbp_json.read_text(encoding="utf-8"))
    groups = project["tag_groups"]
    taken = set()
    tags: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {}
    value_names: Dict[Tuple[str, int], Dict[int, str]] = {}
    for group in groups:
        for index, tag in enumerate(group["tags"]):
            key = (group["id"], index)
            name = tag["name"] if tag["name"] not in taken else f"{group['name']}_{tag['name']}"
            taken.add(tag["name"])
            types = (stored or _STORED).get(key) or tuple(_TYPES.get(p["type"], "u8") for p in tag["params"])
            params = ", ".join(p["name"] for p in tag["params"])
            tags[key] = (name, types, f"{group['name']} tag {tag['name']}" + (f" ({params})" if params else ""))
            for position, param in enumerate(tag["params"]):
                if param.get("items"):
                    value_names[(name, position)] = dict(enumerate(param["items"]))
    return tags, value_names


def load_codec(msbp_json: Path, stored=None) -> TagCodec:
    """The codec of another game's ``msbp.json``; ``stored`` adds its own {(group, type): stored types}."""
    return TagCodec(*_catalogue(msbp_json, {**_STORED, **(stored or {})}))


TAGS, VALUE_NAMES = _catalogue(Path(__file__).with_name("msbp.json"))
CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
