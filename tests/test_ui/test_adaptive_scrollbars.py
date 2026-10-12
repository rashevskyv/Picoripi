import gc

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QListWidget,
    QPlainTextEdit,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QVBoxLayout,
)

from ui.adaptive_scrollbars import AdaptiveScrollBar, install_adaptive_scrollbars


def test_install_adaptive_scrollbars_replaces_scroll_area_bars(qapp):
    edit = QPlainTextEdit()
    edit.setPlainText("\n".join(str(i) for i in range(100)))
    edit.show()

    install_adaptive_scrollbars(qapp)
    QApplication.processEvents()

    assert isinstance(edit.verticalScrollBar(), AdaptiveScrollBar)
    assert isinstance(edit.horizontalScrollBar(), AdaptiveScrollBar)


def test_adaptive_scrollbar_changes_thickness_without_losing_value(qapp):
    edit = QPlainTextEdit()
    edit.setPlainText("\n".join(str(i) for i in range(100)))
    edit.show()
    install_adaptive_scrollbars(qapp)
    QApplication.processEvents()

    bar = edit.verticalScrollBar()
    bar.setValue(12)
    viewport_width = edit.viewport().width()
    frame = bar.parentWidget()
    collapsed_geometry = frame.geometry()
    collapsed_right_edge = collapsed_geometry.x() + collapsed_geometry.width()

    bar._set_expanded(True, animated=False)
    QApplication.processEvents()
    assert bar.width() == AdaptiveScrollBar.EXPANDED_THICKNESS
    assert bar.width() >= 22
    assert edit.viewport().width() == viewport_width
    assert frame.geometry().x() < collapsed_geometry.x()
    assert frame.geometry().x() + frame.geometry().width() == collapsed_right_edge
    assert bar.value() == 12

    bar._set_expanded(False, animated=False)
    QApplication.processEvents()
    assert bar.width() == AdaptiveScrollBar.COLLAPSED_THICKNESS
    assert edit.viewport().width() == viewport_width
    assert frame.geometry().x() + frame.geometry().width() == collapsed_right_edge
    assert bar.value() == 12


def test_vertical_scrollbars_are_adaptive_across_common_scroll_widgets(qapp):
    container = QWidget()
    layout = QVBoxLayout(container)

    plain = QPlainTextEdit()
    plain.setPlainText("\n".join(str(i) for i in range(80)))
    layout.addWidget(plain)

    rich = QTextEdit()
    rich.setPlainText("\n".join(str(i) for i in range(80)))
    layout.addWidget(rich)

    list_widget = QListWidget()
    list_widget.addItems([f"Item {i}" for i in range(80)])
    layout.addWidget(list_widget)

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    for i in range(80):
        tree.addTopLevelItem(QTreeWidgetItem([f"Node {i}"]))
    layout.addWidget(tree)

    container.show()
    install_adaptive_scrollbars(qapp)
    QApplication.processEvents()

    for widget in (plain, rich, list_widget, tree):
        assert isinstance(widget.verticalScrollBar(), AdaptiveScrollBar)
        assert widget.verticalScrollBar().width() == AdaptiveScrollBar.COLLAPSED_THICKNESS


def test_scroll_widget_created_after_install_gets_adaptive_vertical_bar(qapp):
    install_adaptive_scrollbars(qapp)

    edit = QTextEdit()
    edit.setPlainText("\n".join(str(i) for i in range(100)))
    edit.show()
    QApplication.processEvents()

    assert isinstance(edit.verticalScrollBar(), AdaptiveScrollBar)


def test_bar_on_a_qt_created_scroll_area_survives_the_cycle_collector(qapp):
    # A combo box popup is a list view Qt creates itself: Python only ever holds temporary wrappers of it.
    combo = QComboBox()
    combo.addItems([str(i) for i in range(50)])
    install_adaptive_scrollbars(qapp)
    combo.show()
    QApplication.processEvents()
    gc.collect()

    # A freed wrapper comes back as a fresh plain QScrollBar over the live AdaptiveScrollBar.
    bar = combo.view().verticalScrollBar()
    assert isinstance(bar, AdaptiveScrollBar)
    assert bar.thickness == AdaptiveScrollBar.COLLAPSED_THICKNESS
