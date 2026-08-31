"""Tool windows that the OS treats as their own, not as owned dialogs."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget


def show_as_independent_window(widget: QWidget) -> None:
    """Put a tool on Alt-Tab and the taskbar as its own window.

    A ``QDialog`` parented to the main window is an owned Windows dialog: it
    has no Alt-Tab entry of its own, and focusing the main window can bury it
    with no way back except clicking through the owner.
    """
    if widget.parent() is not None:
        widget.setParent(None)
    widget.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    if isinstance(widget, QDialog):
        widget.setModal(False)
    widget.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
