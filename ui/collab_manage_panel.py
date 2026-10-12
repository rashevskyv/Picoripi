"""The room's management tabs in the Work Together window: roles, claims, comments and the moderator log.

Every button is enabled by the room's permission table (``core/collab/roles.py``); the room checks again when the
button is used, so a button that is enabled by mistake is still refused.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.collab.roles import ASSIGNABLE, HOST, MODERATOR, REVIEWER, TRANSLATOR, OBSERVER, allowed
from core.i18n import tr

ID_ROLE = Qt.ItemDataRole.UserRole
PREVIEW_CHARS = 80


def role_label(role: Optional[str]) -> str:
    return {
        HOST: tr('Host'), MODERATOR: tr('Moderator'), REVIEWER: tr('Reviewer'),
        TRANSLATOR: tr('Translator'), OBSERVER: tr('Observer'),
    }.get(role or "", tr('No role'))


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


def _fill(widget: QListWidget, rows: List[Tuple[str, str]]) -> None:
    """Replace the rows, keeping the selected one selected when it is still there."""
    selected = widget.currentItem().data(ID_ROLE) if widget.currentItem() is not None else None
    widget.clear()
    for item_id, text in rows:
        item = QListWidgetItem(text)
        item.setData(ID_ROLE, item_id)
        widget.addItem(item)
        if item_id == selected:
            widget.setCurrentItem(item)


def _selected_id(widget: QListWidget) -> Optional[str]:
    item = widget.currentItem()
    return item.data(ID_ROLE) if item is not None else None


class ManagePanel(QTabWidget):
    """Four tabs: roles, claims (with the requests), comments and the log (host only)."""

    def __init__(self, parent: QWidget, handler: Any):
        super().__init__(parent)
        self.handler = handler

        # Roles
        roles_tab = QWidget(self)
        roles_layout = QVBoxLayout(roles_tab)
        self.people = QListWidget(roles_tab)
        self.people.setToolTip(tr('Select a participant to change its role, remove it or make it the host.'))
        self.people.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        roles_layout.addWidget(self.people, 1)
        row = QHBoxLayout()
        self.role_box = QComboBox(roles_tab)
        for role in ASSIGNABLE:
            self.role_box.addItem(role_label(role), role)
        self.role_box.currentIndexChanged.connect(lambda *_: self._refresh_buttons())
        row.addWidget(self.role_box)
        self.set_role_button = QPushButton(tr('Set role'), roles_tab)
        self.set_role_button.clicked.connect(self._set_role)
        row.addWidget(self.set_role_button)
        roles_layout.addLayout(row)
        row = QHBoxLayout()
        self.kick_button = QPushButton(tr('Remove from room'), roles_tab)
        self.kick_button.setToolTip(tr('The participant cannot join again until you allow it back.'))
        self.kick_button.clicked.connect(self._kick)
        self.unban_button = QPushButton(tr('Allow back'), roles_tab)
        self.unban_button.clicked.connect(self._unban)
        self.transfer_button = QPushButton(tr('Make host'), roles_tab)
        self.transfer_button.setToolTip(tr('Give the host role to this participant. You become a moderator.'))
        self.transfer_button.clicked.connect(self._transfer)
        for button in (self.kick_button, self.unban_button, self.transfer_button):
            row.addWidget(button)
        roles_layout.addLayout(row)
        self.addTab(roles_tab, tr('Roles'))

        # Claims and requests
        claims_tab = QWidget(self)
        claims_layout = QVBoxLayout(claims_tab)
        self.claims = QListWidget(claims_tab)
        self.claims.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        claims_layout.addWidget(self.claims, 1)
        self.release_button = QPushButton(tr('Release the claim'), claims_tab)
        self.release_button.setToolTip(tr('Give the area back. The owner, a host or a moderator can do this.'))
        self.release_button.clicked.connect(self._release)
        claims_layout.addWidget(self.release_button)
        self.requests = QListWidget(claims_tab)
        self.requests.setToolTip(tr('Someone asked for an area that another participant claimed.'))
        self.requests.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        claims_layout.addWidget(self.requests, 1)
        row = QHBoxLayout()
        self.approve_request_button = QPushButton(tr('Give the area'), claims_tab)
        self.approve_request_button.setToolTip(tr('Take the area from its owner and give it to the one who asked.'))
        self.approve_request_button.clicked.connect(lambda: self._decide(True))
        self.deny_request_button = QPushButton(tr('Refuse'), claims_tab)
        self.deny_request_button.clicked.connect(lambda: self._decide(False))
        row.addWidget(self.approve_request_button)
        row.addWidget(self.deny_request_button)
        claims_layout.addLayout(row)
        self.addTab(claims_tab, tr('Claims'))

        # Comments
        comments_tab = QWidget(self)
        comments_layout = QVBoxLayout(comments_tab)
        self.comments = QListWidget(comments_tab)
        self.comments.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        comments_layout.addWidget(self.comments, 1)
        row = QHBoxLayout()
        self.resolve_button = QPushButton(tr('Resolve'), comments_tab)
        self.resolve_button.clicked.connect(self._resolve)
        self.delete_button = QPushButton(tr('Delete'), comments_tab)
        self.delete_button.clicked.connect(self._delete_comment)
        row.addWidget(self.resolve_button)
        row.addWidget(self.delete_button)
        comments_layout.addLayout(row)
        self.addTab(comments_tab, tr('Comments'))

        # Moderator log (host only)
        log_tab = QWidget(self)
        log_layout = QVBoxLayout(log_tab)
        self.log = QListWidget(log_tab)
        self.log.setToolTip(tr('What the host and the moderators changed, most recent last.'))
        log_layout.addWidget(self.log, 1)
        self.log_tab = log_tab
        self.addTab(log_tab, tr('Moderator log'))

        self._refresh_buttons()

    # ---- what is shown ------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the lists from the window's mirror of the room (one pass; the lists are small)."""
        handler = self.handler
        me = handler._my_id()
        _fill(self.people, [(mid, self._person_text(mid, member, me)) for mid, member in handler.members.items()])
        _fill(self.claims, [(cid, self._claim_text(claim)) for cid, claim in handler.claims.items()])
        _fill(self.requests, [(rid, tr('{name} asks for {label}, {count} row(s)', name=req.get("name", "?"),
                                       label=req.get("scope", {}).get("label", ""), count=req.get("count", 0)))
                              for rid, req in handler.requests.items()])
        _fill(self.comments, [(cid, self._comment_text(comment)) for cid, comment in handler.comments.items()])
        self.setTabVisible(self.indexOf(self.log_tab), handler.role == HOST)
        if handler.role == HOST:
            _fill(self.log, [(str(index), self._log_text(entry)) for index, entry in enumerate(handler.log)])
        self._refresh_buttons()

    def _person_text(self, mid: str, member: Dict[str, Any], me: Optional[str]) -> str:
        state = tr('removed') if member.get("banned") else (tr('online') if member.get("online") else tr('offline'))
        suffix = tr(' (you)') if mid == me else ""
        return f"{member.get('name', '?')}{suffix}: {role_label(member.get('role'))}, {state}"

    def _claim_text(self, claim: Dict[str, Any]) -> str:
        text = tr('{name}: {label}, {count} row(s)', name=claim.get("name", "?"),
                  label=claim.get("scope", {}).get("label", ""), count=len(claim.get("keys") or []))
        return text if claim.get("online") else text + tr(' (offline)')

    def _comment_text(self, comment: Dict[str, Any]) -> str:
        text = tr('{author} on {label}: {text}', author=comment.get("author_name", "?"),
                  label=comment.get("scope", {}).get("label", "") or tr('the whole project'),
                  text=_short(comment.get("text", "")))
        return text + tr(' [resolved]') if comment.get("resolved") else text

    def _log_text(self, entry: Dict[str, Any]) -> str:
        when = time.strftime("%H:%M", time.localtime(entry["time"])) if entry.get("time") else ""
        action = str(entry.get("action", "")).replace("_", " ")
        return f"{when} {entry.get('name', '?')}: {action}"

    # ---- buttons -------------------------------------------------------------------

    def _refresh_buttons(self) -> None:
        handler = self.handler
        role = handler.role or ""
        me = handler._my_id()
        member = handler.members.get(_selected_id(self.people) or "")
        target_role = member.get("role") if member else None
        new_role = self.role_box.currentData()
        is_other = member is not None and _selected_id(self.people) != me
        self.set_role_button.setEnabled(bool(is_other and allowed(role, "set_role", target=target_role, new=new_role)))
        self.kick_button.setEnabled(bool(is_other and not member.get("banned") and allowed(role, "kick", target=target_role)))
        self.unban_button.setEnabled(bool(is_other and member.get("banned") and allowed(role, "kick", target=target_role)))
        self.transfer_button.setEnabled(bool(is_other and role == HOST and not member.get("banned")))
        claim = handler.claims.get(_selected_id(self.claims) or "")
        self.release_button.setEnabled(bool(claim and (claim.get("owner") == me or allowed(role, "claim_decide"))))
        decide = allowed(role, "claim_decide") and _selected_id(self.requests) is not None
        self.approve_request_button.setEnabled(decide)
        self.deny_request_button.setEnabled(decide)
        comment = handler.comments.get(_selected_id(self.comments) or "")
        self.resolve_button.setEnabled(comment is not None)
        self.delete_button.setEnabled(bool(comment and (comment.get("author") == me
                                                       or allowed(role, "delete_any_comment"))))

    def _set_role(self) -> None:
        mid = _selected_id(self.people)
        if mid:
            self.handler.set_role(mid, self.role_box.currentData())

    def _kick(self) -> None:
        mid = _selected_id(self.people)
        member = self.handler.members.get(mid or "")
        if member and QMessageBox.question(self, tr('Remove from room'), tr(
                'Remove {name} from the room? They cannot join again until you allow it back.',
                name=member.get("name", "?"))) == QMessageBox.StandardButton.Yes:
            self.handler.kick(mid)

    def _unban(self) -> None:
        mid = _selected_id(self.people)
        if mid:
            self.handler.unban(mid)

    def _transfer(self) -> None:
        mid = _selected_id(self.people)
        member = self.handler.members.get(mid or "")
        if member and QMessageBox.question(self, tr('Make host'), tr(
                'Give the host role to {name}? You become a moderator and cannot give it back on your own.',
                name=member.get("name", "?"))) == QMessageBox.StandardButton.Yes:
            self.handler.transfer_host(mid)

    def _release(self) -> None:
        cid = _selected_id(self.claims)
        if cid:
            self.handler.release(cid)

    def _decide(self, approve: bool) -> None:
        rid = _selected_id(self.requests)
        if rid:
            self.handler.decide(rid, approve)

    def _resolve(self) -> None:
        cid = _selected_id(self.comments)
        comment = self.handler.comments.get(cid or "")
        if comment is not None:
            self.handler.resolve_comment(cid, not comment.get("resolved"))

    def _delete_comment(self) -> None:
        cid = _selected_id(self.comments)
        if cid:
            self.handler.delete_comment(cid)
