from typing import List, Optional, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QLineEdit, QLabel, QScrollArea, QWidget, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.glossary_manager import GlossaryManager
from core.i18n import tr


class CategorySelectionDialog(QDialog):
    """Dialog for choosing and adding categories for glossary AI classification."""
    def __init__(self, parent, categories: List[str]):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(tr('Choose Glossary Categories'))
        self.resize(360, 400)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr('Select categories to organize your glossary:'), self))
        
        # Scroll area for checkboxes
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        self.checkboxes = []
        for cat in categories:
            cb = QCheckBox(cat, self)
            cb.setChecked(True)
            scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        # Custom category input
        layout.addWidget(QLabel(tr('Add custom categories (comma-separated):'), self))
        self.custom_input = QLineEdit(self)
        self.custom_input.setPlaceholderText(tr('e.g. Items, Weapons, Spells'))
        layout.addWidget(self.custom_input)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_selected_categories(self) -> List[str]:
        """Get the selected categories."""
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        custom_text = self.custom_input.text().strip()
        if custom_text:
            for item in custom_text.split(","):
                clean_item = item.strip()
                if clean_item and clean_item not in selected:
                    selected.append(clean_item)
        return selected


class GlossaryOccurrenceWorker(QThread):
    """Glossary occurrence worker implementation."""
    finished_with_result = pyqtSignal(dict)

    def __init__(self, glossary_manager: GlossaryManager, data_source: list, parent: Optional[Any] = None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.glossary_manager = glossary_manager
        self.data_source = data_source

    def run(self):
        """Run."""
        try:
            occurrence_map = self.glossary_manager.build_occurrence_index(
                self.data_source,
                is_cancelled=self.isInterruptionRequested
            )
            if self.isInterruptionRequested():
                return
            self.finished_with_result.emit(occurrence_map)
        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"GlossaryOccurrenceWorker failed: {e}", exc_info=True)
            if not self.isInterruptionRequested():
                self.finished_with_result.emit({})

