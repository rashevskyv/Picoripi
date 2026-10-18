"""Field scripts (``field/*.sct``) as editor strings: one string per text segment, saved back into the decoded body.

A segment is a page's text cut at each label inside it (``core.containers.skies_script.text_segments``). The field
scripts have no label inside a text, so a segment is a page. A file in ``FIXED_SIZE`` keeps every segment's byte length:
a longer text is refused and the source text stays; a shorter text is padded with spaces to the same length. Other
files may grow: ``grow_regions`` moves the labels and the branch operands to the new places of their targets.
"""
from __future__ import annotations

from typing import List, Sequence, Set, Tuple

from core.containers import skies_script

from . import text

BIG_ENDIAN = True   # GameCube
# Scripts whose text keeps every segment's length (a path matches by its end). Empty: every script uses the
# script-level budget. A script that grows in one line must shorten another, so its file size and tail stay
# unchanged (a growth that moves the tail froze the Dreamcast game, 2026-10-18; see OPEN_ITEMS).
FIXED_SIZE = ()


def is_fixed(rel_path: str, names: Tuple[str, ...] = FIXED_SIZE) -> bool:
    if "*" in names:
        return True
    key = rel_path.replace("\\", "/")
    return any(key == name or key.endswith("/" + name) for name in names)


def segments(body: bytes, big: bool = BIG_ENDIAN) -> List[Tuple[int, int]]:
    """(start, end) byte offsets of each text segment, in file order. ``big`` is the script's byte order."""
    return [(start, end) for _page, start, end in skies_script.text_segments(body, big)]


def read_strings(body: bytes, big: bool = BIG_ENDIAN) -> List[str]:
    return [text.decode(body[start:end]) for start, end in segments(body, big)]


def write_strings(source: bytes, strings: Sequence[str], fixed: bool,
                  big: bool = BIG_ENDIAN) -> Tuple[bytes, List[int], Set[str]]:
    """The body with the edited strings written in. Returns (new body, refused string indices, missing characters).

    Every string is compared with the source text, so an unchanged string keeps its bytes. The source body is the only
    base: the offsets come from it, never from a previous save.
    """
    spans = segments(source, big)
    if len(strings) != len(spans):
        raise ValueError(f"expected {len(spans)} strings, got {len(strings)}")
    replacements = {}
    changed_index = {}
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
        changed_index[(start, end)] = index
    if not replacements:
        return source, refused, missing
    if fixed:
        out = bytearray(source)
        for (start, end), new in replacements.items():
            out[start:end] = new
        return bytes(out), refused, missing
    try:
        out, _delta = skies_script.grow_regions(source, replacements, big, net_zero=True)
    except ValueError:
        # Over the script's budget: the whole script keeps its source text.
        return source, sorted(changed_index.values()), missing
    return out, refused, missing
