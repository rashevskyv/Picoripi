from PyQt6 import QtWidgets
from core.i18n import tr
from tools.bfn_editor.bfn_widgets import FillRangeDialog
from tools.bfn_editor.bfn_commands import EditMetricsCommand
from utils.logging_utils import log_error


class MappingEditMixin:
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
        
        action_copy = menu.addAction(tr("Copy Character(s) (Ctrl+C)"))
        action_paste = menu.addAction(tr("Paste Character(s) (Ctrl+V)"))
        menu.addSeparator()
        
        action_fill = menu.addAction(tr("Fill sequentially From/To..."))
        action_render = menu.addAction(tr("Render Font to Selected Glyph..."))
        
        action_clear = None
        if len(selected_rows) > 0:
            action_clear = menu.addAction(tr("Clear mapping for {0} selected rows", len(selected_rows)))
            
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
            tr("Success"),
            tr("Successfully cleared {0} character mappings!", cleared_count),
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
                QtWidgets.QMessageBox.warning(self, tr("Invalid Sequence"), tr("No characters to fill. The sequence is empty."))
                return
                
            total_items = len(codes)
            available_rows = self.table_glyphs.rowCount() - start_row
            items_to_fill = min(total_items, available_rows)
            
            if items_to_fill <= 0:
                QtWidgets.QMessageBox.warning(self, tr("No Space"), tr("No rows available to fill below the selected position."))
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
                    tr("Success"),
                    tr("Successfully filled {0} symbols sequentially!", items_to_fill),
                )
