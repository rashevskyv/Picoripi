from PyQt5 import QtCore, QtGui, QtWidgets
from tools.bfn_editor.bfn_widgets import FillRangeDialog
from tools.bfn_editor.bfn_commands import EditMetricsCommand, EditMapCommand, BatchMappingCommand

class BfnNavigationMixin:
    def populate_glyph_table(self):
        if not self.sheet_images:
            return
            
        self.table_glyphs.setRowCount(0)
        self.table_glyphs.blockSignals(True)
        
        maps = self.metadata.get("MAP1", [])
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        glyph_to_char = {}
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val = ""
            uni_val = ""
            for m in maps:
                m_type = m.get("mapping_type", 0)
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                
                if m_type == 0:
                    if m_first <= idx <= m_last:
                        try:
                            char_val = chr(idx)
                            uni_val = f"U+{idx:04X}"
                        except Exception:
                            pass
                elif m_type == 2:
                    entries = m.get("entries", [])
                    if idx < len(entries):
                        code = entries[idx]
                        try:
                            char_val = chr(code)
                            uni_val = f"U+{code:04X}"
                        except Exception:
                            pass
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == idx:
                            code = entries[k]
                            try:
                                char_val = chr(code)
                                uni_val = f"U+{code:04X}"
                            except Exception:
                                pass
                            break
            glyph_to_char[idx] = (char_val, uni_val)
            
        orig_glyph_to_char = {}
        if self.original_font_metadata:
            orig_maps = self.original_font_metadata.get("MAP1", [])
            for idx in range(self.start_glyph, self.end_glyph + 1):
                orig_char_val = ""
                orig_uni_val = ""
                for m in orig_maps:
                    m_type = m.get("mapping_type", 0)
                    m_first = m.get("first_char", 0)
                    m_last = m.get("last_char", 0)
                    
                    if m_type == 0:
                        if m_first <= idx <= m_last:
                            try:
                                orig_char_val = chr(idx)
                                orig_uni_val = f"U+{idx:04X}"
                            except Exception:
                                pass
                    elif m_type == 2:
                        entries = m.get("entries", [])
                        if idx < len(entries):
                            code = entries[idx]
                            try:
                                orig_char_val = chr(code)
                                orig_uni_val = f"U+{code:04X}"
                            except Exception:
                                pass
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for k in range(half):
                            if entries[half + k] == idx:
                                code = entries[k]
                                try:
                                    orig_char_val = chr(code)
                                    orig_uni_val = f"U+{code:04X}"
                                except Exception:
                                    pass
                                break
                orig_glyph_to_char[idx] = (orig_char_val, orig_uni_val)
            
        search_query = self.table_search.text().lower()
        
        rows_data = []
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val, uni_val = glyph_to_char.get(idx, ("", ""))
            orig_char_val, _ = orig_glyph_to_char.get(idx, ("", ""))
            
            rem = idx - self.start_glyph
            sheet_idx = rem // (self.rows * self.cols)
            cell_idx = rem % (self.rows * self.cols)
            gx = cell_idx % self.rows
            gy = cell_idx // self.rows
            
            kerning = 0
            width = self.cell_w
            wid_idx = idx - self.first_code
            if 0 <= wid_idx < len(packets):
                kerning = packets[wid_idx]["kerning"]
                width = packets[wid_idx]["width"]
                
            if search_query:
                match = (
                    search_query in str(idx) or
                    search_query in char_val.lower() or
                    search_query in orig_char_val.lower() or
                    search_query in uni_val.lower() or
                    search_query in f"sheet_{sheet_idx}".lower()
                )
                if not match:
                    continue
                    
            rows_data.append((idx, char_val, uni_val, sheet_idx, gx, gy, kerning, width, orig_char_val))
            
        self.table_glyphs.setRowCount(len(rows_data))
        self.table_glyphs.verticalHeader().setDefaultSectionSize(36)
        
        for r_idx, data in enumerate(rows_data):
            idx, char_val, uni_val, sheet_idx, gx, gy, kerning, width, orig_char_val = data
            
            self.table_glyphs.setVerticalHeaderItem(r_idx, QtWidgets.QTableWidgetItem(str(idx)))
            
            item_orig_char = QtWidgets.QTableWidgetItem(orig_char_val)
            item_char = QtWidgets.QTableWidgetItem(char_val)
            item_uni = QtWidgets.QTableWidgetItem(uni_val)
            item_sheet = QtWidgets.QTableWidgetItem(f"Sheet {sheet_idx}")
            item_tile = QtWidgets.QTableWidgetItem(f"Row {gy}, Col {gx}")
            item_kern = QtWidgets.QTableWidgetItem(str(kerning))
            item_width = QtWidgets.QTableWidgetItem(str(width))
            
            for item in (item_orig_char, item_uni, item_sheet, item_tile):
                item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                
            item_char.setFlags(item_char.flags() | QtCore.Qt.ItemIsEditable)
            item_kern.setFlags(item_kern.flags() | QtCore.Qt.ItemIsEditable)
            item_width.setFlags(item_width.flags() | QtCore.Qt.ItemIsEditable)
            
            self.table_glyphs.setItem(r_idx, 1, item_orig_char)
            self.table_glyphs.setItem(r_idx, 3, item_char)
            self.table_glyphs.setItem(r_idx, 4, item_uni)
            self.table_glyphs.setItem(r_idx, 5, item_sheet)
            self.table_glyphs.setItem(r_idx, 6, item_tile)
            self.table_glyphs.setItem(r_idx, 7, item_kern)
            self.table_glyphs.setItem(r_idx, 8, item_width)
            
            # Original Render
            if self.original_sheet_images and 0 <= sheet_idx < len(self.original_sheet_images):
                orig_sheet_img = self.original_sheet_images[sheet_idx]
                cell_x = gx * self.cell_w
                cell_y = gy * self.cell_h
                
                orig_crop = orig_sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
                orig_pixmap = QtGui.QPixmap.fromImage(orig_crop)
                
                orig_lbl = QtWidgets.QLabel()
                orig_lbl.setPixmap(orig_pixmap.scaled(28, 28, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                orig_lbl.setAlignment(QtCore.Qt.AlignCenter)
                bg_color = "#000000"
                orig_lbl.setStyleSheet(f"background-color: {bg_color}; margin: 2px;")
                self.table_glyphs.setCellWidget(r_idx, 0, orig_lbl)
            else:
                orig_lbl = QtWidgets.QLabel()
                bg_color = "#000000"
                orig_lbl.setStyleSheet(f"background-color: {bg_color}; margin: 2px;")
                self.table_glyphs.setCellWidget(r_idx, 0, orig_lbl)
            
            # Translated Render
            if 0 <= sheet_idx < len(self.sheet_images):
                sheet_img = self.sheet_images[sheet_idx]
                cell_x = gx * self.cell_w
                cell_y = gy * self.cell_h
                
                glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
                pixmap = QtGui.QPixmap.fromImage(glyph_crop)
                
                lbl = QtWidgets.QLabel()
                lbl.setPixmap(pixmap.scaled(28, 28, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                lbl.setAlignment(QtCore.Qt.AlignCenter)
                bg_color = "#000000"
                lbl.setStyleSheet(f"background-color: {bg_color}; margin: 2px;")
                self.table_glyphs.setCellWidget(r_idx, 2, lbl)
                
        if not getattr(self, "_table_headers_resized", False):
            # Try to restore column widths from settings
            sm = getattr(self, "get_settings_manager", lambda: None)()
            restored = False
            if sm:
                widths = sm.get("bfn_glyph_table_column_widths")
                if widths and len(widths) == self.table_glyphs.columnCount():
                    for col, w in enumerate(widths):
                        self.table_glyphs.setColumnWidth(col, w)
                    restored = True
            
            if not restored:
                if hasattr(self, "on_header_handle_double_clicked"):
                    for col in range(self.table_glyphs.columnCount()):
                        self.on_header_handle_double_clicked(col)
                else:
                    self.table_glyphs.resizeColumnsToContents()
            
            self._table_headers_resized = True
            
        self.table_glyphs.blockSignals(False)
        
    def refresh_table_row(self, glyph_idx):
        if not self.sheet_images:
            return
            
        found_row = -1
        for row in range(self.table_glyphs.rowCount()):
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if v_header and int(v_header.text()) == glyph_idx:
                found_row = row
                break
                
        if found_row == -1:
            return
            
        self.table_glyphs.blockSignals(True)
        
        maps = self.metadata.get("MAP1", [])
        char_val = ""
        uni_val = ""
        for m in maps:
            m_type = m.get("mapping_type", 0)
            m_first = m.get("first_char", 0)
            m_last = m.get("last_char", 0)
            
            if m_type == 0:
                if m_first <= glyph_idx <= m_last:
                    try:
                        char_val = chr(glyph_idx)
                        uni_val = f"U+{glyph_idx:04X}"
                    except Exception:
                        pass
            elif m_type == 2:
                entries = m.get("entries", [])
                if glyph_idx < len(entries):
                    code = entries[glyph_idx]
                    try:
                        char_val = chr(code)
                        uni_val = f"U+{code:04X}"
                    except Exception:
                        pass
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        code = entries[k]
                        try:
                            char_val = chr(code)
                            uni_val = f"U+{code:04X}"
                        except Exception:
                            pass
                        break
                        
        item_char = self.table_glyphs.item(found_row, 3)
        if item_char:
            item_char.setText(char_val)
        item_uni = self.table_glyphs.item(found_row, 4)
        if item_uni:
            item_uni.setText(uni_val)
            
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = glyph_idx - self.first_code
        kerning = 0
        width = self.cell_w
        if 0 <= wid_idx < len(packets):
            kerning = packets[wid_idx]["kerning"]
            width = packets[wid_idx]["width"]
            
        item_kern = self.table_glyphs.item(found_row, 7)
        if item_kern:
            item_kern.setText(str(kerning))
        item_width = self.table_glyphs.item(found_row, 8)
        if item_width:
            item_width.setText(str(width))
            
        rem = glyph_idx - self.start_glyph
        sheet_idx = rem // (self.rows * self.cols)
        cell_idx = rem % (self.rows * self.cols)
        gx = cell_idx % self.rows
        gy = cell_idx // self.rows
        
        if 0 <= sheet_idx < len(self.sheet_images):
            sheet_img = self.sheet_images[sheet_idx]
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
            pixmap = QtGui.QPixmap.fromImage(glyph_crop)
            
            lbl = QtWidgets.QLabel()
            lbl.setPixmap(pixmap.scaled(28, 28, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            bg_color = "#000000"
            lbl.setStyleSheet(f"background-color: {bg_color}; margin: 2px;")
            self.table_glyphs.setCellWidget(found_row, 2, lbl)
            
        self.table_glyphs.blockSignals(False)

    def on_table_item_changed(self, item):
        if not self.sheet_images:
            return
            
        row = item.row()
        col = item.column()
        
        v_header = self.table_glyphs.verticalHeaderItem(row)
        if not v_header:
            return
        glyph_idx = int(v_header.text())
        
        val_str = item.text()
        self.table_glyphs.blockSignals(True)
        
        try:
            if col == 3:
                # Find old mapping code
                old_code = 0
                maps = self.metadata.get("MAP1", [])
                for m in maps:
                    m_type = m.get("mapping_type", 0)
                    if m_type == 2:
                        entries = m.get("entries", [])
                        if glyph_idx < len(entries):
                            old_code = entries[glyph_idx]
                            break
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for k in range(half):
                            if entries[half + k] == glyph_idx:
                                old_code = entries[k]
                                break
                                
                if len(val_str) > 0:
                    new_code = ord(val_str[0])
                else:
                    new_code = 0
                    
                if old_code == new_code:
                    self.table_glyphs.blockSignals(False)
                    return
                    
                cmd = EditMapCommand(self, glyph_idx, old_code, new_code)
                self.undo_stack.push(cmd)
                self._set_dirty(True)
                    
            elif col == 7:
                try:
                    new_kern = int(val_str)
                    new_kern = max(-128, min(127, new_kern))
                    
                    wid = self.metadata.get("WID1", [{}])[0]
                    packets = wid.get("packets", [])
                    wid_idx = glyph_idx - self.first_code
                    
                    old_kern = 0
                    old_width = self.cell_w
                    if 0 <= wid_idx < len(packets):
                        old_kern = packets[wid_idx]["kerning"]
                        old_width = packets[wid_idx]["width"]
                        
                    if old_kern == new_kern:
                        self.table_glyphs.blockSignals(False)
                        return
                        
                    cmd = EditMetricsCommand(self, glyph_idx, old_kern, new_kern, old_width, old_width)
                    self.undo_stack.push(cmd)
                    self._set_dirty(True)
                except ValueError:
                    pass
                    
            elif col == 8:
                try:
                    new_width = int(val_str)
                    
                    wid = self.metadata.get("WID1", [{}])[0]
                    packets = wid.get("packets", [])
                    wid_idx = glyph_idx - self.first_code
                    
                    old_kern = 0
                    old_width = self.cell_w
                    if 0 <= wid_idx < len(packets):
                        old_kern = packets[wid_idx]["kerning"]
                        old_width = packets[wid_idx]["width"]
                        
                    new_width = max(0, min(self.cell_w - old_kern, new_width))
                    
                    if old_width == new_width:
                        self.table_glyphs.blockSignals(False)
                        return
                        
                    cmd = EditMetricsCommand(self, glyph_idx, old_kern, old_kern, old_width, new_width)
                    self.undo_stack.push(cmd)
                    self._set_dirty(True)
                except ValueError:
                    pass
        except Exception as e:
            print(f"Error updating table metadata: {e}")
            
        self.table_glyphs.blockSignals(False)

    def update_char_mapping(self, glyph_idx, new_code):
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            if m_type == 2:
                entries = m.get("entries", [])
                if glyph_idx < len(entries):
                    entries[glyph_idx] = new_code
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        entries[k] = new_code
                        break

    def on_table_cell_double_clicked(self, row, col):
        if col in (3, 7, 8):
            return
            
        v_header = self.table_glyphs.verticalHeaderItem(row)
        if not v_header:
            return
        glyph_idx = int(v_header.text())
        
        rem = glyph_idx - self.start_glyph
        sheet_idx = rem // (self.rows * self.cols)
        cell_idx = rem % (self.rows * self.cols)
        gx = cell_idx % self.rows
        gy = cell_idx // self.rows
        
        self.tabs.setCurrentIndex(0)
        
        if 0 <= sheet_idx < len(self.sheet_images):
            self.set_current_sheet_row(sheet_idx)
            
        self.selected_cell = (gx, gy)
        self.populate_info_panel(gx, gy)
        self.update_overlays()

    def show_table_context_menu(self, pos):
        if not self.sheet_images:
            return
            
        index = self.table_glyphs.indexAt(pos)
        if not index.isValid():
            return
            
        selected_ranges = self.table_glyphs.selectedRanges()
        selected_rows = set()
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.add(row)
                
        menu = QtWidgets.QMenu(self)
        is_dark = getattr(self, 'is_dark_theme', True)
        if is_dark:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2b2d42;
                    color: #f8f9fa;
                    border: 1px solid #3d405b;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 20px;
                    border-radius: 2px;
                }
                QMenu::item:selected {
                    background-color: #00b4d8;
                    color: #141419;
                    font-weight: bold;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #1e1e24;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 20px;
                    border-radius: 2px;
                    color: #1e1e24;
                }
                QMenu::item:selected {
                    background-color: #0077b6;
                    color: #ffffff;
                    font-weight: bold;
                }
            """)
        
        action_fill = menu.addAction("Fill sequentially From/To...")
        
        action_clear = None
        if len(selected_rows) > 0:
            action_clear = menu.addAction(f"Clear mapping for {len(selected_rows)} selected rows")
            
        action = menu.exec_(self.table_glyphs.viewport().mapToGlobal(pos))
        
        if action == action_fill:
            self.fill_sequence_dialog(index.row())
        elif action_clear and action == action_clear:
            self.clear_selected_mappings(selected_rows)

    def clear_selected_mappings(self, selected_rows):
        if not selected_rows:
            return
            
        changes = []
        for row in selected_rows:
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if not v_header:
                continue
            glyph_idx = int(v_header.text())
            
            # Find old code
            old_code = 0
            maps = self.metadata.get("MAP1", [])
            for m in maps:
                m_type = m.get("mapping_type", 0)
                if m_type == 2:
                    entries = m.get("entries", [])
                    if glyph_idx < len(entries):
                        old_code = entries[glyph_idx]
                        break
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == glyph_idx:
                            old_code = entries[k]
                            break
            changes.append((glyph_idx, old_code, 0))
            
        if not changes:
            return
            
        cmd = BatchMappingCommand(self, changes, f"Clear {len(changes)} Mappings")
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            f"Successfully cleared {len(changes)} character mappings!"
        )

    def fill_sequence_dialog(self, start_row):
        dialog = FillRangeDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            start_code, end_code = dialog.get_range()
            if start_code is None or end_code is None:
                QtWidgets.QMessageBox.warning(self, "Invalid Range", "Failed to parse the start or end character/code.")
                return
                
            if start_code > end_code:
                start_code, end_code = end_code, start_code
                
            total_items = end_code - start_code + 1
            available_rows = self.table_glyphs.rowCount() - start_row
            items_to_fill = min(total_items, available_rows)
            
            if items_to_fill <= 0:
                QtWidgets.QMessageBox.warning(self, "No Space", "No rows available to fill below the selected position.")
                return
                
            changes = []
            for i in range(items_to_fill):
                row = start_row + i
                v_header = self.table_glyphs.verticalHeaderItem(row)
                if not v_header:
                    continue
                glyph_idx = int(v_header.text())
                
                # Find old code
                old_code = 0
                maps = self.metadata.get("MAP1", [])
                for m in maps:
                    m_type = m.get("mapping_type", 0)
                    if m_type == 2:
                        entries = m.get("entries", [])
                        if glyph_idx < len(entries):
                            old_code = entries[glyph_idx]
                            break
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for k in range(half):
                            if entries[half + k] == glyph_idx:
                                old_code = entries[k]
                                break
                                
                new_code = start_code + i
                changes.append((glyph_idx, old_code, new_code))
                
            if not changes:
                return
                
            cmd = BatchMappingCommand(self, changes, f"Fill {len(changes)} Mappings")
            self.undo_stack.push(cmd)
            self._set_dirty(True)
            
            QtWidgets.QMessageBox.information(
                self, 
                "Success", 
                f"Successfully filled {items_to_fill} symbols sequentially!"
            )

    def generate_translation_map(self) -> dict:
        """
        Generate a translation mapping dictionary {trans_char: orig_char} 
        by comparing translated and original MAP1 characters for each glyph.
        """
        translation_map = {}
        if not self.original_font_metadata:
            return translation_map

        maps = self.metadata.get("MAP1", [])
        orig_maps = self.original_font_metadata.get("MAP1", [])

        def get_char_for_glyph(glyph_idx, map_blocks):
            for m in map_blocks:
                m_type = m.get("mapping_type", 0)
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_type == 0:
                    if m_first <= glyph_idx <= m_last:
                        try:
                            return chr(glyph_idx)
                        except Exception:
                            pass
                elif m_type == 2:
                    entries = m.get("entries", [])
                    if glyph_idx < len(entries):
                        code = entries[glyph_idx]
                        if code > 0:
                            try:
                                return chr(code)
                            except Exception:
                                pass
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == glyph_idx:
                            code = entries[k]
                            if code > 0:
                                try:
                                    return chr(code)
                                except Exception:
                                    pass
            return ""

        for idx in range(self.start_glyph, self.end_glyph + 1):
            try:
                trans_char = get_char_for_glyph(idx, maps)
                orig_char = get_char_for_glyph(idx, orig_maps)
                
                if trans_char and orig_char and trans_char != orig_char:
                    if len(trans_char) == 1 and len(orig_char) == 1:
                        # Skip control characters or nul
                        if ord(trans_char) >= 32 and ord(orig_char) >= 32:
                            translation_map[trans_char] = orig_char
            except Exception:
                pass

        return translation_map

