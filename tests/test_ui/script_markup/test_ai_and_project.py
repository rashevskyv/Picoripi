import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import (QMessageBox)
from core.script_markup import (
    HierarchyAIPromptTooLarge,
    HierarchyMark,
    HierarchyType,
    HierarchyTypeDefinition,
)
from .helpers import (
    _make_dialog,
    _use_hierarchy_mode,
)

def test_studio_hierarchy_project_payload_roundtrips_markup(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.current_raw_path = "C:/scripts/raw.txt"
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\nNeeds work\n")
    dialog.hierarchy_type_definitions["custom:camera"] = HierarchyTypeDefinition(
        "custom:camera",
        "Camera",
        "Camera direction.",
        "#abc123",
    )
    dialog._rebuild_hierarchy_type_combo()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
        HierarchyMark(3, 3, 3, HierarchyType.TEXT, order=4),
    ]
    dialog._refresh()

    payload = dialog._hierarchy_project_payload()
    restored = _make_dialog(qapp)

    assert restored._apply_hierarchy_project_payload(payload)

    assert restored.raw_edit.toPlainText() == dialog.raw_edit.toPlainText()
    assert restored.current_raw_path == "C:/scripts/raw.txt"
    assert len(restored.hierarchy_marks) == 4
    assert restored._hierarchy_mark_order == 4
    assert restored.hierarchy_type_definitions["custom:camera"].color == "#abc123"
    assert "rendered_markdown" in payload
    assert payload["unmarked_ranges"]
    assert "Chapter One" in restored.flags_list.topLevelItem(0).child(0).text(0)

def test_studio_publishes_saved_hierarchy_project_for_mempalace(qapp, tmp_path):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\n")
    raw_path = tmp_path / "raw_script.txt"
    dialog.current_raw_path = str(raw_path)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1)
    ]
    project_path = tmp_path / "script_markup_project.json"
    dialog.mw.mempalace_builder_dialog = MagicMock()

    with patch(
        "ui.script_markup_studio_dialog.QFileDialog.getSaveFileName",
        return_value=(str(project_path), "JSON"),
    ) as save_dialog, patch("ui.script_markup_studio_dialog.QMessageBox.information"):
        assert dialog._save_hierarchy_project()

    expected = str(project_path.resolve())
    assert dialog.current_hierarchy_project_path == expected
    assert save_dialog.call_args.args[3] == "JSON (*.json)"
    assert save_dialog.call_args.args[2] == str(tmp_path / "script_markup_project.json")
    assert dialog.project_state_label.text() == f"Markup project: {expected}"
    assert dialog.mw.script_markup_studio_project_path == expected
    dialog.mw.mempalace_builder_dialog._load_active_markup_studio_project.assert_called_once()

def test_studio_publishes_opened_hierarchy_project_for_mempalace(qapp, tmp_path):
    source = _make_dialog(qapp)
    _use_hierarchy_mode(source)
    source.raw_edit.setPlainText("Act One\n")
    source.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1)
    ]
    source._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(source._hierarchy_project_payload()),
        encoding="utf-8",
    )
    restored = _make_dialog(qapp)

    with patch(
        "ui.script_markup_studio_dialog.QFileDialog.getOpenFileName",
        return_value=(str(project_path), "JSON"),
    ):
        assert restored._load_hierarchy_project()

    expected = str(project_path.resolve())
    assert restored.current_hierarchy_project_path == expected
    assert restored.mw.script_markup_studio_project_path == expected

def test_studio_finishes_complete_markup_for_mempalace(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA\nHello.\n")
    speaker = HierarchyMark(
        0, 0, 0, HierarchyType.SPEAKER, text="MIDNA", order=1,
        origin="local_autofill", approved=False,
    )
    text = HierarchyMark(
        1, 1, 1, HierarchyType.TEXT, order=2,
        origin="local_autofill", approved=False,
    )
    dialog.hierarchy_marks = [speaker, text]
    dialog._refresh()
    questions = []
    saves = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.question",
        lambda *_args: questions.append(_args) or QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        dialog,
        "_save_hierarchy_project",
        lambda: saves.append(True) or True,
    )

    assert dialog._finish_markup_for_mempalace() is True

    assert all(mark.approved for mark in dialog.hierarchy_marks)
    assert len(questions) == 1
    assert "accept 2 visible Auto-fill nodes" in questions[0][2]
    assert saves == [True]

