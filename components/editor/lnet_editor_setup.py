from PyQt6.QtWidgets import QMainWindow, QPushButton, QMenu
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

from .constants import (
    LT_CURRENT_LINE_COLOR, LT_LINKED_CURSOR_BLOCK_COLOR, LT_PREVIEW_SELECTED_LINE_COLOR, LT_PREVIOUSLY_SELECTED_LINE_COLOR,
    LT_ZEBRA_EVEN_COLOR, LT_ZEBRA_ODD_COLOR,
    DT_CURRENT_LINE_COLOR, DT_LINKED_CURSOR_BLOCK_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIOUSLY_SELECTED_LINE_COLOR,
    DT_ZEBRA_EVEN_COLOR, DT_ZEBRA_ODD_COLOR,
    LINKED_CURSOR_POS_COLOR, TAG_INTERACTION_HIGHLIGHT_COLOR,
    SEARCH_MATCH_HIGHLIGHT_COLOR, WIDTH_EXCEEDED_LINE_COLOR, SHORT_LINE_COLOR,
    EMPTY_ODD_SUBLINE_COLOR, NEW_BLUE_SUBLINE_COLOR,
    CRITICAL_PROBLEM_LINE_COLOR, WARNING_PROBLEM_LINE_COLOR
)


def set_theme_colors(editor, main_window_ref):
    """Apply theme-specific colors to the editor and its line number area."""
    theme = 'light'
    if main_window_ref and hasattr(main_window_ref, 'theme'):
        theme = main_window_ref.theme

    if theme == 'dark':
        editor.current_line_color = DT_CURRENT_LINE_COLOR
        editor.linked_cursor_block_color = DT_LINKED_CURSOR_BLOCK_COLOR
        editor.preview_selected_line_color = DT_PREVIEW_SELECTED_LINE_COLOR
        editor.previously_selected_line_color = DT_PREVIOUSLY_SELECTED_LINE_COLOR
        editor.zebra_even_color = DT_ZEBRA_EVEN_COLOR
        editor.zebra_odd_color = DT_ZEBRA_ODD_COLOR
        editor.lineNumberArea.odd_line_background = DT_ZEBRA_ODD_COLOR
        editor.lineNumberArea.even_line_background = DT_ZEBRA_EVEN_COLOR
        editor.lineNumberArea.number_color = QColor("#B0B0B0")
    else:
        editor.current_line_color = LT_CURRENT_LINE_COLOR
        editor.linked_cursor_block_color = LT_LINKED_CURSOR_BLOCK_COLOR
        editor.preview_selected_line_color = LT_PREVIEW_SELECTED_LINE_COLOR
        editor.previously_selected_line_color = LT_PREVIOUSLY_SELECTED_LINE_COLOR
        editor.zebra_even_color = LT_ZEBRA_EVEN_COLOR
        editor.zebra_odd_color = LT_ZEBRA_ODD_COLOR
        editor.lineNumberArea.odd_line_background = LT_ZEBRA_ODD_COLOR
        editor.lineNumberArea.even_line_background = LT_ZEBRA_EVEN_COLOR
        editor.lineNumberArea.number_color = QColor(Qt.GlobalColor.darkGray)

    editor.linked_cursor_pos_color = LINKED_CURSOR_POS_COLOR
    editor.tag_interaction_highlight_color = TAG_INTERACTION_HIGHLIGHT_COLOR
    editor.search_match_highlight_color = SEARCH_MATCH_HIGHLIGHT_COLOR
    editor.width_exceeded_line_color = WIDTH_EXCEEDED_LINE_COLOR
    editor.short_line_color = SHORT_LINE_COLOR
    editor.empty_odd_subline_color = EMPTY_ODD_SUBLINE_COLOR
    editor.new_blue_subline_color = NEW_BLUE_SUBLINE_COLOR
    editor.critical_problem_line_color = CRITICAL_PROBLEM_LINE_COLOR
    editor.warning_problem_line_color = WARNING_PROBLEM_LINE_COLOR

    if hasattr(editor, 'highlightManager') and editor.highlightManager:
        editor.highlightManager.update_zebra_stripes()


def create_tag_button(editor, parent_widget, display: str, open_tag: str,
                      close_tag: str = None, menu: QMenu = None):
    """Create a small button for inserting or wrapping text with a game tag."""
    btn = QPushButton(parent_widget)
    button_size = 24
    btn.setFixedSize(button_size, button_size)

    is_color = display.startswith('#')
    if is_color:
        style = f"background-color: {display}; border: 1px solid black; border-radius: 3px;"
        btn.setStyleSheet(style)
        btn.setToolTip(f"Wrap: {open_tag}{'...' + close_tag if close_tag else ''}")
    else:
        btn.setText(display)
        btn.setToolTip(f"Insert/Wrap: {open_tag}{'...' + close_tag if close_tag else ''}")
        btn.setStyleSheet("padding: 0px; font-size: 14px;")

    def on_click():
        """Handle the click event."""
        if close_tag:
            editor.mouse_handler.wrap_selection_with_custom_tags(open_tag, close_tag)
        else:
            editor.mouse_handler.insert_single_tag(open_tag)
        if menu:
            menu.close()

    btn.clicked.connect(on_click)
    return btn


def update_auxiliary_widths(editor):
    """Recalculate pixel-width display area and preview indicator area widths."""
    current_font_metrics = editor.fontMetrics()

    max_width_for_calc = editor.game_dialog_max_width_pixels
    if max_width_for_calc < 1000:
        max_width_for_calc = 1000

    editor.pixel_width_display_area_width = current_font_metrics.horizontalAdvance(str(max_width_for_calc)) + 6

    num_indicators_to_display = 0
    main_window = editor.window()
    if isinstance(main_window, QMainWindow) and hasattr(main_window, 'current_game_rules') \
            and main_window.current_game_rules:
        problem_defs = main_window.current_game_rules.get_problem_definitions()
        num_indicators_to_display = len(problem_defs)

    max_preview_indicators = getattr(editor.lineNumberArea, 'max_problem_indicators', 5)
    num_indicators_to_display = min(num_indicators_to_display, max_preview_indicators)

    indicator_area_width = 0
    indicator_area_width += editor.lineNumberArea.preview_indicator_width + editor.lineNumberArea.preview_indicator_spacing
    if num_indicators_to_display > 0:
        indicator_area_width += (editor.lineNumberArea.preview_indicator_width * num_indicators_to_display) + \
                                (editor.lineNumberArea.preview_indicator_spacing * num_indicators_to_display)

    editor.preview_indicator_area_width = indicator_area_width + 2

    editor.updateLineNumberAreaWidth(0)
