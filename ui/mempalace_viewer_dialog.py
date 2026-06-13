import os
import json
from PyQt6.QtWidgets import (
    QDialog, QAbstractItemView, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QProgressBar, QTextEdit, 
    QMessageBox, QGroupBox, QTabWidget, QWidget, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QSplitter
)
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtCore import Qt, pyqtSlot
from core.mempalace_client import MemePalaceClient
from utils.logging_utils import log_info, log_error

class MemePalaceViewerDialog(QDialog):
    """Dialog class for meme palace viewer."""
    def __init__(self, main_window, parent=None):
        """Initialize a new instance."""
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("MemePalace Database Viewer")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)
        
        # Premium Fluent-Style Sheet
        self.setStyleSheet("""
            QDialog {
                background-color: #fcfcfc;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #333333;
            }
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                background-color: #ffffff;
                min-width: 150px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton#refreshBtn {
                background-color: #107c41;
            }
            QPushButton#refreshBtn:hover {
                background-color: #0b5930;
            }
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 6px;
                background-color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-bottom: 1px solid #f3f3f3;
            }
            QListWidget::item:selected {
                background-color: #e2f0fd;
                color: #0078d7;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f3f3f3;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 15px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 2px solid #0078d7;
                font-weight: bold;
            }
            QTableWidget {
                border: none;
                background-color: #ffffff;
                gridline-color: #eaeaea;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QTableWidget::horizontalHeader {
                background-color: #f3f3f3;
                border: none;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 6px;
                background-color: #ffffff;
                color: #333333;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                padding: 10px;
            }
        """)

        self.client = None
        self._init_client()
        self._setup_ui()
        self._load_wings()

    def _init_client(self):
        """Locate the SQLite database using recursive project/single-file search logic."""
        try:
            project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else None
            if not project_dir:
                project_dir = os.path.dirname(self.mw.data_store.project_file) if (hasattr(self.mw, "data_store") and self.mw.data_store and getattr(self.mw.data_store, "project_file", None)) else os.getcwd()

            if project_dir:
                db_name = "mempalace_local.db"
                curr = project_dir
                for _ in range(4):
                    tp_subdir = os.path.join(curr, "TwilightPrincess")
                    if os.path.isdir(tp_subdir) and os.path.exists(os.path.join(tp_subdir, db_name)):
                        project_dir = tp_subdir
                        break
                    if os.path.exists(os.path.join(curr, db_name)):
                        project_dir = curr
                        break
                    parent = os.path.dirname(curr)
                    if parent == curr:
                        break
                    curr = parent

            self.client = MemePalaceClient(project_dir=project_dir)
            log_info(f"MemePalaceViewer initialized SQLite client at path: {self.client.db_path}")
        except Exception as e:
            log_error(f"Failed to initialize database client in viewer: {e}")

    def _setup_ui(self):
        """Internal helper to setup ui."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Header bar
        header_layout = QHBoxLayout()
        
        # Wing Selection
        wing_label = QLabel("Wing (Active Game):")
        self.wing_combo = QComboBox()
        self.wing_combo.currentIndexChanged.connect(self._handle_wing_changed)
        header_layout.addWidget(wing_label)
        header_layout.addWidget(self.wing_combo)
        
        header_layout.addSpacing(20)

        # DB Path Indicator
        self.db_path_label = QLabel("Database Path: Loading...")
        self.db_path_label.setStyleSheet("color: #666666; font-family: 'Consolas', monospace; font-size: 11px;")
        if self.client and self.client.db_path:
            self.db_path_label.setText(f"SQLite DB: {os.path.abspath(self.client.db_path)}")
        header_layout.addWidget(self.db_path_label, 1)

        # Refresh Button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.clicked.connect(self._refresh_data)
        header_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(header_layout)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel - Rooms list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_label = QLabel("Story Rooms / Timeline Locations:")
        left_label.setStyleSheet("font-weight: bold; color: #0078d7;")
        left_layout.addWidget(left_label)
        
        self.rooms_list = QListWidget()
        self.rooms_list.itemSelectionChanged.connect(self._handle_room_selected)
        left_layout.addWidget(self.rooms_list)
        
        splitter.addWidget(left_widget)

        # Right Panel - Tabs Widget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Scene Dialogues & Actions
        scene_tab = QWidget()
        scene_layout = QVBoxLayout(scene_tab)
        scene_layout.setContentsMargins(10, 10, 10, 10)
        
        # Visual Scene Action
        vis_label = QLabel("Visual Action Context (AI Scene Annotation):")
        vis_label.setStyleSheet("font-weight: bold;")
        scene_layout.addWidget(vis_label)
        
        self.visual_context_text = QTextEdit()
        self.visual_context_text.setReadOnly(True)
        self.visual_context_text.setPlaceholderText("No visual action context annotation has been generated for this room yet...")
        scene_layout.addWidget(self.visual_context_text)
        
        # Dialogues Block
        diag_label = QLabel("Verbatim Dialogue Lines in Room:")
        diag_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        scene_layout.addWidget(diag_label)
        
        self.dialogues_table = QTableWidget()
        self.dialogues_table.setColumnCount(3)
        self.dialogues_table.setHorizontalHeaderLabels(["Line ID", "Speaker (Deducted)", " verbatims Text"])
        self.dialogues_table.horizontalHeader().setStretchLastSection(True)
        self.dialogues_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dialogues_table.cellDoubleClicked.connect(self._handle_dialogue_double_clicked)
        scene_layout.addWidget(self.dialogues_table)
        
        self.tab_widget.addTab(scene_tab, "Scene Context & Dialogues")

        # Tab 2: Character Cast & Relations
        relations_tab = QWidget()
        relations_layout = QVBoxLayout(relations_tab)
        relations_tab.setLayout(relations_layout)
        relations_layout.setContentsMargins(10, 10, 10, 10)
        
        cast_label = QLabel("Global Temporal Knowledge Graph Relations:")
        cast_label.setStyleSheet("font-weight: bold; color: #0078d7;")
        relations_layout.addWidget(cast_label)
        
        self.relations_table = QTableWidget()
        self.relations_table.setColumnCount(4)
        self.relations_table.setHorizontalHeaderLabels(["Source Entity", "Relationship Type", "Target Entity", "Timeline Room/Source"])
        self.relations_table.horizontalHeader().setStretchLastSection(True)
        self.relations_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        relations_layout.addWidget(self.relations_table)
        
        self.tab_widget.addTab(relations_tab, "Character Cast & Relations")
        
        splitter.addWidget(self.tab_widget)
        
        # Set splitter proportions (30% left list, 70% right tabs)
        splitter.setSizes([270, 630])
        main_layout.addWidget(splitter)

    def _load_wings(self):
        """Fetch wings from SQLite and populate combo box."""
        if not self.client:
            return
        
        try:
            wings = self.client.get_wings()
            self.wing_combo.clear()
            
            for wing in wings:
                self.wing_combo.addItem(wing["name"], wing["name"])
                
            # Pre-select matching wing for current active rules
            if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
                game_name = self.mw.active_game_rules.get_display_name()
                clean_name = "".join([c if c.isalnum() else "_" for c in game_name]).strip("_")
                index = self.wing_combo.findText(clean_name)
                if index >= 0:
                    self.wing_combo.setCurrentIndex(index)
                    
            # Fallback if combo is still empty
            if self.wing_combo.count() == 0:
                self.wing_combo.addItem("Zelda_TP", "Zelda_TP")
                
        except Exception as e:
            log_error(f"Error loading wings in viewer: {e}")

    def _load_rooms_and_relations(self):
        """Fetch all rooms and relations for the selected Wing."""
        if not self.client:
            return
            
        wing_name = self.wing_combo.currentData() or self.wing_combo.currentText()
        if not wing_name:
            return

        # Keep track of currently selected room to restore selection state after refresh
        selected_room = None
        selected_items = self.rooms_list.selectedItems()
        if selected_items:
            selected_room = selected_items[0].data(Qt.ItemDataRole.UserRole)

        # 1. Load Rooms List
        try:
            self.rooms_list.clear()
            rooms = self.client.get_rooms(wing_name)
            
            # Sort rooms so that Global_Cast_Profiles always comes first!
            rooms_sorted = []
            cast_room = None
            for r in rooms:
                if r["name"] == "Global_Cast_Profiles":
                    cast_room = r
                else:
                    rooms_sorted.append(r)
            
            rooms_sorted.sort(key=lambda x: x["name"])
            if cast_room:
                rooms_sorted.insert(0, cast_room)

            restore_item = None
            for room in rooms_sorted:
                name = room["name"]
                item = QListWidgetItem()
                
                # Special styling for cast profiles
                if name == "Global_Cast_Profiles":
                    item.setText("👥 GLOBAL CHARACTER CAST")
                    item.setForeground(QColor("#5c2d91"))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setText(name.replace("_", " "))
                    
                item.setData(Qt.ItemDataRole.UserRole, name) # Keep clean SQLite key
                self.rooms_list.addItem(item)
                
                if selected_room and name == selected_room:
                    restore_item = item
                
            # Restore previous selection or fallback to first item
            if restore_item:
                self.rooms_list.setCurrentItem(restore_item)
            elif self.rooms_list.count() > 0:
                self.rooms_list.setCurrentRow(0)
                
        except Exception as e:
            log_error(f"Error loading rooms in viewer: {e}")

        # 2. Load Relations Table
        try:
            self.relations_table.setRowCount(0)
            relations = self.client.get_relations(wing_name)
            
            self.relations_table.setRowCount(len(relations))
            for row_idx, rel in enumerate(relations):
                # Highlight relationship with colors
                src = QTableWidgetItem(rel.get("source", "Unknown"))
                rel_type = QTableWidgetItem(rel.get("relation", ""))
                rel_type.setForeground(QColor("#0078d7"))
                tgt = QTableWidgetItem(rel.get("target", "Unknown"))
                valid = QTableWidgetItem(rel.get("valid_from", "Global").replace("_", " "))
                
                self.relations_table.setItem(row_idx, 0, src)
                self.relations_table.setItem(row_idx, 1, rel_type)
                self.relations_table.setItem(row_idx, 2, tgt)
                self.relations_table.setItem(row_idx, 3, valid)
                
            self.relations_table.resizeColumnsToContents()
        except Exception as e:
            log_error(f"Error loading relations in viewer: {e}")

    @pyqtSlot(int)
    def _handle_wing_changed(self, index):
        """Internal helper to handle wing changed."""
        self._load_rooms_and_relations()

    @pyqtSlot()
    def _handle_room_selected(self):
        """Triggered when a room is clicked in the left list widget."""
        selected_items = self.rooms_list.selectedItems()
        if not selected_items or not self.client:
            return
            
        room_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
        wing_name = self.wing_combo.currentData() or self.wing_combo.currentText()
        
        try:
            # Clear UI before loading
            self.visual_context_text.clear()
            self.dialogues_table.setRowCount(0)
            
            drawers = self.client.get_room_drawers(wing_name, room_name)
            
            visual_ctx = ""
            dialogue_lines = []
            speaker_map = {}

            # Parse drawers content
            for dr in drawers:
                name = dr["name"]
                content = dr["content"]
                meta = dr["metadata"] or {}
                
                if name == "visual_scene_context":
                    visual_ctx = content
                elif name == "dialogues" or name == "dialogue_lines":
                    # Parse dialogues block. Verbatim format is "[Line_ID]: text" or "ID: line_id | Text: text"
                    speaker_map = meta.get("speaker_map") or {}
                    
                    lines = content.strip().split("\n")
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        # Format 1: "ID: zelda_tp_script_Str_12 | Text: Tell me..."
                        if line.startswith("ID: ") and " | Text: " in line:
                            parts = line.partition(" | Text: ")
                            line_id = parts[0].replace("ID: ", "").strip()
                            text = parts[2].strip()
                            # Deduce speaker
                            speaker = speaker_map.get(line_id) or "Unknown Speaker"
                            dialogue_lines.append([line_id, speaker, text])
                        
                        # Format 2: "[zelda_tp_script_Str_12]: Tell me..."
                        elif line.startswith("[") and "]: " in line:
                            parts = line.partition("]: ")
                            line_id = parts[0][1:].strip()
                            text = parts[2].strip()
                            speaker = speaker_map.get(line_id) or speaker_map.get(f"[{line_id}]") or "Unknown Speaker"
                            dialogue_lines.append([line_id, speaker, text])
                        
                        # Format 3: Continuation of the previous dialogue line OR raw line without exact ID
                        else:
                            if dialogue_lines:
                                # Append to the text of the last added line
                                dialogue_lines[-1][2] += "\n" + line.strip()
                            else:
                                # Fallback if it's the very first line and somehow doesn't match ID formats
                                if ":" in line and not line.startswith("{"):
                                    parts = line.partition(":")
                                    dialogue_lines.append([parts[0].strip(), "Unknown Speaker", parts[2].strip()])
                                else:
                                    dialogue_lines.append(["N/A", "Unknown Speaker", line.strip()])
                
                elif name == "character_cast_profiles":
                    # Special Global Cast Profiles Drawer
                    visual_ctx = f"👥 GLOBAL CHARACTER CAST PROFILES:\n\n{content}"
            
            # 1. Show Visual scene actions with premium HTML styling
            if visual_ctx:
                if room_name == "Global_Cast_Profiles":
                    self.visual_context_text.setHtml(f"<div style='color: #5c2d91; font-size:13px;'>{visual_ctx.replace(chr(10), '<br>')}</div>")
                else:
                    self.visual_context_text.setHtml(
                        f"<div style='background-color: #f6f8fa; border-left: 4px solid #0078d7; padding: 10px; font-size: 13px; font-style: italic; color: #24292e;'>"
                        f"<strong>AI Environment & Mood:</strong><br>{visual_ctx}</div>"
                    )
            else:
                self.visual_context_text.setHtml(
                    "<span style='color: #999999; font-style: italic; font-size: 13px;'>"
                    "No AI-assisted visual scene description has been generated for this room yet. Only chronological timelines are mapped.</span>"
                )

            # 2. Populated Dialogue table
            self.dialogues_table.setRowCount(len(dialogue_lines))
            for idx, (line_id, speaker, text) in enumerate(dialogue_lines):
                id_item = QTableWidgetItem(line_id)
                id_item.setForeground(QColor("#666666"))
                
                spk_item = QTableWidgetItem(speaker)
                if speaker != "Unknown Speaker" and speaker != "Dialogue/Narrator":
                    spk_item.setForeground(QColor("#0078d7"))
                    font = QFont()
                    font.setBold(True)
                    spk_item.setFont(font)
                    
                txt_item = QTableWidgetItem(text)
                
                self.dialogues_table.setItem(idx, 0, id_item)
                self.dialogues_table.setItem(idx, 1, spk_item)
                self.dialogues_table.setItem(idx, 2, txt_item)
                
            self.dialogues_table.resizeColumnsToContents()
            self.dialogues_table.horizontalHeader().setStretchLastSection(True)
            
        except Exception as e:
            log_error(f"Error handling room selection in viewer: {e}")

    @pyqtSlot()
    def _refresh_data(self):
        """Force reload database file and refresh UI lists."""
        self._init_client()
        self._load_wings()
        QMessageBox.information(self, "MemePalace Viewer", "Database records refreshed successfully!")

    def closeEvent(self, event):
        """Clear reference in main window when closed."""
        if hasattr(self.mw, 'mempalace_viewer_dialog'):
            self.mw.mempalace_viewer_dialog = None
        event.accept()

    @pyqtSlot(int, int)
    def _handle_dialogue_double_clicked(self, row, column):
        """Triggered when a dialogue row is double-clicked.
        Parses the Line ID, searches for the matching block and row index in Picoripi,
        selects them, and raises the main window to the front.
        """
        id_item = self.dialogues_table.item(row, 0)
        if not id_item:
            return
        
        line_id = id_item.text().strip()
        if not line_id or line_id == "N/A":
            return

        # Parse line_id of format "{block_label}_Str_{s_idx}"
        if "_Str_" not in line_id:
            return
            
        parts = line_id.split("_Str_")
        if len(parts) < 2:
            return
            
        block_label = "_Str_".join(parts[:-1])
        try:
            s_idx = int(parts[-1])
        except ValueError:
            return

        found_block_idx = -1

        # 1. Search in project_manager
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            for idx, b in enumerate(self.mw.project_manager.project.blocks):
                if b.name == block_label:
                    found_block_idx = idx
                    break

        # 2. Search in data_store.block_names
        if found_block_idx == -1 and hasattr(self.mw, 'data_store') and self.mw.data_store:
            store = self.mw.data_store
            for idx_str, b_desc in store.block_names.items():
                clean_desc = b_desc
                if "Message ID" in b_desc:
                    clean_desc = b_desc.partition("(")[0].strip()
                
                if clean_desc == block_label or idx_str == block_label:
                    try:
                        found_block_idx = int(idx_str)
                        break
                    except ValueError:
                        pass

        # 3. Direct parse if block_label is Block_X
        if found_block_idx == -1 and block_label.startswith("Block_"):
            try:
                found_block_idx = int(block_label.replace("Block_", ""))
            except ValueError:
                pass

        if found_block_idx == -1:
            log_info(f"MemePalaceViewer: Could not find block for label: {block_label}")
            return

        # Try to select the block and string in Picoripi
        try:
            from PyQt6.QtWidgets import QTreeWidgetItemIterator
            from PyQt6.QtCore import QTimer, Qt
            
            # Focus main window
            self.mw.raise_()
            self.mw.activateWindow()

            # Find the tree item corresponding to the found block
            target_item = None
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                if iterator.value().data(0, Qt.ItemDataRole.UserRole) == found_block_idx:
                    target_item = iterator.value()
                    break
                iterator += 1

            if target_item:
                self.mw.block_list_widget.setCurrentItem(target_item)
                # Use a short delay so the main table populates strings before we select the exact line
                QTimer.singleShot(50, lambda: self.mw.list_selection_handler.select_string_by_absolute_index(s_idx))
            else:
                # Fallback if tree item is not found, select it anyway directly
                self.mw.data_store.current_block_idx = found_block_idx
                self.mw.ui_updater.populate_strings_for_block(found_block_idx)
                QTimer.singleShot(50, lambda: self.mw.list_selection_handler.select_string_by_absolute_index(s_idx))

        except Exception as e:
            log_error(f"Error navigating to block/string from MemePalace double click: {e}")
