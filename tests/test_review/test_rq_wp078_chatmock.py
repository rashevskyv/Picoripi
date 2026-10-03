"""Review queue WP7: the ChatMock setup in wiki 5 against the provider code, with a fake ChatMock on 127.0.0.1.

Wiki 5: Active Provider "OpenAI Compatible", Endpoint http://127.0.0.1:8000/v1, any non-empty API key,
Model gpt-5, then Test Provider. The fake answers like an OpenAI-compatible server and has no /healthz.
"""
import http.server
import json
import threading

import pytest

from core.translation.config import build_default_translation_config
from core.translation.providers import create_translation_provider
from ui.settings.provider_worker import ProviderTestWorker
from utils import app_mode


@pytest.fixture
def chatmock():
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
            reply = json.dumps({"id": "chatcmpl-1", "object": "chat.completion", "model": body.get("model"),
                                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Test"},
                                             "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

        def do_GET(self):
            seen.append({"path": self.path})
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1", seen
    server.shutdown()
    server.server_close()
    thread.join(5)


def wiki_settings(endpoint):
    settings = dict(build_default_translation_config()["providers"]["openai"])
    settings.update(endpoint=endpoint, api_key="sk-anything", model="gpt-5")
    return settings


def test_the_wiki_setup_passes_test_provider(chatmock, qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    endpoint, seen = chatmock
    worker = ProviderTestWorker("openai", wiki_settings(endpoint))       # "OpenAI Compatible" -> key "openai"

    with qtbot.waitSignal(worker.finished_signal, timeout=10000) as signal:
        worker.start()
    qtbot.waitUntil(worker.isFinished, timeout=5000)

    assert signal.args == [True, "Test"]
    (request,) = seen
    assert request["path"] == "/v1/chat/completions"
    assert request["auth"] == "Bearer sk-anything"
    assert request["body"]["model"] == "gpt-5"


def test_a_translation_request_to_chatmock_and_what_rides_along(chatmock):
    """A loopback endpoint is treated as a Web2API proxy: Picoripi adds `think` and probes /healthz.
    ChatMock has no /healthz (404 here) -- the worker count is then left as the user set it."""
    endpoint, seen = chatmock
    provider = create_translation_provider("openai", wiki_settings(endpoint))

    assert provider.profile == "web2api"
    assert provider.clamp_workers(4) == 4
    response = provider.translate([{"role": "user", "content": "Hi"}], settings_override={"think": 1, "json": True})

    assert response.text == "Test"
    posted = [r for r in seen if r["path"] == "/v1/chat/completions"][0]["body"]
    assert posted["think"] == 1                     # a Web2API field ChatMock is sent and must ignore
    assert "response_format" not in posted          # JSON mode is only asked of the hosted OpenAI API
    assert {"path": "/healthz"} in seen