def test_studio_applies_ai_marks_without_touching_manual_marks(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\nFADO\nHey!\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
    ]
    dialog._hierarchy_mark_order = 3
    dialog._refresh()

    added, skipped = dialog._apply_hierarchy_ai_marks([
        HierarchyMark(2, 2, 2, HierarchyType.TEXT),
        HierarchyMark(3, 3, 1, HierarchyType.SPEAKER, text="FADO"),
        HierarchyMark(4, 4, 2, HierarchyType.TEXT),
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Duplicate"),
    ])

    assert added == 3
    assert skipped == 1
    assert {mark.text for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.SPEAKER} == {
        "RUSL",
        "FADO",
    }
    assert "# Act One" in dialog._psm_text
    assert "**RUSL**: Hello." in dialog._psm_text
    assert "**FADO**: Hey!" in dialog._psm_text

def test_studio_continue_from_examples_requires_existing_marks(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("RUSL\nHello.\n")
    messages = []

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    def fail_provider_lookup():
        raise AssertionError("Provider should not be created without marked examples.")

    monkeypatch.setattr(dialog, "_create_hierarchy_ai_provider", fail_provider_lookup)

    dialog._continue_hierarchy_from_examples()

    assert messages == [
        (
            "Continue from marked examples",
            "Mark at least one hierarchy example manually, then run this auto-fill again.",
        )
    ]

def test_studio_continue_from_examples_is_local_and_applies_repeated_speaker_blocks(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\nFADO\nHey!\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 3
    messages = []

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    def fail_provider_lookup():
        raise AssertionError("Continue from marked examples must not use an AI provider.")

    monkeypatch.setattr(dialog, "_create_hierarchy_ai_provider", fail_provider_lookup)

    dialog._continue_hierarchy_from_examples()

    assert messages
    assert messages[-1][0] == "Continue from marked examples"
    assert "Added 2 local hierarchy marks." in messages[-1][1]
    assert {mark.text for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.SPEAKER} == {
        "RUSL",
        "FADO",
    }
    assert "**RUSL**: Hello." in dialog._psm_text
    assert "**FADO**: Hey!" in dialog._psm_text

def test_studio_continue_finds_learned_context_inside_existing_text(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "Known line.\n"
        "(Example condition}\n"
        "Example reply.\n"
        "(Another condition}\n"
        "Another reply.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(
            2,
            2,
            4,
            HierarchyType.CONTEXT,
            text="Example condition",
            start_col=1,
            end_col=18,
            order=3,
        ),
        HierarchyMark(3, 5, 5, HierarchyType.TEXT, order=4),
    ]
    dialog._hierarchy_mark_order = 5
    assert dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()) == []
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 1 local hierarchy marks." in messages[-1][1]
    contexts = sorted(
        (mark.start_line, mark.text, mark.start_col, mark.end_col)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.CONTEXT
    )
    assert contexts == [
        (2, "Example condition", 1, 18),
        (4, "Another condition", 1, 18),
    ]
    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 5), (5, 5, 5)]

def test_studio_continue_fills_speaker_on_synthetic_scene_start(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "TALO\nTime to practice!\n~~~~~~~~~~~~~~~~\nMALO\nKnown line.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(
            0, 2, 2, HierarchyType.STRUCTURE, text="Scene 4", order=1
        ),
        HierarchyMark(3, 3, 3, HierarchyType.SPEAKER, text="MALO", order=2),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 2 local hierarchy marks." in messages[-1][1]
    assert any(
        mark.type_id == HierarchyType.SPEAKER
        and mark.start_line == 0
        and mark.text == "TALO"
        for mark in dialog.hierarchy_marks
    )
    assert any(
        mark.type_id == HierarchyType.TEXT
        and (mark.start_line, mark.end_line) == (1, 1)
        for mark in dialog.hierarchy_marks
    )

def test_studio_continue_learns_custom_type_and_splits_existing_text(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    custom_type = "custom:camera"
    dialog.hierarchy_type_definitions[custom_type] = HierarchyTypeDefinition(
        custom_type,
        "Camera",
        "Camera direction",
        "#dceeff",
    )
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "Known line.\n"
        "<Camera: close-up>\n"
        "Reply.\n"
        "<Camera: wide shot>\n"
        "Next reply.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 5, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(
            2,
            2,
            4,
            custom_type,
            text="Camera: close-up",
            start_col=1,
            end_col=17,
            order=3,
        ),
    ]
    dialog._hierarchy_mark_order = 4
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 1 local hierarchy marks." in messages[-1][1]
    assert "Other/custom types: 1" in messages[-1][1]
    assert sorted(
        (mark.start_line, mark.text, mark.start_col, mark.end_col)
        for mark in dialog.hierarchy_marks
        if mark.type_id == custom_type
    ) == [
        (2, "Camera: close-up", 1, 17),
        (4, "Camera: wide shot", 1, 18),
    ]
    assert sorted(
        (mark.start_line, mark.end_line)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1), (3, 3), (5, 5)]

