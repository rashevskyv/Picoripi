from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QMessageBox
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from components.chapter_picker import ChapterSelectionDialog, HierarchicalChapterComboBox
from core.mempalace.story_timeline import StoryVirtualFolder, StoryVirtualProjection


def _projection():
    scene = StoryVirtualFolder(3, "scene", "Scene One", (), ())
    chapter = StoryVirtualFolder(2, "chapter", "Chapter One", (scene,), ())
    act = StoryVirtualFolder(1, "act", "Act One", (chapter,), ())
    return StoryVirtualProjection(7, (act,), ())


def test_chapter_dialog_preserves_story_hierarchy(qapp):
    dialog = ChapterSelectionDialog(_projection(), selected_id=3)

    act = dialog.tree.topLevelItem(1)
    chapter = act.child(0)
    scene = chapter.child(0)

    assert act.text(0) == "Act One"
    assert chapter.text(0) == "Chapter One"
    assert scene.text(0) == "Scene One"
    assert dialog.tree.currentItem() is scene
    assert dialog.selection() == (3, ("Act One", "Chapter One", "Scene One"))


def test_chapter_dialog_search_keeps_matching_ancestors(qapp):
    dialog = ChapterSelectionDialog(_projection())
    dialog.search_edit.setText("scene one")

    act = dialog.tree.topLevelItem(1)
    assert not act.isHidden()
    assert not act.child(0).isHidden()
    assert not act.child(0).child(0).isHidden()
    assert dialog.none_item.isHidden()
    assert dialog.tree.currentItem().text(0) == "Scene One"


def test_compact_picker_holds_only_current_selection(qapp):
    picker = HierarchicalChapterComboBox()
    picker.set_story_projection(_projection())
    picker.set_story_selection(3, ("Act One", "Chapter One", "Scene One"))

    assert picker.count() == 1
    assert picker.currentData() == 3
    assert picker.current_story_path() == ("Act One", "Chapter One", "Scene One")
    assert picker.currentText() == "Act One › Chapter One › Scene One"


def test_chapter_dialog_adds_root_chapter_to_project(qapp):
    window = QMainWindow()
    project = MagicMock()
    project.metadata = {}
    project.blocks = []
    window.project_manager = MagicMock(project=project)
    window.ui_updater = MagicMock()
    dialog = ChapterSelectionDialog(_projection(), parent=window)
    dialog.tree.setCurrentItem(dialog.none_item)

    with patch(
        "components.chapter_picker.QInputDialog.getText",
        return_value=("Fishing", True),
    ):
        dialog.add_chapter_button.click()

    node_id, path = dialog.selection()
    assert str(node_id).startswith("manual:")
    assert path == ("Fishing",)
    assert project.metadata["manual_story_structures"]["nodes"][0]["node_type"] == "chapter"
    assert project.metadata["manual_story_structures"]["nodes"][0]["parent_id"] is None
    window.project_manager.save.assert_called_once()


def test_chapter_dialog_adds_nested_chapter_and_renames_parent(qapp):
    window = QMainWindow()
    project = MagicMock()
    project.metadata = {}
    project.blocks = []
    window.project_manager = MagicMock(project=project)
    window.ui_updater = MagicMock()
    dialog = ChapterSelectionDialog(_projection(), parent=window)
    act = dialog.tree.topLevelItem(1)
    dialog.tree.setCurrentItem(act)

    with patch(
        "components.chapter_picker.QInputDialog.getText",
        return_value=("Fishing", True),
    ):
        dialog.add_chapter_button.click()

    child = dialog.tree.currentItem()
    assert dialog.selection()[1] == ("Act One", "Fishing")
    node = project.metadata["manual_story_structures"]["nodes"][0]
    assert node["parent_id"] == 1

    dialog.tree.setCurrentItem(act)
    with patch(
        "components.chapter_picker.QInputDialog.getText",
        return_value=("Opening Act", True),
    ):
        dialog.rename_button.click()

    assert act.text(0) == "Opening Act"
    assert tuple(child.data(0, dialog.PATH_ROLE)) == ("Opening Act", "Fishing")


def test_manual_story_structure_is_merged_into_projection():
    from core.manual_story_structures import (
        add_manual_story_node,
        apply_manual_story_structures,
        rename_story_node,
    )

    project = MagicMock()
    project.metadata = {}
    project.blocks = []
    node_id = add_manual_story_node(project, "Fishing", "chapter", parent_id=1)
    rename_story_node(project, 1, "Opening Act")

    merged = apply_manual_story_structures(_projection(), project)

    assert merged.roots[0].title == "Opening Act"
    manual = next(child for child in merged.roots[0].children if child.id == node_id)
    assert manual.title == "Fishing"
    assert manual.node_type == "chapter"


def test_chapter_dialog_persists_dragged_hierarchy_and_assigned_paths(qapp):
    from core.manual_story_structures import apply_manual_story_structures

    window = QMainWindow()
    assignment = {
        "structure_id": 3,
        "structure_path": ["Act One", "Chapter One", "Scene One"],
    }
    project = SimpleNamespace(
        metadata={},
        blocks=[SimpleNamespace(metadata={
            "story_context_assignments": {"0": assignment}
        })],
    )
    window.project_manager = MagicMock(project=project)
    window.ui_updater = MagicMock()
    dialog = ChapterSelectionDialog(_projection(), parent=window)
    act = dialog.tree.topLevelItem(1)
    chapter = act.child(0)
    scene = chapter.takeChild(0)
    old_path = tuple(scene.data(0, dialog.PATH_ROLE))
    act.insertChild(0, scene)

    dialog._persist_tree_move(scene, old_path)

    assert tuple(scene.data(0, dialog.PATH_ROLE)) == ("Act One", "Scene One")
    assert assignment["structure_path"] == ["Act One", "Scene One"]
    merged = apply_manual_story_structures(_projection(), project)
    assert [child.id for child in merged.roots[0].children] == [3, 2]
    window.project_manager.save.assert_called_once_with()


def test_chapter_dialog_removes_subtree_and_clears_assignments(qapp):
    from core.manual_story_structures import apply_manual_story_structures

    window = QMainWindow()
    assignment = {
        "structure_id": 3,
        "structure_path": ["Act One", "Chapter One", "Scene One"],
    }
    project = SimpleNamespace(
        metadata={},
        blocks=[SimpleNamespace(metadata={
            "story_context_assignments": {"0": assignment}
        })],
    )
    window.project_manager = MagicMock(project=project)
    window.ui_updater = MagicMock()
    dialog = ChapterSelectionDialog(_projection(), parent=window)
    act = dialog.tree.topLevelItem(1)
    chapter = act.child(0)
    dialog.tree.setCurrentItem(chapter)

    with patch(
        "components.chapter_picker.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        dialog.remove_button.click()

    assert act.childCount() == 0
    assert assignment == {"structure_id": "story:none", "structure_path": []}
    merged = apply_manual_story_structures(_projection(), project)
    assert merged.roots[0].children == ()
    window.project_manager.save.assert_called_once_with()
