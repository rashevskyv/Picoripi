#!/usr/bin/env python3
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_widgets import ImageView, SimImageView
from tools.bfn_editor.bfn_theme import apply_theme_by_settings
from tools.bfn_editor.bfn_io import BfnIoMixin
from tools.bfn_editor.bfn_simulation import BfnSimMixin
from tools.bfn_editor.bfn_navigation import BfnNavigationMixin
from tools.bfn_editor.bfn_view import BfnViewMixin

VERSION = "1.0.21"

ROLE_SHEET_IDX = QtCore.Qt.UserRole + 1
ROLE_FONT_NAME = QtCore.Qt.UserRole + 2
ROLE_ARCHIVE_NAME = QtCore.Qt.UserRole + 3
ROLE_SOURCE_TYPE = QtCore.Qt.UserRole + 4
ROLE_DISK_PATH = QtCore.Qt.UserRole + 5


class BfnEditorWindow(QtWidgets.QMainWindow, BfnIoMixin, BfnSimMixin, BfnNavigationMixin, BfnViewMixin):
    """
    BFN Font Editor Window — embedded into Picoripi as a standalone tool window.

    Integration points:
      - open_from_bytes(bfn_bytes, bfn_name, save_callback, font_sync_callback):
            Opens a BFN file from RAM (e.g., loaded from an ARC archive).
            save_callback(bytes) is called after successful save to update the archive in RAM.
            font_sync_callback() is called to trigger Picoripi font map reload.
      - open_from_path(path):
            Opens a BFN file directly from disk.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'BFN Font Editor v{VERSION}')
        self.resize(1300, 850)

        # State
        self.bfn_path = ''
        self.folder_path = ''
        self.temp_dir = ''
        self.metadata = {}
        self.sheet_images = []
        self.original_font_metadata = None
        self.original_sheet_images = []
        self._table_headers_resized = False
        self.current_sheet_index = -1
        self.selected_cell = None  # (gx, gy)
        self.selected_sim_item = None
        self.selected_char_index = -1
        self._dragging_in_sim = False
        self._dirty = False
        self.changes_saved_during_session = False

        # Integration callbacks (set by Picoripi when opening from archive)
        self.archive_save_callback = None  # callable(filename, bytes) — write updated BFN back to archive
        self.font_sync_callback = None     # callable() — trigger font map reload in Picoripi
        
        self.archive_name = ""
        self.archive_files = {}
        self.current_bfn_name = ""
        self.font_sources = {}

        self.undo_stack = QtWidgets.QUndoStack(self)
        self.undo_stack.cleanChanged.connect(lambda clean: self._set_dirty(not clean))
        
        self.auto_sync_timer = QtCore.QTimer(self)
        self.auto_sync_timer.setSingleShot(True)
        self.auto_sync_timer.timeout.connect(self.auto_sync_and_recalculate)

        self.cell_w = 24
        self.cell_h = 24
        self.rows = 5
        self.cols = 5
        self.real_w = 24
        self.real_h = 24
        self.start_glyph = 0
        self.end_glyph = 0
        self.first_code = 0
        self.last_code = 0
        self.is_dark_theme = True

        self.setup_ui()
        self.apply_theme()

    # ------------------------------------------------------------------
    # Public API for Picoripi integration
    # ------------------------------------------------------------------

    def open_from_bytes(self, bfn_bytes: bytes, bfn_name: str = "font.bfn",
                        save_callback=None, font_sync_callback=None,
                        archive_name="", archive_files=None):
        """Open a BFN from in-memory bytes (e.g., extracted from an ARC archive)."""
        self.archive_save_callback = save_callback
        self.font_sync_callback = font_sync_callback
        self.archive_name = archive_name
        self.archive_files = archive_files or {}
        self.current_bfn_name = bfn_name
        
        # Populate in_memory font sources first
        if self.archive_name:
            self.font_sources[self.archive_name] = {
                "type": "in_memory",
                "path": "",
                "files": self.archive_files
            }
        else:
            self.font_sources[bfn_name] = {
                "type": "in_memory",
                "path": "",
                "files": {bfn_name: bfn_bytes}
            }
            
        self.scan_fonts_directories()
        self.load_bfn_bytes(bfn_bytes, bfn_name)

    def open_from_path(self, path: str, font_sync_callback=None):
        """Open a BFN file directly from disk."""
        self.archive_save_callback = None
        self.font_sync_callback = font_sync_callback
        self.archive_name = ""
        self.archive_files = {}
        self.current_bfn_name = os.path.basename(path)
        
        self.font_sources = {}
        self.scan_fonts_directories()
        self.load_bfn(path)

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- Left Panel: Sheets List ---
        left_layout = QtWidgets.QVBoxLayout()

        left_layout.addWidget(QtWidgets.QLabel('Texture Sheets:'))
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
        toolbar.addWidget(QtWidgets.QLabel('Zoom:'))
        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 20.0)
        self.scale_spin.setSingleStep(0.5)
        self.scale_spin.setValue(2.0)
        self.scale_spin.valueChanged.connect(self.on_scale_spin_changed)
        toolbar.addWidget(self.scale_spin)

        self.btn_save = QtWidgets.QPushButton('Save Changes (Ctrl+S)')
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_changes)
        toolbar.addWidget(self.btn_save)

        # Undo/Redo
        self.action_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.action_undo.setShortcut(QtGui.QKeySequence.Undo)
        self.action_redo = self.undo_stack.createRedoAction(self, "Redo")
        self.action_redo.setShortcut(QtGui.QKeySequence.Redo)
        self.addAction(self.action_undo)
        self.addAction(self.action_redo)

        self.btn_undo = QtWidgets.QPushButton('Undo')
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.action_undo.trigger)
        self.action_undo.changed.connect(lambda: self.btn_undo.setEnabled(self.action_undo.isEnabled()))
        self.action_undo.changed.connect(lambda: self.btn_undo.setText(self.action_undo.text()))
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = QtWidgets.QPushButton('Redo')
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.action_redo.trigger)
        self.action_redo.changed.connect(lambda: self.btn_redo.setEnabled(self.action_redo.isEnabled()))
        self.action_redo.changed.connect(lambda: self.btn_redo.setText(self.action_redo.text()))
        toolbar.addWidget(self.btn_redo)

        toolbar.addSpacing(10)

        self.chk_auto_sync = QtWidgets.QCheckBox('Auto-sync')
        self.chk_auto_sync.setToolTip('Automatically save and recalculate all text widths in Picoripi in real-time')
        
        auto_sync_val = False
        sm = self.get_settings_manager()
        if sm:
            auto_sync_val = sm.get("bfn_auto_sync_enabled", False)
        self.chk_auto_sync.setChecked(auto_sync_val)
        self.chk_auto_sync.stateChanged.connect(self.on_auto_sync_toggled)
        toolbar.addWidget(self.chk_auto_sync)

        self.btn_sync_recalculate = QtWidgets.QPushButton('Sync & Recalculate')
        self.btn_sync_recalculate.setToolTip('Force save changes and recalculate all text widths and issues in Picoripi')
        self.btn_sync_recalculate.clicked.connect(self.force_sync_and_recalculate)
        toolbar.addWidget(self.btn_sync_recalculate)

        toolbar.addStretch()
        editor_layout.addLayout(toolbar)

        # Vertical splitter: glyph grid on top, simulator on bottom
        editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

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
        sim_header_layout.addWidget(QtWidgets.QLabel('Enter text to simulate rendering (with kerning & width):'))
        
        self.chk_sync_sim_text = QtWidgets.QCheckBox('Sync with editor')
        self.chk_sync_sim_text.setChecked(True)
        self.chk_sync_sim_text.setToolTip("Automatically synchronize with the selected string in the main translation editor")
        sim_header_layout.addWidget(self.chk_sync_sim_text)
        sim_header_layout.addStretch(1)
        sim_layout.addLayout(sim_header_layout)

        self.sim_input = QtWidgets.QPlainTextEdit()
        self.sim_input.setPlaceholderText(
            'Type anything here to test in real-time... Right-click for pangrams/placeholder text.'
        )
        self.sim_input.setMaximumHeight(65)
        self.sim_input.textChanged.connect(self.on_sim_text_changed)
        self.sim_input.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.sim_input.customContextMenuRequested.connect(self.show_sim_input_context_menu)
        sim_layout.addWidget(self.sim_input)

        self.sim_scene = QtWidgets.QGraphicsScene(self)
        self.sim_view = SimImageView()
        self.sim_view.setScene(self.sim_scene)
        self.sim_view.setRenderHint(QtGui.QPainter.Antialiasing, False)
        self.sim_view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
        sim_layout.addWidget(self.sim_view, 1)

        editor_splitter.addWidget(sim_container)
        editor_splitter.setSizes([450, 250])
        editor_layout.addWidget(editor_splitter)

        self.tabs.addTab(tab_editor, "Font Editor")

        # Tab 2: Glyph Table
        tab_table = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(tab_table)
        table_layout.setContentsMargins(8, 8, 8, 8)

        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel('Search Glyph/Character:'))
        self.table_search = QtWidgets.QLineEdit()
        self.table_search.setPlaceholderText('Type character, index or sheet index to filter...')
        self.table_search.textChanged.connect(self.populate_glyph_table)
        search_layout.addWidget(self.table_search)
        table_layout.addLayout(search_layout)

        self.table_glyphs = QtWidgets.QTableWidget()
        headers = [
            'Original Render', 'Original Char',
            'Glyph Render', 'Character', 'Font Char',
            'Texture Sheet', 'Tile Position', 'Kerning', 'Width'
        ]
        self.table_glyphs.setColumnCount(len(headers))
        self.table_glyphs.setHorizontalHeaderLabels(headers)
        for col_idx, header_text in enumerate(headers):
            item = self.table_glyphs.horizontalHeaderItem(col_idx)
            if item:
                item.setToolTip(header_text)
        header = self.table_glyphs.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.installEventFilter(self)
        
        # Connect double-click on header boundary to auto-resize column to fit contents
        header.sectionHandleDoubleClicked.connect(self.on_header_handle_double_clicked)
        
        # Ensure that during interactive drag-resizing, cell widgets update dynamically in real time
        header.sectionResized.connect(lambda *args: self.table_glyphs.updateGeometries())
        
        self.table_glyphs.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        self.table_glyphs.itemChanged.connect(self.on_table_item_changed)
        self.table_glyphs.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_glyphs.customContextMenuRequested.connect(self.show_table_context_menu)
        table_layout.addWidget(self.table_glyphs)

        # Rapid keyboard navigation in table
        original_table_keyPress = self.table_glyphs.keyPressEvent

        def table_keyPressEvent(event):
            key = event.key()
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if key == QtCore.Qt.Key_C:
                    self.copy_glyph_values()
                    event.accept()
                    return
                elif key == QtCore.Qt.Key_V:
                    self.paste_glyph_values()
                    event.accept()
                    return

            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
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
                if key not in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab,
                               QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter,
                               QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                    current = self.table_glyphs.currentIndex()
                    if current.isValid() and current.column() in (3, 7, 8):
                        self.table_glyphs.edit(current)
            original_table_keyPress(event)

        self.table_glyphs.keyPressEvent = table_keyPressEvent

        self.tabs.addTab(tab_table, "Glyph Table")

        # --- Right Panel: Glyph Info & Editing ---
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(QtWidgets.QLabel('Glyph Information:'))

        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        right_layout.addWidget(self.info_text)

        form_layout = QtWidgets.QGridLayout()
        form_layout.addWidget(QtWidgets.QLabel('Kerning (Left Shift):'), 0, 0)
        self.spin_kerning = QtWidgets.QSpinBox()
        self.spin_kerning.setRange(-128, 127)
        self.spin_kerning.setEnabled(False)
        self.spin_kerning.valueChanged.connect(self.on_params_changed)
        form_layout.addWidget(self.spin_kerning, 0, 1)

        form_layout.addWidget(QtWidgets.QLabel('Width (Char Space):'), 1, 0)
        self.spin_width = QtWidgets.QSpinBox()
        self.spin_width.setRange(0, 255)
        self.spin_width.setEnabled(False)
        self.spin_width.valueChanged.connect(self.on_params_changed)
        form_layout.addWidget(self.spin_width, 1, 1)

        right_layout.addLayout(form_layout)

        self.btn_auto_width = QtWidgets.QPushButton('Auto-detect Width')
        self.btn_auto_width.setEnabled(False)
        self.btn_auto_width.clicked.connect(self.auto_detect_width)
        right_layout.addWidget(self.btn_auto_width)

        right_layout.addSpacing(15)
        right_layout.addWidget(QtWidgets.QLabel('Texture Actions:'))

        self.btn_export_sheet = QtWidgets.QPushButton('Export Current Sheet PNG...')
        self.btn_export_sheet.setEnabled(False)
        self.btn_export_sheet.clicked.connect(self.export_sheet_png)
        right_layout.addWidget(self.btn_export_sheet)

        self.btn_import_sheet = QtWidgets.QPushButton('Import Current Sheet PNG...')
        self.btn_import_sheet.setEnabled(False)
        self.btn_import_sheet.clicked.connect(self.import_sheet_png)
        right_layout.addWidget(self.btn_import_sheet)

        right_layout.addSpacing(10)

        self.btn_export_glyph = QtWidgets.QPushButton('Export Selected Glyph PNG...')
        self.btn_export_glyph.setEnabled(False)
        self.btn_export_glyph.clicked.connect(self.export_glyph_png)
        right_layout.addWidget(self.btn_export_glyph)

        self.btn_import_glyph = QtWidgets.QPushButton('Import Selected Glyph PNG...')
        self.btn_import_glyph.setEnabled(False)
        self.btn_import_glyph.clicked.connect(self.import_glyph_png)
        right_layout.addWidget(self.btn_import_glyph)

        right_layout.addSpacing(10)

        self.btn_render_font = QtWidgets.QPushButton('Render System Font to Glyphs...')
        self.btn_render_font.setEnabled(False)
        self.btn_render_font.clicked.connect(self.render_system_font_to_glyphs)
        right_layout.addWidget(self.btn_render_font)

        right_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(320)
        main_layout.addWidget(right_widget)

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage('Ready. Open a BFN file or extracted folder.')

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

    def apply_dark_theme(self):
        self.apply_theme()

    def setup_shortcuts(self):
        self.sc_save = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        self.sc_save.activated.connect(self.save_changes)

        self.sc_left = QtWidgets.QShortcut(QtGui.QKeySequence("Left"), self)
        self.sc_left.activated.connect(lambda: self.navigate_grid(-1, 0))
        self.sc_right = QtWidgets.QShortcut(QtGui.QKeySequence("Right"), self)
        self.sc_right.activated.connect(lambda: self.navigate_grid(1, 0))
        self.sc_up = QtWidgets.QShortcut(QtGui.QKeySequence("Up"), self)
        self.sc_up.activated.connect(lambda: self.navigate_grid(0, -1))
        self.sc_down = QtWidgets.QShortcut(QtGui.QKeySequence("Down"), self)
        self.sc_down.activated.connect(lambda: self.navigate_grid(0, 1))

        self.sc_close = QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self)
        self.sc_close.activated.connect(self.on_esc_pressed)

    def on_esc_pressed(self):
        focus_w = self.focusWidget()
        if hasattr(self, 'table_glyphs') and self.table_glyphs:
            if self.table_glyphs.state() == QtWidgets.QAbstractItemView.EditingState:
                if focus_w:
                    self.sc_close.setEnabled(False)
                    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
                    QtWidgets.QApplication.sendEvent(focus_w, event)
                    self.sc_close.setEnabled(True)
                return
        self.close()

    def eventFilter(self, source, event):
        if (hasattr(self, 'table_glyphs') and self.table_glyphs and
            source == self.table_glyphs.horizontalHeader() and
            event.type() == QtCore.QEvent.MouseButtonDblClick):
            
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

    def on_header_handle_double_clicked(self, logical_index):
        # Calculate maximum width of this column manually based ONLY on row content (excluding header text)
        col = logical_index
        
        # Start with a minimum base width for cell margins
        max_w = 35
        
        # Iterate over all rows to find the max width of cell contents
        row_count = self.table_glyphs.rowCount()
        table_font = self.table_glyphs.font()
        
        for row in range(row_count):
            widget = self.table_glyphs.cellWidget(row, col)
            if widget:
                # If it's a QLabel with a pixmap, use the pixmap width plus margins
                if isinstance(widget, QtWidgets.QLabel) and widget.pixmap() and not widget.pixmap().isNull():
                    max_w = max(max_w, widget.pixmap().width() + 16)
                else:
                    max_w = max(max_w, widget.sizeHint().width())
            else:
                item = self.table_glyphs.item(row, col)
                if item and item.text():
                    # Check if item has custom font
                    item_font = item.font() if item.font().family() else table_font
                    item_fm = QtGui.QFontMetrics(item_font)
                    text_w = item_fm.horizontalAdvance(item.text())
                    max_w = max(max_w, text_w + 24)
                    
        # Apply limits (between 35 and 600)
        max_w = max(35, min(max_w, 600))
        
        # Set the column width
        self.table_glyphs.setColumnWidth(col, max_w)

    def get_settings_manager(self):
        curr = self.parent()
        while curr:
            if hasattr(curr, "settings_manager") and curr.settings_manager:
                return curr.settings_manager
            curr = curr.parent()
        
        from PyQt5.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "settings_manager") and w.settings_manager:
                return w.settings_manager
        return None

    def save_column_widths(self):
        sm = self.get_settings_manager()
        if sm:
            widths = []
            for col in range(self.table_glyphs.columnCount()):
                widths.append(self.table_glyphs.columnWidth(col))
            sm.set("bfn_glyph_table_column_widths", widths)
            if hasattr(sm.mw, "bfn_glyph_table_column_widths"):
                sm.mw.bfn_glyph_table_column_widths = widths
            sm.save_settings()

    # ------------------------------------------------------------------
    # Override save_changes to also call Picoripi sync callbacks
    # ------------------------------------------------------------------

    def save_changes(self, silent=False):
        # Call the mixin implementation (defined in BfnIoMixin)
        super_save = None
        for cls in type(self).__mro__:
            if cls is BfnEditorWindow:
                continue
            if 'save_changes' in cls.__dict__:
                super_save = cls.__dict__['save_changes']
                break
        if super_save:
            super_save(self, silent=silent)

        # After successful save, trigger Picoripi font sync
        if not self._dirty and self.font_sync_callback:
            try:
                self.font_sync_callback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Tree Widget and Active BFN Switch Methods
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Tree Widget and Active BFN Switch Methods
    # ------------------------------------------------------------------

    def scan_fonts_directories(self):
        """Scan active plugin fonts directory and custom fonts directory for archives and loose fonts."""
        # Preserve existing in-memory sources
        in_memory_sources = {k: v for k, v in self.font_sources.items() if v["type"] == "in_memory"}
        self.font_sources = in_memory_sources
        
        parent = self.parent()
        if not parent:
            return
            
        plugin_name = getattr(parent, 'active_game_plugin', None)
        custom_fonts_path = getattr(parent, 'fonts_dir_path', None)
        
        from pathlib import Path
        fonts_dirs = []
        if plugin_name:
            fonts_dirs.append(Path("plugins") / plugin_name / "fonts")
        if custom_fonts_path:
            custom_dir = Path(custom_fonts_path)
            if custom_dir.is_dir():
                fonts_dirs.append(custom_dir)
                
        from core.containers import ContainerManager
        
        for fonts_dir in fonts_dirs:
            if not fonts_dir.is_dir():
                continue
            for font_file in fonts_dir.iterdir():
                if not font_file.is_file():
                    continue
                suffix = font_file.suffix.lower()
                
                # Check for archives containing fonts
                if suffix in (".arc", ".rarc", ".u8"):
                    archive_name = font_file.name
                    if archive_name in self.font_sources:
                        continue
                    try:
                        archive_data = font_file.read_bytes()
                        if ContainerManager.is_supported(archive_data):
                            container = ContainerManager.open(archive_data)
                            if container:
                                files = {}
                                for inner_path in container.list_files():
                                    if Path(inner_path).suffix.lower() == ".bfn":
                                        try:
                                            files[Path(inner_path).name] = container.read_file(inner_path)
                                        except Exception:
                                            pass
                                if files:
                                    self.font_sources[archive_name] = {
                                        "type": "disk_archive",
                                        "path": str(font_file.resolve()),
                                        "files": files
                                    }
                    except Exception as e:
                        print(f"Error scanning archive {font_file}: {e}")
                        
                # Check for loose bfn files
                elif suffix == ".bfn":
                    font_name = font_file.name
                    if font_name in self.font_sources:
                        continue
                    try:
                        bfn_bytes = font_file.read_bytes()
                        self.font_sources[font_name] = {
                            "type": "disk_loose",
                            "path": str(font_file.resolve()),
                            "files": {font_name: bfn_bytes}
                        }
                    except Exception as e:
                        print(f"Error scanning loose font {font_file}: {e}")

    def rebuild_tree_widget(self, active_sheet_count=0, expanded_keys=None):
        """Populate the left tree widget with all found font sources, BFN files and sheets."""
        # Save expanded state of items to avoid collapsing on rebuild
        if expanded_keys is None:
            expanded_keys = set()
            iterator = QtWidgets.QTreeWidgetItemIterator(self.list_sheets)
            while iterator.value():
                item = iterator.value()
                if item.isExpanded():
                    archive = item.data(0, ROLE_ARCHIVE_NAME)
                    font = item.data(0, ROLE_FONT_NAME)
                    sheet = item.data(0, ROLE_SHEET_IDX)
                    # We identify nodes by:
                    # - (source_name, None) for top-level archive/source node
                    # - (source_name, bfn_name) for font file node
                    if sheet is None:
                        expanded_keys.add((archive, font))
                iterator += 1

        self.list_sheets.blockSignals(True)
        self.list_sheets.clear()
        
        from core.bfn_core import BfnCore
        
        for source_name, source_info in sorted(self.font_sources.items()):
            src_type = source_info["type"]
            disk_path = source_info["path"]
            files = source_info["files"]
            
            is_archive = src_type == "disk_archive" or (src_type == "in_memory" and len(files) > 1) or (self.archive_name and source_name == self.archive_name)
            
            if is_archive:
                archive_item = QtWidgets.QTreeWidgetItem(self.list_sheets, [source_name])
                archive_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                archive_item.setData(0, ROLE_DISK_PATH, disk_path)
                archive_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                
                # Restore top-level expansion
                if not expanded_keys or (source_name, None) in expanded_keys:
                    archive_item.setExpanded(True)
                else:
                    archive_item.setExpanded(False)
                
                for bfn_name, bfn_bytes in sorted(files.items()):
                    file_item = QtWidgets.QTreeWidgetItem(archive_item, [bfn_name])
                    file_item.setData(0, ROLE_FONT_NAME, bfn_name)
                    file_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                    file_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                    file_item.setData(0, ROLE_DISK_PATH, disk_path)
                    
                    sheet_count = 0
                    is_current = (bfn_name == self.current_bfn_name and (not self.archive_name or source_name == self.archive_name))
                    if is_current:
                        sheet_count = active_sheet_count
                    else:
                        try:
                            temp_bfn = BfnCore()
                            temp_bfn.load(bfn_bytes)
                            if temp_bfn.gly1:
                                gly = temp_bfn.gly1[0]
                                sheet_count = (gly["end_glyph"] - gly["start_glyph"]) // (gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]) + 1
                        except Exception:
                            sheet_count = 1
                            
                    # Restore font expansion
                    if (not expanded_keys and is_current) or (source_name, bfn_name) in expanded_keys:
                        file_item.setExpanded(True)
                    else:
                        file_item.setExpanded(False)
                        
                    for s in range(sheet_count):
                        sheet_item = QtWidgets.QTreeWidgetItem(file_item, [f"Sheet {s}"])
                        sheet_item.setData(0, ROLE_SHEET_IDX, s)
                        sheet_item.setData(0, ROLE_FONT_NAME, bfn_name)
                        sheet_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                        sheet_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                        sheet_item.setData(0, ROLE_DISK_PATH, disk_path)
            else:
                bfn_name = list(files.keys())[0]
                
                file_item = QtWidgets.QTreeWidgetItem(self.list_sheets, [bfn_name])
                file_item.setData(0, ROLE_FONT_NAME, bfn_name)
                file_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                file_item.setData(0, ROLE_DISK_PATH, disk_path)
                
                sheet_count = 0
                is_current = (bfn_name == self.current_bfn_name and not self.archive_name)
                if is_current:
                    sheet_count = active_sheet_count
                else:
                    try:
                        temp_bfn = BfnCore()
                        temp_bfn.load(files[bfn_name])
                        if temp_bfn.gly1:
                            gly = temp_bfn.gly1[0]
                            sheet_count = (gly["end_glyph"] - gly["start_glyph"]) // (gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]) + 1
                    except Exception:
                        sheet_count = 1
                
                # For loose files, the key is (None, bfn_name)
                if not expanded_keys or (None, bfn_name) in expanded_keys:
                    file_item.setExpanded(True)
                else:
                    file_item.setExpanded(False)
                    
                for s in range(sheet_count):
                    sheet_item = QtWidgets.QTreeWidgetItem(file_item, [f"Sheet {s}"])
                    sheet_item.setData(0, ROLE_SHEET_IDX, s)
                    sheet_item.setData(0, ROLE_FONT_NAME, bfn_name)
                    sheet_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                    sheet_item.setData(0, ROLE_DISK_PATH, disk_path)
                    
        self.list_sheets.blockSignals(False)

    def set_current_sheet_row(self, sheet_idx):
        """Select a sheet item in the tree that matches the sheet_idx for the current font using role metadata."""
        iterator = QtWidgets.QTreeWidgetItemIterator(self.list_sheets)
        while iterator.value():
            item = iterator.value()
            role_sheet = item.data(0, ROLE_SHEET_IDX)
            role_font = item.data(0, ROLE_FONT_NAME)
            role_archive = item.data(0, ROLE_ARCHIVE_NAME)
            
            if role_sheet == sheet_idx and role_font == self.current_bfn_name:
                if not self.archive_name or role_archive == self.archive_name:
                    self.list_sheets.blockSignals(True)
                    self.list_sheets.setCurrentItem(item)
                    self.list_sheets.blockSignals(False)
                    self.select_sheet(sheet_idx)
                    break
            iterator += 1

    def select_sheet_tree(self, current, previous):
        """Handle tree item selection to change sheet or switch active font using role metadata."""
        if not current:
            return
            
        sheet_idx = current.data(0, ROLE_SHEET_IDX)
        bfn_name = current.data(0, ROLE_FONT_NAME)
        
        if sheet_idx is None:
            if bfn_name:
                if current.childCount() > 0:
                    self.list_sheets.setCurrentItem(current.child(0))
                    return
                sheet_idx = 0
            else:
                # Not a sheet item
                return
                
        archive_name = current.data(0, ROLE_ARCHIVE_NAME) or ""
        source_type = current.data(0, ROLE_SOURCE_TYPE)
        disk_path = current.data(0, ROLE_DISK_PATH) or ""
        
        is_different = (bfn_name != self.current_bfn_name or archive_name != self.archive_name)
        if is_different:
            self.switch_active_bfn_new(bfn_name, archive_name, source_type, disk_path, sheet_idx)
        else:
            self.select_sheet(sheet_idx)

    def switch_active_bfn_new(self, bfn_name, archive_name, source_type, disk_path, target_sheet_idx):
        """Switch active BFN font with proper save prompts and target file callbacks."""
        if self._dirty:
            reply = QtWidgets.QMessageBox.question(
                self, 
                'Unsaved Changes', 
                f"You have unsaved changes in '{self.current_bfn_name}'! Do you want to save them before switching?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.save_changes()
            elif reply == QtWidgets.QMessageBox.Cancel:
                self.set_current_sheet_row(self.current_sheet_index)
                return
                
        # Retrieve bytes from font_sources
        key = archive_name if archive_name else bfn_name
        source_info = self.font_sources.get(key)
        if not source_info:
            return
            
        bfn_bytes = source_info["files"].get(bfn_name)
        if not bfn_bytes:
            return
            
        # Set target callbacks based on source type
        self.archive_name = archive_name
        self.current_bfn_name = bfn_name
        
        if source_type == "in_memory":
            # Callback is provided by Picoripi
            # self.archive_save_callback is preserved
            self.archive_files = source_info["files"]
        elif source_type == "disk_archive":
            # Dynamic save callback for disk archives
            def dynamic_save_callback(filename: str, new_bytes: bytes):
                try:
                    from core.containers import ContainerManager
                    from pathlib import Path
                    archive_bytes = Path(disk_path).read_bytes()
                    container = ContainerManager.open(archive_bytes)
                    if container:
                        container.write_file(filename, new_bytes)
                        updated_archive = container.pack()
                        Path(disk_path).write_bytes(updated_archive)
                        # Update our local source files cache
                        source_info["files"][filename] = new_bytes
                        print(f"BFN Editor: Saved and packed '{filename}' to disk archive '{disk_path}'.")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, 'BFN Editor', f'Failed to write back to disk archive:\n{ex}')
            self.archive_save_callback = dynamic_save_callback
            self.archive_files = source_info["files"]
        elif source_type == "disk_loose":
            # Dynamic save callback for loose files on disk
            def dynamic_save_callback(filename: str, new_bytes: bytes):
                try:
                    from pathlib import Path
                    Path(disk_path).write_bytes(new_bytes)
                    # Update local source cache
                    source_info["files"][filename] = new_bytes
                    print(f"BFN Editor: Saved loose font '{filename}' to '{disk_path}'.")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, 'BFN Editor', f'Failed to save loose BFN to disk:\n{ex}')
            self.archive_save_callback = dynamic_save_callback
            self.archive_files = {}
            
        # Temporarily clear undo stack to avoid cross-font undoing
        self.undo_stack.clear()
        
        # Спробуємо завантажити оригінальний шрифт для порівняння
        self.original_font_metadata = None
        self.original_sheet_images = []
        
        parent = self.parent()
        if parent:
            orig_fonts_path = getattr(parent, 'orig_fonts_dir_path', None)
            if orig_fonts_path:
                from pathlib import Path
                orig_dir = Path(orig_fonts_path)
                if orig_dir.is_dir():
                    orig_bytes = None
                    if self.archive_name:
                        orig_archive_path = orig_dir / self.archive_name
                        if orig_archive_path.is_file():
                            try:
                                from core.containers import ContainerManager
                                archive_data = orig_archive_path.read_bytes()
                                if ContainerManager.is_supported(archive_data):
                                    container = ContainerManager.open(archive_data)
                                    if container:
                                        for inner_path in container.list_files():
                                            if Path(inner_path).name == bfn_name:
                                                orig_bytes = container.read_file(inner_path)
                                                break
                            except Exception as ex:
                                print(f"Error loading original font from archive: {ex}")
                    else:
                        orig_file_path = orig_dir / bfn_name
                        if orig_file_path.is_file():
                            try:
                                orig_bytes = orig_file_path.read_bytes()
                            except Exception as ex:
                                print(f"Error loading loose original font: {ex}")
                                
                    if orig_bytes:
                        try:
                            self.load_original_bfn_bytes(orig_bytes, bfn_name)
                            print(f"BFN Editor: Successfully loaded original comparison font '{bfn_name}'.")
                        except Exception as ex:
                            print(f"Failed to parse original font: {ex}")
        
        self.load_bfn_bytes(bfn_bytes, bfn_name)
        self.set_current_sheet_row(target_sheet_idx)

    def showEvent(self, event):
        super().showEvent(event)
        self.scan_fonts_directories()
        sheet_count = len(self.sheet_images)
        self.rebuild_tree_widget(sheet_count)
        
        if self.current_bfn_name:
            self.set_current_sheet_row(self.current_sheet_index if self.current_sheet_index >= 0 else 0)
        else:
            # Standalone mode: auto-select first sheet of first font to avoid empty table
            def find_first_sheet(parent_item):
                if parent_item.data(0, ROLE_SHEET_IDX) is not None:
                    return parent_item
                for i in range(parent_item.childCount()):
                    res = find_first_sheet(parent_item.child(i))
                    if res:
                        return res
                return None
                
            first_sheet = None
            for i in range(self.list_sheets.topLevelItemCount()):
                first_sheet = find_first_sheet(self.list_sheets.topLevelItem(i))
                if first_sheet:
                    break
            if first_sheet:
                self.list_sheets.setCurrentItem(first_sheet)

    def on_auto_sync_toggled(self, state):
        is_checked = (state == QtCore.Qt.Checked)
        sm = self.get_settings_manager()
        if sm:
            sm.set("bfn_auto_sync_enabled", is_checked)
            sm.save_settings()
            
        if is_checked and self._dirty:
            self.schedule_auto_sync()

    def schedule_auto_sync(self):
        self.auto_sync_timer.start(300)

    def auto_sync_and_recalculate(self):
        if self._dirty:
            self.save_changes(silent=True)

    def force_sync_and_recalculate(self):
        self.save_changes(silent=True)
        if not self._dirty and self.font_sync_callback:
            try:
                self.font_sync_callback()
            except Exception:
                pass
        self.status.showMessage("Force recalculation complete. Picoripi widths updated.")

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)
