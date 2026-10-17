"""The emulator commands of the Project Manager: one line per platform. Run in emulator uses the line of its platform."""
from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from core.i18n import tr
from core.project_library.build import emulator_template_for
from core.project_library.registry import emulator_setting


class EmulatorDialog(QDialog):
    """Edit the command of each platform. ``changes()`` returns only the settings the user changed."""

    def __init__(self, parent, platforms: List[str], settings: Dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle(tr("Emulator commands"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr(
            "The command that starts your emulator for each platform. Write {path} where the built file or "
            "folder goes, for example \"C:\\Emu\\emu.exe\" {path}. An empty line means no command for that platform.")))
        form = QFormLayout()
        self._fields: Dict[str, QLineEdit] = {}
        self._before: Dict[str, str] = {}
        for platform in platforms:
            value = emulator_template_for(settings, platform)
            field = QLineEdit(value)
            form.addRow(platform or tr("No platform"), field)
            self._fields[platform] = field
            self._before[platform] = value
        layout.addLayout(form)
        if not platforms:
            layout.addWidget(QLabel(tr("No build target yet. Add a project with a build target first.")))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def changes(self) -> Dict[str, str]:
        """``{settings name: command}`` of each platform whose line changed."""
        result = {}
        for platform, field in self._fields.items():
            value = field.text().strip()
            if value != self._before[platform]:
                result[emulator_setting(platform)] = value
        return result
