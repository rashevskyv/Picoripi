"""ask_ai: one request to the translation provider of settings.json, here a local OpenAI-compatible server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from mcp_server import tools


class _Proxy(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        self.seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = json.dumps({"id": "1", "choices": [{"message": {"role": "assistant", "content": "Привіт"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_ask_ai_sends_the_prompt_to_the_configured_provider_and_returns_the_reply(tmp_path):
    server = HTTPServer(("127.0.0.1", 0), _Proxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1"
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"translation_config": {"provider": "openai", "providers": {
            "openai": {"endpoint": url, "base_url": url, "model": "gemini-test", "timeout": 10}}}}), encoding="utf-8")
        reply = tools.ask_ai("Hello", system="Translate to Ukrainian.", settings_path=settings)
    finally:
        server.shutdown()
    assert reply == {"provider": "openai", "model": "gemini-test", "text": "Привіт"}
    assert [m["content"] for m in _Proxy.seen[0]["messages"]] == ["Translate to Ukrainian.", "Hello"]


def test_ask_ai_without_provider_settings_says_so(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"translation_config": {"provider": "openai"}}), encoding="utf-8")
    assert "no settings" in tools.ask_ai("Hello", settings_path=settings)["error"]
