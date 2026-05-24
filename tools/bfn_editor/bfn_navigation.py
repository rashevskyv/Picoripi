from PyQt5 import QtCore, QtGui, QtWidgets
import os
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
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == idx:
                            code = m_first + c_idx
                            try:
                                char_val = chr(code)
                                uni_val = f"U+{code:04X}"
                            except Exception:
                                pass
                            break
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
            
            font_char_val = char_val
            if char_val and hasattr(self, 'reverse_translation_map') and self.reverse_translation_map:
                virtual_char = self.reverse_translation_map.get(char_val)
                if virtual_char:
                    char_val = virtual_char
            elif not char_val and hasattr(self, 'translation_map') and self.translation_map:
                # Glyph has no MAP1 entry: check for a synthetic mapping "#g{idx}"
                synthetic_key = f"#g{idx}"
                virtual_char = self.translation_map.get(synthetic_key, "")
                if virtual_char:
                    char_val = virtual_char

            glyph_to_char[idx] = (char_val, font_char_val)
            
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
                        for c_idx, g_idx in enumerate(entries):
                            if g_idx == idx:
                                code = m_first + c_idx
                                try:
                                    orig_char_val = chr(code)
                                    orig_uni_val = f"U+{code:04X}"
                                except Exception:
                                    pass
                                break
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
            char_val, font_char_val = glyph_to_char.get(idx, ("", ""))
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
                    search_query in font_char_val.lower() or
                    search_query in f"sheet_{sheet_idx}".lower()
                )
                if not match:
                    continue
                    
            rows_data.append((idx, char_val, font_char_val, sheet_idx, gx, gy, kerning, width, orig_char_val))
            
        self.table_glyphs.setRowCount(len(rows_data))
        self.table_glyphs.verticalHeader().setDefaultSectionSize(36)
        
        for r_idx, data in enumerate(rows_data):
            idx, char_val, font_char_val, sheet_idx, gx, gy, kerning, width, orig_char_val = data
            
            self.table_glyphs.setVerticalHeaderItem(r_idx, QtWidgets.QTableWidgetItem(str(idx)))
            
            item_orig_char = QtWidgets.QTableWidgetItem(orig_char_val)
            item_char = QtWidgets.QTableWidgetItem(char_val)
            item_font_char = QtWidgets.QTableWidgetItem(font_char_val)
            item_sheet = QtWidgets.QTableWidgetItem(f"Sheet {sheet_idx}")
            item_tile = QtWidgets.QTableWidgetItem(f"Row {gy}, Col {gx}")
            item_kern = QtWidgets.QTableWidgetItem(str(kerning))
            item_width = QtWidgets.QTableWidgetItem(str(width))
            
            for item in (item_orig_char, item_font_char, item_sheet, item_tile):
                item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                
            # Visually mark Font Char as read-only
            if getattr(self, "is_dark_theme", True):
                item_font_char.setForeground(QtGui.QBrush(QtGui.QColor("#88888b")))
                item_font_char.setBackground(QtGui.QBrush(QtGui.QColor("#1a1a20")))
            else:
                item_font_char.setForeground(QtGui.QBrush(QtGui.QColor("#7e8a9b")))
                item_font_char.setBackground(QtGui.QBrush(QtGui.QColor("#eef1f6")))
            item_font_char.setToolTip("Font Character (read-only, stored in font metadata)")
                
            item_char.setFlags(item_char.flags() | QtCore.Qt.ItemIsEditable)
            item_kern.setFlags(item_kern.flags() | QtCore.Qt.ItemIsEditable)
            item_width.setFlags(item_width.flags() | QtCore.Qt.ItemIsEditable)
            
            self.table_glyphs.setItem(r_idx, 1, item_orig_char)
            self.table_glyphs.setItem(r_idx, 3, item_char)
            self.table_glyphs.setItem(r_idx, 4, item_font_char)
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
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == glyph_idx:
                        code = m_first + c_idx
                        try:
                            char_val = chr(code)
                            uni_val = f"U+{code:04X}"
                        except Exception:
                            pass
                        break
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
                        
        font_char_val = char_val
        if char_val and hasattr(self, 'reverse_translation_map') and self.reverse_translation_map:
            virtual_char = self.reverse_translation_map.get(char_val)
            if virtual_char:
                char_val = virtual_char
        elif not char_val and hasattr(self, 'translation_map') and self.translation_map:
            # Glyph has no MAP1 entry: check for a synthetic mapping "#g{glyph_idx}"
            synthetic_key = f"#g{glyph_idx}"
            virtual_char = self.translation_map.get(synthetic_key, "")
            if virtual_char:
                char_val = virtual_char
                
        item_char = self.table_glyphs.item(found_row, 3)
        if item_char:
            item_char.setText(char_val)
        item_font_char = self.table_glyphs.item(found_row, 4)
        if item_font_char:
            item_font_char.setText(font_char_val)
            if getattr(self, "is_dark_theme", True):
                item_font_char.setForeground(QtGui.QBrush(QtGui.QColor("#88888b")))
                item_font_char.setBackground(QtGui.QBrush(QtGui.QColor("#1a1a20")))
            else:
                item_font_char.setForeground(QtGui.QBrush(QtGui.QColor("#7e8a9b")))
                item_font_char.setBackground(QtGui.QBrush(QtGui.QColor("#eef1f6")))
            item_font_char.setToolTip("Font Character (read-only, stored in font metadata)")
            
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
                # 1. Get the original character of this glyph from the font MAP1 metadata
                orig_char = self.get_original_char_for_glyph(glyph_idx)
                
                # Synthetic key used when the glyph has no MAP1 entry (empty glyph)
                synthetic_key = f"#g{glyph_idx}"
                
                # 2. Get the new virtual character typed by the user
                new_virtual_char = val_str[0] if len(val_str) > 0 else ""
                
                if orig_char:
                    # Normal case: glyph has a physical char in MAP1
                    # 3. Get the old virtual character from self.reverse_translation_map
                    old_virtual_char = self.reverse_translation_map.get(orig_char, "")
                    
                    if old_virtual_char == new_virtual_char:
                        self.table_glyphs.blockSignals(False)
                        return
                    
                    # 4. Update the translation maps in memory
                    if orig_char in self.reverse_translation_map:
                        del self.reverse_translation_map[orig_char]
                    if old_virtual_char in self.translation_map:
                        del self.translation_map[old_virtual_char]
                        
                    if new_virtual_char:
                        duplicate_orig = self.translation_map.get(new_virtual_char)
                        if duplicate_orig:
                            if duplicate_orig in self.reverse_translation_map:
                                del self.reverse_translation_map[duplicate_orig]
                            del self.translation_map[new_virtual_char]
                            
                        self.translation_map[new_virtual_char] = orig_char
                        self.reverse_translation_map[orig_char] = new_virtual_char
                else:
                    # Empty glyph case: no MAP1 entry.
                    # Automatically initialize a physical mapping in MAP1 for this empty glyph!
                    physical_code = glyph_idx
                    self.update_char_mapping(glyph_idx, physical_code)
                    orig_char = chr(physical_code)
                    
                    # Update table row to reflect physical mapping instantly in Font Char column
                    item_font_char = self.table_glyphs.item(row, 2)
                    if item_font_char:
                        item_font_char.setText(orig_char)
                        
                    # Now fallback to normal flow because orig_char is set!
                    old_virtual_char = self.reverse_translation_map.get(orig_char, "")
                    
                    if old_virtual_char == new_virtual_char:
                        self.table_glyphs.blockSignals(False)
                        return
                    
                    if orig_char in self.reverse_translation_map:
                        del self.reverse_translation_map[orig_char]
                    if old_virtual_char in self.translation_map:
                        del self.translation_map[old_virtual_char]
                        
                    if new_virtual_char:
                        duplicate_orig = self.translation_map.get(new_virtual_char)
                        if duplicate_orig:
                            if duplicate_orig in self.reverse_translation_map:
                                del self.reverse_translation_map[duplicate_orig]
                            del self.translation_map[new_virtual_char]
                            
                        self.translation_map[new_virtual_char] = orig_char
                        self.reverse_translation_map[orig_char] = new_virtual_char
                
                # 5. Save the updated translation map to disk
                self.save_translation_map()
                
                # 6. Refresh UI
                self.table_glyphs.blockSignals(False)
                self.refresh_table_row(glyph_idx)
                self.update_simulation()
                
                # Call Picoripi sync callback to reload the map and refresh previews!
                if self.font_sync_callback:
                    try:
                        self.font_sync_callback()
                    except Exception:
                        pass
                return
                    
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

    def get_translation_map_path(self):
        import os
        project_dir = None
        active_plugin = None
        parent_win = self.parent()
        if parent_win:
            mw = getattr(parent_win, "mw", None) if hasattr(parent_win, "mw") else parent_win
            if hasattr(mw, "project_manager") and mw.project_manager and mw.project_manager.project_dir:
                project_dir = mw.project_manager.project_dir
            if hasattr(mw, "active_game_plugin"):
                active_plugin = mw.active_game_plugin
                
        mapping_path = None
        if project_dir:
            mapping_path = os.path.join(project_dir, "translation_map.json")
        elif active_plugin:
            plugin_dir = os.path.join("plugins", active_plugin)
            if os.path.exists(plugin_dir):
                mapping_path = os.path.join(plugin_dir, "translation_map.json")
        return mapping_path

    def load_translation_map(self):
        self.translation_map = {}
        self.reverse_translation_map = {}
        try:
            mapping_path = self.get_translation_map_path()
            if mapping_path and os.path.exists(mapping_path):
                import json
                with open(mapping_path, "r", encoding="utf-8") as f:
                    raw_map = json.load(f)
                    self.translation_map = {}
                    for k, v in raw_map.items():
                        # Accept synthetic keys "#g{idx}" (empty-glyph mappings) as-is
                        if k.startswith("#g") or v.startswith("#g"):
                            self.translation_map[k] = v
                        elif len(k) == 1 and len(v) == 1 and ord(k) >= 128 and ord(v) >= 128:
                            self.translation_map[k] = v
                    # Rebuild reverse map only from normal (non-synthetic) entries
                    self.reverse_translation_map = {
                        v: k for k, v in self.translation_map.items()
                        if not k.startswith("#g") and not v.startswith("#g")
                    }
                print(f"BFN Editor: Loaded {len(self.translation_map)} characters from translation_map.json.")
        except Exception as e:
            print(f"Failed to load translation map: {e}")


    def save_translation_map(self):
        try:
            mapping_path = self.get_translation_map_path()
            if mapping_path:
                import json
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump(self.translation_map, f, indent=4, ensure_ascii=False)
                self.status.showMessage(f"Updated translation_map.json with {len(self.translation_map)} characters!")
        except Exception as e:
            print(f"Failed to save translation map: {e}")

    def get_original_char_for_glyph(self, glyph_idx):
        metadata = self.original_font_metadata if self.original_font_metadata else self.metadata
        maps = metadata.get("MAP1", [])
        for m in maps:
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
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == glyph_idx:
                        code = m_first + c_idx
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
                        try:
                            return chr(code)
                        except Exception:
                            pass
        return ""

    def update_char_mapping(self, glyph_idx, new_code):
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            if m_type == 2:
                entries = m.get("entries", [])
                first_char = m.get("first_char", 0)
                last_char = m.get("last_char", 0)
                
                # First, clear any other character mapping to this glyph_idx
                for i in range(len(entries)):
                    if entries[i] == glyph_idx:
                        entries[i] = 0xFFFF
                
                if new_code > 0:
                    if new_code < first_char:
                        padding_left = first_char - new_code
                        m["entries"] = [0xFFFF] * padding_left + entries
                        entries = m["entries"]
                        m["first_char"] = new_code
                        first_char = new_code
                    
                    idx_in_entries = new_code - first_char
                    if idx_in_entries >= len(entries):
                        padding_right = idx_in_entries - len(entries) + 1
                        entries.extend([0xFFFF] * padding_right)
                        m["last_char"] = first_char + len(entries) - 1
                        
                    entries[new_code - first_char] = glyph_idx
                    m["mapping_entry_count"] = len(entries)
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                found = False
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        entries[k] = new_code
                        found = True
                        break
                if not found:
                    entries.insert(half, new_code)
                    entries.append(glyph_idx)
                    m["mapping_entry_count"] = len(entries) // 2
                    m["first_char"] = min(m.get("first_char", new_code), new_code)
                    m["last_char"] = max(m.get("last_char", new_code), new_code)


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
        
        action_copy = menu.addAction("Copy Character(s) (Ctrl+C)")
        action_paste = menu.addAction("Paste Character(s) (Ctrl+V)")
        menu.addSeparator()
        
        action_fill = menu.addAction("Fill sequentially From/To...")
        action_render = menu.addAction("Render Font to Selected Glyph...")
        
        action_clear = None
        if len(selected_rows) > 0:
            action_clear = menu.addAction(f"Clear mapping for {len(selected_rows)} selected rows")
            
        selected_glyphs = []
        for row in sorted(selected_rows):
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if v_header:
                try:
                    selected_glyphs.append(int(v_header.text()))
                except ValueError:
                    pass

        action = menu.exec_(self.table_glyphs.viewport().mapToGlobal(pos))
        
        if action == action_copy:
            self.copy_glyph_values()
        elif action == action_paste:
            self.paste_glyph_values()
        elif action == action_fill:
            self.fill_sequence_dialog(index.row())
        elif action == action_render:
            self.render_system_font_to_glyphs(selected_glyphs=selected_glyphs)
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
        # Detect spellchecker language from parent MainWindow (if available)
        lang = ""
        p = self.parent()
        if p is not None:
            lang = getattr(p, "spellchecker_language", "") or ""
        dialog = FillRangeDialog(self, lang=lang)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            codes = dialog.get_sequence_codes()
            if not codes:
                QtWidgets.QMessageBox.warning(self, "Invalid Sequence", "No characters to fill. The sequence is empty.")
                return
                
            total_items = len(codes)
            available_rows = self.table_glyphs.rowCount() - start_row
            items_to_fill = min(total_items, available_rows)
            
            if items_to_fill <= 0:
                QtWidgets.QMessageBox.warning(self, "No Space", "No rows available to fill below the selected position.")
                return
                
            new_translation_map = dict(self.translation_map)
            new_reverse_map = dict(self.reverse_translation_map)
            
            filled_count = 0
            for i in range(items_to_fill):
                row = start_row + i
                v_header = self.table_glyphs.verticalHeaderItem(row)
                if not v_header:
                    continue
                glyph_idx = int(v_header.text())
                
                # Get the original CP1252 character for this glyph
                orig_char = self.get_original_char_for_glyph(glyph_idx)
                if not orig_char:
                    self.update_char_mapping(glyph_idx, glyph_idx)
                    orig_char = chr(glyph_idx)
                
                # Get new virtual character
                new_char_code = codes[i]
                new_virtual_char = chr(new_char_code) if new_char_code > 0 else ""
                
                # Update maps in memory
                # Remove old mapping from reverse
                if orig_char in new_reverse_map:
                    old_virtual_char = new_reverse_map[orig_char]
                    if old_virtual_char in new_translation_map:
                        del new_translation_map[old_virtual_char]
                    del new_reverse_map[orig_char]
                
                if new_virtual_char:
                    # Clear any duplicate mapping to prevent conflict
                    duplicate_orig = new_translation_map.get(new_virtual_char)
                    if duplicate_orig:
                        if duplicate_orig in new_reverse_map:
                            del new_reverse_map[duplicate_orig]
                        del new_translation_map[new_virtual_char]
                        
                    new_translation_map[new_virtual_char] = orig_char
                    new_reverse_map[orig_char] = new_virtual_char
                    filled_count += 1
                else:
                    filled_count += 1
            
            if filled_count > 0:
                from tools.bfn_editor.bfn_commands import BatchVirtualMapCommand
                cmd = BatchVirtualMapCommand(self, new_translation_map, new_reverse_map, f"Fill {filled_count} Mappings")
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
                            return bytes([glyph_idx]).decode('cp1252')
                        except Exception:
                            try:
                                return chr(glyph_idx)
                            except Exception:
                                pass
                elif m_type == 2:
                    entries = m.get("entries", [])
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == glyph_idx:
                            code = m_first + c_idx
                            if code > 0:
                                try:
                                    return bytes([code]).decode('cp1252')
                                except Exception:
                                    try:
                                        return chr(code)
                                    except Exception:
                                        pass
                            break
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == glyph_idx:
                            code = entries[k]
                            if code > 0:
                                try:
                                    return bytes([code]).decode('cp1252')
                                except Exception:
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
                        # Мапимо лише символи локалізації (кирилицю/діакритику), латиницю (ASCII) ігноруємо
                        if ord(trans_char) >= 128 and ord(orig_char) >= 128:
                            translation_map[trans_char] = orig_char
            except Exception:
                pass

        return translation_map

    def get_current_char_code_for_glyph(self, glyph_idx):
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            if m_type == 0:
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_first <= glyph_idx <= m_last:
                    return glyph_idx
            elif m_type == 2:
                entries = m.get("entries", [])
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == glyph_idx:
                        return m.get("first_char", 0) + c_idx
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        return entries[k]
        return 0

    def copy_glyph_values(self):
        selected_indexes = self.table_glyphs.selectedIndexes()
        if not selected_indexes:
            return

        # Sort selected indexes by row and then by column
        selected_indexes.sort(key=lambda idx: (idx.row(), idx.column()))

        # Check if there are any cells from column 3 (Character)
        char_cells = [idx for idx in selected_indexes if idx.column() == 3]
        
        texts = []
        if char_cells:
            for idx in char_cells:
                item = self.table_glyphs.item(idx.row(), 3)
                texts.append(item.text() if item else "")
        else:
            # If column 3 is not selected, get all unique rows involved
            rows = sorted(list(set(idx.row() for idx in selected_indexes)))
            for r in rows:
                item = self.table_glyphs.item(r, 3)
                texts.append(item.text() if item else "")

        clipboard_text = "\n".join(texts)
        QtWidgets.QApplication.clipboard().setText(clipboard_text)

    def paste_glyph_values(self):
        text = QtWidgets.QApplication.clipboard().text()
        if not text:
            return

        # Smart split
        if '\n' in text or '\r' in text:
            lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            if len(lines) > 1 and lines[-1] == "":
                lines.pop()
        else:
            lines = list(text)

        current = self.table_glyphs.currentIndex()
        if not current.isValid():
            return
            
        start_row = current.row()
        total_rows = self.table_glyphs.rowCount()
        items_to_fill = min(len(lines), total_rows - start_row)
        
        if items_to_fill <= 0:
            return

        new_translation_map = dict(self.translation_map)
        new_reverse_map = dict(self.reverse_translation_map)
        
        pasted_count = 0
        for i in range(items_to_fill):
            row = start_row + i
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if not v_header:
                continue
            glyph_idx = int(v_header.text())
            
            orig_char = self.get_original_char_for_glyph(glyph_idx)
            if not orig_char:
                self.update_char_mapping(glyph_idx, glyph_idx)
                orig_char = chr(glyph_idx)
                
            new_char = lines[i]
            new_virtual_char = new_char[0] if new_char else ""
            
            # Update maps in memory
            # Remove old mapping from reverse
            if orig_char in new_reverse_map:
                old_virtual_char = new_reverse_map[orig_char]
                if old_virtual_char in new_translation_map:
                    del new_translation_map[old_virtual_char]
                del new_reverse_map[orig_char]
            
            if new_virtual_char:
                # Clear any duplicate mapping to prevent conflict
                duplicate_orig = new_translation_map.get(new_virtual_char)
                if duplicate_orig:
                    if duplicate_orig in new_reverse_map:
                        del new_reverse_map[duplicate_orig]
                    del new_translation_map[new_virtual_char]
                    
                new_translation_map[new_virtual_char] = orig_char
                new_reverse_map[orig_char] = new_virtual_char
                pasted_count += 1
            else:
                pasted_count += 1

        if pasted_count > 0:
            from tools.bfn_editor.bfn_commands import BatchVirtualMapCommand
            cmd = BatchVirtualMapCommand(self, new_translation_map, new_reverse_map, f"Paste {pasted_count} Character Mappings")
            self.undo_stack.push(cmd)
            self._set_dirty(True)


