"""REVIEW_QUEUE WP1: glossary pipeline as before without /healthz; the self-hosted timeout floor."""
import importlib.util
import json
from pathlib import Path

from core.translation.providers import WEB2API_TIMEOUT_FLOOR, OpenAIProvider
from test_review._rq_wp1_6_helpers import FakeAIServer

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp1_6" / "ai"
BASELINE = json.loads((GOLDEN_DIR / "baseline.json").read_text(encoding="utf-8"))


def _scenarios():
    spec = importlib.util.spec_from_file_location("rq_wp1_6_ai_golden_p", GOLDEN_DIR / "make_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_glossary_pipeline_build_is_as_before_and_keeps_its_workers_without_healthz(qapp):
    """A short build through a real endpoint with no /healthz: same entries, summary, request count, 4 workers."""
    before = BASELINE["glossary_pipeline_without_healthz"]
    now = _scenarios().glossary_pipeline_without_healthz(workers=4)

    assert now["healthz_asked"] is True and before["healthz_asked"] is False  # the new probe ran and found nothing
    for key in ("finished", "entries", "requests", "workers", "logs_about_accounts"):
        assert now[key] == before[key], key
    assert now["workers"] == 4 and now["logs_about_accounts"] == []


class _PolicySpy:
    """Wraps OpenAIProvider._policy and keeps the timeout each request was given."""

    def __init__(self, monkeypatch):
        self.timeouts = []
        original = OpenAIProvider._policy

        def spy(provider, settings, default_timeout):
            policy = original(provider, settings, default_timeout)
            self.timeouts.append(policy.timeout)
            return policy

        monkeypatch.setattr(OpenAIProvider, "_policy", spy)


def test_a_self_hosted_endpoint_waits_at_least_180_s_even_for_a_60_s_setting(monkeypatch):
    """Single-string translation and chat both go through translate(): the floor applies to them too."""
    server = FakeAIServer(lambda body: (200, {}, FakeAIServer.completion('{"translation": "ok"}')))
    spy = _PolicySpy(monkeypatch)
    try:
        self_hosted = OpenAIProvider({"endpoint": server.url, "model": "m", "timeout": 60})
        self_hosted.translate([{"role": "user", "content": "Hi"}], settings_override={"think": 2})
        list(self_hosted.translate_stream([{"role": "user", "content": "chat"}]))
        as_hosted = OpenAIProvider({"endpoint": server.url, "model": "m", "timeout": 60, "profile": "openai"})
        as_hosted.translate([{"role": "user", "content": "Hi"}])
        longer = OpenAIProvider({"endpoint": server.url, "model": "m", "timeout": 300})
        longer.translate([{"role": "user", "content": "Hi"}])
    finally:
        server.stop()

    assert WEB2API_TIMEOUT_FLOOR == 180.0
    assert spy.timeouts == [180.0, 180.0, 60.0, 300.0]
