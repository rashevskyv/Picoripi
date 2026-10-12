"""The block tree's menu in a room: claim, assign and comment on a block, a virtual folder or a real folder.

A scope is the set of row keys under the item. A block item gives its block; a virtual item (story, speaker,
notated and other family folders) gives the rows of its mappings; any other item is a folder and gives every row
under it. The room decides what the participant may do; the menu only offers the actions its role allows.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QInputDialog, QMenu

from core.collab.roles import CLAIM_OWNERS, allowed
from core.i18n import tr

MAPPINGS_ROLE = Qt.ItemDataRole.UserRole + 13


def keys_of_item(handler: Any, item: Any) -> Tuple[str, str, List[str]]:
    """(scope kind, label, row keys) of one tree item."""
    label = item.text(0)
    mappings = item.data(0, MAPPINGS_ROLE)
    if isinstance(mappings, list) and mappings:
        keys = []
        for pair in mappings:
            try:
                keys.append(handler._key(int(pair[0]), int(pair[1])))
            except (TypeError, ValueError, IndexError):
                continue
        return "virtual", label, keys
    block = item.data(0, Qt.ItemDataRole.UserRole)
    if isinstance(block, int) and block >= 0:
        return "block", label, handler.keys_of_block(block)
    return "folder", label, _keys_under(handler, item)


def _keys_under(handler: Any, item: Any) -> List[str]:
    keys: List[str] = []
    for index in range(item.childCount()):
        child = item.child(index)
        _kind, _label, child_keys = keys_of_item(handler, child)
        keys.extend(child_keys)
    return keys


def install_tree_menu(handler: Any, tree: Any) -> None:
    """Right-click on the block tree offers the room actions. Installed once per tree."""
    if getattr(tree, "_collab_menu_installed", False):
        return
    tree._collab_menu_installed = True
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tree.customContextMenuRequested.connect(lambda pos: show_tree_menu(handler, tree, pos))


def show_tree_menu(handler: Any, tree: Any, pos: Any) -> None:
    item = tree.itemAt(pos)
    if item is None or handler.client is None:
        return
    kind, label, keys = keys_of_item(handler, item)
    if not keys:
        return
    role = handler.role or ""
    menu = QMenu(tree)
    claim = menu.addAction(tr('Claim for me'))
    claim.setEnabled(allowed(role, "claim"))
    assign_menu = menu.addMenu(tr('Assign to…'))
    assign_menu.setEnabled(allowed(role, "assign"))
    for mid, member in handler.members.items():
        if not member.get("banned") and member.get("role") in CLAIM_OWNERS:
            action = assign_menu.addAction(member.get("name", "?"))
            action.setData(mid)
    comment = menu.addAction(tr('Comment…'))
    chosen = menu.exec(tree.viewport().mapToGlobal(pos))
    if chosen is None:
        return
    if chosen is claim:
        handler.claim(kind, label, keys)
    elif chosen is comment:
        text, ok = QInputDialog.getMultiLineText(tree, tr('Comment'), tr('Comment on {scope}:', scope=label), "")
        if ok and text.strip():
            handler.comment(kind, label, keys, text.strip())
    elif chosen in assign_menu.actions() and chosen.data():
        handler.assign(chosen.data(), kind, label, keys)
