"""One retry, timeout and error-classification policy for every AI call.

A failure is first *classified* -- what kind it is and whether sending the same
request again can help -- and only then retried. A bad key, a missing model or a
wrong URL fails identically on every attempt, so those are raised at once; a rate
limit, a timeout or a dropped connection is retried with exponential backoff, and
a ``Retry-After`` from the server is always waited out in full.

Free of Qt. ``sleep``, ``clock`` and ``rng`` are injected so the backoff and the
circuit breaker are tested without waiting.
"""
from __future__ import annotations

import random
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Tuple

import requests


class TranslationProviderError(Exception):
    """Custom exception for provider-related errors."""
    # Seconds the server asked us to wait (its Retry-After), 0.0 if it named none.
    retry_after: float = 0.0


class ErrorKind(Enum):
    CONNECT = "connect"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    AUTH = "auth"
    BAD_REQUEST = "bad_request"
    PARSE = "parse"
    EMPTY = "empty"
    CANCELLED = "cancelled"


_RETRYABLE_KINDS = frozenset({ErrorKind.CONNECT, ErrorKind.TIMEOUT, ErrorKind.RATE_LIMIT, ErrorKind.SERVER})


class TransportError(TranslationProviderError):
    """A classified provider failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind,
        status: Optional[int] = None,
        retry_after: float = 0.0,
        retryable: Optional[bool] = None,
        raw_text: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.retry_after = max(0.0, float(retry_after or 0.0))
        self.retryable = (kind in _RETRYABLE_KINDS) if retryable is None else bool(retryable)
        self.raw_text = raw_text


_AUTH_STATUSES = frozenset({401, 403})

# requests renders HTTP failures as "<code> Client Error: ..." / "<code> Server
# Error: ...". Anchoring on that shape keeps a port number or a token count in an
# unrelated message from being read as a status.
_STATUS_RE = re.compile(r"\b([1-5]\d{2})\s+(?:client|server)\s+error", re.I)

# An upstream status quoted inside a proxy's own error body, e.g.
# '502 Bad Gateway ... {"error": {"message": "upstream error: HTTP Error 405"}}'.
# The quoted status is the real answer, however transient the 502 around it looks.
_RELAYED_STATUS_RE = re.compile(r"upstream error:\s*HTTP Error\s*(\d{3})", re.I)

_RETRY_AFTER_RE = re.compile(r"retry (?:after|in) (\d+(?:\.\d+)?)\s*s", re.I)

# The native Gemini endpoint carries the API key in the URL, and requests puts
# the URL into its exception text.
_SECRET_RE = re.compile(r"([?&]key=)[^&\s'\"]+", re.I)

# Named conditions, for failures that arrive as prose instead of a status.
_PHRASES: Tuple[Tuple[ErrorKind, Tuple[str, ...]], ...] = (
    (ErrorKind.RATE_LIMIT, ("too many requests", "rate limit")),
    (ErrorKind.TIMEOUT, ("gateway timeout", "timed out", "timeout")),
    (ErrorKind.CONNECT, ("connection reset", "connection aborted", "connection refused", "remote end closed")),
    (ErrorKind.SERVER, ("bad gateway", "service unavailable", "overloaded", "capacity", "temporarily unavailable")),
)


def redact(text: object) -> str:
    """``text`` with any ``?key=`` secret masked."""
    return _SECRET_RE.sub(r"\1***", str(text or ""))


def _kind_for_status(status: int) -> ErrorKind:
    if status in _AUTH_STATUSES:
        return ErrorKind.AUTH
    if status == 429:
        return ErrorKind.RATE_LIMIT
    if status == 408:
        return ErrorKind.TIMEOUT
    if status == 425 or status >= 500:
        return ErrorKind.SERVER
    return ErrorKind.BAD_REQUEST


def _retry_after(response: Any, *texts: str) -> float:
    header = None
    if response is not None:
        try:
            header = response.headers.get("Retry-After")
        except Exception:
            header = None
    try:
        # ponytail: the HTTP-date form of Retry-After parses as 0 and falls back
        # to the backoff delay. Parse it if a server here ever sends one.
        value = max(0.0, float(header))
    except (TypeError, ValueError):
        value = 0.0
    if value > 0.0:
        return value
    for text in texts:
        match = _RETRY_AFTER_RE.search(text or "")
        if match:
            return float(match.group(1))
    return 0.0


def _classify_text(message: str, body: str = "") -> Tuple[ErrorKind, Optional[int]]:
    text = f"{message} {body}"
    relayed = _RELAYED_STATUS_RE.search(text)
    if relayed:
        status = int(relayed.group(1))
        return _kind_for_status(status), status
    match = _STATUS_RE.search(text)
    if match:
        status = int(match.group(1))
        return _kind_for_status(status), status
    lowered = text.lower()
    for kind, phrases in _PHRASES:
        if any(phrase in lowered for phrase in phrases):
            return kind, None
    return ErrorKind.BAD_REQUEST, None


def classify(error: Any, message: Optional[str] = None) -> TransportError:
    """Turn an exception or a failed ``requests.Response`` into a ``TransportError``.

    ``message`` replaces the default text when the caller has a better one. An
    error nothing here recognises is treated as not retryable: repeating a
    request that failed for an unknown reason is how a block gets extended.
    """
    if isinstance(error, TransportError):
        return error

    response = error if isinstance(error, requests.Response) else getattr(error, "response", None)
    body = ""
    if response is not None:
        try:
            body = str(response.text or "")
        except Exception:
            body = ""

    if message is None:
        message = str(error) if isinstance(error, BaseException) else f"HTTP {getattr(response, 'status_code', '?')}"
        if isinstance(error, requests.Timeout) and not isinstance(error, requests.exceptions.ConnectTimeout):
            message = f"Request timed out: {message}"
        elif isinstance(error, requests.RequestException) or not isinstance(error, BaseException):
            message = f"API request failed: {message}" + (f" - {body[:200]}" if body else "")
    message = redact(message)

    status: Optional[int] = getattr(response, "status_code", None) if response is not None else None
    if isinstance(status, int) and status >= 400:
        kind = _kind_for_status(status)
        relayed = _RELAYED_STATUS_RE.search(body)
        if relayed:
            kind = _kind_for_status(int(relayed.group(1)))
    # ConnectTimeout is both a ConnectionError and a Timeout: nothing answered.
    elif isinstance(error, requests.exceptions.ConnectTimeout):
        kind = ErrorKind.CONNECT
    elif isinstance(error, requests.Timeout):
        kind = ErrorKind.TIMEOUT
    elif isinstance(error, requests.ConnectionError):
        kind = ErrorKind.CONNECT
    else:
        kind, status = _classify_text(message, body)

    retry_after = max(
        float(getattr(error, "retry_after", 0.0) or 0.0),
        _retry_after(response, message, body),
    )
    return TransportError(
        message,
        kind=kind,
        status=status if isinstance(status, int) else None,
        retry_after=retry_after,
        raw_text=body or None,
    )


class CircuitBreaker:
    """Stops calling a backend that keeps failing, until it has had time to recover.

    After ``threshold`` retryable failures in a row the breaker opens for the
    ``Retry-After`` the last failure carried, or ``cooldown`` when it named none.
    While open, ``check`` fails fast instead of sending a request that would only
    extend the block. The count is across threads: three threads failing once
    each is the same dead backend as one thread failing three times.
    """

    def __init__(self, threshold: int = 5, cooldown: float = 30.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.threshold = max(1, int(threshold))
        self.cooldown = float(cooldown)
        self._clock = clock
        self._lock = threading.Lock()
        self._consecutive = 0
        self._open_until = 0.0

    def check(self) -> None:
        with self._lock:
            remaining = self._open_until - self._clock()
        if remaining > 0:
            raise TransportError(
                f"Provider is cooling down after repeated failures; retry in {remaining:.0f}s.",
                kind=ErrorKind.RATE_LIMIT,
                retry_after=remaining,
                retryable=False,
            )

    def record_success(self) -> None:
        with self._lock:
            self._consecutive = 0
            self._open_until = 0.0

    def record_failure(self, error: TransportError) -> None:
        if not error.retryable:
            return
        with self._lock:
            self._consecutive += 1
            if self._consecutive >= self.threshold:
                self._open_until = self._clock() + (error.retry_after or self.cooldown)
                self._consecutive = 0


class AbortableSession(requests.Session):
    """A session whose open sockets can be shut down from another thread.

    Closing a ``requests`` session leaves an in-flight read running (measured:
    a 4 s reply still took 4 s), and the server never learns the client left.
    Shutting the socket down ends the read at once and closes the connection,
    which a server such as the Web2API proxy sees and stops working on.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sockets: list = []
        self._sockets_lock = threading.Lock()
        sockets, lock = self._sockets, self._sockets_lock

        from urllib3.connection import HTTPConnection, HTTPSConnection
        from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

        def tracked(base):
            class Tracked(base):
                def connect(self):
                    super().connect()
                    with lock:
                        sockets.append(self.sock)
            return Tracked

        class Pool(HTTPConnectionPool):
            ConnectionCls = tracked(HTTPConnection)

        class SecurePool(HTTPSConnectionPool):
            ConnectionCls = tracked(HTTPSConnection)

        for adapter in self.adapters.values():
            adapter.poolmanager.pool_classes_by_scheme = {"http": Pool, "https": SecurePool}

    def abort(self) -> None:
        """Shut down every socket this session opened; safe from any thread."""
        import socket
        with self._sockets_lock:
            sockets, self._sockets[:] = list(self._sockets), []
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


