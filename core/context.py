# core/context.py
from typing import Protocol, Optional, Any, Dict, List, Tuple, Set, TYPE_CHECKING, Type
from PyQt6.QtWidgets import QStatusBar, QWidget, QListWidget, QComboBox, QSpinBox, QPushButton
from PyQt6.QtGui import QAction

if TYPE_CHECKING:
    from core.state_manager import StateManager
    from core.data_store import AppDataStore
    from core.project_manager import ProjectManager
    from core.settings_manager import SettingsManager
    from core.data_state_processor import DataStateProcessor
    from core.undo_manager import UndoManager
    from core.spellchecker_manager import SpellcheckerManager
    from core.saved_translations_manager import SavedTranslationsManager
    from core.filter_query_api import FilterQueryAPI
    from ui.ui_updater import UIUpdater
    from handlers.list_selection_handler import ListSelectionHandler
    from handlers.text_operation_handler import TextOperationHandler
    from handlers.app_action_handler import AppActionHandler
    from handlers.project_action_handler import ProjectActionHandler
    from handlers.issue_scan_handler import IssueScanHandler
    from handlers.search_handler import SearchHandler
    from handlers.string_settings_handler import StringSettingsHandler
    from handlers.translation_handler import TranslationHandler
    from handlers.text_analysis_handler import TextAnalysisHandler
    from handlers.ai_chat_handler import AIChatHandler
    from handlers.bookmark_handler import BookmarkHandler
    from handlers.saved_translations_handler import SavedTranslationsHandler
    from plugins.base_game_rules import BaseGameRules
    from components.editor.line_numbered_text_edit import LineNumberedTextEdit
    from components.custom_list_widget import CustomListWidget
    from components.search_panel import SearchPanelWidget

class UIProvider(Protocol):
    """U i provider implementation."""
    @property
    def statusBar(self) -> Optional[QStatusBar]:
        """Statusbar."""
        ...
    def force_focus(self) -> None:
        """Force focus."""
        ...
    @property
    def preview_text_edit(self) -> 'LineNumberedTextEdit':
        """Preview text edit."""
        ...
    @property
    def original_text_edit(self) -> 'LineNumberedTextEdit':
        """Original text edit."""
        ...
    @property
    def edited_text_edit(self) -> 'LineNumberedTextEdit':
        """Edited text edit."""
        ...
    @property
    def block_list_widget(self) -> 'CustomListWidget':
        """Block list widget."""
        ...
    @property
    def search_panel_widget(self) -> 'SearchPanelWidget':
        """Search panel widget."""
        ...
    @property
    def open_glossary_button(self) -> QPushButton:
        """Open glossary button."""
        ...
    def show_message(self, title: str, text: str, type: str = "info") -> None:
        """Show message."""
        ...
    def ask_yes_no(self, title: str, text: str, default_yes: bool = True) -> bool:
        """Ask yes no."""
        ...
    def show_archive_size_warning(self, archive_rel_path: str, new_size: int, orig_size: int) -> None:
        """Show archive size warning."""
        ...
    def create_progress_tracker(self, title: str, message: str, max_val: int) -> Any:
        """Create progress tracker."""
        ...

