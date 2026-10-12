"""A bar above the editor while in a room: this row's claim, comments and approval, who is on it, and a conflict to settle."""
from __future__ import annotations

import time
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton

from core.collab.roles import allowed
from core.i18n import tr
from ui.collab_menu import show_row_menu

PREVIEW_CHARS = 80


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


class CollabRowBar(QFrame):
    """Hidden outside a room. ``refresh`` is called whenever the editor shows a row or the room changes it."""

    def __init__(self, main_window: Any, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setObjectName("collab_row_bar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._key: Optional[str] = None
        self._locked = False
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_menu)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.theirs_button = QPushButton(tr('Take theirs'), self)
        self.theirs_button.setToolTip(tr('Use the text the other participant saved in the room for this row.'))
        self.theirs_button.clicked.connect(lambda: self._handler().take_theirs(self._key))
        layout.addWidget(self.theirs_button)
        self.mine_button = QPushButton(tr('Keep mine'), self)
        self.mine_button.setToolTip(tr('Send your text to the room; it replaces the other participant\'s version.'))
        self.mine_button.clicked.connect(lambda: self._handler().keep_mine(self._key))
        layout.addWidget(self.mine_button)
        self.claim_button = QPushButton(tr('Claim this row'), self)
        self.claim_button.setToolTip(tr('Reserve this row for yourself. Nobody else edits it while you hold it.'))
        self.claim_button.clicked.connect(self._claim)
        layout.addWidget(self.claim_button)
        self.approve_button = QPushButton(tr('Approve'), self)
        self.approve_button.setToolTip(tr('Mark this row as checked. Its text does not change.'))
        self.approve_button.clicked.connect(self._approve)
        layout.addWidget(self.approve_button)
        self.comment_button = QPushButton(tr('Comment…'), self)
        self.comment_button.setToolTip(tr('Leave a comment on this row for everyone in the room.'))
        self.comment_button.clicked.connect(self._comment)
        layout.addWidget(self.comment_button)
        self.hide()

    def _handler(self):
        return getattr(self.mw, "collab_handler", None)

    def _lock_editor(self, locked: bool) -> None:
        """The editor is read-only while the row is not this participant's to change. Only this bar sets and clears
        the flag, so a read-only editor for another reason is left as it is."""
        editor = getattr(self.mw, "edited_text_edit", None)
        if editor is None or (not locked and not self._locked):
            return
        editor.setReadOnly(locked)
        self._locked = locked

    def _open_menu(self, pos) -> None:
        handler = self._handler()
        if handler is not None and self._key is not None:
            show_row_menu(handler, self, pos, self._key)

    def refresh(self, block_idx: int, string_idx: int) -> None:
        handler = self._handler()
        if handler is None or not handler.active or block_idx < 0 or string_idx < 0:
            self._lock_editor(False)
            self.hide()
            return
        self._key = handler._key(block_idx, string_idx)
        self._lock_editor(not handler.can_edit(self._key))   # a row claimed by someone else is read-only
        conflict = handler.conflicts.get(self._key)
        if conflict:
            self.label.setText(tr('Conflict: {name} saved "{theirs}"; yours is "{mine}".',
                                  name=conflict.get("name") or "?", theirs=_short(conflict.get("text", "")),
                                  mine=_short(conflict.get("mine", ""))))
            self.theirs_button.show()
            self.mine_button.show()
            self.claim_button.hide()
            self.approve_button.hide()
            self.comment_button.hide()
            self.show()
            return
        self.theirs_button.hide()
        self.mine_button.hide()
        notes = handler.row_notes(self._key)
        role = handler.role or ""
        self.claim_button.setVisible(allowed(role, "claim") and not notes["claimed_by"])
        self.approve_button.setVisible(allowed(role, "approve"))
        self.approve_button.setText(tr('Remove approval') if notes["approved"] else tr('Approve'))
        self.comment_button.show()
        parts = []
        if notes["claimed_by_me"]:
            parts.append(tr('Claimed by you'))
        elif notes["claimed_by"]:
            parts.append(tr('Claimed by {name}', name=notes["claimed_by"]))
        here = handler.others_on(block_idx, string_idx)
        if here:
            parts.append(tr('Here now: {names}', names=", ".join(here)))
        info = handler.row_info.get(self._key)
        if info and info.get("name"):
            when = time.strftime("%H:%M", time.localtime(info["time"])) if info.get("time") else ""
            parts.append(tr('Last changed by {name} {when}', name=info["name"], when=when).strip())
        if notes["approved"]:
            parts.append(tr('Approved'))
        if notes["comments_open"]:
            parts.append(tr('{count} open comment(s)', count=notes["comments_open"]))
        self.label.setText(" · ".join(parts))
        self.show()

    def _claim(self) -> None:
        handler = self._handler()
        if handler is not None and self._key is not None:
            handler.claim("row", handler.describe(self._key), [self._key])

    def _approve(self) -> None:
        handler = self._handler()
        if handler is not None and self._key is not None:
            handler.approve_row(self._key, not handler.row_notes(self._key)["approved"])

    def _comment(self) -> None:
        handler = self._handler()
        if handler is None or self._key is None:
            return
        label = handler.describe(self._key)
        text, ok = QInputDialog.getMultiLineText(self, tr('Comment'), tr('Comment on {scope}:', scope=label), "")
        if ok and text.strip():
            handler.comment("row", label, [self._key], text.strip())
