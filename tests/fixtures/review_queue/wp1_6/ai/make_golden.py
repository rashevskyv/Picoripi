"""Golden outputs for the WP1/WP6 AI review-queue tests, and the scenarios that produce them.

The same scenario functions run on the old code (here, as a script) and on the current code (imported by
``tests/test_review/test_rq_wp1_6_ai_*.py``); the tests compare the two.

* ``worker_paths.json`` -- every AIWorker task path, recorded on the code from just before the 6.5 split
  (commit 3cfae115 = ``74ff7f75^``). Regenerate:

      git archive 3cfae115 | tar -x -C <dir>
      cd <dir> && PYTHONPATH=. QT_QPA_PLATFORM=offscreen <repo>/venv/Scripts/python.exe \
          <repo>/tests/fixtures/review_queue/wp1_6/ai/make_golden.py worker < /dev/null

* ``baseline.json`` -- the legacy Build Glossary with an unreadable chunk and a glossary-pipeline build through
  a real OpenAI-compatible endpoint without ``/healthz``, recorded on the pre-audit baseline (691699c0):

      cd D:/git/dev/Picoripi-baseline && PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
          ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp1_6/ai/make_golden.py baseline < /dev/null

Only the code under test comes from the working directory; the fake server comes from this repository.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[3]  # .../tests

# ------------------------------------------------------------------- fakes


class FakeComposer:
    """The prompt composer the worker calls; deterministic text, no window."""

    mw = None

    def __init__(self, client=None):
        self.client = client

    def _get_mempalace_client(self):
        return self.client

    def _get_wing_name(self):
        return "wing"

    def _get_block_label(self, block_idx):
        return f"blk{block_idx}"

    def compose_batch_request(self, **kwargs):
        items = [{"id": i["id"], "text": i["text"]} for i in kwargs["source_items"]]
        user = "Translate.\n\nJSON DATA TO PROCESS:\n" + json.dumps({"strings": items}, ensure_ascii=False)
        return kwargs.get("system_prompt", "SYS"), user, None

    def compose_variation_request(self, **kwargs):
        return "VAR-SYS", "Variation of: " + str(kwargs.get("current_translation", ""))

    def compose_glossary_occurrence_batch_request(self, **kwargs):
        items = kwargs["batch_items"]
        return "OCC-SYS", "JSON DATA TO UPDATE:\n" + json.dumps(items, ensure_ascii=False)


class FakeClient:
    """A MemPalace client that knows a chapter for every string."""

    def get_cached_context(self, bmg_id, text):
        return None

    def get_script_mapping(self, wing, bmg_id):
        line = int(bmg_id.rsplit("_", 1)[1])
        return {"script_line": 100 + line, "chapter_num": 1 + line // 12, "chapter_title": "Ordon"}


class FakeProvider:
    """``translate`` answers through ``reply(messages, n)``; every call is recorded."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []
        self.lock = threading.Lock()

    def translate(self, messages, session=None, settings_override=None):
        from core.translation.providers import ProviderResponse

        with self.lock:
            n = len(self.calls)
            self.calls.append({"messages": json.loads(json.dumps(messages)),
                               "override": dict(sorted((settings_override or {}).items()))})
        return ProviderResponse(text=self.reply(messages, n))


def echo_chunk(messages, _n):
    user = messages[-1]["content"]
    data = json.loads(user.partition("JSON DATA TO PROCESS:")[2])
    return json.dumps({"translated_strings": [{"id": s["id"], "translation": "UA " + s["text"]}
                                              for s in data["strings"]]}, ensure_ascii=False)


# --------------------------------------------------------------- recording

_SUMMARY = re.compile(r"p(50|95) \d+\.\d+s")


def _record(worker):
    events = []
    lock = threading.Lock()

    def add(*event):
        with lock:
            events.append(list(event))

    worker.step_updated.connect(lambda i, text, status: add("step", i, text, status))
    worker.progress_updated.connect(lambda n: add("progress", n))
    worker.detail_updated.connect(lambda text: add("detail", _SUMMARY.sub(r"p\1 Xs", text)))
    worker.total_chunks_calculated.connect(lambda a, b: add("total", a, b))
    worker.chunk_translated.connect(lambda i, text, _ctx: add("chunk", i, text))
    worker.success.connect(lambda response, _ctx: add("success", response.text))
    worker.error.connect(lambda message, ctx: add("error", message, ctx.get("failed_chunks")))
    worker.translation_cancelled.connect(lambda: add("cancelled"))
    worker.finished.connect(lambda: add("finished"))
    return events


