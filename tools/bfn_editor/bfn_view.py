from PyQt5 import QtCore, QtGui, QtWidgets
from tools.bfn_editor.bfn_commands import EditMetricsCommand

class BfnViewMixin:
    def on_scale_spin_changed(self, value):
        self.view.blockSignals(True)
        self.view.set_scale(value)
        self.view.blockSignals(False)

    def on_view_scale_changed(self, scale):
        self.scale_spin.blockSignals(True)
        self.scale_spin.setValue(scale)
        self.scale_spin.blockSignals(False)

    def on_view_clicked(self, p: QtCore.QPointF):
        if self.rows <= 0 or self.cols <= 0:
            return
        gx = int(p.x() // self.real_w)
        gy = int(p.y() // self.real_h)
        
        if gx < 0 or gy < 0 or gx >= self.cols or gy >= self.rows:
            self.selected_cell = None
            self.selected_char_index = -1
            self.selected_sim_item = None
            self.populate_info_panel(-1, -1)
            self.update_overlays()
            self.update_simulation()
            return
            
        self.selected_cell = (gx, gy)
        idx = self.get_selected_glyph_index()
        if idx == -1:
            self.selected_cell = None
            self.selected_char_index = -1
            self.selected_sim_item = None
            self.populate_info_panel(-1, -1)
            self.update_overlays()
            self.update_simulation()
            return
            
        self.populate_info_panel(gx, gy)
        self.update_overlays()

    def navigate_grid(self, dx, dy):
        if self.table_glyphs.hasFocus() or self.sim_input.hasFocus() or self.table_search.hasFocus():
            return
        if not self.sheet_images or self.selected_cell is None:
            return
        gx, gy = self.selected_cell
        gx += dx
        gy += dy
        
        if gx < 0:
            gx = self.cols - 1
            gy -= 1
        elif gx >= self.cols:
            gx = 0
            gy += 1
            
        if gy < 0:
            gy = self.rows - 1
            # Wrap sheet index back
            if self.current_sheet_index > 0:
                self.set_current_sheet_row(self.current_sheet_index - 1)
            else:
                self.set_current_sheet_row(len(self.sheet_images) - 1)
        elif gy >= self.rows:
            gy = 0
            # Wrap sheet index forward
            if self.current_sheet_index < len(self.sheet_images) - 1:
                self.set_current_sheet_row(self.current_sheet_index + 1)
            else:
                self.set_current_sheet_row(0)
                
        self.selected_cell = (gx, gy)
        self.populate_info_panel(gx, gy)
        self.update_overlays()

    def get_selected_glyph_index(self):
        if self.selected_cell is None or self.current_sheet_index < 0:
            return -1
        gx, gy = self.selected_cell
        rem = gy * self.cols + gx
        idx = self.start_glyph + self.current_sheet_index * (self.rows * self.cols) + rem
        if idx > self.end_glyph:
            return -1
        return idx

    def populate_info_panel(self, gx, gy):
        idx = self.get_selected_glyph_index()
        if idx == -1:
            if self.selected_cell is None:
                self.info_text.setText("No glyph selected")
            else:
                self.info_text.setText(f"Cell ({gx}, {gy})\nOut of valid glyph range!")
            self.spin_kerning.setEnabled(False)
            self.spin_width.setEnabled(False)
            self.btn_auto_width.setEnabled(False)
            self.btn_export_glyph.setEnabled(False)
            self.btn_import_glyph.setEnabled(False)
            return
            
        self.spin_kerning.setEnabled(True)
        self.spin_width.setEnabled(True)
        self.btn_auto_width.setEnabled(True)
        self.btn_export_glyph.setEnabled(True)
        self.btn_import_glyph.setEnabled(True)
        
        # Check mapping character
        map_char = "Unknown"
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            m_first = m.get("first_char", 0)
            m_last = m.get("last_char", 0)
            
            if m_type == 0:  # Linear mapping
                if m_first <= idx <= m_last:
                    try:
                        map_char = f"'{chr(idx)}' (Unicode: U+{idx:04X})"
                    except Exception:
                        map_char = f"Unicode: U+{idx:04X}"
            elif m_type == 2:  # Table mapping
                entries = m.get("entries", [])
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == idx:
                        code = m_first + c_idx
                        try:
                            map_char = f"'{chr(code)}' (Unicode: U+{code:04X})"
                        except Exception:
                            map_char = f"Unicode: U+{code:04X}"
                        break
            elif m_type == 3:  # Map mapping
                # Entries contains: [unicode_code_0, unicode_code_1..., glyph_idx_0, glyph_idx_1...]
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == idx:
                        code = entries[k]
                        try:
                            map_char = f"'{chr(code)}' (Unicode: U+{code:04X})"
                        except Exception:
                            map_char = f"Unicode: U+{code:04X}"
                        break
                        
        self.info_text.setText(
            f"Selected Glyph Index: {idx}\n"
            f"Sheet: {self.current_sheet_index}, Cell: ({gx}, {gy})\n"
            f"Mapping: {map_char}"
        )
        
        # Get kerning and width
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        wid_idx = idx - self.first_code
        if 0 <= wid_idx < len(packets):
            pack = packets[wid_idx]
            self.spin_kerning.blockSignals(True)
            self.spin_width.blockSignals(True)
            self.spin_kerning.setValue(pack["kerning"])
            self.spin_width.setValue(pack["width"])
            self.spin_kerning.blockSignals(False)
            self.spin_width.blockSignals(False)
        else:
            self.spin_kerning.blockSignals(True)
            self.spin_width.blockSignals(True)
            self.spin_kerning.setValue(0)
            self.spin_width.setValue(self.cell_w)
            self.spin_kerning.blockSignals(False)
            self.spin_width.blockSignals(False)

    def update_overlays(self):
        if self.selected_cell is None:
            self.sel_rect_item.setVisible(False)
            self.kerning_line_item.setVisible(False)
            self.width_line_item.setVisible(False)
            return
            
        gx, gy = self.selected_cell
        x0 = gx * self.real_w
        y0 = gy * self.real_h
        
        self.sel_rect_item.setRect(QtCore.QRectF(x0, y0, self.cell_w, self.cell_h))
        self.sel_rect_item.setVisible(True)
        
        idx = self.get_selected_glyph_index()
        if idx == -1:
            self.kerning_line_item.setVisible(False)
            self.width_line_item.setVisible(False)
            return
            
        kerning = self.spin_kerning.value()
        width = self.spin_width.value()
        
        left_x = x0 + kerning
        right_x = x0 + kerning + width
        
        self.kerning_line_item.setLine(left_x, y0, left_x, y0 + self.cell_h)
        self.kerning_line_item.setVisible(True)
        
        self.width_line_item.setLine(right_x, y0, right_x, y0 + self.cell_h)
        self.width_line_item.setVisible(True)

    def on_params_changed(self):
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
            
        new_kern = self.spin_kerning.value()
        new_width = self.spin_width.value()
        
        if old_kern == new_kern and old_width == new_width:
            return
            
        cmd = EditMetricsCommand(self, idx, old_kern, new_kern, old_width, new_width)
        self.undo_stack.push(cmd)
        self._set_dirty(True)

    def _set_dirty(self, val):
        self._dirty = val
        self.btn_save.setEnabled(val)
        if val:
            self.status.showMessage("Unsaved changes pending. Click Save or press Ctrl+S to apply.")
            if hasattr(self, 'chk_auto_sync') and self.chk_auto_sync.isChecked():
                self.schedule_auto_sync()
        else:
            self.status.showMessage("All changes saved.")
