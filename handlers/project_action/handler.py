"""ProjectActionHandler: project lifecycle, blocks, session, recent projects, tree."""
from typing import Any, Optional
from core.i18n import tr
from core.project_manager import ProjectManager
from handlers.base_handler import BaseHandler
from handlers.project_action.lifecycle_mixin import LifecycleMixin
from handlers.project_action.blocks_mixin import BlocksMixin
from handlers.project_action.session_mixin import SessionMixin
from handlers.project_action.recent_mixin import RecentMixin
from handlers.project_action.tree_mixin import TreeMixin
from handlers.project_action.library_mixin import LibraryMixin
from utils.thread_utils import safe_shutdown_thread


STARTUP_STALL_MS = 120_000   # a start-up project load with no progress for this long is given up


class ProjectActionHandler(
    LifecycleMixin,
    BlocksMixin,
    SessionMixin,
    RecentMixin,
    TreeMixin,
    LibraryMixin,
    BaseHandler,
):
    """Handler for project action operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        # Ensure ProjectManager is initialized on the main window
        if not hasattr(self.mw, 'project_manager') or self.mw.project_manager is None:
            self.mw.project_manager = ProjectManager()

        from PyQt6.QtCore import QObject, QTimer
        timer_parent = self.mw if isinstance(self.mw, QObject) else None
        self._restore_view_timer = QTimer(timer_parent)
        self._restore_view_timer.setSingleShot(True)
        self._restore_view_timer.timeout.connect(self._on_restore_view_timer_timeout)
        self._pending_restore_block: int = 0
        self._pending_restore_cat: Optional[str] = None
        self._finish_startup_after_restore_timer = False
        # The start-up watchdog: a project load that makes no progress for STARTUP_STALL_MS is given up.
        self._startup_watchdog = QTimer(timer_parent)
        self._startup_watchdog.setSingleShot(True)
        self._startup_watchdog.timeout.connect(self._on_startup_stalled)
        self._startup_project = ""
        self._open_generation = 0
        self._added_to_recent: set = set()   # recent entries this session's open added (undone on failure)

    def _report_startup(self, value: int, message: str) -> None:
        reporter = getattr(self.mw, 'report_startup_progress', None)
        if callable(reporter):
            reporter(value, message)
        if self._startup_project:
            self._startup_watchdog.start(STARTUP_STALL_MS)   # progress: the load is alive

    def _arm_startup_watchdog(self, project_path: str) -> None:
        self._startup_project = project_path
        self._startup_watchdog.start(STARTUP_STALL_MS)

    def _disarm_startup_watchdog(self) -> None:
        self._startup_project = ""
        self._startup_watchdog.stop()

    def _on_startup_stalled(self) -> None:
        """No progress for STARTUP_STALL_MS: stop the load, forget the project as the last one, open the manager."""
        path, self._startup_project = self._startup_project, ""
        if not path or getattr(self.mw, '_startup_splash', None) is None:
            return
        self._open_generation += 1
        worker = getattr(self, '_active_load_worker', None)
        if worker is not None:
            safe_shutdown_thread(worker, worker, timeout_ms=2000)
        self._project_open_failed(path, tr("Loading stopped: no progress for {0} seconds.",
                                             STARTUP_STALL_MS // 1000))

    def _set_project_actions_enabled(self, enabled: bool):
        """Enable or disable project-specific UI actions and update their tooltips."""
        from ui.builders.layout_builder import ADD_BLOCK_TOOLTIP, ADD_FOLDER_TOOLTIP
        actions_map = {
            'close_project_action': {
                'enabled_tip': "Close the current project or file",
                'disabled_tip': "No project or file open to close"
            },
            'import_block_action': {
                'enabled_tip': "Import Block...",
                'disabled_tip': "This action is only available in Project mode (within a .uiproj project)."
            },
            'import_directory_action': {
                'enabled_tip': "Import Directory...",
                'disabled_tip': "This action is only available in Project mode (within a .uiproj project)."
            },
            'add_block_button': {
                'enabled_tip': ADD_BLOCK_TOOLTIP,
                'disabled_tip': "Adding blocks is only available in Project mode (within a .uiproj project)."
            },
            'add_folder_button': {
                'enabled_tip': ADD_FOLDER_TOOLTIP,
                'disabled_tip': "Creating folders is only available in Project mode (within a .uiproj project)."
            },
            'export_bmg_json_action': {
                'enabled_tip': "Export the currently selected BMG file's text content to JSON",
                'disabled_tip': "Export BMG to JSON is only available when a project is open."
            },
            'import_bmg_json_action': {
                'enabled_tip': "Import BMG text content from an exported JSON file into the currently selected block",
                'disabled_tip': "Import BMG from JSON is only available when a project is open."
            },
            'save_translated_action': {
                'enabled_tip': "Save current translation to local backup database",
                'disabled_tip': "No project or file is open"
            },
            'restore_translated_action': {
                'enabled_tip': "Restore last saved translation for this string",
                'disabled_tip': "No project or file is open"
            },
            'export_translations_action': {
                'enabled_tip': "Export all current project/file translations to a JSON file",
                'disabled_tip': "No project or file is open"
            },
            'export_original_action': {
                'enabled_tip': "Export all current project/file original text to a JSON file",
                'disabled_tip': "No project or file is open"
            },
            'import_translations_action': {
                'enabled_tip': "Import translations from an exported JSON file",
                'disabled_tip': "No project or file is open"
            }
        }
        for action_name, tips in actions_map.items():
            action = getattr(self.mw, action_name, None)
            if action:
                action.setEnabled(enabled)
                action.setToolTip(tips['enabled_tip'] if enabled else tips['disabled_tip'])

