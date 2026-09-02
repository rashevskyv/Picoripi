"""Script Markup Studio dialog composition and __init__."""
from __future__ import annotations


from PyQt6.QtWidgets import (
    QDialog, QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtCore import QThread
from core.script_markup import (
    default_recipe, HierarchyMark, default_type_definitions,
)
from core.script_markup.hierarchy_ai_jobs import (
    HierarchyAIPrepareWorker as _HierarchyAIPrepareWorker,
    HierarchyAIWorker as _HierarchyAIWorker,
)
from components.ai_status_dialog import AIStatusDialog
from core.i18n import tr

from ui.script_markup.mixins import (
    ProjectIoMixin,
    HierarchyAiMixin,
    TeachPreviewMixin,
    OutlineContextMixin,
    OutlineStructureMixin,
    OutlineNavMixin,
    OutlineTreeMixin,
    OverlayMixin,
    HierarchyMarkOpsMixin,
    MarkingMixin,
    SessionMixin,
    RangeEditMixin,
    SearchViewMixin,
    HistoryMixin,
    UiMixin,
)


class ScriptMarkupStudioDialog(
    ProjectIoMixin,
    HierarchyAiMixin,
    TeachPreviewMixin,
    OutlineContextMixin,
    OutlineStructureMixin,
    OutlineNavMixin,
    OutlineTreeMixin,
    OverlayMixin,
    HierarchyMarkOpsMixin,
    MarkingMixin,
    SessionMixin,
    RangeEditMixin,
    SearchViewMixin,
    HistoryMixin,
    UiMixin,
    QDialog,
):
    """Single-view studio for marking up raw game scripts."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.recipe = default_recipe()
        self.mode = "hierarchy"      # "hierarchy" (new tree marks), "picoripi", or "custom"
        self.start_line = 0          # 1-based timeline start (0 = from top)
        self.end_line = 0            # 1-based timeline end (0 = to bottom)
        self._psm_text = ""          # last rendered standardized script
        self.current_raw_path = ""
        self.current_hierarchy_project_path = ""
        self._last_json_payload_path = ""
        self.manual_marks: dict[int, dict[str, object]] = {}
        self.hierarchy_marks: list[HierarchyMark] = []
        self.hierarchy_type_definitions = default_type_definitions()
        self._hierarchy_mark_order = 0
        self._has_unmarked_hierarchy_lines = False
        self._search_signature: tuple[str, bool, bool, bool] | None = None
        self._search_matches: list[tuple[int, int]] = []
        self._search_index: int | None = None
        self._search_error = ""
        self._search_document_revision: int | None = None
        self._search_text_fingerprint: tuple[int, int] | None = None
        self._raw_text_revision = 0
        self._range_edit_mark_key: str | None = None
        self._range_edit_start_line: int | None = None
        self._range_edit_end_line: int | None = None
        self._range_edit_start_col: int | None = None
        self._range_edit_end_col: int | None = None
        self._range_edit_drag_handle: str | None = None
        self._raw_navigation_line: int | None = None
        self._bulk_edit_mark_keys: list[str] = []
        self._bulk_edit_initial_controls: dict[str, object] = {}
        self._outline_reveal_keys: set[str] = set()
        self._outline_expansion_overrides: dict[str, bool] = {}
        self._outline_expansion_signal_suspended = 0
        self._outline_search_expansion_state: dict[str, bool] | None = None
        self._hierarchy_outline_signature = None
        self._collapsed_hierarchy_keys: set[str] = set()
        self._raw_line_depths: dict[int, int] = {}
        self._raw_fold_headers: dict[int, str] = {}
        self._raw_hierarchy_view_signature: tuple[tuple[tuple[int, int], ...], tuple[int, ...]] | None = None
        self._hierarchy_line_styles_cache_key = None
        self._hierarchy_line_styles_cache = None
        self._raw_hierarchy_view_data_cache_key = None
        self._raw_hierarchy_view_data_cache = None
        self._hierarchy_mark_by_key_cache: dict[str, HierarchyMark] | None = None
        self._hierarchy_paths_by_key_cache: dict[str, tuple[HierarchyMark, ...]] | None = None
        self._history_stack: list[dict] = []
        self._history_index = -1
        self._history_ready = False
        self._history_suspended = 0
        self._restoring_history = False
        self._history_text_dirty = False
        self._preview_dialog: QDialog | None = None
        self._preview_view: QPlainTextEdit | None = None
        self._hierarchy_ai_prepare_thread: QThread | None = None
        self._hierarchy_ai_prepare_worker: _HierarchyAIPrepareWorker | None = None
        self._hierarchy_ai_thread: QThread | None = None
        self._hierarchy_ai_worker: _HierarchyAIWorker | None = None
        self._hierarchy_ai_status: AIStatusDialog | None = None
        self._hierarchy_ai_last_response = ""
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._hierarchy_ai_started_at: float | None = None
        self._hierarchy_ai_progress_state: tuple[int, int, str] | None = None
        self._hierarchy_ai_elapsed_timer = QTimer(self)
        self._hierarchy_ai_elapsed_timer.setInterval(1000)
        self._hierarchy_ai_elapsed_timer.timeout.connect(self._update_hierarchy_ai_elapsed_detail)

        self.setWindowTitle(tr('Script Markup Studio'))
        self.resize(900, 720)
        self.setMinimumSize(720, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._refresh)
        self._history_text_timer = QTimer(self)
        self._history_text_timer.setSingleShot(True)
        self._history_text_timer.setInterval(450)
        self._history_text_timer.timeout.connect(self._record_pending_text_history)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(2000)
        self._autosave_timer.timeout.connect(self._autosave_session_tick)
        self._is_autosaved_dirty = False
        self._last_saved_state = None

        self._setup_ui()
        self._update_mode_controls()
        self._restore_window_geometry()
        restored_session = self._restore_autosaved_session()
        if not restored_session:
            self._auto_discover_script()
        self._history_ready = True
        self._record_history(force=True)