def _run(task, reply, *, client=None, on_call=None):
    from handlers.translation.ai_worker import AIWorker

    provider = FakeProvider(reply)
    worker = AIWorker(provider, FakeComposer(client), task)
    if on_call is not None:
        inner = provider.reply
        provider.reply = lambda messages, n: on_call(worker, n) or inner(messages, n)
    events = _record(worker)
    worker.run()
    return {"events": events, "calls": provider.calls}


STEPS = ["Preparing", "Sending", "Waiting", "Applying"]


def _block_task(count, workers):
    items = [{"id": i, "text": f"Line {i}"} for i in range(count)]
    return {
        "type": "translate_block_chunked", "source_items": items, "block_idx": 0,
        "temp_id_map": {i: (0, i) for i in range(count)}, "attempt": 1, "max_retries": 4,
        "mode_description": "block 1", "provider_settings_override": {"timeout": 60},
        "workers": workers, "dialog_steps": STEPS,
        "composer_args": {"system_prompt": "SYS", "source_items": items, "block_idx": 0},
    }


def _fail_chunk(bad_chunk):
    from core.translation.providers import TranslationProviderError

    def reply(messages, n):
        data = json.loads(messages[-1]["content"].partition("JSON DATA TO PROCESS:")[2])
        if data["strings"][0]["id"] == bad_chunk * 12:
            raise TranslationProviderError("upstream 502 for this chunk")
        return echo_chunk(messages, n)
    return reply


def worker_scenarios() -> dict:
    """Every AIWorker path the 6.5 split touched, on fixed input."""
    out = {}
    out["block_sequential"] = _run(_block_task(30, 1), echo_chunk, client=FakeClient())
    out["block_parallel"] = _run(_block_task(30, 3), echo_chunk)
    out["block_sequential_error_on_chunk_2"] = _run(_block_task(30, 1), _fail_chunk(1))
    out["block_parallel_error_on_chunk_2"] = _run(_block_task(36, 3), _fail_chunk(1))
    out["block_sequential_cancel_during_chunk_2"] = _run(
        _block_task(36, 1), echo_chunk, on_call=lambda worker, n: worker.cancel() if n == 1 else None)

    out["build_glossary"] = _run({
        "type": "build_glossary", "block_data": [f"Link meets Ordon villager number {i}." for i in range(60)],
        "target_indices": list(range(60)), "chunk_size": 1000, "system_prompt": "GLOSSARY-SYS",
        "user_prompt_template": "Find terms:\n{text_chunk}", "dialog_steps": STEPS,
    }, lambda m, n: json.dumps([{"original": f"Term{n}", "translation": f"Терм{n}", "notes": ""}]))

    occurrences = [{"block_idx": 0, "string_idx": i, "original": f"Ordon {i}", "translation": f"Ордон {i}"}
                   for i in range(30)]
    out["glossary_occurrence_batch_update"] = _run({
        "type": "glossary_occurrence_batch_update", "attempt": 1, "max_retries": 3, "dialog_steps": STEPS,
        "composer_args": {"system_prompt": "OCC", "term": "Ordon", "old_translation": "Ордон",
                          "new_translation": "Ордонь", "batch_items": occurrences},
    }, lambda m, n: json.dumps({"occurrences": [{"string_idx": n, "translation": f"Ордонь {n}"}]}))

    for kind in ("translate_single", "generate_variation"):
        out[kind] = _run({
            "type": kind, "attempt": 1, "max_retries": 3, "dialog_steps": STEPS, "block_idx": 0, "string_idx": 2,
            "composer_args": {"current_translation": "Привіт", "original_text": "Hello"},
        }, lambda m, n: '{"translation": "Вітаю"}')
    return out


