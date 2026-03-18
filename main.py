# --- START OF FILE main.py ---
import sys
import json
import re
import importlib
import inspect
import argparse
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QLabel, QComboBox, QSpinBox, QPushButton
from PyQt5.QtCore import Qt, QSize, QEvent, QTimer, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QKeyEvent
from typing import Optional, Dict, Tuple, Set

from ui.ui_setup import setup_main_window_ui
from ui.ui_event_filters import MainWindowEventFilter, TextEditEventFilter
from ui.ui_updater import UIUpdater
from ui.updaters.string_settings_updater import StringSettingsUpdater
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.custom_list_widget import CustomListWidget
from components.search_panel import SearchPanelWidget
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET

from handlers.app_action_handler import AppActionHandler
from handlers.project_action_handler import ProjectActionHandler
from handlers.issue_scan_handler import IssueScanHandler
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.search_handler import SearchHandler
from handlers.string_settings_handler import StringSettingsHandler

from handlers.translation_handler import TranslationHandler
from handlers.text_analysis_handler import TextAnalysisHandler
from handlers.ai_chat_handler import AIChatHandler

from core.settings_manager import SettingsManager
from core.data_state_processor import DataStateProcessor
from core.undo_manager import UndoManager
from core.state_manager import StateManager, AppState
from core.data_store import AppDataStore
from core.translation.config import build_default_translation_config
from core.spellchecker_manager import SpellcheckerManager
from core.project_manager import ProjectManager

from plugins.base_game_rules import BaseGameRules

from utils.logging_utils import log_info, log_warning, log_error, log_debug
from utils.hotkey_manager import HotkeyManager
from utils.constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE,
    LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR
)
from utils.utils import ALL_TAGS_PATTERN

from ui.settings_dialog import SettingsDialog
from components.custom_list_item_delegate import CustomListItemDelegate

from ui.main_window.main_window_helper import MainWindowHelper
from ui.main_window.main_window_actions import MainWindowActions
from ui.main_window.main_window_ui_handler import MainWindowUIHandler
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler
from ui.main_window.main_window_event_handler import MainWindowEventHandler
from ui.main_window.main_window_block_handler import MainWindowBlockHandler

from core.context import ProjectContext, UIProvider


