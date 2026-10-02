"""TransportPolicy: what is retryable, how long to wait, and when to stop calling."""
import pytest
import requests

from core.translation.providers import TranslationProviderError
from core.translation.transport import (
    CircuitBreaker,
    ErrorKind,
    TransportError,
    TransportPolicy,
    classify,
    gate_for,
    redact,
)


def _http_error(status, body="", headers=None):
    response = requests.Response()
    response.status_code = status
    response._content = body.encode("utf-8")
    response.headers.update(headers or {})
    response.url = "http://localhost:8081/v1/chat/completions"
    return requests.HTTPError(f"{status} Error for url: {response.url}", response=response)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def _policy(clock=None, **kw):
    clock = clock or FakeClock()
    kw.setdefault("jitter", 0.0)
    return TransportPolicy(sleep=clock.sleep, clock=clock, **kw), clock


class TestClassify:
    @pytest.mark.parametrize("status, kind, retryable", [
        (400, ErrorKind.BAD_REQUEST, False),
        (401, ErrorKind.AUTH, False),
        (403, ErrorKind.AUTH, False),
        (404, ErrorKind.BAD_REQUEST, False),
        (405, ErrorKind.BAD_REQUEST, False),
        (422, ErrorKind.BAD_REQUEST, False),
        (408, ErrorKind.TIMEOUT, True),
        (425, ErrorKind.SERVER, True),
        (429, ErrorKind.RATE_LIMIT, True),
        (500, ErrorKind.SERVER, True),
        (502, ErrorKind.SERVER, True),
        (503, ErrorKind.SERVER, True),
    ])
    def test_http_status(self, status, kind, retryable):
        error = classify(_http_error(status))
        assert (error.kind, error.retryable, error.status) == (kind, retryable, status)
        assert isinstance(error, TranslationProviderError)

    def test_requests_exceptions(self):
        assert classify(requests.ConnectionError("refused")).kind is ErrorKind.CONNECT
        assert classify(requests.exceptions.ConnectTimeout("no answer")).kind is ErrorKind.CONNECT
        assert classify(requests.exceptions.ReadTimeout("slow")).kind is ErrorKind.TIMEOUT

    def test_retry_after_header_wins(self):
        error = classify(_http_error(429, "Retry after 5s", {"Retry-After": "42"}))
        assert error.retry_after == 42.0

    @pytest.mark.parametrize("body", ["captcha: Retry after 30s", "all accounts busy, retry in 30s"])
    def test_retry_after_from_both_proxy_phrasings(self, body):
        assert classify(_http_error(429, body)).retry_after == 30.0

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 405, 422])
    def test_a_relayed_permanent_status_beats_the_502_wrapping_it(self, code):
        """A proxy reports its own trouble as 502 and quotes the real answer."""
        body = f'{{"error": {{"message": "upstream error: HTTP Error {code}: nope"}}}}'
        assert classify(_http_error(502, body)).retryable is False

    @pytest.mark.parametrize("code", [429, 500, 502, 503])
    def test_a_relayed_transient_status_is_still_retried(self, code):
        body = f'{{"error": {{"message": "upstream error: HTTP Error {code}: busy"}}}}'
        assert classify(_http_error(502, body)).retryable is True

    @pytest.mark.parametrize("message", [
        "429 Client Error: Too Many Requests",
        "503 Server Error: Service Unavailable",
        "Request timed out after 60 seconds.",
        "Model is overloaded, try again later",
        "Connection aborted",
    ])
    def test_plain_message_retryable(self, message):
        assert classify(RuntimeError(message)).retryable is True

    @pytest.mark.parametrize("message", [
        "401 Client Error: Unauthorized",
        "404 Client Error: Not Found for url: http://localhost:8081/v1/models",
        "OpenAI API key is not set",
        "Failed to parse AI response",
        # A port or a token count must not be read as a server error.
        "connecting to http://localhost:5002/v1",
        "context window exceeded: 502 tokens over",
    ])
    def test_plain_message_not_retryable(self, message):
        assert classify(RuntimeError(message)).retryable is False

    def test_api_key_never_reaches_the_message(self):
        url = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=SECRET123"
        error = classify(requests.ConnectionError(f"Max retries exceeded with url: {url}"))
        assert "SECRET123" not in str(error)
        assert redact(f"{url}&alt=sse").endswith("?key=***&alt=sse")

    def test_a_classified_error_is_returned_unchanged(self):
        error = TransportError("empty", kind=ErrorKind.EMPTY)
        assert classify(error) is error
        assert error.retryable is False


