"""Rhythm Paradise Megamix MSBT control tags, named by the game's own message project.

Catalogue: ``msbp.json`` = ``arc/pajama.msbp`` from ``romfs/EUENmessage/pajama.zlib`` (``python -m plugins.common.msbp``):
  ``{PageBreak}`` ``{Size:N}`` ``{Color:R:G:B:A}``                     System
  ``{GameName}`` ``{RhythmItemName}`` ``{Money}`` ``{GameBestScore}`` ...  Replace: values the game inserts
  ``{Jump}`` ``{Branch}`` ``{NaviChar}`` ``{AnnounceLyt}`` ...           Talk: dialogue flow and the guide character
  ``{Change_WholePage}`` ``{CharWait}`` ``{CharSE}`` ``{BGM}``           TalkMode: how text appears, sound cues
  ``{InputType}`` ``{IgnoreLF}`` ``{Dummy}`` and ``{/InputType}``        Etc
Anything the catalogue cannot reproduce byte for byte stays raw ``{tag:G:T:hex}``. The text also uses ``/`` to
mark the places where a line may break and the karaoke beats of the songs; keep them.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from plugins.common.lms_tags import TAG_RE, TagCodec, catalogue_from_msbp  # noqa: F401 - TAG_RE is this module's API

PROJECT = json.loads(Path(__file__).with_name("msbp.json").read_text(encoding="utf-8"))


def _unique_names(project: dict) -> dict:
    """The project with every tag name unique; a repeat gets its group's name in front."""
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
