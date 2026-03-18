# components/glossary_edit_dialog.py
"""
Dialog for editing a single glossary entry (term → translation + notes).
Supports optional AI Fill and AI Notes Variation actions.
"""
from typing import Callable, Optional, Tuple

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QHBoxLayout, QPushButton, QDialogButtonBox, QWidget,
)
from PyQt5.QtCore import Qt, QObject, QEvent


class ReturnToAcceptFilter(QObject):
    """Convert plain Return/Enter key presses into dialog acceptance."""

    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if not (modifiers & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self._dialog.accept()
                return True
        return super().eventFilter(obj, event)


class GlossaryEditDialog(QDialog):
    """
    Simple dialog for editing a glossary entry.

    Shows term, optional context line, translation field (with optional AI Fill button),
    and notes field (with optional AI Variations button).
    """

    def __init__(
        self,
        parent: QWidget,
        term: str,
        translation: str = "",
        notes: str = "",
        context: Optional[str] = None,
        ai_assist_callback: Optional[Callable[[], None]] = None,
        notes_variation_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Glossary Entry")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel(f"<b>Term:</b> {term}"))
        if context:
            form_layout.addWidget(QLabel(f"<b>Context:</b> <i>{context}</i>"))

        # --- Translation row ---
        translation_layout = QHBoxLayout()
        translation_layout.addWidget(QLabel("Translation:"))
        translation_layout.addStretch(1)
        self._ai_button_default_text = "AI Fill"
        self._ai_button = QPushButton(self._ai_button_default_text, self)
        self._ai_button.setVisible(ai_assist_callback is not None)
        if ai_assist_callback:
            self._ai_button.clicked.connect(ai_assist_callback)
        translation_layout.addWidget(self._ai_button)
        form_layout.addLayout(translation_layout)

        self._translation_edit = QLineEdit(self)
        self._translation_edit.setText(translation)
        self._translation_edit.installEventFilter(ReturnToAcceptFilter(self))
        form_layout.addWidget(self._translation_edit)

        # --- Notes row ---
        notes_header_layout = QHBoxLayout()
        notes_header_layout.addWidget(QLabel("Notes:"))
        notes_header_layout.addStretch(1)
        self._notes_variation_default_text = "AI Variations"
        self._notes_variation_button = QPushButton(self._notes_variation_default_text, self)
        self._notes_variation_button.setVisible(notes_variation_callback is not None)
        if notes_variation_callback:
            self._notes_variation_button.clicked.connect(notes_variation_callback)
        notes_header_layout.addWidget(self._notes_variation_button)
        form_layout.addLayout(notes_header_layout)

        self._notes_edit = QPlainTextEdit(self)
        self._notes_edit.setMinimumHeight(80)
        self._notes_edit.setPlainText(notes)
        form_layout.addWidget(self._notes_edit)

        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_values(self, translation: str, notes: str) -> None:
        self._translation_edit.setText(translation)
        self._notes_edit.setPlainText(notes)

    def get_values(self) -> Tuple[str, str]:
        return (
            self._translation_edit.text().strip(),
            self._notes_edit.toPlainText().strip(),
        )

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_button.setEnabled(not busy)
        if busy:
            self._ai_button.setText(f"{self._ai_button_default_text} (working...)")
        else:
            self._ai_button.setText(self._ai_button_default_text)

        self._notes_variation_button.setEnabled(not busy)
        if busy:
            self._notes_variation_button.setText(f"{self._notes_variation_default_text} (working...)")
        else:
            self._notes_variation_button.setText(self._notes_variation_default_text)
