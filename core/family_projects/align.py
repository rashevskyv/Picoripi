"""Match the units of one console to the units of its parent by their match keys.

A match key is what the plugin says two units share (by default the translator-visible text). Core only compares
keys; it never reads a game format.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple


def key_hash(key: str) -> str:
    """Stable fingerprint of one match key (stored instead of the key itself)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Alignment:
    """pairs: (parent position, console position) of equal keys, in order. The rest are listed as *_only."""

    pairs: Tuple[Tuple[int, int], ...]
    parent_only: Tuple[int, ...]
    console_only: Tuple[int, ...]


def align(parent: Sequence[str], keys: Sequence[str]) -> Alignment:
    """Pair equal keys in order (difflib matching blocks on their hashes).

    ponytail: SequenceMatcher finds the matching blocks; a key repeated in a moved place can pair with the wrong
    copy. Upgrade path: the plugin gives a unique key (for example a message id) when it has one.
    """
    left = [key_hash(k) for k in parent]
    right = [key_hash(k) for k in keys]
    pairs: List[Tuple[int, int]] = []
    for block in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks():
        pairs.extend((block.a + k, block.b + k) for k in range(block.size))
    used_parent = {i for i, _ in pairs}
    used_console = {j for _, j in pairs}
    return Alignment(
        pairs=tuple(pairs),
        parent_only=tuple(i for i in range(len(left)) if i not in used_parent),
        console_only=tuple(j for j in range(len(right)) if j not in used_console),
    )
