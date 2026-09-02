from PyQt6 import QtWidgets

from core.i18n import tr


class GlyphNavMixin:
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
            QtWidgets.QMessageBox.information(self, tr("Empty Glyphs"), tr("No empty glyphs found in the table."))

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
            QtWidgets.QMessageBox.information(self, tr("Empty Glyphs"), tr("No empty glyphs found in the table."))

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
            QtWidgets.QMessageBox.warning(
                self,
                tr("Not Found"),
                tr("Glyph with index {0} is not in the current range or does not exist.", glyph_idx),
            )
