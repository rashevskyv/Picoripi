from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QWidget
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from typing import Dict, Any, Set

class AutofixSelectionDialog(QDialog):
    def __init__(self, problem_definitions: Dict[str, Dict[str, Any]], active_autofixes: Dict[str, bool], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selective Auto-Fix")
        self.resize(450, 400)
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.problem_definitions = problem_definitions
        self.active_autofixes = active_autofixes
        self.checkboxes: Dict[str, QCheckBox] = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title/Description label
        desc_label = QLabel("Select which issues to automatically fix across all strings in the project:")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Scroll area for problem checkboxes
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
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

        # Selection helpers
        helper_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_none)
        
        helper_layout.addWidget(select_all_btn)
        helper_layout.addWidget(select_none_btn)
        helper_layout.addStretch(1)
        layout.addLayout(helper_layout)

        # Dialog buttons (Fix / Cancel)
        btn_layout = QHBoxLayout()
        fix_btn = QPushButton("Fix All")
        fix_btn.setDefault(True)
        fix_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(fix_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def _select_none(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def get_selected_problems(self) -> Set[str]:
        return {pid for pid, cb in self.checkboxes.items() if cb.isChecked()}
