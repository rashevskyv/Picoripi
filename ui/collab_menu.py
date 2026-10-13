"""The room's menus: one scope menu for the block tree and for the row bar.

A scope is the set of row keys under the item. A block item gives its block; a virtual item (story, speaker,
notated and other family folders) gives the rows of its mappings; any other item is a folder and gives every row
under it; a row gives its own key. The menu offers: Claim for me, Release my claim here, Assign to, Comment, Resolve
the open comments here. The room decides what the participant may do; the menu only offers what the role allows.
"""
from __future__ import annotations

from typing import Any, List, Set, Tuple

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
        _kind, _label, child_keys = keys_of_item(handler, item.child(index))
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
    if keys:
        show_scope_menu(handler, tree, tree.viewport().mapToGlobal(pos), kind, label, keys)


def show_row_menu(handler: Any, widget: Any, pos: Any, key: str) -> None:
    """The row's menu (the row bar): the same items as the tree, for one row."""
    if handler.client is None or not key:
        return
    show_scope_menu(handler, widget, widget.mapToGlobal(pos), "row", handler.describe(key), [key])


def show_scope_menu(handler: Any, parent: Any, global_pos: Any, kind: str, label: str, keys: List[str]) -> None:
    role = handler.role or ""
    scope: Set[str] = set(keys)
    me = handler._my_id()
    mine = any(claim["owner"] == me and not claim["keys"].isdisjoint(scope) for claim in handler.claims.values())
    open_comments = any(not c["resolved"] and (c["keys"] is None or not c["keys"].isdisjoint(scope))
                        for c in handler.comments.values())
    menu = QMenu(parent)
    claim = menu.addAction(tr('Claim for me'))
    claim.setEnabled(allowed(role, "claim"))
    release = menu.addAction(tr('Release my claim here'))
    release.setEnabled(mine)
    assign_menu = menu.addMenu(tr('Assign to…'))
    assign_menu.setEnabled(allowed(role, "assign"))
    for mid, member in handler.members.items():
        if not member.get("banned") and member.get("role") in CLAIM_OWNERS:
            assign_menu.addAction(member.get("name", "?")).setData(mid)
    comment = menu.addAction(tr('Comment…'))
    resolve = menu.addAction(tr('Resolve comments here'))
    resolve.setEnabled(open_comments)
    chosen = menu.exec(global_pos)
    if chosen is None:
        return
    if chosen is claim:
        handler.claim(kind, label, keys)
    elif chosen is release:
        handler.release_mine_in(scope)
    elif chosen is comment:
        text, ok = QInputDialog.getMultiLineText(parent, tr('Comment'), tr('Comment on {scope}:', scope=label), "")
        if ok and text.strip():
            handler.comment(kind, label, keys, text.strip())
    elif chosen is resolve:
        handler.resolve_open_in(scope)
    elif chosen in assign_menu.actions() and chosen.data():
        handler.assign(chosen.data(), kind, label, keys)
