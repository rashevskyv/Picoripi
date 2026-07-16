from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QPushButton, QStyle, QSpacerItem, QSizePolicy, QComboBox, QSpinBox, QMenu, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.custom_tree_widget import CustomTreeWidget


class NavigableLabel(QLabel):
    """Read-only text that can open its represented virtual destination."""

    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        event.accept()


class ClickableLabel(QLabel):
    """Read-only value that exposes a deliberate single-click action."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

class LayoutBuilder:
    """Layout builder implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        self.mw = main_window
        self.style = main_window.style()

    def build(self):
        """Create ."""
        central_widget = QWidget()
        self.mw.setCentralWidget(central_widget)
        self.mw.main_vertical_layout = QVBoxLayout(central_widget)
        
        self.mw.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self._build_left_panel()
        self._build_right_panel()
        
        self.mw.main_splitter.addWidget(self.left_panel)
        self.mw.main_splitter.addWidget(self.mw.right_splitter)
        self.mw.main_splitter.setSizes([200, 800])

        self.mw.main_vertical_layout.addWidget(self.mw.main_splitter)

    def _build_left_panel(self):
        """Internal helper to create left panel."""
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Block Header
        block_header_layout = QHBoxLayout()
        block_header_layout.addWidget(QLabel("Blocks (double-click to rename):"))
        block_header_layout.addStretch()

        self.mw.add_folder_button = self._create_header_button(self.style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), 'Create new virtual folder')
        self.mw.add_folder_button.setEnabled(False)
        block_header_layout.addWidget(self.mw.add_folder_button)

        self.mw.expand_all_button = self._create_header_button(self.style.standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton), 'Expand all folders', '⇊')
        block_header_layout.addWidget(self.mw.expand_all_button)

        self.mw.collapse_all_button = self._create_header_button(self.style.standardIcon(QStyle.StandardPixmap.SP_TitleBarShadeButton), 'Collapse all folders', '⇈')
        block_header_layout.addWidget(self.mw.collapse_all_button)

        left_layout.addLayout(block_header_layout)

        # Block Filter
        block_filter_layout = QHBoxLayout()
        self.mw.show_unsaved_blocks_checkbox = QCheckBox("Show Unsaved Only")
        self.mw.show_unsaved_blocks_checkbox.setToolTip("Only show blocks and folders with unsaved changes.")
        self.mw.show_unsaved_blocks_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        block_filter_layout.addWidget(self.mw.show_unsaved_blocks_checkbox)
        block_filter_layout.addStretch()
        left_layout.addLayout(block_filter_layout)

        # Block List Container
        block_list_container = QWidget()
        block_list_container_layout = QVBoxLayout(block_list_container)
        block_list_container_layout.setContentsMargins(0, 0, 0, 0)
        block_list_container_layout.setSpacing(0)

        self.mw.block_list_widget = CustomTreeWidget(self.mw)
        self.mw.block_list_widget.setAlternatingRowColors(True)
        
        block_list_container_layout.addWidget(self.mw.block_list_widget)

        # Block Toolbar
        block_toolbar = QHBoxLayout()
        block_toolbar.setContentsMargins(4, 4, 4, 4)
        block_toolbar.setSpacing(4)

        self.mw.add_block_button = self._create_toolbar_button('+', 'Add new block (import file)')
        block_toolbar.addWidget(self.mw.add_block_button)

        self.mw.delete_block_button = self._create_toolbar_button('-', 'Delete selected block')
        block_toolbar.addWidget(self.mw.delete_block_button)

        self.mw.rename_block_button = self._create_toolbar_button('✎', 'Rename selected block')
        block_toolbar.addWidget(self.mw.rename_block_button)

        block_toolbar.addStretch()

        self.mw.move_block_up_button = self._create_toolbar_button('↑', 'Move block up')
        block_toolbar.addWidget(self.mw.move_block_up_button)

        self.mw.move_block_down_button = self._create_toolbar_button('↓', 'Move block down')
        block_toolbar.addWidget(self.mw.move_block_down_button)

        block_list_container_layout.addLayout(block_toolbar)
        left_layout.addWidget(block_list_container)
        
        left_layout.addSpacing(8)
        self.mw.open_glossary_button = QPushButton('Glossary…')
        self.mw.open_glossary_button.setToolTip('Open glossary')
        left_layout.addWidget(self.mw.open_glossary_button)

    def _build_right_panel(self):
        """Internal helper to create right panel."""
        self.mw.right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Right (Preview)
        top_right_panel = QWidget()
        top_right_layout = QVBoxLayout(top_right_panel)
        
        preview_header_layout = QHBoxLayout()
        preview_header_layout.setContentsMargins(0, 0, 8, 0)
        preview_header_layout.addWidget(QLabel("Strings in block (click line to select):"))
        preview_header_layout.addStretch()
        
        self.mw.highlight_categorized_checkbox = QCheckBox("Highlight moved")
        self.mw.highlight_categorized_checkbox.setToolTip("Highlight strings in the parent block that have already been moved to a virtual block (category). Helps you see what's left to organize.")
        self.mw.highlight_categorized_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.highlight_categorized_checkbox.hide()
        preview_header_layout.addWidget(self.mw.highlight_categorized_checkbox)
        
        preview_header_layout.addSpacing(15)
        
        self.mw.hide_categorized_checkbox = QCheckBox("Hide moved")
        self.mw.hide_categorized_checkbox.setToolTip("Filter out strings from the parent block view if they are already present in any virtual block. Useful for focused organizing.")
        self.mw.hide_categorized_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.hide_categorized_checkbox.hide()
        preview_header_layout.addWidget(self.mw.hide_categorized_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.hide_empty_strings_checkbox = QCheckBox("Hide empty strings")
        self.mw.hide_empty_strings_checkbox.setToolTip("Collapse consecutive empty strings into a single placeholder.")
        self.mw.hide_empty_strings_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.hide_empty_strings_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.hide_translated_checkbox = QCheckBox("Hide translated")
        self.mw.hide_translated_checkbox.setToolTip("Hide strings that have already been translated.")
        self.mw.hide_translated_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.hide_translated_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.show_overrides_only_checkbox = QCheckBox("Show Overrides Only")
        self.mw.show_overrides_only_checkbox.setToolTip("Only show strings that have custom font or width overrides.")
        self.mw.show_overrides_only_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.show_overrides_only_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.show_unsaved_only_checkbox = QCheckBox("Show Unsaved Only")
        self.mw.show_unsaved_only_checkbox.setToolTip("Only show strings with unsaved changes.")
        self.mw.show_unsaved_only_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.show_unsaved_only_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.show_warnings_only_checkbox = QCheckBox("Show Warnings Only:")
        self.mw.show_warnings_only_checkbox.setToolTip("Only show strings with selected warnings.")
        self.mw.show_warnings_only_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.show_warnings_only_checkbox)
        
        self.mw.warnings_filter_button = QPushButton("Warnings: 0 / 0")
        self.mw.warnings_filter_button.setToolTip("Select warnings to filter by")
        self.mw.warnings_filter_button.setFixedWidth(150)
        self.mw.warnings_filter_button.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.warnings_filter_button)
        
        top_right_layout.addLayout(preview_header_layout)
        self.mw.preview_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.preview_text_edit.setObjectName("preview_text_edit")
        self.mw.preview_text_edit.setReadOnly(True)
        self.mw.preview_text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        top_right_layout.addWidget(self.mw.preview_text_edit)
        self.mw.right_splitter.addWidget(top_right_panel)

        # Bottom Right (Editors)
        self.mw.bottom_right_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._build_original_panel()
        self._build_middle_panel()
        self._build_edited_panel()
        
        self.mw.right_splitter.addWidget(self.mw.bottom_right_splitter)
        self.mw.right_splitter.setSizes([150, 450])
        self.mw.bottom_right_splitter.setSizes([380, 40, 380])

    def _build_original_panel(self):
        """Internal helper to create original panel."""
        bottom_left_panel = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_panel)

        self.mw.left_header_container = QWidget()
        left_header_layout = QVBoxLayout(self.mw.left_header_container)
        left_header_layout.setContentsMargins(0, 0, 0, 0)
        left_header_layout.setSpacing(0)

        original_tools_layout = QHBoxLayout()
        original_tools_layout.setContentsMargins(0, 0, 0, 0)
        original_tools_layout.setSpacing(6)

        original_tools_layout.addWidget(QLabel("Max-width:"))
        self.mw.original_width_label = ClickableLabel("")
        self.mw.original_width_label.setObjectName("original_width_value")
        self.mw.original_width_label.setStyleSheet(
            "QLabel#original_width_value { font-weight: bold; padding: 1px 6px; "
            "border: 1px solid palette(mid); border-radius: 3px; }"
        )
        self.mw.original_width_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.original_width_label.setToolTip(
            "Click to copy this original-text width to the translation Max-width field."
        )
        original_tools_layout.addWidget(self.mw.original_width_label)
        original_tools_layout.addStretch(1)

        self.mw.hide_original_tags_checkbox = QCheckBox("Hide tags")
        self.mw.hide_original_tags_checkbox.setToolTip("Hide tags in all text panels. (Ctrl+Q)")
        self.mw.hide_original_tags_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        original_tools_layout.addWidget(self.mw.hide_original_tags_checkbox)
        left_header_layout.addStretch(1)
        left_header_layout.addLayout(original_tools_layout)

        original_header_layout = QHBoxLayout()
        original_header_layout.setContentsMargins(0, 0, 0, 0)
        original_header_layout.addWidget(self._create_editor_title_label("Original"))
        original_header_layout.addStretch(1)

        left_header_layout.addLayout(original_header_layout)
        bottom_left_layout.addWidget(self.mw.left_header_container)

        self.mw.original_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.original_text_edit.setObjectName("original_text_edit")
        self.mw.original_text_edit.setReadOnly(True)
        self.mw.original_text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        bottom_left_layout.addWidget(self.mw.original_text_edit)
        self.mw.bottom_right_splitter.addWidget(bottom_left_panel)

    def _build_middle_panel(self):
        """Internal helper to create middle panel."""
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        
        middle_layout.addSpacing(92)
        
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
        
        # Create a dynamic beautiful icon for Inspect Story Context with letter 'S'
        pixmap_s = QPixmap(32, 32)
        pixmap_s.fill(Qt.GlobalColor.transparent)
        painter_s = QPainter(pixmap_s)
        painter_s.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_s.setPen(QColor("#0078d7")) # Classic Microsoft Blue
        font_s = QFont("Arial", 22, QFont.Weight.Bold)
        painter_s.setFont(font_s)
        painter_s.drawText(pixmap_s.rect(), Qt.AlignmentFlag.AlignCenter, "S")
        painter_s.end()
        story_icon = QIcon(pixmap_s)

        # Match the purple "R" used by Script Markup Studio in the Tools menu.
        pixmap_markup = QPixmap(32, 32)
        pixmap_markup.fill(Qt.GlobalColor.transparent)
        painter_markup = QPainter(pixmap_markup)
        painter_markup.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_markup.setPen(QColor("#8e44ad"))
        font_markup = QFont("Arial", 22, QFont.Weight.Bold)
        painter_markup.setFont(font_markup)
        painter_markup.drawText(
            pixmap_markup.rect(), Qt.AlignmentFlag.AlignCenter, "R"
        )
        painter_markup.end()
        markup_icon = QIcon(pixmap_markup)
        
        # Create a dynamic beautiful icon for Restore Translation (document sheet with a blue arrow pointing right)
        pixmap_r = QPixmap(32, 32)
        pixmap_r.fill(Qt.GlobalColor.transparent)
        painter_r = QPainter(pixmap_r)
        painter_r.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Draw document sheet (sheet of paper)
        painter_r.setPen(QColor("#7f8c8d")) # Gray outline
        painter_r.setBrush(QColor("#ffffff")) # White filled paper
        
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        paper_poly = QPolygonF([
            QPointF(4, 4),
            QPointF(14, 4),
            QPointF(20, 10),
            QPointF(20, 26),
            QPointF(4, 26)
        ])
        painter_r.drawPolygon(paper_poly)
        
        # Draw fold corner line
        painter_r.drawLine(14, 4, 14, 10)
        painter_r.drawLine(14, 10, 20, 10)
        
        # Draw some decorative text lines on the paper
        painter_r.setPen(QColor("#bdc3c7"))
        painter_r.drawLine(7, 10, 11, 10)
        painter_r.drawLine(7, 14, 15, 14)
        painter_r.drawLine(7, 18, 17, 18)
        painter_r.drawLine(7, 22, 13, 22)
        
        # Draw blue arrow coming out of the sheet pointing right
        painter_r.setPen(QColor("#0078d7"))
        painter_r.setBrush(QColor("#0078d7"))
        
        # Thicker line for the arrow shaft
        arrow_pen = painter_r.pen()
        arrow_pen.setColor(QColor("#0078d7"))
        arrow_pen.setWidth(3)
        painter_r.setPen(arrow_pen)
        painter_r.drawLine(10, 15, 23, 15)
        
        # Arrow head points
        arrow_head = QPolygonF([
            QPointF(19, 10),
            QPointF(26, 15),
            QPointF(19, 20)
        ])
        painter_r.setPen(Qt.PenStyle.NoPen)
        painter_r.setBrush(QColor("#0078d7"))
        painter_r.drawPolygon(arrow_head)
        
        painter_r.end()
        restore_icon = QIcon(pixmap_r)

        self.mw.revert_string_button = QPushButton()
        self.mw.revert_string_button.setIcon(self.style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.mw.revert_string_button.setToolTip("Revert current string to original file content")
        self.mw.revert_string_button.setFixedWidth(30)
        self.mw.revert_string_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.revert_string_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.revert_string_button, 0, Qt.AlignmentFlag.AlignCenter)
        
        middle_layout.addSpacing(6)
        
        self.mw.restore_translation_button = QPushButton()
        self.mw.restore_translation_button.setIcon(restore_icon)
        self.mw.restore_translation_button.setToolTip("Restore last saved/reverted translation (Ctrl+Shift+T)")
        self.mw.restore_translation_button.setFixedWidth(30)
        self.mw.restore_translation_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.restore_translation_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.restore_translation_button, 0, Qt.AlignmentFlag.AlignCenter)
        
        middle_layout.addSpacing(6)
        
        self.mw.inspect_story_context_button = QPushButton()
        self.mw.inspect_story_context_button.setIcon(story_icon)
        self.mw.inspect_story_context_button.setToolTip('Show timeline, speaker and visual context for the selected row from MemePalace (Ctrl+I)')
        self.mw.inspect_story_context_button.setFixedWidth(30)
        self.mw.inspect_story_context_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mw.inspect_story_context_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.inspect_story_context_button, 0, Qt.AlignmentFlag.AlignCenter)

        middle_layout.addSpacing(6)

        self.mw.open_current_string_in_markup_studio_button = QPushButton()
        self.mw.open_current_string_in_markup_studio_button.setIcon(markup_icon)
        self.mw.open_current_string_in_markup_studio_button.setToolTip(
            "Open the marked-script place linked to the current game string in "
            "Script Markup Studio"
        )
        self.mw.open_current_string_in_markup_studio_button.setFixedWidth(30)
        self.mw.open_current_string_in_markup_studio_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.mw.open_current_string_in_markup_studio_button.setStyleSheet(
            "QPushButton { padding: 4px; border: 1px solid #ccc; "
            "border-radius: 4px; background-color: #f9f9f9; } "
            "QPushButton:hover { background-color: #e6e6e6; }"
        )
        middle_layout.addWidget(
            self.mw.open_current_string_in_markup_studio_button,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        middle_layout.addStretch(1)
        
        middle_panel.setFixedWidth(34)
        self.mw.bottom_right_splitter.addWidget(middle_panel)

    def _build_edited_panel(self):
        """Internal helper to create edited panel."""
        bottom_right_panel = QWidget()
        bottom_right_layout = QVBoxLayout(bottom_right_panel)
        
        self.mw.right_header_container = QWidget()
        right_header_layout = QVBoxLayout(self.mw.right_header_container)
        right_header_layout.setContentsMargins(0, 0, 0, 0)
        right_header_layout.setSpacing(0)

        control_height = 30

        header_grid = QGridLayout()
        header_grid.setContentsMargins(0, 2, 0, 2)
        header_grid.setHorizontalSpacing(4)
        header_grid.setVerticalSpacing(2)
        compact_context_height = 28
        compact_context_width = 220
        compact_label_width = 62

        # Row 1: window information on the left, actions on the far right.
        self.mw.window_kind_label = NavigableLabel("Window:")
        self.mw.window_kind_label.setStyleSheet(
            "font-weight: bold; color: #2e7d32; font-size: 13px;"
        )
        self.mw.window_kind_label.setToolTip(
            "Message window type from the game data. Double-click to open the physical game block.")
        self.mw.window_kind_label.setFixedWidth(compact_label_width)
        header_grid.addWidget(self.mw.window_kind_label, 0, 0)

        self.mw.window_kind_value_label = QLabel("")
        self.mw.window_kind_value_label.setFixedWidth(compact_context_width)
        self.mw.window_kind_value_label.setFixedHeight(compact_context_height)
        self.mw.window_kind_value_label.setStyleSheet("color: #000000; font-size: 13px;")
        self.mw.window_kind_value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.mw.window_kind_value_label.setToolTip(self.mw.window_kind_label.toolTip())
        header_grid.addWidget(self.mw.window_kind_value_label, 0, 1)

        editor_action_group = QWidget()
        editor_action_layout = QHBoxLayout(editor_action_group)
        editor_action_layout.setContentsMargins(0, 0, 0, 0)
        editor_action_layout.setSpacing(4)

        self.mw.navigate_down_button = QPushButton()
        self.mw.navigate_down_button.setIcon(self.style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.mw.navigate_down_button.setToolTip("Navigate to next problem string (Ctrl+Down)")
        self.mw.navigate_down_button.setFixedSize(control_height, control_height)
        editor_action_layout.addWidget(self.mw.navigate_down_button)

        self.mw.navigate_up_button = QPushButton()
        self.mw.navigate_up_button.setIcon(self.style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.mw.navigate_up_button.setToolTip("Navigate to previous problem string (Ctrl+Up)")
        self.mw.navigate_up_button.setFixedSize(control_height, control_height)
        editor_action_layout.addWidget(self.mw.navigate_up_button)

        self.mw.ai_translate_button = QPushButton('AI Translate')
        self.mw.ai_translate_button.setFixedHeight(control_height)
        editor_action_layout.addWidget(self.mw.ai_translate_button)

        self.mw.ai_variation_button = QPushButton('AI Variation')
        self.mw.ai_variation_button.setFixedHeight(control_height)
        editor_action_layout.addWidget(self.mw.ai_variation_button)

        self.mw.auto_fix_button = QPushButton('Auto-fix')
        self.mw.auto_fix_button.setToolTip("Automatically fix issues in the current string (Ctrl+Shift+A). Ctrl-click to select rules.")
        self.mw.auto_fix_button.setFixedHeight(control_height)
        editor_action_layout.addWidget(self.mw.auto_fix_button)
        header_grid.addWidget(
            editor_action_group,
            0,
            3,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        # Row 2: chapter assignment.
        self.mw.chapter_select_label = NavigableLabel("Chapter:")
        self.mw.chapter_select_label.setStyleSheet(
            "font-weight: bold; color: #6a1b9a; font-size: 13px;"
        )
        self.mw.chapter_select_label.setToolTip(
            "Double-click to open this row in its virtual Chapter."
        )
        self.mw.chapter_select_label.setFixedWidth(compact_label_width)
        header_grid.addWidget(self.mw.chapter_select_label, 1, 0)
        self.mw.chapter_combobox = QComboBox()
        self.mw.chapter_combobox.setFixedWidth(compact_context_width)
        self.mw.chapter_combobox.setFixedHeight(compact_context_height)
        self.mw.chapter_combobox.setStyleSheet("font-size: 13px;")
        self.mw.chapter_combobox.setToolTip(
            "Assign this row to a Story chapter or scene, including rows without a script link."
        )
        self.mw.chapter_combobox.story_structure_id = None
        # Compatibility alias for navigation code and older UI tests.
        self.mw.chapter_value_label = self.mw.chapter_combobox
        header_grid.addWidget(self.mw.chapter_combobox, 1, 1)

        self.mw.speaker_label = QLabel("")
        self.mw.speaker_label.setObjectName("speaker_label")
        self.mw.speaker_label.setStyleSheet("QLabel#speaker_label { font-weight: bold; color: #2e7d32; font-size: 12px; padding-left: 5px; }")
        self.mw.speaker_label.setToolTip("Speaker for the current line mapped from MemePalace")
        self.mw.speaker_label.setVisible(False)

        # Row 3: speaker on the left, all translation formatting on the right.
        self.mw.speaker_select_label = NavigableLabel("Speaker:")
        self.mw.speaker_select_label.setStyleSheet("font-weight: bold; color: #1565c0; font-size: 13px;")
        self.mw.speaker_select_label.setToolTip(
            "Double-click to open this row in its virtual Speaker or Item block."
        )
        self.mw.speaker_select_label.setFixedWidth(compact_label_width)
        header_grid.addWidget(self.mw.speaker_select_label, 2, 0)
        self.mw.speaker_combobox = QComboBox()
        self.mw.speaker_combobox.setEditable(True)
        self.mw.speaker_combobox.setToolTip("Select or type speaker name for this string")
        self.mw.speaker_combobox.setFixedWidth(compact_context_width)
        self.mw.speaker_combobox.setFixedHeight(compact_context_height)
        self.mw.speaker_combobox.setStyleSheet("font-size: 13px;")
        self.mw.speaker_combobox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header_grid.addWidget(self.mw.speaker_combobox, 2, 1)

        formatting_group = QWidget()
        formatting_layout = QHBoxLayout(formatting_group)
        formatting_layout.setContentsMargins(0, 0, 0, 0)
        formatting_layout.setSpacing(4)
        font_label = QLabel("Font:")
        formatting_layout.addWidget(font_label)
        self.mw.font_combobox = QComboBox()
        self.mw.font_combobox.setFixedWidth(170)
        self.mw.font_combobox.setFixedHeight(control_height)
        formatting_layout.addWidget(self.mw.font_combobox)
        formatting_layout.addSpacing(12)

        formatting_layout.addWidget(QLabel("Max-width:"))
        self.mw.width_spinbox = QSpinBox()
        self.mw.width_spinbox.setRange(0, 10000)
        self.mw.width_spinbox.setToolTip("Set custom width for this string (0 = use plugin default)")
        self.mw.width_spinbox.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mw.width_spinbox.setFixedHeight(control_height)
        self.mw.width_spinbox.setFixedWidth(110)
        
        def show_width_context_menu(pos):
            """Show width context menu."""
            menu = QMenu()
            reset_action = menu.addAction("Reset to Plugin Default")
            set_from_original_action = menu.addAction("Set Width from Original")
            action = menu.exec(self.mw.width_spinbox.mapToGlobal(pos))
            if action == reset_action:
                block_idx = self.mw.data_store.physical_block_idx
                string_idx = self.mw.data_store.current_string_idx
                handler = getattr(self.mw, "string_settings_handler", None)
                if handler is not None and block_idx != -1 and string_idx != -1:
                    default_width = handler.get_default_width_for_string(block_idx, string_idx)
                else:
                    default_width = getattr(self.mw, 'game_dialog_max_width_pixels', 300)
                self.mw.width_spinbox.setValue(default_width)
            elif action == set_from_original_action:
                handler = getattr(self.mw, "string_settings_handler", None)
                if handler is not None:
                    handler.copy_original_width_to_editor()

        self.mw.width_spinbox.customContextMenuRequested.connect(show_width_context_menu)
        formatting_layout.addWidget(self.mw.width_spinbox)
        
        self.mw.apply_width_button = QPushButton("Apply")
        self.mw.apply_width_button.setEnabled(False)
        self.mw.apply_width_button.setFixedHeight(control_height)
        self.mw.apply_width_button.setFixedWidth(72)
        formatting_layout.addWidget(self.mw.apply_width_button)
        header_grid.addWidget(
            formatting_group,
            2,
            3,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        header_grid.setColumnStretch(2, 1)
        right_header_layout.addLayout(header_grid)

        editable_title_layout = QHBoxLayout()
        editable_title_layout.setContentsMargins(0, 0, 0, 0)
        editable_title_layout.addWidget(self._create_editor_title_label("Editable"))
        editable_title_layout.addStretch(1)
        right_header_layout.addLayout(editable_title_layout)
        bottom_right_layout.addWidget(self.mw.right_header_container)

        # Sync heights using event filter
        from PyQt6.QtCore import QObject, QEvent
        class HeaderSyncFilter(QObject):
            """Header sync filter implementation."""
            def __init__(self, source, target):
                """Initialize a new instance."""
                super().__init__(source)
                self.source = source
                self.target = target
                if self.source.height() > 0:
                    self.target.setFixedHeight(self.source.height())

            def eventFilter(self, obj, event):
                """Eventfilter."""
                if obj is self.source and event.type() == QEvent.Type.Resize:
                    self.target.setFixedHeight(self.source.height())
                return super().eventFilter(obj, event)

        self.mw.header_sync_filter = HeaderSyncFilter(self.mw.right_header_container, self.mw.left_header_container)
        self.mw.right_header_container.installEventFilter(self.mw.header_sync_filter)

        self.mw.edited_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.edited_text_edit.setObjectName("edited_text_edit")
        
        # BFN Visual Preview Widget
        from ui.components.bfn_preview_widget import BfnPreviewWidget
        self.mw.bfn_preview_widget = BfnPreviewWidget(self.mw)
        
        # Vertical splitter for editor and visual preview
        self.mw.editor_preview_splitter = QSplitter(Qt.Orientation.Vertical)
        self.mw.editor_preview_splitter.addWidget(self.mw.edited_text_edit)
        self.mw.editor_preview_splitter.addWidget(self.mw.bfn_preview_widget)
        self.mw.editor_preview_splitter.setSizes([350, 130])
        
        bottom_right_layout.addWidget(self.mw.editor_preview_splitter)
        
        self.mw.bottom_right_splitter.addWidget(bottom_right_panel)

    def _create_header_button(self, icon, tooltip, text=None):
        """Internal helper to create header button."""
        btn = QPushButton()
        if icon: btn.setIcon(icon)
        elif text: btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        return btn

    def _create_editor_title_label(self, text):
        """Create the lightweight standalone title used immediately above an editor."""
        label = QLabel(text)
        label.setStyleSheet("QLabel { color: #000000; font-size: 11px; padding: 1px 0; }")
        return label

    def _create_toolbar_button(self, text, tooltip):
        """Internal helper to create toolbar button."""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setEnabled(False)
        return btn
