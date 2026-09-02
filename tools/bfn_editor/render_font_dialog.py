from PyQt6 import QtCore, QtGui, QtWidgets
from core.i18n import tr
from tools.bfn_editor.scale_slider import ScaleSliderWidget

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


class RenderFontDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cell_w=24, cell_h=24, has_selected_glyph=False, preview_list=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Render System Font to Glyphs"))
        self.setModal(True)
        self.resize(400, 560)
        
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.preview_list = preview_list if preview_list else []
        self.preview_index = 0
        self.char_str = ""
        self.orig_glyph_img = None
        self._font_combo_just_focused = False
        
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
        lbl_orig_title = QtWidgets.QLabel(tr("Original Glyph:"))
        lbl_orig_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_orig_title.setStyleSheet("font-weight: bold; color: #88888b; font-size: 11px;")
        orig_box.addWidget(lbl_orig_title)
        
        self.lbl_preview_orig = QtWidgets.QLabel()
        self.lbl_preview_orig.setFixedSize(128, 128)
        self.lbl_preview_orig.setStyleSheet("border: 1px solid #3d405b; background-color: #141419; border-radius: 4px;")
        self.lbl_preview_orig.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        orig_box.addWidget(self.lbl_preview_orig)
        preview_layout.addLayout(orig_box)
        
        # Arrow
        arrow_lbl = QtWidgets.QLabel("➔")
        arrow_lbl.setStyleSheet("font-size: 24px; color: #00b4d8;")
        preview_layout.addWidget(arrow_lbl, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Rendered
        new_box = QtWidgets.QVBoxLayout()
        lbl_new_title = QtWidgets.QLabel(tr("Rendered Font:"))
        lbl_new_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_new_title.setStyleSheet("font-weight: bold; color: #00b4d8; font-size: 11px;")
        new_box.addWidget(lbl_new_title)
        
        self.lbl_preview_new = QtWidgets.QLabel()
        self.lbl_preview_new.setFixedSize(128, 128)
        self.lbl_preview_new.setStyleSheet("border: 1px solid #3d405b; background-color: #141419; border-radius: 4px;")
        self.lbl_preview_new.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        new_box.addWidget(self.lbl_preview_new)
        preview_layout.addLayout(new_box)
        
        layout.addLayout(preview_layout)
        
        # --- Preview Navigation Bar ---
        self.nav_layout = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀")
        self.btn_prev.setFixedSize(30, 24)
        self.btn_prev.clicked.connect(self._on_prev_preview)
        
        self.lbl_preview_info = QtWidgets.QLabel(tr("Glyph {0} of {1}", 1, 1))
        self.lbl_preview_info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_info.setStyleSheet("font-weight: bold; color: #00b4d8; font-size: 11px; text-decoration: underline;")
        self.lbl_preview_info.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.lbl_preview_info.setToolTip(tr("Click to jump to a specific glyph index, character, or position (e.g., 24)"))
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
        
        # 1. Font Family (Editable with real-time filtering and focus events)
        self.font_combo = QtWidgets.QFontComboBox()
        self.font_combo.setEditable(True)
        self.font_combo.setCompleter(None) # Disable default auto-completion which interferes with filtering
        
        if _LAST_RENDER_PARAMS["font_family"] is not None:
            self.font_combo.setCurrentFont(QtGui.QFont(_LAST_RENDER_PARAMS["font_family"]))
        form.addRow(tr("Font Family:"), self.font_combo)
        
        # Install event filter to select all text when lineEdit gets focus
        self.font_combo.installEventFilter(self)
        if self.font_combo.lineEdit():
            self.font_combo.lineEdit().installEventFilter(self)
            self.font_combo.lineEdit().textEdited.connect(self._on_font_text_edited)
        if self.font_combo.view():
            self.font_combo.view().installEventFilter(self)
            
        self.font_combo.activated.connect(self._on_font_activated)
        
        
        # 2. Font Size
        self.spin_size = QtWidgets.QSpinBox()
        self.spin_size.setRange(6, 120)
        if _LAST_RENDER_PARAMS["size"] is not None:
            self.spin_size.setValue(_LAST_RENDER_PARAMS["size"])
        else:
            default_size = self.ascent if self.ascent > 0 else max(6, cell_h - 4)
            self.spin_size.setValue(default_size)
        form.addRow(tr("Font Size (px):"), self.spin_size)
        
        # Font Style (Bold & Italic)
        self.style_layout = QtWidgets.QHBoxLayout()
        self.chk_bold = QtWidgets.QCheckBox(tr("Bold"))
        self.chk_bold.setChecked(_LAST_RENDER_PARAMS.get("bold", False))
        self.chk_italic = QtWidgets.QCheckBox(tr("Italic"))
        self.chk_italic.setChecked(_LAST_RENDER_PARAMS.get("italic", False))
        self.style_layout.addWidget(self.chk_bold)
        self.style_layout.addWidget(self.chk_italic)
        self.style_layout.addStretch()
        form.addRow(tr("Font Style:"), self.style_layout)
        
        # Horizontal Scale
        self.scale_h = ScaleSliderWidget(
            default_val=_LAST_RENDER_PARAMS.get("stretch", 100),
            min_val=-200,
            max_val=400
        )
        form.addRow(tr("Horizontal Scale:"), self.scale_h)
        
        # Vertical Scale
        self.scale_v = ScaleSliderWidget(
            default_val=_LAST_RENDER_PARAMS.get("v_scale", 100),
            min_val=-200,
            max_val=400
        )
        form.addRow(tr("Vertical Scale:"), self.scale_v)
        
        # 3. Offsets X & Y
        self.spin_x = QtWidgets.QSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.setValue(_LAST_RENDER_PARAMS["x_offset"])
        form.addRow(tr("X Offset:"), self.spin_x)
        
        self.spin_y = QtWidgets.QSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.setValue(_LAST_RENDER_PARAMS["y_offset"])
        form.addRow(tr("Y Offset:"), self.spin_y)
        
        # 4. Horizontal Alignment
        self.combo_align_h = QtWidgets.QComboBox()
        self.combo_align_h.addItem(tr("Center"), QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.combo_align_h.addItem(tr("Left"), QtCore.Qt.AlignmentFlag.AlignLeft)
        self.combo_align_h.addItem(tr("Right"), QtCore.Qt.AlignmentFlag.AlignRight)
        if _LAST_RENDER_PARAMS["align_h"] is not None:
            idx = self.combo_align_h.findData(_LAST_RENDER_PARAMS["align_h"])
            if idx >= 0:
                self.combo_align_h.setCurrentIndex(idx)
        form.addRow(tr("Horizontal Alignment:"), self.combo_align_h)
        
        # 5. Vertical Alignment
        self.combo_align_v = QtWidgets.QComboBox()
        self.combo_align_v.addItem(tr("Center"), QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.combo_align_v.addItem(tr("Top"), QtCore.Qt.AlignmentFlag.AlignTop)
        self.combo_align_v.addItem(tr("Bottom"), QtCore.Qt.AlignmentFlag.AlignBottom)
        self.combo_align_v.addItem(tr("Baseline"), "baseline")
        if _LAST_RENDER_PARAMS["align_v"] is not None:
            idx = self.combo_align_v.findData(_LAST_RENDER_PARAMS["align_v"])
            if idx >= 0:
                self.combo_align_v.setCurrentIndex(idx)
        else:
            self.combo_align_v.setCurrentIndex(3)
        form.addRow(tr("Vertical Alignment:"), self.combo_align_v)
        
        # 6. Scope
        self.combo_scope = QtWidgets.QComboBox()
        if has_selected_glyph:
            self.combo_scope.addItem(tr("Selected glyph(s) only"), "selected")
        self.combo_scope.addItem(tr("All glyphs"), "all")
        self.combo_scope.addItem(tr("Cyrillic glyphs only (U+0400-04FF)"), "cyrillic")
        self.combo_scope.addItem(tr("Latin glyphs only (A-Z, a-z)"), "latin")
        self.combo_scope.addItem(tr("Custom glyph range..."), "custom")
        form.addRow(tr("Scope:"), self.combo_scope)
        
        # Range fields (hidden by default unless Custom is selected)
        self.range_widget = QtWidgets.QWidget()
        range_layout = QtWidgets.QHBoxLayout(self.range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(4)
        self.spin_start_glyph = QtWidgets.QSpinBox()
        self.spin_start_glyph.setRange(0, 99999)
        self.spin_end_glyph = QtWidgets.QSpinBox()
        self.spin_end_glyph.setRange(0, 99999)
        range_layout.addWidget(QtWidgets.QLabel(tr("From:")))
        range_layout.addWidget(self.spin_start_glyph)
        range_layout.addWidget(QtWidgets.QLabel(tr("To:")))
        range_layout.addWidget(self.spin_end_glyph)
        self.range_widget.setVisible(False)
        form.addRow("", self.range_widget)
        
        layout.addLayout(form)
        
        # Connect scope change to show/hide range fields
        self.combo_scope.currentIndexChanged.connect(self._on_scope_changed)
        
        # 7. Checkboxes
        self.chk_auto_metrics = QtWidgets.QCheckBox(tr("Auto-detect width and kerning"))
        self.chk_auto_metrics.setChecked(_LAST_RENDER_PARAMS["auto_metrics"])
        layout.addWidget(self.chk_auto_metrics)
        
        self.chk_antialiasing = QtWidgets.QCheckBox(tr("Enable Text Antialiasing"))
        self.chk_antialiasing.setChecked(_LAST_RENDER_PARAMS["antialiasing"])
        layout.addWidget(self.chk_antialiasing)
        
        # Help label
        help_lbl = QtWidgets.QLabel(
            tr(
                "Note: Glyphs will be drawn using the selected system font.\n"
                "If auto-detect is enabled, width and kerning will be recalculated."
            )
        )
        help_lbl.setStyleSheet("color: #88888b; font-size: 11px;")
        layout.addWidget(help_lbl)
        
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
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
            tr("Jump to Glyph"),
            tr("Enter Glyph Index, Character, or Position (1-{0}):", len(self.preview_list)),
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
                tr("Not Found"),
                tr("Could not find any glyph matching '{0}' as index, character, or position.", search_query),
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
            self.lbl_preview_orig.setText(tr("N/A"))
            self.lbl_preview_new.setText(tr("Empty"))
            self.lbl_preview_info.setText("")
            return
            
        item = self.preview_list[self.preview_index]
        self.char_str = item["char"]
        self.orig_glyph_img = item["img"]
        
        # Update original glyph view (pixelated scaled view)
        if self.orig_glyph_img:
            orig_pix = QtGui.QPixmap.fromImage(self.orig_glyph_img)
            self.lbl_preview_orig.setPixmap(orig_pix.scaled(128, 128, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.FastTransformation))
        else:
            self.lbl_preview_orig.setText(tr("N/A"))
            
        # Update navigation info label
        self.lbl_preview_info.setText(
            tr("Glyph '{0}' (idx: {1}) - {2} of {3}", self.char_str, item['idx'], self.preview_index + 1, len(self.preview_list))
        )
        
        # Trigger real-time text rendering preview update
        self._update_preview()

    def _update_preview(self):
        if not self.char_str:
            self.lbl_preview_new.setText(tr("Empty"))
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
        
        new_glyph = QtGui.QImage(self.cell_w, self.cell_h, QtGui.QImage.Format.Format_ARGB32)
        new_glyph.fill(QtGui.QColor(0, 0, 0, 0))
        
        painter = QtGui.QPainter(new_glyph)
        try:
            if antialiasing:
                painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
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
                if align_h == QtCore.Qt.AlignmentFlag.AlignHCenter:
                    x = max(0, (self.cell_w - text_width) // 2) + x_offset
                elif align_h == QtCore.Qt.AlignmentFlag.AlignRight:
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
        finally:
            painter.end()
        
        new_pix = QtGui.QPixmap.fromImage(new_glyph)
        self.lbl_preview_new.setPixmap(new_pix.scaled(128, 128, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.FastTransformation))

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

    def eventFilter(self, obj, event):
        if obj in (self.font_combo, self.font_combo.lineEdit()):
            if event.type() in (
                QtCore.QEvent.Type.FocusIn,
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QEvent.Type.MouseButtonDblClick
            ):
                line_edit = self.font_combo.lineEdit()
                if line_edit:
                    QtCore.QTimer.singleShot(50, line_edit.selectAll)
                    
        elif obj == self.font_combo.view():
            if event.type() == QtCore.QEvent.Type.KeyPress:
                key = event.key()
                # Allow standard list navigation keys to work on the popup view
                if key in (
                    QtCore.Qt.Key.Key_Up,
                    QtCore.Qt.Key.Key_Down,
                    QtCore.Qt.Key.Key_Enter,
                    QtCore.Qt.Key.Key_Return,
                    QtCore.Qt.Key.Key_Escape,
                    QtCore.Qt.Key.Key_PageUp,
                    QtCore.Qt.Key.Key_PageDown
                ):
                    return super().eventFilter(obj, event)
                    
                # Proxy all other typing and editing events back to lineEdit
                line_edit = self.font_combo.lineEdit()
                if line_edit:
                    QtCore.QCoreApplication.sendEvent(line_edit, event)
                    return True # Consume event so view doesn't handle it
                    
        return super().eventFilter(obj, event)

    def _on_font_text_edited(self, text):
        filter_text = text.lower().strip()
        view = self.font_combo.view()
        model = self.font_combo.model()
        total = model.rowCount()
        
        if not filter_text:
            self._reset_font_filter()
            return
            
        words = filter_text.split()
        
        # Hide matching rows in view
        for i in range(total):
            name = model.index(i, 0).data() or ""
            name_lower = name.lower()
            if all(w in name_lower for w in words):
                view.setRowHidden(i, False)
            else:
                view.setRowHidden(i, True)
                
        # Automatically show drop-down popup when typing
        if not view.isVisible():
            self.font_combo.showPopup()

    def _on_font_activated(self, index):
        self._reset_font_filter()

    def _reset_font_filter(self):
        view = self.font_combo.view()
        model = self.font_combo.model()
        total = model.rowCount()
        for i in range(total):
            view.setRowHidden(i, False)

