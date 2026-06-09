from __future__ import annotations
from typing import TYPE_CHECKING
import sys
import importlib
import traceback
from PyQt6.QtWidgets import QMenu, QMessageBox
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from utils.logging_utils import log_info, log_error
from plugins.base_game_rules import BaseGameRules

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowPluginHandler:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window

    def setup_plugin_ui(self):
        if not self.mw.current_game_rules:
            return
            
        self.mw.tag_checker_handler = self.mw.current_game_rules.get_tag_checker_handler()
        if self.mw.tag_checker_handler:
            log_info(f"TagCheckerHandler of type {type(self.mw.tag_checker_handler).__name__} was provided by the plugin.")

        plugin_actions_data = self.mw.current_game_rules.get_plugin_actions()
        for action_data in plugin_actions_data:
            action_name = action_data.get('name')
            if not action_name: continue
            
            action = QAction(action_data.get('text', action_name), self.mw)
            if 'tooltip' in action_data: action.setToolTip(action_data['tooltip'])
            if 'shortcut' in action_data: action.setShortcut(QKeySequence(action_data['shortcut']))
            if 'handler' in action_data: action.triggered.connect(action_data['handler'])
            
            self.mw.plugin_actions[action_name] = action

            if action_data.get('menu'):
                menu_name = action_data.get('menu')
                target_menu = self.mw.menuBar().findChild(QMenu, f"&{menu_name}")
                if not target_menu:
                    target_menu = self.mw.menuBar().addMenu(f"&{menu_name}")
                target_menu.addAction(action)

            if action_data.get('toolbar'):
                if hasattr(self.mw, 'main_toolbar'):
                    self.mw.main_toolbar.addAction(action)

    def load_game_plugin(self):
        if not self.mw.active_game_plugin:
            log_info("No active game plugin specified. Loading base game rules.")
            self._load_fallback_rules()
            return

        log_info(f"Attempting to load plugin: '{self.mw.active_game_plugin}'")

        try:
            module_path = f"plugins.{self.mw.active_game_plugin}.rules"
            if module_path in sys.modules:
                del sys.modules[module_path]
                # Force reload of related modules to ensure clean state
                related_modules = [
                    f"plugins.{self.mw.active_game_plugin}.config",
                    f"plugins.{self.mw.active_game_plugin}.tag_checker_handler",
                    f"plugins.{self.mw.active_game_plugin}.tag_manager",
                    f"plugins.{self.mw.active_game_plugin}.problem_analyzer",
                    f"plugins.{self.mw.active_game_plugin}.text_fixer",
                    f"plugins.{self.mw.active_game_plugin}.tag_logic"
                ]
                for mod in related_modules:
                    if mod in sys.modules:
                        del sys.modules[mod]

            game_rules_module = importlib.import_module(module_path)
            
            if hasattr(game_rules_module, 'GameRules') and issubclass(getattr(game_rules_module, 'GameRules'), BaseGameRules):
                GameRulesClass = getattr(game_rules_module, 'GameRules')
                self.mw.current_game_rules = GameRulesClass(main_window_ref=self.mw)
                log_info(f"Successfully loaded and instantiated game rules: {GameRulesClass.__name__}")
                
                # Load default tag mappings and merge with custom aliases
                self.mw.default_tag_mappings = self.mw.current_game_rules.get_default_tag_mappings() or {}
                self._load_custom_aliases()
            else:
                error_msg = f"Class 'GameRules' not found or not a subclass of BaseGameRules in module {module_path}"
                log_error(error_msg)
                self._load_fallback_rules(error_msg)

        except ImportError as e:
            error_msg = f"Could not import game plugin module {module_path}:\n{e}\n\n{traceback.format_exc()}"
            log_error(error_msg)
            self._load_fallback_rules(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error loading game plugin {module_path}:\n{e}\n\n{traceback.format_exc()}"
            log_error(error_msg, exc_info=True)
            self._load_fallback_rules(error_msg)
            
        if hasattr(self.mw, 'translation_handler'):
            self.mw.translation_handler.initialize_glossary_highlighting()

    def _load_custom_aliases(self):
        if not self.mw.active_game_plugin:
            return
        from pathlib import Path
        import json
        aliases_path = Path("plugins") / self.mw.active_game_plugin / "aliases.json"
        if aliases_path.exists():
            try:
                with open(aliases_path, 'r', encoding='utf-8') as f:
                    custom_aliases = json.load(f)
                if isinstance(custom_aliases, dict):
                    if not hasattr(self.mw, 'default_tag_mappings') or self.mw.default_tag_mappings is None:
                        self.mw.default_tag_mappings = {}
                    self.mw.default_tag_mappings.update(custom_aliases)
                    log_info(f"Loaded {len(custom_aliases)} custom aliases from {aliases_path}")
            except Exception as e:
                log_error(f"Failed to load custom aliases from {aliases_path}: {e}")

    def _load_fallback_rules(self, error_message: str = None):
        log_info("Loading fallback game rules.")
        
        # Show error to user so they know why settings are missing
        if error_message:
            QMessageBox.critical(self.mw, "Plugin Load Error", 
                                 f"Failed to load plugin '{self.mw.active_game_plugin}'.\n"
                                 "Falling back to base rules.\n\n"
                                 f"Error details:\n{error_message}")

        try:
            from plugins.base_game_rules import BaseGameRules 
            self.mw.current_game_rules = BaseGameRules(main_window_ref=self.mw)
            log_info("Loaded fallback BaseGameRules.")
            self.mw.default_tag_mappings = self.mw.current_game_rules.get_default_tag_mappings() or {}
            self._load_custom_aliases()
        except Exception as e:
            log_error(f"CRITICAL ERROR: Could not load fallback game rules: {e}", exc_info=True)
            self.mw.current_game_rules = None

    def trigger_check_tags_action(self):
        if self.mw.tag_checker_handler:
            self.mw.tag_checker_handler.start_or_continue_check()
