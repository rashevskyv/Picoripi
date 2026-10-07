"""Paper Mario: The Origami King MSBT control tags, named from the game's own ``msg/<language>/msg.msbp``.

``msbp.json`` comes from ``python -m plugins.common.msbp msg.msbp msbp.json``: six tag groups (System, Control,
Layout, Text, Private, Karaoke). The codec is the Thousand-Year Door one (``plugins.paper_mario_nx.tags``).
The System ``Font`` tag stores a signed 16-bit font number, not the MSBP's string: ``{Font:4}`` ... ``{Font:-1}``
(back to the default font).
"""
from pathlib import Path

from plugins.paper_mario_nx.tags import TAG_RE, load_codec  # noqa: F401 - TAG_RE is this module's API

CODEC = load_codec(Path(__file__).with_name("msbp.json"), {(0, 1): ("s16",)})
TAGS = CODEC.tags
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
parse_tag = CODEC.parse_tag
