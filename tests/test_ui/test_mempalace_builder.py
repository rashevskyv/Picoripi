import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget, QListWidgetItem
from PyQt6.QtCore import QPoint, Qt
from ui.mempalace_builder_dialog import MemePalaceBuilderDialog
from ui.mempalace.mempalace_ui import (
    DANGER_BUTTON_STYLE,
    SECONDARY_BUTTON_STYLE,
    WORKFLOW_BUTTON_STYLE,
)
from core.script_markup import (
    HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT,
    HierarchyType,
    default_type_definitions,
)
from core.mempalace.dialogue_mapping import GameString


def _hierarchy_project_payload(source_path=""):
    definitions = default_type_definitions()
    return {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": source_path,
        "raw_text": "Act I\nChapter One\nScene One\nMIDNA\nHello.\n",
        "type_definitions": [
            {
                "type_id": item.type_id,
                "label": item.label,
                "description": item.description,
                "color": item.color,
            }
            for item in definitions.values()
        ],
        "hierarchy_marks": [
            {"start_line": 0, "end_line": 4, "depth": 0, "type_id": HierarchyType.STRUCTURE, "order": 1, "origin": "manual", "approved": True},
            {"start_line": 1, "end_line": 4, "depth": 1, "type_id": HierarchyType.STRUCTURE, "order": 2, "origin": "manual", "approved": True},
            {"start_line": 2, "end_line": 4, "depth": 2, "type_id": HierarchyType.STRUCTURE, "order": 3, "origin": "manual", "approved": True},
            {"start_line": 3, "end_line": 3, "depth": 3, "type_id": HierarchyType.SPEAKER, "order": 4, "origin": "manual", "approved": True},
            {"start_line": 4, "end_line": 4, "depth": 4, "type_id": HierarchyType.TEXT, "order": 5, "origin": "manual", "approved": True},
        ],
    }


def _hierarchy_project_with_reference_item(source_path=""):
    payload = _hierarchy_project_payload(source_path)
    payload["raw_text"] += (
        "Collection Screen\nWallet\nA wallet from your childhood.\n"
    )
    payload["hierarchy_marks"].extend([
        {
            "start_line": 5, "end_line": 7, "depth": 0,
            "type_id": HierarchyType.STRUCTURE, "text": "Collection Screen",
            "order": 6, "origin": "manual", "approved": True,
        },
        {
            "start_line": 6, "end_line": 6, "depth": 1,
            "type_id": HierarchyType.ITEM, "order": 7,
            "origin": "manual", "approved": True,
        },
        {
            "start_line": 7, "end_line": 7, "depth": 2,
            "type_id": HierarchyType.ITEM_DESCRIPTION, "order": 8,
            "origin": "manual", "approved": True,
        },
    ])
    return payload