class TestPolicyRun:
    def test_returns_first_success_without_sleeping(self):
        policy, clock = _policy()
        assert policy.run(lambda: "ok") == "ok"
        assert clock.slept == []

    def test_backoff_doubles_and_caps(self):
        policy, _ = _policy(base=2.0, cap=16.0)
        assert [policy.delay(n) for n in range(1, 6)] == [2.0, 4.0, 8.0, 16.0, 16.0]

    def test_full_jitter_stays_inside_the_backoff(self):
        policy = TransportPolicy(base=2.0, jitter=1.0, rng=lambda: 0.25)
        assert policy.delay(2) == 1.0

    def test_recovers_after_retryable_failures(self):
        policy, clock = _policy(max_attempts=4, base=2.0)
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise _http_error(503)
            return "ok"

        assert policy.run(flaky) == "ok"
        assert len(calls) == 3
        assert sum(clock.slept) == 2.0 + 4.0

    def test_fatal_error_is_not_retried(self):
        policy, clock = _policy(max_attempts=4)
        calls = []

        def broken():
            calls.append(1)
            raise _http_error(401)

        with pytest.raises(TransportError) as info:
            policy.run(broken)
        assert info.value.kind is ErrorKind.AUTH
        assert calls == [1] and clock.slept == []

    def test_raises_once_attempts_are_spent(self):
        policy, clock = _policy(max_attempts=3, base=1.0)
        with pytest.raises(TransportError) as info:
            policy.run(lambda: (_ for _ in ()).throw(_http_error(429)))
        assert info.value.kind is ErrorKind.RATE_LIMIT
        assert sum(clock.slept) == 1.0 + 2.0

    def test_retry_after_is_waited_in_full(self):
        policy, clock = _policy(max_attempts=2, base=2.0, cap=10.0)
        calls = []

        def limited():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429, headers={"Retry-After": "45"})
            return "ok"

        assert policy.run(limited) == "ok"
        assert sum(clock.slept) == 45.0

    def test_total_deadline_stops_a_wait_that_cannot_fit(self):
        policy, clock = _policy(max_attempts=5, total_deadline=30.0)
        calls = []

        def limited():
            calls.append(1)
            raise _http_error(429, headers={"Retry-After": "45"})

        with pytest.raises(TransportError):
            policy.run(limited)
        assert calls == [1] and clock.slept == []

    def test_cancelling_stops_the_backoff(self):
        policy, clock = _policy(max_attempts=6, base=8.0)
        with pytest.raises(TransportError) as info:
            policy.run(
                lambda: (_ for _ in ()).throw(_http_error(503)),
                is_cancelled=lambda: bool(clock.slept),
            )
        assert info.value.kind is ErrorKind.CANCELLED
        assert clock.slept == [0.5]

    def test_on_retry_reports_each_wait(self):
        policy, _ = _policy(max_attempts=4, base=2.0)
        seen, calls = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise _http_error(502)
            return "ok"

        policy.run(flaky, on_retry=lambda attempt, delay, error: seen.append((attempt, delay, error.kind)))
        assert seen == [(1, 2.0, ErrorKind.SERVER)]

    def test_requests_timeout_splits_connect_and_read(self):
        assert TransportPolicy(timeout=180).requests_timeout() == (10.0, 180.0)
        assert TransportPolicy(timeout=5).requests_timeout() == (5.0, 5.0)


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures_and_closes_after_cooldown(self):
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=3, cooldown=30.0, clock=clock)
        failure = classify(_http_error(503))

        for _ in range(2):
            breaker.record_failure(failure)
        breaker.check()  # still closed

        breaker.record_failure(failure)
        with pytest.raises(TransportError) as info:
            breaker.check()
        assert info.value.kind is ErrorKind.RATE_LIMIT
        assert info.value.retry_after == 30.0
        assert info.value.retryable is False

        clock.now += 30.0
        breaker.check()

    def test_opens_for_the_servers_retry_after(self):
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock)
        breaker.record_failure(classify(_http_error(429, headers={"Retry-After": "120"})))
        clock.now += 60.0
        with pytest.raises(TransportError):
            breaker.check()

    def test_a_success_resets_the_count(self):
        breaker = CircuitBreaker(threshold=2, clock=FakeClock())
        failure = classify(_http_error(503))
        breaker.record_failure(failure)
        breaker.record_success()
        breaker.record_failure(failure)
        breaker.check()

    def test_fatal_errors_do_not_trip_it(self):
        breaker = CircuitBreaker(threshold=1, clock=FakeClock())
        breaker.record_failure(classify(_http_error(401)))
        breaker.check()

    def test_policy_fails_fast_while_open(self):
        policy, clock = _policy(max_attempts=1)
        breaker = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock)
        calls = []

        def down():
            calls.append(1)
            raise _http_error(503)

        with pytest.raises(TransportError):
            policy.run(down, breaker=breaker)
        with pytest.raises(TransportError):
            policy.run(down, breaker=breaker)
        assert calls == [1]


def test_gate_is_shared_per_key_and_replaced_when_the_limit_changes():
    assert gate_for("test://gate", 2) is gate_for("test://gate", 2)
    assert gate_for("test://gate", 3) is not gate_for("test://gate-other", 3)
    gate = gate_for("test://gate", 1)
    assert gate.acquire(blocking=False) is True
    assert gate.acquire(blocking=False) is False
    gate.release()
