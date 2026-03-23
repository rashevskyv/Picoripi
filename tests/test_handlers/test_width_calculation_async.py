import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QProgressDialog, QMessageBox, QPlainTextEdit
from handlers.app_action_handler import AppActionHandler
from handlers.width_calculation_worker import WidthCalculationWorker

@pytest.fixture
def mock_mw(qapp):
    from PyQt5.QtCore import QObject
    mw = MagicMock()
    mw.data_store = MagicMock()
    mw.data_store.data = []
    mw.data = mw.data_store.data  # Ensure self.mw.data is available
    mw.data_store.block_names = {}
    mw.font_map = {"a": {"width": 10}}
    mw.line_width_warning_threshold_pixels = 200
    mw.game_dialog_max_width_pixels = 400
    mw.helper = MagicMock()
    mw.helper.get_font_map_for_string.return_value = mw.font_map
    mw.string_metadata = {}
    mw.text_analysis_handler = MagicMock()
    return mw

@pytest.fixture
def mock_ui():
    return MagicMock()

@pytest.fixture
def mock_data_processor():
    dp = MagicMock()
    dp.get_current_string_text.return_value = ("aaa", "source")
    dp._get_string_from_source.return_value = "aaa"
    return dp

@pytest.fixture
def mock_game_rules():
    gr = MagicMock()
    gr.get_problem_definitions.return_value = {}
    return gr

def test_calculate_widths_for_block_action_async_no_freeze(mock_mw, mock_ui, mock_data_processor, mock_game_rules, qapp):
    handler = AppActionHandler(mock_mw, mock_data_processor, mock_ui, mock_game_rules)
    
    num_strings = 100
    mock_mw.data_store.data = [[f"string_{i}\npart2_{i}" for i in range(num_strings)]] 
    mock_mw.data = mock_mw.data_store.data  # Re-sync mock_mw.data
    mock_mw.data_store.block_names = {"0": "BigBlock"}
    
    # Need to keep font_map_helper references
    mock_mw.helper.get_font_map_for_string.return_value = {"a": {"width": 10}}

    with patch("handlers.app_action_handler.QProgressDialog") as MockProgress, \
         patch("handlers.app_action_handler.LargeTextReportDialog") as MockReportDialog:
        
        progress_mock = MockProgress.return_value
        
        def simulate_worker_finish():
            import time
            max_wait = 5.0
            start = time.time()
            # Wait for worker to be created and started
            while not hasattr(handler, 'width_worker') and time.time() - start < 1.0:
                qapp.processEvents()
                time.sleep(0.01)
            
            if hasattr(handler, 'width_worker'):
                worker = handler.width_worker
                while worker.isRunning() and time.time() - start < max_wait:
                    qapp.processEvents()
                    time.sleep(0.1)
                # One last processEvents to ensure signals are handled
                for _ in range(10): qapp.processEvents()
            
        progress_mock.exec_.side_effect = simulate_worker_finish
        
        handler.calculate_widths_for_block_action(0)
        
        # Verify worker was started
        assert hasattr(handler, 'width_worker')
        
        # Verify which dialog was called
        handler_called = mock_mw.text_analysis_handler.show_diagnostic_analysis.called
        fallback_called = MockReportDialog.called
        
        assert handler_called or fallback_called, "No report dialog was shown"
        assert handler_called, f"Fell back to text report. mock_mw has handler? {hasattr(mock_mw, 'text_analysis_handler')}"
        
        # Verify entries were passed
        args, kwargs = mock_mw.text_analysis_handler.show_diagnostic_analysis.call_args
        entries = args[0]
        title = kwargs.get('title') or (args[1] if len(args) > 1 else "")
        
        assert len(entries) > 0
        assert "width_pixels" in entries[0]
        assert "BigBlock" in title
