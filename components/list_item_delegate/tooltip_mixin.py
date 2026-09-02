from PyQt6.QtWidgets import QToolTip
from PyQt6.QtGui import QCursor
from PyQt6.QtCore import QEvent, QRect, Qt


class CustomListItemTooltipMixin:
    """Tooltip / helpEvent for list item delegate."""

    def handle_tooltip(self, event, view, option, index):
        """Handle tooltip."""
        mouse_pos = event.pos()
        item_rect = option.rect
        main_window = self.list_widget.window() if self.list_widget else None
        if not main_window: return

        current_number_area_width = self._get_current_number_area_width(option)
        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        
        if number_rect.contains(mouse_pos):
            block_idx = index.data(Qt.ItemDataRole.UserRole)
            if block_idx is not None:
                tooltip_text = self._get_problems_tooltip_text(main_window, index)
                if tooltip_text:
                    QToolTip.showText(QCursor.pos(), tooltip_text, view)
                    return
        
        QToolTip.hideText()

    def _get_problems_tooltip_text(self, main_window, index) -> str:
        """Internal helper to get the problems tooltip text."""
        problem_definitions = {}
        if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            problem_definitions = main_window.current_game_rules.get_problem_definitions()
        
        tooltip_lines = []
        
        has_metadata_changes = self._item_has_layout_overrides(main_window, index)
        if has_metadata_changes:
            tooltip_lines.append("<b>Custom Layout Settings</b>: Layout settings override applied inside this item.")
            
        stored_counts = index.data(Qt.ItemDataRole.UserRole + 20)
        if isinstance(stored_counts, dict) and problem_definitions:
            block_problem_counts = stored_counts
            if block_problem_counts:
                sorted_ids = sorted(block_problem_counts.keys(), key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99))
                for pid in sorted_ids:
                    count = block_problem_counts[pid]
                    if count > 0:
                        prob_def = problem_definitions.get(pid, {})
                        name = prob_def.get("name", pid)
                        desc = prob_def.get("description", "")
                        tooltip_lines.append(f"<b>{name}</b>: {count} cases<br><i>{desc}</i>")
            
        if tooltip_lines:
            return "<br><br>".join(tooltip_lines)
        return ""

    def helpEvent(self, event, view, option, index) -> bool:
        """Helpevent."""
        if event.type() == QEvent.Type.ToolTip:
            self.handle_tooltip(event, view, option, index)
            return True
        return super().helpEvent(event, view, option, index)
