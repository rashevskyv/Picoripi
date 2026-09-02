import sys
import json
import importlib
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QLabel, QComboBox, QSpinBox, QPushButton
from PyQt6.QtCore import Qt, QRect, qInstallMessageHandler
# Monkeypatch Qt item roles for backwards compatibility
Qt.EditRole = Qt.ItemDataRole.EditRole
Qt.DisplayRole = Qt.ItemDataRole.DisplayRole
Qt.UserRole = Qt.ItemDataRole.UserRole
Qt.ToolTipRole = Qt.ItemDataRole.ToolTipRole
Qt.BackgroundRole = Qt.ItemDataRole.BackgroundRole
Qt.ForegroundRole = Qt.ItemDataRole.ForegroundRole
Qt.CheckStateRole = Qt.ItemDataRole.CheckStateRole
Qt.FontRole = Qt.ItemDataRole.FontRole
Qt.SizeHintRole = Qt.ItemDataRole.SizeHintRole
from PyQt6.QtGui import QIcon, QKeyEvent, QShowEvent
from typing import Optional, Dict, Set, Any, List

from ui.ui_setup import setup_main_window_ui
from ui.ui_event_filters import MainWindowEventFilter, TextEditEventFilter
from ui.ui_updater import UIUpdater
from ui.updaters.string_settings_updater import StringSettingsUpdater
from components.search_panel import SearchPanelWidget

from handlers.app_action_handler import AppActionHandler
from handlers.project_action_handler import ProjectActionHandler
from handlers.virtual_folder_handler import VirtualFolderHandler
from handlers.issue_scan_handler import IssueScanHandler
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.search_handler import SearchHandler
from handlers.string_settings_handler import StringSettingsHandler

from handlers.translation_handler import TranslationHandler
from handlers.text_analysis_handler import TextAnalysisHandler
from handlers.ai_chat_handler import AIChatHandler
from handlers.bookmark_handler import BookmarkHandler
from handlers.saved_translations_handler import SavedTranslationsHandler
from handlers.speaker_handler import SpeakerHandler
from handlers.category_handler import CategoryHandler

from core.settings_manager import SettingsManager
from core.data_state_processor import DataStateProcessor
from core.undo_manager import UndoManager
from core.state_manager import StateManager, AppState
from utils.constants import SETTINGS_FILE_PATH
from core.data_store import AppDataStore
from core.translation.config import build_default_translation_config
from core.spellchecker_manager import SpellcheckerManager
from core.project_manager import ProjectManager
from core.saved_translations_manager import SavedTranslationsManager
from core.filter_query_api import FilterQueryAPI

from plugins.base_game_rules import BaseGameRules

from utils.logging_utils import log_info, log_warning, log_error, log_debug
from utils.hotkey_manager import HotkeyManager
from utils.constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE
)

from components.startup_splash import StartupSplash

from ui.main_window.main_window_helper import MainWindowHelper
from ui.main_window.main_window_actions import MainWindowActions
from ui.main_window.main_window_ui_handler import MainWindowUIHandler
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler
from ui.main_window.main_window_event_handler import MainWindowEventHandler
from ui.main_window.main_window_block_handler import MainWindowBlockHandler

from core.context import UIProvider
from core.i18n import tr


class StateProperty:
    def __init__(self, state_enum: AppState):
        self.state_enum = state_enum

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.state.is_active(self.state_enum)

    def __set__(self, instance, value):
        instance.state.set_active(self.state_enum, value)


class SettingsProperty:
    def __init__(self, key: str, default: Any):
        self.key = key
        self.default = default

    def __get__(self, instance, owner):
        if instance is None:
            return self
        val = instance.settings_manager.get(self.key, None)
        if val is None:
            if callable(self.default):
                return self.default(instance)
            return self.default
        return val

    def __set__(self, instance, value):
        instance.settings_manager.set(self.key, value)


