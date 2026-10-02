"""ai_traffic.log: JSON Lines, one writer at a time, rolled over instead of truncated."""
import json
import threading
from types import SimpleNamespace

import utils.constants as constants
import utils.logging_utils as logging_utils
from core.translation.transport import ErrorKind, TransportError

MW = SimpleNamespace(log_ai_traffic=True)
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "привіт"}]


def _records():
    path = logging_utils.ai_traffic_log_path()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_log_lives_in_the_settings_dir_not_the_working_directory():
    assert logging_utils.ai_traffic_log_path() == constants.SETTINGS_DIR / "ai_traffic.log"


def test_request_response_and_error_records():
    logging_utils.log_ai_traffic(MW, "translate", MESSAGES, request_id="ab12", chunk=3, attempt=2)
    logging_utils.log_ai_traffic(MW, "translate", MESSAGES, response_text="готово", request_id="ab12", duration_ms=1500)
    error = TransportError("429 Too Many Requests", kind=ErrorKind.RATE_LIMIT, status=429)
    logging_utils.log_ai_traffic(MW, "translate", MESSAGES, error=error, request_id="cd34")

    request, response, failure = _records()[-3:]
    assert request["event"] == "request" and request["messages"] == MESSAGES
    assert (request["request_id"], request["chunk"], request["attempt"]) == ("ab12", 3, 2)
    assert request["chars_in"] == len("sys") + len("привіт")
    assert response["event"] == "response" and response["response"] == "готово"
    assert (response["request_id"], response["chars_out"], response["duration_ms"]) == ("ab12", 6, 1500)
    assert "messages" not in response
    assert (failure["event"], failure["kind"], failure["status"]) == ("error", "rate_limit", 429)


def test_nothing_is_written_when_the_setting_is_off():
    path = logging_utils.ai_traffic_log_path()
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    logging_utils.log_ai_traffic(SimpleNamespace(log_ai_traffic=False, settings_manager=None), "translate", MESSAGES)
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    assert after == before


def test_parallel_writers_never_interleave_lines():
    path = logging_utils.ai_traffic_log_path()
    start = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
    payload = "x" * 4000

    def write(worker):
        for n in range(40):
            logging_utils.log_ai_traffic(MW, "t", MESSAGES, response_text=payload, request_id=f"{worker}-{n}")

    threads = [threading.Thread(target=write, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    records = _records()[start:]  # every line parses, or json.loads raised above
    assert len(records) == 8 * 40
    assert {r["request_id"] for r in records} == {f"{w}-{n}" for w in range(8) for n in range(40)}


def test_a_full_log_is_rolled_over_not_truncated(monkeypatch):
    path = logging_utils.ai_traffic_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"event": "old run"}\n', encoding="utf-8")
    monkeypatch.setattr(logging_utils, "AI_TRAFFIC_MAX_BYTES", 5)

    logging_utils.log_ai_traffic(MW, "translate", MESSAGES)

    assert "old run" in path.with_name(path.name + ".1").read_text(encoding="utf-8")
    assert [r["event"] for r in _records()] == ["request"]
