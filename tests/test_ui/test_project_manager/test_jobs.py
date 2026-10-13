"""Background jobs of the Project Manager: results and failures. The project scan has its own tests (test_scan.py)."""
from ui.project_manager.jobs import BackgroundJob


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
