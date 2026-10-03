"""REVIEW_QUEUE WP6: the dialogs the mixins open (6.4).

Real MainWindow in interactive mode; message boxes are answered by clicking their buttons (BoxAnswerer).
"""
import importlib
import pathlib
import pkgutil

from test_review._rq_wp1_6_helpers import open_project
from test_review.test_rq_wp1_6_ui_lifecycle import _select_string, interactive, project  # noqa: F401


# ------------------------------------------------------- real names in the mixins

def _genuine():
    from PyQt6.QtCore import QPoint, QTimer
    from PyQt6.QtGui import QAction, QTextCursor
    from PyQt6.QtWidgets import QDialog, QMessageBox, QProgressDialog, QTreeWidgetItemIterator

    return {
        "QMessageBox": QMessageBox, "Path": pathlib.Path, "QTextCursor": QTextCursor,
        "QTreeWidgetItemIterator": QTreeWidgetItemIterator, "QProgressDialog": QProgressDialog,
        "QAction": QAction, "QDialog": QDialog, "QTimer": QTimer, "QPoint": QPoint,
    }


def test_every_module_uses_the_real_qt_and_path_classes():
    """No module global named like a Qt class or Path is a stand-in (the removed _ShimName proxies)."""
    genuine = _genuine()
    wrong = []
    for package_name in ("handlers", "core", "components", "ui", "dialogs"):
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, package_name + "."):
            try:
                module = importlib.import_module(info.name)
            except Exception:
                continue
            for name, real in genuine.items():
                value = module.__dict__.get(name)
                if value is not None and value is not real:
                    wrong.append(f"{info.name}.{name} = {value!r}")
    assert wrong == []


# ------------------------------------------------------------ project dialogs

# ------------------------------------------------------------------ paste block

def test_paste_block_fills_the_rows_from_the_clipboard(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    from PyQt6.QtWidgets import QApplication

    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["one", "two", "three"]}), monkeypatch, qtbot)
    _select_string(mw, qtbot, 0, 0)
    QApplication.clipboard().setText("один{END}\nдва{END}\n")

    mw.paste_block_action.trigger()

    rows = [mw.data_processor.get_current_string_text(0, i)[0] for i in range(3)]
    assert rows == ["один", "два", "three"]
    assert mw.undo_manager.current_group is None
    assert mw.can_undo_paste is True


def test_paste_with_an_empty_clipboard_leaves_undo_working(interactive, qtbot, tmp_path, monkeypatch):  # noqa: F811
    from PyQt6.QtWidgets import QApplication

    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["one", "two"]}), monkeypatch, qtbot)
    _select_string(mw, qtbot, 0, 0)
    QApplication.clipboard().clear()

    mw.paste_block_action.trigger()

    assert interactive.boxes.seen[-1]["text"] == "Clipboard empty."
    assert mw.undo_manager.current_group is None
