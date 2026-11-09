"""Image AI widgets shared by Settings > Image AI and the Textures window: the provider list and the local
CLI agent command with its presets (``core.texture_formats.image_ai.AGENT_PRESETS``)."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget

from core.i18n import tr
from core.texture_formats import image_ai

AGENT_NAMES = {"codex": "Codex", "claude": "Claude Code", "gemini": "Gemini CLI", "hermes": "Hermes"}


def provider_combo(parent=None) -> QComboBox:
    combo = QComboBox(parent)
    names = {"openai": tr("OpenAI (API key)"), "command": tr("Local CLI agent (Codex, Claude Code, Hermes...)")}
    for provider in image_ai.PROVIDERS:
        combo.addItem(names.get(provider, provider), provider)
    return combo


class AgentCommand(QWidget):
    """A preset list and the command line it fills; any other command can be typed in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preset = QComboBox(self)
        self.preset.addItem(tr("Custom command"), "")
        for agent, command in image_ai.AGENT_PRESETS.items():
            self.preset.addItem(AGENT_NAMES.get(agent, agent), command)
        self.preset.setAccessibleName(tr("Agent"))
        self.edit = QLineEdit(self)
        self.edit.setAccessibleName(tr("Agent command"))
        self.edit.setToolTip(tr("Runs in a temporary folder with the task on standard input. {input}: the texture "
                                "PNG, {output}: the PNG the agent must write, {prompt_file}: the task as a file."))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preset)
        layout.addWidget(self.edit, 1)
        self.preset.activated.connect(lambda _index: self.preset.currentData() and self.edit.setText(self.preset.currentData()))

    def set_command(self, command: str) -> None:
        self.edit.setText(command)
        self.preset.setCurrentIndex(max(0, self.preset.findData(command)))

    def command(self) -> str:
        return self.edit.text().strip()
