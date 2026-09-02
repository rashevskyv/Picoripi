from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtGui import QFontMetrics, QFont
from PyQt6.QtCore import QSize, QModelIndex, Qt, QRect


class CustomListItemEditorMixin:
    """Editor data, sizeHint, and geometry for list item delegate."""

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Sizehint."""
        default_hint = super().sizeHint(option, index)
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        fm = QFontMetrics(font_for_metrics)
        min_height = fm.height() + 6 

        current_number_area_width = self._get_current_number_area_width(option)
        problem_indicator_zone_total_width = self._get_problem_indicator_zone_width()
        color_marker_zone_total_width = self._get_color_marker_zone_width()

        calculated_width = current_number_area_width + \
                           self.padding_after_number_area + \
                           color_marker_zone_total_width + \
                           (self.padding_after_color_marker_zone if color_marker_zone_total_width > 0 else 0) + \
                           problem_indicator_zone_total_width + \
                           (self.padding_after_problem_indicator_zone if problem_indicator_zone_total_width > 0 else 0) + \
                           fm.horizontalAdvance(str(index.data(Qt.ItemDataRole.DisplayRole))) + 20

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))


    def setEditorData(self, editor, index):
        # We explicitly stored the pure name in Qt.ItemDataRole.UserRole + 4 to avoid 
        # issues where QTreeWidget fallback pulls the DisplayRole (which has issue counts).
        """Seteditordata."""
        pure_name = index.data(Qt.ItemDataRole.UserRole + 4)
        if pure_name is not None:
            if hasattr(editor, 'setText'):
                editor.setText(pure_name)
                return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Setmodeldata."""
        if hasattr(editor, 'text'):
            new_text = editor.text()
            model.setData(index, new_text, Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        """Updateeditorgeometry."""
        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)
        text_start_x = item_rect.left() + current_number_area_width + self.padding_after_number_area
        
        # The editor should fill the space from the end of the gutter to the end of the item
        editor_rect = QRect(text_start_x, item_rect.top(), item_rect.right() - text_start_x, item_rect.height())
        editor.setGeometry(editor_rect)
