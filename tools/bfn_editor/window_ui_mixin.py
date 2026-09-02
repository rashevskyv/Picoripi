from PyQt6 import QtCore, QtGui, QtWidgets

from core.i18n import tr
from tools.bfn_editor.bfn_widgets import ImageView, SimImageView
from tools.bfn_editor.bfn_theme import apply_theme_by_settings


def painted_text_width(fm: QtGui.QFontMetrics, text: str) -> int:
    """Pixel width of ``text`` including negative glyph bearings (first/last clip)."""
    if not text:
        return 0
    width = fm.horizontalAdvance(text)
    left = fm.leftBearing(text[0])
    right = fm.rightBearing(text[-1])
    if left < 0:
        width -= left
    if right < 0:
        width -= right
    return width


def wrap_ui_text(text: str, fm: QtGui.QFontMetrics, max_width: int) -> tuple[str, int]:
    """Split a label into at most two lines so it can fit ``max_width``.

    Returns (display_text, widest_line_px). A single long word is left intact
    and the returned width grows with it — the widget must then widen.
    """
    text = " ".join(str(text or "").split())
    if not text:
        return "", 0
    full = painted_text_width(fm, text)
    if full <= max_width:
        return text, full
    words = text.split(" ")
    if len(words) == 1:
        return text, full
    best_i = 1
    best_w = full
    for i in range(1, len(words)):
        a = " ".join(words[:i])
        b = " ".join(words[i:])
        w = max(painted_text_width(fm, a), painted_text_width(fm, b))
        if w < best_w:
            best_w = w
            best_i = i
    wrapped = " ".join(words[:best_i]) + "\n" + " ".join(words[best_i:])
    return wrapped, best_w


def _shrink_font(widget: QtWidgets.QWidget, steps: int = 1) -> None:
    font = QtGui.QFont(QtWidgets.QApplication.font())
    if font.pointSize() > 0:
        font.setPointSize(max(8, font.pointSize() - steps))
    elif font.pixelSize() > 0:
        font.setPixelSize(max(10, font.pixelSize() - steps))
    widget.setFont(font)


def _fit_button(btn: QtWidgets.QPushButton, text: str, max_width: int) -> int:
    """Put ``text`` on the button, wrapping to two lines if needed. Returns min width."""
    _shrink_font(btn, 1)
    fm = btn.fontMetrics()
    pad = 16
    wrapped, line_w = wrap_ui_text(text, fm, max(40, max_width - pad))
    btn.setText(wrapped)
    lines = wrapped.count("\n") + 1
    btn.setMinimumHeight(fm.height() * lines + 10)
    need = line_w + pad
    btn.setMinimumWidth(need)
    btn.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Minimum,
    )
    return need