def test_studio_continue_fills_unicode_speaker_with_number_suffix(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\nKnown line.\nCAFÉ MAN #1\nWelcome to my shop.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda *_args: None,
    )

    dialog._continue_hierarchy_from_examples()

    assert any(
        mark.type_id == HierarchyType.SPEAKER
        and mark.start_line == 2
        and mark.text == "CAFÉ MAN #1"
        for mark in dialog.hierarchy_marks
    )
    assert any(
        mark.type_id == HierarchyType.TEXT
        and (mark.start_line, mark.end_line) == (3, 3)
        for mark in dialog.hierarchy_marks
    )

def test_studio_hierarchy_ai_progress_shows_scope_and_elapsed_time(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    progress_values = []
    step_updates = []

    class FakeStatus:
        is_running = True
        detail = ""

        def update_progress(self, value):
            progress_values.append(value)

        def set_detail_text(self, text):
            self.detail = text

        def update_step(self, index, text, status):
            step_updates.append((index, text, status))

    status = FakeStatus()
    dialog._hierarchy_ai_status = status
    dialog._hierarchy_ai_started_at = 10.0
    monkeypatch.setattr("ui.script_markup_studio_dialog.time.monotonic", lambda: 75.0)

    dialog._on_hierarchy_ai_progress(1, 3, "Act One")

    assert progress_values == [0]
    assert "Scope 1/3: Act One" in status.detail
    assert "Waiting for AI response... elapsed 01:05" in status.detail
    assert step_updates == [(1, "Processing structure 1/3", 1)]

def test_studio_auto_join_duplicate_structures_does_not_require_single_line_headings(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Part A\nFirst block.\nPart A\nSecond block.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Part A", order=1),
        HierarchyMark(2, 3, 0, HierarchyType.STRUCTURE, text="Part A", order=2),
    ]
    dialog._refresh()

    changed = dialog._auto_join_adjacent_duplicate_structures()
    dialog._apply_ignore_precedence()
    dialog._refresh()

    assert changed == 1
    structures = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE
    ]
    assert [(mark.start_line, mark.end_line, mark.text) for mark in structures] == [
        (0, 3, "Part A"),
    ]
    ignored = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.IGNORE
    ]
    assert [(mark.start_line, mark.end_line) for mark in ignored] == [(2, 2)]
    assert dialog._psm_text.count("# Part A") == 1

def test_studio_auto_join_duplicate_structures_respects_breaker_boundaries(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Scene\nBeat one.\n~~~~~\nScene\nBeat two.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 1, HierarchyType.STRUCTURE, text="Scene", order=1),
        HierarchyMark(2, 2, 1, HierarchyType.BREAKER, order=2),
        HierarchyMark(3, 4, 1, HierarchyType.STRUCTURE, text="Scene", order=3),
    ]
    dialog._refresh()

    assert dialog._auto_join_adjacent_duplicate_structures() == 0
    structures = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE
    ]
    assert [(mark.start_line, mark.end_line, mark.text) for mark in structures] == [
        (0, 1, "Scene"),
        (3, 4, "Scene"),
    ]

def test_studio_prepares_ai_markup_jobs_by_structure_when_full_prompt_is_too_large(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nA\n" + ("x" * 120) + "\nAct Two\nB\n" + ("y" * 120) + "\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(3, 5, 0, HierarchyType.STRUCTURE, text="Act Two", order=2),
    ]
    dialog._refresh()

    def fake_builder(payload, max_prompt_chars=None):
        scope = payload.get("scope") or {}
        label = scope.get("label") or "full script"
        if label == "full script":
            raise HierarchyAIPromptTooLarge("full prompt too large")
        return SimpleNamespace(
            scope_label=label,
            prompt_chars=100,
            unmarked_range_count=len(payload.get("unmarked_ranges", [])),
            messages=[],
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        fake_builder,
    )

    jobs = dialog._prepare_hierarchy_ai_jobs(
        dialog.raw_edit.toPlainText().splitlines(),
        dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
    )

    assert [job.scope_label.split(" (raw script")[0] for job in jobs] == ["Act One", "Act Two"]

