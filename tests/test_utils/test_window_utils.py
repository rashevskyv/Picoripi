from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget

from utils.window_utils import show_as_independent_window


def test_owned_dialog_becomes_a_top_level_window(qapp):
    owner = QWidget()
    dialog = QDialog(owner)
    assert dialog.parent() is owner

    show_as_independent_window(dialog)

    assert dialog.parent() is None
    assert dialog.windowFlags() & Qt.WindowType.Window
    assert not dialog.isModal()
    assert not dialog.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)
    dialog.deleteLater()
    owner.deleteLater()
