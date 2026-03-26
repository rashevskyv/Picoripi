# components/custom_tree_widget.py
"""Project file-tree widget — thin orchestrator that composes all behaviour mixins."""
from PyQt5.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView, QApplication, QToolTip,
    QTreeWidgetItemIterator,
)
from PyQt5.QtCore import Qt, QPoint, QEvent, QTimer
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter

from utils.logging_utils import log_debug, log_error

from .tree_navigation_mixin import TreeNavigationMixin
from .tree_context_menu_mixin import TreeContextMenuMixin
from .tree_folder_mixin import TreeFolderMixin
from .tree_drag_drop_mixin import TreeDragDropMixin
from .tree_spellcheck_mixin import TreeSpellcheckMixin


class CustomTreeWidget(
    TreeDragDropMixin,
    TreeContextMenuMixin,
    TreeFolderMixin,
    TreeNavigationMixin,
    TreeSpellcheckMixin,
    QTreeWidget,
):
    """QTreeWidget subclass for the project block tree.

    All substantial behaviour is delegated to focused mixin classes:
      - TreeDragDropMixin      — drag-and-drop
      - TreeContextMenuMixin   — right-click context menu
      - TreeFolderMixin        — virtual folder CRUD + PM sync + expansion state
      - TreeNavigationMixin    — keyboard navigation + move-up/move-down
      - TreeSpellcheckMixin    — spellcheck dialog + Reveal-in-Explorer
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Basic widget setup ────────────────────────────────────────────────
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.viewport().setMouseTracking(True)
        self.setMouseTracking(True)
        self._is_programmatic_expansion = False

        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.viewport().setAttribute(Qt.WA_AlwaysShowToolTips)

        from .custom_list_item_delegate import CustomListItemDelegate
        self.setItemDelegate(CustomListItemDelegate(self))
        self.setIndentation(15)

        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)

        # ── Drag & drop ───────────────────────────────────────────────────────
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Snapshot of items captured at startDrag() before Qt changes selection
        self._pending_drag_items = []
        self._custom_drop_target = None
        self.setDropIndicatorShown(False)

        self.setStyleSheet("""
            QTreeWidget::item:selected { background-color: #0078D7; color: white; }
            QTreeWidget::item:selected:!active { background-color: #0078D7; color: white; }
            QTreeView::drop-indicator { color: #0078D7; }
        """)

        # ── Color-marker palette ──────────────────────────────────────────────
        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
        }

        # ── Signal connections ────────────────────────────────────────────────
        self.itemExpanded.connect(self._handle_item_state_changed)
        self.itemCollapsed.connect(self._handle_item_state_changed)
        self.itemChanged.connect(self._handle_item_changed)

    # ─────────────────────────────────────────────────────────────────────────
    # Qt event overrides
    # ─────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        # Right-click on an already-selected item: don't let Qt clear the multi-selection.
        if event.button() == Qt.RightButton:
            item = self.itemAt(event.pos())
            if item and item in self.selectedItems():
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        log_debug(f"CustomTreeWidget: keyPressEvent key={event.key()}, mods={int(event.modifiers())}")
        is_ctrl = bool(event.modifiers() & Qt.ControlModifier)
        is_alt = bool(event.modifiers() & Qt.AltModifier)
        is_shift = bool(event.modifiers() & Qt.ShiftModifier)

        if is_ctrl and not is_alt and not is_shift:
            if event.key() == Qt.Key_PageDown:
                self.navigate_blocks(direction=1); event.accept(); return
            if event.key() == Qt.Key_PageUp:
                self.navigate_blocks(direction=-1); event.accept(); return

        if is_alt and is_shift and not is_ctrl:
            key = event.key()
            if key == Qt.Key_Up:
                self.navigate_blocks(direction=-1); event.accept(); return
            if key == Qt.Key_Down:
                self.navigate_blocks(direction=1); event.accept(); return
            if key == Qt.Key_Left:
                self.navigate_folders(direction=-1); event.accept(); return
            if key == Qt.Key_Right:
                self.navigate_folders(direction=1); event.accept(); return

        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            mw = self.window()
            if hasattr(mw, 'handle_zoom'):
                mw.handle_zoom(event.angleDelta().y(), target='tree')
                event.accept()
                return
        super().wheelEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        target_info = getattr(self, '_custom_drop_target', None)
        if target_info:
            target_item, drop_pos = target_info
            if drop_pos in ("Above", "Below"):
                rect = self.visualItemRect(target_item)
                painter = QPainter(self.viewport())
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#0078D7"))
                y = rect.top() if drop_pos == "Above" else rect.bottom()
                painter.drawRect(rect.left(), y - 2, rect.width(), 4)
                painter.end()

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            log_debug("CustomTreeWidget: event() ToolTip received")
        return super().event(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            log_debug(f"CustomTreeWidget: viewport ToolTip at {event.pos()}")
        elif event.type() == QEvent.MouseMove:
            index = self.indexAt(event.pos())
            if index.isValid():
                delegate = self.itemDelegate(index)
                if delegate and hasattr(delegate, 'handle_tooltip'):
                    option = self.viewOptions()
                    option.rect = self.visualRect(index)
                    delegate.handle_tooltip(event, self, option, index)
            else:
                QToolTip.hideText()
        return super().viewportEvent(event)

    # ─────────────────────────────────────────────────────────────────────────
    # General-purpose helpers (shared by multiple mixins)
    # ─────────────────────────────────────────────────────────────────────────

    def _create_color_icon(self, color: QColor, size: int = 12) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def create_item(self, text: str, block_idx=None, role=Qt.UserRole) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item

    def select_block_by_index(self, block_idx: int, category: str = None) -> bool:
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item_block_idx = item.data(0, Qt.UserRole)
            item_category = item.data(0, Qt.UserRole + 10)
            match = (
                item_block_idx == block_idx
                and (item_category == category if category else item_category is None)
            )
            if match:
                self.clearSelection()
                self.setCurrentItem(item)
                item.setSelected(True)
                self.scrollToItem(item)
                return True
            iterator += 1
        return False

    def _get_next_unnamed_name(self, pm) -> str:
        """Return the next available 'Unnamed N' folder name."""
        if not pm or not pm.project:
            return "Unnamed 1"
        existing = set()

        def collect(folders):
            for f in folders:
                existing.add(f.name)
                collect(f.children)

        collect(pm.project.virtual_folders)
        n = 1
        while f"Unnamed {n}" in existing:
            n += 1
        return f"Unnamed {n}"
