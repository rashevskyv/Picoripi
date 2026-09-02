import os
import json
import shutil
import tempfile
from PIL import Image

from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr

from tools.bfn_editor.bfn_engine import extract_bfn_logic
from tools.bfn_editor.bfn_widgets import GridItem


class IoLoadMixin:
    def choose_source(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            tr('Open BFN Font or choose Cancel for extracted folder'),
            filter=tr('BFN Fonts (*.bfn);;All Files (*)')
        )
        if path:
            self.load_bfn(path)
        else:
            self.choose_folder()

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, tr('Select folder containing data.json and sheet_*.png'))
        if not folder:
            return
        if not os.path.exists(os.path.join(folder, 'data.json')):
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Folder does not contain data.json metadata file!'))
            return
        self.load_folder(folder)

    def load_bfn(self, path):
        self.status.showMessage(tr("Loading BFN file: {0}...", os.path.basename(path)))
        self.clear_temp()
        self.temp_dir = tempfile.mkdtemp(prefix="bfn_viewer_")
        
        try:
            extract_bfn_logic(path, self.temp_dir)
            self.bfn_path = path
            self.folder_path = ''
            self.load_from_extracted_dir(self.temp_dir)
            self.status.showMessage(tr("Successfully loaded BFN: {0} (editing in-place)", os.path.basename(path)))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to parse BFN file: {0}', e))
            self.status.showMessage(tr("Failed to load BFN."))
            self.clear_temp()

    def load_bfn_bytes(self, bfn_bytes, bfn_name="fontres.bfn"):
        self.status.showMessage(tr("Loading BFN from archive: {0}...", bfn_name))
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
            self.status.showMessage(tr("Successfully loaded BFN from archive: {0}", bfn_name))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to parse BFN from archive: {0}', e))
            self.status.showMessage(tr("Failed to load BFN from archive."))
            self.clear_temp()

    def load_folder(self, path):
        self.status.showMessage(tr("Loading extracted folder: {0}...", os.path.basename(path)))
        self.clear_temp()
        self.bfn_path = ''
        self.folder_path = path
        try:
            self.load_from_extracted_dir(path)
            self.status.showMessage(tr("Successfully loaded folder: {0}", os.path.basename(path)))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to load folder: {0}', e))
            self.status.showMessage(tr("Failed to load folder."))

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
        self.info_text.setText(tr("Click on any tile in the grid to view and edit its parameters."))
        
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
                tr('Unsaved Changes'),
                tr("You have unsaved changes! Do you want to save them before exiting?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.save_changes()
                self.clear_temp()
                event.accept()
            elif reply == QtWidgets.QMessageBox.StandardButton.No:
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
