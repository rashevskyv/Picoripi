"""Collaboration window: host a room or join one, see who is in it and where, jump to them, leave."""
from __future__ import annotations

import getpass
import secrets
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from handlers.collab_handler import DEFAULT_PORT, LanLookup, load_settings
from ui.collab_manage_panel import ManagePanel
from utils.thread_utils import single_shot

KEY_ROLE = Qt.ItemDataRole.UserRole


class CollabDialog(QDialog):
    """Modeless; lives while the main window lives."""

    def __init__(self, main_window: Any, handler: Any):
        super().__init__(main_window if isinstance(main_window, QWidget) else None)
        self.mw, self.handler = main_window, handler
        self.setWindowTitle(tr('Work Together'))
        self.resize(620, 820)
        saved = load_settings()
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(tr(
            'One of you hosts the room on their computer; the others join it with the address and password the '
            'host gives them. Everyone opens the same project (the same game text). Edits, who is where and who '
            'changed a row reach everyone in a second or two. Traffic is not encrypted: use a local network or a '
            'VPN (Tailscale, ZeroTier, Radmin VPN).'), wordWrap=True))

        self.name_edit = QLineEdit(saved.get("name") or getpass.getuser(), self)
        self.name_edit.setToolTip(tr('How the others see you.'))
        form = QFormLayout()
        form.addRow(tr('Your name:'), self.name_edit)
        layout.addLayout(form)

        host_box = QGroupBox(tr('Host a room'), self)
        host_form = QFormLayout(host_box)
        self.port_spin = QSpinBox(host_box)
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(int(saved.get("port") or DEFAULT_PORT))
        self.port_spin.setToolTip(tr('The port the others connect to. Windows may ask to allow Picoripi through the firewall.'))
        host_form.addRow(tr('Port:'), self.port_spin)
        self.host_password = QLineEdit(secrets.token_urlsafe(6), host_box)
        self.host_password.setToolTip(tr('The others type this to join. Change it for every new group.'))
        host_form.addRow(tr('Password:'), self.host_password)
        self.lan_check = QCheckBox(tr('Allow other computers (LAN)'), host_box)
        self.lan_check.setToolTip(tr('Off: only this computer can join. On: computers on your network can join with '
                                     'the password. Set it before you start the room.'))
        host_form.addRow(self.lan_check)
        self.lan_warning = QLabel(tr('Traffic is plain HTTP: the password is sent without encryption. Allow other '
                                     'computers only on a network you trust.'), host_box)
        self.lan_warning.setWordWrap(True)
        host_form.addRow(self.lan_warning)
        self.host_button = QPushButton(tr('Start the room'), host_box)
        self.host_button.setToolTip(tr('Start the room on this computer and join it.'))
        self.host_button.clicked.connect(self._host)
        host_form.addRow(self.host_button)
        self.invite_label = QLabel(host_box)
        self.invite_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.invite_label.setWordWrap(True)
        host_form.addRow(self.invite_label)
        self.copy_button = QPushButton(tr('Copy the invitation'), host_box)
        self.copy_button.setToolTip(tr('Copy the addresses and the password to send to the others.'))
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.invite_label.text()))
        host_form.addRow(self.copy_button)
        layout.addWidget(host_box)

        join_box = QGroupBox(tr('Join a room'), self)
        join_form = QFormLayout(join_box)
        self.address_edit = QLineEdit(saved.get("address") or "", join_box)
        self.address_edit.setPlaceholderText("192.168.1.20:8765")
        self.address_edit.setToolTip(tr('The address the host gave you: computer:port.'))
        join_form.addRow(tr('Address:'), self.address_edit)
        self.join_password = QLineEdit(join_box)
        self.join_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.join_password.setToolTip(tr('The password the host gave you.'))
        join_form.addRow(tr('Password:'), self.join_password)
        self.join_button = QPushButton(tr('Join'), join_box)
        self.join_button.setToolTip(tr('Connect to the host\'s room.'))
        self.join_button.clicked.connect(self._join)
        join_form.addRow(self.join_button)
        layout.addWidget(join_box)

        layout.addWidget(QLabel(tr('In the room (double-click to go to where they are):'), self))
        self.people = QListWidget(self)
        self.people.itemDoubleClicked.connect(lambda item: self.handler.jump_to(item.data(KEY_ROLE)))
        layout.addWidget(self.people, 1)
        self.manage = ManagePanel(self, self.handler)
        layout.addWidget(self.manage, 2)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.progress_button = QPushButton(tr('Progress page'), self)
        self.progress_button.setToolTip(tr('Open the room\'s progress page: who translated how much, what is left.'))
        self.progress_button.clicked.connect(lambda: self.mw.actions.open_progress())
        buttons.addWidget(self.progress_button)
        self.leave_button = QPushButton(tr('Leave the room'), self)
        self.leave_button.setToolTip(tr('Disconnect; when you host, the room closes for everyone.'))
        self.leave_button.clicked.connect(self._leave)
        buttons.addStretch(1)
        buttons.addWidget(self.leave_button)
        layout.addLayout(buttons)
        self._tick()

    def _host(self) -> None:
        if not self._ready():
            return
        lan = self.lan_check.isChecked()
        try:
            port = self.handler.host(self.port_spin.value(), self.host_password.text(),
                                     self.name_edit.text().strip(), lan=lan)
        except OSError as exc:
            self.status_label.setText(tr('The room could not start: {error}', error=exc))
            return
        if lan:
            # Name lookup can wait for DNS: the invitation is filled in when the addresses arrive.
            self.invite_label.setText(tr('Looking up this computer\'s addresses…'))
            self._invite_port = port
            self._lan_lookup = LanLookup()
            self._lan_lookup.found.connect(self._show_lan_invite)
            self._lan_lookup.start()
        else:
            self.invite_label.setText(tr('Address: {addresses} (this computer only)\nPassword: {password}',
                                         addresses=f"127.0.0.1:{port}", password=self.host_password.text()))
        self._tick()

    def _show_lan_invite(self, ips: list) -> None:
        if self.handler.server is None or self.handler.server.port != self._invite_port:
            return                                         # the room was left while the lookup ran
        addresses = [f"{ip}:{self._invite_port}" for ip in ips] or [f"<{tr('this computer')}>:{self._invite_port}"]
        self.invite_label.setText(tr('Address: {addresses}\nPassword: {password}',
                                     addresses=" / ".join(addresses), password=self.host_password.text()))

    def _join(self) -> None:
        if not self._ready() or not self.address_edit.text().strip():
            return
        self.handler.join(self.address_edit.text().strip(), self.join_password.text(), self.name_edit.text().strip())
        self._tick()

    def _leave(self) -> None:
        self.handler.leave()
        self.invite_label.clear()
        self._tick()

    def _ready(self) -> bool:
        if not self.handler.project_open():
            self.status_label.setText(tr('Open a project first: the room shares the rows of the open project.'))
            return False
        if not self.name_edit.text().strip():
            self.status_label.setText(tr('Type your name first.'))
            return False
        return True

    def _tick(self) -> None:
        """Refresh the list and the buttons while the window is open."""
        handler = self.handler
        self.host_button.setEnabled(not handler.active)
        self.join_button.setEnabled(not handler.active)
        self.leave_button.setEnabled(handler.active)
        self.copy_button.setEnabled(bool(self.invite_label.text()))
        self.people.clear()
        for person in handler.participants:
            item = QListWidgetItem(tr('{name} — {where}', name=person.get("name", "?"), where=handler.describe(person.get("where"))))
            item.setData(KEY_ROLE, person.get("where"))
            self.people.addItem(item)
        self.status_label.setText(handler.last_message or handler.status_text())
        if handler.active:
            self.manage.refresh()
        if self.isVisible():
            single_shot(1000, self, self._tick)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self._tick()