def test_studio_ai_markup_reports_raw_line_when_even_single_scope_is_too_large(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(("Very long line\n") * 20)
    dialog._refresh()

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        lambda _payload, max_prompt_chars=None: (_ for _ in ()).throw(
            HierarchyAIPromptTooLarge("full prompt too large")
        ),
    )

    try:
        dialog._prepare_hierarchy_ai_jobs(
            dialog.raw_edit.toPlainText().splitlines(),
            dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
        )
    except HierarchyAIPromptTooLarge as exc:
        assert "A raw script section is too large" in str(exc)
        assert "raw script line 1" in str(exc)
    else:
        raise AssertionError("Expected raw-scope guidance for too-large script.")

def test_studio_ai_markup_prepares_unstructured_scope_outside_structures(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Outside structure\nAct One\nInside structure\n")
    dialog.hierarchy_marks = [
        HierarchyMark(1, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()

    def fake_builder(payload, max_prompt_chars=None):
        scope = payload.get("scope") or {}
        label = scope.get("label") or "full script"
        if label == "full script":
            raise HierarchyAIPromptTooLarge("full prompt too large")
        return SimpleNamespace(
            scope_label=label,
            prompt_chars=100,
            unmarked_range_count=len(payload.get("unmarked_ranges", [])),
            messages=[],
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        fake_builder,
    )

    jobs = dialog._prepare_hierarchy_ai_jobs(
        dialog.raw_edit.toPlainText().splitlines(),
        dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
    )

    assert jobs[0].scope_label == "Unstructured source (raw script line 1)"
    assert jobs[1].scope_label.startswith("Act One")
    assert "lines 1-1" not in jobs[0].scope_label

def test_studio_hierarchy_template_payload_loads_type_definitions_only(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Camera pans.\n")
    dialog.hierarchy_type_definitions["custom:camera"] = HierarchyTypeDefinition(
        "custom:camera",
        "Camera",
        "Camera direction.",
        "#abc123",
    )
    dialog._rebuild_hierarchy_type_combo()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 1, "custom:camera", text="Camera pans", order=1),
    ]
    dialog._refresh()

    payload = dialog._hierarchy_template_payload()
    restored = _make_dialog(qapp)

    assert restored._apply_hierarchy_template_payload(payload)

    assert restored.hierarchy_marks == []
    assert restored.hierarchy_type_definitions["custom:camera"].label == "Camera"
    assert restored.hierarchy_type_definitions["custom:camera"].color == "#abc123"
    assert payload["examples"][0]["source_excerpt"] == "Camera pans."
    assert payload["ai_instructions"]

def test_studio_opens_builder_project_at_exact_line_without_reloading_it_twice(qapp, tmp_path):
    source = _make_dialog(qapp)
    _use_hierarchy_mode(source)
    source.raw_edit.setPlainText("Act\nMIDNA\nFirst line\nSecond line\n")
    source.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="MIDNA", order=2),
        HierarchyMark(2, 3, 2, HierarchyType.TEXT, order=3),
    ]
    source._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(source._hierarchy_project_payload()),
        encoding="utf-8",
    )
    studio = _make_dialog(qapp)

    assert studio.open_hierarchy_project_at_line(str(project_path), 2)
    assert studio.current_hierarchy_project_path == str(project_path.resolve())
    assert studio.raw_edit.textCursor().blockNumber() == 2
    assert studio.flags_list.currentItem() is not None

    studio.raw_edit.appendPlainText("Unsaved new markup")
    assert studio.open_hierarchy_project_at_line(str(project_path), 3)
    assert studio.raw_edit.textCursor().blockNumber() == 3
    assert "Unsaved new markup" in studio.raw_edit.toPlainText()

def test_studio_assigns_linked_dialogue_to_speaker_and_saves(qapp, tmp_path):
    studio = _make_dialog(qapp)
    _use_hierarchy_mode(studio)
    studio.raw_edit.setPlainText("LETTER\nAbout Mail Delivery\n")
    studio.hierarchy_marks = [
        HierarchyMark(
            0, 0, 3, HierarchyType.SPEAKER, text="LETTER", order=1,
            origin="speaker_assignment",
        ),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
    ]
    studio._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(studio._hierarchy_project_payload()), encoding="utf-8"
    )
    studio.current_hierarchy_project_path = str(project_path.resolve())

    assert studio.assign_speaker_at_line(str(project_path), 1, "POSTMAN")

    assert studio.hierarchy_marks[0].text == "POSTMAN"
    saved = json.loads(project_path.read_text(encoding="utf-8"))
    assert saved["hierarchy_marks"][0]["text"] == "POSTMAN"
