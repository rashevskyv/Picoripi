from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QDialog
from handlers.text_operation_handler import TextOperationHandler

class MockUIProvider:
    def __init__(self):
        self.data_store = self
        self._programmatically_changing = False
        self._texts = {"edited_text_edit": "Initial text"}
        self._cursor_pos = 0

    def is_programmatically_changing(self): return self._programmatically_changing
    def set_programmatically_changing(self, v): self._programmatically_changing = v
    def get_editor_text(self, etype): return self._texts.get(etype, "")
    def set_editor_text(self, etype, text, preserve_undo=True): self._texts[etype] = text
    def update_editor_linenumber_area(self, etype): pass
    def set_search_status(self, msg): pass
    def show_message(self, t, m, i="info"): pass

class MockContext(MagicMock):
    @property
    def physical_block_idx(self) -> int:
        if hasattr(self, '_physical_block_idx') and self._physical_block_idx >= 0:
            return self._physical_block_idx
        if hasattr(self, 'current_block_idx') and self.current_block_idx >= 0:
            return self.current_block_idx
        return -1

    def __getattribute__(self, name):
        if name in ('physical_block_idx', '_physical_block_idx'):
            return object.__getattribute__(self, name)
        return super().__getattribute__(name)

    @physical_block_idx.setter
    def physical_block_idx(self, val: int) -> None:
        self._physical_block_idx = val

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_store = self
        self._physical_block_idx = -1
        self.current_block_idx = 0
        self.current_string_idx = 0
        # The editor is showing this row, which is what makes a text change a
        # real user edit rather than the app refilling the view.
        self.editor_bound_row = (0, 0)
        self.data = [["Original line 1"]]
        self.edited_data = {}
        self.edited_file_data = [["Original line 1"]]
        self.edited_sublines = set()
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 300
        self.ui_provider = MockUIProvider()
        self.ui_updater = MagicMock()
        self.current_game_rules = MagicMock()
        self.current_game_rules.convert_editor_text_to_data.side_effect = lambda x: x
        self.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"PREVIEW: {x}"
        self.newline_display_symbol = "↵"
        self.show_multiple_spaces_as_dots = False
        self.is_programmatically_changing_text = False
        # A real edit happens outside loading; both guards must be modelled or
        # MagicMock returns a truthy stub and the edit looks like app-driven churn.
        self.is_loading_data = False
        self.edited_text_edit = MagicMock()
        self.helper = MagicMock()
        self.helper.get_font_map_for_string.return_value = {}

    def update_title(self): pass
    def get_font_map_for_string(self, b, s): return {}

@patch('handlers.text_operation_handler.get_scanner_thread_pool')
@patch('handlers.text_operation_handler.AsyncIssueScanner')
def test_text_edited_basic(mock_async_scanner, mock_get_pool):
    ctx = MockContext()
    data_processor = MagicMock()
    # Mock data_processor._get_string_from_source to return original
    data_processor._get_string_from_source.return_value = "Original line 1"
    data_processor.get_current_string_text.return_value = ("Changed line 1", "edited")

    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)

    # Simulate editing text
    ctx.edited_text_edit.toPlainText.return_value = "Changed line 1"

    handler.text_edited()
    handler._on_preview_update_timer_timeout()

    # Verify edited_sublines contains index 0
    assert 0 in ctx.data_store.edited_sublines
    # Verify data_processor.update_edited_data was called
    data_processor.update_edited_data.assert_called()
    # Verify scanner was instantiated and submitted to the shared thread pool.
    mock_async_scanner.assert_called_once()
    mock_get_pool.return_value.start.assert_called_once_with(mock_async_scanner.return_value)

def test_revert_line():
    ctx = MockContext()
    data_processor = MagicMock()
    data_processor._get_string_from_source.return_value = "Original line 1"
    data_processor.get_current_string_text.return_value = ("Changed line 1", "edited")

    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)

    handler.revert_single_line(0)

    # Verify update_edited_data called with original text
    data_processor.update_edited_data.assert_called_with(0, 0, "Original line 1", action_type="REVERT")

def test_fix_all_strings_target_strings():
    with patch('handlers.text_operation_handler.AutofixSelectionDialog') as mock_dialog_class, \
         patch('handlers.text_operation_handler.QProgressDialog') as mock_progress_class, \
         patch('handlers.text_operation_handler.AutofixWorker') as mock_worker_class:
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_selected_problems.return_value = ["some_problem"]
        mock_dialog_class.return_value = mock_dialog

        mock_progress = MagicMock()
        mock_progress_class.return_value = mock_progress

        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        ctx = MockContext()
        ctx.current_game_rules.get_problem_definitions.return_value = {"some_problem": {"name": "Some Problem"}}
        ctx.edited_text_edit.document().characterCount.return_value = 10
        ctx.edited_text_edit.textCursor().position.return_value = 5

        data_processor = MagicMock()
        data_processor.get_current_string_text.return_value = ("Fixed text", "edited")
        ui_updater = MagicMock()
        handler = TextOperationHandler(ctx, data_processor, ui_updater)

        # Simulate worker finishing immediately when start is called
        def mock_start():
            handler._on_autofix_finished([(0, 0, "Original text", "Fixed text")])
        mock_worker.start.side_effect = mock_start

        target_strings = [(0, 0)]
        handler.fix_all_strings(target_strings)

        mock_worker_class.assert_called_once()
        mock_worker.start.assert_called_once()
        data_processor.update_edited_data.assert_called_once_with(
            0, 0, "Fixed text", action_type="AUTOFIX", skip_ui_refresh=True
        )

def test_autofix_cleanup_with_running_worker():
    ctx = MockContext()
    data_processor = MagicMock()
    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    mock_worker.wait.return_value = True

    handler._active_autofix_worker = mock_worker

    # Call cleanup
    handler._cleanup_active_autofix()

    # Ensure worker was cancelled, waited on and deleted later
    mock_worker.cancel.assert_called_once()
    mock_worker.wait.assert_called_once_with(2000)
    mock_worker.deleteLater.assert_called_once()
    assert handler._active_autofix_worker is None


def test_autofix_cleanup_with_real_thread(qtbot):
    ctx = MockContext()
    data_processor = MagicMock()
    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)

    from handlers.autofix_worker import AutofixWorker
    worker = AutofixWorker(
        game_rules=ctx.current_game_rules,
        target_strings=[(0, 0)],
        data=[["line1"]],
        edited_data={},
        edited_file_data=[],
        string_metadata={},
        all_font_maps={},
        font_map={},
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=set(),
        page_local=False
    )
    
    # Assign worker to handler
    handler._active_autofix_worker = worker
    
    # Start thread
    worker.start()
    assert worker.isRunning()
    
    # Call cleanup
    handler._cleanup_active_autofix()
    
    # Verify that the thread has stopped and handler reference is cleared
    assert not worker.isRunning()
    assert handler._active_autofix_worker is None


