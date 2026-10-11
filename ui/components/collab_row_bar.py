"""A bar above the editor while in a room: who changed this row last, who is on it now, and a conflict to settle."""
from __future__ import annotations

import time
from typing import Any, Optional

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from core.i18n import tr

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
        self.hide()

    def _handler(self):
        return getattr(self.mw, "collab_handler", None)

    def refresh(self, block_idx: int, string_idx: int) -> None:
        handler = self._handler()
        if handler is None or not handler.active or block_idx < 0 or string_idx < 0:
            self.hide()
            return
        self._key = handler._key(block_idx, string_idx)
        conflict = handler.conflicts.get(self._key)
        if conflict:
            self.label.setText(tr('Conflict: {name} saved "{theirs}"; yours is "{mine}".',
                                  name=conflict.get("name") or "?", theirs=_short(conflict.get("text", "")),
                                  mine=_short(conflict.get("mine", ""))))
            self.theirs_button.show()
            self.mine_button.show()
            self.show()
            return
        self.theirs_button.hide()
        self.mine_button.hide()
        parts = []
        here = handler.others_on(block_idx, string_idx)
        if here:
            parts.append(tr('Here now: {names}', names=", ".join(here)))
        info = handler.row_info.get(self._key)
        if info and info.get("name"):
            when = time.strftime("%H:%M", time.localtime(info["time"])) if info.get("time") else ""
            parts.append(tr('Last changed by {name} {when}', name=info["name"], when=when).strip())
        if not parts:
            self.hide()
            return
        self.label.setText(" · ".join(parts))
        self.show()
