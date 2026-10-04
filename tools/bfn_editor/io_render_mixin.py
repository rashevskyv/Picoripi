"""Font editor: render a system or TTF font into glyphs, and move a glyph's pixels inside its cell.

``render_glyph_image`` (in ``render_font_dialog``) draws one character into a cell and ``auto_metrics`` measures it; the dialog's
preview and ``render_glyphs`` (one undo step for a list of glyphs) both use them, so a script can render
exactly what the dialog would.
"""
from PyQt6 import QtGui, QtWidgets

from core import font_formats
from core.i18n import tr

from tools.bfn_editor.bfn_widgets import RenderFontDialog
from tools.bfn_editor.render_font_dialog import render_glyph_image
from tools.bfn_editor.bfn_commands import RenderFontCommand


def auto_metrics(image, cell_w, cell_h):
    """``(kerning, width)`` of a rendered glyph from its ink; a column of 5+ inked pixels at an edge
    gets one pixel of room."""
    columns = [x for x in range(cell_w) if any(image.pixelColor(x, y).alpha() > 15 for y in range(cell_h))]
    if not columns:
        return 0, cell_w // 2
    min_x, max_x = columns[0], columns[-1]

    def longest_run(x):
        best = run = 0
        for y in range(cell_h):
            run = run + 1 if image.pixelColor(x, y).alpha() > 15 else 0
            best = max(best, run)
        return best

    kerning = min_x if longest_run(min_x) < 5 else max(0, min_x - 1)
    right = max_x if longest_run(max_x) < 5 else max_x + 1
    return kerning, right - kerning + 1


