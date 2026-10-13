"""The project scan: cards, icons and counts with their cache rules, and the real child process that runs it.

Projects use the real ``plain_text`` plugin folder (so the card has no missing-plugin issue); the rules that count are
explicit fakes passed to ``scan.run``. The last test starts the real child process.
"""
import json
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.project_library import index, plugin_facts, scan
from core.project_library.scan import ICON_FILE_NAME
from plugins.base_game_rules import BaseGameRules
from ui.project_manager.scan_process import ScanProcess


class LineRules(BaseGameRules):
    """A JSON file is a list of blocks of lines; no icon."""

    def load_data_from_json_obj(self, json_obj):
        return json_obj, {}


class IconRules(LineRules):
    """Supplies a plugin icon: the bytes of the PNG the test passes in."""

    png = b""

    def project_icon(self, project_dir):
        return self.png


def _loader(rules):
    return lambda plugin_name: rules


def _project(root, name, translated="Salut", plugin="plain_text"):
    folder = root / name / "picoripi"
    folder.mkdir(parents=True)
    (folder / "a.json").write_text(json.dumps([["Hi", "Bye"]]), encoding="utf-8")
    (folder / "t.json").write_text(json.dumps([[translated, "Bye"]]), encoding="utf-8")
    project = folder / "project.uiproj"
    project.write_text(json.dumps({
        "id": name, "name": name, "plugin_name": plugin,
        "blocks": [{"source_file": "a.json", "translation_file": "t.json"}],
        "metadata": {"source_path": str(folder), "translation_path": str(folder)},
    }), encoding="utf-8")
    return str(project)


def _scan(data_dir, projects, rules=None, is_cancelled=lambda: False):
    events = []
    summary = scan.run(str(data_dir), projects, events.append, is_cancelled, load_rules=_loader(rules or LineRules()))
    return events, summary


def _of(events, kind):
    return [event for event in events if event["event"] == kind]


def _png(path, width=300, height=200):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.red)
    assert image.save(str(path), "PNG")
    return path


def test_first_scan_reads_each_card_and_counts_each_project(tmp_path):
    projects = [("k1", _project(tmp_path, "one")), ("k2", _project(tmp_path, "two"))]

    events, summary = _scan(tmp_path / "data", projects)

    assert {event["key"] for event in _of(events, "card")} == {"k1", "k2"}
    assert _of(events, "plan")[0]["stale"] == 2
    assert summary["counted"] == 2 and summary["failed"] == 0
    stored = index.read(tmp_path / "data")
    assert stored["k1"]["counts"]["translated"] == 1
    assert stored["k1"]["signature"]


def test_second_scan_reuses_the_counts_and_counts_nothing(tmp_path):
    projects = [("k1", _project(tmp_path, "one"))]
    _scan(tmp_path / "data", projects)

    events, summary = _scan(tmp_path / "data", projects)

    assert _of(events, "plan")[0]["stale"] == 0
    assert _of(events, "counts") == []
    assert summary["counted"] == 0


def test_a_changed_translation_file_recounts_only_its_project(tmp_path):
    first = _project(tmp_path, "one")
    second = _project(tmp_path, "two")
    projects = [("k1", first), ("k2", second)]
    _scan(tmp_path / "data", projects)
    (tmp_path / "one" / "picoripi" / "t.json").write_text(json.dumps([["Bonjour", "Bye"]]), encoding="utf-8")

    events, _summary = _scan(tmp_path / "data", projects)

    assert [event["key"] for event in _of(events, "counts")] == ["k1"]
    assert index.read(tmp_path / "data")["k1"]["counts"]["translated"] == 1


def test_a_parser_or_version_change_recounts_the_project(tmp_path, monkeypatch):
    projects = [("k1", _project(tmp_path, "one"))]
    _scan(tmp_path / "data", projects)
    monkeypatch.setattr(plugin_facts, "APP_VERSION", "9.9.9-test")

    events, summary = _scan(tmp_path / "data", projects)

    assert [event["key"] for event in _of(events, "counts")] == ["k1"]
    assert summary["counted"] == 1


