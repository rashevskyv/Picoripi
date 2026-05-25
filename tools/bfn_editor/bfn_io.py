import os
import json
import shutil
import tempfile
from PIL import Image

from PyQt5 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic
from tools.bfn_editor.bfn_widgets import GridItem, RenderFontDialog
from tools.bfn_editor.bfn_commands import ImportSheetCommand, ImportGlyphCommand, RenderFontCommand

class BfnIoMixin:
    def choose_source(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            'Open BFN Font or choose Cancel for extracted folder', 
            filter='BFN Fonts (*.bfn);;All Files (*)'
        )
        if path:
            self.load_bfn(path)
        else:
            self.choose_folder()
            
    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select folder containing data.json and sheet_*.png')
        if not folder:
            return
        if not os.path.exists(os.path.join(folder, 'data.json')):
            QtWidgets.QMessageBox.critical(self, 'Error', 'Folder does not contain data.json metadata file!')
            return
        self.load_folder(folder)

    def load_bfn(self, path):
        self.status.showMessage(f"Loading BFN file: {os.path.basename(path)}...")
        self.clear_temp()
        self.temp_dir = tempfile.mkdtemp(prefix="bfn_viewer_")
        
        try:
            extract_bfn_logic(path, self.temp_dir)
            self.bfn_path = path
            self.folder_path = ''
            self.load_from_extracted_dir(self.temp_dir)
            self.status.showMessage(f"Successfully loaded BFN: {os.path.basename(path)} (editing in-place)")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to parse BFN file: {e}')
            self.status.showMessage("Failed to load BFN.")
            self.clear_temp()

    def load_bfn_bytes(self, bfn_bytes, bfn_name="fontres.bfn"):
        self.status.showMessage(f"Loading BFN from archive: {bfn_name}...")
        self.clear_temp()
        self.temp_dir = tempfile.mkdtemp(prefix="bfn_viewer_")
        
        try:
            # Створимо тимчасовий bfn файл
            temp_bfn_path = os.path.join(self.temp_dir, bfn_name)
            with open(temp_bfn_path, 'wb') as f:
                f.write(bfn_bytes)
                
            extract_bfn_logic(temp_bfn_path, self.temp_dir)
            self.bfn_path = temp_bfn_path
            self.folder_path = ''
            self.load_from_extracted_dir(self.temp_dir)
            self.status.showMessage(f"Successfully loaded BFN from archive: {bfn_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to parse BFN from archive: {e}')
            self.status.showMessage("Failed to load BFN from archive.")
            self.clear_temp()

    def load_folder(self, path):
        self.status.showMessage(f"Loading extracted folder: {os.path.basename(path)}...")
        self.clear_temp()
        self.bfn_path = ''
        self.folder_path = path
        try:
            self.load_from_extracted_dir(path)
            self.status.showMessage(f"Successfully loaded folder: {os.path.basename(path)}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to load folder: {e}')
            self.status.showMessage("Failed to load folder.")

    def load_from_extracted_dir(self, dir_path):
        json_path = os.path.join(dir_path, 'data.json')
        with open(json_path, 'r') as f:
            self.metadata = json.load(f)
            
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            if m.get("mapping_type", 0) == 0:
                m["mapping_type"] = 2
                first_char = m.get("first_char", 0)
                last_char = m.get("last_char", 0)
                m["mapping_entry_count"] = last_char - first_char + 1
                m["entries"] = [i for i in range(m["mapping_entry_count"])]
                
        self.load_translation_map()
            
        gly = self.metadata.get("GLY1", [{}])[0]
        self.cell_w = int(gly.get("cell_width", 24))
        self.cell_h = int(gly.get("cell_height", 24))
        self.rows = int(gly.get("glyph_horizontal_count", 5))
        self.cols = int(gly.get("glyph_vertical_count", 5))
        self.real_w = self.cell_w
        self.real_h = self.cell_h
        self.start_glyph = int(gly.get("start_glyph", 0))
        self.end_glyph = int(gly.get("end_glyph", 224))
        
        wid = self.metadata.get("WID1", [{}])[0]
        self.first_code = int(wid.get("first_code_included", 0))
        self.last_code = int(wid.get("last_code_included", 224))
        
        from tools.bfn_editor.bfn_editor_window import ROLE_ARCHIVE_NAME, ROLE_FONT_NAME, ROLE_SHEET_IDX

        # Collect expanded states before clearing the tree
        expanded_keys = set()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.list_sheets)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                archive = item.data(0, ROLE_ARCHIVE_NAME)
                font = item.data(0, ROLE_FONT_NAME)
                sheet = item.data(0, ROLE_SHEET_IDX)
                if sheet is None:
                    expanded_keys.add((archive, font))
            iterator += 1

        self.sheet_images.clear()
        self.list_sheets.clear()
        
        sheet_count = (self.end_glyph - self.start_glyph) // (self.rows * self.cols) + 1
        for s in range(sheet_count):
            png_name = f"sheet_{s}.png"
            png_path = os.path.join(dir_path, png_name)
            if not os.path.exists(png_path):
                img = Image.new("RGBA", (gly.get("texture_width", 128), gly.get("texture_height", 128)), (0,0,0,0))
                img.save(png_path)
                
            qimg = QtGui.QImage(png_path)
            self.sheet_images.append(qimg)
            
        # Build QTreeWidget structure using custom metadata roles
        self.rebuild_tree_widget(sheet_count, expanded_keys=expanded_keys)
            
        if self.grid_item:
            self.scene.removeItem(self.grid_item)
            self.grid_item = None
            
        self.grid_item = GridItem(self.cell_w, self.cell_h, self.rows, self.cols)
        self.scene.addItem(self.grid_item)
        self.grid_item.stackBefore(self.sel_rect_item)
        
        if sheet_count > 0:
            self.set_current_sheet_row(0)
            
        self.selected_cell = None
        self.update_overlays()
        self.info_text.setText("Click on any tile in the grid to view and edit its parameters.")
        
        self.btn_export_sheet.setEnabled(True)
        self.btn_import_sheet.setEnabled(True)
        self.btn_render_font.setEnabled(True)
        self.populate_glyph_table()
        self.update_simulation()
        
        self._set_dirty(False)
        self._sync_with_global_preview_cache()

    def select_sheet(self, index):
        if index < 0 or index >= len(self.sheet_images):
            return
        self.current_sheet_index = index
        self.display_current_sheet()
        
        if self.selected_cell:
            self.populate_info_panel(*self.selected_cell)
            self.update_overlays()

    def display_current_sheet(self):
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.sheet_images):
            return
        qimg = self.sheet_images[self.current_sheet_index]
        self.pixmap_item.setPixmap(QtGui.QPixmap.fromImage(qimg))
        
        w = self.rows * self.real_w
        h = self.cols * self.real_h
        self.scene.setSceneRect(QtCore.QRectF(0, 0, max(w, qimg.width()), max(h, qimg.height())))

    def save_changes(self, silent=False):
        self.status.showMessage("Saving changes...")
        
        target_dir = self.folder_path
        if self.bfn_path:
            if not self.temp_dir or not os.path.exists(self.temp_dir):
                try:
                    self.temp_dir = tempfile.mkdtemp(prefix="bfn_viewer_")
                    self.bfn_path = os.path.join(self.temp_dir, os.path.basename(self.bfn_path))
                except Exception as ex:
                    print(f"Failed to recreate temp_dir during save: {ex}")
            target_dir = self.temp_dir
            
        if not target_dir or not os.path.exists(target_dir):
            details = (
                f"target_dir: '{target_dir}'\n"
                f"self.folder_path: '{self.folder_path}'\n"
                f"self.bfn_path: '{self.bfn_path}'\n"
                f"self.temp_dir: '{self.temp_dir}'\n"
                f"Exists: {os.path.exists(target_dir) if target_dir else False}"
            )
            QtWidgets.QMessageBox.critical(self, 'Error', f'No valid target folder found to save assets!\n\nDetails:\n{details}')
            return
            
        try:
            json_path = os.path.join(target_dir, 'data.json')
            with open(json_path, 'w') as f:
                json.dump(self.metadata, f, indent=4)
                
            for s in range(len(self.sheet_images)):
                png_path = os.path.join(target_dir, f"sheet_{s}.png")
                self.sheet_images[s].save(png_path)
                
            if self.bfn_path:
                repack_bfn_logic(target_dir, self.bfn_path)
                self.status.showMessage(f"Successfully saved and compiled BFN: {os.path.basename(self.bfn_path)}")
                
                with open(self.bfn_path, 'rb') as f:
                    saved_bytes = f.read()
                    
                # Update local cache of this file in archive
                if self.archive_files:
                    self.archive_files[self.current_bfn_name] = saved_bytes
                
                # Якщо це файл з архіву, то викличемо колбек для збереження назад в Picoripi
                if hasattr(self, "archive_save_callback") and self.archive_save_callback:
                    self.archive_save_callback(self.current_bfn_name, saved_bytes)
 
                # Update our font sources cache for this file to avoid out-of-sync
                key = self.archive_name if self.archive_name else self.current_bfn_name
                if key in self.font_sources:
                    self.font_sources[key]["files"][self.current_bfn_name] = saved_bytes
            else:
                self.status.showMessage(f"Successfully saved files in folder: {os.path.basename(target_dir)}")
                
            # Save the virtual translation map if it contains entries,
            # otherwise fall back to auto-generating from MAP1 difference (for unit tests and legacy compatibility)
            if hasattr(self, 'translation_map') and self.translation_map:
                self.save_translation_map()
            elif self.original_font_metadata:
                try:
                    translation_map = self.generate_translation_map()
                    parent_win = self.parent()
                    active_plugin = None
                    mw = None
                    project_dir = None
                    
                    if parent_win:
                        if hasattr(parent_win, "active_game_plugin"):
                            active_plugin = parent_win.active_game_plugin
                            mw = parent_win
                        elif hasattr(parent_win, "mw"):
                            mw = parent_win.mw
                            if hasattr(mw, "active_game_plugin"):
                                active_plugin = mw.active_game_plugin
                                
                    if mw and hasattr(mw, "project_manager") and mw.project_manager and mw.project_manager.project_dir:
                        project_dir = mw.project_manager.project_dir
                    
                    mapping_path = None
                    if project_dir:
                        mapping_path = os.path.join(project_dir, "translation_map.json")
                    elif active_plugin:
                        plugin_dir = os.path.join("plugins", active_plugin)
                        if os.path.exists(plugin_dir):
                            mapping_path = os.path.join(plugin_dir, "translation_map.json")
                    
                    if mapping_path:
                        with open(mapping_path, "w", encoding="utf-8") as f:
                            json.dump(translation_map, f, indent=4, ensure_ascii=False)
                        self.status.showMessage(f"Successfully saved BFN and updated translation_map.json with {len(translation_map)} characters!")
                except Exception as ex:
                    print(f"Failed to auto-generate or save translation map: {ex}")
                
            self._sync_with_global_preview_cache()
            self._set_dirty(False)
            self.changes_saved_during_session = True
            if not silent:
                QtWidgets.QMessageBox.information(self, 'Success', 'All changes saved successfully!')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to save changes: {e}')
            self.status.showMessage("Failed to save changes.")

    def _sync_with_global_preview_cache(self):
        """Sync the current font state with global Picoripi preview cache."""
        parent_mw = None
        if hasattr(self, 'parent') and callable(self.parent):
            parent_mw = self.parent()
        elif hasattr(self, 'mw'):
            parent_mw = self.mw

        if parent_mw:
            try:
                from core.bfn_core import BfnCore
                bfn_cache = BfnCore()
                bfn_cache.metadata = self.metadata
                bfn_cache.gly1 = self.metadata.get("GLY1", [])
                bfn_cache.map1 = self.metadata.get("MAP1", [])
                bfn_cache.wid1 = self.metadata.get("WID1", [])
                bfn_cache.inf1 = self.metadata.get("INF1", [])
                
                # Directly assign QImages list to the cache
                bfn_cache._qimages_cache = list(self.sheet_images)
                
                if not hasattr(parent_mw, 'all_bfn_fonts') or parent_mw.all_bfn_fonts is None:
                    parent_mw.all_bfn_fonts = {}
                    
                name = getattr(self, 'current_bfn_name', 'font.bfn') or 'font.bfn'
                
                parent_mw.all_bfn_fonts[name] = bfn_cache
                parent_mw.all_bfn_fonts[os.path.basename(name)] = bfn_cache
                parent_mw.all_bfn_fonts["default.bfn"] = bfn_cache
                parent_mw.all_bfn_fonts["default"] = bfn_cache
                
                if getattr(self, 'archive_name', None):
                    archive_key = f"{self.archive_name}/{os.path.basename(name)}"
                    parent_mw.all_bfn_fonts[archive_key] = bfn_cache
                
                if hasattr(parent_mw, 'bfn_preview_widget') and parent_mw.bfn_preview_widget:
                    parent_mw.bfn_preview_widget.update()
            except Exception:
                pass

    def clear_temp(self):
        self._table_headers_resized = False
        if hasattr(self, 'auto_sync_timer') and self.auto_sync_timer:
            try:
                self.auto_sync_timer.stop()
            except Exception:
                pass
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = ''

    def closeEvent(self, event):
        if hasattr(self, "save_column_widths"):
            try:
                self.save_column_widths()
            except Exception as e:
                print(f"Error saving column widths on close: {e}")

        if self._dirty:
            reply = QtWidgets.QMessageBox.question(
                self, 
                'Unsaved Changes', 
                "You have unsaved changes! Do you want to save them before exiting?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.save_changes()
                self.clear_temp()
                event.accept()
            elif reply == QtWidgets.QMessageBox.No:
                self.clear_temp()
                event.accept()
            else:
                event.ignore()
        else:
            self.clear_temp()
            event.accept()

        if event.isAccepted() and getattr(self, "changes_saved_during_session", False):
            parent_mw = None
            if hasattr(self, 'parent') and callable(self.parent):
                parent_mw = self.parent()
            elif hasattr(self, 'mw'):
                parent_mw = self.mw
                
            if parent_mw:
                if hasattr(parent_mw, 'settings_manager') and parent_mw.settings_manager:
                    parent_mw.settings_manager.load_all_font_maps()
                elif hasattr(parent_mw, 'font_map_loader'):
                    parent_mw.font_map_loader.load_all_font_maps()
                    
                if hasattr(parent_mw, 'string_settings_updater'):
                    parent_mw.string_settings_updater.update_font_combobox()
                
                if hasattr(parent_mw, 'app_action_handler'):
                    parent_mw.app_action_handler.rescan_all_tags()

    def export_sheet_png(self):
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.sheet_images):
            return
            
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            'Export Sheet PNG', 
            f"sheet_{self.current_sheet_index}.png",
            filter='PNG Images (*.png)'
        )
        if not path:
            return
            
        self.sheet_images[self.current_sheet_index].save(path)
        QtWidgets.QMessageBox.information(self, 'Success', f'Successfully exported sheet to {os.path.basename(path)}')

    def import_sheet_png(self):
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.sheet_images):
            return
            
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            'Import Sheet PNG', 
            filter='PNG Images (*.png)'
        )
        if not path:
            return
            
        new_qimg = QtGui.QImage(path)
        if new_qimg.isNull():
            QtWidgets.QMessageBox.critical(self, 'Error', 'Failed to load selected image!')
            return
            
        curr_qimg = self.sheet_images[self.current_sheet_index]
        if new_qimg.width() != curr_qimg.width() or new_qimg.height() != curr_qimg.height():
            QtWidgets.QMessageBox.critical(
                self, 
                'Error', 
                f'Image dimensions mismatch! Expected {curr_qimg.width()}x{curr_qimg.height()}, got {new_qimg.width()}x{new_qimg.height()}'
            )
            return
            
        cmd = ImportSheetCommand(self, self.current_sheet_index, curr_qimg, new_qimg)
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        QtWidgets.QMessageBox.information(self, 'Success', 'Successfully imported sheet PNG!')

    def export_glyph_png(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        cell_x = gx * self.cell_w
        cell_y = gy * self.cell_h
        glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            'Export Glyph PNG', 
            f"glyph_sheet{self.current_sheet_index}_row{gy}_col{gx}.png",
            filter='PNG Images (*.png)'
        )
        if not path:
            return
            
        glyph_crop.save(path)
        QtWidgets.QMessageBox.information(self, 'Success', f'Successfully exported glyph to {os.path.basename(path)}')

    def import_glyph_png(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        cell_x = gx * self.cell_w
        cell_y = gy * self.cell_h
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            'Import Glyph PNG (Alpha Channel Supported)', 
            filter='PNG Images (*.png)'
        )
        if not path:
            return
            
        new_glyph = QtGui.QImage(path)
        if new_glyph.isNull():
            QtWidgets.QMessageBox.critical(self, 'Error', 'Failed to load selected image!')
            return
            
        if new_glyph.width() != self.cell_w or new_glyph.height() != self.cell_h:
            QtWidgets.QMessageBox.critical(
                self, 
                'Error', 
                f'Glyph dimensions mismatch! Expected {self.cell_w}x{self.cell_h}, got {new_glyph.width()}x{new_glyph.height()}'
            )
            return
            
        old_glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
        
        cmd = ImportGlyphCommand(self, self.current_sheet_index, cell_x, cell_y, old_glyph_crop, new_glyph)
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        QtWidgets.QMessageBox.information(self, 'Success', 'Successfully imported glyph PNG!')

    def render_system_font_to_glyphs(self, selected_glyphs=None):
        if not self.sheet_images:
            return
            
        # 1. Build map of glyphs to characters early for preview support
        glyph_to_char = {}
        maps = self.metadata.get("MAP1", [])
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val = ""
            for m in maps:
                m_type = m.get("mapping_type", 0)
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_type == 0:
                    if m_first <= idx <= m_last:
                        try:
                            char_val = chr(idx)
                        except Exception:
                            pass
                        break
                elif m_type == 2:
                    entries = m.get("entries", [])
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == idx:
                            code = m_first + c_idx
                            try:
                                char_val = chr(code)
                            except Exception:
                                pass
                            break
                    if char_val:
                        break
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == idx:
                            code = entries[k]
                            try:
                                char_val = chr(code)
                            except Exception:
                                pass
                            break
                    if char_val:
                        break
            if char_val:
                if hasattr(self, 'reverse_translation_map') and self.reverse_translation_map:
                    virtual_char = self.reverse_translation_map.get(char_val)
                    if virtual_char:
                        char_val = virtual_char
                glyph_to_char[idx] = char_val
            elif hasattr(self, 'translation_map') and self.translation_map:
                # Glyph has no MAP1 entry: check for a synthetic mapping "#g{idx}"
                synthetic_key = f"#g{idx}"
                virtual_char = self.translation_map.get(synthetic_key, "")
                if virtual_char:
                    glyph_to_char[idx] = virtual_char
                
        # Determine current or fallback glyphs for interactive real-time preview
        has_sel = (selected_glyphs and len(selected_glyphs) > 0) or (self.selected_cell is not None and self.current_sheet_index >= 0)
        
        glyphs_for_preview = []
        if selected_glyphs and len(selected_glyphs) > 0:
            glyphs_for_preview = list(selected_glyphs)
        elif self.selected_cell is not None and self.current_sheet_index >= 0:
            gx, gy = self.selected_cell
            rem = self.current_sheet_index * (self.rows * self.cols) + gy * self.rows + gx
            idx = self.start_glyph + rem
            if self.start_glyph <= idx <= self.end_glyph:
                glyphs_for_preview = [idx]
        else:
            # Fallback: search for first 30 glyphs that have character mappings to preview
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and ch.strip():
                    glyphs_for_preview.append(idx)
                    if len(glyphs_for_preview) >= 30:
                        break
                        
        preview_list = []
        for idx in glyphs_for_preview:
            char_str = glyph_to_char.get(idx, "")
            if not char_str:
                continue
                
            rem = idx - self.start_glyph
            sheet_idx = rem // (self.rows * self.cols)
            cell_idx = rem % (self.rows * self.cols)
            gx = cell_idx % self.rows
            gy = cell_idx // self.rows
            
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            img = None
            if 0 <= sheet_idx < len(self.sheet_images):
                img = self.sheet_images[sheet_idx].copy(cell_x, cell_y, self.cell_w, self.cell_h)
                
            preview_list.append({"char": char_str, "img": img, "idx": idx})
            
        dialog = RenderFontDialog(self, self.cell_w, self.cell_h, has_selected_glyph=has_sel, preview_list=preview_list)
        
        # Set ranges if custom scope is selected
        dialog.spin_start_glyph.setValue(self.start_glyph)
        dialog.spin_end_glyph.setValue(self.end_glyph)
        
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
            
        params = dialog.get_params()
                
        # 2. Determine list of glyphs to render
        scope = params["scope"]
        glyphs_to_render = []
        
        if scope == "selected" and has_sel:
            if selected_glyphs and len(selected_glyphs) > 0:
                glyphs_to_render = list(selected_glyphs)
            else:
                gx, gy = self.selected_cell
                rem = self.current_sheet_index * (self.rows * self.cols) + gy * self.rows + gx
                idx = self.start_glyph + rem
                if self.start_glyph <= idx <= self.end_glyph:
                    glyphs_to_render.append(idx)
        elif scope == "all":
            glyphs_to_render = list(range(self.start_glyph, self.end_glyph + 1))
        elif scope == "cyrillic":
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and "\u0400" <= ch <= "\u04FF":
                    glyphs_to_render.append(idx)
        elif scope == "latin":
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and (("A" <= ch <= "Z") or ("a" <= ch <= "z")):
                    glyphs_to_render.append(idx)
        elif scope == "custom":
            start_g = max(self.start_glyph, params["start_glyph"])
            end_g = min(self.end_glyph, params["end_glyph"])
            glyphs_to_render = list(range(start_g, end_g + 1))
            
        if not glyphs_to_render:
            QtWidgets.QMessageBox.warning(self, "No Glyphs", "No valid glyphs found to render in the selected scope.")
            return
            
        pixel_changes = []
        metrics_changes = []
        
        # Prepare QFont
        font = params["font"]
        h_scale = params.get("h_scale", 100)
        v_scale = params.get("v_scale", 100)
        x_offset = params["x_offset"]
        y_offset = params["y_offset"]
        align_h = params["align_h"]
        align_v = params["align_v"]
        auto_metrics = params["auto_metrics"]
        antialiasing = params["antialiasing"]
        
        # Alignment flags
        alignment = QtCore.Qt.AlignmentFlag(0)
        if align_h is not None:
            alignment |= align_h
        if align_v != "baseline" and align_v is not None:
            alignment |= align_v
            
        ascent = 0
        inf_list = self.metadata.get("INF1", [])
        if inf_list:
            ascent = inf_list[0].get("ascent", 0)
            
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        progress = QtWidgets.QProgressDialog("Rendering glyphs...", "Cancel", 0, len(glyphs_to_render), self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        
        for step, idx in enumerate(glyphs_to_render):
            if progress.wasCanceled():
                break
            progress.setValue(step)
            
            char_str = glyph_to_char.get(idx, "")
            if not char_str:
                continue
                
            rem = idx - self.start_glyph
            sheet_idx = rem // (self.rows * self.cols)
            cell_idx = rem % (self.rows * self.cols)
            gx = cell_idx % self.rows
            gy = cell_idx // self.rows
            
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            sheet_img = self.sheet_images[sheet_idx]
            old_glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
            
            # Render new glyph image
            new_glyph = QtGui.QImage(self.cell_w, self.cell_h, QtGui.QImage.Format_ARGB32)
            new_glyph.fill(QtGui.QColor(0, 0, 0, 0))
            
            painter = QtGui.QPainter(new_glyph)
            if antialiasing:
                painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(255, 255, 255, 255))
            
            # Apply scaling relative to the cell center
            painter.save()
            cx = self.cell_w / 2.0
            cy = self.cell_h / 2.0
            painter.translate(cx, cy)
            painter.scale(h_scale / 100.0, v_scale / 100.0)
            painter.translate(-cx, -cy)
            
            if align_v == "baseline":
                # Draw text aligned on baseline
                font_metrics = QtGui.QFontMetrics(font)
                text_width = font_metrics.horizontalAdvance(char_str)
                x = x_offset
                if align_h == QtCore.Qt.AlignHCenter:
                    x = max(0, (self.cell_w - text_width) // 2) + x_offset
                elif align_h == QtCore.Qt.AlignRight:
                    x = self.cell_w - text_width + x_offset
                
                painter.drawText(x, ascent + y_offset, char_str)
            else:
                rect = QtCore.QRect(x_offset, y_offset, self.cell_w, self.cell_h)
                painter.drawText(rect, alignment, char_str)
                
            painter.restore()
            painter.end()
            
            pixel_changes.append((sheet_idx, cell_x, cell_y, old_glyph_crop, new_glyph))
            
            # Recalculate metrics if requested
            if auto_metrics:
                min_x = -1
                max_x = -1
                for x in range(self.cell_w):
                    has_pixel = False
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(x, y)
                        if color.alpha() > 15:
                            has_pixel = True
                            break
                    if has_pixel:
                        min_x = x
                        break
                        
                for x in range(self.cell_w - 1, -1, -1):
                    has_pixel = False
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(x, y)
                        if color.alpha() > 15:
                            has_pixel = True
                            break
                    if has_pixel:
                        max_x = x
                        break
                        
                if min_x == -1 or max_x == -1:
                    new_kern = 0
                    new_width = self.cell_w // 2
                else:
                    max_block_left = 0
                    current_block = 0
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(min_x, y)
                        if color.alpha() > 15:
                            current_block += 1
                        else:
                            if current_block > max_block_left:
                                max_block_left = current_block
                            current_block = 0
                    if current_block > max_block_left:
                        max_block_left = current_block
                        
                    max_block_right = 0
                    current_block = 0
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(max_x, y)
                        if color.alpha() > 15:
                            current_block += 1
                        else:
                            if current_block > max_block_right:
                                max_block_right = current_block
                            current_block = 0
                    if current_block > max_block_right:
                        max_block_right = current_block
                        
                    if max_block_left < 5:
                        new_kern = min_x
                    else:
                        new_kern = max(0, min_x - 1)
                        
                    if max_block_right < 5:
                        right_boundary = max_x
                    else:
                        right_boundary = max_x + 1
                        
                    new_width = right_boundary - new_kern + 1
                    
                wid_idx = idx - self.first_code
                if 0 <= wid_idx:
                    # Extend packets if this glyph is beyond the current WID1 range
                    if wid_idx >= len(packets):
                        padding_count = wid_idx - len(packets) + 1
                        packets.extend([{"kerning": 0, "width": self.cell_w} for _ in range(padding_count)])
                        wid["last_code_included"] = self.first_code + len(packets)
                    old_kern = packets[wid_idx]["kerning"]
                    old_width = packets[wid_idx]["width"]
                    metrics_changes.append((idx, old_kern, new_kern, old_width, new_width))
                    
        progress.setValue(len(glyphs_to_render))
        
        if pixel_changes:
            cmd = RenderFontCommand(self, pixel_changes, metrics_changes, f"Render Font ({scope})")
            self.undo_stack.push(cmd)
            self._set_dirty(True)
            QtWidgets.QMessageBox.information(
                self, 
                "Success", 
                f"Successfully rendered {len(pixel_changes)} glyphs using the system font!"
            )

    def auto_detect_width(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        cell_x = gx * self.cell_w
        cell_y = gy * self.cell_h
        
        min_x = -1
        max_x = -1
        
        # 1. Scan left-to-right for first pixel with alpha > 15
        for x in range(self.cell_w):
            has_pixel = False
            for y in range(self.cell_h):
                color = sheet_img.pixelColor(cell_x + x, cell_y + y)
                if color.alpha() > 15:
                    has_pixel = True
                    break
            if has_pixel:
                min_x = x
                break
                
        # 2. Scan right-to-left for last pixel with alpha > 15
        for x in range(self.cell_w - 1, -1, -1):
            has_pixel = False
            for y in range(self.cell_h):
                color = sheet_img.pixelColor(cell_x + x, cell_y + y)
                if color.alpha() > 15:
                    has_pixel = True
                    break
            if has_pixel:
                max_x = x
                break
                
        if min_x == -1 or max_x == -1:
            new_kern = 0
            new_width = self.cell_w // 2
        else:
            # Find maximum continuous block in first column (min_x)
            max_block_left = 0
            current_block = 0
            for y in range(self.cell_h):
                color = sheet_img.pixelColor(cell_x + min_x, cell_y + y)
                if color.alpha() > 15:
                    current_block += 1
                else:
                    if current_block > max_block_left:
                        max_block_left = current_block
                    current_block = 0
            if current_block > max_block_left:
                max_block_left = current_block
                
            # Find maximum continuous block in last column (max_x)
            max_block_right = 0
            current_block = 0
            for y in range(self.cell_h):
                color = sheet_img.pixelColor(cell_x + max_x, cell_y + y)
                if color.alpha() > 15:
                    current_block += 1
                else:
                    if current_block > max_block_right:
                        max_block_right = current_block
                    current_block = 0
            if current_block > max_block_right:
                max_block_right = current_block
                
            if max_block_left < 5:
                new_kern = min_x
            else:
                new_kern = max(0, min_x - 1)
                
            if max_block_right < 5:
                right_boundary = max_x
            else:
                right_boundary = max_x + 1
                
            new_width = right_boundary - new_kern + 1
            # clamp width
            new_width = max(1, min(self.cell_w - new_kern, new_width))
            
        # Get old values
        idx = self.get_selected_glyph_index()
        if idx == -1:
            return
            
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = idx - self.first_code
        
        old_kern = 0
        old_width = self.cell_w
        if 0 <= wid_idx < len(packets):
            old_kern = packets[wid_idx]["kerning"]
            old_width = packets[wid_idx]["width"]
            
        if old_kern == new_kern and old_width == new_width:
            return
            
        # Block signals so we don't trigger intermediate commands
        self.spin_kerning.blockSignals(True)
        self.spin_width.blockSignals(True)
        self.spin_kerning.setValue(new_kern)
        self.spin_width.setValue(new_width)
        self.spin_kerning.blockSignals(False)
        self.spin_width.blockSignals(False)
        
        from tools.bfn_editor.bfn_commands import EditMetricsCommand
        cmd = EditMetricsCommand(self, idx, old_kern, new_kern, old_width, new_width)
        self.undo_stack.push(cmd)
        self._set_dirty(True)

    def load_original_bfn_bytes(self, bfn_bytes, bfn_name="fontres.bfn"):
        import tempfile
        import shutil
        from tools.bfn_editor.bfn_engine import extract_bfn_logic
        from PIL import Image
        
        orig_temp_dir = tempfile.mkdtemp(prefix="bfn_original_")
        try:
            temp_bfn_path = os.path.join(orig_temp_dir, bfn_name)
            with open(temp_bfn_path, 'wb') as f:
                f.write(bfn_bytes)
                
            extract_bfn_logic(temp_bfn_path, orig_temp_dir)
            
            # Тепер розпарсимо його метадані та картинки
            json_path = os.path.join(orig_temp_dir, 'data.json')
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    self.original_font_metadata = json.load(f)
                    
                # Нормалізуємо mapping так само як у load_from_extracted_dir
                maps = self.original_font_metadata.get("MAP1", [])
                for m in maps:
                    if m.get("mapping_type", 0) == 0:
                        m["mapping_type"] = 2
                        first_char = m.get("first_char", 0)
                        last_char = m.get("last_char", 0)
                        m["mapping_entry_count"] = last_char - first_char + 1
                        m["entries"] = [i for i in range(m["mapping_entry_count"])]
                        
                gly = self.original_font_metadata.get("GLY1", [{}])[0]
                rows = int(gly.get("glyph_horizontal_count", 5))
                cols = int(gly.get("glyph_vertical_count", 5))
                start_glyph = int(gly.get("start_glyph", 0))
                end_glyph = int(gly.get("end_glyph", 224))
                
                sheet_count = (end_glyph - start_glyph) // (rows * cols) + 1
                self.original_sheet_images = []
                for s in range(sheet_count):
                    png_path = os.path.join(orig_temp_dir, f"sheet_{s}.png")
                    if os.path.exists(png_path):
                        qimg = QtGui.QImage(png_path)
                        self.original_sheet_images.append(qimg)
        finally:
            # Очистимо тимчасову папку для оригінального шрифту
            try:
                shutil.rmtree(orig_temp_dir, ignore_errors=True)
            except Exception:
                pass
