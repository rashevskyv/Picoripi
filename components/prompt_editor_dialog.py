"""Reusable prompt editor dialog for AI requests."""
from __future__ import annotations
from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPlainTextEdit,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QCheckBox,
)
from PyQt5.QtCore import Qt

class PromptEditorDialog(QDialog):
    """Allow users to preview/edit AI system+user prompts before sending."""

    def __init__(
        self,
        *,
        parent=None,
        title: str,
        system_prompt: str,
        user_prompt: str,
        allow_save: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or "Prompt Editor")
        self.resize(900, 600)

        self._allow_save = allow_save

        layout = QVBoxLayout(self)

        system_label_row = QHBoxLayout()
        system_label_row.addWidget(QLabel("System Prompt:", self))
        layout.addLayout(system_label_row)

        self._system_edit = QPlainTextEdit(self)
        self._system_edit.setPlainText(system_prompt or "")
        layout.addWidget(self._system_edit, 1)

        user_label_row = QHBoxLayout()
        user_label_row.addWidget(QLabel("User Prompt:", self))
        layout.addLayout(user_label_row)

        self._user_edit = QPlainTextEdit(self)
        self._user_edit.setPlainText(user_prompt or "")
        layout.addWidget(self._user_edit, 2)

        options_row = QHBoxLayout()
        options_row.addStretch(1)
        self._save_checkbox = QCheckBox("Save changes to prompt template", self)
        self._save_checkbox.setVisible(allow_save)
        options_row.addWidget(self._save_checkbox)
        layout.addLayout(options_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_user_inputs(self) -> Tuple[str, str, bool]:
        """Return edited system prompt, user prompt, and save flag."""
        return (
            self._system_edit.toPlainText(),
            self._user_edit.toPlainText(),
            bool(self._save_checkbox.isChecked()) if self._allow_save else False,
        )
