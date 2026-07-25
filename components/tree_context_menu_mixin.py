# components/tree_context_menu_mixin.py
"""Context-menu mixin for CustomTreeWidget."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QInputDialog, QMenu, QStyle, QMessageBox, QTreeWidgetItemIterator,
)
from PyQt6.QtGui import QAction

from utils.logging_utils import log_debug


class TreeContextMenuMixin:
    """Builds and shows the right-click context menu."""

    def show_context_menu(self, pos):
        """Show context menu."""
        item = self.itemAt(pos)
        if item:
            text = item.text(0)
            role_val = item.data(0, Qt.UserRole)
            ch_id = item.data(0, Qt.UserRole + 11)
            
            parent = item.parent()
            if text == "Chapters" or (parent and parent.text(0) == "Chapters"):
                # "Chapters" root and "Act X" folders are read-only structures
                return

        selected_items = self.selectedItems()

        if item and item not in selected_items:
            self.setCurrentItem(item)
            item.setSelected(True)
            selected_items = [item]

        main_window = self.window()
        menu = QMenu(self)

        selected_rows = self._selected_editor_assignment_rows()
        if self._add_mempalace_context_menu(menu, selected_rows):
            menu.addSeparator()

        # в”Ђв”Ђ 1. Batch "Move to Folder" в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        if len(selected_items) > 1:
            act = menu.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder),
                f"Move {len(selected_items)} item(s) to folder...",
            )
            pah = getattr(main_window, 'project_action_handler', None)
            if pah and hasattr(pah, 'add_items_to_folder_action'):
                act.triggered.connect(pah.add_items_to_folder_action)
            menu.addSeparator()

        # в”Ђв”Ђ 2. Global import actions в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        pm = getattr(main_window, 'project_manager', None)
        if pm:
            aah = getattr(main_window, 'app_action_handler', None)
            pah = getattr(main_window, 'project_action_handler', None)

            add_block = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), "Import Block...")
            if aah and hasattr(aah, 'import_block_action'):
                add_block.triggered.connect(aah.import_block_action)

            add_dir = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), "Import Directory...")
            if aah and hasattr(aah, 'import_directory_action'):
                add_dir.triggered.connect(aah.import_directory_action)
            elif pah and hasattr(pah, 'import_directory_action'):
                add_dir.triggered.connect(pah.import_directory_action)
            menu.addSeparator()

        # в”Ђв”Ђ Empty-space click: "Create Folder", "Translate All", "Revert All", "Restore All" в”Ђв”Ђ
        if not item:
            act = menu.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), "Create Folder"
            )
            act.triggered.connect(self._create_folder_at_cursor)
            
            has_data = bool(getattr(main_window, 'data_store', None) and getattr(main_window.data_store, 'data', None))
            
            menu.addSeparator()
            
            translator = getattr(main_window, 'translation_handler', None)
            if translator:
                tall = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), "AI: Translate All Blocks (UA Chronological)")
                tall.setEnabled(has_data)
                tall.triggered.connect(lambda: translator.translate_all_blocks_chronologically() if hasattr(translator, "translate_all_blocks_chronologically") else None)
                
            rall = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "Revert All Blocks to Original")
            rall.setEnabled(has_data)
            rall.triggered.connect(self._revert_all_blocks_to_original)
            
            sth = getattr(main_window, 'saved_translations_handler', None)
            if sth:
                rst_all = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "Restore All Translations")
                rst_all.setEnabled(has_data)
                rst_all.triggered.connect(lambda: sth.restore_all_saved_translations_action())
                
            menu.exec(self.mapToGlobal(pos))
            return

        from PyQt6.QtCore import QItemSelectionModel
        self.selectionModel().setCurrentIndex(
            self.indexFromItem(item), QItemSelectionModel.SelectionFlag.Current
        )

        block_idx = item.data(0, Qt.UserRole)
        folder_id = item.data(0, Qt.UserRole + 1)
        merged_ids = item.data(0, Qt.UserRole + 2) or []
        compaction_type = item.data(0, Qt.UserRole + 3)
        pm = getattr(main_window, 'project_manager', None)

        # ── Speaker folder: jump to this speaker's glossary entry ──────────────
        speaker_folder_name = item.data(0, Qt.UserRole + 15)
        if (
            block_idx == -3
            and isinstance(speaker_folder_name, str)
            and speaker_folder_name.strip()
            and speaker_folder_name.strip().casefold() != "none"
        ):
            translator = getattr(main_window, 'translation_handler', None)
            if translator and hasattr(translator, 'show_glossary_dialog'):
                gloss_act = menu.addAction(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
                    f"Open '{speaker_folder_name}' in glossary",
                )
                gloss_act.triggered.connect(
                    lambda checked=False, name=speaker_folder_name:
                    self._open_speaker_in_glossary(name)
                )
                menu.addSeparator()

        # в”Ђв”Ђ 4. Folder actions в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        if folder_id or merged_ids:
            if merged_ids and len(merged_ids) > 1:
                for f_idx, f_id in enumerate(merged_ids):
                    folder = pm.find_virtual_folder(f_id) if pm else None
                    if folder:
                        if f_idx > 0:
                            menu.addSeparator()
                        header = menu.addAction(
                            self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), f"FOLDER: {folder.name}"
                        )
                        header.setEnabled(False)
                        ren = menu.addAction(
                            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Rename Folder..."
                        )
                        ren.triggered.connect(
                            lambda checked=False, fid=f_id, name=folder.name: self._rename_folder_by_id(fid, name)
                        )
                        dlt = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), "Delete Folder")
                        dlt.triggered.connect(
                            lambda checked=False, itm=item, fid=f_id: self._delete_folder_by_id(itm, fid)
                        )
                        sub = menu.addAction(
                            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), "Create Subfolder..."
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
                            self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), f"FOLDER: {folder.name}"
                        )
                        h.setEnabled(False)
                    ren = menu.addAction(
                        self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Rename Folder..."
                    )
                    ren.triggered.connect(
                        lambda checked=False, fid=folder.id, name=folder.name: self._rename_folder_by_id(fid, name)
                    )
                    dlt = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), "Delete Folder")
                    dlt.triggered.connect(
                        lambda checked=False, itm=item, fid=folder.id: self._delete_folder_by_id(itm, fid)
                    )
                    sub = menu.addAction(
                        self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), "Create Subfolder..."
                    )
                    sub.triggered.connect(
                        lambda checked=False, fid=folder.id: self._create_subfolder_by_id(fid)
                    )
                    menu.addSeparator()

        # в”Ђв”Ђ 4b. Category (virtual block) actions в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        category_name = item.data(0, Qt.UserRole + 10)
        if category_name and block_idx is not None:
            lsh = getattr(main_window, 'list_selection_handler', None)
            cat_h = menu.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
                f"VIRTUAL BLOCK: {category_name}",
            )
            cat_h.setEnabled(False)
            if lsh:
                ren = menu.addAction(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Rename Virtual Block..."
                )
                ren.triggered.connect(
                    lambda checked=False, bidx=block_idx, cname=category_name: lsh.rename_category(bidx, cname)
                )
                dlt = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), "Delete Virtual Block")
                dlt.triggered.connect(
                    lambda checked=False, bidx=block_idx, cname=category_name: lsh.delete_category(bidx, cname)
                )
            menu.addSeparator()

        if block_idx is not None:
            ds = getattr(main_window, 'data_store', None)
            if block_idx == -2:
                block_name = item.text(0)
            else:
                block_name = (
                    ds.block_names.get(str(block_idx), f"Block {block_idx}") if ds else f"Block {block_idx}"
                )

            if compaction_type == 2:
                h = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), f"BLOCK: {block_name}")
                h.setEnabled(False)

            lsh = getattr(main_window, 'list_selection_handler', None)
            pah = getattr(main_window, 'project_action_handler', None)

            ren = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Rename Block")
            if lsh and hasattr(lsh, 'rename_block'):
                ren.triggered.connect(lambda checked=False, i=item: lsh.rename_block(i))

            dlt = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon), "Remove Block")
            if pah and hasattr(pah, 'delete_block_action'):
                dlt.triggered.connect(lambda checked=False: pah.delete_block_action())

            cf = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), "Create Folder")
            cf.triggered.connect(self._create_folder_at_cursor)
            menu.addSeparator()

            # Reveal in Explorer sub-menu
            reveal_menu = menu.addMenu(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "Reveal in Explorer")
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

            # Set Default Font
            ssh = getattr(main_window, 'string_settings_handler', None)
            if ssh:
                font_menu = menu.addMenu(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Set Default Font")
                
                # Default option
                default_font_display_text = f"Default ({main_window.default_font_file or 'None'})"
                def_act = font_menu.addAction(default_font_display_text)
                def_act.triggered.connect(
                    lambda checked=False, idx=block_idx: ssh.apply_font_to_block(idx, "default")
                )
                
                all_fonts = getattr(main_window, 'all_font_maps', {})
                if all_fonts:
                    for font_key in sorted(all_fonts.keys()):
                        if font_key != main_window.default_font_file:
                            font_act = font_menu.addAction(font_key)
                            font_act.triggered.connect(
                                lambda checked=False, idx=block_idx, fk=font_key: ssh.apply_font_to_block(idx, fk)
                            )
                menu.addSeparator()

            # Rescan / Calculate widths
            aah = getattr(main_window, 'app_action_handler', None)
            ish = getattr(main_window, 'issue_scan_handler', None)
            if ish and hasattr(ish, 'rescan_issues_for_single_block'):
                ra = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Rescan Issues")
                ra.triggered.connect(lambda checked=False, idx=block_idx: ish.rescan_issues_for_single_block(idx))
            if aah and hasattr(aah, 'calculate_widths_for_block_action'):
                ca = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), "Calculate Line Widths")
                ca.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: aah.calculate_widths_for_block_action(idx, cname)
                )

            # Spellcheck
            scm = getattr(main_window, 'spellchecker_manager', None)
            if scm and scm.enabled:
                menu.addSeparator()
                sca = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton), "Spellcheck")
                sca.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: self._open_spellcheck_for_block(idx, cname)
                )

            # AI translation
            translator = getattr(main_window, 'translation_handler', None)
            if translator:
                menu.addSeparator()
                progress = translator.translation_progress.get(block_idx)
                if progress and progress['completed_chunks'] and len(progress['completed_chunks']) < progress['total_chunks']:
                    ra = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "AI: Resume Translation")
                    ra.triggered.connect(
                        lambda checked=False, idx=block_idx: translator.resume_block_translation(idx)
                    )
                else:
                    action_label = (
                        f"AI: Translate Virtual Block '{category_name}' (UA)"
                        if category_name
                        else (
                            f"AI: Translate Chapter '{block_name}' (UA)"
                            if block_idx == -2
                            else f"AI: Translate Block '{block_name}' (UA)"
                        )
                    )
                    ta = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), action_label)
                    ta.triggered.connect(
                        lambda checked=False, idx=block_idx, cname=category_name, chid=ch_id: translator.translate_current_block(idx, cname, chid)
                    )

                # Translate All option
                tall = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), "AI: Translate All Blocks (UA Chronological)")
                if hasattr(translator, "translate_all_blocks_chronologically"):
                    tall.triggered.connect(lambda checked=False: translator.translate_all_blocks_chronologically())
                else:
                    # Fallback if not fully implemented in UI yet
                    tall.triggered.connect(lambda checked=False: QMessageBox.information(self, "Translate All", "Translating all blocks chronologically according to script. (Will be run in background)"))

                glossary_label = (
                    f"AI: Build Glossary for Virtual Block '{category_name}'"
                    if category_name
                    else f"AI: Build Glossary for '{block_name}'"
                )
                ga = menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), glossary_label)
                ga.triggered.connect(
                    lambda checked=False, idx=block_idx, cname=category_name: main_window.build_glossary_with_ai(idx, cname)
                )

            # Save selected specific changes
            menu.addSeparator()
            selected_strings = self._get_selected_strings_by_block()
            unsaved_strings_in_selection = []
            for b_idx, s_indices in selected_strings.items():
                for s_idx in s_indices:
                    if (b_idx, s_idx) in main_window.data_store.edited_data:
                        unsaved_strings_in_selection.append((b_idx, s_idx))
            
            if len(unsaved_strings_in_selection) > 0:
                if len(selected_strings) > 1:
                    save_label = f"Save changes for selected blocks ({len(unsaved_strings_in_selection)} strings)"
                elif category_name:
                    save_label = f"Save changes for Virtual Block '{category_name}' ({len(unsaved_strings_in_selection)} strings)"
                elif block_idx == -2:
                    save_label = f"Save changes for Chapter '{block_name}' ({len(unsaved_strings_in_selection)} strings)"
                else:
                    save_label = f"Save changes for '{block_name}' ({len(unsaved_strings_in_selection)} strings)"
                    
                sv = menu.addAction(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
                    save_label,
                )
                sv.triggered.connect(lambda checked=False, items=unsaved_strings_in_selection: main_window.data_processor.save_specific_edits(items))

            # Revert to original
            menu.addSeparator()
            total_strings = sum(len(s) for s in selected_strings.values())
            
            if total_strings > 0:
                if len(selected_strings) > 1:
                    label = f"Revert selected blocks to original ({total_strings} strings)"
                elif category_name:
                    label = f"Revert Virtual Block '{category_name}' to original ({total_strings} strings)"
                elif block_idx == -2:
                    label = f"Revert Chapter '{block_name}' to original ({total_strings} strings)"
                else:
                    label = f"Revert '{block_name}' to original ({total_strings} strings)"
                    
                rv = menu.addAction(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack),
                    label,
                )
                rv.triggered.connect(self._revert_selected_to_original)

            # Restore Translated Option in Context Menu
            if hasattr(main_window, 'saved_translations_manager') and main_window.saved_translations_manager:
                selected_strings = self._get_selected_strings_by_block()
                any_saved = False
                for b_idx, s_indices in selected_strings.items():
                    if any(main_window.saved_translations_manager.has_saved_translation(b_idx, s_idx) for s_idx in s_indices):
                        any_saved = True
                        break
                if any_saved:
                    label = "Restore Translated"
                    if block_idx == -2:
                        label = f"Restore Translated for Chapter '{block_name}'"
                    elif category_name:
                        label = f"Restore Translated for Virtual Block '{category_name}'"
                    elif len(selected_strings) > 1:
                        label = f"Restore Translated for {len(selected_strings)} selected blocks"
                    else:
                        label = f"Restore Translated for '{block_name}'"
                        
                    rs = menu.addAction(
                        self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward),
                        label,
                    )
                    rs.triggered.connect(self._restore_selected_translations)

            # BFN Editor for .bfn files
            is_bfn = False
            if pm and pm.project:
                block_map = getattr(main_window, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    fn = block.metadata.get('archive_file_name', '') if block.metadata.get('is_archive_member', False) else block.source_file
                    if fn.lower().endswith('.bfn'):
                        is_bfn = True

            if is_bfn:
                actions = getattr(main_window, 'actions', None)
                if actions and hasattr(actions, 'open_bfn_editor_for_block'):
                    bfn_act = menu.addAction(
                        self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
                        "Edit BFN Font..."
                    )
                    bfn_act.triggered.connect(lambda checked=False, idx=block_idx: actions.open_bfn_editor_for_block(idx))
                    menu.addSeparator()

            # Properties action
            menu.addSeparator()
            prop_act = menu.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
                "Properties..."
            )
            prop_act.triggered.connect(lambda checked=False, idx=block_idx: self._show_block_properties(idx))

        menu.exec(self.mapToGlobal(pos))

    def _mempalace_assignment_targets(self):
        """Return unique editable Memory Palace targets currently shown in the tree."""
        targets = {"story": [], "speaker": [], "item": [], "all": []}
        seen = set()
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            target = self._story_assignment_target(item)
            if target and target[0] in targets:
                facet, value, path = target
                key = (facet, str(value), tuple(path))
                if key not in seen:
                    seen.add(key)
                    targets[facet].append((value, tuple(path), item))
            iterator += 1
        return targets

    def _add_mempalace_context_menu(
        self, menu, selected_rows, preserve_tree_selection=False
    ):
        """Add an explicit choose-operation-then-target Memory Palace menu."""
        targets = self._mempalace_assignment_targets()
        if not any(targets.values()):
            return False

        count = len(selected_rows)
        palace_menu = menu.addMenu(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            f"MemPalace Context ({count} selected)",
        )
        palace_menu.setEnabled(bool(selected_rows))
        preserved_locator = (
            self._virtual_item_locator(self.currentItem())
            if preserve_tree_selection and self.currentItem() is not None
            else None
        )

        definitions = (
            ("story", "Change Chapter / Scene", "None", "story:none"),
            ("speaker", "Change Speaker", "None", "None"),
            ("item", "Change Item", "None", "None"),
        )
        for facet, title, none_label, none_value in definitions:
            entries = list(targets[facet])
            if facet == "story":
                action = palace_menu.addAction(title + "…")
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows),
                    story_entries=tuple(entries), restore_locator=preserved_locator:
                    self._open_story_assignment_dialog(
                        rows, story_entries, restore_locator
                    )
                )
                continue

            if facet == "speaker":
                action = palace_menu.addAction(title + "…")
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows),
                    speaker_entries=tuple(entries), restore_locator=preserved_locator:
                    self._open_speaker_assignment_dialog(
                        rows, speaker_entries, restore_locator
                    )
                )
                continue

            facet_menu = palace_menu.addMenu(title)
            if not any(str(value) == none_value for value, _path, _item in entries):
                entries.append((none_value, (), None))

            def sort_key(entry):
                value, path, _target_item = entry
                label = " › ".join(path) if facet == "story" and path else str(value)
                return (str(value) != none_value, label.casefold())

            for value, path, target_item in sorted(entries, key=sort_key):
                label = (
                    " › ".join(path)
                    if facet == "story" and path
                    else (none_label if str(value) == none_value else str(value))
                )
                action = facet_menu.addAction(label)
                locator = preserved_locator or (
                    self._virtual_item_locator(target_item) if target_item else None
                )
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows), target_facet=facet,
                    target_value=value, target_path=path, target_label=label,
                    target_locator=locator: self._assign_rows_to_story_context(
                        rows,
                        target_facet,
                        target_value,
                        target_path,
                        target_label,
                        target_locator,
                    )
                )

        palace_menu.addSeparator()
        notes_menu = palace_menu.addMenu("Notes")
        note_action = notes_menu.addAction("Add / Edit Notes...")
        note_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._open_note_assignment_dialog(rows, restore_locator)
        )
        from core.story_context_overrides import get_story_context_override
        has_notes = any(
            str(get_story_context_override(self.window(), *row).get("translator_note") or "").strip()
            for row in selected_rows
        )
        clear_note_action = notes_menu.addAction("Remove Notes")
        clear_note_action.setEnabled(has_notes)
        clear_note_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._set_notes_for_rows(rows, "", restore_locator)
        )
        palace_menu.addSeparator()
        clear_action = palace_menu.addAction("Clear All Context")
        clear_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._assign_rows_to_story_context(
                    rows, "all", "None", (), "None", restore_locator
                )
        )
        return True

    def _open_speaker_in_glossary(self, display_name: str) -> None:
        """Open the glossary at the entry for a speaker folder.

        The folder shows the glossary-*translated* speaker name, but the glossary
        is keyed by the source original (``_select_initial_term`` matches
        ``entry.original``). Map the displayed translation back to its original so
        the right row is selected; for an untranslated speaker the displayed name
        already is the original (so the glossary opens ready to add its entry).
        """
        main_window = self.window()
        translator = getattr(main_window, 'translation_handler', None)
        if not translator or not hasattr(translator, 'show_glossary_dialog'):
            return
        original = str(display_name).strip()
        glossary_manager = (
            getattr(translator, '_glossary_manager', None)
            or getattr(getattr(translator, 'glossary_handler', None), 'glossary_manager', None)
        )
        try:
            for entry in (glossary_manager.get_entries() if glossary_manager else []):
                translation = str(getattr(entry, 'translation', '') or '').split(';')[0].strip()
                if translation and translation.casefold() == original.casefold():
                    original = str(getattr(entry, 'original', '') or '').strip() or original
                    break
        except Exception as exc:
            log_debug(f"_open_speaker_in_glossary: reverse lookup failed: {exc}")
        translator.show_glossary_dialog(original)

    def _open_note_assignment_dialog(self, selected_rows, restore_locator=None):
        """Collect one translator note and attach it to all selected rows."""
        if not selected_rows:
            return False
        from core.story_context_overrides import get_story_context_override

        notes = {
            str(get_story_context_override(self.window(), *row).get("translator_note") or "")
            for row in selected_rows
        }
        initial = notes.pop() if len(notes) == 1 else ""
        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Translator Note",
            f"Note for {len(selected_rows)} selected string(s):",
            initial,
        )
        if not accepted:
            return False
        return self._set_notes_for_rows(selected_rows, text, restore_locator)

    def _open_story_assignment_dialog(
        self, selected_rows, entries, restore_locator=None
    ):
        """Choose a nested Story target in a searchable dialog."""
        from components.chapter_picker import ChapterSelectionDialog

        choices = [
            (value, path)
            for value, path, _item in entries
            if str(value) != "story:none" and path
        ]
        dialog = ChapterSelectionDialog(
            choices=choices,
            parent=self.window(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        structure_id, path = dialog.selection()
        value = structure_id if structure_id is not None else "story:none"
        target_item = next(
            (
                item
                for entry_value, entry_path, item in entries
                if entry_value == structure_id and tuple(entry_path) == tuple(path)
            ),
            None,
        )
        label = " › ".join(path) if path else "None"
        locator = restore_locator or (
            self._virtual_item_locator(target_item) if target_item else None
        )
        return self._assign_rows_to_story_context(
            tuple(selected_rows),
            "story",
            value,
            tuple(path),
            label,
            locator,
        )

    def _open_speaker_assignment_dialog(
        self, selected_rows, entries, restore_locator=None
    ):
        """Choose a speaker in a compact searchable dialog."""
        from components.name_picker import SpeakerSelectionDialog

        dialog = SpeakerSelectionDialog(
            [value for value, _path, _item in entries],
            parent=self.window(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        name = dialog.selection()
        target_item = next(
            (item for value, _path, item in entries if str(value) == name),
            None,
        )
        locator = restore_locator or (
            self._virtual_item_locator(target_item) if target_item else None
        )
        return self._assign_rows_to_story_context(
            tuple(selected_rows),
            "speaker",
            name,
            (),
            name,
            locator,
        )

    # в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ

    def _revert_selected_to_original(self):
        """Internal helper to revert selected to original."""
        main_window = self.window()
        if not hasattr(main_window, 'data_processor'):
            return
            
        selected_strings = self._get_selected_strings_by_block()
        if not selected_strings:
            return
            
        total_strings = sum(len(s_indices) for s_indices in selected_strings.values())
        
        reply = QMessageBox.question(
            self,
            "Revert to Original",
            f"Are you sure you want to revert {total_strings} string(s) to their original state?\n\n"
            "All unsaved changes for these strings will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        flat_list = []
        for b_idx, s_indices in selected_strings.items():
            for s_idx in s_indices:
                flat_list.append((b_idx, s_idx))
                
        main_window.data_processor.perform_revert_strings(-2, flat_list, confirm=False)

    def _show_block_properties(self, block_idx: int):
        """Internal helper to show block properties."""
        from .block_properties_dialog import BlockPropertiesDialog
        dialog = BlockPropertiesDialog(self.window(), block_idx)
        dialog.exec()

    def _get_selected_strings_by_block(self) -> dict:
        """Internal helper to get the selected strings by block."""
        main_window = self.window()
        selected_strings = {}
        
        for item in self.selectedItems():
            block_idx = item.data(0, Qt.UserRole)
            category_name = item.data(0, Qt.UserRole + 10)
            ch_id = item.data(0, Qt.UserRole + 11)
            
            if block_idx == -2:
                # Chapter
                composer = getattr(main_window, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()
                        mappings = client.get_chapter_mappings(wing_name, ch_id)
                        for m in mappings:
                            bmg_id = m.get("bmg_id")
                            indices = main_window.list_selection_handler.resolve_bmg_id_to_indices(bmg_id)
                            if indices:
                                b_idx, s_idx = indices
                                selected_strings.setdefault(b_idx, []).append(s_idx)
            elif category_name:
                # Virtual block/category
                if block_idx >= 0 and main_window.project_manager and main_window.project_manager.project:
                    pm = main_window.project_manager
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    proj_b_idx = block_map.get(block_idx, block_idx)
                    if proj_b_idx < len(pm.project.blocks):
                        block = pm.project.blocks[proj_b_idx]
                        category = next((c for c in block.categories if c.name == category_name), None)
                        if category:
                            for s_idx in category.line_indices:
                                selected_strings.setdefault(block_idx, []).append(s_idx)
            elif block_idx is not None and block_idx >= 0:
                # Standard Block
                if main_window.data_store and main_window.data_store.data and block_idx < len(main_window.data_store.data):
                    num_strings = len(main_window.data_store.data[block_idx])
                    selected_strings[block_idx] = list(range(num_strings))
                    
        return selected_strings

    def _restore_selected_translations(self):
        """Internal helper to restore selected translations."""
        main_window = self.window()
        if not hasattr(main_window, 'saved_translations_manager'):
            return
            
        selected_strings = self._get_selected_strings_by_block()
        if not selected_strings:
            return
            
        to_restore_count = 0
        for b_idx, s_indices in selected_strings.items():
            for s_idx in s_indices:
                if main_window.saved_translations_manager.has_saved_translation(b_idx, s_idx):
                    to_restore_count += 1
                    
        if to_restore_count == 0:
            QMessageBox.information(self, "Restore Translation", "No saved translations found for the selection.")
            return
            
        reply = QMessageBox.question(
            self,
            "Restore Translations",
            f"Are you sure you want to restore saved translations for {to_restore_count} string(s)?\n\n"
            "This will overwrite current edits in memory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()
            
        try:
            for b_idx, s_indices in selected_strings.items():
                saved_s_indices = [s_idx for s_idx in s_indices if main_window.saved_translations_manager.has_saved_translation(b_idx, s_idx)]
                if saved_s_indices:
                    main_window.saved_translations_handler.restore_translations_for_strings(b_idx, saved_s_indices)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("RESTORE_STRINGS")

    def _revert_all_blocks_to_original(self):
        """Internal helper to revert all blocks to original."""
        main_window = self.window()
        if not hasattr(main_window, 'data_processor') or not main_window.data_store.data:
            return
            
        num_blocks = len(main_window.data_store.data)
        total_strings = sum(len(main_window.data_store.data[b_idx]) for b_idx in range(num_blocks))
        
        reply = QMessageBox.question(
            self,
            "Revert All Blocks",
            f"Are you sure you want to revert all {total_strings} string(s) across {num_blocks} block(s) to their original state?\n\n"
            "All unsaved changes in the entire project will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        flat_list = []
        for b_idx in range(num_blocks):
            num_strings = len(main_window.data_store.data[b_idx])
            for s_idx in range(num_strings):
                flat_list.append((b_idx, s_idx))
                
        main_window.data_processor.perform_revert_strings(-2, flat_list, confirm=False)
