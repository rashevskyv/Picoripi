"""Pass 2: build centered context windows around a term's occurrences.

A term's meaning lives in the text around each occurrence, not in the arbitrary
sweep chunk it was found in (roadmap section 5, pass 2). Given every occurrence
of a term, we cut a window around each one -- the occurrence string in the
middle, extended by whole neighbouring strings -- and hand the windows to the AI
as one stack.

The window width is **derived from the occurrence count** against a fixed stack
budget, not a constant: one occurrence gets a deep window (nothing else to go
on), forty occurrences each get a thin slice (variety carries the picture).
Windows are bounded by whole game strings; a string is never split.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple


# Per-stack budget and window bounds, in the caller's weighing unit. Defaults are
# characters; pass a token estimator via ``weigh`` to work in tokens.
DEFAULT_STACK_BUDGET = 8000
DEFAULT_MAX_WINDOW = 4000
DEFAULT_MIN_WINDOW = 240
DEFAULT_MAX_OCCURRENCES = 40


@dataclass(frozen=True)
class Occurrence:
    """One appearance of a term at a game-string coordinate."""

    block_idx: int
    string_idx: int


@dataclass(frozen=True)
class ContextWindow:
    """A window of whole game strings centered on one occurrence."""

    occurrence: Occurrence
    block_idx: int
    start_string_idx: int
    end_string_idx: int  # inclusive
    text: str


def _sample_evenly(occurrences: Sequence[Occurrence], limit: int) -> List[Occurrence]:
    """Take ``limit`` occurrences spread evenly across the sequence.

    When a term appears more often than the budget can cover, variety of usage
    matters more than any single site, so sample across the whole range rather
    than truncating to the first ``limit``.
    """
    count = len(occurrences)
    if count <= limit:
        return list(occurrences)
    step = count / limit
    return [occurrences[int(i * step)] for i in range(limit)]


def plan_window_size(
    occurrence_count: int,
    *,
    stack_budget: int = DEFAULT_STACK_BUDGET,
    max_window: int = DEFAULT_MAX_WINDOW,
    min_window: int = DEFAULT_MIN_WINDOW,
) -> int:
    """Per-occurrence window size = stack budget / count, clamped.

    One occurrence yields ``max_window`` (depth); many occurrences share the
    budget and each shrinks toward ``min_window`` (breadth).
    """
    if occurrence_count <= 0:
        return max_window
    share = stack_budget // occurrence_count
    return max(min_window, min(max_window, share))


def build_window(
    dataset: Sequence[Sequence[object]],
    occurrence: Occurrence,
    window_size: int,
    *,
    separator: str = "\n",
    weigh: Callable[[str], int] = len,
) -> ContextWindow:
    """Grow a window of whole strings around ``occurrence`` up to ``window_size``.

    The occurrence string is always included, even if it alone exceeds the
    window. Expansion alternates outward (after, then before) adding one whole
    neighbouring string at a time while the budget allows.
    """
    block = dataset[occurrence.block_idx]
    center = occurrence.string_idx

    def text_at(idx: int) -> str:
        value = block[idx]
        return "" if value is None else str(value)

    start = center
    end = center
    used = weigh(text_at(center))
    sep_weight = weigh(separator)

    expand_after = True
    while True:
        can_after = end + 1 < len(block)
        can_before = start - 1 >= 0
        if not can_after and not can_before:
            break

        # Alternate direction, but fall through to the other side if one is done.
        take_after = (expand_after and can_after) or (not can_before)
        target = end + 1 if take_after else start - 1

        cost = sep_weight + weigh(text_at(target))
        if used + cost > window_size:
            break

        used += cost
        if take_after:
            end = target
        else:
            start = target
        expand_after = not expand_after

    texts = [text_at(i) for i in range(start, end + 1)]
    return ContextWindow(
        occurrence=occurrence,
        block_idx=occurrence.block_idx,
        start_string_idx=start,
        end_string_idx=end,
        text=separator.join(texts),
    )


def build_context_stack(
    dataset: Sequence[Sequence[object]],
    occurrences: Sequence[Occurrence],
    *,
    stack_budget: int = DEFAULT_STACK_BUDGET,
    max_window: int = DEFAULT_MAX_WINDOW,
    min_window: int = DEFAULT_MIN_WINDOW,
    max_occurrences: int = DEFAULT_MAX_OCCURRENCES,
    separator: str = "\n",
    weigh: Callable[[str], int] = len,
) -> Tuple[List[ContextWindow], bool]:
    """Build the centered-window stack for one term.

    Returns ``(windows, overflowed)``. ``overflowed`` is True when the term had
    more occurrences than ``max_occurrences`` and was sampled -- the signal that
    the 5->1 rolling synthesis (pass 2b) is needed instead of a single stack.
    """
    valid = [
        occ
        for occ in occurrences
        if 0 <= occ.block_idx < len(dataset)
        and isinstance(dataset[occ.block_idx], (list, tuple))
        and 0 <= occ.string_idx < len(dataset[occ.block_idx])
    ]
    if not valid:
        return [], False

    overflowed = len(valid) > max_occurrences
    chosen = _sample_evenly(valid, max_occurrences)
    window_size = plan_window_size(
        len(chosen),
        stack_budget=stack_budget,
        max_window=max_window,
        min_window=min_window,
    )
    windows = [
        build_window(dataset, occ, window_size, separator=separator, weigh=weigh)
        for occ in chosen
    ]
    return windows, overflowed
