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

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent):
        scene_pos = self.mapToScene(event.pos())
        v = self.parent()
        while v and not hasattr(v, 'selected_cell'):
            v = v.parent()
            
        if not v or v.rows <= 0 or v.cols <= 0 or not v.sheet_images:
            return
            
        gx = int(scene_pos.x() // v.real_w)
        gy = int(scene_pos.y() // v.real_h)
        
        # In ImageView, cell dimensions are real_w (columns) and real_h (rows).
        # We need to ensure we map correctly: gx maps to cols (width), gy maps to rows (height).
        if gx < 0 or gy < 0 or gx >= v.rows or gy >= v.cols:
            return
            
        # Select cell
        v.selected_cell = (gx, gy)
        v.populate_info_panel(gx, gy)
        v.update_overlays()
        
        glyph_idx = v.get_selected_glyph_index()
        if glyph_idx == -1:
            return
            
        menu = QtWidgets.QMenu(self)
        is_dark = getattr(v, 'is_dark_theme', True)
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
            
        action_render = menu.addAction("Render Font to Selected Glyph...")
        action_import = menu.addAction("Import Selected Glyph PNG...")
        action_export = menu.addAction("Export Selected Glyph PNG...")
        
        action = menu.exec_(event.globalPos())
        if action == action_render:
            v.render_system_font_to_glyphs()
        elif action == action_import:
            v.import_glyph_png()
        elif action == action_export:
            v.export_glyph_png()

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
            
        if event.button() == QtCore.Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())
            if item is None:
                v = self.parent()
                while v and not hasattr(v, 'selected_cell'):
                    v = v.parent()
                if v:
                    v.selected_cell = None
                    v.selected_char_index = -1
                    v.selected_sim_item = None
                    v.populate_info_panel(-1, -1)
                    v.update_overlays()
                    v.update_simulation()
                    
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

# Default fill ranges per language key.
# Each tuple: (label shown in combobox, lang_key, start_char, end_char, explicit_sequence)
_FILL_PRESETS = [
    ("Latin  A – Z",                       "la",    "A",      "Z",      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("Latin  a – z",                       "la_l",  "a",      "z",      "abcdefghijklmnopqrstuvwxyz"),
    ("Ukrainian  А – Я (uppercase)",       "uk_u",  "\u0410", "\u042F", "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"),
    ("Ukrainian  а – я (lowercase)",       "uk_l",  "\u0430", "\u044F", "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"),
    ("Russian  А – Я (uppercase with Ё)",  "ru_u",  "\u0410", "\u042F", "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"),
    ("Russian  а – я (lowercase with ё)",  "ru_l",  "\u0430", "\u044F", "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
    ("Belarusian  А – Я (uppercase)",      "be_u",  "\u0410", "\u042F", "АБВГДЕЁЖЗІЙКЛМНОПРСТУЎФХЦЧШЫЬЭЮЯ"),
    ("Belarusian  а – я (lowercase)",      "be_l",  "\u0430", "\u044F", "абвгдеёжзійклмнопрстуўфхцчшыьэюя"),
    ("Greek  Α – Ω (uppercase)",           "el",    "\u0391", "\u03A9", "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"),
    ("Greek  α – ω (lowercase)",           "el_l",  "\u03B1", "\u03C9", "αβγδεζηθικλμνξοπρστυφχψω"),
    ("Arabic  \u0621 – \u064A",            "ar",    "\u0621", "\u064A", None),
    ("Hiragana  \u3041 – \u3096",          "ja",    "\u3041", "\u3096", None),
    ("Katakana  \u30A1 – \u30F6",          "ja_k",  "\u30A1", "\u30F6", None),
    ("Hangul syllables (first 32)",        "ko",    "\uAC00", "\uAC1F", None),
    ("Custom (edit below)",                "custom", "",      "",       None),
]

# Map from spellchecker lang code to preset lang_key
_LANG_TO_PRESET = {
    "uk": "uk_u",
    "ru": "ru_u",
    "be": "be_u",
    "bg": "ru_u",
    "sr": "ru_u",
    "mk": "ru_u",
    "el": "el",
    "ar": "ar",
    "ja": "ja",
    "ko": "ko",
}


class FillRangeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, lang=""):
        super().__init__(parent)
        self.setWindowTitle("Fill From To")
        self.setModal(True)
        self.resize(380, 260)

        # Determine default preset key from spellchecker language
        base_lang = lang.split("_")[0].split("-")[0].lower() if lang else ""
        default_preset_key = _LANG_TO_PRESET.get(base_lang, "la")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Alphabet / Language selector ---
        lang_row = QtWidgets.QHBoxLayout()
        lang_row.addWidget(QtWidgets.QLabel("Alphabet:"))
        self.lang_combo = QtWidgets.QComboBox()
        for item in _FILL_PRESETS:
            label, key = item[0], item[1]
            self.lang_combo.addItem(label, key)
        # Select default
        for i, item in enumerate(_FILL_PRESETS):
            key = item[1]
            if key == default_preset_key:
                self.lang_combo.setCurrentIndex(i)
                break
        lang_row.addWidget(self.lang_combo, 1)
        layout.addLayout(lang_row)

        # --- Start / End and Sequence fields ---
        form = QtWidgets.QFormLayout()
        self.input_start = QtWidgets.QLineEdit()
        self.input_start.setPlaceholderText("e.g. A or U+0410 or 0410")
        self.input_end = QtWidgets.QLineEdit()
        self.input_end.setPlaceholderText("e.g. Z or U+042F or 042F")
        self.input_sequence = QtWidgets.QLineEdit()
        self.input_sequence.setPlaceholderText("Sequence of characters to fill sequentially")
        
        form.addRow("Start Character / Code:", self.input_start)
        form.addRow("End Character / Code:", self.input_end)
        form.addRow("Sequence Preview / Edit:", self.input_sequence)
        layout.addLayout(form)

        help_lbl = QtWidgets.QLabel(
            "Choose a preset, enter a range, or edit the sequence directly.\n"
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

        # Fill fields from current preset, then connect signal
        self._apply_preset(self.lang_combo.currentIndex())
        self.lang_combo.currentIndexChanged.connect(self._apply_preset)

        # If user edits manually — switch combobox to "Custom" and update sequence
        self.input_start.textEdited.connect(self._on_start_end_edited)
        self.input_end.textEdited.connect(self._on_start_end_edited)
        self.input_sequence.textEdited.connect(self._on_manual_edit)

    # ------------------------------------------------------------------
    def _apply_preset(self, index):
        item = _FILL_PRESETS[index]
        label, key, start_ch, end_ch, explicit_seq = item
        if key == "custom":
            return  # keep whatever user typed
            
        self.input_start.blockSignals(True)
        self.input_end.blockSignals(True)
        self.input_sequence.blockSignals(True)
        
        self.input_start.setText(start_ch)
        self.input_end.setText(end_ch)
        
        if explicit_seq:
            self.input_sequence.setText(explicit_seq)
        else:
            # Generate from start and end
            if start_ch and end_ch:
                try:
                    s_code = ord(start_ch)
                    e_code = ord(end_ch)
                    if s_code <= e_code:
                        seq = "".join(chr(c) for c in range(s_code, e_code + 1))
                        self.input_sequence.setText(seq)
                    else:
                        self.input_sequence.setText("")
                except Exception:
                    self.input_sequence.setText("")
            else:
                self.input_sequence.setText("")
                
        self.input_start.blockSignals(False)
        self.input_end.blockSignals(False)
        self.input_sequence.blockSignals(False)

    def _on_manual_edit(self):
        # Switch combobox to "Custom" silently so auto-apply doesn't override
        custom_idx = next(
            (i for i, item in enumerate(_FILL_PRESETS) if item[1] == "custom"),
            -1
        )
        if custom_idx >= 0 and self.lang_combo.currentIndex() != custom_idx:
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(custom_idx)
            self.lang_combo.blockSignals(False)

    def _on_start_end_edited(self):
        self._on_manual_edit()
        self._update_sequence_from_start_end()

    def _update_sequence_from_start_end(self):
        start_val, end_val = self.get_range()
        if start_val is not None and end_val is not None:
            if start_val <= end_val:
                try:
                    seq = "".join(chr(c) for c in range(start_val, end_val + 1))
                    self.input_sequence.blockSignals(True)
                    self.input_sequence.setText(seq)
                    self.input_sequence.blockSignals(False)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    def get_sequence_codes(self):
        txt = self.input_sequence.text()
        return [ord(c) for c in txt]

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


_LAST_RENDER_PARAMS = {
    "font_family": None,
    "size": None,
    "x_offset": 0,
    "y_offset": 0,
    "align_h": None,
    "align_v": None,
    "auto_metrics": True,
    "antialiasing": True,
    "bold": False,
    "italic": False,
    "stretch": 100,
    "v_scale": 100
}


class ScaleSliderWidget(QtWidgets.QWidget):
    valueChanged = QtCore.pyqtSignal(int)
    
    def __init__(self, default_val=100, min_val=-200, max_val=400, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Min spinbox
        self.spin_min = QtWidgets.QSpinBox()
        self.spin_min.setRange(-2000, 2000)
        self.spin_min.setValue(min_val)
        self.spin_min.setToolTip("Minimum scale boundary")
        self.spin_min.setFixedWidth(55)
        
        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.setToolTip("Drag to adjust scale")
        
        # Max spinbox
        self.spin_max = QtWidgets.QSpinBox()
        self.spin_max.setRange(-2000, 2000)
        self.spin_max.setValue(max_val)
        self.spin_max.setToolTip("Maximum scale boundary")
        self.spin_max.setFixedWidth(55)
        
        # Value spinbox
        self.spin_val = QtWidgets.QSpinBox()
        self.spin_val.setRange(-2000, 2000)
        self.spin_val.setValue(default_val)
        self.spin_val.setSuffix(" %")
        self.spin_val.setToolTip("Current scale value")
        self.spin_val.setFixedWidth(70)
        
        layout.addWidget(self.spin_min)
        layout.addWidget(self.slider)
        layout.addWidget(self.spin_max)
        layout.addWidget(self.spin_val)
        
        # Connections
        self.spin_min.valueChanged.connect(self._on_min_changed)
        self.spin_max.valueChanged.connect(self._on_max_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin_val.valueChanged.connect(self._on_spin_changed)
        
    def _on_min_changed(self, val):
        if val >= self.spin_max.value():
            self.spin_max.setValue(val + 1)
        self.slider.setMinimum(val)
        self.slider.setValue(self.spin_val.value())
        
    def _on_max_changed(self, val):
        if val <= self.spin_min.value():
            self.spin_min.setValue(val - 1)
        self.slider.setMaximum(val)
        self.slider.setValue(self.spin_val.value())
        
    def _on_slider_changed(self, val):
        self.spin_val.blockSignals(True)
        self.spin_val.setValue(val)
        self.spin_val.blockSignals(False)
        self.valueChanged.emit(val)
        
    def _on_spin_changed(self, val):
        if val < self.spin_min.value():
            self.spin_min.setValue(val)
        elif val > self.spin_max.value():
            self.spin_max.setValue(val)
            
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.valueChanged.emit(val)
        
    def value(self):
        return self.spin_val.value()
        
    def setValue(self, val):
        self.spin_val.setValue(val)


class RenderFontDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cell_w=24, cell_h=24, has_selected_glyph=False, preview_list=None):
        super().__init__(parent)
        self.setWindowTitle("Render System Font to Glyphs")
        self.setModal(True)
        self.resize(400, 560)
        
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.preview_list = preview_list if preview_list else []
        self.preview_index = 0
        self.char_str = ""
        self.orig_glyph_img = None
        
        # Try to find ascent from BFN Editor metadata for smart default forecasting
        ascent = 0
        v = parent
        while v and not hasattr(v, 'metadata'):
            v = v.parent()
        if v and hasattr(v, 'metadata'):
            inf_list = v.metadata.get("INF1", [])
            if inf_list:
                ascent = inf_list[0].get("ascent", 0)
        self.ascent = ascent

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        
        # --- Real-time Interactive Previews ---
        preview_layout = QtWidgets.QHBoxLayout()
        preview_layout.setContentsMargins(4, 4, 4, 4)
        
        # Original
        orig_box = QtWidgets.QVBoxLayout()
        lbl_orig_title = QtWidgets.QLabel("Original Glyph:")
        lbl_orig_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_orig_title.setStyleSheet("font-weight: bold; color: #88888b; font-size: 11px;")
        orig_box.addWidget(lbl_orig_title)
        
        self.lbl_preview_orig = QtWidgets.QLabel()
        self.lbl_preview_orig.setFixedSize(128, 128)
        self.lbl_preview_orig.setStyleSheet("border: 1px solid #3d405b; background-color: #141419; border-radius: 4px;")
        self.lbl_preview_orig.setAlignment(QtCore.Qt.AlignCenter)
        orig_box.addWidget(self.lbl_preview_orig)
        preview_layout.addLayout(orig_box)
        
        # Arrow
        arrow_lbl = QtWidgets.QLabel("➔")
        arrow_lbl.setStyleSheet("font-size: 24px; color: #00b4d8;")
        preview_layout.addWidget(arrow_lbl, 0, QtCore.Qt.AlignCenter)
        
        # Rendered
        new_box = QtWidgets.QVBoxLayout()
        lbl_new_title = QtWidgets.QLabel("Rendered Font:")
        lbl_new_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_new_title.setStyleSheet("font-weight: bold; color: #00b4d8; font-size: 11px;")
        new_box.addWidget(lbl_new_title)
        
        self.lbl_preview_new = QtWidgets.QLabel()
        self.lbl_preview_new.setFixedSize(128, 128)
        self.lbl_preview_new.setStyleSheet("border: 1px solid #3d405b; background-color: #141419; border-radius: 4px;")
        self.lbl_preview_new.setAlignment(QtCore.Qt.AlignCenter)
        new_box.addWidget(self.lbl_preview_new)
        preview_layout.addLayout(new_box)
        
        layout.addLayout(preview_layout)
        
        # --- Preview Navigation Bar ---
        self.nav_layout = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀")
        self.btn_prev.setFixedSize(30, 24)
        self.btn_prev.clicked.connect(self._on_prev_preview)
        
        self.lbl_preview_info = QtWidgets.QLabel("Glyph 1 of 1")
        self.lbl_preview_info.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_preview_info.setStyleSheet("font-weight: bold; color: #00b4d8; font-size: 11px; text-decoration: underline;")
        self.lbl_preview_info.setCursor(QtCore.Qt.PointingHandCursor)
        self.lbl_preview_info.setToolTip("Click to jump to a specific glyph index, character, or position (e.g., 24)")
        self.lbl_preview_info.mousePressEvent = self._on_preview_info_clicked
        
        self.btn_next = QtWidgets.QPushButton("▶")
        self.btn_next.setFixedSize(30, 24)
        self.btn_next.clicked.connect(self._on_next_preview)
        
        self.nav_layout.addWidget(self.btn_prev)
        self.nav_layout.addWidget(self.lbl_preview_info, 1)
        self.nav_layout.addWidget(self.btn_next)
        layout.addLayout(self.nav_layout)
        
        # Hide navigation elements if there's only 1 or no preview items
        has_multiple_previews = len(self.preview_list) > 1
        self.btn_prev.setVisible(has_multiple_previews)
        self.btn_next.setVisible(has_multiple_previews)
        self.lbl_preview_info.setVisible(has_multiple_previews)
        
        layout.addSpacing(5)
        
        # --- Form parameters ---
        form = QtWidgets.QFormLayout()
        
        # 1. Font Family
        self.font_combo = QtWidgets.QFontComboBox()
        if _LAST_RENDER_PARAMS["font_family"] is not None:
            self.font_combo.setCurrentFont(QtGui.QFont(_LAST_RENDER_PARAMS["font_family"]))
        form.addRow("Font Family:", self.font_combo)
        
        # Configure font family search to match substrings/middle words
        completer = self.font_combo.completer()
        if completer:
            completer.setFilterMode(QtCore.Qt.MatchContains)
        
        # 2. Font Size
        self.spin_size = QtWidgets.QSpinBox()
        self.spin_size.setRange(6, 120)
        if _LAST_RENDER_PARAMS["size"] is not None:
            self.spin_size.setValue(_LAST_RENDER_PARAMS["size"])
        else:
            default_size = self.ascent if self.ascent > 0 else max(6, cell_h - 4)
            self.spin_size.setValue(default_size)
        form.addRow("Font Size (px):", self.spin_size)
        
        # Font Style (Bold & Italic)
        self.style_layout = QtWidgets.QHBoxLayout()
        self.chk_bold = QtWidgets.QCheckBox("Bold")
        self.chk_bold.setChecked(_LAST_RENDER_PARAMS.get("bold", False))
        self.chk_italic = QtWidgets.QCheckBox("Italic")
        self.chk_italic.setChecked(_LAST_RENDER_PARAMS.get("italic", False))
        self.style_layout.addWidget(self.chk_bold)
        self.style_layout.addWidget(self.chk_italic)
        self.style_layout.addStretch()
        form.addRow("Font Style:", self.style_layout)
        
        # Horizontal Scale
        self.scale_h = ScaleSliderWidget(
            default_val=_LAST_RENDER_PARAMS.get("stretch", 100),
            min_val=-200,
            max_val=400
        )
        form.addRow("Horizontal Scale:", self.scale_h)
        
        # Vertical Scale
        self.scale_v = ScaleSliderWidget(
            default_val=_LAST_RENDER_PARAMS.get("v_scale", 100),
            min_val=-200,
            max_val=400
        )
        form.addRow("Vertical Scale:", self.scale_v)
        
        # 3. Offsets X & Y
        self.spin_x = QtWidgets.QSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.setValue(_LAST_RENDER_PARAMS["x_offset"])
        form.addRow("X Offset:", self.spin_x)
        
        self.spin_y = QtWidgets.QSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.setValue(_LAST_RENDER_PARAMS["y_offset"])
        form.addRow("Y Offset:", self.spin_y)
        
        # 4. Horizontal Alignment
        self.combo_align_h = QtWidgets.QComboBox()
        self.combo_align_h.addItem("Center", QtCore.Qt.AlignHCenter)
        self.combo_align_h.addItem("Left", QtCore.Qt.AlignLeft)
        self.combo_align_h.addItem("Right", QtCore.Qt.AlignRight)
        if _LAST_RENDER_PARAMS["align_h"] is not None:
            idx = self.combo_align_h.findData(_LAST_RENDER_PARAMS["align_h"])
            if idx >= 0:
                self.combo_align_h.setCurrentIndex(idx)
        form.addRow("Horizontal Alignment:", self.combo_align_h)
        
        # 5. Vertical Alignment
        self.combo_align_v = QtWidgets.QComboBox()
        self.combo_align_v.addItem("Center", QtCore.Qt.AlignVCenter)
        self.combo_align_v.addItem("Top", QtCore.Qt.AlignTop)
        self.combo_align_v.addItem("Bottom", QtCore.Qt.AlignBottom)
        self.combo_align_v.addItem("Baseline", "baseline")
        if _LAST_RENDER_PARAMS["align_v"] is not None:
            idx = self.combo_align_v.findData(_LAST_RENDER_PARAMS["align_v"])
            if idx >= 0:
                self.combo_align_v.setCurrentIndex(idx)
        else:
            self.combo_align_v.setCurrentIndex(3)
        form.addRow("Vertical Alignment:", self.combo_align_v)
        
        # 6. Scope
        self.combo_scope = QtWidgets.QComboBox()
        if has_selected_glyph:
            self.combo_scope.addItem("Selected glyph(s) only", "selected")
        self.combo_scope.addItem("All glyphs", "all")
        self.combo_scope.addItem("Cyrillic glyphs only (U+0400-04FF)", "cyrillic")
        self.combo_scope.addItem("Latin glyphs only (A-Z, a-z)", "latin")
        self.combo_scope.addItem("Custom glyph range...", "custom")
        form.addRow("Scope:", self.combo_scope)
        
        # Range fields (hidden by default unless Custom is selected)
        self.range_widget = QtWidgets.QWidget()
        range_layout = QtWidgets.QHBoxLayout(self.range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(4)
        self.spin_start_glyph = QtWidgets.QSpinBox()
        self.spin_start_glyph.setRange(0, 99999)
        self.spin_end_glyph = QtWidgets.QSpinBox()
        self.spin_end_glyph.setRange(0, 99999)
        range_layout.addWidget(QtWidgets.QLabel("From:"))
        range_layout.addWidget(self.spin_start_glyph)
        range_layout.addWidget(QtWidgets.QLabel("To:"))
        range_layout.addWidget(self.spin_end_glyph)
        self.range_widget.setVisible(False)
        form.addRow("", self.range_widget)
        
        layout.addLayout(form)
        
        # Connect scope change to show/hide range fields
        self.combo_scope.currentIndexChanged.connect(self._on_scope_changed)
        
        # 7. Checkboxes
        self.chk_auto_metrics = QtWidgets.QCheckBox("Auto-detect width and kerning")
        self.chk_auto_metrics.setChecked(_LAST_RENDER_PARAMS["auto_metrics"])
        layout.addWidget(self.chk_auto_metrics)
        
        self.chk_antialiasing = QtWidgets.QCheckBox("Enable Text Antialiasing")
        self.chk_antialiasing.setChecked(_LAST_RENDER_PARAMS["antialiasing"])
        layout.addWidget(self.chk_antialiasing)
        
        # Help label
        help_lbl = QtWidgets.QLabel(
            "Note: Glyphs will be drawn using the selected system font.\n"
            "If auto-detect is enabled, width and kerning will be recalculated."
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

        # Connect slots for real-time visual updates
        self.font_combo.currentFontChanged.connect(self._update_preview)
        self.spin_size.valueChanged.connect(self._update_preview)
        self.chk_bold.stateChanged.connect(self._update_preview)
        self.chk_italic.stateChanged.connect(self._update_preview)
        self.scale_h.valueChanged.connect(self._update_preview)
        self.scale_v.valueChanged.connect(self._update_preview)
        self.spin_x.valueChanged.connect(self._update_preview)
        self.spin_y.valueChanged.connect(self._update_preview)
        self.combo_align_h.currentIndexChanged.connect(self._update_preview)
        self.combo_align_v.currentIndexChanged.connect(self._update_preview)
        self.chk_antialiasing.stateChanged.connect(self._update_preview)

        # Setup and load first preview item
        self._update_preview_item()

    def accept(self):
        # Save last render parameters for session persistence
        params = self.get_params()
        _LAST_RENDER_PARAMS["font_family"] = self.font_combo.currentFont().family()
        _LAST_RENDER_PARAMS["size"] = self.spin_size.value()
        _LAST_RENDER_PARAMS["x_offset"] = self.spin_x.value()
        _LAST_RENDER_PARAMS["y_offset"] = self.spin_y.value()
        _LAST_RENDER_PARAMS["align_h"] = params["align_h"]
        _LAST_RENDER_PARAMS["align_v"] = params["align_v"]
        _LAST_RENDER_PARAMS["auto_metrics"] = self.chk_auto_metrics.isChecked()
        _LAST_RENDER_PARAMS["antialiasing"] = self.chk_antialiasing.isChecked()
        
        # Save new parameters
        _LAST_RENDER_PARAMS["bold"] = self.chk_bold.isChecked()
        _LAST_RENDER_PARAMS["italic"] = self.chk_italic.isChecked()
        _LAST_RENDER_PARAMS["stretch"] = self.scale_h.value()
        _LAST_RENDER_PARAMS["v_scale"] = self.scale_v.value()
        
        super().accept()

    def _on_scope_changed(self):
        scope_type = self.combo_scope.itemData(self.combo_scope.currentIndex())
        self.range_widget.setVisible(scope_type == "custom")

    def _on_preview_info_clicked(self, event):
        if not self.preview_list:
            return
            
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Jump to Glyph",
            f"Enter Glyph Index, Character, or Position (1-{len(self.preview_list)}):"
        )
        if not ok or not text:
            return
            
        search_query = text.strip()
        if not search_query:
            return
            
        found_idx = -1
        
        # 1. Try to parse as position number (1-based index)
        try:
            pos = int(search_query)
            if 1 <= pos <= len(self.preview_list):
                found_idx = pos - 1
        except ValueError:
            pass
            
        # 2. Try to match as glyph index (idx field in preview items)
        if found_idx == -1:
            try:
                g_idx = int(search_query)
                for i, item in enumerate(self.preview_list):
                    if item.get("idx") == g_idx:
                        found_idx = i
                        break
            except ValueError:
                pass
                
        # 3. Try to match as character (exact or case-insensitive)
        if found_idx == -1:
            for i, item in enumerate(self.preview_list):
                if item.get("char") == search_query:
                    found_idx = i
                    break
            if found_idx == -1:
                # Fallback: case-insensitive
                for i, item in enumerate(self.preview_list):
                    if item.get("char", "").lower() == search_query.lower():
                        found_idx = i
                        break
                        
        if found_idx != -1:
            self.preview_index = found_idx
            self._update_preview_item()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Found",
                f"Could not find any glyph matching '{search_query}' as index, character, or position."
            )

    def _on_prev_preview(self):
        if len(self.preview_list) <= 1:
            return
        self.preview_index = (self.preview_index - 1) % len(self.preview_list)
        self._update_preview_item()
        
    def _on_next_preview(self):
        if len(self.preview_list) <= 1:
            return
        self.preview_index = (self.preview_index + 1) % len(self.preview_list)
        self._update_preview_item()

    def _update_preview_item(self):
        if not self.preview_list:
            self.lbl_preview_orig.setText("N/A")
            self.lbl_preview_new.setText("Empty")
            self.lbl_preview_info.setText("")
            return
            
        item = self.preview_list[self.preview_index]
        self.char_str = item["char"]
        self.orig_glyph_img = item["img"]
        
        # Update original glyph view (pixelated scaled view)
        if self.orig_glyph_img:
            orig_pix = QtGui.QPixmap.fromImage(self.orig_glyph_img)
            self.lbl_preview_orig.setPixmap(orig_pix.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation))
        else:
            self.lbl_preview_orig.setText("N/A")
            
        # Update navigation info label
        self.lbl_preview_info.setText(f"Glyph '{self.char_str}' (idx: {item['idx']}) - {self.preview_index + 1} of {len(self.preview_list)}")
        
        # Trigger real-time text rendering preview update
        self._update_preview()

    def _update_preview(self):
        if not self.char_str:
            self.lbl_preview_new.setText("Empty")
            return
            
        params = self.get_params()
        font = params["font"]
        h_scale = params["h_scale"]
        v_scale = params["v_scale"]
        x_offset = params["x_offset"]
        y_offset = params["y_offset"]
        align_h = params["align_h"]
        align_v = params["align_v"]
        antialiasing = params["antialiasing"]
        
        new_glyph = QtGui.QImage(self.cell_w, self.cell_h, QtGui.QImage.Format_ARGB32)
        new_glyph.fill(QtGui.QColor(0, 0, 0, 0))
        
        painter = QtGui.QPainter(new_glyph)
        if antialiasing:
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(255, 255, 255, 255))
        
        ascent_val = self.ascent if self.ascent > 0 else int(self.cell_h * 0.75)
        
        # Apply scaling relative to the cell center
        painter.save()
        cx = self.cell_w / 2.0
        cy = self.cell_h / 2.0
        painter.translate(cx, cy)
        painter.scale(h_scale / 100.0, v_scale / 100.0)
        painter.translate(-cx, -cy)
        
        if align_v == "baseline":
            font_metrics = QtGui.QFontMetrics(font)
            text_width = font_metrics.horizontalAdvance(self.char_str)
            x = x_offset
            if align_h == QtCore.Qt.AlignHCenter:
                x = max(0, (self.cell_w - text_width) // 2) + x_offset
            elif align_h == QtCore.Qt.AlignRight:
                x = self.cell_w - text_width + x_offset
            
            painter.drawText(x, ascent_val + y_offset, self.char_str)
        else:
            alignment = QtCore.Qt.AlignmentFlag(0)
            if align_h is not None:
                alignment |= align_h
            if align_v != "baseline" and align_v is not None:
                alignment |= align_v
            rect = QtCore.QRect(x_offset, y_offset, self.cell_w, self.cell_h)
            painter.drawText(rect, alignment, self.char_str)
            
        painter.restore()
        painter.end()
        
        new_pix = QtGui.QPixmap.fromImage(new_glyph)
        self.lbl_preview_new.setPixmap(new_pix.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation))

    def get_params(self):
        qfont = self.font_combo.currentFont()
        qfont.setPixelSize(self.spin_size.value())
        qfont.setBold(self.chk_bold.isChecked())
        qfont.setItalic(self.chk_italic.isChecked())
        
        idx = self.combo_scope.currentIndex()
        scope_val = self.combo_scope.itemData(idx)
        
        align_h_idx = self.combo_align_h.currentIndex()
        align_h_val = self.combo_align_h.itemData(align_h_idx)
        
        align_v_idx = self.combo_align_v.currentIndex()
        align_v_val = self.combo_align_v.itemData(align_v_idx)
        
        return {
            "font": qfont,
            "h_scale": self.scale_h.value(),
            "v_scale": self.scale_v.value(),
            "x_offset": self.spin_x.value(),
            "y_offset": self.spin_y.value(),
            "align_h": align_h_val,
            "align_v": align_v_val,
            "scope": scope_val,
            "start_glyph": self.spin_start_glyph.value(),
            "end_glyph": self.spin_end_glyph.value(),
            "auto_metrics": self.chk_auto_metrics.isChecked(),
            "antialiasing": self.chk_antialiasing.isChecked()
        }