def run_cancellable(
    fn: Callable[[], Any],
    is_cancelled: Optional[Callable[[], bool]],
    poll: float = 0.1,
    on_cancel: Optional[Callable[[], None]] = None,
) -> Any:
    """Run blocking ``fn`` so that a cancel does not have to wait for it.

    The call runs on a helper thread and the caller polls ``is_cancelled``; on
    cancel the caller raises ``CANCELLED`` at once and the helper is discarded.
    ``on_cancel`` (e.g. ``AbortableSession.abort``) is called first, so the
    request's connection is closed and the server stops working on it;
    without it the server still completes the abandoned request.

    Without ``is_cancelled`` this is a plain call.
    """
    if is_cancelled is None:
        return fn()
    outcome: dict = {}

    def target() -> None:
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # handed to the caller below
            outcome["error"] = exc

    thread = threading.Thread(target=target, name="ai-request", daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(poll)
        if thread.is_alive() and is_cancelled():
            if on_cancel is not None:
                on_cancel()
            raise TransportError("Cancelled.", kind=ErrorKind.CANCELLED)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


@dataclass
class TransportPolicy:
    """How long to wait for a request, and how to retry it."""

    timeout: float = 60.0
    connect_timeout: float = 10.0
    max_attempts: int = 3
    base: float = 2.0
    cap: float = 60.0
    # Share of each backoff delay that is randomised: 0 = fixed, 1 = full jitter.
    jitter: float = 0.5
    # Seconds the whole call, waits included, may take. None = no limit.
    total_deadline: Optional[float] = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    rng: Callable[[], float] = random.random

    def requests_timeout(self) -> Tuple[float, float]:
        """(connect, read) so a dead endpoint fails fast, not after the read budget."""
        read = float(self.timeout)
        return (min(float(self.connect_timeout), read), read)

    def delay(self, attempt: int, retry_after: float = 0.0) -> float:
        """Wait before retry number ``attempt`` (1-based). Never below ``retry_after``."""
        backoff = min(self.cap, self.base * (2 ** (attempt - 1)))
        jitter = min(1.0, max(0.0, self.jitter))
        backoff = backoff * (1.0 - jitter) + backoff * jitter * self.rng()
        return max(backoff, float(retry_after or 0.0))

    def run(
        self,
        fn: Callable[[], Any],
        is_cancelled: Optional[Callable[[], bool]] = None,
        *,
        on_retry: Optional[Callable[[int, float, TransportError], None]] = None,
        breaker: Optional[CircuitBreaker] = None,
    ) -> Any:
        """Call ``fn``, retrying retryable failures. Raises ``TransportError``."""
        started = self.clock()
        attempts = max(1, int(self.max_attempts))
        for attempt in range(1, attempts + 1):
            self._raise_if_cancelled(is_cancelled)
            if breaker is not None:
                breaker.check()
            try:
                result = fn()
            except Exception as exc:
                error = classify(exc)
                if breaker is not None:
                    breaker.record_failure(error)
                delay = self.delay(attempt, error.retry_after)
                out_of_time = (
                    self.total_deadline is not None
                    and self.clock() - started + delay > self.total_deadline
                )
                if not error.retryable or attempt >= attempts or out_of_time:
                    if error is exc:
                        raise
                    raise error from exc
                if on_retry is not None:
                    on_retry(attempt, delay, error)
                self._wait(delay, is_cancelled)
            else:
                if breaker is not None:
                    breaker.record_success()
                return result
        raise RuntimeError("TransportPolicy.run made no attempt")  # unreachable

    def _wait(self, delay: float, is_cancelled: Optional[Callable[[], bool]]) -> None:
        # Sleep in short slices so a cancel does not sit out a 60 s Retry-After.
        remaining = delay
        while remaining > 0:
            self._raise_if_cancelled(is_cancelled)
            step = min(0.5, remaining)
            self.sleep(step)
            remaining -= step
        self._raise_if_cancelled(is_cancelled)

    @staticmethod
    def _raise_if_cancelled(is_cancelled: Optional[Callable[[], bool]]) -> None:
        if is_cancelled is not None and is_cancelled():
            raise TransportError("Cancelled.", kind=ErrorKind.CANCELLED)
