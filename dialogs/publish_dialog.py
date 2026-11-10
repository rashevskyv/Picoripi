"""The question before a build that can publish: publish to the translation repository, and what is new.

Non-modal: the caller shows it with ``open()`` and reads ``publish_description()`` in its ``accepted`` slot. An
empty description pushes without a Telegram message; an unchecked box builds without publishing.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout

from core.i18n import tr


class PublishDialog(QDialog):
    def __init__(self, parent, labels: List[str]):
        super().__init__(parent)
        self.setWindowTitle(tr("Publish translation"))
        layout = QVBoxLayout(self)
        self.publish_check = QCheckBox(tr("Publish the translation to the game's repository after the build"), self)
        self.publish_check.setChecked(True)
        layout.addWidget(self.publish_check)
        layout.addWidget(QLabel(tr("Publishes: {0}", ", ".join(labels)), self))
        layout.addWidget(QLabel(tr("What's new (posted to the Telegram thread; empty: push only, no message):"), self))
        self.description_edit = QPlainTextEdit(self)
        self.description_edit.setPlaceholderText(tr("For example: the Forest Haven dialogues are retranslated"))
        self.description_edit.setTabChangesFocus(True)
        layout.addWidget(self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.publish_check.toggled.connect(self.description_edit.setEnabled)
        self.description_edit.setFocus()

    def publish_description(self) -> Optional[str]:
        """The description to publish with ("" for push only), or None when the box is unchecked."""
        if not self.publish_check.isChecked():
            return None
        return self.description_edit.toPlainText().strip()
