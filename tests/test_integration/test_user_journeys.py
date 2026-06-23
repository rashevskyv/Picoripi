import pytest
pytestmark = pytest.mark.serial
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QTextEdit, QMainWindow
from PyQt6.QtCore import QTimer

from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor
from core.undo_manager import UndoManager
from ui.updaters.preview_updater import PreviewUpdater
from handlers.text_operation_handler import TextOperationHandler
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler
from core.glossary_manager import GlossaryManager
from handlers.translation.glossary_handler import GlossaryOccurrenceWorker

class IntegrationMockMainWindow(QMainWindow):
    """Specialized mock window for integration testing user journeys."""
    @property
    def physical_block_idx(self) -> int:
        if hasattr(self, '_physical_block_idx'):
            val = self._physical_block_idx
            if val is not None and not isinstance(val, MagicMock):
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        if hasattr(self, 'current_block_idx'):
            c_idx = self.current_block_idx
            if c_idx is not None and not isinstance(c_idx, MagicMock):
                try:
                    return int(c_idx)
                except (TypeError, ValueError):
                    pass
        return -1

    @physical_block_idx.setter
    def physical_block_idx(self, val: int) -> None:
        self._physical_block_idx = val

    def __init__(self):
        super().__init__()
        self.data_store = self
        self.data = [["Original Line 1", "Original Line 2"]]
        self.edited_file_data = [["Original Line 1", "Original Line 2"]]
        self.edited_data = {}
        self.unsaved_block_indices = set()
        self.edited_sublines = set()
        self.unsaved_changes = False
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.block_names = {"0": "Test Block"}
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 208
        self.game_dialog_max_width_pixels = 208
        self.project_manager = MagicMock()
        self.project_manager.project = MagicMock()
        self.project_manager.project.blocks = [MagicMock()]
        self.block_to_project_file_map = {0: 0}
        self.undo_manager = None
        self.is_programmatically_changing_text = False
        self.current_game_rules = None
        self.active_game_plugin = "zelda_mc"
        self.helper = MagicMock()
        self.helper.get_font_map_for_string.return_value = {}
        self.helper.get_font_for_name.return_value = None
        self._is_test_mode = True

        # Display settings
        self.show_multiple_spaces_as_dots = False
        self.show_warnings_only = False
        self.active_warning_filters = []
        self.hide_empty_strings = False
        self.hide_translated = False
        self.hide_categorized = False
        self.highlight_categorized = False
        self.show_overrides_only = False
        self.show_unsaved_only = False
        self.displayed_string_indices = [0, 1]

        # UI controls setup
        self.original_width_label = MagicMock()
        self.warnings_filter_button = MagicMock()

        from core.filter_query_api import FilterQueryAPI
        self.filter_query_api = FilterQueryAPI(self)

def test_user_journey_undo_redo_preview(qapp, qtbot):
    """
    User Journey 1:
    Change text -> Preview update -> Undo -> verify revert -> Redo -> verify restore.
    """
    mw = IntegrationMockMainWindow()
    mw._is_sync_scan = True
    dsp = DataStateProcessor(mw)
    mw.data_processor = dsp
    mw.editor_operation_handler = MagicMock()

    # Configure actual widgets
    mw.original_text_edit = QTextEdit()
    mw.original_text_edit.reset_selection_state = lambda: None
    mw.original_text_edit.updateLineNumberAreaWidth = lambda x: None
    mw.original_text_edit.setDocumentFont = lambda x: None

    mw.edited_text_edit = QTextEdit()
    mw.edited_text_edit.reset_selection_state = lambda: None
    mw.edited_text_edit.updateLineNumberAreaWidth = lambda x: None
    mw.edited_text_edit.setDocumentFont = lambda x: None

    mw.preview_text_edit = QTextEdit()
    mw.preview_text_edit.reset_selection_state = lambda: None
    mw.preview_text_edit.updateLineNumberAreaWidth = lambda x: None
    mw.preview_text_edit.setDocumentFont = lambda x: None

    # Load plugin
    mw.active_game_plugin = "plain_text"
    ph = MainWindowPluginHandler(mw)
    ph.load_game_plugin()

    # Real undo manager and preview updater
    mw.undo_manager = UndoManager(mw)
    preview_updater = PreviewUpdater(mw, dsp)
    mw.ui_updater = MagicMock()
    mw.ui_updater.preview_updater = preview_updater
    mw.ui_updater.update_text_views.side_effect = preview_updater.update_text_views
    mw.ui_updater.synchronize_original_cursor.side_effect = preview_updater.synchronize_original_cursor

    # Mocking block update for UI
    mw.ui_updater.update_block_item_text_with_problem_count = MagicMock()

    # Setup handler
    toh = TextOperationHandler(mw, dsp, mw.ui_updater)
    mw.text_operation_handler = toh

    try:
        # Initial state
        preview_updater.populate_strings_for_block(0, force=True)
        assert mw.preview_text_edit.toPlainText().startswith("Original Line 1")

        # 1. Edit text
        mw.is_programmatically_changing_text = False
        mw.edited_text_edit.setPlainText("New Changed Line 1")

        # Record action in undo manager before invoking handler to simulate editor behavior
        mw.undo_manager.record_action(
            "TEXT_EDIT", 0, 0, "Original Line 1", "New Changed Line 1"
        )

        # Apply text edit
        toh.text_edited()
        # Force timeout immediate execution and stop the timer to prevent race conditions
        toh.preview_update_timer.stop()
        toh._on_preview_update_timer_timeout()

        # Wait for the async issue scan to finish, which triggers update_text_views
        qtbot.waitUntil(
            lambda: mw.preview_text_edit.toPlainText().startswith("New Changed Line 1"),
            timeout=25000
        )

        # Verify the edited data has been updated
        assert dsp.get_current_string_text(0, 0)[0] == "New Changed Line 1"

        # 2. Perform Undo
        mw.undo_manager.undo()
        assert dsp.get_current_string_text(0, 0)[0] == "Original Line 1"
        assert mw.edited_text_edit.toPlainText() == "Original Line 1"

        # 3. Perform Redo
        mw.undo_manager.redo()
        assert dsp.get_current_string_text(0, 0)[0] == "New Changed Line 1"
        assert mw.edited_text_edit.toPlainText() == "New Changed Line 1"
    finally:
        if 'toh' in locals():
            if hasattr(toh, 'preview_update_timer'):
                toh.preview_update_timer.stop()
            if toh.current_scanner_thread is not None:
                toh.current_scanner_thread.cancel()
                toh.current_scanner_thread = None
        if 'dsp' in locals():
            if getattr(dsp, 'autosave_timer', None) is not None:
                dsp.autosave_timer.stop()
            if getattr(dsp, 'durable_session_timer', None) is not None:
                dsp.durable_session_timer.stop()
        from handlers.async_issue_scanner import get_scanner_thread_pool
        pool = get_scanner_thread_pool()
        if pool is not None:
            pool.waitForDone()

