from PyQt6 import QtCore, QtGui, QtWidgets
import os
from tools.bfn_editor.bfn_widgets import FillRangeDialog
from tools.bfn_editor.bfn_commands import EditMetricsCommand, EditMapCommand, BatchMappingCommand
from utils.logging_utils import log_info, log_error

class BfnNavigationMixin:
    def _resolve_char_from_maps(self, idx: int, maps: list) -> str:
        for m in maps:
            m_type = m.get("mapping_type", 0)
            m_first = m.get("first_char", 0)
            m_last = m.get("last_char", 0)
            
            if m_type == 0:
                if m_first <= idx <= m_last:
                    try:
                        return bytes([idx]).decode('cp1252')
                    except Exception:
                        try:
                            return chr(idx)
                        except Exception:
                            pass
            elif m_type == 2:
                entries = m.get("entries", [])
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == idx:
                        code = m_first + c_idx
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
                    if entries[half + k] == idx:
                        code = entries[k]
                        try:
                            return bytes([code]).decode('cp1252')
                        except Exception:
                            try:
                                return chr(code)
                            except Exception:
                                pass
                        break
        return ""

    def _get_glyph_translation_mapping(self, idx: int, char_val: str) -> tuple[str, str]:
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
        return char_val, font_char_val

    def _calculate_glyph_position(self, idx: int) -> tuple[int, int, int]:
        rem = idx - self.start_glyph
        sheet_idx = rem // (self.rows * self.cols)
        cell_idx = rem % (self.rows * self.cols)
        gx = cell_idx % self.rows
        gy = cell_idx // self.rows
        return sheet_idx, gx, gy

    def _get_glyph_metrics(self, idx: int, packets: list) -> tuple[int, int]:
        wid_idx = idx - self.first_code
        kerning = 0
        width = self.cell_w
        if 0 <= wid_idx < len(packets):
            kerning = packets[wid_idx]["kerning"]
            width = packets[wid_idx]["width"]
        return kerning, width

    def _create_glyph_image_label(self, sheet_images: list, sheet_idx: int, gx: int, gy: int) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel()
        bg_color = "#000000"
        lbl.setStyleSheet(f"background-color: {bg_color}; margin: 2px;")
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        if sheet_images and 0 <= sheet_idx < len(sheet_images):
            sheet_img = sheet_images[sheet_idx]
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
            pixmap = QtGui.QPixmap.fromImage(glyph_crop)
            lbl.setPixmap(pixmap.scaled(
                28, 28,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            ))
        return lbl

    def _style_font_char_item(self, item: QtWidgets.QTableWidgetItem) -> None:
        item.setFlags(item.flags() ^ QtCore.Qt.ItemFlag.ItemIsEditable)
        if getattr(self, "is_dark_theme", True):
            item.setForeground(QtGui.QBrush(QtGui.QColor("#88888b")))
            item.setBackground(QtGui.QBrush(QtGui.QColor("#1a1a20")))
        else:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#7e8a9b")))
            item.setBackground(QtGui.QBrush(QtGui.QColor("#eef1f6")))
        item.setToolTip("Font Character (read-only, stored in font metadata)")

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
            raw_char = self._resolve_char_from_maps(idx, maps)
            char_val, font_char_val = self._get_glyph_translation_mapping(idx, raw_char)
            glyph_to_char[idx] = (char_val, font_char_val)
            
        orig_glyph_to_char = {}
        if self.original_font_metadata:
            orig_maps = self.original_font_metadata.get("MAP1", [])
            for idx in range(self.start_glyph, self.end_glyph + 1):
                orig_char = self._resolve_char_from_maps(idx, orig_maps)
                orig_glyph_to_char[idx] = orig_char
            
        search_query = self.table_search.text().lower()
        
        rows_data = []
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val, font_char_val = glyph_to_char.get(idx, ("", ""))
            orig_char_data = orig_glyph_to_char.get(idx, "")
            
            sheet_idx, gx, gy = self._calculate_glyph_position(idx)
            kerning, width = self._get_glyph_metrics(idx, packets)
                
            if search_query:
                match = (
                    search_query in str(idx) or
                    search_query in char_val.lower() or
                    search_query in orig_char_data.lower() or
                    search_query in font_char_val.lower() or
                    search_query in f"sheet_{sheet_idx}".lower()
                )
                if not match:
                    continue
                    
            rows_data.append((idx, char_val, font_char_val, sheet_idx, gx, gy, kerning, width, orig_char_data))
            
        self.table_glyphs.setRowCount(len(rows_data))
        self.table_glyphs.verticalHeader().setDefaultSectionSize(36)
        
        for r_idx, data in enumerate(rows_data):
            idx, char_val, font_char_val, sheet_idx, gx, gy, kerning, width, orig_char_data = data
            
            self.table_glyphs.setVerticalHeaderItem(r_idx, QtWidgets.QTableWidgetItem(str(idx)))
            
            item_orig_char = QtWidgets.QTableWidgetItem(orig_char_data)
            item_char = QtWidgets.QTableWidgetItem(char_val)
            item_font_char = QtWidgets.QTableWidgetItem(font_char_val)
            item_sheet = QtWidgets.QTableWidgetItem(f"Sheet {sheet_idx}")
            item_tile = QtWidgets.QTableWidgetItem(f"Row {gy}, Col {gx}")
            item_kern = QtWidgets.QTableWidgetItem(str(kerning))
            item_width = QtWidgets.QTableWidgetItem(str(width))
            
            for item in (item_orig_char, item_sheet, item_tile):
                item.setFlags(item.flags() ^ QtCore.Qt.ItemFlag.ItemIsEditable)
                
            self._style_font_char_item(item_font_char)
                
            item_char.setFlags(item_char.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            item_kern.setFlags(item_kern.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            item_width.setFlags(item_width.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            
            self.table_glyphs.setItem(r_idx, 1, item_orig_char)
            self.table_glyphs.setItem(r_idx, 3, item_char)
            self.table_glyphs.setItem(r_idx, 4, item_font_char)
            self.table_glyphs.setItem(r_idx, 5, item_sheet)
            self.table_glyphs.setItem(r_idx, 6, item_tile)
            self.table_glyphs.setItem(r_idx, 7, item_kern)
            self.table_glyphs.setItem(r_idx, 8, item_width)
            
            # Original Render
            orig_lbl = self._create_glyph_image_label(self.original_sheet_images, sheet_idx, gx, gy)
            self.table_glyphs.setCellWidget(r_idx, 0, orig_lbl)
            
            # Translated Render
            lbl = self._create_glyph_image_label(self.sheet_images, sheet_idx, gx, gy)
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
        raw_char = self._resolve_char_from_maps(glyph_idx, maps)
        char_val, font_char_val = self._get_glyph_translation_mapping(glyph_idx, raw_char)
                
        item_char = self.table_glyphs.item(found_row, 3)
        if item_char:
            item_char.setText(char_val)
        item_font_char = self.table_glyphs.item(found_row, 4)
        if item_font_char:
            item_font_char.setText(font_char_val)
            self._style_font_char_item(item_font_char)
            
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        kerning, width = self._get_glyph_metrics(glyph_idx, packets)
            
        item_kern = self.table_glyphs.item(found_row, 7)
        if item_kern:
            item_kern.setText(str(kerning))
        item_width = self.table_glyphs.item(found_row, 8)
        if item_width:
            item_width.setText(str(width))
            
        sheet_idx, gx, gy = self._calculate_glyph_position(glyph_idx)
        
        lbl = self._create_glyph_image_label(self.sheet_images, sheet_idx, gx, gy)
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
                _empty_glyph_registered = False
                
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
                    physical_code = self.get_next_free_char_code()
                    if physical_code is None:
                        physical_code = glyph_idx
                        
                    self.update_char_mapping(glyph_idx, physical_code)
                    orig_char = chr(physical_code)
                    _empty_glyph_registered = True
                    
                    # Update table row to reflect physical mapping instantly in Font Char column (col 4)
                    item_font_char = self.table_glyphs.item(row, 4)
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
                
                # 5b. If a new physical code was assigned to a previously empty glyph,
                # the MAP1 change is only in memory — persist the BFN to disk immediately
                # so the mapping survives a restart.
                if _empty_glyph_registered:
                    try:
                        self.save_changes(silent=True)
                    except Exception as _e:
                        log_error(f"BFN Editor: Failed to auto-save BFN after empty glyph registration: {_e}")
                
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
            log_error(f"Error updating table metadata: {e}")
            
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
                needs_save = False
                
                # 1. Normalize mapping direction: Ukrainian character (ord >= 256) must be the key,
                # CP1252 character (ord < 256) must be the value.
                normalized_map = {}
                for k, v in raw_map.items():
                    if k.startswith("#g") or v.startswith("#g"):
                        normalized_map[k] = v
                    elif len(k) == 1 and len(v) == 1:
                        if ord(k) < 256 and ord(v) >= 256:
                            # Swap to make Ukrainian character the key
                            normalized_map[v] = k
                        elif ord(k) >= 256 and ord(v) < 256:
                            normalized_map[k] = v
                        else:
                            normalized_map[k] = v
                            
                # 2. First pass: parse and migrate any synthetic mappings to real physical mappings in MAP1
                migrated_map = {}
                for k, v in normalized_map.items():
                    # Check if either k or v is a synthetic key "#g{idx}"
                    synthetic_key = None
                    virtual_char = None
                    if k.startswith("#g"):
                        synthetic_key = k
                        virtual_char = v
                    elif v.startswith("#g"):
                        synthetic_key = v
                        virtual_char = k
                        
                    if synthetic_key and virtual_char:
                        try:
                            glyph_idx = int(synthetic_key[2:])
                            # Check if this glyph already has a physical character code in MAP1
                            current_code = self.get_current_char_code_for_glyph(glyph_idx)
                            
                            # If it doesn't have a mapped code, or if the current code is already taken
                            # (excluding the synthetic key itself) or is equal to glyph_idx which could conflict,
                            # dynamically allocate a clean printable character code!
                            taken_codes = [ord(val) for key, val in normalized_map.items() if len(val) == 1 and key != synthetic_key]
                            if current_code <= 0 or current_code >= 0xFFFF or current_code in taken_codes or current_code == glyph_idx:
                                physical_code = self.get_next_free_char_code(migrated_map)
                                if physical_code is None:
                                    physical_code = glyph_idx
                            else:
                                physical_code = current_code
                                
                            self.update_char_mapping(glyph_idx, physical_code)
                            orig_char = chr(physical_code)
                                
                            # Convert to clean physical mapping in memory
                            migrated_map[virtual_char] = orig_char
                            needs_save = True
                        except Exception as e:
                            log_error(f"Failed to migrate synthetic key {synthetic_key}: {e}")
                    else:
                        # Keep normal entries as-is
                        migrated_map[k] = v
                        
                # 3. Second pass: heal any control characters/non-printable character codes in migrated_map
                healed_map = {}
                for k, v in migrated_map.items():
                    if len(k) == 1 and len(v) == 1:
                        char_code = ord(v)
                        # Control/non-printable range in Unicode/CP1252
                        if char_code < 32 or (127 <= char_code <= 160):
                            try:
                                # Find which glyph currently maps to this control code
                                glyph_idx = -1
                                for idx in range(self.start_glyph, self.end_glyph + 1):
                                    if self.get_current_char_code_for_glyph(idx) == char_code:
                                        glyph_idx = idx
                                        break
                                        
                                if glyph_idx != -1:
                                    physical_code = self.get_next_free_char_code(healed_map)
                                    if physical_code is not None:
                                        self.update_char_mapping(glyph_idx, physical_code)
                                        v = chr(physical_code)
                                        needs_save = True
                            except Exception as e:
                                log_error(f"Failed to heal control character code {char_code} for glyph {glyph_idx}: {e}")
                    healed_map[k] = v
                    
                # Load healed entries
                # Valid entry: key is non-ASCII unicode (ord >= 128), value is printable CP1252 (161-255)
                # Reject entries with control/non-printable value codes
                for k, v in healed_map.items():
                    if len(k) == 1 and len(v) == 1:
                        k_code = ord(k)
                        v_code = ord(v)
                        # Key must be non-ASCII (Cyrillic etc.), value must be printable CP1252 range 161-255
                        if k_code >= 128 and 161 <= v_code <= 255:
                            self.translation_map[k] = v
                        elif k_code >= 128 and v_code >= 128:
                            # Borderline case: both non-ASCII, allow but mark for heal next time
                            self.translation_map[k] = v
                            needs_save = True
                    elif k.startswith("#g") or v.startswith("#g"): # fallback if migration failed
                        self.translation_map[k] = v
                        
                # Rebuild reverse map only from normal (non-synthetic) entries
                self.reverse_translation_map = {
                    v: k for k, v in self.translation_map.items()
                    if not k.startswith("#g") and not v.startswith("#g")
                }
                
                # 4. Fourth pass: re-register any physical codes that are in translation_map
                # but NOT present in the current MAP1 (e.g. BFN wasn't saved after empty glyph assignment).
                # Find all codes currently registered in MAP1:
                registered_codes = set()
                for m in self.metadata.get("MAP1", []):
                    m_type = m.get("mapping_type", 0)
                    if m_type == 0:
                        for code in range(m.get("first_char", 0), m.get("last_char", 0) + 1):
                            registered_codes.add(code)
                    elif m_type == 2:
                        first_char = m.get("first_char", 0)
                        for c_idx, g_idx in enumerate(m.get("entries", [])):
                            if g_idx != 0xFFFF:
                                registered_codes.add(first_char + c_idx)
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for ki in range(half):
                            registered_codes.add(entries[ki])
                
                # Find all glyph indices that have NO code in MAP1 (empty glyphs)
                # Read range from metadata directly — self.start_glyph/end_glyph may not be set yet
                gly_meta = self.metadata.get("GLY1", [{}])[0]
                _heal_start = int(gly_meta.get("start_glyph", 0))
                _heal_end = int(gly_meta.get("end_glyph", _heal_start))
                all_glyphs = set(range(_heal_start, _heal_end + 1))
                mapped_glyphs = set()
                for m in self.metadata.get("MAP1", []):
                    m_type = m.get("mapping_type", 0)
                    if m_type == 2:
                        for g_idx in m.get("entries", []):
                            if g_idx != 0xFFFF:
                                mapped_glyphs.add(g_idx)
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for ki in range(half):
                            mapped_glyphs.add(entries[half + ki])
                empty_glyphs = sorted(all_glyphs - mapped_glyphs)
                empty_glyph_iter = iter(empty_glyphs)
                
                orphan_codes_found = False
                for virtual_char, phys_char in list(self.translation_map.items()):
                    if len(virtual_char) != 1 or len(phys_char) != 1:
                        continue
                    phys_code = ord(phys_char)
                    if phys_code not in registered_codes:
                        # This physical code has no glyph assigned — find an empty glyph and assign it
                        try:
                            empty_glyph = next(empty_glyph_iter)
                            self.update_char_mapping(empty_glyph, phys_code)
                            registered_codes.add(phys_code)
                            mapped_glyphs.add(empty_glyph)
                            orphan_codes_found = True
                            log_info(f"BFN Editor: Re-registered orphan code {phys_code} ('{virtual_char}') to glyph {empty_glyph}")
                        except StopIteration:
                            log_error(f"BFN Editor: No empty glyphs left to re-register code {phys_code} ('{virtual_char}')")
                
                if orphan_codes_found:
                    needs_save = True
                
                if needs_save:
                    # Save the cleaned mapping_file without synthetic keys back to disk
                    self.save_translation_map()
                    # Physically save the BFN font file to commit the MAP1 changes to disk
                    try:
                        self.save_changes(silent=True)
                    except Exception as e:
                        log_error(f"Failed to auto-save BFN font during migration: {e}")
                    
                log_info(f"BFN Editor: Loaded {len(self.translation_map)} characters from translation_map.json.")
        except Exception as e:
            log_error(f"Failed to load translation map: {e}")


    def save_translation_map(self):
        try:
            mapping_path = self.get_translation_map_path()
            if mapping_path:
                import json
                # Filter out corrupt entries before saving:
                # - key must be 1 char, non-ASCII (ord >= 128)
                # - value must be 1 char, printable CP1252 (161-255)
                # Synthetic keys (#g...) are never saved to disk
                clean_map = {}
                for k, v in self.translation_map.items():
                    if k.startswith("#g") or (isinstance(v, str) and v.startswith("#g")):
                        continue  # skip synthetic entries
                    if len(k) == 1 and len(v) == 1:
                        k_code = ord(k)
                        v_code = ord(v)
                        if k_code >= 128 and 161 <= v_code <= 255:
                            clean_map[k] = v
                        # skip entries with control/invalid value codes
                    # skip entries with non-single-char keys/values
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump(clean_map, f, indent=4, ensure_ascii=False)
                self.status.showMessage(f"Updated translation_map.json with {len(clean_map)} characters!")
        except Exception as e:
            log_error(f"Failed to save translation map: {e}")

    def get_next_free_char_code(self, temp_translation_map=None):
        used_codes = set()
        
        # 1. Collect codes used in the active translation map
        trans_map = temp_translation_map if temp_translation_map is not None else getattr(self, 'translation_map', {})
        if trans_map:
            for v in trans_map.values():
                if isinstance(v, str) and len(v) == 1:
                    used_codes.add(ord(v))
                elif isinstance(v, str) and v.startswith("#g"):
                    try:
                        used_codes.add(int(v[2:]))
                    except Exception:
                        pass
        
        # 2. Add ASCII printable characters to avoid overwriting them
        for code in range(32, 128):
            used_codes.add(code)
            
        # 3. Add control / non-printable CP1252 characters to avoid them
        for code in range(0, 32):
            used_codes.add(code)
        for code in range(127, 161):
            used_codes.add(code)
                        
        # 4. Find the first free code in the CP1252 printable range 161-255
        for code in range(161, 256):
            if code not in used_codes:
                return code
                
        return None

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
                        try:
                            return bytes([code]).decode('cp1252')
                        except Exception:
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
                            return bytes([code]).decode('cp1252')
                        except Exception:
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

        action = menu.exec(self.table_glyphs.viewport().mapToGlobal(pos))
        
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
            
        new_translation_map = dict(self.translation_map)
        new_reverse_map = dict(self.reverse_translation_map)
        
        cleared_count = 0
        for row in selected_rows:
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if not v_header:
                continue
            try:
                glyph_idx = int(v_header.text())
            except ValueError:
                continue
                
            # Get current physical character code
            code = self.get_current_char_code_for_glyph(glyph_idx)
            phys_char = None
            if code > 0:
                try:
                    phys_char = bytes([code]).decode('cp1252')
                except Exception:
                    phys_char = chr(code)
                    
            # 1. Clear normal mapping
            if phys_char and phys_char in new_reverse_map:
                virtual_char = new_reverse_map[phys_char]
                if virtual_char in new_translation_map:
                    del new_translation_map[virtual_char]
                del new_reverse_map[phys_char]
                cleared_count += 1
                
            # 2. Clear synthetic mapping if any (#g...)
            synth_key = f"#g{glyph_idx}"
            if synth_key in new_translation_map:
                val = new_translation_map[synth_key]
                if val in new_reverse_map:
                    del new_reverse_map[val]
                del new_translation_map[synth_key]
                cleared_count += 1
                
            # If the value in translation_map is synth_key
            for k, v in list(new_translation_map.items()):
                if v == synth_key:
                    del new_translation_map[k]
                    cleared_count += 1

        if cleared_count == 0:
            return
            
        from tools.bfn_editor.bfn_commands import BatchVirtualMapCommand
        cmd = BatchVirtualMapCommand(self, new_translation_map, new_reverse_map, f"Clear {cleared_count} Virtual Mappings")
        self.undo_stack.push(cmd)
        self._set_dirty(True)
        
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            f"Successfully cleared {cleared_count} character mappings!"
        )

    def fill_sequence_dialog(self, start_row):
        # Detect spellchecker language from parent MainWindow (if available)
        lang = ""
        p = self.parent()
        if p is not None:
            lang = getattr(p, "spellchecker_language", "") or ""
        dialog = FillRangeDialog(self, lang=lang)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
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
                    physical_code = self.get_next_free_char_code(new_translation_map)
                    if physical_code is None:
                        physical_code = glyph_idx
                    self.update_char_mapping(glyph_idx, physical_code)
                    orig_char = chr(physical_code)
                
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
                
                if trans_char:
                    virtual_char = self.reverse_translation_map.get(trans_char)
                    if virtual_char:
                        if virtual_char != orig_char:
                            translation_map[virtual_char] = trans_char
                    elif orig_char and trans_char != orig_char:
                        if len(trans_char) == 1 and len(orig_char) == 1:
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
                physical_code = self.get_next_free_char_code(new_translation_map)
                if physical_code is None:
                    physical_code = glyph_idx
                self.update_char_mapping(glyph_idx, physical_code)
                orig_char = chr(physical_code)
                
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

    def goto_next_empty_glyph(self):
        current = self.table_glyphs.currentIndex()
        start_row = current.row() if current.isValid() else 0
        row_count = self.table_glyphs.rowCount()
        
        found_row = -1
        # Search down
        for row in range(start_row + 1, row_count):
            item = self.table_glyphs.item(row, 3) # Column 3 is Character
            if not item or not item.text().strip():
                found_row = row
                break
                
        if found_row == -1:
            # Wrap around and search from top
            for row in range(0, start_row + 1):
                if row >= row_count:
                    break
                item = self.table_glyphs.item(row, 3)
                if not item or not item.text().strip():
                    found_row = row
                    break
                    
        if found_row != -1:
            self.table_glyphs.setCurrentCell(found_row, 3)
            self.table_glyphs.scrollToItem(self.table_glyphs.currentItem())
        else:
            QtWidgets.QMessageBox.information(self, "Empty Glyphs", "No empty glyphs found in the table.")

    def goto_prev_empty_glyph(self):
        current = self.table_glyphs.currentIndex()
        row_count = self.table_glyphs.rowCount()
        start_row = current.row() if current.isValid() else row_count - 1
        
        found_row = -1
        # Search up
        for row in range(start_row - 1, -1, -1):
            item = self.table_glyphs.item(row, 3)
            if not item or not item.text().strip():
                found_row = row
                break
                
        if found_row == -1:
            # Wrap around and search from bottom
            for row in range(row_count - 1, start_row - 1, -1):
                if row < 0:
                    break
                item = self.table_glyphs.item(row, 3)
                if not item or not item.text().strip():
                    found_row = row
                    break
                    
        if found_row != -1:
            self.table_glyphs.setCurrentCell(found_row, 3)
            self.table_glyphs.scrollToItem(self.table_glyphs.currentItem())
        else:
            QtWidgets.QMessageBox.information(self, "Empty Glyphs", "No empty glyphs found in the table.")

    def jump_to_glyph_index(self, glyph_idx=None):
        if glyph_idx is None:
            glyph_idx = self.spin_jump_idx.value()
            
        row_count = self.table_glyphs.rowCount()
        found_row = -1
        for row in range(row_count):
            v_header = self.table_glyphs.verticalHeaderItem(row)
            if v_header and int(v_header.text()) == glyph_idx:
                found_row = row
                break
                
        if found_row != -1:
            self.table_glyphs.setCurrentCell(found_row, 3)
            self.table_glyphs.scrollToItem(self.table_glyphs.currentItem())
        else:
            QtWidgets.QMessageBox.warning(self, "Not Found", f"Glyph with index {glyph_idx} is not in the current range or does not exist.")


