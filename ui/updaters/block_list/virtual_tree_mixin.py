"""Build virtual projection roots and related tree helpers."""
from __future__ import annotations

import re
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem, QStyle
from utils.utils import natural_sort_key
from pathlib import Path
from core.mempalace.story_timeline import (
    StoryVirtualFolder,
    StoryVirtualProjection,
)
from core.i18n import tr

class VirtualTreeMixin:
    """Build virtual projection roots and related tree helpers."""

    def _add_virtual_role_leaf(
        self,
        parent,
        label: str,
        block_kind: int,
        identity_role: int,
        identity,
        mappings,
    ):
        mappings = list(mappings)
        if not mappings:
            return None
        item = QTreeWidgetItem([label])
        self._set_item_style_icon(item, 0, QStyle.StandardPixmap.SP_FileDialogDetailedView)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setData(0, Qt.ItemDataRole.UserRole, block_kind)
        item.setData(0, identity_role, identity)
        item.setData(0, Qt.ItemDataRole.UserRole + 4, label)
        item.setData(0, Qt.EditRole, label)
        item.setData(0, Qt.ItemDataRole.UserRole + 13, mappings)
        item.setToolTip(
            0,
            f"{len(mappings)} game strings\n"
            "Drop selected Strings here to assign this attribute manually.\n"
            "You can also right-click and choose an action under MemPalace Context.",
        )
        parent.addChild(item)
        self._register_item_in_cache(item)
        self._apply_virtual_issue_indicators(item)
        return item

    def _apply_virtual_issue_indicators(self, item: QTreeWidgetItem) -> None:
        """Copy physical-block warning ticks onto a virtual folder or leaf."""
        kind = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(kind, int) and kind >= 0:
            return
        mappings = item.data(0, Qt.ItemDataRole.UserRole + 13) or []
        rules = getattr(self.mw, "current_game_rules", None)
        defs = rules.get_problem_definitions() if rules else {}
        if not isinstance(defs, dict):
            defs = {}
        counts = (
            self._get_aggregated_problems_for_block(-2, row_mappings=list(mappings))
            if mappings
            else {pid: 0 for pid in defs}
        )
        item.setData(0, Qt.ItemDataRole.UserRole + 20, dict(counts or {}))
        if not defs:
            self._stamp_item_paint_stats(item)
            return
        label = item.data(0, Qt.ItemDataRole.UserRole + 4)
        if not label:
            label = re.sub(r" \(\d+\)$", "", item.text(0) or "")
            item.setData(0, Qt.ItemDataRole.UserRole + 4, label)
        prior_tip = item.toolTip(0)
        self._apply_issues_and_tooltip(item, label, counts, defs)
        issue_tip = item.toolTip(0)
        if prior_tip and issue_tip:
            item.setToolTip(0, f"{prior_tip}<br><br>{issue_tip}")
        elif prior_tip:
            item.setToolTip(0, prior_tip)

    def _set_virtual_folder_mappings(self, item: QTreeWidgetItem) -> list[tuple[int, int]]:
        """Store the unique rows contained by a virtual folder and all descendants."""
        rows = []
        seen = set()

        def add(values):
            for value in values or ():
                if isinstance(value, (tuple, list)) and len(value) == 2:
                    row = (int(value[0]), int(value[1]))
                    if row not in seen:
                        seen.add(row)
                        rows.append(row)

        add(item.data(0, Qt.ItemDataRole.UserRole + 13))
        for child_idx in range(item.childCount()):
            child = item.child(child_idx)
            if child.childCount():
                add(self._set_virtual_folder_mappings(child))
            else:
                add(child.data(0, Qt.ItemDataRole.UserRole + 13))
        if item.childCount():
            item.setData(0, Qt.ItemDataRole.UserRole + 13, rows)
            kind = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(kind, int) or kind < 0:
                item.setData(0, Qt.ItemDataRole.UserRole + 18, "aggregate")
            item.setToolTip(0, f"{len(rows)} game strings in this folder and its subfolders")
            self._apply_virtual_issue_indicators(item)
        return rows

    def _add_story_folder_item(
        self,
        parent,
        folder: StoryVirtualFolder,
        selected_id,
        allowed_rows: set[tuple[int, int]] | None = None,
        hide_empty: bool = False,
    ) -> bool:
        """Add one normalized story folder recursively and restore selection when possible."""
        mappings = self._story_mapping_indices(folder.mappings)
        overridden_rows, rows_by_structure = self._story_override_index()
        mappings = [row for row in mappings if row not in overridden_rows]
        for row in rows_by_structure.get(folder.id, ()):
            if row not in mappings:
                mappings.append(row)
        if allowed_rows is not None:
            mappings = [row for row in mappings if row in allowed_rows]
        mappings = [row for row in mappings if not self._is_blank_row(*row)]
        if getattr(self.mw.data_store, "show_unsaved_blocks_only", False):
            own_unsaved = any(item in self.mw.data_store.edited_data for item in mappings)
        else:
            own_unsaved = True

        item = QTreeWidgetItem([folder.title])
        icon = (
            QStyle.StandardPixmap.SP_DirIcon
            if folder.children
            else QStyle.StandardPixmap.SP_FileDialogDetailedView
        )
        self._set_item_style_icon(item, 0, icon)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setData(0, Qt.ItemDataRole.UserRole, -2)
        item.setData(0, Qt.ItemDataRole.UserRole + 11, folder.id)
        item.setData(0, Qt.ItemDataRole.UserRole + 4, folder.title)
        item.setData(0, Qt.ItemDataRole.UserRole + 13, mappings)
        item.setToolTip(
            0,
            f"{folder.node_type.title()} · {len(mappings)} linked game strings\n"
            "Drop selected Strings here to link them to this Story structure.",
        )

        child_added = False
        for child in folder.children:
            child_added = self._add_story_folder_item(
                item, child, selected_id, allowed_rows, hide_empty
            ) or child_added
        if hide_empty and not mappings and not child_added:
            return False
        if not own_unsaved and not child_added:
            return False

        parent.addChild(item)
        self._register_item_in_cache(item)
        self._apply_virtual_issue_indicators(item)
        if selected_id == folder.id:
            self.mw.block_list_widget.setCurrentItem(item)
            item.setSelected(True)
            ancestor = item.parent()
            while ancestor is not None:
                ancestor.setExpanded(True)
                ancestor = ancestor.parent()
        return True

    def _add_story_projection_root(
        self,
        parent,
        projection: StoryVirtualProjection,
        allowed_rows: set[tuple[int, int]] | None = None,
        selected_id=None,
    ):
        scope = self._virtual_scope(allowed_rows)
        root = QTreeWidgetItem(["Story"])
        self._set_item_style_icon(root, 0, QStyle.StandardPixmap.SP_DirIcon)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root.setData(0, Qt.ItemDataRole.UserRole + 4, "Story")
        for folder in projection.roots:
            self._add_story_folder_item(
                root, folder, selected_id, scope, True
            )
        if root.childCount() == 0:
            return None
        none_rows = sorted(scope - self._story_linked_rows(projection))
        none_item = self._add_virtual_role_leaf(
            root, "None", -2, Qt.ItemDataRole.UserRole + 11,
            "story:none", none_rows,
        )
        if selected_id == "story:none" and none_item is not None:
            self.mw.block_list_widget.setCurrentItem(none_item)
        if root.childCount() == 0:
            return None
        self._set_virtual_folder_mappings(root)
        parent.addChild(root)
        return root

    def _add_speaker_projection_root(
        self,
        parent,
        speakers: dict[str, list[tuple[int, int]]],
        allowed_rows: set[tuple[int, int]] | None = None,
    ):
        scope = self._virtual_scope(allowed_rows)
        root = QTreeWidgetItem(["Speakers"])
        self._set_item_style_icon(root, 0, QStyle.StandardPixmap.SP_DirIcon)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root.setData(0, Qt.ItemDataRole.UserRole + 4, "Speakers")
        assigned = set()
        for name in sorted(
            (name for name in speakers if name != "None"), key=natural_sort_key
        ):
            rows = [row for row in speakers[name] if row in scope]
            if not rows:
                continue
            assigned.update(rows)
            self._add_virtual_role_leaf(
                root, name, -3, Qt.ItemDataRole.UserRole + 15, name, rows
            )
        if root.childCount() == 0:
            return None
        none_rows = sorted(scope - assigned)
        none_item = self._add_virtual_role_leaf(
            root, "None", -3, Qt.ItemDataRole.UserRole + 15,
            "None", none_rows,
        )
        if none_item is not None:
            root.takeChild(root.indexOfChild(none_item))
            root.insertChild(0, none_item)
        if root.childCount() == 0:
            return None
        self._set_virtual_folder_mappings(root)
        parent.addChild(root)
        return root

    def _add_item_projection_root(
        self,
        parent,
        item_mappings: dict[str, list[tuple[int, int]]],
        allowed_rows: set[tuple[int, int]] | None = None,
    ):
        scope = self._virtual_scope(allowed_rows)
        root = QTreeWidgetItem(["Items"])
        self._set_item_style_icon(root, 0, QStyle.StandardPixmap.SP_DirIcon)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root.setData(0, Qt.ItemDataRole.UserRole + 4, "Items")
        assigned = set()
        for name in sorted(item_mappings, key=natural_sort_key):
            rows = [row for row in item_mappings[name] if row in scope]
            if not rows:
                continue
            assigned.update(rows)
            self._add_virtual_role_leaf(
                root, name, -4, Qt.ItemDataRole.UserRole + 16, name, rows
            )
        if root.childCount() == 0:
            return None
        none_item = self._add_virtual_role_leaf(
            root, "None", -4, Qt.ItemDataRole.UserRole + 16,
            "None", sorted(scope - assigned),
        )
        if none_item is not None:
            root.takeChild(root.indexOfChild(none_item))
            root.insertChild(0, none_item)
        if root.childCount() == 0:
            return None
        self._set_virtual_folder_mappings(root)
        parent.addChild(root)
        return root

    def _notated_rows(self) -> set[tuple[int, int]]:
        """Rows carrying an explicit translator note."""
        return {
            row
            for row, assignment in self._story_context_overrides().items()
            if assignment.get("notated") is True
            and str(assignment.get("translator_note") or "").strip()
        }

    def _add_notated_projection_root(
        self,
        parent,
        allowed_rows: set[tuple[int, int]] | None = None,
    ):
        """Add the independent Notated facet to the virtual tree."""
        scope = self._virtual_scope(allowed_rows)
        noted = sorted(scope & self._notated_rows())
        if not noted:
            return None
        root = QTreeWidgetItem(["Notated"])
        self._set_item_style_icon(root, 0, QStyle.StandardPixmap.SP_DirIcon)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root.setData(0, Qt.ItemDataRole.UserRole + 4, "Notated")
        self._add_virtual_role_leaf(
            root, "Notated", -5, Qt.ItemDataRole.UserRole + 19, "Notated", noted
        )
        self._add_virtual_role_leaf(
            root, "None", -5, Qt.ItemDataRole.UserRole + 19,
            "None", sorted(scope - set(noted)),
        )
        self._set_virtual_folder_mappings(root)
        parent.addChild(root)
        return root

    def _window_kind_groups(self) -> dict[str, set[tuple[int, int]]]:
        if self._window_kind_groups_cache is None:
            groups = {}
            rules = getattr(self.mw, "current_game_rules", None)
            for block_idx, string_idx in sorted(self._all_game_rows()):
                name = "Unknown"
                getter = getattr(rules, "get_preview_window_style", None)
                if callable(getter):
                    try:
                        style = getter(block_idx=block_idx, string_idx=string_idx)
                        candidate = style.get("kind_name") if isinstance(style, dict) else None
                        if isinstance(candidate, str) and candidate.strip():
                            name = candidate.strip()
                    except Exception:
                        pass
                groups.setdefault(name, set()).add((block_idx, string_idx))
            self._window_kind_groups_cache = groups
        cleaned = {}
        for name, rows in self._window_kind_groups_cache.items():
            kept = {row for row in rows if not self._is_blank_row(*row)}
            if kept:
                cleaned[name] = kept
        return cleaned

    def _window_bound_rows(self) -> set[tuple[int, int]]:
        """Rows classified into a concrete Window facet."""
        return {row for rows in self._window_kind_groups().values() for row in rows}

    def _update_string_statistics(self, unbound_rows=None) -> None:
        label = getattr(self.mw, "statistics_status_label", None)
        if label is None:
            return
        total = len(self._all_game_rows())
        unbound = len(unbound_rows or ())
        label.setText(tr("Strings: {0} | Unbound: {1}").format(f"{total:,}", f"{unbound:,}"))

    def _add_windows_projection_root(
        self,
        parent,
        projection: StoryVirtualProjection,
        speakers: dict[str, list[tuple[int, int]]],
        item_mappings: dict[str, list[tuple[int, int]]],
    ):
        windows_root = QTreeWidgetItem([tr("Windows")])
        self._set_item_style_icon(windows_root, 0, QStyle.StandardPixmap.SP_DirIcon)
        windows_root.setFlags(windows_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        windows_root.setData(0, Qt.ItemDataRole.UserRole + 4, "Windows")
        story_rows = self._story_linked_rows(projection)
        speaker_rows = {
            row for name, rows in speakers.items() if name != "None" for row in rows
        }
        item_rows = {row for rows in item_mappings.values() for row in rows}
        for kind_name, rows in sorted(self._window_kind_groups().items(), key=lambda x: x[0].casefold()):
            kind_root = QTreeWidgetItem([tr(kind_name)])
            self._set_item_style_icon(kind_root, 0, QStyle.StandardPixmap.SP_DirIcon)
            kind_root.setFlags(kind_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
            kind_root.setData(0, Qt.ItemDataRole.UserRole + 4, kind_name)
            self._add_story_projection_root(kind_root, projection, rows)
            self._add_speaker_projection_root(kind_root, speakers, rows)
            self._add_item_projection_root(kind_root, item_mappings, rows)
            self._add_notated_projection_root(kind_root, rows)
            unbound = sorted(
                row
                for row in (rows - story_rows - speaker_rows - item_rows)
                if not self._is_blank_row(*row)
            )
            unbound_item = self._add_virtual_role_leaf(
                kind_root, "None", -3, Qt.ItemDataRole.UserRole + 15,
                "None", unbound,
            )
            if unbound_item is not None:
                unbound_item.setData(0, Qt.ItemDataRole.UserRole + 17, "unbound")
            if kind_root.childCount() > 0:
                self._set_virtual_folder_mappings(kind_root)
                windows_root.addChild(kind_root)
        if windows_root.childCount() == 0:
            return None
        self._set_virtual_folder_mappings(windows_root)
        parent.addChild(windows_root)
        return windows_root

    def _set_item_style_icon(self, item: QTreeWidgetItem, column: int, standard_icon_enum) -> None:
        """Internal helper to set the item style icon."""
        try:
            if hasattr(self.mw, 'style') and self.mw.style():
                icon = self.mw.style().standardIcon(standard_icon_enum)
                from PyQt6.QtGui import QIcon
                if isinstance(icon, QIcon) and not icon.isNull():
                    item.setIcon(column, icon)
        except Exception:
            pass

    def _register_item_in_cache(self, item: QTreeWidgetItem):
        """Internal helper to register item in cache."""
        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        if block_idx is not None:
            self._block_items_cache.setdefault(block_idx, []).append(item)

    def _start_chapters_worker_when_ready(self) -> None:
        """Start virtual block loading while the startup progress UI is still visible."""
        worker = self._chapters_load_worker
        if worker is None:
            return
        if not worker.isRunning():
            worker.start()

    def _get_block_display_name_with_ext(self, block_idx: int, base_display_name: str) -> str:
        """Internal helper to get the block display name with ext."""
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            try:
                if (isinstance(proj_b_idx, int) and
                    isinstance(pm.project.blocks, list) and
                    proj_b_idx < len(pm.project.blocks)):

                    block = pm.project.blocks[proj_b_idx]
                    if block is not None and isinstance(getattr(block, 'metadata', None), dict):
                        is_archive = block.metadata.get('is_archive_member', False)
                        if is_archive:
                            orig_filename = block.metadata.get('archive_file_name') or Path(block.source_file).name
                            ext = Path(orig_filename).suffix
                            if ext and not base_display_name.lower().endswith(ext.lower()):
                                return f"{base_display_name}{ext}"
            except Exception:
                pass
        return base_display_name
