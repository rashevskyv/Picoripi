"""Retry policy for the pipeline's AI calls.

A glossary build makes hundreds of independent requests. A single rate limit
part-way through must not throw the whole run away, so transient failures --
429, 5xx, timeouts, dropped connections -- are retried with exponential backoff.

Configuration failures are the opposite case: a bad key, a missing model or a
wrong URL will fail identically on every attempt, so they are re-raised at once
rather than burning a minute of backoff per call.

The providers surface errors as ``TranslationProviderError`` carrying only a
message string, so transience is judged from the text. Matching is deliberately
narrow -- ``"502 Server Error"`` and named conditions, never a bare ``"502"`` --
because a loose match would treat a port number or a token count in an
unrelated message as a server error and retry something hopeless.

Pure policy with an injected ``sleep``, so the backoff is tested without waiting.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional


# requests renders HTTP failures as "<code> Client Error: ..." / "<code> Server
# Error: ...". Anchoring on that shape keeps stray digits from matching.
_STATUS_RE = re.compile(r"\b(408|409|425|429|500|502|503|504|529)\s+(?:client|server)\s+error", re.I)

# Named conditions, for providers that phrase failures in prose instead.
_TRANSIENT_PHRASES = (
    "too many requests",
    "rate limit",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "timed out",
    "timeout",
    "overloaded",
    "capacity",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "connection refused",
    "remote end closed",
)


def is_transient(error: object) -> bool:
    """Whether a failure is worth retrying rather than aborting the run."""
    text = str(error or "")
    if _STATUS_RE.search(text):
        return True
    lowered = text.lower()
    return any(phrase in lowered for phrase in _TRANSIENT_PHRASES)


def backoff_delays(attempts: int, *, base: float = 2.0, cap: float = 60.0) -> List[float]:
    """Delays to wait between ``attempts`` tries: base, 2x, 4x ... capped."""
    return [min(cap, base * (2 ** i)) for i in range(max(0, attempts - 1))]


def call_with_retry(
    call: Callable[[], str],
    *,
    attempts: int = 6,
    sleep: Callable[[float], None],
    base: float = 2.0,
    cap: float = 60.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
) -> str:
    """Call ``call``, retrying transient failures with exponential backoff.

    Re-raises the last error once the attempts are spent, and re-raises a
    non-transient error immediately. Cancellation is honoured while waiting: a
    cancelled run stops backing off and surfaces the pending error.
    """
    delays = backoff_delays(attempts, base=base, cap=cap)
    last: Optional[Exception] = None

    for index in range(max(1, attempts)):
        try:
            return call()
        except Exception as exc:  # provider errors are plain exceptions
            last = exc
            if not is_transient(exc):
                raise
            if index >= len(delays):
                raise
            if is_cancelled is not None and is_cancelled():
                raise
            delay = delays[index]
            if on_retry is not None:
                on_retry(index + 1, delay, exc)
            sleep(delay)
            if is_cancelled is not None and is_cancelled():
                raise

    # Unreachable: the loop either returns or raises.
    raise last if last else RuntimeError("call_with_retry made no attempt")
