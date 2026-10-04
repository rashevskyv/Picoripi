"""BFN editor: detect glyph widths; load the original font bytes."""
import os
import json

from PyQt6 import QtGui

from tools.bfn_editor.render_font_dialog import ink_metrics
from utils.logging_utils import log_debug


class IoDetectMixin:
    def auto_detect_width(self):
        if not self.selected_cell or self.current_sheet_index < 0:
            return
            
        gx, gy = self.selected_cell
        sheet_img = self.sheet_images[self.current_sheet_index]
        
        new_kern, new_width = ink_metrics(sheet_img.copy(gx * self.cell_w, gy * self.cell_h, self.cell_w, self.cell_h))
            
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
                        m["linear_count"] = m.get("mapping_entry_count", 0)
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
            except Exception as exc:
                log_debug(f"io_detect_mixin.IoDetectMixin.load_original_bfn_bytes: ignored {exc!r}")
