"""Review queue WP8: Picoripi's real OpenAI-compatible provider against the real WP8 proxy (Google stubbed).

The proxy runs in a subprocess from the WP8 worktree (see _rq_wp078_helpers.py); the tests
skip when that worktree is not on disk. Nothing leaves 127.0.0.1.
"""
import json
import threading
import time

import pytest

from core.translation.config import build_default_translation_config
from core.translation.providers import OpenAIProvider, create_translation_provider
from core.translation.transport import ErrorKind, TransportError
from handlers.translation.ai_worker import AIWorker
from . import _rq_wp078_helpers as helpers
from utils import app_mode

pytestmark = pytest.mark.skipif(not (helpers.PROXY_ROOT / "gemini_web2api").is_dir(),
                                reason="the WP8 proxy worktree is not on this machine")


@pytest.fixture
def start(tmp_path):
    started = []

    def run(**options):
        proxy = helpers.start_proxy(tmp_path / f"proxy{len(started)}", **options)
        started.append(proxy)
        return proxy

    yield run
    for proxy in started:
        proxy.stop()


def provider_settings(proxy) -> dict:
    """The "openai" provider block of the default config, pointed at the proxy as a user would."""
    settings = dict(build_default_translation_config()["providers"]["openai"])
    settings.update(endpoint=proxy.base_url, model="gemini-3.6-flash")
    return settings


class _Composer:
    """The three things a chunked run asks of its prompt composer; the request body is the chunk's items."""
    mw = None

    def _get_mempalace_client(self):
        return None

    def _get_wing_name(self):
        return "wing"

    def _get_block_label(self, block_idx):
        return f"block{block_idx}"

    def compose_batch_request(self, **kwargs):
        return "Translate into Ukrainian.", json.dumps(kwargs.get("source_items", []), ensure_ascii=False), "json"


def run_chunked(provider, item_count, workers):
    items = [{"id": i, "text": f"Line {i}"} for i in range(item_count)]
    worker = AIWorker(provider, _Composer(), {
        "type": "translate_block_chunked", "block_idx": 0, "source_items": items, "workers": workers,
        "enable_editor_review": False,
        "composer_args": {"system_prompt": "sys", "block_idx": 0, "mode_description": "block 1"},
    })
    chunks, errors = {}, []
    worker.chunk_translated.connect(lambda idx, text, ctx: chunks.__setitem__(idx, text))
    worker.error.connect(lambda message, ctx: errors.append(message))
    worker.run()
    return chunks, errors


def translated_ids(chunks) -> list:
    ids = []
    for text in chunks.values():
        ids.extend(row["id"] for row in json.loads(text)["translated_strings"])
    return sorted(ids)


# ------------------------------------------------------------------------------------- Test Provider


def test_test_provider_gets_its_answer_through_the_proxy(start, qtbot, monkeypatch):
    """The Settings button's worker (a real QThread) against the proxy: success and the model's word."""
    from ui.settings.provider_worker import ProviderTestWorker
    monkeypatch.setattr(app_mode, "headless", False)
    proxy = start(accounts=1)

    worker = ProviderTestWorker("openai", provider_settings(proxy))
    with qtbot.waitSignal(worker.finished_signal, timeout=15000) as signal:
        worker.start()
    qtbot.waitUntil(worker.isFinished, timeout=5000)

    assert signal.args == [True, "Test"]
    assert '"POST /v1/chat/completions HTTP/1.1" 200' in proxy.log()


# ------------------------------------------------------------------------------------- one translation


def test_a_ukrainian_translation_round_trips_as_utf8_in_a_temporary_chat(start):
    proxy = start(accounts=1)
    provider = create_translation_provider("openai", provider_settings(proxy))

    response = provider.translate([
        {"role": "system", "content": "Translate into Ukrainian."},
        {"role": "user", "content": json.dumps([{"id": 7, "text": "Їжак узяв ґанок"}], ensure_ascii=False)},
    ], settings_override={"think": 1, "json": True})

    assert provider.profile == "web2api"
    assert json.loads(response.text) == {"translated_strings": [{"id": 7, "translation": "Переклад 7"}]}
    (call,) = [c for c in proxy.calls() if c["event"] == "start"]
    assert call["temporary"] == [1]                       # a temporary Gemini chat
    assert call["utf8"] is True                           # the Cyrillic went out as UTF-8 bytes


def test_a_chunked_block_translation_round_trips_through_the_proxy(start):
    proxy = start(accounts=2)
    provider = create_translation_provider("openai", provider_settings(proxy))

    chunks, errors = run_chunked(provider, item_count=30, workers=1)

    assert errors == []
    assert translated_ids(chunks) == list(range(30))
    assert "Переклад 0" in "".join(chunks.values())


# ------------------------------------------------------------------------------------- Parallel Requests cap


