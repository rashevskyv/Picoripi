"""Review-queue WP8 x Picoripi: the WP8 proxy in a subprocess on 127.0.0.1 with Google stubbed out.

Run as a script, this file starts ``gemini_web2api`` from the WP8 worktree with a stub in
place of the one call that reaches gemini.google.com (``gemini.post_no_redirect``), the
build-label fetch and the start-up probes left out, and every non-loopback name lookup
refused. Everything else -- handler, gate, rotation, payload, response parser -- is the
proxy's real code. Imported, it gives tests ``start_proxy()``.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

PROXY_ROOT = Path(os.environ.get("RQ_WP8_PROXY_ROOT", r"D:\git\dev\gemini-web2api-wp8"))


def gemini_frame(text: str) -> bytes:
    """A StreamGenerate body as the proxy's extract_response_text reads it."""
    inner = [None, ["c_stub", "r_stub"], None, None, [["rc_stub", [text]]], "x" * 250]
    line = json.dumps([["wrb.fr", None, json.dumps(inner, ensure_ascii=False)]], ensure_ascii=False)
    return (")]}'\n\n" + str(len(line)) + "\n" + line + "\n").encode("utf-8")


def stub_answer(prompt: str) -> str:
    """What the fake Gemini says: "Test" to the provider test, a JSON translation to a chunk."""
    if 'Say the word "Test"' in prompt:
        return "Test"
    ids = [int(i) for i in re.findall(r'"id":\s*(\d+)', prompt)]
    if ids:
        return json.dumps({"translated_strings": [{"id": i, "translation": f"Переклад {i}"} for i in ids]},
                          ensure_ascii=False)
    return "Переклад"


# ------------------------------------------------------------------------------------------- test side


class ProxyProcess:
    def __init__(self, process, port, state_dir: Path):
        self.process = process
        self.port = port
        self.state_dir = state_dir
        self.base_url = f"http://127.0.0.1:{port}/v1"

    def log(self) -> str:
        return (self.state_dir / "proxy.log").read_text(encoding="utf-8", errors="replace")

    def calls(self) -> list:
        path = self.state_dir / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def peak_concurrency(self) -> int:
        return max((call["inflight"] for call in self.calls() if call["event"] == "start"), default=0)

    def stop(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(10)
        for stream in (self.process.stdout, self.process.stderr):
            if stream:
                stream.close()


def start_proxy(state_dir: Path, *, accounts: int = 2, hold: float = 0.0, fail_first_after: float = None,
                average_sec: float = None, config: dict = None) -> ProxyProcess:
    """Start the proxy on a free loopback port and wait until it listens."""
    state_dir.mkdir(parents=True, exist_ok=True)
    spec = {"root": str(PROXY_ROOT), "dir": str(state_dir), "accounts": accounts, "hold": hold,
            "fail_first_after": fail_first_after, "average_sec": average_sec, "config": config or {}}
    log = open(state_dir / "proxy.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, __file__, json.dumps(spec)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=log, cwd=str(state_dir), env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    log.close()
    line = process.stdout.readline().decode().strip()
    if not line.startswith("PORT "):
        process.kill()
        raise RuntimeError(f"the proxy did not start: {line!r}\n" + (state_dir / "proxy.log").read_text(errors="replace"))
    return ProxyProcess(process, int(line.split()[1]), state_dir)


# ------------------------------------------------------------------------------------------- proxy side


def _serve(spec: dict) -> None:
    sys.path.insert(0, spec["root"])
    real_getaddrinfo = socket.getaddrinfo

    def offline(host, *args, **kwargs):
        if host is not None and str(host) not in ("127.0.0.1", "::1", "localhost"):
            raise socket.gaierror(f"offline: no lookup of {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = offline

    from gemini_web2api import config, gate, gemini
    from gemini_web2api.accounts import UpstreamError
    from gemini_web2api.server import GeminiHandler, ThreadedServer

    state = Path(spec["dir"])
    settings = {"host": "127.0.0.1", "startup_check": False, "captcha_open_browser": False, "log_requests": True,
                "min_request_gap_sec": 0, "max_request_gap_sec": 0, "min_account_gap_sec": 0,
                "max_account_gap_sec": 0, "retry_delay_sec": 0.5}
    settings.update(spec["config"])
    (state / "config.json").write_text(json.dumps(settings), encoding="utf-8")
    rows = [{"id": f"acc{i}", "name": f"acc{i}", "cookie": f"SAPISID=s{i}; NID=n{i}", "sapisid": f"s{i}",
             "auth_user": "0", "xsrf_token": "tok", "proxy": None, "status": "active", "cooldown_until": 0,
             "error_message": ""} for i in range(spec["accounts"])]
    (state / "accounts.json").write_text(json.dumps({"accounts": rows, "auto_rotate": True}), encoding="utf-8")
    config.load_config(str(state / "config.json"))
    if spec["average_sec"]:
        gate.GATE._average_sec = float(spec["average_sec"])

    lock = threading.Lock()
    counters = {"calls": 0, "inflight": 0}
    calls_file = open(state / "calls.jsonl", "a", encoding="utf-8")

    def record(event, **fields):
        with lock:
            calls_file.write(json.dumps(dict(fields, event=event, t=time.time()), ensure_ascii=False) + "\n")
            calls_file.flush()

    def post(url, body, headers, timeout, proxy=None):
        assert url.startswith("https://gemini.google.com/")
        form = urllib.parse.parse_qs(body.decode("ascii"))
        inner = json.loads(json.loads(form["f.req"][0])[1])
        prompt = inner[0][0]
        with lock:
            counters["calls"] += 1
            counters["inflight"] += 1
            number, inflight = counters["calls"], counters["inflight"]
        record("start", number=number, inflight=inflight, temporary=inner[41], utf8="%D0" in body.decode("ascii"))
        try:
            if spec["fail_first_after"] is not None and number == 1:
                time.sleep(spec["fail_first_after"])
                raise UpstreamError(503, "stub: Gemini failed this attempt")
            time.sleep(spec["hold"])
            return type("Reply", (), {"read": lambda self, _b=gemini_frame(stub_answer(prompt)): _b})()
        finally:
            with lock:
                counters["inflight"] -= 1
            record("end", number=number)

    gemini.post_no_redirect = post
    gemini.update_bl_if_needed = lambda: False
    server = ThreadedServer(("127.0.0.1", 0), GeminiHandler)
    sys.stdout.write(f"PORT {server.server_address[1]}\n")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    _serve(json.loads(sys.argv[1]))
