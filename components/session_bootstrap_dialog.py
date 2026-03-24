# --- START OF FILE components/session_bootstrap_dialog.py ---
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)


class SessionBootstrapDialog(QDialog):
    """Dialog that shows the system prompt and collects optional session instructions."""

    def __init__(self, parent, system_prompt: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Translation – Start Session")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        intro_label = QLabel(
            "Review the system prompt before starting the dialogue. "
            "Add your own instructions for the entire session if needed."
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        system_view = QPlainTextEdit(self)
        system_view.setReadOnly(True)
        system_view.setPlainText(system_prompt)
        system_view.setMinimumHeight(240)
        layout.addWidget(system_view)

        instructions_label = QLabel("Additional Instructions (optional):", self)
        instructions_label.setWordWrap(True)
        layout.addWidget(instructions_label)

        self._instructions_edit = QPlainTextEdit(self)
        self._instructions_edit.setPlaceholderText("Write what should be considered throughout the session...")
        self._instructions_edit.setMinimumHeight(120)
        layout.addWidget(self._instructions_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_instructions(self) -> str:
        return self._instructions_edit.toPlainText().strip()