def test_parallel_requests_are_capped_by_the_proxy_s_usable_accounts(start):
    """Six workers asked, two accounts: two requests at a time reach Gemini and none is refused."""
    proxy = start(accounts=2, hold=0.3)
    provider = create_translation_provider("openai", provider_settings(proxy))

    assert provider.clamp_workers(6) == 2
    chunks, errors = run_chunked(provider, item_count=96, workers=6)

    assert errors == []
    assert translated_ids(chunks) == list(range(96))
    assert proxy.peak_concurrency() == 2
    assert " 429 " not in proxy.log()


# ------------------------------------------------------------------------------------- 429 server_busy


def test_a_server_busy_answer_is_waited_out_and_the_request_then_succeeds(start):
    """Two requests, one account, no queue in the proxy: the second gets 429 + Retry-After, waits, retries."""
    proxy = start(accounts=1, hold=0.6, average_sec=1.0, config={"max_queued_requests": 0})
    provider = OpenAIProvider(provider_settings(proxy))
    provider.enable_retries(lambda: False)
    results, errors = {}, []

    def ask(name):
        try:
            started = time.monotonic()
            text = provider.translate([{"role": "user", "content": json.dumps([{"id": name}])}]).text
            results[name] = (text, time.monotonic() - started)
        except Exception as exc:  # recorded for the assertion below
            errors.append(exc)

    first = threading.Thread(target=ask, args=(1,))
    first.start()
    deadline = time.monotonic() + 10
    while not any(c["event"] == "start" for c in proxy.calls()) and time.monotonic() < deadline:
        time.sleep(0.02)
    second = threading.Thread(target=ask, args=(2,))
    second.start()
    first.join(20)
    second.join(20)

    assert errors == []
    assert json.loads(results[2][0])["translated_strings"][0]["id"] == 2
    assert results[2][1] >= 1.0                                   # it waited out Retry-After: 1
    assert results[2][1] < 10                                     # and did not run into a timeout
    log = proxy.log()
    assert log.count('"POST /v1/chat/completions HTTP/1.1" 429') == 1
    assert log.count('"POST /v1/chat/completions HTTP/1.1" 200') == 2


def test_a_bulk_run_with_more_workers_than_the_proxy_admits_finishes_without_errors(start):
    """The proxy admits one request at a time although two accounts are healthy (max_concurrent_requests=1),
    so Picoripi's two workers overrun it; the default proxy queue holds the extra one instead of refusing it."""
    proxy = start(accounts=2, hold=0.2, average_sec=1.0, config={"max_concurrent_requests": 1})
    provider = create_translation_provider("openai", provider_settings(proxy))

    chunks, errors = run_chunked(provider, item_count=48, workers=2)

    assert errors == []
    assert translated_ids(chunks) == list(range(48))
    assert proxy.peak_concurrency() == 1


def test_a_bulk_run_that_meets_429_server_busy_backs_off_and_finishes(start):
    """As above with no proxy queue: the overrun requests get 429 + Retry-After. Picoripi must back off and
    still translate every chunk instead of failing them."""
    proxy = start(accounts=2, hold=0.2, average_sec=1.0,
                  config={"max_concurrent_requests": 1, "max_queued_requests": 0})
    provider = create_translation_provider("openai", provider_settings(proxy))

    chunks, errors = run_chunked(provider, item_count=48, workers=2)

    def saw_429():
        return '" 429 ' in proxy.log() or "HTTP/1.1\" 429" in proxy.log()

    deadline = time.monotonic() + 10                              # the proxy's log reaches the file a bit later
    while not saw_429() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert saw_429(), proxy.log()
    assert errors == []
    assert translated_ids(chunks) == list(range(48))


# ------------------------------------------------------------------------------------- cancel


def test_cancelling_a_long_request_makes_the_proxy_drop_it(start):
    """REVIEW_QUEUE: 'Cancel in Picoripi during a long request: the proxy log must show
    client disconnected; the request was dropped instead of going on to the next account.'"""
    proxy = start(accounts=2, fail_first_after=1.5)
    provider = OpenAIProvider(provider_settings(proxy))
    cancelled = threading.Event()
    provider.enable_retries(cancelled.is_set)
    threading.Timer(0.4, cancelled.set).start()

    with pytest.raises(TransportError) as info:
        provider.translate([{"role": "user", "content": "a long request"}])
    assert info.value.kind is ErrorKind.CANCELLED

    deadline = time.monotonic() + 10                              # the proxy decides after its first attempt
    while time.monotonic() < deadline and "the request was dropped" not in proxy.log() \
            and len([c for c in proxy.calls() if c["event"] == "end"]) < 2:
        time.sleep(0.05)
    assert "client disconnected; the request was dropped" in proxy.log()
    assert len([c for c in proxy.calls() if c["event"] == "start"]) == 1
