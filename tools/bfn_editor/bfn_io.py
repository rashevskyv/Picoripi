import os
import json
import shutil
import tempfile
from PIL import Image

from PyQt5 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic
from tools.bfn_editor.bfn_widgets import GridItem
from tools.bfn_editor.bfn_commands import ImportSheetCommand, ImportGlyphCommand

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
                m["entries"] = [first_char + i for i in range(m["mapping_entry_count"])]
            
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
        
        self.populate_glyph_table()
        self.update_simulation()
        
        self._set_dirty(False)

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
            target_dir = self.temp_dir
            
        if not target_dir or not os.path.exists(target_dir):
            QtWidgets.QMessageBox.critical(self, 'Error', 'No valid target folder found to save assets!')
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
                
            # Automatically generate and save translation map if original font is loaded
            if self.original_font_metadata:
                try:
                    translation_map = self.generate_translation_map()
                    parent_win = self.parent()
                    active_plugin = None
                    if parent_win:
                        if hasattr(parent_win, "active_game_plugin"):
                            active_plugin = parent_win.active_game_plugin
                        elif hasattr(parent_win, "mw") and hasattr(parent_win.mw, "active_game_plugin"):
                            active_plugin = parent_win.mw.active_game_plugin
                    
                    if active_plugin:
                        plugin_dir = os.path.join("plugins", active_plugin)
                        if os.path.exists(plugin_dir):
                            mapping_path = os.path.join(plugin_dir, "translation_map.json")
                            with open(mapping_path, "w", encoding="utf-8") as f:
                                json.dump(translation_map, f, indent=4, ensure_ascii=False)
                            self.status.showMessage(f"Successfully saved BFN and updated translation_map.json with {len(translation_map)} characters!")
                except Exception as ex:
                    print(f"Failed to auto-generate or save translation map: {ex}")
                
            self._set_dirty(False)
            if not silent:
                QtWidgets.QMessageBox.information(self, 'Success', 'All changes saved successfully!')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to save changes: {e}')
            self.status.showMessage("Failed to save changes.")

    def clear_temp(self):
        self._table_headers_resized = False
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

    def auto_detect_width(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        cell_x = gx * self.cell_w
        cell_y = gy * self.cell_h
        
        max_x_with_alpha = 0
        
        for x in range(self.cell_w - 1, -1, -1):
            has_pixel = False
            for y in range(self.cell_h):
                color = sheet_img.pixelColor(cell_x + x, cell_y + y)
                if color.alpha() > 15:
                    has_pixel = True
                    break
            if has_pixel:
                max_x_with_alpha = x + 1
                break
                
        detected_width = max(1, max_x_with_alpha + 1)
        self.spin_width.setValue(detected_width)

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
                        m["entries"] = [first_char + i for i in range(m["mapping_entry_count"])]
                        
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
