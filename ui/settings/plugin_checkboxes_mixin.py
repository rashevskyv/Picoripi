from PyQt6.QtWidgets import (
    QFormLayout, QLabel, QWidget, QHBoxLayout, QCheckBox, QVBoxLayout, QGroupBox
)
from PyQt6.QtGui import QColor
from core.i18n import tr


class PluginCheckboxesMixin:
    """Detection and autofix checkbox subtabs."""

    def _populate_checkbox_subtab(self, tab, checkbox_dict, title):
        """Internal helper to populate checkbox subtab."""
        layout = QFormLayout(tab)
        layout.addRow(QLabel(title))

        if not self.mw.current_game_rules:
            layout.addRow(QLabel(tr('No game rules loaded.')))
            return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        if not problem_definitions:
            layout.addRow(QLabel(tr('No problem definitions found in current plugin.')))
            if self.mw.current_game_rules.get_display_name() == "Base Game (No Plugin)":
                layout.addRow(QLabel(tr('<i>(Running in fallback mode due to plugin load error)</i>')))
            return

        sorted_problem_ids = sorted(
            problem_definitions.keys(),
            key=lambda pid: problem_definitions[pid].get("priority", 99)
        )

        for problem_id in sorted_problem_ids:
            definition = problem_definitions[problem_id]

            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            color_label = QLabel(self)
            color_label.setFixedSize(20, 20)
            problem_color = definition.get("color", QColor(200, 200, 200, 100))
            if isinstance(problem_color, QColor):
                r, g, b, a = problem_color.red(), problem_color.green(), problem_color.blue(), problem_color.alpha()
                color_label.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: rgba({r}, {g}, {b}, {a})")
            else:
                color_label.setStyleSheet(f"background-color: {problem_color}; border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: {problem_color}")
            row_layout.addWidget(color_label)

            checkbox = QCheckBox(definition.get("name", problem_id), self)
            checkbox.setToolTip(definition.get("description", "No description available."))
            checkbox_dict[problem_id] = checkbox
            checkbox.stateChanged.connect(self.on_rules_changed)
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)

            layout.addRow(row_widget)

    def _setup_detection_subtab(self, tab):
        """Internal helper to setup detection subtab."""
        self._populate_checkbox_subtab(tab, self.detection_checkboxes, "Enable/disable problem detection:")

    def _setup_autofix_subtab(self, tab):
        """Internal helper to setup autofix subtab."""
        layout = QVBoxLayout(tab)
        
        general_group = QGroupBox(tr('General Auto-fix Settings'), tab)
        general_layout = QVBoxLayout(general_group)
        self.align_sentences_checkbox = QCheckBox(tr('Align sentences to original page layout'), general_group)
        self.align_sentences_checkbox.setToolTip(tr('Align translation sentences structure and pages matching original layout.'))
        self.align_sentences_checkbox.stateChanged.connect(self.on_rules_changed)
        general_layout.addWidget(self.align_sentences_checkbox)
        
        self.prevent_empty_lines_checkbox = QCheckBox(tr('Prevent adding empty padding lines during pagination'), general_group)
        self.prevent_empty_lines_checkbox.setToolTip(tr('Do not add empty padding lines at the end of pages to fill remaining space.'))
        self.prevent_empty_lines_checkbox.stateChanged.connect(self.on_rules_changed)
        general_layout.addWidget(self.prevent_empty_lines_checkbox)
        
        layout.addWidget(general_group)
        
        sub_widget = QWidget(tab)
        self._populate_checkbox_subtab(sub_widget, self.autofix_checkboxes, "Enable/disable auto-fix for specific problems:")
        layout.addWidget(sub_widget)
        layout.addStretch(1)
