"""Passes 2 / 2b driver: turn a term's occurrences into one description.

Ties the context-window builder (pass 2) to the rolling synthesizer (pass 2b),
with both AI operations injected:

- ``synthesize_stack(windows) -> fragment``: read a stack of centered windows and
  return one description fragment;
- ``fold(texts) -> description``: merge fragment texts into one (only needed when
  a term has more occurrences than fit a single stack).

When every occurrence fits one stack, one ``synthesize_stack`` call is the whole
description. Otherwise occurrences are batched, each batch yields a fragment, and
the fragments are rolled 5->1 with early stop (roadmap section 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .context_window import (
    DEFAULT_MAX_OCCURRENCES,
    DEFAULT_MAX_WINDOW,
    DEFAULT_MIN_WINDOW,
    DEFAULT_STACK_BUDGET,
    ContextWindow,
    Occurrence,
    build_context_stack,
)
from .rolling_synthesis import DEFAULT_FOLD_AT, RollingSynthesizer, _default_is_new


@dataclass
class DescribeResult:
    """Outcome of describing one term from its occurrences."""

    description: str
    stacks_processed: int = 0
    folded: bool = False
    stopped_early: bool = False


def _batch(occurrences: Sequence[Occurrence], size: int) -> List[List[Occurrence]]:
    return [list(occurrences[i : i + size]) for i in range(0, len(occurrences), size)]


def describe_term(
    dataset: Sequence[Sequence[object]],
    occurrences: Sequence[Occurrence],
    synthesize_stack: Callable[[Sequence[ContextWindow]], str],
    *,
    fold: Optional[Callable[[Sequence[str]], str]] = None,
    stack_budget: int = DEFAULT_STACK_BUDGET,
    max_window: int = DEFAULT_MAX_WINDOW,
    min_window: int = DEFAULT_MIN_WINDOW,
    batch_size: int = DEFAULT_MAX_OCCURRENCES,
    fold_at: int = DEFAULT_FOLD_AT,
    is_new: Callable[[str, str], bool] = _default_is_new,
    weigh: Callable[[str], int] = len,
) -> DescribeResult:
    """Describe one term from its occurrences.

    ``fold`` is required only when the term overflows a single stack; without it,
    an overflowing term falls back to describing its first stack alone.
    """
    def windows_for(batch: Sequence[Occurrence]) -> List[ContextWindow]:
        windows, _ = build_context_stack(
            dataset,
            batch,
            stack_budget=stack_budget,
            max_window=max_window,
            min_window=min_window,
            max_occurrences=len(batch) or 1,
            weigh=weigh,
        )
        return windows

    batches = _batch(occurrences, batch_size)
    if not batches:
        return DescribeResult(description="")

    # Fast path: everything fits one stack -> one synthesize call, no folding.
    if len(batches) == 1 or fold is None:
        windows = windows_for(batches[0])
        if not windows:
            return DescribeResult(description="")
        return DescribeResult(
            description=synthesize_stack(windows),
            stacks_processed=1,
            folded=False,
        )

    # Overflow path: a fragment per batch, rolled 5->1 with early stop.
    roller = RollingSynthesizer(synthesize=fold, fold_at=fold_at, is_new=is_new)
    stacks = 0
    for batch in batches:
        windows = windows_for(batch)
        if not windows:
            continue
        fragment = synthesize_stack(windows)
        stacks += 1
        if not roller.add(fragment):
            break

    result = roller.finish()
    return DescribeResult(
        description=result.description,
        stacks_processed=stacks,
        folded=True,
        stopped_early=result.stopped_early,
    )
