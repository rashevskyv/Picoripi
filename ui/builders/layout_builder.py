from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QStyle, QSpacerItem, QSizePolicy, QComboBox, QSpinBox, QMenu, QCheckBox
)
from PyQt5.QtCore import Qt
from pathlib import Path
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.custom_tree_widget import CustomTreeWidget

class LayoutBuilder:
    def __init__(self, main_window):
        self.mw = main_window
        self.style = main_window.style()

    def build(self):
        central_widget = QWidget()
        self.mw.setCentralWidget(central_widget)
        self.mw.main_vertical_layout = QVBoxLayout(central_widget)
        
        self.mw.main_splitter = QSplitter(Qt.Horizontal)
        
        self._build_left_panel()
        self._build_right_panel()
        
        self.mw.main_splitter.addWidget(self.left_panel)
        self.mw.main_splitter.addWidget(self.mw.right_splitter)
        self.mw.main_splitter.setSizes([200, 800])

        self.mw.main_vertical_layout.addWidget(self.mw.main_splitter)

    def _build_left_panel(self):
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Block Header
        block_header_layout = QHBoxLayout()
        block_header_layout.addWidget(QLabel("Blocks (double-click to rename):"))
        block_header_layout.addStretch()

        self.mw.add_folder_button = self._create_header_button(self.style.standardIcon(QStyle.SP_FileDialogNewFolder), 'Create new virtual folder')
        self.mw.add_folder_button.setEnabled(False)
        block_header_layout.addWidget(self.mw.add_folder_button)

        self.mw.expand_all_button = self._create_header_button(self.style.standardIcon(QStyle.SP_TitleBarUnshadeButton), 'Expand all folders', '⇊')
        block_header_layout.addWidget(self.mw.expand_all_button)

        self.mw.collapse_all_button = self._create_header_button(self.style.standardIcon(QStyle.SP_TitleBarShadeButton), 'Collapse all folders', '⇈')
        block_header_layout.addWidget(self.mw.collapse_all_button)

        left_layout.addLayout(block_header_layout)

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
        self.mw.right_splitter = QSplitter(Qt.Vertical)

        # Top Right (Preview)
        top_right_panel = QWidget()
        top_right_layout = QVBoxLayout(top_right_panel)
        
        preview_header_layout = QHBoxLayout()
        preview_header_layout.setContentsMargins(0, 0, 8, 0)
        preview_header_layout.addWidget(QLabel("Strings in block (click line to select):"))
        preview_header_layout.addStretch()
        
        self.mw.highlight_categorized_checkbox = QCheckBox("Highlight moved")
        self.mw.highlight_categorized_checkbox.setToolTip("Highlight strings in the parent block that have already been moved to a virtual block (category). Helps you see what's left to organize.")
        self.mw.highlight_categorized_checkbox.setCursor(Qt.PointingHandCursor)
        self.mw.highlight_categorized_checkbox.hide()
        preview_header_layout.addWidget(self.mw.highlight_categorized_checkbox)
        
        preview_header_layout.addSpacing(15)
        
        self.mw.hide_categorized_checkbox = QCheckBox("Hide moved")
        self.mw.hide_categorized_checkbox.setToolTip("Filter out strings from the parent block view if they are already present in any virtual block. Useful for focused organizing.")
        self.mw.hide_categorized_checkbox.setCursor(Qt.PointingHandCursor)
        self.mw.hide_categorized_checkbox.hide()
        preview_header_layout.addWidget(self.mw.hide_categorized_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.hide_empty_strings_checkbox = QCheckBox("Hide empty strings")
        self.mw.hide_empty_strings_checkbox.setToolTip("Collapse consecutive empty strings into a single placeholder.")
        self.mw.hide_empty_strings_checkbox.setCursor(Qt.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.hide_empty_strings_checkbox)
        
        preview_header_layout.addSpacing(15)
        self.mw.hide_translated_checkbox = QCheckBox("Hide translated")
        self.mw.hide_translated_checkbox.setToolTip("Hide strings that have already been translated.")
        self.mw.hide_translated_checkbox.setCursor(Qt.PointingHandCursor)
        preview_header_layout.addWidget(self.mw.hide_translated_checkbox)
        
        top_right_layout.addLayout(preview_header_layout)
        self.mw.preview_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.preview_text_edit.setObjectName("preview_text_edit")
        self.mw.preview_text_edit.setReadOnly(True)
        self.mw.preview_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        top_right_layout.addWidget(self.mw.preview_text_edit)
        self.mw.right_splitter.addWidget(top_right_panel)

        # Bottom Right (Editors)
        self.mw.bottom_right_splitter = QSplitter(Qt.Horizontal)
        self._build_original_panel()
        self._build_middle_panel()
        self._build_edited_panel()
        
        self.mw.right_splitter.addWidget(self.mw.bottom_right_splitter)
        self.mw.right_splitter.setSizes([150, 450])
        self.mw.bottom_right_splitter.setSizes([380, 40, 380])

    def _build_original_panel(self):
        bottom_left_panel = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_panel)

        self.mw.left_header_container = QWidget()
        left_header_layout = QVBoxLayout(self.mw.left_header_container)
        left_header_layout.setContentsMargins(0, 0, 0, 0)
        left_header_layout.setSpacing(0)

        original_header_layout = QHBoxLayout()
        original_header_layout.addWidget(QLabel("Original (Read-Only):"))
        self.mw.original_width_label = QLabel("")
        original_header_layout.addWidget(self.mw.original_width_label)
        original_header_layout.addStretch(1)
        
        self.mw.hide_original_tags_checkbox = QCheckBox("Hide tags")
        self.mw.hide_original_tags_checkbox.setToolTip("Hide all tags except forced aliases and tags with custom width in original text.")
        self.mw.hide_original_tags_checkbox.setCursor(Qt.PointingHandCursor)
        original_header_layout.addWidget(self.mw.hide_original_tags_checkbox)
        
        left_header_layout.addLayout(original_header_layout)
        left_header_layout.addStretch(1)
        bottom_left_layout.addWidget(self.mw.left_header_container)

        self.mw.original_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.original_text_edit.setObjectName("original_text_edit")
        self.mw.original_text_edit.setReadOnly(True)
        self.mw.original_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        bottom_left_layout.addWidget(self.mw.original_text_edit)
        self.mw.bottom_right_splitter.addWidget(bottom_left_panel)

    def _build_middle_panel(self):
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        
        middle_layout.addSpacing(92)
        
        from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
        
        # Create a dynamic beautiful icon for Inspect Story Context with letter 'S'
        pixmap_s = QPixmap(32, 32)
        pixmap_s.fill(Qt.transparent)
        painter_s = QPainter(pixmap_s)
        painter_s.setRenderHint(QPainter.Antialiasing, True)
        painter_s.setPen(QColor("#0078d7")) # Classic Microsoft Blue
        font_s = QFont("Arial", 22, QFont.Bold)
        painter_s.setFont(font_s)
        painter_s.drawText(pixmap_s.rect(), Qt.AlignCenter, "S")
        painter_s.end()
        story_icon = QIcon(pixmap_s)
        
        # Create a dynamic beautiful icon for Restore Translation (document sheet with a blue arrow pointing right)
        pixmap_r = QPixmap(32, 32)
        pixmap_r.fill(Qt.transparent)
        painter_r = QPainter(pixmap_r)
        painter_r.setRenderHint(QPainter.Antialiasing, True)
        
        # Draw document sheet (sheet of paper)
        painter_r.setPen(QColor("#7f8c8d")) # Gray outline
        painter_r.setBrush(QColor("#ffffff")) # White filled paper
        
        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
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
        painter_r.setPen(Qt.NoPen)
        painter_r.setBrush(QColor("#0078d7"))
        painter_r.drawPolygon(arrow_head)
        
        painter_r.end()
        restore_icon = QIcon(pixmap_r)

        self.mw.revert_string_button = QPushButton()
        self.mw.revert_string_button.setIcon(self.style.standardIcon(QStyle.SP_ArrowForward))
        self.mw.revert_string_button.setToolTip("Revert current string to original file content")
        self.mw.revert_string_button.setFixedWidth(30)
        self.mw.revert_string_button.setCursor(Qt.PointingHandCursor)
        self.mw.revert_string_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.revert_string_button, 0, Qt.AlignCenter)
        
        middle_layout.addSpacing(6)
        
        self.mw.restore_translation_button = QPushButton()
        self.mw.restore_translation_button.setIcon(restore_icon)
        self.mw.restore_translation_button.setToolTip("Restore last saved/reverted translation (Ctrl+Shift+T)")
        self.mw.restore_translation_button.setFixedWidth(30)
        self.mw.restore_translation_button.setCursor(Qt.PointingHandCursor)
        self.mw.restore_translation_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.restore_translation_button, 0, Qt.AlignCenter)
        
        middle_layout.addSpacing(6)
        
        self.mw.inspect_story_context_button = QPushButton()
        self.mw.inspect_story_context_button.setIcon(story_icon)
        self.mw.inspect_story_context_button.setToolTip('Show timeline, speaker and visual context for the selected row from MemePalace (Ctrl+I)')
        self.mw.inspect_story_context_button.setFixedWidth(30)
        self.mw.inspect_story_context_button.setCursor(Qt.PointingHandCursor)
        self.mw.inspect_story_context_button.setStyleSheet("QPushButton { padding: 4px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9; } QPushButton:hover { background-color: #e6e6e6; }")
        
        middle_layout.addWidget(self.mw.inspect_story_context_button, 0, Qt.AlignCenter)
        middle_layout.addStretch(1)
        
        middle_panel.setFixedWidth(34)
        self.mw.bottom_right_splitter.addWidget(middle_panel)

    def _build_edited_panel(self):
        bottom_right_panel = QWidget()
        bottom_right_layout = QVBoxLayout(bottom_right_panel)
        
        self.mw.right_header_container = QWidget()
        right_header_layout = QVBoxLayout(self.mw.right_header_container)
        right_header_layout.setContentsMargins(0, 0, 0, 0)
        right_header_layout.setSpacing(0)

        # Tools Header
        editable_text_header_layout = QHBoxLayout()
        editable_text_header_layout.addWidget(QLabel("Editable Text:"))
        editable_text_header_layout.addSpacing(10)
        
        self.mw.hide_translation_tags_checkbox = QCheckBox("Hide tags")
        self.mw.hide_translation_tags_checkbox.setToolTip("Hide all tags except forced aliases and tags with custom width in translation.")
        self.mw.hide_translation_tags_checkbox.setCursor(Qt.PointingHandCursor)
        editable_text_header_layout.addWidget(self.mw.hide_translation_tags_checkbox)
        
        editable_text_header_layout.addStretch(1)
        
        self.mw.navigate_down_button = QPushButton()
        self.mw.navigate_down_button.setIcon(self.style.standardIcon(QStyle.SP_ArrowDown))
        self.mw.navigate_down_button.setToolTip("Navigate to next problem string (Ctrl+Down)")
        editable_text_header_layout.addWidget(self.mw.navigate_down_button)

        self.mw.navigate_up_button = QPushButton()
        self.mw.navigate_up_button.setIcon(self.style.standardIcon(QStyle.SP_ArrowUp))
        self.mw.navigate_up_button.setToolTip("Navigate to previous problem string (Ctrl+Up)")
        editable_text_header_layout.addWidget(self.mw.navigate_up_button)

        self.mw.ai_translate_button = QPushButton('AI Translate')
        editable_text_header_layout.addWidget(self.mw.ai_translate_button)

        self.mw.ai_variation_button = QPushButton('AI Variation')
        editable_text_header_layout.addWidget(self.mw.ai_variation_button)

        self.mw.auto_fix_button = QPushButton('Auto-fix')
        self.mw.auto_fix_button.setToolTip("Automatically fix issues in the current string (Ctrl+Shift+A)")
        editable_text_header_layout.addWidget(self.mw.auto_fix_button)
        
        right_header_layout.addLayout(editable_text_header_layout)

        # String Settings Panel
        string_settings_panel = QWidget()
        string_settings_layout = QHBoxLayout(string_settings_panel)
        string_settings_layout.setContentsMargins(0, 5, 0, 5)

        self.mw.speaker_label = QLabel("")
        self.mw.speaker_label.setObjectName("speaker_label")
        self.mw.speaker_label.setStyleSheet("QLabel#speaker_label { font-weight: bold; color: #2e7d32; font-size: 12px; padding-left: 5px; }")
        self.mw.speaker_label.setToolTip("Speaker for the current line mapped from MemePalace")
        string_settings_layout.addWidget(self.mw.speaker_label)

        string_settings_layout.addStretch(1)
        string_settings_layout.addWidget(QLabel("Font:"))
        self.mw.font_combobox = QComboBox()
        string_settings_layout.addWidget(self.mw.font_combobox)

        string_settings_layout.addWidget(QLabel("Width:"))
        self.mw.width_spinbox = QSpinBox()
        self.mw.width_spinbox.setRange(0, 10000)
        self.mw.width_spinbox.setToolTip("Set custom width for this string (0 = use plugin default)")
        self.mw.width_spinbox.setContextMenuPolicy(Qt.CustomContextMenu)
        
        def show_width_context_menu(pos):
            menu = QMenu()
            reset_action = menu.addAction("Reset to Plugin Default")
            action = menu.exec_(self.mw.width_spinbox.mapToGlobal(pos))
            if action == reset_action:
                self.mw.width_spinbox.setValue(getattr(self.mw, 'game_dialog_max_width_pixels', 300))

        self.mw.width_spinbox.customContextMenuRequested.connect(show_width_context_menu)
        string_settings_layout.addWidget(self.mw.width_spinbox)
        
        self.mw.apply_width_button = QPushButton("Apply")
        self.mw.apply_width_button.setEnabled(False)
        string_settings_layout.addWidget(self.mw.apply_width_button)
        right_header_layout.addWidget(string_settings_panel)
        bottom_right_layout.addWidget(self.mw.right_header_container)

        # Sync heights using event filter
        from PyQt5.QtCore import QObject, QEvent
        class HeaderSyncFilter(QObject):
            def __init__(self, source, target):
                super().__init__(source)
                self.source = source
                self.target = target
                if self.source.height() > 0:
                    self.target.setFixedHeight(self.source.height())

            def eventFilter(self, obj, event):
                if obj is self.source and event.type() == QEvent.Resize:
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
        self.mw.editor_preview_splitter = QSplitter(Qt.Vertical)
        self.mw.editor_preview_splitter.addWidget(self.mw.edited_text_edit)
        self.mw.editor_preview_splitter.addWidget(self.mw.bfn_preview_widget)
        self.mw.editor_preview_splitter.setSizes([350, 130])
        
        bottom_right_layout.addWidget(self.mw.editor_preview_splitter)
        
        self.mw.bottom_right_splitter.addWidget(bottom_right_panel)

    def _create_header_button(self, icon, tooltip, text=None):
        btn = QPushButton()
        if icon: btn.setIcon(icon)
        elif text: btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        return btn

    def _create_toolbar_button(self, text, tooltip):
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setEnabled(False)
        return btn
