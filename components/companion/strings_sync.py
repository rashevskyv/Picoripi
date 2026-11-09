"""Tools → Sync Translation with Companion: take the phone's edits into the project, decide conflicts, send the rows.

Network calls run off the GUI thread (``run_companion_call``). Phone edits enter the project only through
``DataStateProcessor.update_edited_data`` (action type ``COMPANION_REMOTE``: undoable, shared with a room).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from components.companion.background_call import run_companion_call
from core.companion_strings import (
    REMOTE,
    SortedEdits,
    StringConflict,
    pull_phone_edits,
    push_rows,
    sort_phone_edits,
    take_snapshot,
)
from core.companion_sync import CompanionSyncClient
from core.i18n import tr



def _text_box(text: str, parent: QWidget) -> QPlainTextEdit:
    box = QPlainTextEdit(text, parent)
    box.setReadOnly(True)
    box.setMaximumHeight(80)
    return box


class StringConflictDialog(QDialog):
    """Each row changed on the PC and on the phone: the original and both texts, and a choice of one."""

    def __init__(self, conflicts: List[StringConflict], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Translation Conflicts"))
        self.resize(700, 520)
        self._groups: Dict[str, QButtonGroup] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("These rows changed on this PC and on the phone. Choose the text to keep for each "
                                   "row. Cancel changes nothing: the phone edits stay on the server."), self))
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget()
        rows = QVBoxLayout(body)
        for conflict in conflicts:
            card = QGroupBox(tr("Block {block}, row {row}").format(block=conflict.block, row=conflict.string + 1), body)
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(tr("Original:"), card))
            card_layout.addWidget(_text_box(conflict.original, card))
            group = QButtonGroup(card)
            pc = QRadioButton(tr("Keep the PC text:"), card)
            pc.setChecked(True)
            phone = QRadioButton(tr("Take the phone text:"), card)
            group.addButton(pc, 1)
            group.addButton(phone, 2)
            card_layout.addWidget(pc)
            card_layout.addWidget(_text_box(conflict.pc, card))
            card_layout.addWidget(phone)
            card_layout.addWidget(_text_box(conflict.phone, card))
            self._groups[conflict.key] = group
            rows.addWidget(card)
        rows.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def phone_keys(self) -> Set[str]:
        """The rows whose phone text was chosen."""
        return {key for key, group in self._groups.items() if group.checkedId() == 2}


def companion_client(mw: Any) -> Optional[CompanionSyncClient]:
    """The client from **Settings → Companion**; None when no server is set."""
    settings = getattr(mw, "settings_manager", None)
    url = settings.get("companion_server_url", "") if settings else ""
    token = settings.get("companion_api_token", "") if settings else ""
    if not isinstance(url, str) or not url.strip():
        return None
    return CompanionSyncClient(url, token if isinstance(token, str) and token else "picoripi")


def project_name(mw: Any) -> Optional[str]:
    """The name the glossary sync uses for this project on the server."""
    project = getattr(getattr(mw, "project_manager", None), "project", None)
    return getattr(project, "name", None) if project is not None else None


def apply_phone_edits(mw: Any, edits: List[tuple]) -> Set[int]:
    """Write phone texts into the project through ``DataStateProcessor``; refresh the blocks they touched."""
    touched: Set[int] = set()
    # ponytail: one pass on the GUI thread; phone edits are few. Slice like the room's join if this ever stalls.
    for block, string, text in edits:
        mw.data_processor.update_edited_data(block, string, text, action_type=REMOTE, skip_ui_refresh=True)
        touched.add(block)
    updater = getattr(mw, "ui_updater", None)
    if updater is not None and touched:
        for block in touched:
            updater.update_block_item_text_with_problem_count(block)
        if getattr(mw.data_store, "physical_block_idx", -1) in touched:
            updater.update_text_views()
    return touched


def sync_translation_with_companion(mw: Any) -> None:
    """The menu action: pull, sort, decide, apply, push."""
    if not getattr(mw.data_store, "data", None) or project_name(mw) is None:
        QMessageBox.information(mw, tr("Companion Sync"), tr("Open a project first."))
        return
    client = companion_client(mw)
    if client is None:
        QMessageBox.information(mw, tr("Companion Sync"), tr("Set the server address in Settings → Companion first."))
        return
    project = project_name(mw)
    run_companion_call(mw, lambda cancelled: pull_phone_edits(client, project, cancelled),
                       lambda result: _on_pulled(mw, client, project, result), label=tr("Fetching phone edits…"))


def _on_pulled(mw: Any, client: CompanionSyncClient, project: str, result: Any) -> None:
    if result is None:
        QMessageBox.warning(mw, tr("Companion Sync"), tr("The request failed; see the log."))
        return
    ok, message, pending = result
    if not ok:
        QMessageBox.warning(mw, tr("Companion Sync"), message)
        return
    flush = getattr(getattr(mw, "editor_operation_handler", None), "stop_and_flush_editor_changes", None)
    if callable(flush):
        flush()                                   # text still being typed counts as the PC text
    edits = sort_phone_edits(pending, take_snapshot(mw))
    chosen = 0
    if edits.conflicts:
        dialog = StringConflictDialog(edits.conflicts, mw)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return                                # nothing taken, nothing sent: every edit stays on the server
        phone = dialog.phone_keys()
        for conflict in edits.conflicts:
            if conflict.key in phone:
                edits.take.append((conflict.block, conflict.string, conflict.phone))
            edits.resolved[conflict.key] = conflict.phone
        chosen = len(edits.conflicts)
    apply_phone_edits(mw, edits.take)
    snapshot = take_snapshot(mw)
    run_companion_call(mw, lambda cancelled: push_rows(client, project, snapshot, edits.resolved, cancelled),
                       lambda pushed: _on_pushed(mw, edits, chosen, pushed), label=tr("Sending the translation…"))


def _on_pushed(mw: Any, edits: SortedEdits, chosen: int, result: Any) -> None:
    taken = len(edits.take)
    if result is None or not result[0]:
        QMessageBox.warning(mw, tr("Companion Sync"), tr(
            "Phone edits taken into the project: {taken}. The rows were not sent: {error}").format(
            taken=taken, error=result[1] if result else tr("see the log")))
        return
    QMessageBox.information(mw, tr("Companion Sync"), tr(
        "Phone edits taken into the project: {taken}. Conflicts decided: {chosen}. "
        "Rows of other project text skipped: {unknown}. Edits still open on the server: {left}.").format(
        taken=taken, chosen=chosen, unknown=edits.unknown, left=result[2]))