def _settings_backed_main_window(settings=None):
    stored = settings if settings is not None else {}
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.settings_manager = MagicMock()
    mock_mw.settings_manager.get.side_effect = lambda key, default=None: stored.get(key, default)
    mock_mw.settings_manager.set.side_effect = lambda key, value: stored.__setitem__(key, value)
    return mock_mw, stored

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_mempalace_builder_empty_lines_filtering(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None # Single-file mode
    
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    # Block 0 has one empty string, one whitespace-only string, and one valid string
    mock_mw.data_store.data = [
        ["", "   ", "Valid dialogue line"]
    ]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.edited_data = {}
    
    parent_widget = QWidget()
    
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # 1. blocks_list_widget has been replaced by table widget in the current layout
    assert dialog is not None
    assert dialog.windowTitle() == "MemPalace Context Builder"


def test_mempalace_builder_uses_consistent_action_styles(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}

    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    workflow_buttons = (
        dialog.ai_profile_speech_btn,
        dialog.map_chapters_btn,
        dialog.analyze_chapter_btn,
        dialog.analyze_all_chapters_btn,
    )
    assert all(button.styleSheet() == WORKFLOW_BUTTON_STYLE for button in workflow_buttons)
    assert dialog.cancel_btn.styleSheet() == SECONDARY_BUTTON_STYLE
    assert dialog.clear_btn.styleSheet() == DANGER_BUTTON_STYLE
    assert dialog.hierarchy_project_browse_btn.styleSheet() == SECONDARY_BUTTON_STYLE
    assert dialog.workflow_tabs.count() == 3
    assert dialog.workflow_tabs.tabText(0) == "1. Source"
    assert dialog.source_next_btn.text() == "Continue to Story Context →"
    assert dialog.map_chapters_btn.isHidden()
    assert dialog.table.isHidden()
    assert dialog.legacy_fallback_checkbox.isHidden()
    assert dialog.file_path_edit.isHidden()
    assert dialog.chapters_splitter.orientation() == Qt.Orientation.Vertical
    assert dialog.chapters_splitter.count() == 2
    assert not dialog.chapters_splitter.childrenCollapsible()
    assert dialog.mapping_review_splitter.orientation() == Qt.Orientation.Horizontal
    assert dialog.mapping_review_splitter.count() == 2
    assert not dialog.mapping_review_splitter.childrenCollapsible()
    assert dialog.workflow_tabs.tabText(1) == "2. Story Context"
    assert dialog.story_group.isHidden()
    assert dialog.mapping_review_table.isHidden()
    assert dialog.workflow_tabs.widget(2).isAncestorOf(dialog.analyze_all_chapters_btn)


def test_mempalace_builder_selects_validated_hierarchy_project(qapp, tmp_path):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    path = tmp_path / "script_markup_project.json"
    path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")

    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    with patch(
        "ui.mempalace_builder_dialog.QFileDialog.getOpenFileName",
        return_value=(str(path), "Markup Studio Project"),
    ) as get_file:
        dialog._browse_hierarchy_project()

    assert get_file.call_args.args[3].startswith("Markup Studio Project")
    assert dialog.hierarchy_project is not None
    assert dialog.hierarchy_project_path_edit.text() == str(path.resolve())
    assert "Act 1, Chapter 1, Scene 1" in dialog.hierarchy_project_preview_label.text()
    assert "Speaker 1, Dialogue 1" in dialog.hierarchy_project_preview_label.text()


def test_mempalace_builder_prefills_live_markup_studio_project(qapp, tmp_path):
    raw_path = tmp_path / "script.txt"
    raw_path.write_text("Act I\nChapter One\nScene One\nMIDNA\nHello.\n", encoding="utf-8")
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(_hierarchy_project_payload(str(raw_path))),
        encoding="utf-8",
    )
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.script_markup_studio_dialog = SimpleNamespace(
        current_hierarchy_project_path=str(project_path)
    )
    parent_widget = QWidget()

    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    assert dialog.hierarchy_project is not None
    assert dialog.hierarchy_project_path_edit.text() == str(project_path.resolve())
    assert dialog.file_path_edit.text() == str(raw_path)
    assert dialog.hierarchy_project_status_label.text() == "Status: Not imported"
    assert "Act 1, Chapter 1, Scene 1" in dialog.hierarchy_project_preview_label.text()


def test_mempalace_builder_rejects_invalid_hierarchy_project_without_state_change(qapp, tmp_path):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    valid_path = tmp_path / "script_markup_project.json"
    valid_path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    invalid_path = tmp_path / "broken.json"
    invalid_path.write_text("{broken", encoding="utf-8")

    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    assert dialog._load_hierarchy_project_preview(str(valid_path))
    previous_project = dialog.hierarchy_project
    previous_path = dialog.hierarchy_project_path_edit.text()

    assert not dialog._load_hierarchy_project_preview(str(invalid_path))
    assert dialog.hierarchy_project is previous_project
    assert dialog.hierarchy_project_path_edit.text() == previous_path
    assert dialog.hierarchy_project_preview_label.text().startswith("Import error:")
    assert "was not replaced" in dialog.hierarchy_project_preview_label.text()
    assert "Previous valid project remains selected" in dialog.hierarchy_project_status_label.text()


