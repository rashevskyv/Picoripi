# --- START OF FILE ui/updaters/title_status_bar_updater.py ---
from pathlib import Path
from utils.utils import log_debug
from .base_ui_updater import BaseUIUpdater

class TitleStatusBarUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)

    def update_title(self):
        title = "Picoripi"

        # Check if a project is open
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and hasattr(self.mw.project_manager, 'project') and self.mw.project_manager.project:
            project_name = self.mw.project_manager.project.name
            title += f" - [{project_name}]"
        elif self.mw.data_store.json_path:
            title += f" - [{Path(self.mw.data_store.json_path).name}]"
        else:
            title += " - [No File Open]"

        if self.mw.data_store.unsaved_changes:
            title += " *"
        self.mw.setWindowTitle(title)

    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = Path(self.mw.data_store.json_path).name if self.mw.data_store.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.data_store.json_path if self.mw.data_store.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = Path(self.mw.data_store.edited_json_path).name if self.mw.data_store.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.data_store.edited_json_path if self.mw.data_store.edited_json_path else "Path to changes file")