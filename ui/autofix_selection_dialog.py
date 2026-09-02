from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QWidget
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from typing import Dict, Any, Set
from core.i18n import tr

class AutofixSelectionDialog(QDialog):
    """Dialog class for autofix selection."""
    def __init__(self, problem_definitions: Dict[str, Dict[str, Any]], active_autofixes: Dict[str, bool], parent=None):
        """Initialize a new instance."""
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self.setWindowTitle(tr('Selective Auto-Fix'))
        self.setMinimumWidth(450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.problem_definitions = problem_definitions
        self.active_autofixes = active_autofixes
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.mw = parent

        self._setup_ui()

    def _setup_ui(self):
        """Internal helper to setup ui."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title/Description label
        desc_label = QLabel(tr('Select which issues to automatically fix across all strings in the project:'))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Scroll area for problem checkboxes
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(8, 8, 8, 8)

        # Populate checkboxes
        sorted_problem_ids = sorted(
            self.problem_definitions.keys(),
            key=lambda pid: self.problem_definitions[pid].get("priority", 99)
        )

        for problem_id in sorted_problem_ids:
            definition = self.problem_definitions[problem_id]
            
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Color block indicator
            color_label = QLabel()
            color_label.setFixedSize(16, 16)
            problem_color = definition.get("color", QColor(200, 200, 200, 100))
            if isinstance(problem_color, QColor):
                r, g, b, a = problem_color.red(), problem_color.green(), problem_color.blue(), problem_color.alpha()
                color_label.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #888; border-radius: 2px;")
            else:
                color_label.setStyleSheet(f"background-color: {problem_color}; border: 1px solid #888; border-radius: 2px;")
            row_layout.addWidget(color_label)

            # Checkbox
            checkbox_name = definition.get("name", problem_id)
            checkbox = QCheckBox(checkbox_name)
            checkbox.setToolTip(definition.get("description", "No description available."))
            
            # Default to settings-based autofix state
            is_enabled = self.active_autofixes.get(problem_id, True)
            checkbox.setChecked(is_enabled)
            
            self.checkboxes[problem_id] = checkbox
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)

            scroll_layout.addWidget(row_widget)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Align sentences checkbox
        self.align_sentences_checkbox = QCheckBox(tr('Align sentences to original page layout'))
        self.align_sentences_checkbox.setToolTip(tr('Align translation sentences structure and pages matching original layout.'))
        if self.mw and hasattr(self.mw, 'align_sentences_to_original_pages'):
            self.align_sentences_checkbox.setChecked(self.mw.align_sentences_to_original_pages)
        else:
            self.align_sentences_checkbox.setChecked(False)
        layout.addWidget(self.align_sentences_checkbox)

        # Prevent adding empty lines checkbox
        self.prevent_empty_lines_checkbox = QCheckBox(tr('Prevent adding empty padding lines during pagination'))
        self.prevent_empty_lines_checkbox.setToolTip(tr('Do not add empty padding lines at the end of pages to fill remaining space.'))
        if self.mw and hasattr(self.mw, 'prevent_empty_lines_in_autofix'):
            self.prevent_empty_lines_checkbox.setChecked(self.mw.prevent_empty_lines_in_autofix)
        else:
            self.prevent_empty_lines_checkbox.setChecked(False)
        layout.addWidget(self.prevent_empty_lines_checkbox)

        # Selection helpers
        helper_layout = QHBoxLayout()
        select_all_btn = QPushButton(tr('Select All'))
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn = QPushButton(tr('Select None'))
        select_none_btn.clicked.connect(self._select_none)
        
        helper_layout.addWidget(select_all_btn)
        helper_layout.addWidget(select_none_btn)
        helper_layout.addStretch(1)
        layout.addLayout(helper_layout)

        # Dialog buttons (Fix / Cancel)
        btn_layout = QHBoxLayout()
        fix_btn = QPushButton(tr('Fix All'))
        fix_btn.setDefault(True)
        fix_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton(tr('Cancel'))
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(fix_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.adjustSize()

    def _select_all(self):
        """Internal helper to select all."""
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def _select_none(self):
        """Internal helper to select none."""
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def accept(self):
        """Accept."""
        if self.mw and hasattr(self.mw, 'align_sentences_to_original_pages'):
            self.mw.align_sentences_to_original_pages = self.align_sentences_checkbox.isChecked()
        if self.mw and hasattr(self.mw, 'prevent_empty_lines_in_autofix'):
            self.mw.prevent_empty_lines_in_autofix = self.prevent_empty_lines_checkbox.isChecked()
        if self.mw and hasattr(self.mw, 'autofix_enabled'):
            self.mw.autofix_enabled = {pid: cb.isChecked() for pid, cb in self.checkboxes.items()}
        if self.mw and hasattr(self.mw, 'settings_manager') and hasattr(self.mw.settings_manager, 'plugin_settings'):
            self.mw.settings_manager.plugin_settings.save()
        from utils.logging_utils import log_debug
        log_debug(
            f"[AutofixDialog] accept: prevent_empty={getattr(self.mw, 'prevent_empty_lines_in_autofix', 'N/A')}, "
            f"align={getattr(self.mw, 'align_sentences_to_original_pages', 'N/A')}, "
            f"autofix_enabled={getattr(self.mw, 'autofix_enabled', 'N/A')}"
        )
        super().accept()

    def get_selected_problems(self) -> Set[str]:
        """Get the selected problems."""
        return {pid for pid, cb in self.checkboxes.items() if cb.isChecked()}
