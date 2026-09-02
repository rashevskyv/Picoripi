"""Reusable prompt editor dialog for AI requests."""
from __future__ import annotations
from typing import Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPlainTextEdit,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QSplitter,
    QWidget,
)
from core.i18n import tr

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
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(title or "Prompt Editor")
        self.resize(900, 600)

        self._allow_save = allow_save

        layout = QVBoxLayout(self)

        # The two prompts differ wildly in length from request to request, so a
        # fixed split is wrong for most of them: let the reader give whichever
        # one they are studying the room.
        self._splitter = QSplitter(Qt.Orientation.Vertical, self)
        layout.addWidget(self._splitter, 1)

        self._system_edit = QPlainTextEdit(self)
        self._system_edit.setPlainText(system_prompt or "")
        self._splitter.addWidget(
            self._labelled("System Prompt:", self._system_edit)
        )

        self._user_edit = QPlainTextEdit(self)
        self._user_edit.setPlainText(user_prompt or "")
        self._splitter.addWidget(self._labelled("User Prompt:", self._user_edit))
        self._splitter.setSizes([200, 400])

        options_row = QHBoxLayout()
        options_row.addStretch(1)
        self._save_checkbox = QCheckBox(tr('Save changes to prompt template'), self)
        self._save_checkbox.setVisible(allow_save)
        options_row.addWidget(self._save_checkbox)
        layout.addLayout(options_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _labelled(self, text: str, editor: QPlainTextEdit) -> QWidget:
        """Pair a label with its editor so the splitter moves them together."""
        pane = QWidget(self)
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        pane_layout.addWidget(QLabel(text, pane))
        pane_layout.addWidget(editor, 1)
        return pane

    def get_user_inputs(self) -> Tuple[str, str, bool]:
        """Return edited system prompt, user prompt, and save flag."""
        return (
            self._system_edit.toPlainText(),
            self._user_edit.toPlainText(),
            bool(self._save_checkbox.isChecked()) if self._allow_save else False,
        )
