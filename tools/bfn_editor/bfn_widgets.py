from PyQt5 import QtCore, QtGui, QtWidgets

class ImageView(QtWidgets.QGraphicsView):
    clicked = QtCore.pyqtSignal(QtCore.QPointF)
    scaleChanged = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QtGui.QPainter.Antialiasing, False)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)  # Needed to change cursor on hover
        self.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.black))
        self.setStyleSheet("background-color: black;")
        
        self._panning = False
        self._last_pos = None
        self._scale = 1.0
        self._scale_min = 0.5
        self._scale_max = 20.0
        self._dragging_handle = None  # 'kerning' | 'width' | None
        self._drag_start_scene_x = None
        self._drag_start_kern = 0
        self._drag_start_width = 0

    def set_scale(self, scale):
        self._scale = scale
        self.resetTransform()
        self.scale(self._scale, self._scale)
        self.scaleChanged.emit(self._scale)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            scene_pos = self.mapToScene(pos)
            
            # Check if dragging lines of selected cell
            v = self.parent()
            while v and not hasattr(v, 'selected_cell'):
                v = v.parent()
                
            if v and v.selected_cell and v.get_selected_glyph_index() != -1:
                idx = v.get_selected_glyph_index()
                wid = v.metadata.get("WID1", [{}])[0]
                packets = wid.get("packets", [])
                
                wid_idx = idx - v.first_code
                if 0 <= wid_idx < len(packets):
                    kerning = packets[wid_idx]["kerning"]
                    width = packets[wid_idx]["width"]
                    
                    gx, gy = v.selected_cell
                    x0 = gx * v.real_w
                    y0 = gy * v.real_h
                    
                    left_x = x0 + kerning
                    right_x = x0 + kerning + width
                    
                    tolerance = max(2.0, 8.0 / self._scale)
                    
                    if y0 <= scene_pos.y() <= y0 + v.real_h:
                        if abs(scene_pos.x() - left_x) <= tolerance:
                            self._dragging_handle = 'kerning'
                            self._drag_start_scene_x = scene_pos.x()
                            self._drag_start_kern = kerning
                            self._drag_start_width = width
                            self.setCursor(QtCore.Qt.SizeHorCursor)
                            event.accept()
                            return
                        elif abs(scene_pos.x() - right_x) <= tolerance:
                            self._dragging_handle = 'width'
                            self._drag_start_scene_x = scene_pos.x()
                            self._drag_start_kern = kerning
                            self._drag_start_width = width
                            self.setCursor(QtCore.Qt.SizeHorCursor)
                            event.accept()
                            return
            
            self._dragging_handle = None
            self._drag_start_scene_x = None
            self.clicked.emit(scene_pos)
            event.accept()
            return
            
        elif event.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
            
        super().mousePressEvent(event)
 
    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        pos = event.pos()
        scene_pos = self.mapToScene(pos)
        
        # Drag handle processing
        if self._dragging_handle is not None and self._drag_start_scene_x is not None:
            v = self.parent()
            while v and not hasattr(v, 'selected_cell'):
                v = v.parent()
                
            if v and v.selected_cell and v.get_selected_glyph_index() != -1:
                idx = v.get_selected_glyph_index()
                wid = v.metadata.get("WID1", [{}])[0]
                packets = wid.get("packets", [])
                wid_idx = idx - v.first_code
                
                if 0 <= wid_idx < len(packets):
                    dx = scene_pos.x() - self._drag_start_scene_x
                    
                    if self._dragging_handle == 'kerning':
                        new_kern = int(round(self._drag_start_kern + dx))
                        new_kern = max(-128, min(127, new_kern))
                        
                        v.spin_kerning.blockSignals(True)
                        v.spin_kerning.setValue(new_kern)
                        v.spin_kerning.blockSignals(False)
                        
                        packets[wid_idx]["kerning"] = new_kern
                        v.update_overlays()
                        v.update_simulation()
                    elif self._dragging_handle == 'width':
                        new_width = int(round(self._drag_start_width + dx))
                        new_width = max(0, min(255, new_width))
                        
                        v.spin_width.blockSignals(True)
                        v.spin_width.setValue(new_width)
                        v.spin_width.blockSignals(False)
                        
                        packets[wid_idx]["width"] = new_width
                        v.update_overlays()
                        v.update_simulation()
                        
            event.accept()
            return
            
        if self._panning and self._last_pos is not None:
            delta = pos - self._last_pos
            self._last_pos = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
            
        # Hover cursor check
        v = self.parent()
        while v and not hasattr(v, 'selected_cell'):
            v = v.parent()
            
        if v and v.selected_cell and v.get_selected_glyph_index() != -1:
            idx = v.get_selected_glyph_index()
            wid = v.metadata.get("WID1", [{}])[0]
            packets = wid.get("packets", [])
            wid_idx = idx - v.first_code
            if 0 <= wid_idx < len(packets):
                kerning = packets[wid_idx]["kerning"]
                width = packets[wid_idx]["width"]
                
                gx, gy = v.selected_cell
                x0 = gx * v.real_w
                y0 = gy * v.real_h
                
                left_x = x0 + kerning
                right_x = x0 + kerning + width
                
                tolerance = max(2.0, 8.0 / self._scale)
                if y0 <= scene_pos.y() <= y0 + v.real_h:
                    if abs(scene_pos.x() - left_x) <= tolerance or abs(scene_pos.x() - right_x) <= tolerance:
                        self.setCursor(QtCore.Qt.SizeHorCursor)
                        super().mouseMoveEvent(event)
                        return
                    
        self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton and self._dragging_handle is not None:
            v = self.parent()
            while v and not hasattr(v, 'selected_cell'):
                v = v.parent()
                
            if v and v.selected_cell and v.get_selected_glyph_index() != -1:
                idx = v.get_selected_glyph_index()
                wid = v.metadata.get("WID1", [{}])[0]
                packets = wid.get("packets", [])
                wid_idx = idx - v.first_code
                
                if 0 <= wid_idx < len(packets):
                    old_kern, old_width = self._drag_start_kern, self._drag_start_width
                    new_kern = packets[wid_idx]["kerning"]
                    new_width = packets[wid_idx]["width"]
                    
                    if old_kern != new_kern or old_width != new_width:
                        # Restore old values temporarily for QUndoCommand to execute properly
                        packets[wid_idx]["kerning"] = old_kern
                        packets[wid_idx]["width"] = old_width
                        
                        from tools.bfn_editor.bfn_commands import EditMetricsCommand
                        cmd = EditMetricsCommand(v, idx, old_kern, new_kern, old_width, new_width)
                        v.undo_stack.push(cmd)
                        v._set_dirty(True)
            
            self._dragging_handle = None
            self._drag_start_scene_x = None
            self.unsetCursor()
            event.accept()
            return
            
        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = False
            self._last_pos = None
            self.unsetCursor()
            event.accept()
            return
            
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
            
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        
        pos = event.pos()
        old_scene_pos = self.mapToScene(pos)
        
        new_scale = self._scale * factor
        new_scale = max(self._scale_min, min(self._scale_max, new_scale))
        
        self.set_scale(new_scale)
        
        new_scene_pos = self.mapToScene(pos)
        d = new_scene_pos - old_scene_pos
        self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x() * new_scale))
        self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y() * new_scale))
        
        event.accept()

