"""Shared helpers for the WP1/WP6 review-queue tests: a real MainWindow with a project, a fake AI server."""
from __future__ import annotations

import http.server
import json
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pytest


# --------------------------------------------------------------------- projects

def make_plain_project(root: Path, blocks: Dict[str, List[str]], name: str = "RQ") -> Path:
    """A plain_text project on disk: one source .txt per block, translations auto-created. Returns the .uiproj."""
    from core.project_manager import ProjectManager

    source = root / "source"
    translation = root / "translation"
    source.mkdir(parents=True, exist_ok=True)
    translation.mkdir(parents=True, exist_ok=True)
    for block, lines in blocks.items():
        (source / f"{block}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (translation / f"{block}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manager = ProjectManager()
    assert manager.create_new_project(
        project_dir=root / "project",
        name=name,
        plugin_name="plain_text",
        source_path=str(source),
        translation_path=str(translation),
        is_directory_mode=True,
        auto_create_translations=True,
    )
    return root / "project" / "project.uiproj"


def new_main_window(qtbot):
    """A real MainWindow, registered with qtbot."""
    from main import MainWindow

    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    return mw


@pytest.fixture
def main_window(qtbot):
    """A real MainWindow that is closed inside the test, while the user-file isolation is still in force.

    Left to qtbot's teardown, the close event writes settings to the real ~/.picoripi.
    Import it into a test module (``from test_review._rq_wp1_6_helpers import main_window``) to use it.
    """
    mw = new_main_window(qtbot)
    yield mw
    # With app_mode.headless off, closing can ask (unsaved changes...): answer without saving.
    answers = BoxAnswerer(lambda box: next(
        (label for label in ("Discard", "Don't Save", "No", "Close Anyway", "OK") if label in box["buttons"]), None))
    try:
        mw.close()
    except RuntimeError:
        pass
    finally:
        answers.stop()


def open_project(mw, project_file: Path, monkeypatch, qtbot, wait: bool = True) -> None:
    """Open ``project_file`` through File > Open Project, the file dialog answered."""
    import handlers.project_action.lifecycle_mixin as lifecycle

    monkeypatch.setattr(
        lifecycle.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(project_file), ""))
    )
    mw.project_action_handler.open_project_action()
    if wait:
        qtbot.waitUntil(lambda: len(mw.data_store.data) > 0 and not mw.is_loading_data, timeout=15000)


# ------------------------------------------------------------- fake AI server

class FakeAIServer:
    """A stdlib OpenAI-compatible server on 127.0.0.1.

    ``reply(body) -> (status, headers, payload_dict_or_bytes)`` decides each answer (None drops the connection
    without one, as a proxy that was stopped does); the default echoes every string of a block-translation
    request back as ``"UA " + text``. ``requests`` keeps every parsed body.
    """

    def __init__(self, reply: Optional[Callable] = None):
        self.requests: List[dict] = []
        self.gets: List[str] = []  # paths of GET requests (/healthz)
        self.reply = reply or self.echo_translation
        self.lock = threading.Lock()
        self.release = threading.Event()  # tests that hold a request open wait on this
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                with server.lock:
                    server.requests.append(body)
                answer = server.reply(body)
                if answer is None:  # a proxy that died: the connection closes without an answer
                    self.close_connection = True
                    return
                status, headers, payload = answer
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    for key, value in (headers or {}).items():
                        self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

            def do_GET(self):
                server.gets.append(self.path)
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def stop(self) -> None:
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()

    # -- canned replies

    @staticmethod
    def items_of(body: dict) -> list:
        """The strings a block-translation request asks for (``[{"id", "text"}]``)."""
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        _, _, data = user.partition("JSON DATA TO PROCESS:")
        start = data.index("{")
        payload, _ = json.JSONDecoder().raw_decode(data[start:])
        return payload["strings_to_translate"]

    @staticmethod
    def completion(text: str) -> dict:
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}

    @classmethod
    def echo_translation(cls, body: dict):
        """Every string of the request back as "UA " + text."""
        items = cls.items_of(body)
        out = {"translated_strings": [{"id": item["id"], "translation": "UA " + item["text"]} for item in items]}
        return 200, {}, cls.completion(json.dumps(out, ensure_ascii=False))


def wait_for(predicate: Callable[[], bool], timeout: float = 10.0) -> bool:
    """Poll a predicate from a plain thread (no event loop)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ------------------------------------------------------------- message boxes

class BoxAnswerer:
    """Answers the message boxes the application opens, the way a person would: by clicking a button.

    Works for modal boxes inside their own ``exec()`` loop too, because it runs on a timer. ``policy(box)``
    gets ``{"title", "text", "buttons", "modal"}`` and returns the label of the button to click (``&`` ignored)
    or None to close the box. Every box seen is kept in ``seen``.
    """

    def __init__(self, policy: Optional[Callable[[dict], Optional[str]]] = None, dialogs: Optional[dict] = None):
        from PyQt6.QtCore import QObject, QTimer

        self.policy = policy or (lambda box: None)
        # Other dialogs by class name: {"TranslationVariationsDialog": fn(dialog)}.
        self.dialogs = dialogs or {}
        self.seen: List[dict] = []
        self.owner = QObject()
        self.timer = QTimer(self.owner)
        self.timer.timeout.connect(self._tick)
        self.timer.start(20)

    def stop(self) -> None:
        self.timer.stop()

    def _tick(self) -> None:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        for widget in QApplication.topLevelWidgets():
            if not widget.isVisible() or widget.property("rq_seen"):
                continue
            handler = self.dialogs.get(type(widget).__name__)
            if handler is not None:
                widget.setProperty("rq_seen", True)
                self.seen.append({"title": widget.windowTitle(), "dialog": type(widget).__name__})
                handler(widget)
                continue
            if not isinstance(widget, QMessageBox):
                continue
            widget.setProperty("rq_seen", True)
            box = {
                "title": widget.windowTitle(),
                "text": widget.text(),
                "informative": widget.informativeText(),
                "buttons": [button.text().replace("&", "") for button in widget.buttons()],
                "modal": widget.isModal(),
                "icon": widget.icon().name,
                "at": time.monotonic(),
            }
            self.seen.append(box)
            choice = self.policy(box)
            target = next((b for b in widget.buttons() if b.text().replace("&", "") == choice), None)
            if target is not None:
                target.click()
            else:
                widget.close()

    def titles(self) -> List[str]:
        return [box["title"] for box in self.seen]
