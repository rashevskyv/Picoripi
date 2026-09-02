from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr

_GLYPH_PREVIEW_PX = 28
_GLYPH_PREVIEW_BG = QtGui.QColor("#000000")


class GlyphTableMixin:
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

    def _invalidate_glyph_preview_cache(self, sheet_img=None) -> None:
        cache = getattr(self, "_glyph_preview_cache", None)
        if not cache:
            return
        if sheet_img is None:
            cache.clear()
            return
        sid = id(sheet_img)
        for key in [k for k in cache if k[0] == sid]:
            del cache[key]

    def _glyph_preview_icon(self, sheet_images: list, sheet_idx: int, gx: int, gy: int) -> QtGui.QIcon:
        if not sheet_images or not (0 <= sheet_idx < len(sheet_images)):
            return QtGui.QIcon()
        cache = getattr(self, "_glyph_preview_cache", None)
        if cache is None:
            cache = {}
            self._glyph_preview_cache = cache
        sheet_img = sheet_images[sheet_idx]
        key = (id(sheet_img), gx, gy, self.cell_w, self.cell_h)
        icon = cache.get(key)
        if icon is not None:
            return icon
        crop = sheet_img.copy(gx * self.cell_w, gy * self.cell_h, self.cell_w, self.cell_h)
        pixmap = QtGui.QPixmap.fromImage(crop).scaled(
            _GLYPH_PREVIEW_PX,
            _GLYPH_PREVIEW_PX,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation,
        )
        icon = QtGui.QIcon(pixmap)
        cache[key] = icon
        return icon

    def _ensure_table_item(self, row: int, col: int) -> QtWidgets.QTableWidgetItem:
        item = self.table_glyphs.item(row, col)
        if item is None:
            item = QtWidgets.QTableWidgetItem()
            self.table_glyphs.setItem(row, col, item)
        return item

    def _set_glyph_preview_item(self, row: int, col: int, icon: QtGui.QIcon) -> None:
        item = self._ensure_table_item(row, col)
        item.setText("")
        item.setIcon(icon)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        item.setBackground(QtGui.QBrush(_GLYPH_PREVIEW_BG))
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def _style_font_char_item(self, item: QtWidgets.QTableWidgetItem) -> None:
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        if getattr(self, "is_dark_theme", True):
            item.setForeground(QtGui.QBrush(QtGui.QColor("#88888b")))
            item.setBackground(QtGui.QBrush(QtGui.QColor("#1a1a20")))
        else:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#7e8a9b")))
            item.setBackground(QtGui.QBrush(QtGui.QColor("#eef1f6")))
        item.setToolTip(tr("Font Character (read-only, stored in font metadata)"))

    def _prepare_font_metadata(self) -> tuple[list, list]:
        maps = self.metadata.get("MAP1", [])
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        return maps, packets

    def _build_glyph_to_char_mapping(self, maps: list) -> dict[int, tuple[str, str]]:
        glyph_to_char = {}
        for idx in range(self.start_glyph, self.end_glyph + 1):
            raw_char = self._resolve_char_from_maps(idx, maps)
            char_val, font_char_val = self._get_glyph_translation_mapping(idx, raw_char)
            glyph_to_char[idx] = (char_val, font_char_val)
        return glyph_to_char

    def _build_original_glyph_to_char_mapping(self) -> dict[int, str]:
        orig_glyph_to_char = {}
        if self.original_font_metadata:
            orig_maps = self.original_font_metadata.get("MAP1", [])
            for idx in range(self.start_glyph, self.end_glyph + 1):
                orig_char = self._resolve_char_from_maps(idx, orig_maps)
                orig_glyph_to_char[idx] = orig_char
        return orig_glyph_to_char

    def _filter_glyphs_by_search(
        self,
        glyph_to_char: dict[int, tuple[str, str]],
        orig_glyph_to_char: dict[int, str],
        packets: list,
        search_query: str
    ) -> list[tuple]:
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
        return rows_data

    def _populate_single_glyph_row(self, r_idx: int, data: tuple) -> None:
        idx, char_val, font_char_val, sheet_idx, gx, gy, kerning, width, orig_char_data = data

        header_item = self.table_glyphs.verticalHeaderItem(r_idx)
        if header_item is None:
            header_item = QtWidgets.QTableWidgetItem()
            self.table_glyphs.setVerticalHeaderItem(r_idx, header_item)
        header_item.setText(str(idx))

        item_orig_char = self._ensure_table_item(r_idx, 1)
        item_char = self._ensure_table_item(r_idx, 3)
        item_font_char = self._ensure_table_item(r_idx, 4)
        item_sheet = self._ensure_table_item(r_idx, 5)
        item_tile = self._ensure_table_item(r_idx, 6)
        item_kern = self._ensure_table_item(r_idx, 7)
        item_width = self._ensure_table_item(r_idx, 8)

        item_orig_char.setText(orig_char_data)
        item_char.setText(char_val)
        item_font_char.setText(font_char_val)
        item_sheet.setText(f"Sheet {sheet_idx}")
        item_tile.setText(f"Row {gy}, Col {gx}")
        item_kern.setText(str(kerning))
        item_width.setText(str(width))

        not_editable = ~QtCore.Qt.ItemFlag.ItemIsEditable
        for item in (item_orig_char, item_sheet, item_tile):
            item.setFlags(item.flags() & not_editable)

        self._style_font_char_item(item_font_char)

        editable = QtCore.Qt.ItemFlag.ItemIsEditable
        item_char.setFlags(item_char.flags() | editable)
        item_kern.setFlags(item_kern.flags() | editable)
        item_width.setFlags(item_width.flags() | editable)

        self._set_glyph_preview_item(
            r_idx, 0, self._glyph_preview_icon(self.original_sheet_images, sheet_idx, gx, gy)
        )
        self._set_glyph_preview_item(
            r_idx, 2, self._glyph_preview_icon(self.sheet_images, sheet_idx, gx, gy)
        )

    def _fill_glyph_table(self, rows_data: list[tuple]) -> None:
        self.table_glyphs.setRowCount(len(rows_data))
        for r_idx, data in enumerate(rows_data):
            self._populate_single_glyph_row(r_idx, data)

    def _restore_glyph_table_column_widths(self) -> None:
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
        if hasattr(self, "_fit_glyph_table_headers"):
            self._fit_glyph_table_headers()

    def populate_glyph_table(self):
        if not self.sheet_images:
            return

        table = self.table_glyphs
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            maps, packets = self._prepare_font_metadata()
            glyph_to_char = self._build_glyph_to_char_mapping(maps)
            orig_glyph_to_char = self._build_original_glyph_to_char_mapping()
            search_query = self.table_search.text().lower()
            rows_data = self._filter_glyphs_by_search(
                glyph_to_char, orig_glyph_to_char, packets, search_query
            )
            self._fill_glyph_table(rows_data)
            self._restore_glyph_table_column_widths()
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)

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
        self._set_glyph_preview_item(
            found_row, 2, self._glyph_preview_icon(self.sheet_images, sheet_idx, gx, gy)
        )

        self.table_glyphs.blockSignals(False)
