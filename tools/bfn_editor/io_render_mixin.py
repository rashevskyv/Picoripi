"""BFN editor: render a system font into glyphs."""
from PyQt6 import QtCore, QtWidgets

from core.i18n import tr

from tools.bfn_editor.bfn_widgets import RenderFontDialog
from tools.bfn_editor.render_font_dialog import ink_metrics, render_glyph
from tools.bfn_editor.bfn_commands import RenderFontCommand
from utils.logging_utils import log_debug


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
                        except Exception as exc:
                            log_debug(f"io_render_mixin.IoRenderMixin.render_system_font_to_glyphs: ignored {exc!r}")
                        break
                elif m_type == 2:
                    entries = m.get("entries", [])
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == idx:
                            code = m_first + c_idx
                            try:
                                char_val = chr(code)
                            except Exception as exc:
                                log_debug(f"io_render_mixin.IoRenderMixin.render_system_font_to_glyphs: ignored {exc!r}")
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
                            except Exception as exc:
                                log_debug(f"io_render_mixin.IoRenderMixin.render_system_font_to_glyphs: ignored {exc!r}")
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
        
        auto_metrics = params["auto_metrics"]
        inf_list = self.metadata.get("INF1", [])
        ascent = inf_list[0].get("ascent", 0) if inf_list else 0
        if ascent <= 0:
            ascent = int(self.cell_h * 0.75)
            
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
            
            new_glyph = render_glyph(char_str, params, self.cell_w, self.cell_h, ascent)
            
            pixel_changes.append((sheet_idx, cell_x, cell_y, old_glyph_crop, new_glyph))
            
            # Recalculate metrics if requested
            if auto_metrics:
                new_kern, new_width = ink_metrics(new_glyph)
                    
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