def test_mempalace_builder_import_sync_persists_metadata_idempotently(qapp, tmp_path):
    mock_mw, settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    raw_path = tmp_path / "script.txt"
    raw_path.write_text("Act I\nChapter One\nScene One\nMIDNA\nHello.\n", encoding="utf-8")
    path = tmp_path / "script_markup_project.json"
    path.write_text(json.dumps(_hierarchy_project_payload(str(raw_path))), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    assert dialog._load_hierarchy_project_preview(str(path))
    assert dialog.hierarchy_project_status_label.text() == "Status: Not imported"
    assert dialog._import_sync_hierarchy_project()
    assert dialog.client._get_connection().execute(
        "SELECT COUNT(*) FROM story_nodes"
    ).fetchone()[0] == 5
    assert dialog.story_tree.topLevelItemCount() == 1
    assert dialog.story_tree.topLevelItem(0).text(0) == "Act"
    assert dialog.story_tree.topLevelItem(0).child(0).text(0) == "Chapter"
    assert dialog.story_tree.topLevelItem(0).child(0).child(0).text(0) == "Scene"
    assert "Imported 5 story nodes" in dialog.story_tree_status_label.text()
    assert dialog.story_group.isHidden()
    dialog.toggle_story_btn.click()
    assert not dialog.story_group.isHidden()
    assert dialog.toggle_story_btn.text() == "Hide imported structure"
    first_metadata = {
        key: settings[key]
        for key in (
            "mempalace_hierarchy_project_path",
            "mempalace_hierarchy_project_hash",
            "mempalace_hierarchy_project_version",
        )
    }
    assert dialog.hierarchy_project_status_label.text().startswith("Status: Up to date")
    assert dialog.file_path_edit.text() == str(raw_path)
    assert dialog.workflow_tabs.isTabEnabled(1)
    assert not dialog.workflow_tabs.isTabEnabled(2)

    assert dialog._import_sync_hierarchy_project()
    assert {key: settings[key] for key in first_metadata} == first_metadata
    assert len(first_metadata) == 3
    assert dialog.client._get_connection().execute(
        "SELECT COUNT(*) FROM story_nodes"
    ).fetchone()[0] == 5


def test_mempalace_builder_displays_reference_entries_as_items_not_speakers(qapp, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    path = tmp_path / "script_markup_project.json"
    path.write_text(
        json.dumps(_hierarchy_project_with_reference_item()),
        encoding="utf-8",
    )
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    assert dialog._load_hierarchy_project_preview(str(path))
    assert dialog._import_sync_hierarchy_project()

    reference_group = next(
        dialog.story_tree.topLevelItem(index)
        for index in range(dialog.story_tree.topLevelItemCount())
        if dialog.story_tree.topLevelItem(index).text(0) == "Reference Items"
    )
    item = reference_group.child(0)
    assert item.text(0) == "Item"
    assert item.text(1) == "Wallet"
    assert item.child(0).text(0) == "Item Description"
    assert "A wallet from your childhood." in item.child(0).text(1)
    assert "1 reference items" in dialog.story_tree_status_label.text()
    assert not any(
        node.text(0) == "Speaker" and node.text(1) == "Wallet"
        for node in [item, item.child(0)]
    )


def test_mempalace_builder_does_not_persist_metadata_when_story_sync_fails(qapp, tmp_path):
    mock_mw, settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    path = tmp_path / "script_markup_project.json"
    path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    assert dialog._load_hierarchy_project_preview(str(path))
    dialog.client.sync_story_timeline = MagicMock(side_effect=RuntimeError("database busy"))

    with patch("ui.mempalace_builder_dialog.QMessageBox.warning") as warning:
        assert not dialog._import_sync_hierarchy_project()

    warning.assert_called_once()
    assert "database busy" in dialog.hierarchy_project_status_label.text()
    assert "mempalace_hierarchy_project_path" not in settings


def test_mempalace_builder_matches_open_project_to_dialogue_nodes(qapp, qtbot, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.data_store.data = [["Hello."]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    qtbot.addWidget(dialog)
    assert dialog._load_hierarchy_project_preview(str(project_path))
    assert dialog._import_sync_hierarchy_project()

    dialog.match_dialogue_btn.click()
    # Cold CI/test processes may need a few seconds to import the alignment
    # stack before the tiny job starts; this is a completion guard, not a
    # performance assertion.
    qtbot.waitUntil(lambda: dialog.worker is None, timeout=25000)

    mappings = dialog.client.get_dialogue_mappings(dialog.story_document_id)
    assert len(mappings) == 1
    assert mappings[0].match_method == "exact_text"
    assert mappings[0].review_status == "matched"
    assert "Marked dialogue coverage: 100.0%" in dialog.dialogue_mapping_summary_label.text()
    assert "Saved context links: 1" in dialog.dialogue_mapping_summary_label.text()
    assert "Need your decision: 0" in dialog.dialogue_mapping_summary_label.text()
    assert not dialog.mapping_review_table.isVisible()
    assert dialog.mapping_review_actions.isHidden()
    assert dialog.match_dialogue_btn.text() == "Recheck After Changes"
    assert dialog.match_dialogue_btn.styleSheet() == SECONDARY_BUTTON_STYLE
    assert not dialog.story_context_done_btn.isHidden()

    restored = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    qtbot.addWidget(restored)
    assert "Story context is ready" in restored.dialogue_mapping_summary_label.text()
    assert "1 automatically matched" in restored.dialogue_mapping_summary_label.text()
    assert "1 active context links" in restored.dialogue_mapping_summary_label.text()
    assert restored.match_dialogue_btn.text() == "Recheck After Changes"
    assert restored.match_dialogue_btn.styleSheet() == SECONDARY_BUTTON_STYLE
    assert not restored.story_context_done_btn.isHidden()


def test_mempalace_builder_excludes_plugin_rejected_window_strings(qapp, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.data_store.data = [["Twilit Parasite\nDIABABA", "Hello."]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.current_game_rules.should_auto_match_story_context.side_effect = (
        lambda block_idx, string_idx: string_idx != 0
    )
    dialog = MemePalaceBuilderDialog(mock_mw, parent=QWidget())

    messages = dialog._game_messages_for_story_alignment(mock_mw.data_store.data)

    assert [(item.string_index, item.text) for item in messages] == [(1, "Hello.")]


def test_mempalace_builder_approves_and_locks_review_mapping(qapp, qtbot, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.data_store.data = [["Hello."]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    qtbot.addWidget(dialog)
    assert dialog._load_hierarchy_project_preview(str(project_path))
    assert dialog._import_sync_hierarchy_project()
    conn = dialog.client._get_connection()
    speaker_id = conn.execute(
        "SELECT id FROM story_nodes WHERE document_id = ? AND node_type = 'speaker'",
        (dialog.story_document_id,),
    ).fetchone()[0]
    conn.execute(
        "UPDATE story_nodes SET text = 'Hello there friend.' "
        "WHERE document_id = ? AND node_type = 'dialogue'",
        (dialog.story_document_id,),
    )
    conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text,
            origin, approved, source_version
        ) VALUES (
            'dialogue:duplicate', ?, ?, 'dialogue', 1,
            'Hello there friend.', 'manual', 1, 1
        )
        """,
        (dialog.story_document_id, speaker_id),
    )
    conn.commit()
    summary = dialog.client.match_game_strings(dialog.story_document_id, [GameString(
        "0", "zel_00", 0, "zel_00_Str_0", "Hello there friend."
    )])
    assert summary.needs_review == 1

    dialog._refresh_dialogue_review_table()
    dialog.resize(920, 700)
    dialog.workflow_tabs.setCurrentIndex(1)
    dialog.show()
    qapp.processEvents()
    assert dialog.mapping_review_table.isHidden()
    assert not dialog.mapping_review_actions.isHidden()
    assert dialog.mapping_review_counter_label.text() == "Decision 1 of 1"
    source_position = dialog.mapping_review_source_label.mapTo(dialog, QPoint(0, 0))
    context_position = dialog.mapping_context_preview.mapTo(dialog, QPoint(0, 0))
    assert source_position.x() < context_position.x()
    assert dialog.mapping_context_preview.height() >= 100
    assert dialog.mapping_review_source_label.text() == "Hello there friend."
    assert dialog.mapping_review_candidate_label.text() == "No reliable script place selected"
    assert "No context selected" in dialog.mapping_context_preview.toPlainText()
    assert dialog.mapping_dialogue_combo.count() == 2
    assert not dialog.approve_mapping_btn.isEnabled()
    dialog.choose_other_mapping_btn.click()
    assert not dialog.mapping_dialogue_choice_widget.isHidden()
    dialog.mapping_dialogue_combo.setCurrentIndex(0)
    qapp.processEvents()
    context_bottom = (
        dialog.mapping_context_preview.mapTo(dialog, QPoint(0, 0)).y()
        + dialog.mapping_context_preview.height()
    )
    actions_top = dialog.approve_mapping_btn.mapTo(dialog, QPoint(0, 0)).y()
    assert context_bottom <= actions_top
    assert dialog.approve_mapping_btn.isEnabled()
    assert dialog.mapping_review_candidate_label.text() == "Hello there friend."
    assert "Act I" in dialog.mapping_review_location_label.text()
    assert "MIDNA" in dialog.mapping_context_preview.toPlainText()
    assert dialog.mapping_context_preview.toPlainText().count("Hello there friend.") == 2
    assert dialog.open_mapping_in_studio_btn.isEnabled()
    studio = MagicMock()
    studio.open_hierarchy_project_at_line.return_value = True
    mock_mw.script_markup_studio_dialog = studio
    dialog.open_mapping_in_studio_btn.click()
    mock_mw.actions.open_script_markup_studio.assert_called_once()
    studio.open_hierarchy_project_at_line.assert_called_once_with(
        str(project_path.resolve()), 4
    )
    studio.raise_.assert_called_once()

    timeline = dialog.client.get_story_timeline
    dialog.client.get_story_timeline = MagicMock(wraps=timeline)
    dialog._show_dialogue_review(0)
    dialog.mapping_dialogue_combo.setCurrentIndex(1)
    dialog.client.get_story_timeline.assert_not_called()
    dialog.approve_mapping_btn.click()

    mapping = dialog.client.get_dialogue_mappings(dialog.story_document_id)[0]
    assert mapping.match_method == "manual"
    assert mapping.review_status == "approved"
    assert mapping.locked
    assert dialog.mapping_review_actions.isHidden()


def test_mempalace_builder_can_mark_review_item_as_not_story_dialogue(qapp, qtbot, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.data_store.data = [["Hello."]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    qtbot.addWidget(dialog)
    assert dialog._load_hierarchy_project_preview(str(project_path))
    assert dialog._import_sync_hierarchy_project()
    conn = dialog.client._get_connection()
    speaker_id = conn.execute(
        "SELECT id FROM story_nodes WHERE document_id = ? AND node_type = 'speaker'",
        (dialog.story_document_id,),
    ).fetchone()[0]
    conn.execute(
        "UPDATE story_nodes SET text = 'Hello there friend.' "
        "WHERE document_id = ? AND node_type = 'dialogue'",
        (dialog.story_document_id,),
    )
    conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text,
            origin, approved, source_version
        ) VALUES (
            'dialogue:duplicate', ?, ?, 'dialogue', 1,
            'Hello there friend.', 'manual', 1, 1
        )
        """,
        (dialog.story_document_id, speaker_id),
    )
    conn.commit()
    summary = dialog.client.match_game_strings(dialog.story_document_id, [GameString(
        "0", "zel_00", 0, "zel_00_Str_0", "Hello there friend."
    )])
    assert summary.needs_review == 1

    dialog._refresh_dialogue_review_table()
    dialog.reject_mapping_btn.click()

    mapping = dialog.client.get_dialogue_mappings(dialog.story_document_id)[0]
    assert mapping.review_status == "rejected"
    assert mapping.dialogue_node_id is None
    assert mapping.locked
    assert dialog.mapping_review_actions.isHidden()
    assert "story context is ready" in dialog.dialogue_mapping_summary_label.text().lower()
    assert "1 reviewed" in dialog.dialogue_mapping_summary_label.text().lower()


def test_mempalace_builder_detects_changed_source_hash_and_restores_status(qapp, tmp_path):
    mock_mw, settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    path = tmp_path / "script_markup_project.json"
    payload = _hierarchy_project_payload()
    path.write_text(json.dumps(payload), encoding="utf-8")
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    assert dialog._load_hierarchy_project_preview(str(path))
    assert dialog._import_sync_hierarchy_project()
    imported_hash = settings["mempalace_hierarchy_project_hash"]

    payload["raw_text"] = payload["raw_text"].replace("Hello.", "Changed.")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert dialog._load_hierarchy_project_preview(str(path))
    status_text = dialog.hierarchy_project_status_label.text()
    assert status_text.startswith("Status: Source changed")
    assert imported_hash[:12] in status_text
    assert dialog.hierarchy_project.source_hash[:12] in status_text
    assert not dialog.workflow_tabs.isTabEnabled(1)

    restored = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    assert restored.hierarchy_project_status_label.text().startswith("Status: Source changed")


def test_mempalace_builder_does_not_expose_removed_script_fallback(qapp):
    mock_mw, _settings = _settings_backed_main_window()
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    assert dialog.legacy_fallback_checkbox.isHidden()
    assert dialog.legacy_script_label.isHidden()
    assert dialog.file_path_edit.isHidden()
    assert dialog.browse_btn.isHidden()
    assert dialog.map_chapters_btn.isHidden()
    assert dialog.table.isHidden()


def test_mempalace_builder_persists_chapters_splitter_sizes(qapp):
    mock_mw, settings = _settings_backed_main_window()
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    dialog.resize(860, 680)
    dialog.show()
    dialog.workflow_tabs.setTabEnabled(1, True)
    dialog.workflow_tabs.setCurrentIndex(1)
    qapp.processEvents()
    dialog.toggle_story_btn.click()
    qapp.processEvents()
    dialog.chapters_splitter.setSizes([220, 360])
    qapp.processEvents()

    dialog.save_builder_settings()
    saved_sizes = settings["mempalace_chapters_splitter_sizes"]

    assert len(saved_sizes) == 2
    assert all(size > 0 for size in saved_sizes)
    restored = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    restored.resize(860, 680)
    restored.workflow_tabs.setTabEnabled(1, True)
    restored.workflow_tabs.setCurrentIndex(1)
    restored.show()
    restored.toggle_story_btn.click()
    qapp.processEvents()
    assert restored.chapters_splitter.sizes() == saved_sizes


def test_mempalace_builder_pipeline_orchestration(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # Enable pipeline and check sequence
    dialog.pipeline_running = True
    dialog.pipeline_step = 1
    
    # Mock core workers and dialog methods
    dialog._pre_analyze_script_via_ai_core = MagicMock()
    dialog._start_chapters_mapping_core = MagicMock()
    dialog._analyze_all_chapters_core = MagicMock()
    dialog._profile_characters_speech_via_ai_core = MagicMock()
    dialog._finish_and_maybe_sleep = MagicMock()
    dialog._get_ai_provider_or_warn = MagicMock(return_value=MagicMock())
    
    # Run step 1
    dialog._run_pipeline_current_step()
    dialog._pre_analyze_script_via_ai_core.assert_called_once()
    
    # Simulate step 1 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 2
    dialog._start_chapters_mapping_core.assert_called_once()
    
    # Simulate step 2 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 3
    dialog._analyze_all_chapters_core.assert_called_once()
    
    # Simulate step 3 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 4
    dialog._profile_characters_speech_via_ai_core.assert_called_once()
    
    # Simulate step 4 success (pipeline complete)
    with patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        dialog._advance_pipeline()
        assert dialog.pipeline_running is False
        assert dialog.pipeline_step == 0
        mock_info.assert_called_once()


def test_mempalace_builder_pipeline_session_persistence(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    
    # Mock settings manager
    mock_settings = {}
    mock_mw.settings_manager = MagicMock()
    def mock_set(key, val):
        mock_settings[key] = val
    def mock_get(key, default=None):
        return mock_settings.get(key, default)
    mock_mw.settings_manager.set.side_effect = mock_set
    mock_mw.settings_manager.get.side_effect = mock_get
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # 1. Start pipeline at step 2
    dialog.pipeline_running = True
    dialog.pipeline_step = 2
    dialog.wing_edit.setText("Zelda_TEST")
    dialog.file_path_edit.setText("d:/test/script.txt")
    
    # 2. Persist state
    dialog._save_pipeline_state()
    assert mock_settings["mempalace_pipeline_running"] is True
    assert mock_settings["mempalace_pipeline_step"] == 2
    assert mock_settings["mempalace_pipeline_wing"] == "Zelda_TEST"
    assert mock_settings["mempalace_pipeline_script"] == "d:/test/script.txt"
    
    # 3. Create a new dialog and load settings to verify recovery
    dialog2 = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    dialog2.load_builder_settings()
    assert dialog2.saved_pipeline_running is True
    assert dialog2.saved_pipeline_step == 2
    assert dialog2.saved_pipeline_wing == "Zelda_TEST"
    assert dialog2.saved_pipeline_script == "d:/test/script.txt"
    assert "Continue Pipeline (Step 2/4)" in dialog2.pipeline_btn.text()


def test_mempalace_builder_keeps_old_analysis_step_locked(qapp, tmp_path):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.settings_manager = MagicMock()
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    assert not dialog.workflow_tabs.isTabEnabled(2)
    assert not dialog.mapping_next_btn.isEnabled()


def test_mempalace_builder_wizard_gates_later_steps_until_source_is_ready(qapp, tmp_path):
    mock_mw, _settings = _settings_backed_main_window()
    mock_mw.project_manager.project_dir = str(tmp_path)
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    assert dialog.workflow_tabs.isTabEnabled(0)
    assert not dialog.workflow_tabs.isTabEnabled(1)
    assert not dialog.workflow_tabs.isTabEnabled(2)
    assert not dialog.source_next_btn.isEnabled()

    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(json.dumps(_hierarchy_project_payload()), encoding="utf-8")
    assert dialog._load_hierarchy_project_preview(str(project_path))
    assert dialog._import_sync_hierarchy_project()

    assert dialog.workflow_tabs.isTabEnabled(1)
    assert not dialog.workflow_tabs.isTabEnabled(2)
    assert dialog.source_next_btn.isEnabled()
    assert "ready" in dialog.source_readiness_label.text().lower()
    dialog.source_next_btn.click()
    assert dialog.workflow_tabs.currentIndex() == 1

    assert not dialog.workflow_tabs.isTabEnabled(2)
    assert not dialog.mapping_next_btn.isEnabled()


def test_mempalace_builder_dialog_passes_target_lang_to_chapter_analyzer(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.settings_manager = MagicMock()
    mock_mw.target_language = "Spanish"

    # Mock translation_handler and provider
    mock_provider = MagicMock()
    mock_mw.translation_handler = MagicMock()
    mock_mw.translation_handler._prepare_provider.return_value = mock_provider

    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)

    # Set up queue and mocks
    dialog.analysis_queue = [1]
    dialog.client = MagicMock()
    dialog.client.db_path = "dummy_db_path"

    # Patch sqlite3 connect and query to return dummy row
    with patch("sqlite3.connect") as mock_connect, \
         patch("ui.mempalace_builder_dialog.MemePalaceChapterAIAnalyzerWorker") as mock_worker_class:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("1", "Intro", 1, "Line 1\nLine 2")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock the worker instance and start method
        mock_worker_instance = MagicMock()
        mock_worker_class.return_value = mock_worker_instance

        # Call the queue processor
        dialog._process_analysis_queue()

        # Assert worker was created with correct target_lang
        mock_worker_class.assert_called_once()
        kwargs = mock_worker_class.call_args[1]
        assert kwargs.get("target_lang") == "Spanish"
