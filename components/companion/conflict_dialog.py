"""Conflict resolution dialog for Companion glossary synchronization."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.companion_sync import ConflictRecord
from core.i18n import tr


class CompanionConflictDialog(QDialog):
    """Dialog for resolving glossary sync conflicts when entries differ on both sides."""

    def __init__(
        self,
        conflicts: List[ConflictRecord],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.conflicts = list(conflicts)
        self._button_groups: Dict[str, QButtonGroup] = {}

        self.setWindowTitle(tr("Companion Synchronization Conflicts"))
        self.resize(650, 480)
        self.setMinimumSize(540, 360)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header description
        header = QLabel(
            tr(
                "The following {count} term(s) have conflicting changes locally and on the Companion device.\n"
                "Please choose which version to keep for each term:"
            ).format(count=len(self.conflicts)),
            self,
        )
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e293b;")
        header.setWordWrap(True)
        main_layout.addWidget(header)

        # Quick action bar
        quick_layout = QHBoxLayout()
        quick_label = QLabel(tr("Bulk actions:"), self)
        quick_label.setStyleSheet("color: #64748b; font-size: 11px;")
        quick_layout.addWidget(quick_label)

        keep_all_local_btn = QPushButton(tr("Keep All Local (PC)"), self)
        keep_all_local_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        keep_all_local_btn.clicked.connect(self._select_all_local)
        quick_layout.addWidget(keep_all_local_btn)

        keep_all_remote_btn = QPushButton(tr("Keep All Remote (Companion)"), self)
        keep_all_remote_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        keep_all_remote_btn.clicked.connect(self._select_all_remote)
        quick_layout.addWidget(keep_all_remote_btn)

        quick_layout.addStretch()
        main_layout.addLayout(quick_layout)

        # Scroll Area with Conflict Cards
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.StyledPanel)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(10)

        for conflict in self.conflicts:
            card = self._create_conflict_card(conflict)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        # Bottom Buttons
        button_box = QDialogButtonBox(self)
        apply_btn = button_box.addButton(tr("Apply Resolution"), QDialogButtonBox.ButtonRole.AcceptRole)
        apply_btn.setStyleSheet("QPushButton { background-color: #6366f1; color: white; font-weight: bold; padding: 6px 14px; }")
        cancel_btn = button_box.addButton(tr("Cancel Sync"), QDialogButtonBox.ButtonRole.RejectRole)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_conflict_card(self, conflict: ConflictRecord) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.Box)
        card.setStyleSheet(
            "QFrame { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(6)

        # Term title
        diff_str = ", ".join(conflict.differing_fields) if conflict.differing_fields else "content"
        title_label = QLabel(f"<b>{conflict.original}</b> <span style='color: #ef4444;'>({tr('Differing')}: {diff_str})</span>")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        card_layout.addWidget(title_label)

        # Options group
        btn_group = QButtonGroup(card)
        self._button_groups[conflict.original] = btn_group

        # Local option
        loc_e = conflict.local_entry
        loc_trans = loc_e.get("translation", "")
        loc_status = loc_e.get("status", "") or "unconfirmed"
        loc_time = conflict.local_time[:19].replace("T", " ") if conflict.local_time else "—"

        local_radio = QRadioButton()
        local_text = (
            f"<b>{tr('Local (PC)')}:</b> \"{loc_trans}\"  "
            f"<span style='color:#64748b;'>[{loc_status}] ({loc_time})</span>"
        )
        local_radio.setText(f"{tr('Local (PC)')}: {loc_trans} [{loc_status}]")
        local_radio.setChecked(True)
        btn_group.addButton(local_radio, 1)

        local_label = QLabel(local_text)
        local_label.setTextFormat(Qt.TextFormat.RichText)
        local_row = QHBoxLayout()
        local_row.addWidget(local_radio)
        local_row.addWidget(local_label)
        local_row.addStretch()
        card_layout.addLayout(local_row)

        # Remote option
        rem_e = conflict.remote_entry
        rem_trans = rem_e.get("translation", "")
        rem_status = rem_e.get("status", "") or "unconfirmed"
        rem_time = conflict.remote_time[:19].replace("T", " ") if conflict.remote_time else "—"

        remote_radio = QRadioButton()
        remote_text = (
            f"<b>{tr('Remote (Companion)')}:</b> \"{rem_trans}\"  "
            f"<span style='color:#64748b;'>[{rem_status}] ({rem_time})</span>"
        )
        remote_radio.setText(f"{tr('Remote (Companion)')}: {rem_trans} [{rem_status}]")
        btn_group.addButton(remote_radio, 2)

        remote_label = QLabel(remote_text)
        remote_label.setTextFormat(Qt.TextFormat.RichText)
        remote_row = QHBoxLayout()
        remote_row.addWidget(remote_radio)
        remote_row.addWidget(remote_label)
        remote_row.addStretch()
        card_layout.addLayout(remote_row)

        return card

    def _select_all_local(self) -> None:
        for group in self._button_groups.values():
            btn = group.button(1)
            if btn:
                btn.setChecked(True)

    def _select_all_remote(self) -> None:
        for group in self._button_groups.values():
            btn = group.button(2)
            if btn:
                btn.setChecked(True)

    def get_resolutions(self) -> Dict[str, str]:
        """Return mapping of original term to 'local' or 'remote' decision."""
        resolutions: Dict[str, str] = {}
        for original, group in self._button_groups.items():
            checked_id = group.checkedId()
            if checked_id == 2:
                resolutions[original] = "remote"
            else:
                resolutions[original] = "local"
        return resolutions