class SimGlyphItem(QtWidgets.QGraphicsItem):
    def __init__(self, glyph_idx: int, char_str: str, sheet_idx: int, cell_x: int, cell_y: int, x_offset: int, y_offset: int, char_pos_idx: int, viewer):
        super().__init__()
        self.glyph_idx = int(glyph_idx)
        self.char_str = str(char_str)
        self.sheet_idx = int(sheet_idx)
        self.cell_x = int(cell_x)
        self.cell_y = int(cell_y)
        self.x_offset = int(x_offset)
        self.y_offset = int(y_offset)
        self.char_pos_idx = int(char_pos_idx)
        self.viewer = viewer
        self._dragging_handle = None
        self._drag_start_scene_x = None
        self._drag_start_kern = 0
        self._drag_start_width = 0
        
        self.setPos(x_offset, y_offset)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QtCore.QRectF:
        width = self.viewer.cell_w
        wid = self.viewer.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = self.glyph_idx - self.viewer.first_code
        if 0 <= wid_idx < len(packets):
            width = packets[wid_idx]["width"]
            
        return QtCore.QRectF(-2, -2, width + 4, self.viewer.cell_h + 4)

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        if self.sheet_idx < 0 or self.sheet_idx >= len(self.viewer.sheet_images):
            return
            
        sheet_img = self.viewer.sheet_images[self.sheet_idx]
        
        kerning = 0
        width = self.viewer.cell_w
        wid = self.viewer.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = self.glyph_idx - self.viewer.first_code
        if 0 <= wid_idx < len(packets):
            kerning = packets[wid_idx]["kerning"]
            width = packets[wid_idx]["width"]
            
        crop_x = self.cell_x + kerning
        crop_w = width
        if crop_w <= 0:
            crop_w = 1
            
        glyph_crop = sheet_img.copy(crop_x, self.cell_y, crop_w, self.viewer.cell_h)
        painter.drawImage(0, 0, glyph_crop)
        
        if getattr(self.viewer, 'selected_sim_item', None) == self:
            pen_border = QtGui.QPen(QtGui.QColor('#00b4d8'))
            pen_border.setWidth(1)
            pen_border.setStyle(QtCore.Qt.DashLine)
            pen_border.setCosmetic(True)
            painter.setPen(pen_border)
            painter.drawRect(0, 0, width, self.viewer.cell_h)
            
            left_x = 0
            pen_k = QtGui.QPen(QtGui.QColor('#3a86c8'))
            pen_k.setWidth(1)
            pen_k.setCosmetic(True)
            painter.setPen(pen_k)
            painter.drawLine(left_x, 0, left_x, self.viewer.cell_h)
            
            right_x = width
            pen_w = QtGui.QPen(QtGui.QColor('#e63946'))
            pen_w.setWidth(1)
            pen_w.setCosmetic(True)
            painter.setPen(pen_w)
            painter.drawLine(right_x, 0, right_x, self.viewer.cell_h)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self.viewer.select_sim_glyph(self)
            
            p = event.pos()
            kerning = 0
            width = self.viewer.cell_w
            wid = self.viewer.metadata.get("WID1", [{}])[0]
            packets = wid.get("packets", [])
            wid_idx = self.glyph_idx - self.viewer.first_code
            if 0 <= wid_idx < len(packets):
                kerning = packets[wid_idx]["kerning"]
                width = packets[wid_idx]["width"]
                
            left_x = 0
            right_x = width
            
            scale = self.viewer.sim_view._scale
            tolerance = max(2.0, 8.0 / scale)
            
            if abs(p.x() - left_x) <= tolerance:
                self._dragging_handle = 'kerning'
                self._drag_start_scene_x = event.scenePos().x()
                self._drag_start_kern = kerning
                self._drag_start_width = width
                self.viewer._dragging_in_sim = True
                self.setCursor(QtCore.Qt.SizeHorCursor)
                event.accept()
                return
            elif abs(p.x() - right_x) <= tolerance:
                self._dragging_handle = 'width'
                self._drag_start_scene_x = event.scenePos().x()
                self._drag_start_kern = kerning
                self._drag_start_width = width
                self.viewer._dragging_in_sim = True
                self.setCursor(QtCore.Qt.SizeHorCursor)
                event.accept()
                return
                
            self._dragging_handle = None
            self._drag_start_scene_x = None
            event.accept()
            return
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if self._dragging_handle is not None and self._drag_start_scene_x is not None:
            wid = self.viewer.metadata.get("WID1", [{}])[0]
            packets = wid.get("packets", [])
            wid_idx = self.glyph_idx - self.viewer.first_code
            
            if 0 <= wid_idx < len(packets):
                dx = event.scenePos().x() - self._drag_start_scene_x
                
                if self._dragging_handle == 'kerning':
                    new_kern = int(round(self._drag_start_kern + dx))
                    new_kern = max(-128, min(127, new_kern))
                    
                    self.viewer.spin_kerning.blockSignals(True)
                    self.viewer.spin_kerning.setValue(new_kern)
                    self.viewer.spin_kerning.blockSignals(False)
                    
                    packets[wid_idx]["kerning"] = new_kern
                elif self._dragging_handle == 'width':
                    new_width = int(round(self._drag_start_width + dx))
                    new_width = max(0, min(255, new_width))
                    
                    self.viewer.spin_width.blockSignals(True)
                    self.viewer.spin_width.setValue(new_width)
                    self.viewer.spin_width.blockSignals(False)
                    
                    packets[wid_idx]["width"] = new_width
                
                self.prepareGeometryChange()
                self.update()
                self.viewer.reposition_simulation_items()
                
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            if self._dragging_handle is not None:
                wid = self.viewer.metadata.get("WID1", [{}])[0]
                packets = wid.get("packets", [])
                wid_idx = self.glyph_idx - self.viewer.first_code
                
                if 0 <= wid_idx < len(packets):
                    old_kern, old_width = self._drag_start_kern, self._drag_start_width
                    new_kern = packets[wid_idx]["kerning"]
                    new_width = packets[wid_idx]["width"]
                    
                    if old_kern != new_kern or old_width != new_width:
                        # Restore old values temporarily for QUndoCommand to execute properly
                        packets[wid_idx]["kerning"] = old_kern
                        packets[wid_idx]["width"] = old_width
                        
                        from tools.bfn_editor.bfn_commands import EditMetricsCommand
                        cmd = EditMetricsCommand(self.viewer, self.glyph_idx, old_kern, new_kern, old_width, new_width)
                        self.viewer.undo_stack.push(cmd)
                        self.viewer._set_dirty(True)
                
                self._dragging_handle = None
                self._drag_start_scene_x = None
                self.viewer._dragging_in_sim = False
                self.unsetCursor()
                self.viewer.update_simulation()
                event.accept()
                return
        super().mouseReleaseEvent(event)

