"""Pass 2b: roll many description fragments into one, 5 at a time.

When a term has too many occurrences to fit one context stack, the fragments
arrive in batches and must be folded without unbounded growth (roadmap section
5, pass 2b):

- collect 5 fragments -> the AI folds them into 1;
- 4 more arrive -> the running synthesis (counting as one) plus the 4 makes 5
  again -> fold to 1;
- repeat: context grows, size stays flat.

**Early stop:** if a fold adds nothing new over the previous synthesis, the term
is done -- frequent terms (a main character) converge after a few folds and stop
eating budget, while rare terms are folded to completion.

This module is pure: the actual AI call and the "is this new?" judgement are
injected as callables so it can be tested without a model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence


DEFAULT_FOLD_AT = 5


def _default_is_new(candidate: str, previous: str) -> bool:
    """Fallback novelty check: different (trimmed) text counts as new."""
    return candidate.strip() != previous.strip()


@dataclass
class SynthesisResult:
    """Outcome of rolling a term's fragments into one description."""

    description: str
    stopped_early: bool = False
    consumed: int = 0
    fold_calls: int = 0
    fragments_seen: int = 0


@dataclass
class RollingSynthesizer:
    """Folds fragments 5-at-a-time with early stop on convergence.

    ``synthesize`` takes the ordered list of inputs (the running synthesis first,
    if any, then new fragments) and returns one folded description. ``is_new``
    decides whether a fresh fold changed anything meaningful.
    """

    synthesize: Callable[[Sequence[str]], str]
    fold_at: int = DEFAULT_FOLD_AT
    is_new: Callable[[str, str], bool] = _default_is_new

    _synthesis: Optional[str] = field(default=None, init=False)
    _buffer: List[str] = field(default_factory=list, init=False)
    _consumed: int = field(default=0, init=False)
    _fold_calls: int = field(default=0, init=False)
    _stopped: bool = field(default=False, init=False)

    def _threshold(self) -> int:
        """How many buffered fragments trigger a fold.

        The first fold needs a full ``fold_at`` raw fragments. Later folds count
        the running synthesis as one of them, so they trigger one fragment sooner.
        """
        return self.fold_at if self._synthesis is None else self.fold_at - 1

    def _fold(self) -> bool:
        """Fold buffered fragments (plus running synthesis) into one.

        Returns True if the caller should keep going, False to stop early.
        """
        inputs: List[str] = []
        if self._synthesis is not None:
            inputs.append(self._synthesis)
        inputs.extend(self._buffer)
        self._buffer = []

        folded = self.synthesize(inputs)
        self._fold_calls += 1

        if self._synthesis is not None and not self.is_new(folded, self._synthesis):
            # Nothing new: keep the prior synthesis and stop.
            self._stopped = True
            return False

        self._synthesis = folded
        return True

    def add(self, fragment: str) -> bool:
        """Feed one fragment. Returns False once the term has converged (stop)."""
        if self._stopped:
            return False
        self._consumed += 1
        self._buffer.append(fragment)
        if len(self._buffer) >= self._threshold():
            return self._fold()
        return True

    def finish(self) -> SynthesisResult:
        """Fold any leftover fragments and return the final description."""
        if not self._stopped and self._buffer:
            self._fold()
        return SynthesisResult(
            description=self._synthesis or "",
            stopped_early=self._stopped,
            consumed=self._consumed,
            fold_calls=self._fold_calls,
            fragments_seen=self._consumed,
        )


def roll_up_fragments(
    fragments: Sequence[str],
    synthesize: Callable[[Sequence[str]], str],
    *,
    fold_at: int = DEFAULT_FOLD_AT,
    is_new: Callable[[str, str], bool] = _default_is_new,
) -> SynthesisResult:
    """Convenience wrapper: roll a whole fragment sequence to one description."""
    roller = RollingSynthesizer(synthesize=synthesize, fold_at=fold_at, is_new=is_new)
    for fragment in fragments:
        if not roller.add(fragment):
            break
    return roller.finish()
