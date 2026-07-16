from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QWidget, QApplication, QLabel
from PyQt6.QtGui import QFont, QPalette, QColor, QTextOption
from PyQt6.QtCore import Qt
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET
from ui.adaptive_scrollbars import install_adaptive_scrollbars
from utils.constants import DT_PREVIEW_SELECTED_LINE_COLOR, LT_PREVIEW_SELECTED_LINE_COLOR
from typing import List
from utils.logging_utils import log_info
from components.custom_list_widget import CustomListWidget
from components.custom_list_item_delegate import CustomListItemDelegate

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowUIHandler:
    """Handler for main window u i operations."""
    def __init__(self, main_window: MainWindow):
        """Initialize a new instance."""
        self.mw = main_window

    def update_editor_rules_properties(self):
        """Update the editor rules properties."""
        for editor in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor:
                editor.line_width_warning_threshold_pixels = self.mw.line_width_warning_threshold_pixels
                editor.game_dialog_max_width_pixels = self.mw.game_dialog_max_width_pixels
                editor.show_width_guideline = getattr(self.mw, 'show_width_guideline', True)
                if hasattr(editor, '_update_auxiliary_widths'):
                    editor._update_auxiliary_widths()
                editor.viewport().update()

    def apply_font_size(self, fast=False, target='all'):
        """Apply font size."""
        if self.mw.current_font_size <= 0:
            return

        general_font = QFont(self.mw.general_font_family, self.mw.current_font_size)
        tree_font = QFont(self.mw.general_font_family, self.mw.tree_font_size)
        preview_font = QFont(self.mw.editor_font_family, self.mw.preview_font_size)
        editors_font = QFont(self.mw.editor_font_family, self.mw.editors_font_size)

        if target in ['all', 'general']:
            QApplication.setFont(general_font)
            # QComboBox creates its popup lazily, outside the normal widget tree.
            # Keep the Font selector's list in step with the application font size.
            font_combobox = getattr(self.mw, 'font_combobox', None)
            if font_combobox:
                try:
                    font_combobox.view().setFont(general_font)
                    font_combobox.view().viewport().update()
                except Exception:
                    pass

        editor_widgets = [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]
        general_ui_widgets = [
            self.mw.search_panel_widget, self.mw.statusBar, self.mw.auto_fix_button
        ]

        labels_in_status_bar = [self.mw.original_path_label, self.mw.edited_path_label, 
                                self.mw.status_label_part1, self.mw.status_label_part2, self.mw.status_label_part3]
        general_ui_widgets.extend(labels_in_status_bar)

        if self.mw.menuBar():
            general_ui_widgets.append(self.mw.menuBar())
            from PyQt6.QtWidgets import QMenu
            for menu in self.mw.menuBar().findChildren(QMenu):
                general_ui_widgets.append(menu)
                
        if self.mw.search_panel_widget:
            general_ui_widgets.extend([
                self.mw.search_panel_widget.search_query_edit,
                self.mw.search_panel_widget.search_query_edit.lineEdit(),
                self.mw.search_panel_widget.find_next_button,
                self.mw.search_panel_widget.find_previous_button,
                self.mw.search_panel_widget.advanced_button,
                self.mw.search_panel_widget.case_sensitive_checkbox,
                self.mw.search_panel_widget.fuzzy_search_checkbox,
                self.mw.search_panel_widget.search_in_original_checkbox,
                self.mw.search_panel_widget.ignore_tags_newlines_checkbox,
                self.mw.search_panel_widget.status_label,
                self.mw.search_panel_widget.close_search_panel_button
            ])

        
        if self.mw.main_splitter:
            for i in range(self.mw.main_splitter.count()):
                widget = self.mw.main_splitter.widget(i)
                if widget not in editor_widgets and widget not in general_ui_widgets:
                    general_ui_widgets.append(widget)
                    for child_widget in widget.findChildren(QWidget):
                         if child_widget not in editor_widgets and child_widget not in general_ui_widgets:
                             general_ui_widgets.append(child_widget)


        for editor, font in zip([self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit], 
                                [preview_font, editors_font, editors_font]):
            if editor:
                try:
                    editor.setFont(font)
                    if hasattr(editor, 'updateGeometry'): editor.updateGeometry()
                    if hasattr(editor, 'adjustSize'): editor.adjustSize()
                    if hasattr(editor, 'updateLineNumberAreaWidth'):
                        editor.updateLineNumberAreaWidth(0)
                    editor.viewport().update()
                except Exception:
                    pass

        if self.mw.block_list_widget:
            try:
                self.mw.block_list_widget.setFont(tree_font)
                self.mw.block_list_widget.viewport().update()
            except Exception:
                pass

        if fast:
            if target == 'tree' and self.mw.block_list_widget:
                # Force refresh of sizes in the tree
                self.mw.block_list_widget.doItemsLayout()
                self.mw.block_list_widget.viewport().update()
            return
    
        for widget in general_ui_widgets:
            if widget and widget not in editor_widgets:
                try:
                    widget.setFont(general_font)
                    if hasattr(widget, 'updateGeometry'): widget.updateGeometry()
                    if hasattr(widget, 'adjustSize'): widget.adjustSize()
                    if isinstance(widget, CustomListWidget):
                        widget.viewport().update()
                except Exception:
                    pass


        if self.mw.block_list_widget and self.mw.block_list_widget.itemDelegate():
            self.mw.block_list_widget.itemDelegate().deleteLater()
            new_delegate = CustomListItemDelegate(self.mw.block_list_widget)
            self.mw.block_list_widget.setItemDelegate(new_delegate)
            self.mw.block_list_widget.viewport().update()

        if self.mw.search_panel_widget:
            try:
                line_edit = self.mw.search_panel_widget.search_query_edit.lineEdit()
                if line_edit:
                    fm = line_edit.fontMetrics()
                    needed_height = fm.height() + 10
                    line_edit.setMinimumHeight(needed_height)
                    self.mw.search_panel_widget.search_query_edit.setMinimumHeight(needed_height + 2)
            except Exception:
                pass

        self.mw.ui_updater.update_text_views()
        self.mw.ui_updater.populate_blocks()
        self.mw.ui_updater.populate_current_view()

    def apply_text_wrap_settings(self):
        """Apply text wrap settings."""
        if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
            if self.mw.preview_wrap_lines:
                self.mw.preview_text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            else:
                self.mw.preview_text_edit.setWordWrapMode(QTextOption.NoWrap)
        
        for editor in [self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor:
                if self.mw.editors_wrap_lines:
                    editor.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
                else:
                    editor.setWordWrapMode(QTextOption.NoWrap)

    def reconfigure_all_highlighters(self):
        # Compose CSS for newline; highlighter supports CSS parsing
        """Reconfigure all highlighters."""
        nl_color = getattr(self.mw, 'newline_color_rgba', "#A020F0")
        nl_css_parts = [f"color: {nl_color}"]
        if getattr(self.mw, 'newline_bold', True): nl_css_parts.append("font-weight: bold")
        if getattr(self.mw, 'newline_italic', False): nl_css_parts.append("font-style: italic")
        if getattr(self.mw, 'newline_underline', False): nl_css_parts.append("text-decoration: underline")
        newline_css_str = "; ".join(nl_css_parts) + ";"

        # Compose CSS for tags
        tag_color = getattr(self.mw, 'tag_color_rgba', getattr(self.mw, 'bracket_tag_color_hex', "#FF8C00"))
        tag_css_parts = [f"color: {tag_color}"]
        if getattr(self.mw, 'tag_bold', True): tag_css_parts.append("font-weight: bold")
        if getattr(self.mw, 'tag_italic', False): tag_css_parts.append("font-style: italic")
        if getattr(self.mw, 'tag_underline', False): tag_css_parts.append("text-decoration: underline")
        tag_css_str = "; ".join(tag_css_parts) + ";"

        common_args = {
            "newline_symbol": self.mw.newline_display_symbol,
            "newline_css_str": newline_css_str,
            "tag_css_str": tag_css_str,
            "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex,
            "bracket_tag_color_hex": tag_color,
        }
        for editor in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor and hasattr(editor, 'highlighter') and editor.highlighter:
                editor.highlighter.reconfigure_styles(**common_args)

    def force_focus(self):
        """Force focus."""
        self.mw.activateWindow()
        self.mw.raise_()
        
    @staticmethod
    def apply_theme(app, theme_name: str):
        """Apply theme."""
        if theme_name == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(46, 46, 46))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
            palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 37))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(74, 74, 74))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(46, 46, 46))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(224, 224, 224))
            palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
            palette.setColor(QPalette.ColorRole.Button, QColor(74, 74, 74))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(DT_PREVIEW_SELECTED_LINE_COLOR))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
            app.setPalette(palette)
            app.setStyleSheet(DARK_THEME_STYLESHEET)
            install_adaptive_scrollbars(app)
            log_info("Applied Dark Theme.")
        else: # 'auto' or 'light'
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(LT_PREVIEW_SELECTED_LINE_COLOR))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Qt.GlobalColor.black))
            app.setPalette(palette)
            app.setStyleSheet(LIGHT_THEME_STYLESHEET)
            install_adaptive_scrollbars(app)
            log_info("Applied Light Theme.")
