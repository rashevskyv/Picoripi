"""WP3 review-queue helpers: a scripted OpenAI-compatible server and the real Companion server on 127.0.0.1."""
from __future__ import annotations

import contextlib
import http.server
import json
import shutil
import socket
import threading
from pathlib import Path
from typing import Callable, List, Optional

from core.glossary_manager import GlossaryManager

REAL_GLOSSARY = Path("translation_prompts/glossary.json")


def glossary_copy(tmp_path: Path) -> Path:
    """A copy of the shipped glossary; the real file is never written."""
    path = tmp_path / "glossary.json"
    shutil.copyfile(REAL_GLOSSARY, path)
    return path


def load(path: Path) -> GlossaryManager:
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=path.read_text(encoding="utf-8"))
    return manager


def kind_of(messages: list) -> str:
    """Which build pass a request belongs to, read from its system prompt."""
    system, user = messages[0]["content"], messages[-1]["content"]
    if system.startswith("You build a translation glossary"):
        return "extract"
    if system.startswith("You translate a single glossary term"):
        return "translate"
    if system.startswith("You keep the glossary"):
        return "reconcile"
    if system.startswith("You identify video game characters"):
        return "name"
    return "describe" if "Excerpts where it appears" in user else "fold"


def field(user: str, label: str) -> str:
    """The value on the ``label: value`` line of a prompt."""
    for line in user.splitlines():
        if line.startswith(label + ":"):
            return line[len(label) + 1:].strip()
    return ""


def reconcile_terms(user: str) -> List[str]:
    listing = json.loads(user[user.index("["):user.rindex("]") + 1])
    return [row["term"] for row in listing]


class FakeOpenAI:
    """``/v1/chat/completions`` answered by ``reply(messages)``; every request body is kept.

    ``reply`` may return an int to answer with that HTTP status instead.
    """

    def __init__(self, reply: Callable[[list], object]) -> None:
        self.reply = reply
        self.requests: List[list] = []
        self._lock = threading.Lock()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                messages = body["messages"]
                with owner._lock:
                    owner.requests.append(messages)
                answer = owner.reply(messages)
                if isinstance(answer, int):
                    self.send_response(answer)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                payload = json.dumps({"choices": [{"message": {"content": answer}}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def of_kind(self, kind: str) -> List[str]:
        """User prompts of one pass, in arrival order."""
        with self._lock:
            return [m[-1]["content"] for m in self.requests if kind_of(m) == kind]

    def __enter__(self) -> "FakeOpenAI":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


@contextlib.contextmanager
def companion_server(data_dir: Path, token: str):
    """The real Companion FastAPI app under uvicorn on a free local port. Yields its base URL."""
    import uvicorn

    from companion.server.main import create_app

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(data_dir=data_dir, auth_token=token), log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    started = threading.Event()

    def wait() -> Optional[bool]:
        for _ in range(500):
            if server.started:
                return True
            started.wait(0.01)
        return None

    assert wait(), "the Companion server did not start"
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
