"""Pass 1a: pack whole game strings into stateless chunks.

The atom is one game string ``(block_idx, string_idx)``; a string is **never**
split across chunks (roadmap section 5, pass 1a). Whole strings are packed until
adding the next would exceed the budget, then a fresh chunk starts. A single
string larger than the budget becomes its own chunk, unsplit and over budget --
an over-budget lone string is preferable to a string cut in half.

Each chunk keeps the items it carries so extracted terms can be attributed back
to their source rows (provenance). The chunks carry no memory of each other: the
weighing unit and separator are injected so callers can weigh by characters
(default) or by a token estimate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple


# Chunk-size presets keyed by model class (roadmap section 5). Small local
# models extract exhaustively only over short inputs; large cloud models tolerate
# more. Values are in the caller's weighing unit (characters by default).
CHUNK_SIZE_PRESETS = {"local": 2000, "balanced": 4000, "cloud": 8000}
DEFAULT_CHUNK_SIZE = CHUNK_SIZE_PRESETS["balanced"]

_MIN_CHUNK_SIZE = 500
_MAX_CHUNK_SIZE = 32000


@dataclass(frozen=True)
class SweepItem:
    """One game string to sweep, tagged with its source coordinates."""

    block_idx: int
    string_idx: int
    text: str


@dataclass(frozen=True)
class SweepChunk:
    """A packed group of whole game strings and their joined text."""

    items: Tuple[SweepItem, ...]
    text: str

    @property
    def is_over_budget(self) -> bool:
        """A single item that alone exceeded the budget was packed unsplit."""
        return len(self.items) == 1


def resolve_chunk_size(value, *, minimum: int = _MIN_CHUNK_SIZE, maximum: int = _MAX_CHUNK_SIZE) -> int:
    """Resolve a preset name or raw number into a clamped chunk size."""
    if isinstance(value, str):
        preset = CHUNK_SIZE_PRESETS.get(value.strip().lower())
        resolved = preset if preset is not None else DEFAULT_CHUNK_SIZE
    else:
        try:
            resolved = int(value)
        except (TypeError, ValueError):
            resolved = DEFAULT_CHUNK_SIZE
    if resolved <= 0:
        resolved = DEFAULT_CHUNK_SIZE
    return max(minimum, min(maximum, resolved))


def pack_chunks(
    items: Iterable[SweepItem],
    budget,
    *,
    separator: str = "\n",
    weigh: Callable[[str], int] = len,
) -> List[SweepChunk]:
    """Pack whole items into chunks, never splitting a single item.

    ``budget`` may be a preset name or a number; it is resolved and clamped.
    Empty or whitespace-only items are skipped -- a blank row carries no terms.
    """
    budget = resolve_chunk_size(budget)
    sep_weight = weigh(separator)

    chunks: List[SweepChunk] = []
    current_items: List[SweepItem] = []
    current_texts: List[str] = []
    current_weight = 0

    def flush() -> None:
        nonlocal current_items, current_texts, current_weight
        if current_items:
            chunks.append(
                SweepChunk(
                    items=tuple(current_items),
                    text=separator.join(current_texts),
                )
            )
            current_items = []
            current_texts = []
            current_weight = 0

    for item in items:
        if not item.text or not item.text.strip():
            continue

        item_weight = weigh(item.text)

        # A single item larger than the budget goes alone, unsplit.
        if item_weight > budget:
            flush()
            chunks.append(SweepChunk(items=(item,), text=item.text))
            continue

        added_weight = item_weight if not current_items else item_weight + sep_weight
        if current_items and current_weight + added_weight > budget:
            flush()
            added_weight = item_weight

        current_items.append(item)
        current_texts.append(item.text)
        current_weight += added_weight

    flush()
    return chunks


def items_from_dataset(
    dataset: Sequence[Sequence[object]],
    *,
    block_indices: Iterable[int] | None = None,
) -> List[SweepItem]:
    """Flatten a ``data_store``-shaped dataset into sweep items.

    ``dataset`` is ``List[block]``; each block is ``List[string]``. Pass
    ``block_indices`` to restrict the sweep to a subset of blocks (the area
    selector: whole project, a few blocks, or one category's block).
    """
    if block_indices is None:
        block_range: Iterable[int] = range(len(dataset))
    else:
        block_range = block_indices

    out: List[SweepItem] = []
    for block_idx in block_range:
        if block_idx < 0 or block_idx >= len(dataset):
            continue
        block = dataset[block_idx]
        if not isinstance(block, (list, tuple)):
            continue
        for string_idx, value in enumerate(block):
            text = "" if value is None else str(value)
            if not text.strip():
                continue
            out.append(SweepItem(block_idx=block_idx, string_idx=string_idx, text=text))
    return out
