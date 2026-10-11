"""WP2/WP4 review queue, end to end: a real window translates through a fake OpenAI-compatible server.

Each test opens a plain_text project in a real MainWindow, points the AI provider at ``FakeAIServer`` on
127.0.0.1 and drives the same entry points the menus call. What the "plugin knows" (speaker, addressee,
conversation, window size) comes from ``install_rules``.
"""
import json
import threading
import time
from pathlib import Path

import pytest

from test_review._rq_wp2_4_helpers import (
    FakeAIServer,
    ModalAnswerer,
    batch_payload,
    install_rules,
    make_project,
    open_window,
    row,
    system_of,
    ua,
    user_of,
    wait_idle,
)

GOLDEN_RESUME = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp2_4" / "resume.json")
    .read_text(encoding="utf-8")
)
MARKER = "--- REQUEST RULES"


@pytest.fixture
def server():
    fake = FakeAIServer()
    yield fake
    fake.stop()


def traffic_records(start: int = 0):
    """ai_traffic.log records written after byte ``start`` (the log lives in the test settings directory)."""
    from utils.logging_utils import ai_traffic_log_path

    path = ai_traffic_log_path()
    if not path.exists():
        return []
    with path.open("rb") as handle:
        handle.seek(start)
        return [json.loads(line) for line in handle.read().decode("utf-8").splitlines() if line.strip()]


def traffic_mark() -> int:
    from utils.logging_utils import ai_traffic_log_path

    path = ai_traffic_log_path()
    return path.stat().st_size if path.exists() else 0


def strings_sent(server):
    return [[item["text"] for item in p["strings_to_translate"]] for p in server.batch_payloads()]


def ids_sent(server):
    return [[item["id"] for item in p["strings_to_translate"]] for p in server.batch_payloads()]


# ============================================================================ WP2