class IoRenderMixin:
    def glyph_characters(self):
        """``{glyph index: character it stands for}``: the translated letter when the translation map
        puts one on the glyph's character, else the character itself."""
        result = {}
        reverse = getattr(self, "reverse_translation_map", None) or {}
        translation = getattr(self, "translation_map", None) or {}
        chars = {glyph: char for char, glyph in font_formats.char_map(self.metadata).items()}
        for idx in range(self.start_glyph, self.end_glyph + 1):
            char_val = chars.get(idx, "")
            if char_val:
                result[idx] = reverse.get(char_val, char_val)
            elif translation.get(f"#g{idx}"):
                result[idx] = translation[f"#g{idx}"]   # a glyph with no MAP1 entry, mapped by index
        return result

    def _glyph_cell(self, idx):
        rem = idx - self.start_glyph
        cell = rem % (self.rows * self.cols)
        return rem // (self.rows * self.cols), (cell % self.rows) * self.cell_w, (cell // self.rows) * self.cell_h

    def selected_glyph_indices(self):
        """The glyphs selected in the table, else the one selected on the sheet."""
        rows = sorted({index.row() for index in self.table_glyphs.selectionModel().selectedRows()})
        glyphs = []
        for row in rows:
            header = self.table_glyphs.verticalHeaderItem(row)
            if header and header.text().isdigit():
                glyphs.append(int(header.text()))
        if not glyphs and self.get_selected_glyph_index() >= 0:
            glyphs = [self.get_selected_glyph_index()]
        return glyphs

    def move_glyph_pixels(self, dx, dy, glyphs=None):
        """Shift each glyph's pixels by ``(dx, dy)`` inside its cell (what leaves the cell is lost) as one
        undo step, for every format: the cell is what the format packs. Returns the number of glyphs moved."""
        glyphs = self.selected_glyph_indices() if glyphs is None else glyphs
        changes = []
        for idx in glyphs:
            if not self.start_glyph <= idx <= self.end_glyph:
                continue
            sheet_idx, cell_x, cell_y = self._glyph_cell(idx)
            if not 0 <= sheet_idx < len(self.sheet_images):
                continue
            old = self.sheet_images[sheet_idx].copy(cell_x, cell_y, self.cell_w, self.cell_h)
            new = QtGui.QImage(old.size(), old.format())
            new.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(new)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Source)
            painter.drawImage(dx, dy, old)
            painter.end()
            changes.append((sheet_idx, cell_x, cell_y, old, new))
        if changes:
            self.undo_stack.push(RenderFontCommand(self, changes, [], "Move glyph"))
            self._set_dirty(True)
        return len(changes)

    def render_glyphs(self, glyphs, params, chars=None, description="Render Font"):
        """Draw each glyph's character with ``params`` (the dialog's ``get_params``) as one undo step.

        ``chars`` overrides the character of a glyph (``{index: char}``); the default is
        ``glyph_characters()``. Returns the number of glyphs drawn.
        """
        chars = chars if chars is not None else self.glyph_characters()
        ascent = (self.metadata.get("INF1") or [{}])[0].get("ascent", 0)
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        pixel_changes, metrics_changes = [], []
        for idx in glyphs:
            char_str = chars.get(idx, "")
            if not char_str:
                continue
            sheet_idx, cell_x, cell_y = self._glyph_cell(idx)
            old = self.sheet_images[sheet_idx].copy(cell_x, cell_y, self.cell_w, self.cell_h)
            new = render_glyph_image(char_str, params, self.cell_w, self.cell_h, ascent)
            pixel_changes.append((sheet_idx, cell_x, cell_y, old, new))
            wid_idx = idx - self.first_code
            if params.get("auto_metrics") and wid_idx >= 0:
                kerning, width = auto_metrics(new, self.cell_w, self.cell_h)
                if getattr(self, "font_format", "bfn") == "g1t":
                    # A G1T has no widths: the game's rule is the ink plus the font's spacing
                    kerning, width = kerning, width + int(getattr(self, "font_params", {}).get("spacing", 0))
                if wid_idx >= len(packets):
                    packets.extend({"kerning": 0, "width": self.cell_w} for _ in range(wid_idx - len(packets) + 1))
                    wid["last_code_included"] = self.first_code + len(packets)
                metrics_changes.append((idx, packets[wid_idx]["kerning"], kerning, packets[wid_idx]["width"], width))
        if pixel_changes:
            self.undo_stack.push(RenderFontCommand(self, pixel_changes, metrics_changes, description))
            self._set_dirty(True)
        return len(pixel_changes)

    def render_system_font_to_glyphs(self, selected_glyphs=None):
        if not self.sheet_images:
            return
        glyph_to_char = self.glyph_characters()

        # Glyphs for the dialog's live preview: the selection, else the first 30 with a character
        has_sel = bool(selected_glyphs) or (self.selected_cell is not None and self.current_sheet_index >= 0)
        if selected_glyphs:
            glyphs_for_preview = list(selected_glyphs)
        elif self.selected_cell is not None and self.current_sheet_index >= 0:
            gx, gy = self.selected_cell
            idx = self.start_glyph + self.current_sheet_index * (self.rows * self.cols) + gy * self.rows + gx
            glyphs_for_preview = [idx] if self.start_glyph <= idx <= self.end_glyph else []
        else:
            glyphs_for_preview = [idx for idx in range(self.start_glyph, self.end_glyph + 1)
                                  if glyph_to_char.get(idx, "").strip()][:30]
        preview_list = []
        for idx in glyphs_for_preview:
            if not glyph_to_char.get(idx):
                continue
            sheet_idx, cell_x, cell_y = self._glyph_cell(idx)
            img = (self.sheet_images[sheet_idx].copy(cell_x, cell_y, self.cell_w, self.cell_h)
                   if 0 <= sheet_idx < len(self.sheet_images) else None)
            preview_list.append({"char": glyph_to_char[idx], "img": img, "idx": idx})

        dialog = RenderFontDialog(self, self.cell_w, self.cell_h, has_selected_glyph=has_sel, preview_list=preview_list)
        dialog.spin_start_glyph.setValue(self.start_glyph)
        dialog.spin_end_glyph.setValue(self.end_glyph)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        params = dialog.get_params()

        scope = params["scope"]
        everything = range(self.start_glyph, self.end_glyph + 1)
        if scope == "selected" and has_sel:
            glyphs_to_render = list(selected_glyphs) if selected_glyphs else glyphs_for_preview
        elif scope == "all":
            glyphs_to_render = list(everything)
        elif scope == "cyrillic":
            glyphs_to_render = [i for i in everything if "Ѐ" <= glyph_to_char.get(i, "") <= "ӿ"]
        elif scope == "latin":
            glyphs_to_render = [i for i in everything if glyph_to_char.get(i, "").isascii()
                                and glyph_to_char.get(i, "").isalpha()]
        elif scope == "custom":
            glyphs_to_render = list(range(max(self.start_glyph, params["start_glyph"]),
                                          min(self.end_glyph, params["end_glyph"]) + 1))
        else:
            glyphs_to_render = []
        if not glyphs_to_render:
            QtWidgets.QMessageBox.warning(self, tr("No Glyphs"), tr("No valid glyphs found to render in the selected scope."))
            return
        count = self.render_glyphs(glyphs_to_render, params, glyph_to_char, f"Render Font ({scope})")
        if count:
            QtWidgets.QMessageBox.information(
                self, tr("Success"), tr("Successfully rendered {0} glyphs using the system font!", count))
