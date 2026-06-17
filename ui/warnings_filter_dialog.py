# ui/warnings_filter_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QWidget
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from typing import Dict, Any, List

class WarningsFilterDialog(QDialog):
    """Dialog for selecting which warnings to filter by in the preview panel."""
    
    def __init__(self, problem_definitions: Dict[str, Dict[str, Any]], active_pids: List[str], selected_pids: List[str], parent=None):
        """
        Initialize the warnings filter dialog.
        
        :param problem_definitions: Dictionary containing all problems defined by the plugin
        :param active_pids: List of problem IDs currently active in detection settings
        :param selected_pids: List of problem IDs currently selected as warning filters
        """
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self.setWindowTitle("Filter by Warnings")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.problem_definitions = problem_definitions
        self.active_pids = active_pids
        self.selected_pids = selected_pids
        self.checkboxes: Dict[str, QCheckBox] = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Description
        desc_label = QLabel("Select warnings to filter strings by in the preview panel:")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Scroll Area for active warnings
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(8, 8, 8, 8)

        # Populate warning checkboxes (only those that are active in detection settings)
        sorted_active_pids = sorted(
            self.active_pids,
            key=lambda pid: self.problem_definitions.get(pid, {}).get("priority", 99)
        )

        if not sorted_active_pids:
            no_warnings_label = QLabel("No active warnings to select.\nEnable warnings in Settings first.")
            no_warnings_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
            no_warnings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(no_warnings_label)
        else:
            for pid in sorted_active_pids:
                definition = self.problem_definitions.get(pid, {})
                
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
                checkbox_name = definition.get("name", pid)
                checkbox = QCheckBox(checkbox_name)
                checkbox.setToolTip(definition.get("description", "No description available."))
                
                # Check state (if it is in selected_pids)
                checkbox.setChecked(pid in self.selected_pids)
                
                self.checkboxes[pid] = checkbox
                row_layout.addWidget(checkbox)
                row_layout.addStretch(1)

                scroll_layout.addWidget(row_widget)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Selection helpers
        if sorted_active_pids:
            helper_layout = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(self._select_all)
            select_none_btn = QPushButton("Select None")
            select_none_btn.clicked.connect(self._select_none)
            
            helper_layout.addWidget(select_all_btn)
            helper_layout.addWidget(select_none_btn)
            helper_layout.addStretch(1)
            layout.addLayout(helper_layout)

        # Dialog buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.adjustSize()

    def _select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def _select_none(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def get_selected_pids(self) -> List[str]:
        """Get the list of selected problem IDs."""
        return [pid for pid, cb in self.checkboxes.items() if cb.isChecked()]