class MainWindow(QMainWindow):
    # --- State Properties (Proxy to StateManager via Descriptors) ---
    is_adjusting_cursor = StateProperty(AppState.ADJUSTING_CURSOR)
    is_adjusting_selection = StateProperty(AppState.ADJUSTING_SELECTION)
    is_programmatically_changing_text = StateProperty(AppState.PROGRAMMATIC_TEXT_CHANGE)
    is_restart_in_progress = StateProperty(AppState.RESTART_IN_PROGRESS)
    is_closing = StateProperty(AppState.CLOSING)
    is_loading_data = StateProperty(AppState.LOADING_DATA)
    is_saving_data = StateProperty(AppState.SAVING_DATA)
    is_reverting_data = StateProperty(AppState.REVERTING_DATA)
    is_reloading_data = StateProperty(AppState.RELOADING_DATA)
    is_pasting_block = StateProperty(AppState.PASTING_BLOCK)
    is_undoing_paste = StateProperty(AppState.UNDOING_PASTE)
    is_auto_fixing = StateProperty(AppState.AUTO_FIXING)



    @property
    def ui_provider(self) -> UIProvider:
        return self

    def force_focus(self):
        self.ui_handler.force_focus()

    def __init__(self, startup_splash: Optional[StartupSplash] = None) -> None:
        super().__init__()
        self._startup_splash = startup_splash
        self._startup_loading_pending = False
        log_info("Initializing main window...")

        self.report_startup_progress(8, tr("Initializing application state…"))
        self._init_metadata()
        self._init_state()
        self._init_visual_settings()
        self.report_startup_progress(12, tr("Loading settings and fonts…"))
        self._init_data_structures()
        self._init_handlers()
        self.report_startup_progress(42, tr("Building the workspace…"))
        self._init_ui()

    def report_startup_progress(self, value: int, message: str) -> None:
        """Update the early startup UI when the application is still loading."""
        splash = getattr(self, '_startup_splash', None)
        if splash is not None:
            splash.update_progress(value, message)

    def finish_startup_loading(self) -> None:
        """Close the startup UI once the main window has usable project data."""
        self._startup_loading_pending = False
        splash = getattr(self, '_startup_splash', None)
        if splash is None:
            if not self.isVisible():
                self.show()
            return
        splash.update_progress(100, "Ready")
        self.show()
        splash.close()
        splash.deleteLater()
        self._startup_splash = None
        self.raise_()
        self.activateWindow()

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
        self.current_game_rules: Optional[BaseGameRules] = None
        self.tag_checker_handler = None
        self.plugin_actions: Dict[str, Any] = {}
        self.is_testing = 'pytest' in sys.modules
        self.glossary_builder_handler = None

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
        self.filter_query_api = FilterQueryAPI(self)

        self.helper = MainWindowHelper(self)
        self.actions = MainWindowActions(self)
        self.data_processor = DataStateProcessor(self)
        self.saved_translations_manager = SavedTranslationsManager(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.undo_manager = UndoManager(self)

        self.report_startup_progress(15, tr("Reading application settings…"))
        self.settings_manager.load_settings()
        from core.i18n import init as init_i18n
        init_i18n(self.settings_manager.get("ui_language", "en"))

        # Actions Handlers
        self.string_settings_updater = StringSettingsUpdater(self, self.data_processor)
        self.spellchecker_manager = SpellcheckerManager(self)
        self.ui_handler = MainWindowUIHandler(self)
        self.plugin_handler = MainWindowPluginHandler(self)
        self.event_handler = MainWindowEventHandler(self)
        self.block_handler = MainWindowBlockHandler(self)

        # Plugin Setup
        self.report_startup_progress(32, tr("Loading game plugin…"))
        self.plugin_handler.load_game_plugin()

        # Merge autofix_enabled and detection_enabled defaults from the plugin if they are empty
        if self.current_game_rules:
            plugin_defaults_autofix = {}
            plugin_defaults_detection = {}
            plugin_name = self.active_game_plugin
            if plugin_name:
                try:
                    config_module = importlib.import_module(f"plugins.{plugin_name}.config")
                    plugin_defaults_autofix = getattr(config_module, 'DEFAULT_AUTOFIX_SETTINGS', {})
                    plugin_defaults_detection = getattr(config_module, 'DEFAULT_DETECTION_SETTINGS', {})
                except Exception:
                    pass

            if not self.autofix_enabled and plugin_defaults_autofix:
                self.autofix_enabled = plugin_defaults_autofix.copy()
            if not self.detection_enabled and plugin_defaults_detection:
                self.detection_enabled = plugin_defaults_detection.copy()

        # Complex Handlers
        self.virtual_folder_handler = VirtualFolderHandler(self, self.data_processor, self.ui_updater)
        self.speaker_handler = SpeakerHandler(self, self.data_processor, self.ui_updater)
        self.category_handler = CategoryHandler(self, self.data_processor, self.ui_updater)
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
        self.bookmark_handler = BookmarkHandler(self, self.data_processor, self.ui_updater)
        self.saved_translations_handler = SavedTranslationsHandler(self, self.data_processor, self.ui_updater)

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
        self.recalculate_widths_action = None
        self.find_action = None
        self.advanced_search_action = None
        self.auto_fix_action = None
        self.open_ai_chat_action = None
        self.restore_translation_button = None
        self.save_translated_action = None
        self.restore_translated_action = None
        self.export_translations_action = None
        self.export_original_action = None
        self.import_translations_action = None
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

        # Setup
        self.report_startup_progress(45, tr("Creating editors and toolbars…"))
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
        self.report_startup_progress(52, tr("Preparing plugin tools…"))
        self.plugin_handler.setup_plugin_ui()
        self.plugin_handler.update_warnings_filter_button()

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
                editor_widget.show_width_guideline = self.show_width_guideline

                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

        self.ui_handler.apply_font_size()
        self.report_startup_progress(58, tr("Restoring the previous workspace…"))
        self.helper.restore_state_after_settings_load()
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

        has_project = bool(self.project_manager and self.project_manager.project)
        has_file = bool(self.data_store.json_path)

        if has_project:
            self.project_action_handler._set_project_actions_enabled(True)
        elif has_file:
            self.project_action_handler._set_project_actions_enabled(False)
            if hasattr(self, 'close_project_action') and self.close_project_action:
                self.close_project_action.setEnabled(True)
                self.close_project_action.setToolTip(tr('Close the current project or file'))
        else:
            self.project_action_handler._set_project_actions_enabled(False)

        current_block = self.data_store.current_block_idx
        self.list_selection_handler._update_block_toolbar_button_states(current_block)

        if hasattr(self, 'bookmark_handler'):
            self.bookmark_handler.update_bookmarks_menu()

        self.ui_updater.update_title()
        self.ui_updater.update_preview_visibility()
        log_info("Main window initialization complete.")

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if hasattr(self, 'hotkey_manager') and not getattr(self.hotkey_manager, '_registered', False):
            try:
                self.hotkey_manager.register()
            except Exception as e:
                log_error(f"Error registering hotkeys in showEvent: {e}", exc_info=True)



    def change_ui_language(self, code: str) -> None:
        """Persist the Language-menu choice. The new catalog loads on the next start."""
        from core.i18n import available_languages, current_language, tr as _tr
        if code == current_language():
            return
        if code not in available_languages():
            return
        self.ui_language = code
        if hasattr(self, "settings_manager"):
            self.settings_manager.set("ui_language", code)
            self.settings_manager.save_settings()
        for other, action in getattr(self, "language_actions", {}).items():
            action.setChecked(other == code)
        QMessageBox.information(
            self,
            _tr("Language"),
            _tr("A restart is required to apply the new interface language."),
        )

    def load_game_plugin(self):
        """Proxy to plugin_handler for backward compatibility in handlers."""
        self.plugin_handler.load_game_plugin()
        # Reload plugin settings to match the new active_game_plugin
        if hasattr(self, 'settings_manager'):
            self.settings_manager.plugin_settings.load(self.settings_manager._settings)

    def nativeEvent(self, eventType, message):
        if hasattr(self, 'hotkey_manager'):
            handled, result = self.hotkey_manager.handle_native_event(eventType, message)
            if handled:
                return True, result
        return False, 0

    # --- Settings Properties (Proxy to SettingsManager via Descriptors) ---
    current_font_size = SettingsProperty('font_size', DEFAULT_APP_FONT_SIZE)
    active_game_plugin = SettingsProperty('active_game_plugin', "zelda_mc")
    ui_language = SettingsProperty('ui_language', "en")
    show_multiple_spaces_as_dots = SettingsProperty('show_multiple_spaces_as_dots', True)
    theme = SettingsProperty('theme', "auto")
    restore_unsaved_on_startup = SettingsProperty('restore_unsaved_on_startup', False)
    game_dialog_max_width_pixels = SettingsProperty('game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
    line_width_warning_threshold_pixels = SettingsProperty('line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
    show_width_guideline = SettingsProperty('show_width_guideline', True)
    show_archive_size_warnings = SettingsProperty('show_archive_size_warnings', True)
    tree_font_size = SettingsProperty('tree_font_size', lambda inst: inst.current_font_size)
    preview_font_size = SettingsProperty('preview_font_size', lambda inst: inst.current_font_size)
    editors_font_size = SettingsProperty('editors_font_size', lambda inst: inst.current_font_size)
    tooltip_font_size = SettingsProperty('tooltip_font_size', 11)
    external_script_path = SettingsProperty('external_script_path', "")
    last_advanced_search_query = SettingsProperty('last_advanced_search_query', "")

    @property
    def main_splitter_state(self) -> Optional[str]:
        if hasattr(self, 'main_splitter') and self.main_splitter is not None:
            import base64
            return base64.b64encode(self.main_splitter.saveState().data()).decode('ascii')
        return None

    @main_splitter_state.setter
    def main_splitter_state(self, val: Optional[str]) -> None:
        if hasattr(self, 'main_splitter') and self.main_splitter is not None and val:
            import base64
            try:
                self.main_splitter.restoreState(base64.b64decode(val.encode('ascii')))
            except Exception as e:
                log_warning(f"Failed to restore main_splitter_state: {e}")

    @property
    def right_splitter_state(self) -> Optional[str]:
        if hasattr(self, 'right_splitter') and self.right_splitter is not None:
            import base64
            return base64.b64encode(self.right_splitter.saveState().data()).decode('ascii')
        return None

    @right_splitter_state.setter
    def right_splitter_state(self, val: Optional[str]) -> None:
        if hasattr(self, 'right_splitter') and self.right_splitter is not None and val:
            import base64
            try:
                self.right_splitter.restoreState(base64.b64decode(val.encode('ascii')))
            except Exception as e:
                log_warning(f"Failed to restore right_splitter_state: {e}")

    @property
    def bottom_right_splitter_state(self) -> Optional[str]:
        if hasattr(self, 'bottom_right_splitter') and self.bottom_right_splitter is not None:
            import base64
            return base64.b64encode(self.bottom_right_splitter.saveState().data()).decode('ascii')
        return None

    @bottom_right_splitter_state.setter
    def bottom_right_splitter_state(self, val: Optional[str]) -> None:
        if hasattr(self, 'bottom_right_splitter') and self.bottom_right_splitter is not None and val:
            import base64
            try:
                self.bottom_right_splitter.restoreState(base64.b64decode(val.encode('ascii')))
            except Exception as e:
                log_warning(f"Failed to restore bottom_right_splitter_state: {e}")

    @property
    def editor_preview_splitter_state(self) -> Optional[str]:
        if hasattr(self, 'editor_preview_splitter') and self.editor_preview_splitter is not None:
            import base64
            return base64.b64encode(self.editor_preview_splitter.saveState().data()).decode('ascii')
        return None

    @editor_preview_splitter_state.setter
    def editor_preview_splitter_state(self, val: Optional[str]) -> None:
        if hasattr(self, 'editor_preview_splitter') and self.editor_preview_splitter is not None and val:
            import base64
            try:
                self.editor_preview_splitter.restoreState(base64.b64decode(val.encode('ascii')))
            except Exception as e:
                log_warning(f"Failed to restore editor_preview_splitter_state: {e}")



    def handle_zoom(self, delta: int, target: str = 'all'):
        """Handle zooming in/out by adjusting font size and updating UI."""
        # delta usually comes from wheel event as 120 (one notch)
        step = 1 if delta > 0 else -1

        targets = {
            'tree': 'tree_font_size',
            'preview': 'preview_font_size',
            'editors': 'editors_font_size',
            'all': 'current_font_size'
        }

        attr = targets.get(target, 'current_font_size')
        old = getattr(self, attr)
        new = max(5, min(72, old + step))
        if new != old:
            setattr(self, attr, new)
            self.ui_handler.apply_font_size(fast=True, target=target)


    def closeEvent(self, event):
        self.event_handler.closeEvent(event)

    def build_glossary_with_ai(self, block_idx=None, category_name: Optional[str] = None):
        log_info(f"Build Glossary with AI action triggered. Category: {category_name}")
        from handlers.translation.glossary_builder_handler import GlossaryBuilderHandler

        target_block_idx = block_idx if block_idx is not None else self.data_store.current_block_idx

        if target_block_idx == -1:
            QMessageBox.information(self, tr('Build Glossary'), tr('Please select a block first.'))
            return

        self.glossary_builder_handler = GlossaryBuilderHandler(self)
        self.glossary_builder_handler.build_glossary_for_block(target_block_idx, category_name)

    def show_message(self, title: str, text: str, type: str = "info") -> None:
        from PyQt6.QtWidgets import QMessageBox
        if type == "error":
            QMessageBox.critical(self, title, text)
        elif type == "warning":
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.information(self, title, text)

    def ask_yes_no(self, title: str, text: str, default_yes: bool = True) -> bool:
        from PyQt6.QtWidgets import QMessageBox
        default_button = QMessageBox.StandardButton.Yes if default_yes else QMessageBox.StandardButton.No
        reply = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default_button
        )
        return reply == QMessageBox.StandardButton.Yes

    def show_archive_size_warning(self, archive_rel_path: str, new_size: int, orig_size: int) -> None:
        if not getattr(self, 'show_archive_size_warnings', True):
            return
        from PyQt6.QtWidgets import QMessageBox, QCheckBox
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(tr('Archive Size Warning'))
        msg_box.setText(
            f"The packed archive '{archive_rel_path}' size ({new_size} bytes) "
            f"exceeds the original archive size ({orig_size} bytes).\n\n"
            f"This may lead to game crashes, text truncation, or corruption when importing the file into the ROM.\n\n"
            f"Please shorten your translation strings in this archive to reduce its size."
        )
        cb = QCheckBox(tr('Do not show this warning in the future'), msg_box)
        msg_box.setCheckBox(cb)
        msg_box.exec()
        if cb.isChecked():
            self.show_archive_size_warnings = False
            self.settings_manager.save_settings()

    def create_progress_tracker(self, title: str, message: str, max_val: int) -> Any:
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        class UIProgressTracker:
            def __init__(self, parent, title_str, msg_str, val_max):
                self.dialog = QProgressDialog(msg_str, None, 0, val_max, parent)
                self.dialog.setCancelButton(None)
                self.dialog.setWindowTitle(title_str)
                self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.dialog.setMinimumDuration(500)
                self.dialog.setValue(0)

            def set_value(self, val: int):
                self.dialog.setValue(val)
                self.dialog.repaint()

            def was_canceled(self) -> bool:
                return self.dialog.wasCanceled()

        return UIProgressTracker(self, title, message, max_val)


def qt_message_handler(mode, context, message):
    """Filter out known annoying warnings from Qt's message logging."""
    if "GetDesignGlyphMetrics failed" in message:
        return
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log_error(f"Uncaught exception: {exc_type.__name__}: {exc_value}", exc_info=(exc_type, exc_value, exc_traceback), category="general")

if __name__ == '__main__':
    qInstallMessageHandler(qt_message_handler)
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

    # Migrate old settings file if it exists
    try:
        import os
        import shutil
        old_local_settings = "settings.json"
        if os.path.exists(old_local_settings):
            if not os.path.exists(SETTINGS_FILE_PATH):
                os.makedirs(os.path.dirname(SETTINGS_FILE_PATH), exist_ok=True)
                shutil.copy2(old_local_settings, SETTINGS_FILE_PATH)
                log_info(f"Successfully migrated settings from {old_local_settings} to {SETTINGS_FILE_PATH}")
            else:
                log_info(f"Settings file already exists in home directory. Skipping migration of local {old_local_settings}.")

            # Rename old local settings file to prevent repeated checks
            migrated_old_path = old_local_settings + ".migrated"
            try:
                if os.path.exists(migrated_old_path):
                    os.remove(migrated_old_path)
                os.rename(old_local_settings, migrated_old_path)
            except Exception as rename_err:
                log_warning(f"Could not rename old settings file: {rename_err}")
    except Exception as e:
        log_error(f"Error migrating settings: {e}", exc_info=True)

    temp_settings = {}
    try:
        with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
            temp_settings = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"Error reading {SETTINGS_FILE_PATH} for theme: {e}", exc_info=True)

    theme_to_apply = temp_settings.get("theme", "auto")
    MainWindowUIHandler.apply_theme(app, theme_to_apply)

    try:
        splash = StartupSplash()
        splash.update_progress(3, "Starting Picoripi…")
        splash.show_centered()
        window = MainWindow(startup_splash=splash)
        if not window._startup_loading_pending:
            window.finish_startup_loading()
    except Exception as e:
        log_error(f"CRITICAL ERROR during MainWindow initialization: {e}", exc_info=True)
        sys.exit(1)
    log_info("Starting Qt event loop...", category="lifecycle")
    exit_code = app.exec()
    log_info(f"Qt event loop finished with exit code: {exit_code}", category="lifecycle")
    log_info("================= Application End =================")
    sys.exit(exit_code)
