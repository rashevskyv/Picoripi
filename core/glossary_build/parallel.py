"""Run a pass's independent AI calls through a small pool of threads.

Every pass of a build is a list of independent requests -- a chunk to sweep, a
term to describe, an entry to translate. The endpoint behind them is a proxy
holding several accounts, each with its own address, and it hands a different
account to every *concurrent* request; requests on different accounts never wait
for each other. Sending one at a time therefore leaves nearly all of that idle:
six requests measured 22.9s in sequence and 6.9s in six threads. There is no
point going wider than the number of accounts -- the extra threads only queue on
some account's own cooldown.

Three rules make a pool safe to run over a six-hundred-entry build:

- **a failure is data, not an exception.** An exception raised inside
  ``pool.map`` propagates out of the loop and throws away the whole result,
  including everything the other threads already finished -- half an hour of
  work lost to one bad request. Each unit comes back as
  ``(item, result, error)`` instead, so a dead request costs exactly one unit.
- **a result carries its item.** The caller writes what came back against the
  item it came from, never against a position in a list.
- **a second pass, quieter.** A failure here usually means a temporary block, so
  the failed units are tried again on fewer threads. ``Retry-After`` on a 429
  says every account is spent: there is no other worker left to hand the request
  to, and an immediate retry only extends the block, so the wait is taken in
  full.

The server already retries internally across its accounts, so there is
deliberately no retry loop inside a unit -- that extra client-side hammering is
what got addresses banned before. The second pass is the only retry.

Free of Qt and of the glossary: the caller supplies the unit of work, so this is
tested with plain functions.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence


# One thread per account behind the proxy.
DEFAULT_WORKERS = 6
# The retry pass runs narrow on purpose: the units failed because something was
# blocked, and six threads walking back into it is how a block gets extended.
RETRY_WORKERS = 2
# How long to wait before the retry pass when the server named no delay itself.
DEFAULT_RETRY_DELAY = 60.0

# Marker for a unit that was never attempted (cancelled, or the run gave up).
_SKIPPED = object()


@dataclass
class PoolResult:
    """What a pooled pass finished with."""

    failed: List[Any] = field(default_factory=list)
    # The longest Retry-After any failure asked for, 0.0 if none did.
    retry_after: float = 0.0
    # Set when the pass stopped early because the backend stopped answering.
    stop_error: Optional[BaseException] = None
    cancelled: bool = False


def retry_after_seconds(error: object) -> float:
    """The delay the server asked for with a 429, or 0.0 if it asked for none.

    The providers attach the header to the error they raise; parsing it back out
    of the message text would be guesswork.
    """
    try:
        return max(0.0, float(getattr(error, "retry_after", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def run_pool(
    items: Sequence[Any],
    work: Callable[[Any], Any],
    *,
    workers: int = DEFAULT_WORKERS,
    on_result: Optional[Callable[[Any, Any], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    max_consecutive_failures: int = 0,
) -> PoolResult:
    """Run ``work(item)`` over ``items`` in ``workers`` threads.

    ``on_result(item, result)`` and ``on_progress(done, total)`` run on the
    calling thread, in the order the items were given, so the caller can write
    each finished unit as it arrives without locking anything. Writing as you go
    is the point: a crash or a stop then costs the unit in flight, not the run.

    ``max_consecutive_failures`` (0 = never) stops the pass once that many units
    in a row have failed -- the backend is not coming back within this run, and
    grinding through the remaining hundreds only fails slower. The count is over
    the whole pool, not per thread: three threads failing once each is the same
    dead backend as one thread failing three times.

    Units go out a poolful at a time rather than all at once. A pool with an
    unbounded queue runs far ahead of whoever is reading the results, so a stop
    or a cancel would land after every one of six hundred requests had already
    been sent -- which is the opposite of stopping.
    """
    items = list(items)
    outcome = PoolResult()
    if not items:
        return outcome

    width = max(1, int(workers))
    total = len(items)
    stopped = False

    def attempt(item):
        if stopped or (is_cancelled is not None and is_cancelled()):
            return item, _SKIPPED, None
        try:
            return item, work(item), None
        except Exception as exc:  # a failure is data; see the module docstring
            return item, None, exc

    consecutive = 0
    done = 0
    with ThreadPoolExecutor(max_workers=width) as pool:
        # ponytail: one batch is a barrier, so a slow request holds up the next
        # batch. Move to a rolling window of futures if that ever costs more
        # than the ordering and the prompt stop are worth.
        for start in range(0, total, width):
            for item, result, error in pool.map(attempt, items[start : start + width]):
                if result is _SKIPPED:
                    continue
                done += 1
                if error is not None:
                    outcome.failed.append(item)
                    outcome.retry_after = max(outcome.retry_after, retry_after_seconds(error))
                    consecutive += 1
                    if max_consecutive_failures and consecutive >= max_consecutive_failures:
                        outcome.stop_error = error
                        stopped = True
                else:
                    consecutive = 0
                    if on_result is not None:
                        on_result(item, result)
                if on_progress is not None:
                    on_progress(done, total)
            if stopped or (is_cancelled is not None and is_cancelled()):
                break

    outcome.cancelled = bool(is_cancelled is not None and is_cancelled())
    return outcome


def run_with_retry_pass(
    items: Sequence[Any],
    work: Callable[[Any], Any],
    *,
    workers: int = DEFAULT_WORKERS,
    retry_workers: int = RETRY_WORKERS,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    sleep: Callable[[float], None] = time.sleep,
    on_result: Optional[Callable[[Any, Any], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    max_consecutive_failures: int = 0,
    on_log: Optional[Callable[[str], None]] = None,
) -> PoolResult:
    """A pooled pass, then one quieter pass over whatever failed.

    The wait before the retry is the ``Retry-After`` the server sent when it sent
    one, and ``retry_delay`` otherwise. A run that stopped early or was cancelled
    is not retried: the backend is down or the user said no.
    """
    first = run_pool(
        items,
        work,
        workers=workers,
        on_result=on_result,
        on_progress=on_progress,
        is_cancelled=is_cancelled,
        max_consecutive_failures=max_consecutive_failures,
    )
    if not first.failed or first.stop_error is not None or first.cancelled:
        return first

    delay = first.retry_after or retry_delay
    if on_log is not None:
        on_log(f"{len(first.failed)} unit(s) failed; retrying in {delay:.0f}s on {retry_workers} threads")
    sleep(delay)
    if is_cancelled is not None and is_cancelled():
        first.cancelled = True
        return first

    second = run_pool(
        first.failed,
        work,
        workers=retry_workers,
        on_result=on_result,
        on_progress=on_progress,
        is_cancelled=is_cancelled,
        max_consecutive_failures=max_consecutive_failures,
    )
    # The retry pass owns the outcome now; the first pass's failures either
    # succeeded here or are still in second.failed.
    second.retry_after = max(second.retry_after, first.retry_after)
    return second
