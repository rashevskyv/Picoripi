from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr

class ImageView(QtWidgets.QGraphicsView):
    clicked = QtCore.pyqtSignal(QtCore.QPointF)
    scaleChanged = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)  # Needed to change cursor on hover
        self.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.black))
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
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
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
                            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
                            event.accept()
                            return
                        elif abs(scene_pos.x() - right_x) <= tolerance:
                            self._dragging_handle = 'width'
                            self._drag_start_scene_x = scene_pos.x()
                            self._drag_start_kern = kerning
                            self._drag_start_width = width
                            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
                            event.accept()
                            return
            
            self._dragging_handle = None
            self._drag_start_scene_x = None
            self.clicked.emit(scene_pos)
            event.accept()
            return
            
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
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
                        max_kern = min(127, self._drag_start_kern + self._drag_start_width)
                        min_kern = max(-128, self._drag_start_kern + self._drag_start_width - 255)
                        new_kern = max(min_kern, min(max_kern, new_kern))
                        
                        v.spin_kerning.blockSignals(True)
                        v.spin_kerning.setValue(new_kern)
                        v.spin_kerning.blockSignals(False)
                        
                        packets[wid_idx]["kerning"] = new_kern
                        
                        new_width = self._drag_start_kern + self._drag_start_width - new_kern
                        v.spin_width.blockSignals(True)
                        v.spin_width.setValue(new_width)
                        v.spin_width.blockSignals(False)
                        packets[wid_idx]["width"] = new_width
                        
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
                        self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
                        super().mouseMoveEvent(event)
                        return
                    
        self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._dragging_handle is not None:
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
            
        action_render = menu.addAction(tr("Render Font to Selected Glyph..."))
        action_import = menu.addAction(tr("Import Selected Glyph PNG..."))
        action_export = menu.addAction(tr("Export Selected Glyph PNG..."))
        
        action = menu.exec(event.globalPos())
        if action == action_render:
            v.render_system_font_to_glyphs()
        elif action == action_import:
            v.import_glyph_png()
        elif action == action_export:
            v.export_glyph_png()

