# components/tree_context_menu_mixin.py
"""Context-menu mixin for CustomTreeWidget."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMenu, QAction, QStyle, QMessageBox

from utils.logging_utils import log_debug


class TreeContextMenuMixin:
    """Builds and shows the right-click context menu."""

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        selected_items = self.selectedItems()

        if item and item not in selected_items:
            self.setCurrentItem(item)
            item.setSelected(True)
            selected_items = [item]

        main_window = self.window()
        menu = QMenu(self)

        # ── 1. Batch "Move to Folder" ────────────────────────────────────────
        if len(selected_items) > 1:
            act = menu.addAction(
                self.style().standardIcon(QStyle.SP_FileDialogNewFolder),
                f"Move {len(selected_items)} item(s) to folder...",
            )
            pah = getattr(main_window, 'project_action_handler', None)
            if pah and hasattr(pah, 'add_items_to_folder_action'):
                act.triggered.connect(pah.add_items_to_folder_action)
            menu.addSeparator()

        # ── 2. Global import actions ─────────────────────────────────────────
        pm = getattr(main_window, 'project_manager', None)
        if pm:
            aah = getattr(main_window, 'app_action_handler', None)
            pah = getattr(main_window, 'project_action_handler', None)

            add_block = menu.addAction(self.style().standardIcon(QStyle.SP_FileIcon), "Import Block...")
            if aah and hasattr(aah, 'import_block_action'):
                add_block.triggered.connect(aah.import_block_action)

            add_dir = menu.addAction(self.style().standardIcon(QStyle.SP_DirIcon), "Import Directory...")
            if aah and hasattr(aah, 'import_directory_action'):
                add_dir.triggered.connect(aah.import_directory_action)
            elif pah and hasattr(pah, 'import_directory_action'):
                add_dir.triggered.connect(pah.import_directory_action)
            menu.addSeparator()

        # ── Empty-space click: only "Create Folder" ──────────────────────────
        if not item:
            act = menu.addAction(
                self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Folder"
            )
            act.triggered.connect(self._create_folder_at_cursor)
            menu.exec_(self.mapToGlobal(pos))
            return

        from PyQt5.QtCore import QItemSelectionModel
        self.selectionModel().setCurrentIndex(
            self.indexFromItem(item), QItemSelectionModel.Current
        )

        block_idx = item.data(0, Qt.UserRole)
        folder_id = item.data(0, Qt.UserRole + 1)
        merged_ids = item.data(0, Qt.UserRole + 2) or []
        compaction_type = item.data(0, Qt.UserRole + 3)
        pm = getattr(main_window, 'project_manager', None)

        # ── 4. Folder actions ────────────────────────────────────────────────
        if folder_id or merged_ids:
            if merged_ids and len(merged_ids) > 1:
                for f_idx, f_id in enumerate(merged_ids):
                    folder = pm.find_virtual_folder(f_id) if pm else None
                    if folder:
                        if f_idx > 0:
                            menu.addSeparator()
                        header = menu.addAction(
                            self.style().standardIcon(QStyle.SP_DirIcon), f"FOLDER: {folder.name}"
                        )
                        header.setEnabled(False)
                        ren = menu.addAction(
                            self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Folder..."
                        )
                        ren.triggered.connect(
                            lambda checked=False, fid=f_id, name=folder.name: self._rename_folder_by_id(fid, name)
                        )
                        dlt = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Folder")
                        dlt.triggered.connect(
                            lambda checked=False, itm=item, fid=f_id: self._delete_folder_by_id(itm, fid)
                        )
                        sub = menu.addAction(
                            self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Subfolder..."
                        )
                        sub.triggered.connect(
                            lambda checked=False, fid=f_id: self._create_subfolder_by_id(fid)
                        )
                menu.addSeparator()
            else:
                f_id_to_use = folder_id or (merged_ids[0] if merged_ids else None)
                folder = pm.find_virtual_folder(f_id_to_use) if (pm and f_id_to_use) else None
                if folder:
                    if compaction_type == 2:
                        h = menu.addAction(
                            self.style().standardIcon(QStyle.SP_DirIcon), f"FOLDER: {folder.name}"
                        )
                        h.setEnabled(False)
                    ren = menu.addAction(
                        self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Folder..."
                    )
                    ren.triggered.connect(
                        lambda checked=False, fid=folder.id, name=folder.name: self._rename_folder_by_id(fid, name)
                    )
                    dlt = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Folder")
                    dlt.triggered.connect(
                        lambda checked=False, itm=item, fid=folder.id: self._delete_folder_by_id(itm, fid)
                    )
                    sub = menu.addAction(
                        self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Subfolder..."
                    )
                    sub.triggered.connect(
                        lambda checked=False, fid=folder.id: self._create_subfolder_by_id(fid)
                    )
                    menu.addSeparator()

        # ── 4b. Category (virtual block) actions ─────────────────────────────
        category_name = item.data(0, Qt.UserRole + 10)
        if category_name and block_idx is not None:
            lsh = getattr(main_window, 'list_selection_handler', None)
            cat_h = menu.addAction(
                self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                f"VIRTUAL BLOCK: {category_name}",
            )
            cat_h.setEnabled(False)
            if lsh:
                ren = menu.addAction(
                    self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Virtual Block..."
                )
                ren.triggered.connect(
                    lambda checked=False, bidx=block_idx, cname=category_name: lsh.rename_category(bidx, cname)
                )
                dlt = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete Virtual Block")
                dlt.triggered.connect(
                    lambda checked=False, bidx=block_idx, cname=category_name: lsh.delete_category(bidx, cname)
                )
            menu.addSeparator()

        # ── 5. Block actions ─────────────────────────────────────────────────
        if block_idx is not None:
            ds = getattr(main_window, 'data_store', None)
            block_name = (
                ds.block_names.get(str(block_idx), f"Block {block_idx}") if ds else f"Block {block_idx}"
            )

            if compaction_type == 2:
                h = menu.addAction(self.style().standardIcon(QStyle.SP_FileIcon), f"BLOCK: {block_name}")
                h.setEnabled(False)

            lsh = getattr(main_window, 'list_selection_handler', None)
            pah = getattr(main_window, 'project_action_handler', None)

            ren = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Rename Block")
            if lsh and hasattr(lsh, 'rename_block'):
                ren.triggered.connect(lambda checked=False, i=item: lsh.rename_block(i))

            dlt = menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Remove Block")
            if pah and hasattr(pah, 'delete_block_action'):
                dlt.triggered.connect(lambda checked=False: pah.delete_block_action())

            cf = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "Create Folder")
            cf.triggered.connect(self._create_folder_at_cursor)
            menu.addSeparator()

            # Reveal in Explorer sub-menu
            reveal_menu = menu.addMenu(self.style().standardIcon(QStyle.SP_DirOpenIcon), "Reveal in Explorer")
            orig_act = reveal_menu.addAction("Original")
            orig_act.triggered.connect(
                lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=False)
            )
            trans_act = reveal_menu.addAction("Translation")
            trans_act.triggered.connect(
                lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=True)
            )
            menu.addSeparator()

            # Color markers
            marker_definitions = {}
            if main_window.current_game_rules:
                marker_definitions = main_window.current_game_rules.get_color_marker_definitions()

            bh = getattr(main_window, 'block_handler', None)
            if bh:
                current_markers = bh.get_block_color_markers(block_idx)
                for color_name, q_color in self.color_marker_definitions.items():
                    label = marker_definitions.get(color_name, color_name.capitalize())
                    action = QAction(self._create_color_icon(q_color), f"Mark '{label}'", menu)
                    action.setCheckable(True)
                    action.setChecked(color_name in current_markers)
                    action.triggered.connect(
                        lambda checked, b=block_idx, c=color_name: bh.toggle_block_color_marker(b, c)
                    )
                    menu.addAction(action)
            menu.addSeparator()

            # Rescan / Calculate widths
            aah = getattr(main_window, 'app_action_handler', None)
            ish = getattr(main_window, 'issue_scan_handler', None)
            if ish and hasattr(ish, 'rescan_issues_for_single_block'):
                ra = menu.addAction(self.style().standardIcon(QStyle.SP_BrowserReload), "Rescan Issues")
                ra.triggered.connect(lambda checked=False, idx=block_idx: ish.rescan_issues_for_single_block(idx))
            if aah and hasattr(aah, 'calculate_widths_for_block_action'):
                ca = menu.addAction(self.style().standardIcon(QStyle.SP_ComputerIcon), "Calculate Line Widths")
                ca.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: aah.calculate_widths_for_block_action(idx, cname)
                )

            # Spellcheck
            scm = getattr(main_window, 'spellchecker_manager', None)
            if scm and scm.enabled:
                menu.addSeparator()
                sca = menu.addAction(self.style().standardIcon(QStyle.SP_DialogHelpButton), "Spellcheck")
                sca.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: self._open_spellcheck_for_block(idx, cname)
                )

            # AI translation
            translator = getattr(main_window, 'translation_handler', None)
            if translator:
                menu.addSeparator()
                progress = translator.translation_progress.get(block_idx)
                if progress and progress['completed_chunks'] and len(progress['completed_chunks']) < progress['total_chunks']:
                    ra = menu.addAction(self.style().standardIcon(QStyle.SP_MediaPlay), "AI: Resume Translation")
                    ra.triggered.connect(
                        lambda checked=False, idx=block_idx: translator.resume_block_translation(idx)
                    )
                else:
                    action_label = (
                        f"AI: Translate Virtual Block '{category_name}' (UA)"
                        if category_name
                        else f"AI: Translate Block '{block_name}' (UA)"
                    )
                    ta = menu.addAction(self.style().standardIcon(QStyle.SP_MessageBoxInformation), action_label)
                    ta.triggered.connect(
                        lambda checked=False, idx=block_idx, cname=category_name: translator.translate_current_block(idx, cname)
                    )

                glossary_label = (
                    f"AI: Build Glossary for Virtual Block '{category_name}'"
                    if category_name
                    else f"AI: Build Glossary for '{block_name}'"
                )
                ga = menu.addAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), glossary_label)
                ga.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: main_window.build_glossary_with_ai(idx, cname)
                )

            # Revert to original
            menu.addSeparator()
            sel_block_indices = []
            for s_item in self.selectedItems():
                b = s_item.data(0, Qt.UserRole)
                if b is not None and b not in sel_block_indices:
                    sel_block_indices.append(b)

            if len(sel_block_indices) > 1:
                rv = menu.addAction(
                    self.style().standardIcon(QStyle.SP_ArrowBack),
                    f"Revert {len(sel_block_indices)} selected blocks to original",
                )
                rv.triggered.connect(lambda: self._revert_blocks_to_original(sel_block_indices))
            else:
                rv = menu.addAction(
                    self.style().standardIcon(QStyle.SP_ArrowBack),
                    f"Revert '{block_name}' to original",
                )
                rv.triggered.connect(lambda: self._revert_blocks_to_original([block_idx]))

        menu.exec_(self.mapToGlobal(pos))

    # ─────────────────────────────────────────────────────────────────────────

    def _revert_blocks_to_original(self, block_indices: list):
        main_window = self.window()
        if not hasattr(main_window, 'data_processor'):
            return
        reply = QMessageBox.question(
            self,
            "Revert to Original",
            f"Are you sure you want to revert {len(block_indices)} block(s) to their original state?\n\n"
            "All unsaved changes in these blocks will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        main_window.data_processor.revert_blocks_to_original(block_indices)