# ------------------------------------------------------------- baseline only

# The second of three chunks answers with something that is not a term list.
LEGACY_BAD_REPLIES = {
    "prose": "Sorry, I could not find any terms here.",
    "object": '{"terms": "none found"}',
    "empty": "",
    "array_after_prose": 'Here you go: [{"original": "Ordon", "translation": "Ордон", "notes": ""}]',
}


def legacy_glossary_with_unreadable_chunk(kind: str) -> dict:
    def reply(messages, n):
        if n == 1:
            return LEGACY_BAD_REPLIES[kind]
        return json.dumps([{"original": f"Term{n}", "translation": f"Терм{n}", "notes": ""}])

    return _run({
        "type": "build_glossary", "block_data": [f"Link meets Ordon villager number {i}." for i in range(60)],
        "target_indices": list(range(60)), "chunk_size": 1000, "system_prompt": "GLOSSARY-SYS",
        "user_prompt_template": "Find terms:\n{text_chunk}", "dialog_steps": STEPS,
    }, reply)


PIPELINE_DATASET = [
    ["Ordon village is calm", "Link visits Ordon", "The Master Sword rests in the Sacred Grove."],
    ["Epona runs to Ordon", "Rusl guards the village", "Kakariko Village lies east."],
]


def pipeline_reply(body):
    """Canned answers for the glossary pipeline passes, chosen by the request text."""
    user = body["messages"][-1]["content"]
    if "Game text chunk" in user:
        found = [t for t in ("Ordon", "Epona", "Master Sword", "Kakariko Village", "Rusl") if t in user]
        return json.dumps([{"term": t, "section": "Names", "fragment": f"{t} appears"} for t in found])
    if "Excerpts where it appears" in user:
        return json.dumps({"description": "a described thing"})
    if "Partial descriptions" in user:
        return json.dumps({"description": "folded"})
    if "Description:" in user:
        return json.dumps([{"translation": "Переклад", "rationale": "r"}])
    return "[]"


def glossary_pipeline_without_healthz(workers: int = 4) -> dict:
    """A short build through a real OpenAI-compatible endpoint that has no /healthz."""
    sys.path.append(str(TESTS))
    from test_review._rq_wp1_6_helpers import FakeAIServer
    from core.glossary_manager import GlossaryManager
    from core.translation.providers import OpenAIProvider
    from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker

    server = FakeAIServer(lambda body: (200, {}, FakeAIServer.completion(pipeline_reply(body))))
    try:
        manager = GlossaryManager()
        manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        provider = OpenAIProvider({"endpoint": server.url, "model": "m"})
        worker = GlossaryBuildWorker(manager, provider, PIPELINE_DATASET, mode="thorough", translate=True,
                                     workers=workers)
        logs, finished = [], []
        worker.log.connect(logs.append)
        worker.build_finished.connect(lambda ok, summary: finished.append([ok, summary]))
        worker.run()
        entries = sorted(
            [e.original, e.translation, e.status, e.section, e.notes] for e in manager.get_entries()
        )
        return {
            "finished": finished, "entries": entries, "workers": worker._workers, "requests": len(server.requests),
            "logs_about_accounts": [line for line in logs if "usable account" in line],
            "healthz_asked": "/healthz" in server.gets,
        }
    finally:
        server.stop()


def baseline_scenarios() -> dict:
    return {
        **{f"legacy_glossary_{kind}": legacy_glossary_with_unreadable_chunk(kind) for kind in LEGACY_BAD_REPLIES},
        "glossary_pipeline_without_healthz": glossary_pipeline_without_healthz(),
    }


if __name__ == "__main__":
    import tempfile

    from PyQt6.QtWidgets import QApplication
    import utils.logging_utils as logging_utils

    # Keep the old code's debug log out of its checkout.
    logging_utils.default_log_file_path = logging_utils.log_file_path = str(Path(tempfile.gettempdir()) / "rq_golden.txt")
    app = QApplication.instance() or QApplication([])
    which = sys.argv[1]
    data = worker_scenarios() if which == "worker" else baseline_scenarios()
    target = HERE / ("worker_paths.json" if which == "worker" else "baseline.json")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
