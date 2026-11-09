"""Reusable prompt editor dialog for AI requests."""
from __future__ import annotations
from typing import Optional, Tuple

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
        notes: Optional[str] = None,
    ) -> None:
        """``notes``: the row's saved notes; ``None`` hides the Notes field (the request is not for one row)."""
        super().__init__(parent)
        self.setWindowTitle(title or tr("Prompt Editor"))
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
            self._labelled(tr("System Prompt:"), self._system_edit)
        )

        self._user_edit = QPlainTextEdit(self)
        self._user_edit.setPlainText(user_prompt or "")
        self._splitter.addWidget(self._labelled(tr("User Prompt:"), self._user_edit))

        self._notes_edit: Optional[QPlainTextEdit] = None
        if notes is None:
            self._splitter.setSizes([200, 400])
        else:
            self._notes_edit = QPlainTextEdit(self)
            self._notes_edit.setPlainText(notes)
            self._notes_edit.setPlaceholderText(tr(
                "What to change in the translation of this row. "
                "Saved with the project and sent with every AI request for this row."
            ))
            self._splitter.addWidget(self._labelled(tr("Notes:"), self._notes_edit))
            self._splitter.setSizes([180, 320, 100])

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

    def notes(self) -> str:
        """The Notes field as typed (empty when the field is hidden)."""
        return self._notes_edit.toPlainText().strip() if self._notes_edit is not None else ""
