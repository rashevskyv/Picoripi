"""Parallelism window for stateless chunk dispatch (roadmap section 5).

Stateless chunks are independent, so they can run concurrently. The safe number
of concurrent requests differs per model and is not knowable up front, so it is
found by measurement, the way TCP congestion control finds a link's capacity
(AIMD -- additive increase, multiplicative decrease):

- a successful batch -> concurrency **+1**, probing for more;
- a failure (rate limit) -> concurrency **halved**, and the failed chunks are
  marked for retry;
- after halving, probe **+1** again.

A local model gains nothing above 1 (it processes one request at a time), so its
cap is 1; the value stays configurable for anyone who wants otherwise. When
auto-measure is off the window is fixed and never adjusts.

This module is pure policy: it decides the window size and nothing else. The
dispatch loop, threads, and the actual requests live in the worker.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIMDWindow:
    """Additive-increase / multiplicative-decrease concurrency window."""

    concurrency: int = 1
    minimum: int = 1
    maximum: int = 16
    additive: int = 1
    factor: float = 0.5
    auto_measure: bool = True

    def __post_init__(self) -> None:
        self.minimum = max(1, int(self.minimum))
        self.maximum = max(self.minimum, int(self.maximum))
        self.concurrency = self._clamp(int(self.concurrency))

    def _clamp(self, value: int) -> int:
        return max(self.minimum, min(self.maximum, value))

    def on_success(self) -> int:
        """Additive increase after a fully successful batch."""
        if self.auto_measure:
            self.concurrency = self._clamp(self.concurrency + self.additive)
        return self.concurrency

    def on_failure(self) -> int:
        """Multiplicative decrease after a rate-limit / failure."""
        if self.auto_measure:
            reduced = int(self.concurrency * self.factor)
            self.concurrency = self._clamp(reduced)
        return self.concurrency

    def at_ceiling(self) -> bool:
        """Whether the window has reached its configured maximum."""
        return self.concurrency >= self.maximum


def fixed_window(concurrency: int, *, maximum: int = 16) -> AIMDWindow:
    """A non-adjusting window pinned at ``concurrency`` (auto-measure off)."""
    c = max(1, int(concurrency))
    return AIMDWindow(
        concurrency=c,
        minimum=1,
        maximum=max(c, maximum),
        auto_measure=False,
    )


def local_window() -> AIMDWindow:
    """The window for a local model: one request at a time, no probing."""
    return AIMDWindow(concurrency=1, minimum=1, maximum=1, auto_measure=False)
