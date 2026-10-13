"""The project scan: cards, icons and counts with their cache rules, and the real child process that runs it.

Projects use the real ``plain_text`` plugin folder (so the card has no missing-plugin issue); the rules that count are
explicit fakes passed to ``scan.run``. The last test starts the real child process.
"""
import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.project_library import index, scan
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