def test_a_retry_tells_the_model_the_real_error_in_the_system_prompt(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Hello there.", "Second line.", "Third line."]})
    mw = open_window(qtbot, monkeypatch, project, server)

    def one_short(body):  # the first reply drops a string
        items = batch_payload(body)["strings_to_translate"][:-1]
        return json.dumps({"translated_strings": [{"id": i["id"], "translation": ua(i["text"])} for i in items]})

    server.script.append(one_short)
    clicked = []

    def answer(widget):
        buttons = getattr(widget, "buttons", lambda: [])()
        for button in buttons:
            if button.text().startswith("Retry"):
                clicked.append(widget.informativeText())
                button.click()
                return True
        if buttons:  # "AI Operation Failed": close it, the assertions below report it
            clicked.append("unexpected: " + widget.text())
            buttons[0].click()
            return True
        return False

    answerer = ModalAnswerer(answer)
    mark = traffic_mark()
    try:
        mw.translation_handler.translate_current_block(0)
        qtbot.waitUntil(lambda: len(server.requests) == 2, timeout=15000)
        wait_idle(qtbot, mw)
    finally:
        answerer.stop()

    first, second = server.bodies()
    reason = "Line count mismatch in chunk 1. Expected 3, got 2."
    assert "RETRY" not in system_of(first)
    assert reason in clicked[0]
    assert system_of(second).startswith(system_of(first))  # the cacheable prefix is unchanged
    reminder = system_of(second)[len(system_of(first)):]
    assert "RETRY: your previous response to this request was rejected." in reminder
    assert f"Reason: Value error during AI operation: {reason}" in reminder
    assert "trailing comma" not in reminder
    assert [row(mw, 0, i) for i in range(3)] == ["UA Hello there.", "UA Second line.", "UA Third line."]
    # The same reminder is what "Log AI traffic" recorded for the second request.
    requests = [r for r in traffic_records(mark) if r["event"] == "request"]
    assert len(requests) == 2 and requests[1]["attempt"] == 2
    assert reason in system_of(requests[1])


def _spy_composer(monkeypatch, mw):
    """Record on which thread each batch request is composed, and for how many strings."""
    composer = mw.translation_handler.prompt_composer
    calls = []
    original = composer.compose_batch_request

    def spy(*args, **kwargs):
        calls.append((threading.current_thread() is threading.main_thread(), len(kwargs["source_items"])))
        return original(*args, **kwargs)

    monkeypatch.setattr(composer, "compose_batch_request", spy)
    return calls


def test_with_the_editor_off_nothing_is_composed_before_the_run(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": [f"Line number {i}." for i in range(30)]})
    mw = open_window(qtbot, monkeypatch, project, server)
    calls = _spy_composer(monkeypatch, mw)

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert len(server.requests) == 3
    assert calls and not any(on_main for on_main, _ in calls)  # every chunk is composed by the worker
    assert [n for _, n in calls] == [12, 12, 6]
    bodies = server.bodies()
    # One system prompt for the whole run (cacheable), and no conversation history: each chunk is a
    # system + user pair (2.4, sessions removed from block translation).
    assert len({system_of(body) for body in bodies}) == 1
    assert all([m["role"] for m in body["messages"]] == ["system", "user"] for body in bodies)


def test_the_review_pass_sees_the_translation_conversation_and_its_fixes_are_applied(
        qtbot, monkeypatch, tmp_path, server):
    """The reviewer gets the chunk's own request (rules, glossary, context), the draft, then REVIEW_REQUEST,
    and returns only the lines it fixes (live design 2026-10-04, replacing the context-blind editor review)."""
    from handlers.translation.prompt_composer.instructions import REVIEW_REQUEST

    project = make_project(tmp_path, {"a": ["Hello there.", "Second line\nbelow."]})
    mw = open_window(qtbot, monkeypatch, project, server, review_enabled=True)
    review = {}

    def fix_one(body):
        review.update(roles=[m["role"] for m in body["messages"]], messages=body["messages"])
        return json.dumps({"translated_strings": [{"id": 1, "translation": "UA Another line\nUA below.",
                                                   "reason": "meaning"}]})

    server.script[:] = [lambda body: None, fix_one]
    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert len(server.requests) == 2
    draft_request = server.requests[0][1]["messages"]
    assert review["roles"] == ["system", "user", "assistant", "user"]
    assert review["messages"][:2] == draft_request                      # the same rules, glossary and context
    assert review["messages"][3]["content"] == REVIEW_REQUEST
    assert [row(mw, 0, 0), row(mw, 0, 1)] == ["UA Hello there.", "UA Another line\\nUA below."]


def test_an_unusable_editor_review_keeps_the_draft(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Hello there.", "Second line."]})
    mw = open_window(qtbot, monkeypatch, project, server, review_enabled=True)
    server.script[:] = [lambda body: None, lambda body: json.dumps({"translated_strings": []})]

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert [row(mw, 0, 0), row(mw, 0, 1)] == ["UA Hello there.", "UA Second line."]


def test_the_editor_previews_one_chunk_and_its_edits_apply_to_every_chunk_and_save_only_the_prompt(
        qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": [f"Line number {i}." for i in range(30)], "b": ["One more line."]})
    mw = open_window(qtbot, monkeypatch, project, server)
    mw.prompt_editor_enabled = True
    calls = _spy_composer(monkeypatch, mw)
    seen = {}

    def answer(widget):
        from components.prompt_editor_dialog import PromptEditorDialog

        if not isinstance(widget, PromptEditorDialog):
            return False
        system, user = widget._system_edit.toPlainText(), widget._user_edit.toPlainText()
        seen["preview_items"] = len(batch_payload({"messages": [{"role": "user", "content": user}]})["strings_to_translate"])
        prompt, marker, rules = system.partition(MARKER)
        seen["marker"] = marker
        widget._system_edit.setPlainText("MY OWN PROMPT LINE.\n" + prompt + marker + rules + "\n- MY RULE FOR THIS RUN.")
        widget._user_edit.setPlainText(user.replace("Game: Plain Text", "Game: EDITED HEADER", 1))
        widget._save_checkbox.setChecked(True)
        widget.accept()
        return True

    answerer = ModalAnswerer(answer)
    try:
        mw.translation_handler.translate_current_block(0)
        wait_idle(qtbot, mw)
    finally:
        answerer.stop()

    # The preview: the first chunk only, composed once on the GUI thread; the run covers all 30 strings.
    assert seen["preview_items"] == 12 and seen["marker"]
    assert [(on_main, n) for on_main, n in calls if on_main] == [(True, 12)]
    assert sum(len(ids) for ids in ids_sent(server)) == 30
    assert all(row(mw, 0, i) == f"UA Line number {i}." for i in range(30))
    # The edited system prompt and header went out with every chunk.
    bodies = server.bodies()
    assert len(bodies) == 3
    for body in bodies:
        assert system_of(body).startswith("MY OWN PROMPT LINE.\n")
        assert system_of(body).endswith("- MY RULE FOR THIS RUN.")
        assert user_of(body).startswith("Game: EDITED HEADER")
    # "Save" stored the part above the rules line, nothing below it.
    saved_files = list((tmp_path / "project").rglob("prompts.json"))
    assert len(saved_files) == 1
    saved = json.loads(saved_files[0].read_text(encoding="utf-8"))["translation"]["system_prompt"]
    assert saved.startswith("MY OWN PROMPT LINE.\n")
    assert MARKER not in saved and "MY RULE FOR THIS RUN" not in saved and "GLOSSARY IS MANDATORY" not in saved

    # The next run uses the saved prompt with the engine's current rules appended afresh.
    mw.prompt_editor_enabled = False
    server.requests.clear()
    mw.translation_handler.translate_current_block(1)
    wait_idle(qtbot, mw)
    next_system = system_of(server.bodies()[0])
    assert next_system.startswith("MY OWN PROMPT LINE.\n") and MARKER in next_system
    assert "MY RULE FOR THIS RUN" not in next_system
    # A saved prompt holds no copy of the rules, so a rule added later (4.1 "RUN MEMORY") reaches it too.
    assert "RUN MEMORY:" in next_system.split(MARKER, 1)[1]


@pytest.mark.parametrize("provider, profile, check", [
    ("openai", "openai", lambda path, body: body.get("response_format") == {"type": "json_object"}),
    ("openai", "auto", lambda path, body: "response_format" not in body),          # a self-hosted proxy
    ("openai", "web2api", lambda path, body: "response_format" not in body),
    ("ollama_chat", "openai", lambda path, body: path.endswith("/api/chat") and body.get("format") == "json"),
    ("gemini", "openai", lambda path, body: ":generateContent" in path
     and body["generationConfig"].get("responseMimeType") == "application/json"),
])
def test_native_json_mode_is_asked_for_only_where_it_exists(qtbot, monkeypatch, tmp_path, server, provider, profile, check):
    from test_review._rq_wp2_4_helpers import configure_provider

    project = make_project(tmp_path, {"a": ["Hello there.", "Second line."]})
    mw = open_window(qtbot, monkeypatch, project, server)
    configure_provider(mw, server, provider=provider, profile=profile)

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert len(server.requests) == 1
    path, body = server.requests[0]
    assert check(path, body), (path, body)
    assert row(mw, 0, 1) == "UA Second line."


# ============================================================================ WP4


GLOSSARY_UI = [
    {"original": "Save", "translation": "Зберегти", "section": "UI", "status": "confirmed"},
    {"original": "Load", "translation": "Завантажити", "section": "UI", "status": "confirmed"},
    {"original": "OK", "translation": "Гаразд", "section": "UI", "status": "confirmed"},
]


def test_fixed_interface_strings_are_filled_without_a_request_and_undone_in_one_step(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Save", "Hello there.", "Load", "OK!", "ok", "OK"]}, glossary=GLOSSARY_UI)
    mw = open_window(qtbot, monkeypatch, project, server)
    messages = []
    monkeypatch.setattr(mw.statusBar, "showMessage", lambda text, *a: messages.append(text))

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert [row(mw, 0, i) for i in range(6)] == ["Зберегти", "UA Hello there.", "Завантажити", "UA OK!", "UA ok", "Гаразд"]
    assert strings_sent(server) == [["Hello there.", "OK!", "ok"]]
    assert "Filled 3 lines from the glossary (fixed interface strings)." in messages

    mw.undo_manager.undo()  # the model's chunk
    assert [row(mw, 0, i) for i in (1, 3, 4)] == ["Hello there.", "OK!", "ok"]
    assert [row(mw, 0, i) for i in (0, 2, 5)] == ["Зберегти", "Завантажити", "Гаразд"]
    mw.undo_manager.undo()  # every fixed string at once
    assert [row(mw, 0, i) for i in (0, 2, 5)] == ["Save", "Load", "OK"]


def test_a_single_string_request_names_the_addressee(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Hello, Link!", "Thank you, sir."]},
                           glossary=[{"original": "Link", "translation": "Лінк"}])
    mw = open_window(qtbot, monkeypatch, project, server)
    install_rules(mw, speakers={(0, 0): "Midna", (0, 1): "Colin"}, addressees={(0, 0): "Link"})
    mark = traffic_mark()

    for string_idx in (0, 1):
        mw.data_store.current_block_idx, mw.data_store.current_string_idx = 0, string_idx
        mw.translation_handler.translate_current_string()
        wait_idle(qtbot, mw)

    first, second = (user_of(body) for body in server.bodies())
    assert "Speaker: Midna\nAddressee: Лінк\n" in first
    assert "Addressee:" not in second  # the plugin does not know who Colin speaks to
    logged = [user_of(r) for r in traffic_records(mark) if r["event"] == "request"]
    assert "Addressee: Лінк" in logged[0]


def test_the_lines_of_one_conversation_go_out_in_one_request(qtbot, monkeypatch, tmp_path, server):
    lines = [f"Line number {i}." for i in range(20)]
    project = make_project(tmp_path, {"a": lines})
    mw = open_window(qtbot, monkeypatch, project, server)
    # A question at 10 answered by 11-13 (across the old 12-string cut), a choice at 3 whose answer is at 15.
    groups = {**{(0, i): "question" for i in (10, 11, 12, 13)}, (0, 3): "choice", (0, 15): "choice"}
    install_rules(mw, flow_groups=groups)

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    chunks = ids_sent(server)
    together = [{10, 11, 12, 13}, {3, 15}]
    for members in together:
        assert any(members <= set(chunk) for chunk in chunks), (members, chunks)
    assert sorted(i for chunk in chunks for i in chunk) == list(range(20))
    assert all(len(chunk) <= 12 for chunk in chunks)
    assert all(row(mw, 0, i) == f"UA Line number {i}." for i in range(20))
    # The old cut would have split the question from two of its answers.
    old_cut = [list(range(0, 12)), list(range(12, 20))]
    assert not any({10, 11, 12, 13} <= set(chunk) for chunk in old_cut)


def test_a_run_saved_by_the_old_version_resumes_with_its_old_chunks(qtbot, monkeypatch, tmp_path, server):
    block = GOLDEN_RESUME["block"]
    project = make_project(tmp_path, {"a": block})
    mw = open_window(qtbot, monkeypatch, project, server)
    # A conversation hook that would regroup a new run must not touch the old plan.
    install_rules(mw, flow_groups={(0, 13): "talk", (0, 25): "talk"})
    pm = mw.project_manager
    pm.project.blocks[mw.block_to_project_file_map.get(0, 0)].metadata["translation_progress"] = json.loads(
        json.dumps(GOLDEN_RESUME["progress_metadata"]))
    pm.save()
    mw.translation_handler.load_progress_from_metadata()  # what opening the project does
    assert 0 in mw.translation_handler.translation_progress

    mw.translation_handler.resume_block_translation(0)
    wait_idle(qtbot, mw)

    # Chunk 0 was done before the update; the rest goes out exactly as the old plan cut it, duplicates and all.
    assert ids_sent(server) == GOLDEN_RESUME["chunks"][1:]
    assert all(row(mw, 0, i) == ua(block[i]) for i in range(12, 30))
    assert all(row(mw, 0, i) == block[i] for i in range(12))  # not sent again
    assert 0 not in mw.translation_handler.translation_progress  # the run finished


def _answer_cached(record, button: str):
    def answer(widget):
        from dialogs.cached_translation_dialog import CachedTranslationDialog

        if not isinstance(widget, CachedTranslationDialog):
            return False
        record.append((widget.source_label.text(), widget.text_edit.toPlainText()))
        getattr(widget, button).click()
        return True
    return answer


def test_a_translation_saved_elsewhere_is_offered_and_restored_without_a_request(qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Thanks!", "See you."], "b": ["Hello.", "Thanks!", "See you."]})
    mw = open_window(qtbot, monkeypatch, project, server)
    project_dir = tmp_path / "project"

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)
    memory_file = project_dir / "translation_memory.json"
    qtbot.waitUntil(memory_file.exists, timeout=5000)
    assert (project_dir / "saved_translations.json").exists()

    shown = []
    answerer = ModalAnswerer(_answer_cached(shown, "restore_btn"))
    server.requests.clear()
    try:
        mw.translation_handler.translate_current_block(1)
        wait_idle(qtbot, mw)
    finally:
        answerer.stop()

    assert len(shown) == 1
    text = shown[0][1]
    assert "Line 2 (same text elsewhere):\nUA Thanks!" in text and "Line 3 (same text elsewhere):\nUA See you." in text
    assert strings_sent(server) == [["Hello."]]  # the two restored rows are not in the request
    assert [row(mw, 1, i) for i in range(3)] == ["UA Hello.", "UA Thanks!", "UA See you."]

    # The memory is rebuilt from saved_translations.json when it is deleted.
    from core.saved_translations_manager import SavedTranslationsManager

    memory_file.unlink()
    rebuilt = SavedTranslationsManager(mw)
    assert rebuilt.find_by_source("See you.") == "UA See you."


def test_a_single_string_request_shows_the_translation_memory_and_a_variation_request_does_not(
        qtbot, monkeypatch, tmp_path, server):
    project = make_project(tmp_path, {"a": ["Thanks a lot!"], "b": ["Hello.", "Thanks a lot!"]})
    mw = open_window(qtbot, monkeypatch, project, server)
    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    shown = []
    answerer = ModalAnswerer(_answer_cached(shown, "translate_btn"))  # "Translate Anew"
    try:
        mw.data_store.current_block_idx, mw.data_store.current_string_idx = 1, 1
        mw.translation_handler.translate_current_string()
        wait_idle(qtbot, mw)
    finally:
        answerer.stop()
    assert shown and shown[0][0] == "Source: saved for the same text elsewhere in the project"
    single = user_of(server.bodies()[-1])
    assert 'TRANSLATION MEMORY (same source elsewhere):\n- "Thanks a lot!" -> "UA Thanks a lot!"' in single

    server.script.append(lambda body: json.dumps(["Дуже дякую!", "Щиро дякую!"], ensure_ascii=False))
    answerer = ModalAnswerer(lambda widget: widget.reject() is None)  # close the variations window
    try:
        mw.translation_handler.variations_handler.generate_variation_for_string(1, 1)
        wait_idle(qtbot, mw)
    finally:
        answerer.stop()
    variation = user_of(server.bodies()[-1])
    assert "Generate 10 different" in system_of(server.bodies()[-1])
    assert "TRANSLATION MEMORY" not in variation


def test_duplicates_fold_only_when_speaker_addressee_and_window_agree(qtbot, monkeypatch, tmp_path, server):
    lines = ["I will help you.", "I will help you.", "I will help you.", "I will help you.",
             "Yes", "Yes", "Thank you so much.", "Thank you so much.", "I will help you."]
    project = make_project(tmp_path, {"a": lines})
    mw = open_window(qtbot, monkeypatch, project, server)
    install_rules(
        mw,
        speakers={(0, 0): "Link", (0, 1): "Link", (0, 2): "Midna", (0, 3): "Link", (0, 8): "Link",
                  (0, 6): "Ilia", (0, 7): "Ilia"},
        addressees={(0, 8): "Zelda"},
        lines_per_window={(0, 3): 1},  # a narrower window than the rest
    )
    logged = []
    import handlers.translation.batch_translator as batch_translator

    monkeypatch.setattr(batch_translator, "log_debug", lambda text, *a, **k: logged.append(text))
    # Each sent string gets its own translation, so rows that share one prove they were folded.
    counter = iter(range(100))
    server.translate = lambda text: f"T{next(counter)} {text}"

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    sent = ids_sent(server)
    assert sent == [[0, 2, 3, 4, 6, 8]]  # 1 folds into 0, 5 into 4, 7 into 6
    assert any("3 duplicate strings will take the translation of 3 others" in text for text in logged)
    rows = [row(mw, 0, i) for i in range(len(lines))]
    assert rows[1] == rows[0] and rows[5] == rows[4] and rows[7] == rows[6]
    assert len({rows[0], rows[2], rows[3], rows[8]}) == 4  # other speaker, other window, other addressee


def test_folding_needs_fewer_chunks_than_the_old_plan(qtbot, monkeypatch, tmp_path, server):
    block = GOLDEN_RESUME["block"]
    project = make_project(tmp_path, {"a": block})
    mw = open_window(qtbot, monkeypatch, project, server)

    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    assert len(server.requests) < len(GOLDEN_RESUME["chunks"]) == 3
    assert [row(mw, 0, i) for i in range(30)] == [ua(text) for text in block]  # every repeat filled the same


def test_a_later_chunk_shows_what_an_earlier_chunk_of_the_run_translated(qtbot, monkeypatch, tmp_path, server):
    lines = ["Yes"] + [f"Line number {i}." for i in range(1, 24)] + ["[C1]Yes[/C1]"]
    project = make_project(tmp_path, {"a": lines})
    mw = open_window(qtbot, monkeypatch, project, server)
    memory = mw.translation_handler.run_memory

    def after_first_chunk_is_applied(body):
        # Chunks follow each other without waiting for the GUI thread to apply the one before; hold the
        # second answer until the first chunk is in the run memory, so the third request is composed after it.
        deadline = time.monotonic() + 10
        while not memory.similar(["Yes"]) and time.monotonic() < deadline:
            time.sleep(0.01)
        return None

    server.script[:] = [lambda body: None, after_first_chunk_is_applied]
    mark = traffic_mark()
    mw.translation_handler.translate_current_block(0)
    wait_idle(qtbot, mw)

    payloads = server.batch_payloads()
    assert len(payloads) == 3
    assert "already_translated_in_this_run" not in payloads[0]
    assert payloads[2]["already_translated_in_this_run"] == [{"text": "Yes", "translation": "UA Yes"}]
    assert "RUN MEMORY" in system_of(server.bodies()[2])
    logged = [user_of(r) for r in traffic_records(mark) if r["event"] == "request"]
    assert '"already_translated_in_this_run"' in logged[2]


def test_closing_the_window_while_previews_are_cached_raises_nothing(qtbot, monkeypatch, tmp_path, server):
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication

    project = make_project(tmp_path, {"a": ["One."], "b": ["Two."]})
    mw = open_window(qtbot, monkeypatch, project, server)
    cache = mw.ui_updater.preview_updater.preview_cache
    cache.cancel_idle_caching()
    cache._start_idle_caching()          # creates the idle timer, a child of the window
    cache._idle_cache_queue = [-1]       # one slice left; it re-arms with QTimer.singleShot(0, ...)
    cache._current_caching_block_idx = None
    cache._cache_next_idle_block()
    sip.delete(cache._idle_timer)        # what destroying the window does to the timer it owns
    with qtbot.capture_exceptions() as exceptions:
        for _ in range(3):
            QCoreApplication.processEvents()
    cache._idle_timer = None             # let the window close cleanly
    assert not exceptions, "".join(str(e[1]) for e in exceptions)
