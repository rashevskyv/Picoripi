from PyQt6.QtCore import Qt

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
