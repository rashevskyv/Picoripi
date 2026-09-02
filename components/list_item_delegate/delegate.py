from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt
from components.list_item_delegate.paint_mixin import CustomListItemPaintMixin
from components.list_item_delegate.tooltip_mixin import CustomListItemTooltipMixin
from components.list_item_delegate.editor_mixin import CustomListItemEditorMixin


class CustomListItemDelegate(
    CustomListItemPaintMixin,
    CustomListItemTooltipMixin,
    CustomListItemEditorMixin,
    QStyledItemDelegate,
):
    """Custom list item delegate implementation."""
    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.list_widget = parent
        
        self.problem_indicator_strip_width = 3 
        self.problem_indicator_strip_spacing = 2 
        self.max_problem_indicators = 3 

        self.color_marker_size = 8 
        self.color_marker_spacing = 3
        self.max_color_markers = 0 
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 58
        
        self.padding_after_number_area = 2 
        self.padding_after_color_marker_zone = 2
        self.padding_after_problem_indicator_zone = 2 
        self.indicator_v_offset = 2 

        self.marker_qcolors = {
            "red": QColor(Qt.GlobalColor.red),
            "green": QColor(Qt.GlobalColor.green),
            "blue": QColor(Qt.GlobalColor.blue),
        }

        # Cached QColors for performance optimization (AUD-P9)
        self._color_selected_default = QColor("#0078D7")
        self._color_dark_selected_bg = QColor("#0078D7").darker(110)
        self._color_dark_normal_bg = QColor("#383838")
        self._color_dark_normal_text = QColor("#B0B0B0")
        self._color_light_selected_bg = QColor("#0078D7").darker(105)
        self._color_light_normal_bg = QColor("#F0F0F0")
        self._color_white = QColor(Qt.GlobalColor.white)
        self._color_dark_gray = QColor(Qt.GlobalColor.darkGray)
        
        self._color_metadata_indicator = QColor(148, 0, 211)
        self._color_metadata_indicator_dark = QColor(148, 0, 211)
        self._color_metadata_indicator_dark.setAlpha(180)
        
        self._color_progress_bg = QColor(46, 139, 87, 25)
        
        self._color_cloud_light = QColor("#FFFFFF")
        self._color_cloud_dark = QColor("#E0E0E0")
        self._color_cloud_border_light = QColor("#44AADD")
        self._color_cloud_border_dark = QColor("#2288CC")
        
        self._color_text_gray_light = QColor(140, 140, 140)
        self._color_text_gray_dark = QColor(160, 160, 160)

    def _get_current_number_area_width(self, option: QStyleOptionViewItem) -> int:
        """Internal helper to get the current number area width."""
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        current_font_size = font_for_metrics.pointSize()
        if current_font_size <= 0: current_font_size = self.fixed_number_area_width_base_font_size

        scaled_width = int(self.fixed_number_area_width_base_pixels * \
                           (current_font_size / self.fixed_number_area_width_base_font_size))
        return max(scaled_width, 24)

    def _get_problem_indicator_zone_width(self) -> int:
        # Indicators are now drawn INSIDE the wider number area
        """Internal helper to get the problem indicator zone width."""
        return 0
    
    def _get_color_marker_zone_width(self) -> int:
        """Internal helper to get the color marker zone width."""
        if self.max_color_markers == 0: return 0
        return (self.color_marker_size * self.max_color_markers) + \
               (self.color_marker_spacing * (self.max_color_markers -1))

