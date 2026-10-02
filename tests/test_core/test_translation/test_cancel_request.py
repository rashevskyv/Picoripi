"""A request that is already waiting for its answer can be cancelled."""
import http.server
import threading
import time

import pytest

from core.translation.providers import OpenAIProvider
from core.translation.transport import ErrorKind, TransportError, run_cancellable


@pytest.fixture
def slow_server():
    class Slow(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            time.sleep(5)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"choices": [{"message": {"content": "late"}}]}')
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def test_cancel_returns_in_under_a_second_while_the_server_is_still_working(slow_server):
    cancelled = threading.Event()
    provider = OpenAIProvider({"endpoint": slow_server, "model": "m"})
    provider.enable_retries(cancelled.is_set)
    threading.Timer(0.5, cancelled.set).start()

    started = time.monotonic()
    with pytest.raises(TransportError) as info:
        provider.translate([{"role": "user", "content": "Hi"}])

    assert info.value.kind is ErrorKind.CANCELLED
    assert time.monotonic() - started < 1.5  # 0.5 s until the cancel, then at most one poll


def test_run_cancellable_passes_results_and_errors_through():
    assert run_cancellable(lambda: 42, lambda: False) == 42
    assert run_cancellable(lambda: 42, None) == 42
    with pytest.raises(KeyError):
        run_cancellable(lambda: {}["missing"], lambda: False)
