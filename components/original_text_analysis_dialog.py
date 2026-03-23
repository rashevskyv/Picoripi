# --- START OF FILE components/original_text_analysis_dialog.py ---
# -*- coding: utf-8 -*-
"""Interactive dialog for analysing original text width."""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence

from PyQt5.QtCore import QPoint, Qt, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollBar,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.utils import calculate_string_width, DEFAULT_CHAR_WIDTH_FALLBACK

BASE_BAR_COLOR = QColor(66, 135, 245, 220)
HIGHLIGHT_BAR_COLOR = QColor(244, 160, 0, 230)


class _BarItem(QGraphicsRectItem):
    """Bar item storing its index for selection syncing."""

    def __init__(self, index: int, *rect_args):
        super().__init__(*rect_args)
        self.index = index


class _AnalysisBarView(QGraphicsView):
    """Specialised bar chart view with zoom/pan and selection callback."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._panning = False
        self._pan_start = QPoint()
        self._bars: List[_BarItem] = []
        self._user_scaled = False
        self.on_bar_selected: Optional[Callable[[int], None]] = None

    def wheelEvent(self, event) -> None:  # noqa: D401 (inherit doc)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._user_scaled = True
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self._user_scaled = True
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: D401
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self._scroll(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton and not self._panning:
            scene_pos = self.mapToScene(event.pos())
            item = self._scene.itemAt(scene_pos, self.transform())
            if isinstance(item, _BarItem) and self.on_bar_selected:
                self.on_bar_selected(item.index)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _scroll(self, delta) -> None:
        h_bar: QScrollBar = self.horizontalScrollBar()
        v_bar: QScrollBar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() - delta.x())
        v_bar.setValue(v_bar.value() - delta.y())

    def resizeEvent(self, event) -> None:  # noqa: D401
        super().resizeEvent(event)
        if not self._user_scaled:
            self._fit_view_to_scene()

    def set_entries(self, entries: Sequence[dict]) -> None:
        """Populate the scene with bar items."""
        self.resetTransform()
        self._user_scaled = False
        self._scene.clear()
        self._bars = []
        if not entries:
            self._scene.setSceneRect(0, 0, 1, 1)
            self._fit_view_to_scene()
            return

        bar_width = 24.0
        spacing = 12.0
        max_height = max(entry['width_pixels'] for entry in entries) or 1.0
        total_width = len(entries) * bar_width + (len(entries) - 1) * spacing

        axis_pen = QPen(QColor(140, 140, 140))
        axis_pen.setWidthF(0.8)
        self._scene.addLine(0.0, 0.0, total_width, 0.0, axis_pen)

        ticks = 5
        for idx in range(1, ticks + 1):
            value = max_height * idx / ticks
            y = -value
            tick_pen = QPen(QColor(200, 200, 200))
            tick_pen.setStyle(Qt.DashLine)
            tick_pen.setWidthF(0.6)
            self._scene.addLine(0.0, y, total_width, y, tick_pen)
            label = QGraphicsSimpleTextItem(f"{value:.1f} px")
            label.setBrush(QColor(90, 90, 90))
            label.setPos(-70.0, y - 10.0)
            self._scene.addItem(label)

        for idx, entry in enumerate(entries):
            bar_height = float(entry['width_pixels'])
            x = idx * (bar_width + spacing)
            rect = _BarItem(idx, x, -bar_height, bar_width, bar_height)
            rect.setBrush(BASE_BAR_COLOR)
            rect.setPen(QPen(Qt.NoPen))
            tooltip_lines: List[str] = [f"#{idx + 1}: {bar_height:.1f} px"]
            if entry.get('block_idx') is not None:
                tooltip_lines.append(
                    (
                        f"Block {entry['block_idx']}, string {entry['string_idx']}, "
                        f"line {entry['line_idx']}"
                    )
                )
            snippet = entry.get('text', '')
            if snippet:
                tooltip_lines.append(snippet)
            rect.setToolTip('\n'.join(tooltip_lines))
            self._scene.addItem(rect)
            self._bars.append(rect)

        padding = max_height * 0.1
        self._scene.setSceneRect(
            -bar_width,
            -(max_height + padding),
            total_width + bar_width * 2,
            max_height + padding * 2,
        )
        self._fit_view_to_scene()

    def highlight_bar(self, index: int) -> None:
        if not self._bars:
            return
        index = max(0, min(index, len(self._bars) - 1))
        for i, bar in enumerate(self._bars):
            bar.setBrush(HIGHLIGHT_BAR_COLOR if i == index else BASE_BAR_COLOR)
        self.centerOn(self._bars[index])

    def _fit_view_to_scene(self) -> None:
        if self._scene is None:
            return
        rect = self._scene.itemsBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = self._scene.sceneRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = QRectF(rect.x(), rect.y(), 1.0, 1.0)
        margin = max(rect.width(), rect.height()) * 0.05
        if margin > 0:
            rect = QRectF(
                rect.x() - margin,
                rect.y() - margin,
                rect.width() + margin * 2,
                rect.height() + margin * 2,
            )
        self.fitInView(rect, Qt.KeepAspectRatio)


class OriginalTextAnalysisDialog(QDialog):
    """Dialog displaying the top 100 wide strings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Original Text Width Analysis")
        self.resize(1100, 750)

        layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Font map:"))
        self._font_combo = QComboBox(self)
        self._font_combo.setMinimumWidth(200)
        selector_layout.addWidget(self._font_combo)
        selector_layout.addStretch(1)
        layout.addLayout(selector_layout)

        # Use stacks for instant switching
        self._chart_stack = QStackedWidget(self)
        layout.addWidget(self._chart_stack)

        self._summary_label = QLabel("Ready")
        self._summary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._summary_label)

        self._table_stack = QStackedWidget(self)
        self._table_stack.setMinimumHeight(250)
        layout.addWidget(self._table_stack)

        # Resource management: {font_name: {"chart": view, "table": table}}
        self._font_views: Dict[str, Dict[str, Any]] = {}

        self._hint_label = QLabel(
            "Scroll: zoom, Middle: pan; Hover for details. Click on bar/row to sync."
        )
        self._hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint_label)

        self._font_combo.currentTextChanged.connect(self._on_font_changed)

        self._entries: List[dict] = []
        self._raw_entries: List[dict] = []
        self._font_maps: dict = {}
        self._current_font_name: Optional[str] = None
        self.on_entry_activated: Optional[Callable[[dict], None]] = None
        self._default_char_width = DEFAULT_CHAR_WIDTH_FALLBACK
        self._max_entries = 100
        self._entries_cache: Dict[str, List[dict]] = {}
        self._custom_title: Optional[str] = None

    def set_custom_title(self, title: str) -> None:
        self._custom_title = title
        self.setWindowTitle(title)

    def show_entries(
        self,
        raw_entries: Iterable[dict],
        font_maps: dict,
        initial_font: Optional[str],
        precomputed_entries: Optional[Sequence[dict]] = None,
        title: Optional[str] = None,
        all_fonts_top_entries: Optional[Dict[str, List[dict]]] = None
    ) -> None:
        if title:
            self.set_custom_title(title)
        elif not self._custom_title:
            self.setWindowTitle("Original Text Width Analysis")
            
        self._raw_entries = [dict(entry) for entry in raw_entries]
        self._font_maps = font_maps or {}
        self._entries_cache.clear()

        # Clear existing stacked views
        self._font_views.clear()
        while self._chart_stack.count():
            w = self._chart_stack.widget(0)
            self._chart_stack.removeWidget(w)
            w.deleteLater()
        while self._table_stack.count():
            w = self._table_stack.widget(0)
            self._table_stack.removeWidget(w)
            w.deleteLater()

        # CASE 1: Worker provided pre-sorted top entries for EACH font (OPTIMIZED)
        if all_fonts_top_entries:
            for f_name, sorted_top_list in all_fonts_top_entries.items():
                self._entries_cache[f_name] = [dict(e) for e in sorted_top_list]
                # Ensure width_pixels is correctly set for the specific font in cache
                for e in self._entries_cache[f_name]:
                    if 'widths' in e and f_name in e['widths']:
                         e['width_pixels'] = float(e['widths'][f_name])

        # CASE 2: Legacy fallback
        if precomputed_entries:
            has_multi_font = any('widths' in (e or {}) for e in precomputed_entries)
            if has_multi_font:
                for font_name in self._font_maps.keys():
                    if font_name in self._entries_cache: continue
                    cached: List[dict] = []
                    for entry in precomputed_entries:
                        new_entry = dict(entry)
                        if 'widths' in new_entry and font_name in new_entry['widths']:
                            new_entry['width_pixels'] = float(new_entry['widths'][font_name])
                        cached.append(new_entry)
                    cached.sort(key=lambda item: item.get('width_pixels', 0.0), reverse=True)
                    self._entries_cache[font_name] = cached[: self._max_entries]
            elif initial_font and initial_font not in self._entries_cache:
                cached: List[dict] = []
                for entry in precomputed_entries:
                    new_entry = dict(entry)
                    new_entry['width_pixels'] = float(new_entry.get('width_pixels', 0.0) or 0.0)
                    cached.append(new_entry)
                cached.sort(key=lambda item: item.get('width_pixels', 0.0), reverse=True)
                self._entries_cache[initial_font] = cached[: self._max_entries]

        self._font_combo.blockSignals(True)
        self._font_combo.clear()
        for font_name in sorted(self._font_maps.keys()):
            self._font_combo.addItem(font_name)
        if self._font_combo.count() == 0:
            self._font_combo.addItem("No font maps")
            self._font_combo.setEnabled(False)
        else:
            self._font_combo.setEnabled(True)
        self._font_combo.blockSignals(False)

        if not self._raw_entries:
            self._summary_label.setText("No data")
            self.show(); self.raise_(); self.activateWindow()
            return

        target_font = initial_font if initial_font in self._font_maps else None
        if target_font is None and self._font_combo.count() > 0:
            target_font = self._font_combo.itemText(0)

        if target_font:
            index = self._font_combo.findText(target_font)
            if index >= 0:
                self._font_combo.setCurrentIndex(index)
            self._apply_font(target_font)
        else:
            self._summary_label.setText("No font selected")
            self.show(); self.raise_(); self.activateWindow()

    def _apply_font(self, font_name: str) -> None:
        self._current_font_name = font_name
        
        # If already rendered for this font, just switch
        if font_name in self._font_views:
            views = self._font_views[font_name]
            self._chart_stack.setCurrentWidget(views['chart'])
            self._table_stack.setCurrentWidget(views['table'])
            self._update_summary(self._entries_cache.get(font_name, []))
            self.show(); self.raise_(); self.activateWindow()
            return

        # Prepare entries
        cached_entries = self._entries_cache.get(font_name)
        if cached_entries is None:
            # Recalculate if not in worker result
            font_map = self._font_maps.get(font_name, {})
            computed: List[dict] = []
            for entry in self._raw_entries:
                text = entry.get('text', '') or ''
                width = calculate_string_width(text, font_map, self._default_char_width)
                new_entry = dict(entry)
                new_entry['width_pixels'] = float(width)
                computed.append(new_entry)
            computed.sort(key=lambda item: item.get('width_pixels', 0.0), reverse=True)
            cached_entries = computed[: self._max_entries]
            self._entries_cache[font_name] = cached_entries

        # Create new widgets for this font
        chart_view = _AnalysisBarView(self)
        table = QTableWidget(self)
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["#", "Width (px)", "Block", "String", "Line", "Text"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        h = table.horizontalHeader()
        for i in range(5): h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.Stretch)

        # Connect signals
        chart_view.on_bar_selected = lambda idx, t=table, cv=chart_view: self._handle_bar_selected_for_table(idx, t, cv)
        table.itemSelectionChanged.connect(lambda t=table, cv=chart_view: self._handle_table_selection_for_chart(t, cv))
        table.itemDoubleClicked.connect(lambda item, entries=cached_entries: self._handle_table_double_click_ext(item, entries))

        # Render data
        chart_view.set_entries(cached_entries)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(cached_entries))
        for row, entry in enumerate(cached_entries):
            vals = [str(row+1), f"{entry['width_pixels']:.1f}", str(entry.get('block_idx','-')), 
                    str(entry.get('string_idx','-')), str(entry.get('line_idx','-')), entry.get('text','')]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col == 1: item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row, col, item)
        table.setUpdatesEnabled(True)

        # Add to stacks
        self._chart_stack.addWidget(chart_view)
        self._table_stack.addWidget(table)
        self._font_views[font_name] = {'chart': chart_view, 'table': table}

        # Switch to new widgets
        self._chart_stack.setCurrentWidget(chart_view)
        self._table_stack.setCurrentWidget(table)
        self._update_summary(cached_entries)
        
        self.show(); self.raise_(); self.activateWindow()

    def _update_summary(self, entries: List[dict]) -> None:
        if not entries:
            self._summary_label.setText("No entries")
            return
        top = entries[0]
        self._summary_label.setText(
            f"Max: {top['width_pixels']:.1f} px | B:{top.get('block_idx','-')} S:{top.get('string_idx','-')} L:{top.get('line_idx','-')} | Font: {self._current_font_name}"
        )

    def _handle_bar_selected_for_table(self, index: int, table: QTableWidget, chart_view: _AnalysisBarView) -> None:
        table.blockSignals(True)
        table.selectRow(index)
        table.blockSignals(False)
        chart_view.highlight_bar(index)
        item = table.item(index, 0)
        if item: table.scrollToItem(item)

    def _handle_table_selection_for_chart(self, table: QTableWidget, chart_view: _AnalysisBarView) -> None:
        rows = table.selectionModel().selectedRows()
        if rows: chart_view.highlight_bar(rows[0].row())

    def _handle_table_double_click_ext(self, item, entries: List[dict]) -> None:
        row = item.row()
        if 0 <= row < len(entries) and self.on_entry_activated:
            self.on_entry_activated(entries[row])
        self.accept()

    def _on_font_changed(self, font_name: str) -> None:
        if font_name and font_name in self._font_maps:
            self._apply_font(font_name)
