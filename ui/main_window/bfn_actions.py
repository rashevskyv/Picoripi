# ui/main_window/bfn_actions.py
import json
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QInputDialog
from utils.logging_utils import log_info, log_error, log_warning
from bmg_tool import BMGFile, BMGMessage

class BfnActions:
    """Helper class containing BFN Font Editor action methods for MainWindow."""
    def __init__(self, main_window):
        self.mw = main_window

    @property
    def helper(self):
        return self.mw.helper

    def open_bfn_editor_standalone(self):
        """Open BFN Font Editor as a standalone window (no archive binding)."""
        from tools.bfn_editor import BfnEditorWindow
        if not hasattr(self.mw, '_bfn_editor_window') or self.mw._bfn_editor_window is None:
            self.mw._bfn_editor_window = BfnEditorWindow(parent=self.mw)
        
        editor = self.mw._bfn_editor_window
        
        # Initialize simulation input with current text from Picoripi translation editor
        current_text = ""
        ds = getattr(self.mw, 'data_store', None)
        if ds and ds.current_block_idx != -1 and ds.current_string_idx != -1:
            current_text, _ = self.mw.data_processor.get_current_string_text(ds.current_block_idx, ds.current_string_idx)
            if current_text is None:
                current_text = ""
        if current_text:
            sync_enabled = True
            if hasattr(editor, 'chk_sync_sim_text'):
                sync_enabled = editor.chk_sync_sim_text.isChecked()
            if sync_enabled:
                editor.sim_input.setPlainText(current_text)
            
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def open_bfn_editor_for_block(self, block_idx: int):
        """
        Open BFN Font Editor bound to a specific .bfn block (may be inside an archive).
        After saving, updates the archive in RAM and reloads font metrics.
        """
        from tools.bfn_editor import BfnEditorWindow
        from PyQt6.QtWidgets import QMessageBox
        from pathlib import Path

        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project:
            QMessageBox.warning(self.mw, 'BFN Editor', 'No project is open.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'BFN Editor', 'Could not resolve block file.')
            return

        block = pm.project.blocks[proj_b_idx]
        is_archive_member = block.metadata.get('is_archive_member', False)

        editor = BfnEditorWindow(parent=self.mw)
        self.mw._bfn_editor_window = editor

        if is_archive_member:
            archive_rel_path = block.metadata.get('archive_rel_path', '')
            inner_file_name = block.metadata.get('archive_file_name', '')
            try:
                container = pm.get_archive_container(archive_rel_path, is_translation=False)
                bfn_bytes = container.read_file(inner_file_name)
                
                # Collect all BFN files from the archive
                archive_files = {}
                for path in container.list_files():
                    if path.lower().endswith(".bfn"):
                        try:
                            archive_files[path] = container.read_file(path)
                        except Exception:
                            pass
            except Exception as e:
                QMessageBox.critical(self.mw, 'BFN Editor', f'Failed to read .bfn from archive:\n{e}')
                return

            def save_callback(filename: str, new_bytes: bytes):
                """Write updated BFN back into the in-memory archive and persist to disk."""
                try:
                    container.write_file(filename, new_bytes)
                    archive_abs = pm.get_absolute_path(archive_rel_path, is_translation=False)
                    Path(archive_abs).write_bytes(container.pack())
                    log_info(f"BFN Editor: saved '{filename}' back to archive '{archive_rel_path}'.")
                except Exception as ex:
                    QMessageBox.critical(editor, 'BFN Editor', f'Failed to write back to archive:\n{ex}')

            editor.open_from_bytes(
                bfn_bytes,
                bfn_name=inner_file_name,
                save_callback=save_callback,
                font_sync_callback=self._bfn_font_sync,
                archive_name=Path(archive_rel_path).name,
                archive_files=archive_files
            )
        else:
            # Regular file on disk
            src_abs = pm.get_absolute_path(block.source_file, is_translation=False)
            editor.open_from_path(src_abs, font_sync_callback=self._bfn_font_sync)

        # Initialize simulation input with current text from Picoripi translation editor
        current_text = ""
        ds = getattr(self.mw, 'data_store', None)
        if ds and ds.current_block_idx != -1 and ds.current_string_idx != -1:
            current_text, _ = self.mw.data_processor.get_current_string_text(ds.current_block_idx, ds.current_string_idx)
            if current_text is None:
                current_text = ""
        if current_text:
            sync_enabled = True
            if hasattr(editor, 'chk_sync_sim_text'):
                sync_enabled = editor.chk_sync_sim_text.isChecked()
            if sync_enabled:
                editor.sim_input.setPlainText(current_text)

        editor.show()
        editor.raise_()

    def _bfn_font_sync(self):
        """Reload font metrics in Picoripi after BFN editor saves changes."""
        sm = getattr(self.mw, 'settings_manager', None)
        if sm and hasattr(sm, 'load_all_font_maps'):
            sm.load_all_font_maps()
        elif hasattr(self.mw, 'font_map_loader'):
            self.mw.font_map_loader.load_all_font_maps()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
        
        # Trigger UI refresh of text editors and preview widget
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()
            if hasattr(ui, 'populate_strings_for_block'):
                # Force refresh preview text lines cache
                ui.populate_current_view(force=True)
        
        # Proactively trigger silent project-wide recalculation after changes in glyphs
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
            
        log_info("BFN Editor: font metrics reloaded and silent full project recalculation started.")

    def export_current_bmg_to_json(self):
        """Export the currently selected BMG file's text content to a JSON file for inspection."""
        pm = getattr(self.mw, 'project_manager', None)
        ds = getattr(self.mw, 'data_store', None)

        if not pm or not pm.project or ds is None or ds.current_block_idx == -1:
            QMessageBox.warning(self.mw, 'Export BMG', 'No block selected. Please select a BMG block first.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(ds.current_block_idx)
        if proj_b_idx is None or proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'Export BMG', 'Cannot resolve the selected block to a project file.')
            return

        block = pm.project.blocks[proj_b_idx]
        is_archive = block.metadata.get('is_archive_member', False)

        # Determine which BMGs to export: translation first, then source
        def _read_bmg_bytes(is_translation: bool):
            """Internal helper to read bmg bytes."""
            if is_archive:
                arc_rel = block.metadata.get('archive_rel_path', '')
                inner = block.metadata.get('archive_file_name', '')
                try:
                    container = pm.get_archive_container(arc_rel, is_translation=is_translation)
                    return container.read_file(inner), f"{arc_rel}/{inner}"
                except Exception:
                    return None, ''
            else:
                path = pm.get_absolute_path(
                    block.translation_file if is_translation else block.source_file,
                    is_translation=is_translation
                )
                if Path(path).exists() and path.lower().endswith('.bmg'):
                    return Path(path).read_bytes(), path
                return None, ''

        # Try translation first, fallback to source
        raw_trans, label_trans = _read_bmg_bytes(is_translation=True)
        raw_src, label_src = _read_bmg_bytes(is_translation=False)

        if raw_trans is None and raw_src is None:
            QMessageBox.warning(self.mw, 'Export BMG',
                'The selected block does not appear to reference a BMG file.')
            return

        def bmg_bytes_to_dict(raw: bytes, label: str) -> dict:
            """Bmg bytes to dict."""
            bmg = BMGFile()
            bmg.load(raw)
            messages = []
            for msg in bmg.messages:
                d = msg.to_dict()
                d['id'] = getattr(msg, 'id', None)
                messages.append(d)
            return {
                'source': label,
                'encoding': bmg.encoding,
                'endianness': 'big' if bmg.endianness == '>' else 'little',
                'file_id': bmg.id,
                'section_order': bmg.section_order,
                'message_count': len(messages),
                'messages': messages
            }

        export_data = {}
        if raw_src is not None:
            export_data['source'] = bmg_bytes_to_dict(raw_src, label_src)
        if raw_trans is not None:
            export_data['translation'] = bmg_bytes_to_dict(raw_trans, label_trans)

        # Ask where to save
        block_name = block.name.replace('/', '_').replace('\\', '_')
        default_name = f"{block_name}_bmg_export.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self.mw,
            'Export BMG to JSON',
            str(Path.home() / default_name),
            'JSON Files (*.json);;All Files (*)'
        )
        if not save_path:
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self.mw, 'Export BMG',
                f'Successfully exported BMG content to:\n{save_path}\n\n'
                f'Messages: {export_data.get("source", export_data.get("translation", {})).get("message_count", 0)}'
            )
        except Exception as e:
            QMessageBox.critical(self.mw, 'Export BMG', f'Failed to save JSON:\n{e}')

    def import_current_bmg_from_json(self):
        """Import BMG text content from an exported JSON file into the currently selected block."""
        pm = getattr(self.mw, 'project_manager', None)
        ds = getattr(self.mw, 'data_store', None)

        if not pm or not pm.project or ds is None or ds.current_block_idx == -1:
            QMessageBox.warning(self.mw, 'Import BMG', 'No block selected. Please select a BMG block first.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(ds.current_block_idx)
        if proj_b_idx is None or proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'Import BMG', 'Cannot resolve the selected block to a project file.')
            return

        block = pm.project.blocks[proj_b_idx]

        # Choose the JSON file to import
        load_path, _ = QFileDialog.getOpenFileName(
            self.mw,
            'Import BMG from JSON',
            str(Path.home()),
            'JSON Files (*.json);;All Files (*)'
        )
        if not load_path:
            return

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.mw, 'Import BMG', f'Failed to load JSON file:\n{e}')
            return

        # Determine which dictionary to read (translation or source)
        bmg_dict = None
        if 'translation' in import_data and 'source' in import_data:
            items = ["Translation (Current Translation)", "Source (English Original)"]
            item, ok = QInputDialog.getItem(
                self.mw, 
                "Select Data to Import", 
                "The JSON file contains both Source and Translation sections.\nWhich one would you like to import?", 
                items, 
                0, 
                False
            )
            if not ok:
                return
            if item == "Translation (Current Translation)":
                bmg_dict = import_data['translation']
            else:
                bmg_dict = import_data['source']
        elif 'translation' in import_data:
            bmg_dict = import_data['translation']
        elif 'source' in import_data:
            bmg_dict = import_data['source']
        elif 'messages' in import_data:
            bmg_dict = import_data
        else:
            QMessageBox.warning(self.mw, 'Import BMG', 'The selected JSON does not contain valid BMG export data.')
            return

        messages_list = bmg_dict.get('messages', [])
        if not messages_list:
            QMessageBox.warning(self.mw, 'Import BMG', 'No messages found in the JSON file.')
            return

        # Confirm with the user
        reply = QMessageBox.question(
            self.mw,
            'Confirm Import',
            f'This will replace all strings in the current block "{block.name}" with the {len(messages_list)} strings from the JSON file.\n'
            'Do you want to proceed?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Reconstruct the list of strings for the editor
        imported_strings = []
        try:
            for m_dict in messages_list:
                bmg_msg = BMGMessage.from_dict(m_dict)
                editor_text = self.mw.current_game_rules.msg_to_editor_text(bmg_msg)
                imported_strings.append(editor_text)
        except Exception as e:
            QMessageBox.critical(self.mw, 'Import BMG', f'Failed to parse messages from JSON:\n{e}')
            return

        # Remove any existing memory edits for this block first
        keys_to_remove = [k for k in ds.edited_data.keys() if isinstance(k, tuple) and k[0] == ds.current_block_idx]
        for key in keys_to_remove:
            del ds.edited_data[key]

        # Batch insert into edited_data (directly store all strings to ensure 100% clean overwrite)
        for string_idx, text in enumerate(imported_strings):
            ds.edited_data[(ds.current_block_idx, string_idx)] = text

        ds.unsaved_changes = bool(ds.edited_data)
        ds.unsaved_block_indices.add(ds.current_block_idx)

        # Trigger UI refresh
        self.helper.rebuild_unsaved_block_indices()
        
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_title'):
                ui.update_title()
            if hasattr(ui, 'populate_strings_for_block'):
                ui.populate_current_view(force=True)
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()

        # Rescan issues for this block
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler.rescan_issues_for_single_block(ds.current_block_idx)

        QMessageBox.information(
            self.mw,
            'Import BMG',
            f'Successfully imported {len(imported_strings)} strings from JSON into block "{block.name}".\n'
            'The changes are loaded in the editor. Click "Save" to save them to the translation file.'
        )
