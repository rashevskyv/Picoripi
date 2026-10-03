"""REVIEW_QUEUE WP1 + WP6 6.5: a real block translation in the real window against a fake OpenAI-compatible server.

The application runs as it does for a person (``app_mode.headless`` off): the worker runs on its QThread, the
status dialog is shown, message boxes are answered by clicking their buttons.
"""
import json
import threading
import time

import pytest

from utils import app_mode
from utils.logging_utils import ai_traffic_log_path
from test_review._rq_wp1_6_helpers import (  # noqa: F401  (main_window is a fixture)
    BoxAnswerer,
    FakeAIServer,
    main_window,
    make_plain_project,
    open_project,
)

pytestmark = pytest.mark.serial

LINES = [f"Line {i} of the story." for i in range(30)]


strings_of = FakeAIServer.items_of
echo = FakeAIServer.echo_translation


@pytest.fixture
def server():
    srv = FakeAIServer(echo)
    yield srv
    srv.stop()


@pytest.fixture
def window(main_window, tmp_path, monkeypatch, qtbot, server):  # noqa: F811
    mw = main_window
    open_project(mw, make_plain_project(tmp_path, {"story": LINES}), monkeypatch, qtbot)
    monkeypatch.setattr(app_mode, "headless", False)
    mw.prompt_editor_enabled = False
    mw.log_ai_traffic = True
    ai_traffic_log_path().unlink(missing_ok=True)  # the settings directory is shared by the session
    configure(mw, server, workers=1)
    return mw


def configure(mw, server, workers, **provider):
    config = dict(mw.translation_config)
    config["provider"] = "openai"
    config["workers"] = workers
    config["providers"] = dict(config["providers"])
    config["providers"]["openai"] = {"endpoint": server.url, "model": "fake-model", "timeout": 60, **provider}
    mw.translation_config = config


def translated(mw):
    return [mw.data_processor.get_current_string_text(0, i)[0] for i in range(len(LINES))]


def traffic():
    path = ai_traffic_log_path()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class DetailSpy:
    """Keeps every detail line the status dialog is given, and whether the dialog was on screen then."""

    def __init__(self, dialog):
        self.lines = []
        original = dialog.set_detail_text

        def spy(text):
            self.lines.append((text, dialog.isVisible()))
            original(text)

        dialog.set_detail_text = spy


def start(mw):
    handler = mw.translation_handler
    handler.translate_current_block(block_idx=0)
    return handler


# ------------------------------------------------------------------ happy path


@pytest.mark.parametrize("workers", [1, 3])
def test_a_batch_of_30_lines_completes_and_logs_every_request_and_response(window, server, qtbot, workers):
    configure(window, server, workers=workers)
    answers = BoxAnswerer()
    handler = window.translation_handler
    detail = DetailSpy(handler.ui_handler.status_dialog)
    try:
        start(window)
        qtbot.waitUntil(lambda: translated(window) == ["UA " + line for line in LINES], timeout=15000)
        qtbot.waitUntil(lambda: not handler.is_ai_running, timeout=10000)
        qtbot.waitUntil(lambda: any("request(s)" in text for text, _ in detail.lines), timeout=5000)
    finally:
        answers.stop()

    assert len(server.requests) == 3                          # 30 lines, 12 per request
    assert not handler.ui_handler.status_dialog.is_running
    assert "AI Operation Failed" not in answers.titles()
    # The progress window showed where it was, chunk by chunk (sequential: the chapter / file / line detail).
    if workers == 1:
        assert [text for text, _ in detail.lines][:3] == [
            "File: story.bmg | Line: 0", "File: story.bmg | Line: 12", "File: story.bmg | Line: 24"
        ]
    records = traffic()
    requests = [r for r in records if r["event"] == "request"]
    responses = [r for r in records if r["event"] == "response"]
    assert len(requests) == len(responses) == 3
    assert sorted(r["request_id"] for r in requests) == sorted(r["request_id"] for r in responses)
    assert len({r["request_id"] for r in requests}) == 3
    assert all(isinstance(r.get("duration_ms"), int) for r in responses)
    assert sorted(r["chunk"] for r in responses) == [0, 1, 2]
    summary = [r for r in records if r["event"] == "summary"]
    assert len(summary) == 1 and summary[0]["summary"].startswith("3 request(s), p50 ")


