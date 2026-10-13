"""Work together UI: the management tabs, the block tree menu and the row bar, with real windows in one room."""
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QMenu, QPlainTextEdit, QTreeWidget, QTreeWidgetItem

from test_core.test_collab import _project_window
from test_core.test_collab_room_state import _host_and_guest
from ui.collab_manage_panel import ManagePanel
from ui.collab_menu import keys_of_item, show_tree_menu
from ui.components.collab_row_bar import CollabRowBar


@pytest.fixture
def pair(tmp_path, qtbot):
    a, b = _project_window(tmp_path, "a"), _project_window(tmp_path, "b")
    yield a, b
    for mw in (a, b):
        mw.collab_handler.leave()


def _select(widget, item_id):
    for row in range(widget.count()):
        if widget.item(row).data(Qt.ItemDataRole.UserRole) == item_id:
            widget.setCurrentRow(row)
            return
    raise AssertionError(f"{item_id} is not listed")


def test_the_host_can_change_remove_and_transfer_but_a_translator_only_sees_the_list(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    host_id, guest_id = a.collab_handler._my_id(), b.collab_handler._my_id()
    host_panel = ManagePanel(None, a.collab_handler)
    qtbot.addWidget(host_panel)
    host_panel.refresh()
    assert host_panel.people.count() == 2
    _select(host_panel.people, guest_id)
    assert host_panel.set_role_button.isEnabled() and host_panel.kick_button.isEnabled()
    assert host_panel.transfer_button.isEnabled()
    assert host_panel.log_tab is not None and host_panel.isTabVisible(host_panel.indexOf(host_panel.log_tab))

    guest_panel = ManagePanel(None, b.collab_handler)
    qtbot.addWidget(guest_panel)
    guest_panel.refresh()
    assert guest_panel.people.count() == 2
    _select(guest_panel.people, host_id)
    assert not guest_panel.set_role_button.isEnabled()
    assert not guest_panel.kick_button.isEnabled() and not guest_panel.transfer_button.isEnabled()
    assert not guest_panel.isTabVisible(guest_panel.indexOf(guest_panel.log_tab))


def test_the_host_removes_a_translator_from_its_panel_after_a_confirmation(qtbot, pair, monkeypatch):
    a, b = _host_and_guest(qtbot, pair)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes.value)
    panel = ManagePanel(None, a.collab_handler)
    qtbot.addWidget(panel)
    panel.refresh()
    guest = b.collab_handler._my_id()
    _select(panel.people, guest)
    panel.kick_button.click()
    qtbot.waitUntil(lambda: a.collab_handler.members[guest]["banned"], timeout=5000)
    qtbot.waitUntil(lambda: b.collab_handler.client is None, timeout=10000)   # the removed window leaves the room


def test_a_claim_from_the_block_tree_menu_is_granted_to_the_guest(qtbot, pair, monkeypatch):
    a, b = _host_and_guest(qtbot, pair)
    tree = QTreeWidget()
    qtbot.addWidget(tree)
    item = QTreeWidgetItem(["Block 1"])
    item.setData(0, Qt.ItemDataRole.UserRole, 0)
    tree.addTopLevelItem(item)
    kind, label, keys = keys_of_item(b.collab_handler, item)
    assert kind == "block" and label == "Block 1" and len(keys) == 3
    tree.resize(300, 200)
    tree.show()
    qtbot.waitExposed(tree)

    def choose_claim(menu, pos):
        return next(action for action in menu.actions() if action.text() == "Claim for me")

    monkeypatch.setattr(QMenu, "exec", choose_claim)
    show_tree_menu(b.collab_handler, tree, tree.visualItemRect(item).center())
    guest = b.collab_handler._my_id()
    qtbot.waitUntil(lambda: any(c["owner"] == guest for c in a.collab_handler.claims.values()), timeout=5000)
    assert sum(len(c["keys"]) for c in a.collab_handler.claims.values()) == 3


def test_the_row_bar_shows_the_claim_and_offers_only_what_the_role_allows(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    key = a.collab_handler._key(0, 0)
    a.collab_handler.claim("row", "Hello", [key])
    qtbot.waitUntil(lambda: bool(b.collab_handler.claims), timeout=5000)
    qtbot.waitUntil(lambda: bool(a.collab_handler.claims), timeout=5000)   # the owner's window learns it on its poll
    bar_b = CollabRowBar(b)
    qtbot.addWidget(bar_b)
    bar_b.refresh(0, 0)
    assert "Claimed by Host" in bar_b.label.text()
    assert not bar_b.claim_button.isVisibleTo(bar_b)          # claimed by someone else
    assert not bar_b.approve_button.isVisibleTo(bar_b)        # a translator cannot approve
    bar_a = CollabRowBar(a)
    qtbot.addWidget(bar_a)
    bar_a.refresh(0, 0)
    assert "Claimed by you" in bar_a.label.text()
    assert bar_a.approve_button.isVisibleTo(bar_a)            # the host can approve


def test_the_row_bar_shows_names_and_texts_of_the_room_as_plain_text(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    key = b.collab_handler._key(0, 0)
    bar = CollabRowBar(b)
    qtbot.addWidget(bar)
    b.collab_handler.conflicts[key] = {"name": "<b>Olena</b>", "text": "<i>Tak</i>", "mine": "Ні"}
    bar.refresh(0, 0)
    assert bar.label.textFormat() == Qt.TextFormat.PlainText
    assert "<b>Olena</b>" in bar.label.text() and "<i>Tak</i>" in bar.label.text()


def test_a_row_claimed_by_someone_else_is_read_only_in_the_editor_until_the_window_leaves(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    editor = QPlainTextEdit()
    qtbot.addWidget(editor)
    b.edited_text_edit = editor
    a.collab_handler.claim("row", "Hello", [a.collab_handler._key(0, 0)])
    qtbot.waitUntil(lambda: bool(b.collab_handler.claims), timeout=5000)
    bar_b = CollabRowBar(b)
    qtbot.addWidget(bar_b)
    bar_b.refresh(0, 0)
    assert editor.isReadOnly()
    b.collab_handler.leave()
    bar_b.refresh(0, 0)
    assert not editor.isReadOnly()                            # the lock is cleared when the room is left


def test_the_row_menu_claims_the_row_for_the_guest(qtbot, pair, monkeypatch):
    a, b = _host_and_guest(qtbot, pair)
    bar = CollabRowBar(b)
    qtbot.addWidget(bar)
    bar.refresh(0, 0)

    def choose_claim(menu, pos):
        return next(action for action in menu.actions() if action.text() == "Claim for me")

    monkeypatch.setattr(QMenu, "exec", choose_claim)
    bar._open_menu(QPoint(1, 1))
    guest = b.collab_handler._my_id()
    qtbot.waitUntil(lambda: any(c["owner"] == guest for c in a.collab_handler.claims.values()), timeout=5000)


def test_a_fresh_profile_makes_no_network_call_and_lists_no_saved_room(qtbot, pair, monkeypatch):
    import socket

    import requests

    from core.collab.client import RoomClient
    from ui.collab_dialog import CollabDialog

    def no_network(*args, **kwargs):
        raise AssertionError("a fresh profile must not connect anywhere")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    monkeypatch.setattr(RoomClient, "start", no_network)
    a, _b = pair
    dialog = CollabDialog(a, a.collab_handler)
    qtbot.addWidget(dialog)
    assert dialog.saved_list.count() == 0
    assert a.collab_handler.client is None
