"""The series term fill worker (D45, item 1): one result per project, progress, and cancel before the next project."""

from core.translation import series_fill
from handlers.series_term_fill_worker import SeriesTermFillWorker


def test_the_worker_fills_each_project_and_reports_a_result_per_project(qtbot, monkeypatch, tmp_path):
    calls = []

    def fake_fill(project_dir, entries, should_cancel):
        calls.append(project_dir.name)
        return {"status": "done", "by_status": {}, "refused_tags": 0, "written": 1, "kept": 0, "planned": 1}

    monkeypatch.setattr(series_fill, "fill_project", fake_fill)
    projects = {"TP HD": tmp_path / "tp_hd" / "m.json", "WW": tmp_path / "ww" / "m.json"}
    worker = SeriesTermFillWorker([("Pikachu", "Пікачу")], projects)

    with qtbot.waitSignal(worker.done, timeout=5000) as signal:
        worker.start()

    assert sorted(calls) == ["tp_hd", "ww"]
    assert sorted(signal.args[0]) == ["TP HD", "WW"]
    worker.wait(2000)


def test_a_cancel_before_the_first_project_reports_none_and_writes_nothing(qtbot, monkeypatch, tmp_path):
    def never(*args, **kwargs):
        raise AssertionError("no project expected")

    monkeypatch.setattr(series_fill, "fill_project", never)
    worker = SeriesTermFillWorker([("Pikachu", "Пікачу")], {"TP HD": tmp_path / "m.json"})
    worker.cancel()

    with qtbot.waitSignal(worker.done, timeout=5000) as signal:
        worker.start()

    assert signal.args[0] is None
    worker.wait(2000)


def test_a_failing_project_is_reported_and_the_others_still_run(qtbot, monkeypatch, tmp_path):
    def fake_fill(project_dir, entries, should_cancel):
        if project_dir.name == "bad":
            raise OSError("disk gone")
        return {"status": "no terms"}

    monkeypatch.setattr(series_fill, "fill_project", fake_fill)
    projects = {"Bad": tmp_path / "bad" / "m.json", "Good": tmp_path / "good" / "m.json"}
    worker = SeriesTermFillWorker([("Pikachu", "Пікачу")], projects)

    with qtbot.waitSignal(worker.done, timeout=5000) as signal:
        worker.start()

    assert signal.args[0]["Bad"] == {"status": "failed", "error": "disk gone"}
    assert signal.args[0]["Good"] == {"status": "no terms"}
    worker.wait(2000)
