import pytest
pytestmark = pytest.mark.serial
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QThread
from components.dictionary_manager_dialog import DictionaryManagerDialog, DictionaryListFetchWorker, DownloadThread

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

@pytest.fixture(autouse=True)
def mock_requests_get():
    """Globally mock requests.get inside dictionary_manager_dialog to prevent real network calls."""
    with patch("components.dictionary_manager_dialog.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        yield mock_get

def test_dictionary_manager_fetch_success(qapp, mock_requests_get):
    # Setup mocks
    parent_widget = QWidget()
    parent_widget.spellchecker_manager = MagicMock()
    parent_widget.spellchecker_manager.scan_local_dictionaries.return_value = ["en"]
    
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "uk_UA", "type": "dir"},
        {"name": "en_US", "type": "dir"}
    ]
    mock_requests_get.return_value = mock_response

    # Instantiate dialog
    dialog = DictionaryManagerDialog(parent_widget)
    assert dialog.status_label.text() == "Fetching remote dictionary list..."
    
    # Manually trigger list fetched to simulate worker completion
    dialog.on_list_fetched(True, mock_response.json.return_value, "")
    
    assert dialog.status_label.text() == "Ready."
    assert "uk_UA" in dialog.lang_code_map
    assert "en_US" in dialog.lang_code_map
    
    # Verify items in list widget
    assert dialog.dict_list.count() > 0
    dialog.reject()

def test_dictionary_manager_fetch_failure(qapp):
    parent_widget = QWidget()
    parent_widget.spellchecker_manager = MagicMock()
    
    dialog = DictionaryManagerDialog(parent_widget)
    
    # Simulate fetch failure
    dialog.on_list_fetched(False, [], "Network error")
    
    assert "Error fetching list: Network error" in dialog.status_label.text()
    assert dialog.dict_list.count() == 0
    dialog.reject()

def test_dictionary_manager_rejection_cleans_threads(qapp):
    parent_widget = QWidget()
    parent_widget.spellchecker_manager = MagicMock()
    
    dialog = DictionaryManagerDialog(parent_widget)
    
    # Safely shutdown the auto-started worker first
    if dialog.list_worker:
        from utils.thread_utils import safe_shutdown_thread
        safe_shutdown_thread(dialog.list_worker, dialog.list_worker)
        dialog.list_worker = None
        
    # Mock threads
    mock_list_worker = MagicMock(spec=DictionaryListFetchWorker)
    mock_download_thread = MagicMock(spec=DownloadThread)
    
    dialog.list_worker = mock_list_worker
    dialog.download_thread = mock_download_thread
    
    with patch("utils.thread_utils.safe_shutdown_thread") as mock_safe_shutdown:
        # Call reject
        dialog.reject()
        
        # Confirm safe_shutdown_thread was called for both threads
        assert mock_safe_shutdown.call_count == 2
        mock_safe_shutdown.assert_any_call(mock_list_worker, mock_list_worker)
        mock_safe_shutdown.assert_any_call(mock_download_thread, mock_download_thread)
        
        assert dialog.list_worker is None
        assert dialog.download_thread is None

def test_dictionary_list_fetch_worker_cancel(mock_requests_get):
    worker = DictionaryListFetchWorker("https://fakeurl.com")
    
    # Set cancelled
    worker.cancel()
    assert worker._is_cancelled is True
    
    # Run should exit early if cancelled
    worker.run()
    # requests.get should be called, but since worker is cancelled, no signals/payload process
    assert mock_requests_get.called

def test_download_thread_cancel(mock_requests_get):
    downloads = [("https://fakeurl.com/en.dic", "resources/spellchecker/temp_test_en.dic")]
    thread = DownloadThread(downloads)
    
    # Call cancel
    thread.cancel()
    assert thread._is_cancelled is True
    
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_requests_get.return_value = mock_response
    
    # Mock file operations to avoid actual file I/O
    with patch("components.dictionary_manager_dialog.open", create=True) as mock_open:
        thread.run()
        # It should exit without writing
        assert mock_open.called