class WindowUiMixin:
    def setup_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- Left Panel: Sheets List ---
        left_layout = QtWidgets.QVBoxLayout()

        left_layout.addWidget(QtWidgets.QLabel(tr('Texture Sheets:')))
        self.list_sheets = QtWidgets.QTreeWidget()
        self.list_sheets.setHeaderHidden(True)
        self.list_sheets.currentItemChanged.connect(self.select_sheet_tree)
        left_layout.addWidget(self.list_sheets)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(240)
        main_layout.addWidget(left_widget)

        # --- Central Tabs ---
        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        # Tab 1: Font Editor
        tab_editor = QtWidgets.QWidget()
        editor_layout = QtWidgets.QVBoxLayout(tab_editor)
        editor_layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(QtWidgets.QLabel(tr('Zoom:')))
        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 20.0)
        self.scale_spin.setSingleStep(0.5)
        self.scale_spin.setValue(2.0)
        self.scale_spin.valueChanged.connect(self.on_scale_spin_changed)
        toolbar.addWidget(self.scale_spin)

        self.btn_save = QtWidgets.QPushButton(tr('Save Changes (Ctrl+S)'))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_changes)
        toolbar.addWidget(self.btn_save)

        # Undo/Redo
        self.action_undo = self.undo_stack.createUndoAction(self, tr("Undo"))
        self.action_undo.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        self.action_redo = self.undo_stack.createRedoAction(self, tr("Redo"))
        self.action_redo.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        self.addAction(self.action_undo)
        self.addAction(self.action_redo)

        self.btn_undo = QtWidgets.QPushButton(tr('Undo'))
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.action_undo.trigger)
        self.action_undo.changed.connect(lambda: self.btn_undo.setEnabled(self.action_undo.isEnabled()))
        self.action_undo.changed.connect(lambda: self.btn_undo.setText(self.action_undo.text()))
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = QtWidgets.QPushButton(tr('Redo'))
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.action_redo.trigger)
        self.action_redo.changed.connect(lambda: self.btn_redo.setEnabled(self.action_redo.isEnabled()))
        self.action_redo.changed.connect(lambda: self.btn_redo.setText(self.action_redo.text()))
        toolbar.addWidget(self.btn_redo)

        toolbar.addSpacing(10)

        self.chk_auto_sync = QtWidgets.QCheckBox(tr('Auto-sync'))
        self.chk_auto_sync.setToolTip(tr('Automatically save and recalculate all text widths in Picoripi in real-time'))
        
        auto_sync_val = False
        sm = self.get_settings_manager()
        if sm:
            auto_sync_val = sm.get("bfn_auto_sync_enabled", False)
        self.chk_auto_sync.setChecked(auto_sync_val)
        self.chk_auto_sync.stateChanged.connect(self.on_auto_sync_toggled)
        toolbar.addWidget(self.chk_auto_sync)

        self.btn_sync_recalculate = QtWidgets.QPushButton(tr('Sync & Recalculate'))
        self.btn_sync_recalculate.setToolTip(tr('Force save changes and recalculate all text widths and issues in Picoripi'))
        self.btn_sync_recalculate.clicked.connect(self.force_sync_and_recalculate)
        toolbar.addWidget(self.btn_sync_recalculate)

        toolbar.addStretch()
        editor_layout.addLayout(toolbar)

        # Vertical splitter: glyph grid on top, simulator on bottom
        editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = ImageView()
        self.view.setScene(self.scene)
        self.view.clicked.connect(self.on_view_clicked)
        self.view.scaleChanged.connect(self.on_view_scale_changed)
        editor_splitter.addWidget(self.view)

        sim_container = QtWidgets.QWidget()
        sim_layout = QtWidgets.QVBoxLayout(sim_container)
        sim_layout.setContentsMargins(0, 6, 0, 0)
        sim_layout.setSpacing(4)

        sim_header_layout = QtWidgets.QHBoxLayout()
        sim_header_layout.addWidget(QtWidgets.QLabel(tr('Enter text to simulate rendering (with kerning & width):')))
        
        self.chk_sync_sim_text = QtWidgets.QCheckBox(tr('Sync with editor'))
        self.chk_sync_sim_text.setChecked(True)
        self.chk_sync_sim_text.setToolTip(tr("Automatically synchronize with the selected string in the main translation editor"))
        sim_header_layout.addWidget(self.chk_sync_sim_text)
        sim_header_layout.addStretch(1)
        sim_layout.addLayout(sim_header_layout)

        self.sim_input = QtWidgets.QPlainTextEdit()
        self.sim_input.setPlaceholderText(
            tr('Type anything here to test in real-time... Right-click for pangrams/placeholder text.')
        )
        self.sim_input.setMaximumHeight(65)
        self.sim_input.textChanged.connect(self.on_sim_text_changed)
        self.sim_input.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.sim_input.customContextMenuRequested.connect(self.show_sim_input_context_menu)
        sim_layout.addWidget(self.sim_input)

        self.sim_scene = QtWidgets.QGraphicsScene(self)
        self.sim_view = SimImageView()
        self.sim_view.setScene(self.sim_scene)
        self.sim_view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        self.sim_view.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, False)
        sim_layout.addWidget(self.sim_view, 1)

        editor_splitter.addWidget(sim_container)
        editor_splitter.setSizes([450, 250])
        editor_layout.addWidget(editor_splitter)

        self.tabs.addTab(tab_editor, tr("Font Editor"))

        # Tab 2: Glyph Table
        tab_table = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(tab_table)
        table_layout.setContentsMargins(8, 8, 8, 8)

        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel(tr('Search Glyph/Character:')))
        self.table_search = QtWidgets.QLineEdit()
        self.table_search.setPlaceholderText(tr('Type character, index or sheet index to filter...'))
        self.table_search.setProperty('selectAllOnClick', True)
        self._glyph_search_timer = QtCore.QTimer(self)
        self._glyph_search_timer.setSingleShot(True)
        self._glyph_search_timer.setInterval(120)
        self._glyph_search_timer.timeout.connect(self.populate_glyph_table)
        self.table_search.textChanged.connect(self._glyph_search_timer.start)
        search_layout.addWidget(self.table_search)
        table_layout.addLayout(search_layout)

        self.table_glyphs = QtWidgets.QTableWidget()
        headers = [
            tr('Original Render'), tr('Original Char'),
            tr('Glyph Render'), tr('Character'), tr('Font Char'),
            tr('Texture Sheet'), tr('Tile Position'), tr('Kerning'), tr('Width')
        ]
        self.table_glyphs.setColumnCount(len(headers))
        self.table_glyphs.setHorizontalHeaderLabels(headers)
        self.table_glyphs.setIconSize(QtCore.QSize(28, 28))
        vheader = self.table_glyphs.verticalHeader()
        vheader.setDefaultSectionSize(36)
        vheader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        header = self.table_glyphs.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setDefaultAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        header.installEventFilter(self)
        self._fit_glyph_table_headers()
        
        # Connect double-click on header boundary to auto-resize column to fit contents
        header.sectionHandleDoubleClicked.connect(self.on_header_handle_double_clicked)
        
        self.table_glyphs.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        self.table_glyphs.itemChanged.connect(self.on_table_item_changed)
        self.table_glyphs.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_glyphs.customContextMenuRequested.connect(self.show_table_context_menu)
        table_layout.addWidget(self.table_glyphs)

        # Rapid keyboard navigation in table
        original_table_keyPress = self.table_glyphs.keyPressEvent

        def table_keyPressEvent(event):
            key = event.key()
            if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                if key == QtCore.Qt.Key.Key_C:
                    self.copy_glyph_values()
                    event.accept()
                    return
                elif key == QtCore.Qt.Key.Key_V:
                    self.paste_glyph_values()
                    event.accept()
                    return

            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                original_table_keyPress(event)

                def move_down():
                    current = self.table_glyphs.currentIndex()
                    if current.isValid():
                        next_row = current.row() + 1
                        if next_row < self.table_glyphs.rowCount():
                            self.table_glyphs.setCurrentCell(next_row, current.column())
                            self.table_glyphs.edit(self.table_glyphs.currentIndex())

                QtCore.QTimer.singleShot(10, move_down)
                event.accept()
                return

            if event.text() and not event.modifiers():
                if key not in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab,
                               QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter,
                               QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace):
                    current = self.table_glyphs.currentIndex()
                    if current.isValid() and current.column() in (3, 7, 8):
                        self.table_glyphs.edit(current)
            original_table_keyPress(event)

        self.table_glyphs.keyPressEvent = table_keyPressEvent

        self.tabs.addTab(tab_table, tr("Glyph Table"))

        # --- Right Panel: Glyph Info & Editing ---
        right_layout = QtWidgets.QVBoxLayout()
        info_title = QtWidgets.QLabel(tr('Glyph Information:'))
        info_title.setWordWrap(True)
        right_layout.addWidget(info_title)

        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        right_layout.addWidget(self.info_text)

        form_layout = QtWidgets.QGridLayout()
        kern_lbl = QtWidgets.QLabel(tr('Kerning (Left Shift):'))
        kern_lbl.setWordWrap(True)
        form_layout.addWidget(kern_lbl, 0, 0)
        self.spin_kerning = QtWidgets.QSpinBox()
        self.spin_kerning.setRange(-128, 127)
        self.spin_kerning.setEnabled(False)
        self.spin_kerning.valueChanged.connect(self.on_params_changed)
        form_layout.addWidget(self.spin_kerning, 0, 1)

        width_lbl = QtWidgets.QLabel(tr('Width (Char Space):'))
        width_lbl.setWordWrap(True)
        form_layout.addWidget(width_lbl, 1, 0)
        self.spin_width = QtWidgets.QSpinBox()
        self.spin_width.setRange(0, 255)
        self.spin_width.setEnabled(False)
        self.spin_width.valueChanged.connect(self.on_params_changed)
        form_layout.addWidget(self.spin_width, 1, 1)

        right_layout.addLayout(form_layout)

        self.btn_auto_width = QtWidgets.QPushButton(tr('Auto-detect Width'))
        self.btn_auto_width.setEnabled(False)
        self.btn_auto_width.clicked.connect(self.auto_detect_width)
        right_layout.addWidget(self.btn_auto_width)

        right_layout.addSpacing(15)
        tex_title = QtWidgets.QLabel(tr('Texture Actions:'))
        tex_title.setWordWrap(True)
        right_layout.addWidget(tex_title)

        self.btn_export_sheet = QtWidgets.QPushButton()
        self.btn_export_sheet.setEnabled(False)
        self.btn_export_sheet.clicked.connect(self.export_sheet_png)

        self.btn_import_sheet = QtWidgets.QPushButton()
        self.btn_import_sheet.setEnabled(False)
        self.btn_import_sheet.clicked.connect(self.import_sheet_png)

        self.btn_export_glyph = QtWidgets.QPushButton()
        self.btn_export_glyph.setEnabled(False)
        self.btn_export_glyph.clicked.connect(self.export_glyph_png)

        self.btn_import_glyph = QtWidgets.QPushButton()
        self.btn_import_glyph.setEnabled(False)
        self.btn_import_glyph.clicked.connect(self.import_glyph_png)

        self.btn_render_font = QtWidgets.QPushButton()
        self.btn_render_font.setEnabled(False)
        self.btn_render_font.clicked.connect(self.render_system_font_to_glyphs)

        actions = QtWidgets.QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(6)
        actions.addWidget(self.btn_export_sheet, 0, 0)
        actions.addWidget(self.btn_import_sheet, 0, 1)
        actions.addWidget(self.btn_export_glyph, 1, 0)
        actions.addWidget(self.btn_import_glyph, 1, 1)
        actions.addWidget(self.btn_render_font, 2, 0, 1, 2)
        right_layout.addLayout(actions)

        right_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        self._right_panel = right_widget
        self._fit_texture_action_buttons()
        main_layout.addWidget(right_widget)

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage(tr('Ready. Open a BFN file or extracted folder.'))

        # Shortcuts
        self.setup_shortcuts()

        # Scene overlays
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.grid_item = None

        self.sel_rect_item = QtWidgets.QGraphicsRectItem()
        pen_sel = QtGui.QPen(QtGui.QColor('#00b4d8'))
        pen_sel.setWidth(2)
        pen_sel.setCosmetic(True)
        self.sel_rect_item.setPen(pen_sel)
        self.sel_rect_item.setVisible(False)
        self.scene.addItem(self.sel_rect_item)

        self.kerning_line_item = QtWidgets.QGraphicsLineItem()
        pen_k = QtGui.QPen(QtGui.QColor('#3a86c8'))
        pen_k.setWidth(2)
        pen_k.setCosmetic(True)
        self.kerning_line_item.setPen(pen_k)
        self.kerning_line_item.setVisible(False)
        self.scene.addItem(self.kerning_line_item)

        self.width_line_item = QtWidgets.QGraphicsLineItem()
        pen_w = QtGui.QPen(QtGui.QColor('#e63946'))
        pen_w.setWidth(2)
        pen_w.setCosmetic(True)
        self.width_line_item.setPen(pen_w)
        self.width_line_item.setVisible(False)
        self.scene.addItem(self.width_line_item)

        self.view.set_scale(2.0)

    def apply_theme(self):
        self.is_dark_theme = apply_theme_by_settings(self)
        self._fit_texture_action_buttons()
        self._fit_glyph_table_headers()

    def apply_dark_theme(self):
        self.apply_theme()

    def setup_shortcuts(self):
        self.sc_save = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.sc_save.activated.connect(self.save_changes)

        self.sc_left = QtGui.QShortcut(QtGui.QKeySequence("Left"), self)
        self.sc_left.activated.connect(lambda: self.navigate_grid(-1, 0))
        self.sc_right = QtGui.QShortcut(QtGui.QKeySequence("Right"), self)
        self.sc_right.activated.connect(lambda: self.navigate_grid(1, 0))
        self.sc_up = QtGui.QShortcut(QtGui.QKeySequence("Up"), self)
        self.sc_up.activated.connect(lambda: self.navigate_grid(0, -1))
        self.sc_down = QtGui.QShortcut(QtGui.QKeySequence("Down"), self)
        self.sc_down.activated.connect(lambda: self.navigate_grid(0, 1))

        self.sc_close = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self)
        self.sc_close.activated.connect(self.on_esc_pressed)

    def on_esc_pressed(self):
        focus_w = self.focusWidget()
        if hasattr(self, 'table_glyphs') and self.table_glyphs:
            if self.table_glyphs.state() == QtWidgets.QAbstractItemView.State.EditingState:
                if focus_w:
                    self.sc_close.setEnabled(False)
                    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape, QtCore.Qt.KeyboardModifier.NoModifier)
                    QtWidgets.QApplication.sendEvent(focus_w, event)
                    self.sc_close.setEnabled(True)
                return
        self.close()

    def eventFilter(self, source, event):
        if (hasattr(self, 'table_glyphs') and self.table_glyphs and
            source == self.table_glyphs.horizontalHeader() and
            event.type() == QtCore.QEvent.Type.MouseButtonDblClick):
            
            pos = event.pos()
            x = pos.x()
            header = self.table_glyphs.horizontalHeader()
            count = header.count()
            
            for i in range(count):
                if header.isSectionHidden(i):
                    continue
                section_start = header.sectionViewportPosition(i)
                section_end = section_start + header.sectionSize(i)
                
                # Check if double click was on the resize boundary (within 5 pixels)
                if abs(x - section_end) <= 5:
                    self.on_header_handle_double_clicked(i)
                    event.accept()
                    return True
        return super().eventFilter(source, event)

    def _fit_texture_action_buttons(self) -> None:
        """Two-column action buttons; wrap labels so every language stays readable."""
        pair = [
            (self.btn_export_sheet, tr('Export Current Sheet PNG...')),
            (self.btn_import_sheet, tr('Import Current Sheet PNG...')),
            (self.btn_export_glyph, tr('Export Selected Glyph PNG...')),
            (self.btn_import_glyph, tr('Import Selected Glyph PNG...')),
        ]
        half = 160
        pair_w = 0
        for btn, label in pair:
            pair_w = max(pair_w, _fit_button(btn, label, half))
        for btn, _label in pair:
            btn.setMinimumWidth(pair_w)
        full = _fit_button(
            self.btn_render_font, tr('Render System Font to Glyphs...'), pair_w * 2 + 6
        )
        auto_w = _fit_button(self.btn_auto_width, tr('Auto-detect Width'), pair_w * 2 + 6)
        panel = getattr(self, '_right_panel', None)
        margins = 12
        if panel is not None and panel.layout() is not None:
            m = panel.layout().contentsMargins()
            margins = m.left() + m.right()
        panel_w = max(pair_w * 2 + 6 + margins, full + margins, auto_w + margins)
        if panel is not None:
            panel.setMinimumWidth(panel_w)
            panel.setMaximumWidth(max(panel_w, 480))

    def _header_caption_width(self, header, text: str) -> int:
        fm = header.fontMetrics()
        line_w = 0
        for part in str(text).split("\n"):
            line_w = max(line_w, painted_text_width(fm, part))
        # Stylesheet padding is 6px each side plus the section border.
        return line_w + 16

    def _fit_glyph_table_headers(self) -> None:
        """Wrap header captions to two lines and keep columns at least that wide."""
        table = getattr(self, 'table_glyphs', None)
        if table is None:
            return
        header = table.horizontalHeader()
        _shrink_font(header, 1)
        fm = header.fontMetrics()
        header_h = fm.height() + 8
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            if item is None:
                continue
            raw = " ".join(item.text().replace("\n", " ").split())
            wrapped, _line_w = wrap_ui_text(raw, fm, 100)
            item.setText(wrapped)
            item.setToolTip(raw)
            need = self._header_caption_width(header, wrapped)
            if table.columnWidth(col) < need:
                table.setColumnWidth(col, need)
            header_h = max(header_h, (wrapped.count("\n") + 1) * fm.height() + 10)
        header.setMinimumHeight(header_h)

    def on_header_handle_double_clicked(self, logical_index):
        # Fit the column to the wider of cell contents and the (possibly wrapped) header.
        col = logical_index
        
        # Start with a minimum base width for cell margins
        max_w = 35
        item = self.table_glyphs.horizontalHeaderItem(col)
        if item and item.text():
            max_w = max(
                max_w,
                self._header_caption_width(self.table_glyphs.horizontalHeader(), item.text()),
            )
        
        # Iterate over all rows to find the max width of cell contents
        row_count = self.table_glyphs.rowCount()
        table_font = self.table_glyphs.font()
        
        for row in range(row_count):
            item = self.table_glyphs.item(row, col)
            if item is None:
                continue
            if not item.icon().isNull():
                max_w = max(max_w, 28 + 16)
            if item.text():
                item_font = item.font() if item.font().family() else table_font
                item_fm = QtGui.QFontMetrics(item_font)
                max_w = max(max_w, item_fm.horizontalAdvance(item.text()) + 24)
                    
        # Apply limits (between 35 and 600)
        max_w = max(35, min(max_w, 600))
        
        # Set the column width
        self.table_glyphs.setColumnWidth(col, max_w)
