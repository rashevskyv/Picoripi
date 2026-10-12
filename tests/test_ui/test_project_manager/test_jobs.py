"""Background jobs of the Project Manager: results, failures, cancellation and the index they write."""
import json

from core.project_library import index
from ui.project_manager.jobs import BackgroundJob, CardScanJob


def _uiproj(folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": name, "name": name, "blocks": [{}, {}]}), encoding="utf-8")
    return str(project_file)


def test_background_job_reports_its_result(qtbot):
    job = BackgroundJob(lambda a, b: a + b, 2, 3)

    with qtbot.waitSignal(job.done, timeout=5000) as blocker:
        job.start()

    assert blocker.args == [5]


def test_background_job_reports_a_failure_instead_of_raising(qtbot):
    def broken():
        raise RuntimeError("disk gone")

    job = BackgroundJob(broken)

    with qtbot.waitSignal(job.failed, timeout=5000) as blocker:
        job.start()

    assert blocker.args == ["disk gone"]


def test_card_scan_reads_each_project_and_saves_the_cards(qtbot, tmp_path):
    good = _uiproj(tmp_path / "good" / "picoripi", "Aria")
    missing = str(tmp_path / "gone" / "picoripi" / "project.uiproj")
    job = CardScanJob(str(tmp_path / "settings"), [("k-good", good, None), ("k-missing", missing, None)])
    seen = []
    job.card_ready.connect(lambda key, card: seen.append((key, card)))

    with qtbot.waitSignal(job.done, timeout=5000):
        job.start()

    cards = dict(seen)
    assert cards["k-good"]["blocks"] == 2
    assert cards["k-missing"]["issues"] == ["project_file_missing"]
    stored = index.read(tmp_path / "settings")
    assert stored["k-good"]["card"]["name"] == "Aria"
    assert "k-missing" in stored


def test_card_scan_reuses_a_cached_card_when_the_file_is_unchanged(qtbot, tmp_path):
    project = _uiproj(tmp_path / "picoripi", "Aria")
    first = CardScanJob(str(tmp_path), [("k", project, None)])
    cards = []
    first.card_ready.connect(lambda key, card: cards.append(card))
    with qtbot.waitSignal(first.done, timeout=5000):
        first.start()

    cached = dict(cards[0], name="cached marker")
    second = CardScanJob(str(tmp_path), [("k", project, cached)])
    again = []
    second.card_ready.connect(lambda key, card: again.append(card))
    with qtbot.waitSignal(second.done, timeout=5000):
        second.start()

    assert again == [cached]


class _InterruptedScan(CardScanJob):
    """A scan whose interruption was requested before it reached the first project (Qt ignores a request made before start)."""

    def isInterruptionRequested(self):
        return True


def test_cancelled_card_scan_stops_before_the_next_project(tmp_path):
    project = _uiproj(tmp_path / "picoripi", "Aria")
    job = _InterruptedScan(str(tmp_path), [("k", project, None)])
    seen = []
    job.card_ready.connect(lambda key, card: seen.append(key))
    finished = []
    job.done.connect(finished.append)

    job.run()  # on this thread: the cancelled scan returns at once

    assert seen == [] and finished == [0]
    assert index.read(tmp_path) == {}
