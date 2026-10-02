"""Tag check for pasted text that knows no game: the same tags, kind by kind.

A plugin whose game has special tags (a player name, colour pairs) writes its
own check; see ``plugins/zelda_ww/tag_logic.py`` and ``plugins/zelda_mc/tag_logic.py``.
"""
import re
from collections import Counter
from typing import Tuple

TAG_STATUS_OK = "OK"
TAG_STATUS_WARNING = "WARNING"

ANY_TAG_PATTERN = re.compile(r"\[[^\]]*\]|\{[^}]*\}")


def tag_kind(tag: str) -> str:
    """``[Color:Red]`` and ``[color:blue]`` are one kind, ``[color]``; ``[/C]`` is ``[/c]``."""
    return tag[0] + tag[1:-1].split(":", 1)[0].strip().lower() + tag[-1]


def compare_tags(processed_text: str, original_text: str) -> Tuple[str, str]:
    """``(status, message)``: a warning when the two texts do not hold the same number of each kind of tag."""
    processed = Counter(tag_kind(tag) for tag in ANY_TAG_PATTERN.findall(processed_text))
    original = Counter(tag_kind(tag) for tag in ANY_TAG_PATTERN.findall(original_text))
    if processed == original:
        return TAG_STATUS_OK, ""
    differing = sorted(kind for kind in processed.keys() | original.keys() if processed[kind] != original[kind])
    details = ", ".join(f"{kind}: {processed[kind]} pasted, {original[kind]} in the original" for kind in differing)
    return TAG_STATUS_WARNING, f"Tag count mismatch. {details}."


def process_pasted_segment(
    segment_to_insert: str,
    original_text_for_tags: str,
    editor_player_tag_const: str = "",
) -> Tuple[str, str, str]:
    """The pasted text unchanged, with the result of the tag comparison."""
    status, message = compare_tags(segment_to_insert, original_text_for_tags)
    return segment_to_insert, status, message
