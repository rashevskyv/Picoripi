"""Mouse-wheel scrolling stays small across glossary panes."""
from PyQt6.QtCore import QPoint, QPointF, QSize, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QListWidgetItem

from components.glossary_dialog import GlossaryDialog
from core.glossary_manager import GlossaryEntry, TranslationVariant


def _dialog(qtbot):
    entries = [
        GlossaryEntry(
            original=f"Term {index}",
            translation=f"Translation {index}",
            section="Terms",
            translation_variants=(
                TranslationVariant(f"Translation {index}", "First rationale"),
                TranslationVariant(f"Alternative {index}", "Second rationale"),
            ),
        )
        for index in range(20)
    ]
    dialog = GlossaryDialog(
        parent=None,
        entries=entries,
        occurrence_map={},
        jump_callback=lambda _occurrence: None,
    )
    qtbot.addWidget(dialog)
    dialog.resize(840, 520)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def _wheel(view, delta):
    viewport = view.viewport()
    local = QPointF(viewport.rect().center())
    event = QWheelEvent(
        local,
        QPointF(viewport.mapToGlobal(local.toPoint())),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(viewport, event)


def _fill_list(view, heights):
    view.clear()
    for index, height in enumerate(heights):
        item = QListWidgetItem(f"Card {index}")
        item.setSizeHint(QSize(220, height))
        view.addItem(item)


def _fill_occurrences(view, line_counts):
    view.clear()
    for index, line_count in enumerate(line_counts):
        item = QListWidgetItem()
        item.setData(
            Qt.ItemDataRole.DisplayRole,
            f"Card {index}<br>" + "detail<br>" * line_count,
        )
        view.addItem(item)


def test_occurrence_list_wheel_moves_by_small_pixels_with_unequal_cards(qtbot):
    dialog = _dialog(qtbot)
    view = dialog._occurrence_list
    view.setFixedSize(260, 110)
    _fill_occurrences(view, [12, 2, 8, 4, 14])
    dialog.resize(850, 530)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    assert view.verticalScrollBar().singleStep() == 20
    assert view.visualItemRect(view.item(0)).height() >= 210

    view.verticalScrollBar().setValue(0)
    _wheel(view, -120)
    after_down = view.verticalScrollBar().value()
    tall_card = view.visualItemRect(view.item(0))
    assert tall_card.top() < view.viewport().height()
    assert tall_card.bottom() >= 0
    assert 0 < after_down <= 80

    _wheel(view, 120)
    assert view.verticalScrollBar().value() < after_down

    _fill_occurrences(view, [30])
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    view.verticalScrollBar().setValue(0)
    _wheel(view, -120)
    assert 0 < view.verticalScrollBar().value() <= 80


def test_variant_list_scroll_setting_survives_refill_and_resize(qtbot):
    dialog = _dialog(qtbot)
    view = dialog._variants_list
    view.setFixedSize(260, 100)
    _fill_list(view, [360])
    dialog.resize(900, 550)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    assert view.verticalScrollBar().singleStep() == 20

    _wheel(view, -120)
    assert 0 < view.verticalScrollBar().value() <= 80

    _fill_list(view, [130, 260, 90, 180])
    dialog.resize(860, 540)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    view.verticalScrollBar().setValue(0)
    assert view.verticalScrollBar().singleStep() == 20
    _wheel(view, -120)
    assert 0 < view.verticalScrollBar().value() <= 80


def test_term_table_uses_pixel_wheel_scrolling(qtbot):
    dialog = _dialog(qtbot)
    view = dialog._active_table()
    view.setFixedSize(260, 110)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    assert view.verticalScrollBar().singleStep() == 20

    _wheel(view, -120)
    assert 0 < view.verticalScrollBar().value() <= 80
