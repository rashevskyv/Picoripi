"""Tests for GlossaryStoppedDialog with auto-retry countdown timer and sleep prevention."""
from ui.glossary_stopped_dialog import GlossaryStoppedDialog, remaining_work


def test_dialog_initialization_with_countdown(qtbot, monkeypatch):
    prevent_called = []
    restore_called = []
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: prevent_called.append(True))
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: restore_called.append(True))

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=50,
        described_count=30,
        undescribed_count=20,
        untranslated_count=10,
        completed_units=15,
        total_units=35,
        last_error="Request timed out after 120.0 seconds",
        auto_retry_delay=300,
        can_resume=True,
        prevent_sleep=True,
        sleep_after=False,
    )
    qtbot.addWidget(dialog)

    assert "Describe pass" in dialog.windowTitle()
    assert dialog.resume_btn is not None
    assert "Resume Unfinished Pass (Auto-retry in 05:00)" in dialog.resume_btn.text()
    assert dialog._timer is not None
    assert dialog._timer.isActive()
    assert dialog.prevent_sleep_checkbox.isChecked()
    assert not dialog.sleep_after_checkbox.isChecked()
    assert len(prevent_called) >= 1
    dialog.close()
    assert len(restore_called) >= 1


def test_dialog_manual_resume_click_stops_timer(qtbot, monkeypatch):
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: None)

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=5,
        auto_retry_delay=300,
        can_resume=True,
    )
    qtbot.addWidget(dialog)

    dialog.resume_btn.click()

    assert dialog.action == GlossaryStoppedDialog.ACTION_RESUME
    assert dialog._timer is None


def test_dialog_tick_countdown_and_auto_resume(qtbot, monkeypatch):
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: None)

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=5,
        auto_retry_delay=2,
        can_resume=True,
    )
    qtbot.addWidget(dialog)

    # 1st tick -> 1 second left
    dialog._on_tick()
    assert "00:01" in dialog.resume_btn.text()
    assert dialog.action != GlossaryStoppedDialog.ACTION_RESUME

    # 2nd tick -> 0 seconds left, triggers resume
    dialog._on_tick()
    assert dialog.action == GlossaryStoppedDialog.ACTION_RESUME
    assert dialog._timer is None


def test_dialog_review_glossary_action(qtbot, monkeypatch):
    restore_called = []
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: restore_called.append(True))

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=5,
        auto_retry_delay=300,
        can_resume=True,
    )
    qtbot.addWidget(dialog)

    dialog.review_btn.click()

    assert dialog.action == GlossaryStoppedDialog.ACTION_REVIEW
    assert dialog._timer is None
    assert len(restore_called) >= 1


def test_dialog_close_action(qtbot, monkeypatch):
    restore_called = []
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: restore_called.append(True))

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=5,
        auto_retry_delay=300,
        can_resume=True,
    )
    qtbot.addWidget(dialog)

    dialog.close_btn.click()

    assert dialog.action == GlossaryStoppedDialog.ACTION_CLOSE
    assert dialog._timer is None
    assert len(restore_called) >= 1


def test_dialog_prevent_sleep_toggle(qtbot, monkeypatch):
    prevent_calls = []
    restore_calls = []
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: prevent_calls.append(True))
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: restore_calls.append(True))

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=5,
        auto_retry_delay=300,
        can_resume=True,
        prevent_sleep=True,
    )
    qtbot.addWidget(dialog)
    assert len(prevent_calls) >= 1

    # Uncheck
    dialog.prevent_sleep_checkbox.setChecked(False)
    assert len(restore_calls) >= 1

    # Recheck
    dialog.prevent_sleep_checkbox.setChecked(True)
    assert len(prevent_calls) >= 2
    dialog.close()


def test_dialog_without_resume_capacity(qtbot, monkeypatch):
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: None)

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=10,
        undescribed_count=0,
        untranslated_count=0,
        can_resume=False,
    )
    qtbot.addWidget(dialog)

    assert dialog.resume_btn is None
    assert dialog._timer is None
    dialog.close()


def test_remaining_work_counts_describe_then_translate():
    done, total, left, translated = remaining_work(
        total_entries=1244,
        described_count=476,
        undescribed_count=768,
        untranslated_count=418,
        translate=True,
    )
    assert translated == 58
    assert total == 2488
    assert done == 534
    assert left == 1954


def test_dialog_shows_progress_bar_and_left_count(qtbot, monkeypatch):
    monkeypatch.setattr("utils.power_utils.prevent_sleep", lambda: None)
    monkeypatch.setattr("utils.power_utils.restore_sleep", lambda: None)

    dialog = GlossaryStoppedDialog(
        stage_name="describe",
        total_entries=1244,
        described_count=476,
        undescribed_count=768,
        untranslated_count=418,
        completed_units=399,
        total_units=1003,
        can_resume=True,
        auto_retry_delay=0,
        translate=True,
    )
    qtbot.addWidget(dialog)

    assert dialog.left_steps == 1954
    assert dialog.remaining_label.text() == "1,954 left"
    assert dialog.progress_bar.value() == 534
    assert dialog.progress_bar.maximum() == 2488
    assert "Describe  476 / 1,244" in dialog.breakdown_label.text()
    assert "Translate  58 / 1,244" in dialog.breakdown_label.text()
    assert dialog.pass_bar is not None
    assert dialog.pass_bar.value() == 399
    dialog.close()
