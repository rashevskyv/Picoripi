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
        self._build_edited_panel()
        
        self.mw.right_splitter.addWidget(self.mw.bottom_right_splitter)
        self.mw.right_splitter.setSizes([150, 450])
        self.mw.bottom_right_splitter.setSizes([400, 400])

    def _build_original_panel(self):
        bottom_left_panel = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_panel)

        original_header_layout = QHBoxLayout()
        original_header_layout.addWidget(QLabel("Original (Read-Only):"))
        self.mw.original_width_label = QLabel("")
        original_header_layout.addWidget(self.mw.original_width_label)
        original_header_layout.addStretch(1)
        bottom_left_layout.addLayout(original_header_layout)

        self.mw.original_editor_top_spacer = QWidget()
        self.mw.original_editor_top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mw.original_editor_top_spacer.setFixedHeight(0)
        bottom_left_layout.addWidget(self.mw.original_editor_top_spacer)

        self.mw.original_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.original_text_edit.setObjectName("original_text_edit")
        self.mw.original_text_edit.setReadOnly(True)
        self.mw.original_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        bottom_left_layout.addWidget(self.mw.original_text_edit)
        self.mw.bottom_right_splitter.addWidget(bottom_left_panel)

    def _build_edited_panel(self):
        bottom_right_panel = QWidget()
        bottom_right_layout = QVBoxLayout(bottom_right_panel)
        
        # Tools Header
        editable_text_header_layout = QHBoxLayout()
        editable_text_header_layout.addWidget(QLabel("Editable Text:"))
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
        editable_text_header_layout.addWidget(self.mw.auto_fix_button)

        from PyQt5.QtGui import QIcon
        self.mw.help_button = QPushButton()
        self.mw.help_button.setIcon(QIcon.fromTheme("input-keyboard", self.style.standardIcon(QStyle.SP_DialogHelpButton)))
        self.mw.help_button.setToolTip("View Shortcuts & Help (F1)")
        editable_text_header_layout.addWidget(self.mw.help_button)

        self.mw.revert_string_button = QPushButton()
        self.mw.revert_string_button.setIcon(self.style.standardIcon(QStyle.SP_ArrowBack))
        self.mw.revert_string_button.setToolTip("Revert current string to original file content")
        editable_text_header_layout.addWidget(self.mw.revert_string_button)
        
        bottom_right_layout.addLayout(editable_text_header_layout)

        # String Settings Panel
        string_settings_panel = QWidget()
        string_settings_layout = QHBoxLayout(string_settings_panel)
        string_settings_layout.setContentsMargins(0, 5, 0, 5)

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
                self.mw.width_spinbox.setValue(getattr(self.mw, 'line_width_warning_threshold_pixels', 208))

        self.mw.width_spinbox.customContextMenuRequested.connect(show_width_context_menu)
        string_settings_layout.addWidget(self.mw.width_spinbox)
        
        self.mw.apply_width_button = QPushButton("Apply")
        self.mw.apply_width_button.setEnabled(False)
        string_settings_layout.addWidget(self.mw.apply_width_button)
        string_settings_layout.addStretch(1)
        bottom_right_layout.addWidget(string_settings_panel)

        # Sync top spacer
        header_heights = [
            self.mw.ai_translate_button.sizeHint().height(),
            self.mw.ai_variation_button.sizeHint().height(),
            self.mw.navigate_up_button.sizeHint().height(),
            self.mw.navigate_down_button.sizeHint().height(),
            self.mw.auto_fix_button.sizeHint().height(),
        ]
        placeholder_height = max(header_heights) + string_settings_panel.sizeHint().height()
        self.mw.original_editor_top_spacer.setFixedHeight(placeholder_height)

        self.mw.edited_text_edit = LineNumberedTextEdit(self.mw)
        self.mw.edited_text_edit.setObjectName("edited_text_edit")
        bottom_right_layout.addWidget(self.mw.edited_text_edit)
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
