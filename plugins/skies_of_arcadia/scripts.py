"""Field scripts (``field/*.sct``) as editor strings: one string per text segment, saved back into the decoded body.

A segment is a page's text cut at each label inside it (``core.containers.skies_script.text_segments``), so the game
reads each string in order. A file in ``FIXED_SIZE`` keeps every segment's byte length: a longer text is refused
and the source text stays; a shorter text is padded with spaces to the same length. The game freezes when such a
file grows, so these edits are in-place only. Other files may grow: their bytes move through ``grow_regions``.
"""
from __future__ import annotations

from typing import List, Sequence, Set, Tuple

from core.containers import skies_script

from . import text

BIG_ENDIAN = True   # GameCube
# Scripts that freeze the game when a text grows (see the module docstring). A path matches by its end.
FIXED_SIZE = ("field/me201a.sct",)


def is_fixed(rel_path: str) -> bool:
    key = rel_path.replace("\\", "/")
    return any(key == name or key.endswith("/" + name) for name in FIXED_SIZE)


def segments(body: bytes) -> List[Tuple[int, int]]:
    """(start, end) byte offsets of each text segment, in file order."""
    return [(start, end) for _page, start, end in skies_script.text_segments(body, BIG_ENDIAN)]


def read_strings(body: bytes) -> List[str]:
    return [text.decode(body[start:end]) for start, end in segments(body)]


def write_strings(source: bytes, strings: Sequence[str], fixed: bool) -> Tuple[bytes, List[int], Set[str]]:
    """The body with the edited strings written in. Returns (new body, refused string indices, missing characters).

    Every string is compared with the source text, so an unchanged string keeps its bytes. The source body is the only
    base: the offsets come from it, never from a previous save.
    """
    spans = segments(source)
    if len(strings) != len(spans):
        raise ValueError(f"expected {len(spans)} strings, got {len(strings)}")
    replacements = {}
    refused: List[int] = []
    missing: Set[str] = set()
    for index, ((start, end), new_text) in enumerate(zip(spans, strings)):
        if new_text == text.decode(source[start:end]):
            continue
        new, lost = text.encode(new_text)
        missing |= lost
        if fixed:
            if len(new) > end - start:
                refused.append(index)
                continue
            new += bytes([text.SPACE]) * (end - start - len(new))
        replacements[(start, end)] = new
    if not replacements:
        return source, refused, missing
    if fixed:
        out = bytearray(source)
        for (start, end), new in replacements.items():
            out[start:end] = new
        return bytes(out), refused, missing
    out, _delta = skies_script.grow_regions(source, replacements, BIG_ENDIAN)
    return out, refused, missing
