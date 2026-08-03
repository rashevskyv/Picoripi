"""Retry policy for the pipeline's AI calls: what is transient, and the backoff."""
import pytest

from core.glossary_build.retry import backoff_delays, call_with_retry, is_transient


class TestIsTransient:
    @pytest.mark.parametrize("message", [
        # The failure that prompted this: a proxy relaying an upstream rate limit.
        '502 Server Error: Bad Gateway for url: http://localhost:8081/v1/chat/'
        'completions - {"error": {"message": "upstream error: HTTP Error 429: '
        'Too Many Requests"}}',
        "429 Client Error: Too Many Requests",
        "503 Server Error: Service Unavailable",
        "Request timed out after 60 seconds.",
        "Model is overloaded, try again later",
        "Connection aborted",
    ])
    def test_retryable(self, message):
        assert is_transient(message) is True

    @pytest.mark.parametrize("message", [
        "401 Client Error: Unauthorized",
        "404 Client Error: Not Found for url: http://localhost:8081/v1/models",
        "OpenAI API key is not set",
        "Failed to parse AI response",
    ])
    def test_not_retryable(self, message):
        assert is_transient(message) is False

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 405, 422])
    def test_a_relayed_permanent_status_beats_the_502_wrapping_it(self, code):
        """A proxy reports its own trouble as 502 and quotes the real answer.

        Retrying a relayed 405 eighteen times spends three minutes proving what
        the first attempt already said: the request is wrong.
        """
        message = (
            f"502 Server Error: Bad Gateway for url: http://localhost:8081/v1/chat/"
            f'completions - {{"error": {{"message": "upstream error: HTTP Error {code}: nope"}}}}'
        )
        assert is_transient(message) is False

    @pytest.mark.parametrize("code", [429, 500, 502, 503])
    def test_a_relayed_transient_status_is_still_retried(self, code):
        message = (
            f"502 Server Error: Bad Gateway for url: http://localhost:8081/v1/chat/"
            f'completions - {{"error": {{"message": "upstream error: HTTP Error {code}: busy"}}}}'
        )
        assert is_transient(message) is True

    def test_bare_number_is_not_a_status_code(self):
        """A port or token count must not be read as a server error."""
        assert is_transient("connecting to http://localhost:5002/v1") is False
        assert is_transient("context window exceeded: 502 tokens over") is False


class TestBackoffDelays:
    def test_doubles_and_caps(self):
        assert backoff_delays(6, base=2.0, cap=60.0) == [2.0, 4.0, 8.0, 16.0, 32.0]
        assert backoff_delays(8, base=2.0, cap=16.0) == [2.0, 4.0, 8.0, 16.0, 16.0, 16.0, 16.0]

    def test_one_attempt_never_waits(self):
        assert backoff_delays(1) == []


class TestCallWithRetry:
    def test_returns_first_success_without_sleeping(self):
        slept = []
        assert call_with_retry(lambda: "ok", sleep=slept.append) == "ok"
        assert slept == []

    def test_recovers_after_transient_failures(self):
        calls = []
        slept = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("429 Client Error: Too Many Requests")
            return "ok"

        assert call_with_retry(flaky, attempts=6, base=2.0, sleep=slept.append) == "ok"
        assert len(calls) == 3
        assert slept == [2.0, 4.0]

    def test_non_transient_aborts_immediately(self):
        slept = []
        calls = []

        def broken():
            calls.append(1)
            raise RuntimeError("401 Client Error: Unauthorized")

        with pytest.raises(RuntimeError):
            call_with_retry(broken, attempts=6, sleep=slept.append)
        assert calls == [1]
        assert slept == []

    def test_raises_once_attempts_are_spent(self):
        slept = []

        def always_429():
            raise RuntimeError("429 Client Error: Too Many Requests")

        with pytest.raises(RuntimeError, match="429"):
            call_with_retry(always_429, attempts=3, base=1.0, sleep=slept.append)
        assert slept == [1.0, 2.0]

    def test_cancelling_stops_the_backoff(self):
        cancelled = []

        def always_429():
            raise RuntimeError("429 Client Error: Too Many Requests")

        with pytest.raises(RuntimeError):
            call_with_retry(
                always_429,
                attempts=6,
                base=1.0,
                sleep=lambda _s: cancelled.append(True),
                is_cancelled=lambda: bool(cancelled),
            )
        # One backoff happened, then the cancel flag stopped the loop.
        assert len(cancelled) == 1

    def test_on_retry_reports_each_wait(self):
        seen = []
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("502 Server Error: Bad Gateway")
            return "ok"

        call_with_retry(
            flaky,
            attempts=4,
            base=2.0,
            sleep=lambda _s: None,
            on_retry=lambda attempt, delay, exc: seen.append((attempt, delay)),
        )
        assert seen == [(1, 2.0)]
