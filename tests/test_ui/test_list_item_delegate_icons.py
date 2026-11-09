"""The Blocks tree delegate looks up each standard icon once per style, not on every paint."""
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QMainWindow, QProxyStyle, QStyle, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem

from components.custom_list_item_delegate import CustomListItemDelegate


class _CountingStyle(QProxyStyle):
    def __init__(self):
        super().__init__()
        self.lookups = []

    def standardIcon(self, standard_icon, option=None, widget=None):
        self.lookups.append(standard_icon)
        return super().standardIcon(standard_icon, option, widget)


def test_folder_rows_reuse_standard_icons_across_paints(qapp):
    window = QMainWindow()
    style = _CountingStyle()
    window.setStyle(style)
    tree = QTreeWidget()
    window.setCentralWidget(tree)
    delegate = CustomListItemDelegate(tree)
    for compaction, ids in ((1, ["a", "b"]), (2, ["c"]), (2, ["d", "e", "f"])):
        item = QTreeWidgetItem([f"Folder {ids[0]}"])
        item.setData(0, Qt.ItemDataRole.UserRole + 2, ids)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, compaction)
        tree.addTopLevelItem(item)

    pixmap = QPixmap(300, 30)
    painter = QPainter(pixmap)
    try:
        for _ in range(5):
            for row in range(tree.topLevelItemCount()):
                option = QStyleOptionViewItem()
                option.rect = QRect(0, 0, 300, 24)
                delegate.paint(painter, option, tree.model().index(row, 0))
    finally:
        painter.end()

    # 15 row paints; one lookup per icon kind.
    assert len(style.lookups) == 2
    assert set(style.lookups) == {QStyle.StandardPixmap.SP_DirIcon, QStyle.StandardPixmap.SP_FileIcon}
