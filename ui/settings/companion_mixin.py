"""Settings mixin for Companion server configuration."""
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from core.companion_sync import CompanionSyncClient
from core.i18n import tr


class SettingsCompanionMixin:
    """Mixin for companion server configuration in settings dialog."""

    def setup_companion_tab(self):
        """Setup Companion server tab."""
        main_layout = QVBoxLayout(self.companion_tab)

        info_label = QLabel(
            tr(
                "Configure connection to your remote Picoripi Companion server (Ubuntu or Docker) "
                "to review and approve translation glossaries from your mobile phone."
            ),
            self,
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; margin-bottom: 12px;")
        main_layout.addWidget(info_label)

        form_layout = QFormLayout()

        self.companion_url_edit = QLineEdit(self)
        self.companion_url_edit.setPlaceholderText(tr("e.g. http://192.168.1.100:8000 or https://companion.myserver.com"))
        form_layout.addRow(QLabel(tr("Server URL:")), self.companion_url_edit)

        self.companion_token_edit = QLineEdit(self)
        self.companion_token_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.companion_token_edit.setPlaceholderText(tr("Secret token or PIN configured on server"))
        form_layout.addRow(QLabel(tr("API Token / PIN:")), self.companion_token_edit)

        test_row = QHBoxLayout()
        self.test_companion_btn = QPushButton(tr("Test Connection"), self)
        self.test_companion_btn.clicked.connect(self._on_test_companion_clicked)
        test_row.addWidget(self.test_companion_btn)

        self.companion_status_label = QLabel(self)
        test_row.addWidget(self.companion_status_label, 1)

        form_layout.addRow("", test_row)

        self.companion_auto_sync_check = QCheckBox(tr("Automatically sync on project open and close"), self)
        self.companion_auto_sync_check.setToolTip(
            tr(
                "When enabled, Picoripi will automatically pull reviewed glossary terms on project open "
                "and push changes on project save/close in the background."
            )
        )
        form_layout.addRow("", self.companion_auto_sync_check)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()

    def _on_test_companion_clicked(self):
        """Test connection to the companion server."""
        url = self.companion_url_edit.text().strip()
        token = self.companion_token_edit.text().strip()

        client = CompanionSyncClient(url, token)
        self.companion_status_label.setText(tr("Connecting..."))
        self.companion_status_label.setStyleSheet("color: #888;")

        ok, msg = client.test_connection()
        if ok:
            self.companion_status_label.setText(f"✓ {msg}")
            self.companion_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.companion_status_label.setText(f"✗ {msg}")
            self.companion_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