class MainWindow(QMainWindow):
    # --- State Properties (Proxy to StateManager) ---
    @property
    def is_adjusting_cursor(self): return self.state.is_active(AppState.ADJUSTING_CURSOR)
    @is_adjusting_cursor.setter
    def is_adjusting_cursor(self, v): self.state.set_active(AppState.ADJUSTING_CURSOR, v)

    @property
    def is_adjusting_selection(self): return self.state.is_active(AppState.ADJUSTING_SELECTION)
    @is_adjusting_selection.setter
    def is_adjusting_selection(self, v): self.state.set_active(AppState.ADJUSTING_SELECTION, v)

    @property
    def is_programmatically_changing_text(self): return self.state.is_active(AppState.PROGRAMMATIC_TEXT_CHANGE)
    @is_programmatically_changing_text.setter
    def is_programmatically_changing_text(self, v): self.state.set_active(AppState.PROGRAMMATIC_TEXT_CHANGE, v)

    @property
    def is_restart_in_progress(self): return self.state.is_active(AppState.RESTART_IN_PROGRESS)
    @is_restart_in_progress.setter
    def is_restart_in_progress(self, v): self.state.set_active(AppState.RESTART_IN_PROGRESS, v)

    @property
    def is_closing(self): return self.state.is_active(AppState.CLOSING)
    @is_closing.setter
    def is_closing(self, v): self.state.set_active(AppState.CLOSING, v)

    @property
    def is_loading_data(self): return self.state.is_active(AppState.LOADING_DATA)
    @is_loading_data.setter
    def is_loading_data(self, v): self.state.set_active(AppState.LOADING_DATA, v)

    @property
    def is_saving_data(self): return self.state.is_active(AppState.SAVING_DATA)
    @is_saving_data.setter
    def is_saving_data(self, v): self.state.set_active(AppState.SAVING_DATA, v)

    @property
    def is_reverting_data(self): return self.state.is_active(AppState.REVERTING_DATA)
    @is_reverting_data.setter
    def is_reverting_data(self, v): self.state.set_active(AppState.REVERTING_DATA, v)

    @property
    def is_reloading_data(self): return self.state.is_active(AppState.RELOADING_DATA)
    @is_reloading_data.setter
    def is_reloading_data(self, v): self.state.set_active(AppState.RELOADING_DATA, v)

    @property
    def is_pasting_block(self): return self.state.is_active(AppState.PASTING_BLOCK)
    @is_pasting_block.setter
    def is_pasting_block(self, v): self.state.set_active(AppState.PASTING_BLOCK, v)

    @property
    def is_undoing_paste(self): return self.state.is_active(AppState.UNDOING_PASTE)
    @is_undoing_paste.setter
    def is_undoing_paste(self, v): self.state.set_active(AppState.UNDOING_PASTE, v)

    @property
    def is_auto_fixing(self): return self.state.is_active(AppState.AUTO_FIXING)
    @is_auto_fixing.setter
    def is_auto_fixing(self, v): self.state.set_active(AppState.AUTO_FIXING, v)


    # --- Data Properties (Proxy to AppDataStore) ---
    @property
    def json_path(self): return self.data_store.json_path
    @json_path.setter
    def json_path(self, v): self.data_store.json_path = v

    @property
    def edited_json_path(self): return self.data_store.edited_json_path
    @edited_json_path.setter
    def edited_json_path(self, v): self.data_store.edited_json_path = v

    @property
    def data(self): return self.data_store.data
    @data.setter
    def data(self, v): self.data_store.data = v

    @property
    def edited_data(self): return self.data_store.edited_data
    @edited_data.setter
    def edited_data(self, v): self.data_store.edited_data = v

    @property
    def edited_file_data(self): return self.data_store.edited_file_data
    @edited_file_data.setter
    def edited_file_data(self, v): self.data_store.edited_file_data = v

    @property
    def block_names(self): return self.data_store.block_names
    @block_names.setter
    def block_names(self, v): self.data_store.block_names = v

    @property
    def current_block_idx(self): return self.data_store.current_block_idx
    @current_block_idx.setter
    def current_block_idx(self, v): self.data_store.current_block_idx = v

    @property
    def current_string_idx(self): return self.data_store.current_string_idx
    @current_string_idx.setter
    def current_string_idx(self, v): self.data_store.current_string_idx = v

    @property
    def selected_string_indices(self): return self.data_store.selected_string_indices
    @selected_string_indices.setter
    def selected_string_indices(self, v): self.data_store.selected_string_indices = v

    @property
    def displayed_string_indices(self): return self.data_store.displayed_string_indices
    @displayed_string_indices.setter
    def displayed_string_indices(self, v): self.data_store.displayed_string_indices = v

    @property
    def current_category_name(self): return self.data_store.current_category_name
    @current_category_name.setter
    def current_category_name(self, v): self.data_store.current_category_name = v

    @property
    def highlight_categorized(self): return self.data_store.highlight_categorized
    @highlight_categorized.setter
    def highlight_categorized(self, v): self.data_store.highlight_categorized = v

    @property
    def hide_categorized(self): return self.data_store.hide_categorized
    @hide_categorized.setter
    def hide_categorized(self, v): self.data_store.hide_categorized = v

    @property
    def unsaved_changes(self): return self.data_store.unsaved_changes
    @unsaved_changes.setter
    def unsaved_changes(self, v): self.data_store.unsaved_changes = v

    @property
    def unsaved_block_indices(self): return self.data_store.unsaved_block_indices
    @unsaved_block_indices.setter
    def unsaved_block_indices(self, v): self.data_store.unsaved_block_indices = v

    @property
    def problems_per_subline(self): return self.data_store.problems_per_subline
    @problems_per_subline.setter
    def problems_per_subline(self, v): self.data_store.problems_per_subline = v

    @property
    def last_selected_block_index(self): return self.data_store.last_selected_block_index
    @last_selected_block_index.setter
    def last_selected_block_index(self, v): self.data_store.last_selected_block_index = v

    @property
    def last_selected_string_index(self): return self.data_store.last_selected_string_index
    @last_selected_string_index.setter
    def last_selected_string_index(self, v): self.data_store.last_selected_string_index = v

    @property
    def ui_provider(self) -> UIProvider:
        return self

    def force_focus(self):
        self.ui_handler.force_focus()

    def __init__(self) -> None:
        super().__init__()
        log_info("Initializing main window...")

        self._init_metadata()
        self._init_state()
        self._init_visual_settings()
        self._init_data_structures()
        self._init_handlers()
        self._init_ui()

    def _init_metadata(self) -> None:
        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        self.general_font_family = GENERAL_APP_FONT_FAMILY
        self.editor_font_family = MONOSPACE_EDITOR_FONT_FAMILY
        self.display_name = "Picoripi"

    def _init_state(self) -> None:
        self.state = StateManager()
        self.data_store = AppDataStore()
        self.project_manager: Optional[ProjectManager] = None
        self.last_cursor_position_in_edited = 0
        self.previous_cursor_pos = 0
        self.last_edited_text_edit_scroll_value_v = 0
        self.last_edited_text_edit_scroll_value_h = 0
        self.last_preview_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_h = 0
        self.initial_load_path = None
        self.initial_edited_load_path = None
        self.window_was_maximized_on_close = False
        self.window_normal_geometry_on_close: Optional[QRect] = None

    def _init_visual_settings(self) -> None:
        # Style Settings
        self.newline_display_symbol = "↵"
        self.newline_color_rgba = "#A020F0"
        self.newline_bold = True
        self.newline_italic = False
        self.newline_underline = False
        self.tag_color_rgba = "#FF8C00"
        self.tag_bold = True
        self.tag_italic = False
        self.tag_underline = False
        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: rgba(128, 128, 128, 128); font-style: italic;"
        self.space_dot_color_hex = "#BBBBBB"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.bracket_tag_color_hex = "#FF8C00"

    def _init_data_structures(self) -> None:
        self.search_history_to_save: List[str] = []
        self.default_tag_mappings: Dict[str, str] = {}
        self.block_color_markers: Dict[str, str] = {}
        self.string_metadata: Dict[str, Any] = {}
        self.default_font_file = ""
        self.autofix_enabled: Dict[str, bool] = {}
        self.detection_enabled: Dict[str, bool] = {}
        self.translation_config = build_default_translation_config()
        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot: Dict[str, Any] = {}
        self.before_paste_block_idx_affected = -1
        self.search_match_block_indices: Set[int] = set()
        self.current_search_results: List[Any] = []
        self.current_search_index = -1
        self.all_font_maps: Dict[str, Any] = {}
        self.font_map: Dict[str, Any] = {}

    def _init_handlers(self) -> None:
        # Core Services
        self.settings_manager = SettingsManager(self)
        
        self.helper = MainWindowHelper(self)
        self.actions = MainWindowActions(self)
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.undo_manager = UndoManager(self)
        
        self.settings_manager.load_settings()
        
        # Actions Handlers
        self.string_settings_updater = StringSettingsUpdater(self, self.data_processor)
        self.spellchecker_manager = SpellcheckerManager(self)
        self.ui_handler = MainWindowUIHandler(self)
        self.plugin_handler = MainWindowPluginHandler(self)
        self.event_handler = MainWindowEventHandler(self)
        self.block_handler = MainWindowBlockHandler(self)

        # Plugin Setup
        self.plugin_handler.load_game_plugin() 
        if self.current_game_rules:
            self.default_tag_mappings = self.current_game_rules.get_default_tag_mappings()

        # Complex Handlers
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater, self.current_game_rules) 
        self.project_action_handler = ProjectActionHandler(self, self.data_processor, self.ui_updater)
        self.issue_scan_handler = IssueScanHandler(self, self.data_processor, self.ui_updater)
        self.search_handler = SearchHandler(self, self.data_processor, self.ui_updater)
        self.string_settings_handler = StringSettingsHandler(self, self.data_processor, self.ui_updater)
        self.translation_handler = TranslationHandler(self, self.data_processor, self.ui_updater)
        self.text_analysis_handler = TextAnalysisHandler(self, self.data_processor, self.ui_updater)
        self.ai_chat_handler = AIChatHandler(self, self.data_processor, self.ui_updater)
        self.hotkey_manager = HotkeyManager(self)

    def _init_ui(self) -> None:
        # UI Attributes (placeholders for setup_main_window_ui)
        self.main_splitter = None
        self.right_splitter = None
        self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None;
        self.save_as_action = None; self.reload_action = None; self.revert_action = None;
        self.reload_tag_mappings_action = None; self.open_settings_action = None;
        self.exit_action = None; self.paste_block_action = None;
        self.undo_typing_action = None; self.redo_typing_action = None;
        self.undo_paste_action = None
        self.rescan_all_tags_action = None
        self.find_action = None
        self.auto_fix_action = None
        self.open_ai_chat_action = None
        self.main_vertical_layout = None
        self.auto_fix_button: Optional[QPushButton] = None 
        self.ai_translate_button: Optional[QPushButton] = None
        self.ai_variation_button: Optional[QPushButton] = None
        self.font_combobox: Optional[QComboBox] = None
        self.width_spinbox: Optional[QSpinBox] = None
        self.apply_width_button: Optional[QPushButton] = None
        
        self.status_label_part1: Optional[QLabel] = None
        self.status_label_part2: Optional[QLabel] = None
        self.status_label_part3: Optional[QLabel] = None
        self.plugin_status_label: Optional[QLabel] = None

        self.current_game_rules: Optional[BaseGameRules] = None 
        self.tag_checker_handler = None 
        self.plugin_actions: Dict[str, Any] = {}

        # Setup 
        setup_main_window_ui(self)
        self.ui_handler.force_focus()
        log_info("UI setup complete.")

        # Set window icon
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            log_info(f"Setting window icon from {icon_path}")
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            log_debug(f"Icon file not found at {icon_path}")

        self.open_glossary_button.clicked.connect(self.translation_handler.show_glossary_dialog)
        self.translation_handler.initialize_glossary_highlighting()

        if self.spellchecker_manager:
            self.spellchecker_manager.reload_glossary_words()

        self.text_analysis_handler.ensure_menu_action()

        log_info("Initializing dynamic UI from plugin...")
        self.plugin_handler.setup_plugin_ui()

        self.search_panel_widget = SearchPanelWidget(self)
        self.main_vertical_layout.insertWidget(0, self.search_panel_widget)
        self.search_panel_widget.setVisible(False)


        self.event_handler.connect_signals()

        self.event_filter = MainWindowEventFilter(self)
        QApplication.instance().installEventFilter(self.event_filter)
        
        self.text_edit_filter = TextEditEventFilter(self)
        self.preview_text_edit.installEventFilter(self.text_edit_filter)
        self.original_text_edit.installEventFilter(self.text_edit_filter)
        self.edited_text_edit.installEventFilter(self.text_edit_filter)


        self.ui_updater.update_plugin_status_label()

        for editor_widget in [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]:
            if editor_widget:
                editor_widget.line_width_warning_threshold_pixels = self.line_width_warning_threshold_pixels
                editor_widget.font_map = self.font_map
                editor_widget.game_dialog_max_width_pixels = self.game_dialog_max_width_pixels
                
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

        self.helper.restore_state_after_settings_load()
        self.ui_handler.apply_font_size()
        self.helper.apply_text_wrap_settings()
        self.string_settings_updater.update_font_combobox()
        self.string_settings_updater.update_string_settings_panel()

        self.helper.rebuild_unsaved_block_indices()

        # Initialize spellchecker state
        log_info("Initializing spellchecker...")
        spellchecker_enabled = getattr(self, 'spellchecker_enabled', False)
        spellchecker_language = getattr(self, 'spellchecker_language', 'uk')
        if self.spellchecker_manager.hunspell:
            log_info(f"Spellchecker dictionary language: {self.spellchecker_manager.language}")
        self.spellchecker_manager.set_enabled(spellchecker_enabled)
        log_info(f"Spellchecker initialization complete. Manager enabled state: {self.spellchecker_manager.enabled}")

        # Update recent projects menu
        self.project_action_handler._update_recent_projects_menu()

        self.hotkey_manager = HotkeyManager(self)
        self.hotkey_manager.register()

        QTimer.singleShot(100, self.ui_handler.force_focus)

        self.ui_updater.update_title()
        log_info("Main window initialization complete.")
    
    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    def load_game_plugin(self):
        """Proxy to plugin_handler for backward compatibility in handlers."""
        self.plugin_handler.load_game_plugin()

    def nativeEvent(self, eventType, message):
        if hasattr(self, 'hotkey_manager'):
            handled, result = self.hotkey_manager.handle_native_event(eventType, message)
            if handled:
                return True, result
        return super().nativeEvent(eventType, message)

    # --- Settings Properties ---
    @property
    def current_font_size(self): return self.settings_manager.get('font_size', DEFAULT_APP_FONT_SIZE)
    @current_font_size.setter
    def current_font_size(self, val): self.settings_manager.set('font_size', val)

    @property
    def active_game_plugin(self): return self.settings_manager.get('active_game_plugin', "zelda_mc")
    @active_game_plugin.setter
    def active_game_plugin(self, val): self.settings_manager.set('active_game_plugin', val)

    @property
    def show_multiple_spaces_as_dots(self): return self.settings_manager.get('show_multiple_spaces_as_dots', True)
    @show_multiple_spaces_as_dots.setter
    def show_multiple_spaces_as_dots(self, val): self.settings_manager.set('show_multiple_spaces_as_dots', val)

    @property
    def theme(self): return self.settings_manager.get('theme', "auto")
    @theme.setter
    def theme(self, val): self.settings_manager.set('theme', val)

    @property
    def restore_unsaved_on_startup(self): return self.settings_manager.get('restore_unsaved_on_startup', False)
    @restore_unsaved_on_startup.setter
    def restore_unsaved_on_startup(self, val): self.settings_manager.set('restore_unsaved_on_startup', val)

    @property
    def game_dialog_max_width_pixels(self): return self.settings_manager.get('game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
    @game_dialog_max_width_pixels.setter
    def game_dialog_max_width_pixels(self, val): self.settings_manager.set('game_dialog_max_width_pixels', val)

    @property
    def line_width_warning_threshold_pixels(self): return self.settings_manager.get('line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
    @line_width_warning_threshold_pixels.setter
    def line_width_warning_threshold_pixels(self, val): self.settings_manager.set('line_width_warning_threshold_pixels', val)

    @property
    def tree_font_size(self): return self.settings_manager.get('tree_font_size', self.current_font_size)
    @tree_font_size.setter
    def tree_font_size(self, val): self.settings_manager.set('tree_font_size', val)

    @property
    def preview_font_size(self): return self.settings_manager.get('preview_font_size', self.current_font_size)
    @preview_font_size.setter
    def preview_font_size(self, val): self.settings_manager.set('preview_font_size', val)

    @property
    def editors_font_size(self): return self.settings_manager.get('editors_font_size', self.current_font_size)
    @editors_font_size.setter
    def editors_font_size(self, val): self.settings_manager.set('editors_font_size', val)


    def handle_zoom(self, delta: int, target: str = 'all'):
        """Handle zooming in/out by adjusting font size and updating UI."""
        # delta usually comes from wheel event as 120 (one notch)
        step = 1 if delta > 0 else -1
        
        updated = False
        if target == 'tree':
            old = self.tree_font_size
            new = max(5, min(72, old + step))
            if new != old:
                self.tree_font_size = new
                updated = True
        elif target == 'preview':
            old = self.preview_font_size
            new = max(5, min(72, old + step))
            if new != old:
                self.preview_font_size = new
                updated = True
        elif target == 'editors':
            old = self.editors_font_size
            new = max(5, min(72, old + step))
            if new != old:
                self.editors_font_size = new
                updated = True
        else: # 'all' - for backward compatibility or global zoom if needed
            old = self.current_font_size
            new = max(5, min(72, old + step))
            if new != old:
                self.current_font_size = new
                # Also update independents to match? 
                # For now let's just update the target specifically.
                updated = True
        
        if updated:
            self.ui_handler.apply_font_size(fast=True, target=target)


    def closeEvent(self, event):
        self.event_handler.closeEvent(event)

    def build_glossary_with_ai(self, block_idx=None, category_name: Optional[str] = None):
        log_info(f"Build Glossary with AI action triggered. Category: {category_name}")
        from handlers.translation.glossary_builder_handler import GlossaryBuilderHandler

        target_block_idx = block_idx if block_idx is not None else self.current_block_idx

        if target_block_idx == -1:
            QMessageBox.information(self, "Build Glossary", "Please select a block first.")
            return
        
        handler = GlossaryBuilderHandler(self)
        handler.build_glossary_for_block(target_block_idx, category_name)


def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log_error(f"Uncaught exception: {exc_type.__name__}: {exc_value}", exc_info=(exc_type, exc_value, exc_traceback), category="general")

if __name__ == '__main__':
    if sys.platform == 'win32':
        import ctypes
        # Set AppUserModelID to ensure the taskbar icon is displayed correctly on Windows
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rashevskyv.picoripi.v1")
    
    sys.excepthook = global_exception_handler
    log_info("================= Application Start =================")
    app = QApplication(sys.argv)
    
    app_icon_path = Path("assets/icon.ico")
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))
    
    temp_settings = {}
    try:
        with open("settings.json", 'r', encoding='utf-8') as f:
            temp_settings = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"Error reading settings.json for theme: {e}", exc_info=True)
        
    theme_to_apply = temp_settings.get("theme", "auto")
    MainWindowUIHandler.apply_theme(app, theme_to_apply)

    try:
        window = MainWindow()
        window.show()
    except Exception as e:
        log_error(f"CRITICAL ERROR during MainWindow initialization: {e}", exc_info=True)
        sys.exit(1)
    log_info("Starting Qt event loop...", category="lifecycle")
    exit_code = app.exec_()
    log_info(f"Qt event loop finished with exit code: {exit_code}", category="lifecycle")
    log_info("================= Application End =================")
    sys.exit(exit_code)