def test_the_request_summary_is_shown_on_the_status_bar_at_the_end(window, server, qtbot):
    """The status window is gone by the time the worker sums up its requests, so the summary goes to the status bar."""
    from PyQt6.QtWidgets import QStatusBar
    configure(window, server, workers=3)
    answers = BoxAnswerer()
    status_bar = window.findChild(QStatusBar)
    try:
        start(window)
        qtbot.waitUntil(lambda: "request(s)" in status_bar.currentMessage(), timeout=15000)
    finally:
        answers.stop()
    assert status_bar.currentMessage().startswith("3 request(s), p50 ")


# ------------------------------------------------------------- the proxy fails


def first_id(body):
    return strings_of(body)[0]["id"]


def run_with_the_proxy_stopping(window, server, qtbot, workers):
    """The first chunk gets through, then the proxy is down; it is back when the user presses Retry."""
    configure(window, server, workers=workers, max_attempts=1)
    state = {"down": True}

    def reply(body):
        if state["down"] and first_id(body) != 0:
            return None
        return echo(body)

    server.reply = reply

    def click(box):
        if box["title"] == "AI Translation Error (Debug)":
            state["down"] = False
            return next(label for label in box["buttons"] if label.startswith("Retry"))
        return None

    answers = BoxAnswerer(click)
    handler = window.translation_handler
    try:
        start(window)
        qtbot.waitUntil(lambda: "AI Translation Error (Debug)" in answers.titles(), timeout=15000)
        kept_before_retry = translated(window)
        sent_before_retry = len(server.requests)
        qtbot.waitUntil(lambda: translated(window) == ["UA " + line for line in LINES], timeout=15000)
        qtbot.waitUntil(lambda: not handler.is_ai_running, timeout=10000)
    finally:
        answers.stop()
    error = next(box for box in answers.seen if box["title"] == "AI Translation Error (Debug)")
    retried = sorted(first_id(body) for body in server.requests[sent_before_retry:])
    return answers, error, kept_before_retry, retried


@pytest.mark.parametrize("workers", [1, 3])
def test_proxy_stopped_mid_run_keeps_finished_chunks_and_retry_sends_only_the_failed_ones(
        window, server, qtbot, workers):
    answers, error, kept_before_retry, retried = run_with_the_proxy_stopping(window, server, qtbot, workers)

    assert kept_before_retry == ["UA " + line for line in LINES[:12]] + LINES[12:]   # chunk 1 stays applied
    assert any(label.startswith("Retry (Wait") for label in error["buttons"])
    assert retried == [12, 24]                                # only the failed chunks are sent again
    assert "AI Operation Failed" not in answers.titles()
    if workers > 1:
        assert "2 of 3 chunks failed (chunk 2, 3)" in error["informative"]
        assert "the finished chunks are kept" in error["informative"]


def test_sequential_run_error_names_the_failed_chunk(window, server, qtbot):
    _, error, _, _ = run_with_the_proxy_stopping(window, server, qtbot, workers=1)
    assert "chunk 2" in error["informative"]


def test_a_429_shows_the_wait_the_proxy_asked_for_on_the_retry_button(window, server, qtbot):
    configure(window, server, workers=3, max_attempts=1)
    server.reply = lambda body: (429, {"Retry-After": "7"}, {"error": {"message": "Too Many Requests"}})
    answers = BoxAnswerer(lambda box: "Stop/Cancel AI" if box["title"] == "AI Translation Error (Debug)" else "OK")
    try:
        start(window)
        qtbot.waitUntil(lambda: "AI Operation Failed" in answers.titles(), timeout=15000)
    finally:
        answers.stop()
    error = next(box for box in answers.seen if box["title"] == "AI Translation Error (Debug)")
    assert "Retry (Wait 7s)" in error["buttons"]
    assert translated(window) == LINES


