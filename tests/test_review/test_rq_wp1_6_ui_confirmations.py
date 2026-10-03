"""REVIEW_QUEUE WP6 6.4: the confirmations the mixins open, answered the way a person would.

Real MainWindow in interactive mode; message boxes and dialogs are answered by clicking (BoxAnswerer).
No keeps everything as it was, Yes / Save does the work.
"""
from test_review._rq_wp1_6_helpers import open_project
from test_review.test_rq_wp1_6_ui_lifecycle import _select_string, interactive, project  # noqa: F401


def _answer(make, label):
    make.boxes.policy = lambda box: label


def _boxes_titled(make, title):
    return [box for box in make.boxes.seen if box["title"] == title]


# ---------------------------------------------------------------- delete block

def test_delete_block_asks_first_and_keeps_the_file(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    mw = interactive()
    project_file = project(tmp_path, {"a": ["one"], "b": ["two"]})
    open_project(mw, project_file, monkeypatch, qtbot)
    pm = mw.project_manager
    _select_string(mw, qtbot, 0, 0)

    _answer(interactive, "No")
    mw.project_action_handler.delete_block_action()
    assert [b.name for b in pm.project.blocks] == ["a", "b"]

    _answer(interactive, "Yes")
    _select_string(mw, qtbot, 0, 0)
    mw.project_action_handler.delete_block_action()
    qtbot.waitUntil(lambda: [b.name for b in pm.project.blocks] == ["b"], timeout=5000)

    asked = _boxes_titled(interactive, "Delete Block")
    assert len(asked) == 2 and "remove block 'a' from the project" in asked[0]["text"]
    assert (tmp_path / "source" / "a.txt").exists()          # only the reference goes


def test_delete_block_survives_a_tree_rebuild_while_it_asks(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    """Chapters arriving rebuild the tree while the question is open; the clicked item is gone by the answer."""
    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["one"], "b": ["two"]}), monkeypatch, qtbot)
    _select_string(mw, qtbot, 0, 0)

    def rebuild_then_yes(box):
        mw.ui_updater.populate_blocks()
        return "Yes"

    interactive.boxes.policy = rebuild_then_yes
    mw.project_action_handler.delete_block_action()

    qtbot.waitUntil(lambda: [b.name for b in mw.project_manager.project.blocks] == ["b"], timeout=5000)


# ------------------------------------------------------------ glossary window

def _glossary_window(mw, qtbot, tmp_path, monkeypatch):
    open_project(mw, project(tmp_path, {"a": ["Hello there", "World"]}), monkeypatch, qtbot)
    manager = mw.translation_handler.glossary_handler.glossary_manager
    manager.add_entry("Hello", "Привіт", "")
    manager.add_entry("World", "Світ", "")
    handler = mw.translation_handler.glossary_handler
    handler.show_glossary_dialog()
    qtbot.waitUntil(lambda: handler.dialog is not None and handler.dialog.isVisible(), timeout=10000)
    return handler.dialog, manager


def test_deleting_a_glossary_entry_asks_first(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    mw = interactive()
    dialog, manager = _glossary_window(mw, qtbot, tmp_path, monkeypatch)
    hello = next(e for e in dialog._all_entries if e.original == "Hello")

    _answer(interactive, "No")
    dialog._attempt_entry_delete(hello)
    assert manager.get_entry("Hello") is not None

    _answer(interactive, "Yes")
    dialog._attempt_entry_delete(hello)
    assert manager.get_entry("Hello") is None
    assert [e.original for e in dialog._all_entries] == ["World"]
    assert len(_boxes_titled(interactive, "Delete Glossary Entry")) == 2


def test_moving_off_an_edited_glossary_entry_offers_to_save_it(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    mw = interactive()
    dialog, manager = _glossary_window(mw, qtbot, tmp_path, monkeypatch)
    dialog._select_initial_term("Hello")
    qtbot.waitUntil(lambda: dialog._current_entry is not None and dialog._current_entry.original == "Hello", timeout=5000)

    dialog._translation_edit.setText("Вітаю")
    _answer(interactive, "Save")
    dialog._select_initial_term("World")

    qtbot.waitUntil(lambda: manager.get_entry("Hello").translation == "Вітаю", timeout=5000)
    assert _boxes_titled(interactive, "Unsaved Changes")[0]["text"] == "Save changes to 'Hello'?"


# --------------------------------------------------------------------- autofix

def test_autofix_all_does_nothing_when_its_selection_is_cancelled_or_empty(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["one  two", "three"]}), monkeypatch, qtbot)
    before = dict(mw.data_store.edited_data)
    handler = mw.editor_operation_handler

    interactive.boxes.dialogs["AutofixSelectionDialog"] = lambda dialog: dialog.reject()
    handler.fix_all_strings()
    assert mw.data_store.edited_data == before

    def nothing_ticked(dialog):
        for box in dialog.checkboxes.values():
            box.setChecked(False)
        dialog.accept()

    interactive.boxes.dialogs["AutofixSelectionDialog"] = nothing_ticked
    handler.fix_all_strings()
    qtbot.waitUntil(lambda: bool(_boxes_titled(interactive, "Auto-fix")), timeout=5000)

    assert _boxes_titled(interactive, "Auto-fix")[0]["text"] == "No problems selected to fix."
    assert mw.data_store.edited_data == before
