import os
import json
import tempfile

from PyQt6 import QtGui, QtWidgets

from core.i18n import tr

from tools.bfn_editor.bfn_engine import repack_bfn_logic
from tools.bfn_editor.bfn_commands import ImportSheetCommand, ImportGlyphCommand


class IoSaveMixin:
    def save_changes(self, silent=False):
        self.status.showMessage(tr("Saving changes..."))
        
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
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('No valid target folder found to save assets!\n\nDetails:\n{0}', details))
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
                self.status.showMessage(tr("Successfully saved and compiled BFN: {0}", os.path.basename(self.bfn_path)))
                
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
                self.status.showMessage(tr("Successfully saved files in folder: {0}", os.path.basename(target_dir)))
                
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
                        self.status.showMessage(tr("Successfully saved BFN and updated translation_map.json with {0} characters!", len(translation_map)))
                except Exception as ex:
                    print(f"Failed to auto-generate or save translation map: {ex}")
                
            self._sync_with_global_preview_cache()
            self._set_dirty(False)
            self.changes_saved_during_session = True
            if not silent:
                QtWidgets.QMessageBox.information(self, tr('Success'), tr('All changes saved successfully!'))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to save changes: {0}', e))
            self.status.showMessage(tr("Failed to save changes."))

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

    def export_sheet_png(self):
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.sheet_images):
            return
            
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            tr('Export Sheet PNG'),
            f"sheet_{self.current_sheet_index}.png",
            filter=tr('PNG Images (*.png)')
        )
        if not path:
            return
            
        self.sheet_images[self.current_sheet_index].save(path)
        QtWidgets.QMessageBox.information(self, tr('Success'), tr('Successfully exported sheet to {0}', os.path.basename(path)))

    def import_sheet_png(self):
        if self.current_sheet_index < 0 or self.current_sheet_index >= len(self.sheet_images):
            return
            
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            tr('Import Sheet PNG'),
            filter=tr('PNG Images (*.png)')
        )
        if not path:
            return
            
        new_qimg = QtGui.QImage(path)
        if new_qimg.isNull():
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to load selected image!'))
            return
            
        curr_qimg = self.sheet_images[self.current_sheet_index]
        if new_qimg.width() != curr_qimg.width() or new_qimg.height() != curr_qimg.height():
            QtWidgets.QMessageBox.critical(
                self, 
                tr('Error'), 
                tr('Image dimensions mismatch! Expected {0}x{1}, got {2}x{3}', curr_qimg.width(), curr_qimg.height(), new_qimg.width(), new_qimg.height())
            )
            return
            
        cmd = ImportSheetCommand(self, self.current_sheet_index, curr_qimg, new_qimg)
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        QtWidgets.QMessageBox.information(self, tr('Success'), tr('Successfully imported sheet PNG!'))

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
            tr('Export Glyph PNG'),
            f"glyph_sheet{self.current_sheet_index}_row{gy}_col{gx}.png",
            filter=tr('PNG Images (*.png)')
        )
        if not path:
            return
            
        glyph_crop.save(path)
        QtWidgets.QMessageBox.information(self, tr('Success'), tr('Successfully exported glyph to {0}', os.path.basename(path)))

    def import_glyph_png(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        cell_x = gx * self.cell_w
        cell_y = gy * self.cell_h
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            tr('Import Glyph PNG (Alpha Channel Supported)'),
            filter=tr('PNG Images (*.png)')
        )
        if not path:
            return
            
        new_glyph = QtGui.QImage(path)
        if new_glyph.isNull():
            QtWidgets.QMessageBox.critical(self, tr('Error'), tr('Failed to load selected image!'))
            return
            
        if new_glyph.width() != self.cell_w or new_glyph.height() != self.cell_h:
            QtWidgets.QMessageBox.critical(
                self, 
                tr('Error'), 
                tr('Glyph dimensions mismatch! Expected {0}x{1}, got {2}x{3}', self.cell_w, self.cell_h, new_glyph.width(), new_glyph.height())
            )
            return
            
        old_glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
        
        cmd = ImportGlyphCommand(self, self.current_sheet_index, cell_x, cell_y, old_glyph_crop, new_glyph)
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        QtWidgets.QMessageBox.information(self, tr('Success'), tr('Successfully imported glyph PNG!'))