class SimImageView(QtWidgets.QGraphicsView):
    scaleChanged = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QtGui.QPainter.Antialiasing, False)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.black))
        self.setStyleSheet("background-color: black;")
        
        self._panning = False
        self._last_pos = None
        self._scale = 1.0
        self._scale_min = 0.2
        self._scale_max = 15.0

    def set_scale(self, scale):
        self._scale = scale
        self.resetTransform()
        self.scale(self._scale, self._scale)
        self.scaleChanged.emit(self._scale)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        pos = event.pos()
        if self._panning and self._last_pos is not None:
            delta = pos - self._last_pos
            self._last_pos = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = False
            self._last_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
            
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        
        pos = event.pos()
        old_scene_pos = self.mapToScene(pos)
        
        new_scale = self._scale * factor
        new_scale = max(self._scale_min, min(self._scale_max, new_scale))
        
        self.set_scale(new_scale)
        
        new_scene_pos = self.mapToScene(pos)
        d = new_scene_pos - old_scene_pos
        self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x() * new_scale))
        self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y() * new_scale))
        
        event.accept()

class GridItem(QtWidgets.QGraphicsItem):
    def __init__(self, cw: int, ch: int, rows: int, cols: int, parent=None):
        super().__init__(parent)
        self.cw = int(cw)
        self.ch = int(ch)
        self.rows = int(rows)
        self.cols = int(cols)
        self.real_w = self.cw
        self.real_h = self.ch
        self.pen = QtGui.QPen(QtGui.QColor('#446622aa'))
        self.pen.setWidth(1)
        self.pen.setCosmetic(True)

    def boundingRect(self) -> QtCore.QRectF:
        w = self.rows * self.real_w
        h = self.cols * self.real_h
        return QtCore.QRectF(0, 0, w, h)

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        painter.setPen(self.pen)
        # vertical lines
        for gx in range(self.rows + 1):
            x = gx * self.real_w
            painter.drawLine(x, 0, x, self.cols * self.real_h)
        # horizontal lines
        for gy in range(self.cols + 1):
            y = gy * self.real_h
            painter.drawLine(0, y, self.rows * self.real_w, y)