def test_the_signature_follows_the_plugin_code_and_the_shared_code_only(tmp_path):
    folder = tmp_path / "plugins"
    for name in ("fake", "other", "common"):
        (folder / name).mkdir(parents=True)
    (folder / "fake" / "rules.py").write_text("A = 1\n", encoding="utf-8")
    (folder / "other" / "rules.py").write_text("B = 1\n", encoding="utf-8")
    (folder / "common" / "shared.py").write_text("C = 1\n", encoding="utf-8")
    project = _project(tmp_path, "one", plugin="fake")

    first = plugin_facts.input_signature(project, folder)
    assert plugin_facts.input_signature(project, folder) == first

    (folder / "other" / "rules.py").write_text("B = 22\n", encoding="utf-8")
    assert plugin_facts.input_signature(project, folder) == first  # another plugin does not count

    (folder / "fake" / "rules.py").write_text("A = 22\n", encoding="utf-8")
    changed = plugin_facts.input_signature(project, folder)
    assert changed != first  # the parser of this plugin changed

    (folder / "common" / "shared.py").write_text("C = 22\n", encoding="utf-8")
    assert plugin_facts.input_signature(project, folder) not in (first, changed)  # shared code too


def test_a_project_whose_plugin_is_missing_gets_the_flag_and_no_count(tmp_path):
    project = _project(tmp_path, "one", plugin="no_such_plugin_folder")

    events, summary = _scan(tmp_path / "data", [("k1", project)])

    assert "plugin_missing" in _of(events, "card")[0]["card"]["issues"]
    assert _of(events, "counts") == []
    assert summary["stale"] == 0


def test_a_user_icon_is_scaled_into_the_cache_and_kept_while_unchanged(tmp_path):
    project = _project(tmp_path, "one")
    _png(tmp_path / "one" / "picoripi" / ICON_FILE_NAME)
    projects = [("k1", project)]

    events, _summary = _scan(tmp_path / "data", projects)

    icon = _of(events, "icon")[0]
    assert icon["source"] == "user"
    stored = QImage(icon["file"])
    assert not stored.isNull() and max(stored.width(), stored.height()) <= scan.ICON_SIZE
    again, _summary = _scan(tmp_path / "data", projects)
    assert _of(again, "icon") == []


def test_a_plugin_icon_is_used_when_the_project_has_no_icon_file(tmp_path):
    project = _project(tmp_path, "one")
    rules = IconRules()
    rules.png = _png(tmp_path / "source.png").read_bytes()

    events, _summary = _scan(tmp_path / "data", [("k1", project)], rules=rules)

    assert _of(events, "icon")[0]["source"] == "plugin"


def test_a_scan_cancelled_before_the_first_project_writes_nothing(tmp_path):
    events, summary = _scan(tmp_path / "data", [("k1", _project(tmp_path, "one"))], is_cancelled=lambda: True)

    assert summary["cancelled"] is True
    assert _of(events, "card") == []
    assert index.read(tmp_path / "data") == {}


def test_the_real_child_process_reports_the_protocol_and_ends(qtbot, tmp_path):
    folder = tmp_path / "game" / "picoripi"
    folder.mkdir(parents=True)
    project = folder / "project.uiproj"
    project.write_text(json.dumps({"id": "empty", "name": "Empty", "plugin_name": "plain_text", "blocks": [],
                                   "metadata": {}}), encoding="utf-8")
    process = ScanProcess(None)
    events = []
    process.event_received.connect(events.append)

    with qtbot.waitSignal(process.stopped, timeout=90000) as blocker:
        assert process.start(str(tmp_path / "data"), [("k1", str(project))])

    assert blocker.args == [True]
    assert [event["event"] for event in events][-1] == "done"
    assert _of(events, "card")[0]["card"]["name"] == "Empty"


