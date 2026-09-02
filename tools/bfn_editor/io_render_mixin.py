from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr

from tools.bfn_editor.bfn_widgets import RenderFontDialog
from tools.bfn_editor.bfn_commands import RenderFontCommand


class IoRenderMixin:
    def render_system_font_to_glyphs(self, selected_glyphs=None):
        if not self.sheet_images:
            return
            
        # 1. Build map of glyphs to characters early for preview support
        glyph_to_char = {}
        maps = self.metadata.get("MAP1", [])
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val = ""
            for m in maps:
                m_type = m.get("mapping_type", 0)
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_type == 0:
                    if m_first <= idx <= m_last:
                        try:
                            char_val = chr(idx)
                        except Exception:
                            pass
                        break
                elif m_type == 2:
                    entries = m.get("entries", [])
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == idx:
                            code = m_first + c_idx
                            try:
                                char_val = chr(code)
                            except Exception:
                                pass
                            break
                    if char_val:
                        break
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == idx:
                            code = entries[k]
                            try:
                                char_val = chr(code)
                            except Exception:
                                pass
                            break
                    if char_val:
                        break
            if char_val:
                if hasattr(self, 'reverse_translation_map') and self.reverse_translation_map:
                    virtual_char = self.reverse_translation_map.get(char_val)
                    if virtual_char:
                        char_val = virtual_char
                glyph_to_char[idx] = char_val
            elif hasattr(self, 'translation_map') and self.translation_map:
                # Glyph has no MAP1 entry: check for a synthetic mapping "#g{idx}"
                synthetic_key = f"#g{idx}"
                virtual_char = self.translation_map.get(synthetic_key, "")
                if virtual_char:
                    glyph_to_char[idx] = virtual_char
                
        # Determine current or fallback glyphs for interactive real-time preview
        has_sel = (selected_glyphs and len(selected_glyphs) > 0) or (self.selected_cell is not None and self.current_sheet_index >= 0)
        
        glyphs_for_preview = []
        if selected_glyphs and len(selected_glyphs) > 0:
            glyphs_for_preview = list(selected_glyphs)
        elif self.selected_cell is not None and self.current_sheet_index >= 0:
            gx, gy = self.selected_cell
            rem = self.current_sheet_index * (self.rows * self.cols) + gy * self.rows + gx
            idx = self.start_glyph + rem
            if self.start_glyph <= idx <= self.end_glyph:
                glyphs_for_preview = [idx]
        else:
            # Fallback: search for first 30 glyphs that have character mappings to preview
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and ch.strip():
                    glyphs_for_preview.append(idx)
                    if len(glyphs_for_preview) >= 30:
                        break
                        
        preview_list = []
        for idx in glyphs_for_preview:
            char_str = glyph_to_char.get(idx, "")
            if not char_str:
                continue
                
            rem = idx - self.start_glyph
            sheet_idx = rem // (self.rows * self.cols)
            cell_idx = rem % (self.rows * self.cols)
            gx = cell_idx % self.rows
            gy = cell_idx // self.rows
            
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            img = None
            if 0 <= sheet_idx < len(self.sheet_images):
                img = self.sheet_images[sheet_idx].copy(cell_x, cell_y, self.cell_w, self.cell_h)
                
            preview_list.append({"char": char_str, "img": img, "idx": idx})
            
        dialog = RenderFontDialog(self, self.cell_w, self.cell_h, has_selected_glyph=has_sel, preview_list=preview_list)
        
        # Set ranges if custom scope is selected
        dialog.spin_start_glyph.setValue(self.start_glyph)
        dialog.spin_end_glyph.setValue(self.end_glyph)
        
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
            
        params = dialog.get_params()
                
        # 2. Determine list of glyphs to render
        scope = params["scope"]
        glyphs_to_render = []
        
        if scope == "selected" and has_sel:
            if selected_glyphs and len(selected_glyphs) > 0:
                glyphs_to_render = list(selected_glyphs)
            else:
                gx, gy = self.selected_cell
                rem = self.current_sheet_index * (self.rows * self.cols) + gy * self.rows + gx
                idx = self.start_glyph + rem
                if self.start_glyph <= idx <= self.end_glyph:
                    glyphs_to_render.append(idx)
        elif scope == "all":
            glyphs_to_render = list(range(self.start_glyph, self.end_glyph + 1))
        elif scope == "cyrillic":
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and "\u0400" <= ch <= "\u04FF":
                    glyphs_to_render.append(idx)
        elif scope == "latin":
            for idx in range(self.start_glyph, self.end_glyph + 1):
                ch = glyph_to_char.get(idx, "")
                if ch and (("A" <= ch <= "Z") or ("a" <= ch <= "z")):
                    glyphs_to_render.append(idx)
        elif scope == "custom":
            start_g = max(self.start_glyph, params["start_glyph"])
            end_g = min(self.end_glyph, params["end_glyph"])
            glyphs_to_render = list(range(start_g, end_g + 1))
            
        if not glyphs_to_render:
            QtWidgets.QMessageBox.warning(self, tr("No Glyphs"), tr("No valid glyphs found to render in the selected scope."))
            return
            
        pixel_changes = []
        metrics_changes = []
        
        # Prepare QFont
        font = params["font"]
        h_scale = params.get("h_scale", 100)
        v_scale = params.get("v_scale", 100)
        x_offset = params["x_offset"]
        y_offset = params["y_offset"]
        align_h = params["align_h"]
        align_v = params["align_v"]
        auto_metrics = params["auto_metrics"]
        antialiasing = params["antialiasing"]
        
        # Alignment flags
        alignment = QtCore.Qt.AlignmentFlag(0)
        if align_h is not None:
            alignment |= align_h
        if align_v != "baseline" and align_v is not None:
            alignment |= align_v
            
        ascent = 0
        inf_list = self.metadata.get("INF1", [])
        if inf_list:
            ascent = inf_list[0].get("ascent", 0)
            
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        progress = QtWidgets.QProgressDialog("Rendering glyphs...", "Cancel", 0, len(glyphs_to_render), self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        
        for step, idx in enumerate(glyphs_to_render):
            if progress.wasCanceled():
                break
            progress.setValue(step)
            
            char_str = glyph_to_char.get(idx, "")
            if not char_str:
                continue
                
            rem = idx - self.start_glyph
            sheet_idx = rem // (self.rows * self.cols)
            cell_idx = rem % (self.rows * self.cols)
            gx = cell_idx % self.rows
            gy = cell_idx // self.rows
            
            cell_x = gx * self.cell_w
            cell_y = gy * self.cell_h
            
            sheet_img = self.sheet_images[sheet_idx]
            old_glyph_crop = sheet_img.copy(cell_x, cell_y, self.cell_w, self.cell_h)
            
            # Render new glyph image
            new_glyph = QtGui.QImage(self.cell_w, self.cell_h, QtGui.QImage.Format.Format_ARGB32)
            new_glyph.fill(QtGui.QColor(0, 0, 0, 0))
            
            painter = QtGui.QPainter(new_glyph)
            try:
                if antialiasing:
                    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
                    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                painter.setFont(font)
                painter.setPen(QtGui.QColor(255, 255, 255, 255))
                
                # Apply scaling relative to the cell center
                painter.save()
                cx = self.cell_w / 2.0
                cy = self.cell_h / 2.0
                painter.translate(cx, cy)
                painter.scale(h_scale / 100.0, v_scale / 100.0)
                painter.translate(-cx, -cy)
                
                if align_v == "baseline":
                    # Draw text aligned on baseline
                    font_metrics = QtGui.QFontMetrics(font)
                    text_width = font_metrics.horizontalAdvance(char_str)
                    x = x_offset
                    if align_h == QtCore.Qt.AlignmentFlag.AlignHCenter:
                        x = max(0, (self.cell_w - text_width) // 2) + x_offset
                    elif align_h == QtCore.Qt.AlignmentFlag.AlignRight:
                        x = self.cell_w - text_width + x_offset
                    
                    painter.drawText(x, ascent + y_offset, char_str)
                else:
                    rect = QtCore.QRect(x_offset, y_offset, self.cell_w, self.cell_h)
                    painter.drawText(rect, alignment, char_str)
                    
                painter.restore()
            finally:
                painter.end()
            
            pixel_changes.append((sheet_idx, cell_x, cell_y, old_glyph_crop, new_glyph))
            
            # Recalculate metrics if requested
            if auto_metrics:
                min_x = -1
                max_x = -1
                for x in range(self.cell_w):
                    has_pixel = False
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(x, y)
                        if color.alpha() > 15:
                            has_pixel = True
                            break
                    if has_pixel:
                        min_x = x
                        break
                        
                for x in range(self.cell_w - 1, -1, -1):
                    has_pixel = False
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(x, y)
                        if color.alpha() > 15:
                            has_pixel = True
                            break
                    if has_pixel:
                        max_x = x
                        break
                        
                if min_x == -1 or max_x == -1:
                    new_kern = 0
                    new_width = self.cell_w // 2
                else:
                    max_block_left = 0
                    current_block = 0
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(min_x, y)
                        if color.alpha() > 15:
                            current_block += 1
                        else:
                            if current_block > max_block_left:
                                max_block_left = current_block
                            current_block = 0
                    if current_block > max_block_left:
                        max_block_left = current_block
                        
                    max_block_right = 0
                    current_block = 0
                    for y in range(self.cell_h):
                        color = new_glyph.pixelColor(max_x, y)
                        if color.alpha() > 15:
                            current_block += 1
                        else:
                            if current_block > max_block_right:
                                max_block_right = current_block
                            current_block = 0
                    if current_block > max_block_right:
                        max_block_right = current_block
                        
                    if max_block_left < 5:
                        new_kern = min_x
                    else:
                        new_kern = max(0, min_x - 1)
                        
                    if max_block_right < 5:
                        right_boundary = max_x
                    else:
                        right_boundary = max_x + 1
                        
                    new_width = right_boundary - new_kern + 1
                    
                wid_idx = idx - self.first_code
                if 0 <= wid_idx:
                    # Extend packets if this glyph is beyond the current WID1 range
                    if wid_idx >= len(packets):
                        padding_count = wid_idx - len(packets) + 1
                        packets.extend([{"kerning": 0, "width": self.cell_w} for _ in range(padding_count)])
                        wid["last_code_included"] = self.first_code + len(packets)
                    old_kern = packets[wid_idx]["kerning"]
                    old_width = packets[wid_idx]["width"]
                    metrics_changes.append((idx, old_kern, new_kern, old_width, new_width))
                    
        progress.setValue(len(glyphs_to_render))
        
        if pixel_changes:
            cmd = RenderFontCommand(self, pixel_changes, metrics_changes, f"Render Font ({scope})")
            self.undo_stack.push(cmd)
            self._set_dirty(True)
            QtWidgets.QMessageBox.information(
                self,
                tr("Success"),
                tr("Successfully rendered {0} glyphs using the system font!", len(pixel_changes)),
            )