class ProjectContext(Protocol):
    """Project context implementation."""
    @property
    def state(self) -> 'StateManager':
        """State."""
        ...
    @property
    def data_store(self) -> 'AppDataStore':
        """Data store."""
        ...
    @property
    def project_manager(self) -> Optional['ProjectManager']:
        """Project manager."""
        ...
    @property
    def settings_manager(self) -> 'SettingsManager':
        """Settings manager."""
        ...
    @property
    def data_processor(self) -> 'DataStateProcessor':
        """Data processor."""
        ...
    @property
    def saved_translations_manager(self) -> 'SavedTranslationsManager':
        """Saved translations manager."""
        ...
    @property
    def ui_updater(self) -> 'UIUpdater':
        """Ui updater."""
        ...
    @property
    def undo_manager(self) -> 'UndoManager':
        """Undo manager."""
        ...
    @property
    def spellchecker_manager(self) -> 'SpellcheckerManager':
        """Spellchecker manager."""
        ...
    @property
    def filter_query_api(self) -> 'FilterQueryAPI':
        """Filter query API."""
        ...
    
    # Handlers
    @property
    def list_selection_handler(self) -> 'ListSelectionHandler':
        """List selection handler."""
        ...
    @property
    def editor_operation_handler(self) -> 'TextOperationHandler':
        """Editor operation handler."""
        ...
    @property
    def app_action_handler(self) -> 'AppActionHandler':
        """App action handler."""
        ...
    @property
    def project_action_handler(self) -> 'ProjectActionHandler':
        """Project action handler."""
        ...
    @property
    def issue_scan_handler(self) -> 'IssueScanHandler':
        """Issue scan handler."""
        ...
    @property
    def search_handler(self) -> 'SearchHandler':
        """Search handler."""
        ...
    @property
    def string_settings_handler(self) -> 'StringSettingsHandler':
        """String settings handler."""
        ...
    @property
    def translation_handler(self) -> 'TranslationHandler':
        """Translation handler."""
        ...
    @property
    def text_analysis_handler(self) -> 'TextAnalysisHandler':
        """Text analysis handler."""
        ...
    @property
    def ai_chat_handler(self) -> 'AIChatHandler':
        """Ai chat handler."""
        ...
    @property
    def bookmark_handler(self) -> 'BookmarkHandler':
        """Bookmark handler."""
        ...
    @property
    def saved_translations_handler(self) -> 'SavedTranslationsHandler':
        """Saved translations handler."""
        ...
    
    @property
    def ui_provider(self) -> UIProvider:
        """Ui provider."""
        ...
    
    # Direct UI access shortcuts (MainWindow properties)
    @property
    def preview_text_edit(self) -> 'LineNumberedTextEdit':
        """Preview text edit."""
        ...
    @property
    def original_text_edit(self) -> 'LineNumberedTextEdit':
        """Original text edit."""
        ...
    @property
    def edited_text_edit(self) -> 'LineNumberedTextEdit':
        """Edited text edit."""
        ...
    @property
    def block_list_widget(self) -> 'CustomListWidget':
        """Block list widget."""
        ...
    @property
    def search_panel_widget(self) -> 'SearchPanelWidget':
        """Search panel widget."""
        ...
    @property
    def open_glossary_button(self) -> QPushButton:
        """Open glossary button."""
        ...
    
    # Data access shortcuts
    @property
    def data(self) -> List[Any]:
        """Data."""
        ...
    @property
    def edited_file_data(self) -> List[Any]:
        """Edited file data."""
        ...
    @property
    def edited_data(self) -> Dict[Tuple[int, int], str]:
        """Edited data."""
        ...
    
    @property
    def current_block_idx(self) -> int:
        """Current block idx."""
        ...
    @property
    def current_string_idx(self) -> int:
        """Current string idx."""
        ...
    
    @property
    def current_game_rules(self) -> Optional['BaseGameRules']:
        """Current game rules."""
        ...
    @property
    def active_game_plugin(self) -> Optional[str]:
        """Active game plugin."""
        ...
    @property
    def block_to_project_file_map(self) -> Dict[int, int]:
        """Block to project file map."""
        ...
    
    @property
    def unsaved_changes(self) -> bool:
        """Unsaved changes."""
        ...
    @unsaved_changes.setter
    def unsaved_changes(self, value: bool) -> None:
        """Unsaved changes."""
        ...

    def update_title(self) -> None:
        """Update the title."""
        ...
    
    # UI actions & settings
    @property
    def autofix_enabled(self) -> Dict[str, bool]:
        """Autofix enabled."""
        ...
    @autofix_enabled.setter
    def autofix_enabled(self, value: Dict[str, bool]) -> None:
        """Autofix enabled."""
        ...
    @property
    def detection_enabled(self) -> Dict[str, bool]:
        """Detection enabled."""
        ...
    @detection_enabled.setter
    def detection_enabled(self, value: Dict[str, bool]) -> None:
        """Detection enabled."""
        ...
    
    @property
    def line_width_warning_threshold_pixels(self) -> int:
        """Line width warning threshold pixels."""
        ...
    @property
    def game_dialog_max_width_pixels(self) -> int:
        """Game dialog max width pixels."""
        ...
    @property
    def show_width_guideline(self) -> bool:
        """Show width guideline."""
        ...
    @property
    def spellchecker_enabled(self) -> bool:
        """Spellchecker enabled."""
        ...
    @property
    def spellchecker_language(self) -> str:
        """Spellchecker language."""
        ...
    
    @property
    def newline_display_symbol(self) -> str:
        """Newline display symbol."""
        ...
    @property
    def newline_color_rgba(self) -> str:
        """Newline color rgba."""
        ...
    @property
    def newline_bold(self) -> bool:
        """Newline bold."""
        ...
    @property
    def newline_italic(self) -> bool:
        """Newline italic."""
        ...
    @property
    def newline_underline(self) -> bool:
        """Newline underline."""
        ...
    @property
    def tag_color_rgba(self) -> str:
        """Tag color rgba."""
        ...
    @property
    def tag_bold(self) -> bool:
        """Tag bold."""
        ...
    @property
    def tag_italic(self) -> bool:
        """Tag italic."""
        ...
    @property
    def tag_underline(self) -> bool:
        """Tag underline."""
        ...
    @property
    def newline_css(self) -> str:
        """Newline css."""
        ...
    @property
    def tag_css(self) -> str:
        """Tag css."""
        ...
    @property
    def space_dot_color_hex(self) -> str:
        """Space dot color hex."""
        ...
    @property
    def preview_wrap_lines(self) -> bool:
        """Preview wrap lines."""
        ...
    @property
    def editors_wrap_lines(self) -> bool:
        """Editors wrap lines."""
        ...
    @property
    def bracket_tag_color_hex(self) -> str:
        """Bracket tag color hex."""
        ...
    
    @property
    def font_combobox(self) -> Optional[QComboBox]:
        """Font combobox."""
        ...
    @property
    def width_spinbox(self) -> Optional[QSpinBox]:
        """Width spinbox."""
        ...
    @property
    def apply_width_button(self) -> Optional[QPushButton]:
        """Apply width button."""
        ...
    @property
    def auto_fix_button(self) -> Optional[QPushButton]:
        """Auto fix button."""
        ...
    @property
    def ai_translate_button(self) -> Optional[QPushButton]:
        """Ai translate button."""
        ...
    @property
    def ai_variation_button(self) -> Optional[QPushButton]:
        """Ai variation button."""
        ...
    
    @property
    def status_label_part1(self) -> Optional[QWidget]:
        """Status label part1."""
        ...
    @property
    def status_label_part2(self) -> Optional[QWidget]:
        """Status label part2."""
        ...
    @property
    def status_label_part3(self) -> Optional[QWidget]:
        """Status label part3."""
        ...
    @property
    def plugin_status_label(self) -> Optional[QWidget]:
        """Plugin status label."""
        ...
    @property
    def statusBar(self) -> Optional[QStatusBar]:
        """Statusbar."""
        ...
    
    @property
    def close_project_action(self) -> Optional[QAction]:
        """Close project action."""
        ...
    
    # Additional properties needed by handlers
    @property
    def prompt_editor_enabled(self) -> bool:
        """Prompt editor enabled."""
        ...
    @property
    def string_metadata(self) -> Dict[Tuple[int, int], Any]:
        """String metadata."""
        ...
    @property
    def current_font_map(self) -> Dict[str, Any]:
        """Current font map."""
        ...
    @property
    def font_map(self) -> Dict[str, Any]:
        """Font map."""
        ...
    @property
    def lines_per_page(self) -> int:
        """Lines per page."""
        ...
    @property
    def default_tag_mappings(self) -> Dict[str, str]:
        """Default tag mappings."""
        ...

    def get_service(self, service_type: Type[Any]) -> Any:
        """Get the service."""
        ...