def test_user_journey_plugin_switch_validation(qapp, qtbot):
    """
    User Journey 2:
    Load project with 'zelda_mc' -> input long text -> observe width warnings.
    Switch plugin to 'plain_text' -> verify warnings resolved or recalculated.
    """
    mw = IntegrationMockMainWindow()
    dsp = DataStateProcessor(mw)
    mw.data_processor = dsp

    # Load MC plugin
    mw.active_game_plugin = "zelda_mc"
    ph = MainWindowPluginHandler(mw)
    ph.load_game_plugin()

    assert mw.current_game_rules is not None
    assert mw.game_dialog_max_width_pixels == 208

    # Configure handlers
    mw.ui_updater = MagicMock()
    toh = TextOperationHandler(mw, dsp, mw.ui_updater)
    mw.text_operation_handler = toh

    try:
        # Set a medium length string (57 chars * 6px/char = 342px)
        # This exceeds Zelda MC limit (208px) but fits plain_text (600px)
        medium_string = "This is a medium length string that is over limit for MC."

        # Run issue scan
        toh._rescan_issues_for_current_string(0, 0, medium_string)

        # Check that warnings were generated for width exceeded
        mc_problems = mw.data_store.problems_per_subline.get((0, 0, 0), [])
        assert len(mc_problems) > 0
        # At least one problem should be about width limit
        assert any("limit" in str(p).lower() or "width" in str(p).lower() or "exceed" in str(p).lower() for p in mc_problems)

        # Now switch to 'plain_text' which has a limit of 600px
        mw.active_game_plugin = "plain_text"
        mw.game_dialog_max_width_pixels = 600
        mw.line_width_warning_threshold_pixels = 600
        ph.load_game_plugin()

        # Re-run issue scan
        toh._rescan_issues_for_current_string(0, 0, medium_string)

        # Verify that either warnings are resolved or recalculated for new rules
        pt_problems = mw.data_store.problems_per_subline.get((0, 0, 0), [])
        # Since 600px is much larger than 208px, the string should fit under plain_text limits
        assert len(pt_problems) == 0
    finally:
        if 'dsp' in locals():
            if getattr(dsp, 'autosave_timer', None) is not None:
                dsp.autosave_timer.stop()
            if getattr(dsp, 'durable_session_timer', None) is not None:
                dsp.durable_session_timer.stop()

def test_user_journey_glossary_crud_highlight(qapp, qtbot):
    """
    User Journey 3:
    Create Glossary entry -> GlossaryOccurrenceWorker runs -> Highlights apply -> Autosave.
    """
    mw = IntegrationMockMainWindow()
    dsp = DataStateProcessor(mw)
    mw.data_processor = dsp

    # Setup data store with some text
    mw.data = [["I saw Zelda in the castle.", "Link went to Hyrule."]]
    mw.edited_file_data = [["I saw Zelda in the castle.", "Link went to Hyrule."]]
    mw.data_store.data = mw.data
    mw.data_store.displayed_string_indices = [0, 1]

    # Create glossary manager and clear/add entry
    glossary_manager = GlossaryManager()
    glossary_manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    glossary_manager.add_entry("Zelda", "Зельда", "Princess")

    # Run the worker to build the occurrence index
    worker = GlossaryOccurrenceWorker(glossary_manager, mw.data, parent=mw)

    results = []
    worker.finished_with_result.connect(lambda res: results.append(res))
    try:
        worker.run()
        qtbot.waitUntil(lambda: len(results) > 0, timeout=30000)
    finally:
        if worker.isRunning():
            worker.requestInterruption()
        worker.wait(5000)

    try:
        occurrence_map = results[0]
        assert "Zelda" in occurrence_map
        occurrences = occurrence_map["Zelda"]
        assert len(occurrences) > 0
        assert occurrences[0].block_idx == 0
        assert occurrences[0].string_idx == 0
        assert occurrences[0].start == 6 # "Zelda" starts at index 6 in "I saw Zelda"

        # Check that autosave scheduling functions correctly
        with patch.object(dsp, "schedule_autosave") as mock_save:
            dsp.update_edited_data(0, 0, "I saw Zelda in the castle.")
            mock_save.assert_called_once()
    finally:
        if 'dsp' in locals():
            if getattr(dsp, 'autosave_timer', None) is not None:
                dsp.autosave_timer.stop()
            if getattr(dsp, 'durable_session_timer', None) is not None:
                dsp.durable_session_timer.stop()
