"""Match the messages of one console to the messages of the family base by their source text."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple


def source_hash(text: str) -> str:
    """Stable key of one source text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Alignment:
    """pairs: (base index, console index) of equal source texts, in order. base_only / console_only: the rest."""

    pairs: Tuple[Tuple[int, int], ...]
    base_only: Tuple[int, ...]
    console_only: Tuple[int, ...]


def align(base: Sequence[str], console: Sequence[str]) -> Alignment:
    """Align two lists of source texts. Equal texts pair up in order (difflib matching blocks on their hashes).

    ponytail: SequenceMatcher finds the matching blocks; a message repeated in a moved place can pair with the
    wrong copy. Upgrade path: match by message id when both sides have unique ids.
    """
    left = [source_hash(t) for t in base]
    right = [source_hash(t) for t in console]
    pairs: List[Tuple[int, int]] = []
    for block in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks():
        pairs.extend((block.a + k, block.b + k) for k in range(block.size))
    used_base = {i for i, _ in pairs}
    used_console = {j for _, j in pairs}
    return Alignment(
        pairs=tuple(pairs),
        base_only=tuple(i for i in range(len(left)) if i not in used_base),
        console_only=tuple(j for j in range(len(right)) if j not in used_console),
    )
