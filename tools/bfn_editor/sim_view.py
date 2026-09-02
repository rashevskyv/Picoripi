from PyQt6 import QtCore, QtGui, QtWidgets

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

    def _wid_entry(self):
        """Return (kerning, width) for this glyph from WID1."""
        kerning = 0
        width = self.viewer.cell_w
        wid = self.viewer.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = self.glyph_idx - self.viewer.first_code
        if 0 <= wid_idx < len(packets):
            kerning = packets[wid_idx]["kerning"]
            width = packets[wid_idx]["width"]
        return kerning, width

    def boundingRect(self) -> QtCore.QRectF:
        # The whole font cell is drawn (game-accurate), so cover all of it
        return QtCore.QRectF(-2, -2, self.viewer.cell_w + 4, self.viewer.cell_h + 4)

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        if self.sheet_idx < 0 or self.sheet_idx >= len(self.viewer.sheet_images):
            return

        sheet_img = self.viewer.sheet_images[self.sheet_idx]

        # Draw the full font cell. The layout already shifted this item's
        # position left by kerning (JUTResFont::drawChar_scale semantics),
        # so the inked part of the glyph lands exactly on the text cursor.
        glyph_crop = sheet_img.copy(self.cell_x, self.cell_y,
                                    self.viewer.cell_w, self.viewer.cell_h)
        painter.drawImage(0, 0, glyph_crop)

        if getattr(self.viewer, 'selected_sim_item', None) == self:
            kerning, width = self._wid_entry()
            pen_border = QtGui.QPen(QtGui.QColor('#00b4d8'))
            pen_border.setWidth(1)
            pen_border.setStyle(QtCore.Qt.PenStyle.DashLine)
            pen_border.setCosmetic(True)
            painter.setPen(pen_border)
            # The advance region starts kerning px into the cell
            painter.drawRect(kerning, 0, width, self.viewer.cell_h)

            left_x = kerning
            pen_k = QtGui.QPen(QtGui.QColor('#3a86c8'))
            pen_k.setWidth(1)
            pen_k.setCosmetic(True)
            painter.setPen(pen_k)
            painter.drawLine(left_x, 0, left_x, self.viewer.cell_h)

            right_x = kerning + width
            pen_w = QtGui.QPen(QtGui.QColor('#e63946'))
            pen_w.setWidth(1)
            pen_w.setCosmetic(True)
            painter.setPen(pen_w)
            painter.drawLine(right_x, 0, right_x, self.viewer.cell_h)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.viewer.select_sim_glyph(self)
            
            p = event.pos()
            kerning, width = self._wid_entry()

            # Advance region in item coordinates: [kerning, kerning + width]
            left_x = kerning
            right_x = kerning + width
            
            scale = self.viewer.sim_view._scale
            tolerance = max(2.0, 8.0 / scale)
            
            if abs(p.x() - left_x) <= tolerance:
                self._dragging_handle = 'kerning'
                self._drag_start_scene_x = event.scenePos().x()
                self._drag_start_kern = kerning
                self._drag_start_width = width
                self.viewer._dragging_in_sim = True
                self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
                event.accept()
                return
            elif abs(p.x() - right_x) <= tolerance:
                self._dragging_handle = 'width'
                self._drag_start_scene_x = event.scenePos().x()
                self._drag_start_kern = kerning
                self._drag_start_width = width
                self.viewer._dragging_in_sim = True
                self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
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
                    max_kern = min(127, self._drag_start_kern + self._drag_start_width)
                    min_kern = max(-128, self._drag_start_kern + self._drag_start_width - 255)
                    new_kern = max(min_kern, min(max_kern, new_kern))
                    
                    self.viewer.spin_kerning.blockSignals(True)
                    self.viewer.spin_kerning.setValue(new_kern)
                    self.viewer.spin_kerning.blockSignals(False)
                    
                    packets[wid_idx]["kerning"] = new_kern
                    
                    new_width = self._drag_start_kern + self._drag_start_width - new_kern
                    self.viewer.spin_width.blockSignals(True)
                    self.viewer.spin_width.setValue(new_width)
                    self.viewer.spin_width.blockSignals(False)
                    packets[wid_idx]["width"] = new_width
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
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
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
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.black))
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
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
            
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
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
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
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
        
        pos = event.position().toPoint()
        old_scene_pos = self.mapToScene(pos)
        
        new_scale = self._scale * factor
        new_scale = max(self._scale_min, min(self._scale_max, new_scale))
        
        self.set_scale(new_scale)
        
        new_scene_pos = self.mapToScene(pos)
        d = new_scene_pos - old_scene_pos
        self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x() * new_scale))
        self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y() * new_scale))
        
        event.accept()

