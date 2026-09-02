"""Compatibility shim: remaining builder logic lives in ui.mempalace.* mixins."""
from __future__ import annotations

import os
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt

from core.mempalace_worker import MemePalaceChapterAIAnalyzerWorker
from core.i18n import tr

from ui.mempalace.mempalace_ui import MemePalaceBuilderUiMixin
from ui.mempalace.mempalace_pipeline import MemePalacePipelineMixin
from ui.mempalace.hierarchy_mixin import MemePalaceHierarchyMixin
from ui.mempalace.dialogue_mixin import MemePalaceDialogueMixin
from ui.mempalace.analysis_mixin import MemePalaceAnalysisMixin
from ui.mempalace.session_mixin import MemePalaceSessionMixin
from ui.mempalace import analysis_mixin as _analysis_mixin
from ui.mempalace.constants import (
    _HIERARCHY_HASH_KEY,
    _HIERARCHY_PATH_KEY,
    _HIERARCHY_VERSION_KEY,
)


class _ShimName:
    """Late-bound name that always reads from this shim module."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _resolve(self):
        import sys
        return getattr(sys.modules[__name__], object.__getattribute__(self, "_name"))

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __repr__(self):
        return repr(self._resolve())


# Tests patch ui.mempalace_builder_dialog.MemePalaceChapterAIAnalyzerWorker
_analysis_mixin.MemePalaceChapterAIAnalyzerWorker = _ShimName("MemePalaceChapterAIAnalyzerWorker")


class MemePalaceBuilderDialog(
    MemePalaceBuilderUiMixin,
    MemePalacePipelineMixin,
    MemePalaceHierarchyMixin,
    MemePalaceDialogueMixin,
    MemePalaceAnalysisMixin,
    MemePalaceSessionMixin,
    QDialog,
):
    """Dialog class for meme palace builder."""

    def __init__(self, main_window, parent=None):
        """Initialize a new instance."""
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle(tr('MemPalace Context Builder'))
        self.resize(1080, 800)
        self.setMinimumSize(900, 800)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.worker = None
        self.client = None
        self.composer = None
        self.analysis_queue = []
        self.analysis_total_count = 0
        self.analysis_completed_count = 0
        self.current_analysis_idx = -1
        self.user_cancelled = False
        self.should_sleep_after = False
        self.pipeline_running = False
        self.pipeline_step = 0
        self.saved_pipeline_running = False
        self.saved_pipeline_step = 0
        self.saved_pipeline_wing = ""
        self.saved_pipeline_script = ""
        self.hierarchy_project = None
        self.imported_hierarchy_project_path = ""
        self.imported_hierarchy_project_hash = ""
        self.imported_hierarchy_project_version = None
        self.hierarchy_selection_error = ""
        self.story_document_id = None

        self._init_composer_and_client()
        self._setup_ui()
        self.load_builder_settings()
        self._load_active_markup_studio_project()
        
        # Auto-fill script path if empty
        if not self.file_path_edit.text().strip():
            script_path = self.composer._find_script_path() if self.composer else None
            if isinstance(script_path, str) and script_path:
                self.file_path_edit.setText(script_path)
                self.append_log(f"Auto-discovered game script file: {os.path.basename(script_path)}")
                
        self._refresh_wizard_state()


__all__ = [
    "MemePalaceBuilderDialog",
    "QFileDialog",
    "QMessageBox",
    "MemePalaceChapterAIAnalyzerWorker",
    "_HIERARCHY_PATH_KEY",
    "_HIERARCHY_HASH_KEY",
    "_HIERARCHY_VERSION_KEY",
]