# Default fill ranges per spellchecker language code.
# Each entry: (start_char, end_char) as single characters.
# Languages not listed fall back to Latin A–Z.
_LANG_FILL_DEFAULTS = {
    # Cyrillic — uppercase А–Я block (U+0410–U+042F)
    "uk": ("\u0410", "\u042F"),  # Ukrainian
    "ru": ("\u0410", "\u042F"),  # Russian
    "be": ("\u0410", "\u042F"),  # Belarusian
    "bg": ("\u0410", "\u042F"),  # Bulgarian
    "sr": ("\u0410", "\u042F"),  # Serbian
    "mk": ("\u0410", "\u042F"),  # Macedonian
    # Greek — uppercase Α–Ω
    "el": ("\u0391", "\u03A9"),
    # Arabic — basic block \u0621–\u064A
    "ar": ("\u0621", "\u064A"),
    # Japanese hiragana — \u3041–\u3096
    "ja": ("\u3041", "\u3096"),
    # Korean — Hangul syllables begin \uAC00
    "ko": ("\uAC00", "\uAC1B"),
}


class FillRangeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, lang=""):
        super().__init__(parent)
        self.setWindowTitle("Fill From To")
        self.setModal(True)
        self.resize(320, 200)

        # Determine defaults from language code (strip region suffix: 'uk_UA' -> 'uk')
        base_lang = lang.split("_")[0].split("-")[0].lower() if lang else ""
        default_start, default_end = _LANG_FILL_DEFAULTS.get(base_lang, ("A", "Z"))

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.input_start = QtWidgets.QLineEdit(default_start)
        self.input_start.setPlaceholderText("e.g. A or U+0410 or 0410")
        self.input_end = QtWidgets.QLineEdit(default_end)
        self.input_end.setPlaceholderText("e.g. Z or U+041A or 041A")

        form.addRow("Start Character / Code:", self.input_start)
        form.addRow("End Character / Code:", self.input_end)
        layout.addLayout(form)

        lang_hint = f" (detected: {base_lang})" if base_lang else ""
        help_lbl = QtWidgets.QLabel(
            f"Enter either a single character or Unicode hex (e.g., U+0410 or 0410).{lang_hint}\n"
            "The table will be filled sequentially starting from the selected row."
        )
        help_lbl.setStyleSheet("color: #88888b; font-size: 11px;")
        layout.addWidget(help_lbl)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_range(self):
        start_txt = self.input_start.text().strip()
        end_txt = self.input_end.text().strip()
        
        def parse_val(txt):
            if not txt:
                return None
            if txt.upper().startswith("U+") or txt.upper().startswith("0X"):
                clean = txt.replace("U+", "").replace("u+", "").replace("0x", "").replace("0X", "")
                try:
                    return int(clean, 16)
                except ValueError:
                    pass
            if len(txt) > 1 and all(c in "0123456789ABCDEFabcdef" for c in txt):
                try:
                    return int(txt, 16)
                except ValueError:
                    pass
            if len(txt) == 1:
                return ord(txt[0])
            try:
                return int(txt)
            except ValueError:
                pass
            return None

        start_val = parse_val(start_txt)
        end_val = parse_val(end_txt)
        return start_val, end_val