# --------------------------------------------------------------------- cancel


@pytest.mark.parametrize("workers", [1, 3])
def test_cancel_while_a_request_is_in_flight_closes_fast_and_asks_to_revert_not_an_error(window, server, qtbot, workers):
    configure(window, server, workers=workers)
    arrived = threading.Event()

    def reply(body):
        if first_id(body) != 0:
            arrived.set()
            server.release.wait(10)                # the proxy is still working on it
        return echo(body)

    server.reply = reply
    answers = BoxAnswerer(lambda box: "Yes")       # yes, cancel; yes, keep what was translated
    handler = window.translation_handler
    dialog = handler.ui_handler.status_dialog
    try:
        start(window)
        qtbot.waitUntil(lambda: arrived.is_set() and translated(window)[0] == "UA " + LINES[0], timeout=15000)
        assert dialog.isVisible()
        pressed = time.monotonic()
        dialog.cancel_button.click()
        qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=3000)
        closed_after = time.monotonic() - pressed
        qtbot.waitUntil(lambda: not handler.is_ai_running, timeout=5000)
    finally:
        server.release.set()
        answers.stop()

    assert closed_after < 1.0
    assert "Cancel AI operation?" in answers.titles()
    assert "Translation Cancelled" in answers.titles()           # the revert prompt
    revert = next(box for box in answers.seen if box["title"] == "Translation Cancelled")
    assert revert["text"] == "Keep the already translated parts?" and revert["modal"]
    assert not [box for box in answers.seen if box["icon"] in ("Critical", "Warning")]
    assert translated(window)[:12] == ["UA " + line for line in LINES[:12]]   # kept, as answered


# ------------------------------------------------------------------- think


@pytest.mark.parametrize("profile, expect_think", [(None, True), ("openai", False)])
def test_think_goes_to_a_self_hosted_endpoint_and_not_to_a_hosted_api(window, server, qtbot, profile, expect_think):
    """A self-hosted URL gets ``think``; an endpoint with ``"profile": "openai"`` (what api.openai.com is) does not."""
    configure(window, server, workers=1, **({"profile": profile} if profile else {}))
    answers = BoxAnswerer()
    try:
        start(window)
        qtbot.waitUntil(lambda: translated(window) == ["UA " + line for line in LINES], timeout=15000)
        qtbot.waitUntil(lambda: not window.translation_handler.is_ai_running, timeout=10000)
    finally:
        answers.stop()
    assert len(server.requests) == 3
    assert all(("think" in body) is expect_think for body in server.requests)
    if expect_think:
        assert {body["think"] for body in server.requests} == {1}
    else:
        assert all(body["response_format"] == {"type": "json_object"} for body in server.requests)


def test_api_openai_com_is_detected_as_hosted_and_gets_no_think():
    """No network: the body built for api.openai.com, through the same provider factory the window uses."""
    from core.translation.providers import create_translation_provider

    hosted = create_translation_provider("openai", {"endpoint": "https://api.openai.com/v1", "model": "gpt-4o-mini",
                                                    "api_key": "k"})
    body = hosted._prepare_body([{"role": "user", "content": "x"}], {"think": 1, "json": True, "timeout": 60})
    assert hosted.profile == "openai" and "think" not in body and "think_mode" not in body


def test_a_refused_reply_is_logged_against_its_chunk(window, server, qtbot):
    """A reply that comes back but is refused (no JSON here) gets an error record carrying its chunk number."""
    configure(window, server, workers=3, max_attempts=1)
    server.reply = lambda body: (200, {}, FakeAIServer.completion("no json at all")) if first_id(body) == 12 else echo(body)
    answers = BoxAnswerer(lambda box: "Stop/Cancel AI" if box["title"] == "AI Translation Error (Debug)" else "OK")
    try:
        start(window)
        qtbot.waitUntil(lambda: "AI Operation Failed" in answers.titles(), timeout=15000)
    finally:
        answers.stop()

    refused = [r for r in traffic() if r["event"] == "error" and r.get("chunk") == 1]
    assert refused and "JSON" in refused[0]["error"]