def test_a_cancel_stops_the_scan_after_the_project_in_progress(tmp_path):
    projects = [("k1", _project(tmp_path, "one")), ("k2", _project(tmp_path, "two")), ("k3", _project(tmp_path, "three"))]
    stop = {"now": False}
    events = []

    def emit(event):
        events.append(event)
        if event["event"] == "counts":
            stop["now"] = True  # the window asks for a stop after the first count

    summary = scan.run(str(tmp_path / "data"), projects, emit, lambda: stop["now"], load_rules=_loader(LineRules()))

    assert summary["cancelled"] is True
    assert [event["key"] for event in _of(events, "counts")] == ["k1"]
    stored = index.read(tmp_path / "data")
    assert "counts" in stored["k1"]
    assert "counts" not in stored["k2"] and "counts" not in stored["k3"]  # cards are cached for all, counts for one


def _pipe_with(data):
    read_fd, write_fd = os.pipe()
    os.write(write_fd, data)
    os.close(write_fd)  # the end of the pipe, as when the window is gone
    return read_fd


def test_the_child_reads_the_job_line_and_a_cancel_line_after_it():
    from core.project_library.scan_child import _read_job

    read_fd = _pipe_with(b'{"data_dir": "d", "projects": []}\ncancel\n')
    try:
        job, rest = _read_job(read_fd)
    finally:
        os.close(read_fd)

    assert job == {"data_dir": "d", "projects": []}
    assert rest == b"cancel\n"


def test_the_child_sets_cancel_on_a_cancel_line_and_at_the_end_of_the_pipe():
    import threading

    from core.project_library.scan_child import _watch_stdin

    cancelled = threading.Event()
    read_fd = _pipe_with(b"other\ncancel\n")
    try:
        _watch_stdin(read_fd, b"", cancelled)
    finally:
        os.close(read_fd)
    assert cancelled.is_set()

    closed = threading.Event()
    read_fd = _pipe_with(b"no cancel line\n")
    try:
        _watch_stdin(read_fd, b"", closed)
    finally:
        os.close(read_fd)
    assert closed.is_set()  # the end of the pipe means the window is gone


def test_a_real_child_stops_between_projects_when_the_window_cancels(qtbot, tmp_path):
    projects = [("k%d" % number, _project(tmp_path, "p%d" % number)) for number in range(200)]
    process = ScanProcess(None)
    events = []
    process.event_received.connect(events.append)

    with qtbot.waitSignal(process.stopped, timeout=90000) as blocker:
        assert process.start(str(tmp_path / "data"), projects)
        qtbot.waitUntil(lambda: len(_of(events, "counts")) >= 1, timeout=60000)
        process.cancel()

    assert blocker.args == [False]
    done = _of(events, "done")[0]
    assert done["cancelled"] is True
    assert done["counted"] < len(projects)  # the child stopped, it was not killed (no done without a clean end)


def test_a_child_that_ignores_the_cancel_is_killed_after_the_grace_time(qtbot, monkeypatch, tmp_path):
    from ui.project_manager import scan_process

    monkeypatch.setattr(scan_process, "CANCEL_GRACE_MS", 100)
    stubborn = [sys.executable, "-c", "import sys, time; sys.stdin.readline(); time.sleep(600)"]
    process = ScanProcess(None, command=stubborn)

    with qtbot.waitSignal(process.stopped, timeout=60000) as blocker:
        assert process.start(str(tmp_path / "data"), [])
        process.cancel()

    assert blocker.args == [False]
    assert not process.running()


def test_stderr_lines_of_the_child_reach_the_app_log_as_warnings(qtbot, monkeypatch, tmp_path):
    from ui.project_manager import scan_process

    warnings = []
    monkeypatch.setattr(scan_process, "log_warning", warnings.append)
    child = ("import sys; sys.stdin.readline(); "
             "sys.stderr.write('Project index set aside as x\\n'); sys.stderr.flush(); "
             "print('{\"event\": \"done\", \"cancelled\": false}')")
    process = ScanProcess(None, command=[sys.executable, "-c", child])

    with qtbot.waitSignal(process.stopped, timeout=60000) as blocker:
        assert process.start(str(tmp_path / "data"), [])

    assert blocker.args == [True]
    assert "Project scan: Project index set aside as x" in warnings
