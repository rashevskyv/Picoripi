import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from ui.updaters.block_list_updater import BlockListUpdater

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    pw = QTreeWidget()
    mw.block_list_widget = pw
    mw.data_store.block_names = {"0": "Block Zero", "1": "Block One"}
    mw.data_store.data = [["Str0"], ["Str1", "Str2"]]
    
    pm = MagicMock()
    pm.project.blocks = []
    block0 = MagicMock()
    block0.source_file = "src/block0.txt"
    pm.project.blocks.append(block0)
    pm.SOURCES_DIR = "src"
    mw.project_manager = pm
    
    mw.data_store.problems_per_subline = {
        (0, 0, 0): {"prob1"},
        (1, 0, 0): {"prob1", "prob2"},
    }
    
    gr = MagicMock()
    gr.get_problem_definitions.return_value = {
        "prob1": {"priority": 1, "name": "Width Error"},
        "prob2": {"priority": 2, "name": "Empty Odd Line Error"}
    }
    mw.current_game_rules = gr
    
    return mw

@pytest.fixture
def mock_dp():
    dp = MagicMock()
    dp.get_current_string_text.side_effect = lambda b, s: (f"Text {b} {s}", None)
    return dp

@pytest.fixture
def updater(mock_mw, mock_dp):
    return BlockListUpdater(mock_mw, mock_dp)

def test_BlockListUpdater_populate_blocks(updater):
    # Mock create_item because it's a custom method on main window's block list widget
    mock_item = QTreeWidgetItem()
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)
    updater.mw.project_manager = None # Force fallback legacy mode
    
    updater.populate_blocks()
    
    # Verify that it creates 2 items
    assert updater.mw.block_list_widget.create_item.call_count == 2
    
    # Check that dir_nodes logic works
    assert updater.mw.block_list_widget.topLevelItemCount() > 0

def test_BlockListUpdater_update_block_item_text_with_problem_count(updater):
    # Setup tree item
    item = QTreeWidgetItem(["Block 0Base"])
    item.setData(0, Qt.UserRole, 0)
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.update_block_item_text_with_problem_count(0)
    
    expected_text = "Block Zero (1)"
    assert item.text(0) == expected_text
    assert "Width Error" in item.toolTip(0)

    item1 = QTreeWidgetItem(["Block 1Base"])
    item1.setData(0, Qt.UserRole, 1)
    updater.mw.block_list_widget.addTopLevelItem(item1)
    
    updater.update_block_item_text_with_problem_count(1)
    expected_text1 = "Block One (2)"
    assert item1.text(0) == expected_text1
    assert "Width Error" in item1.toolTip(0)
    assert "Empty Odd Line Error" in item1.toolTip(0)

def test_BlockListUpdater_clear_all_problem_block_highlights_and_text(updater):
    # Setup tree item
    item = QTreeWidgetItem(["Block Zero (1)"])
    item.setData(0, Qt.UserRole, 0)
    item.setToolTip(0, "Some Error")
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.clear_all_problem_block_highlights_and_text()
    
    assert item.text(0) == "Block Zero"
    assert item.toolTip(0) == ""


def test_BlockListUpdater_populate_chapters(updater):
    # Setup mock for mempalace client and chapters
    mock_client = MagicMock()
    mock_client.get_all_chapters.return_value = [
        {"num": "Act 1, Ch 1", "title": "Ordon Village", "id": 10},
        {"num": "Act 2, Ch 1", "title": "Faron Woods", "id": 20}
    ]
    mock_client.get_chapter_mappings.return_value = [
        {"bmg_id": "main_Str_10", "script_line": 100, "bmg_text": "Hello World"}
    ]
    mock_client.get_all_chapter_mappings.return_value = {
        10: [{"bmg_id": "main_Str_10", "script_line": 100, "bmg_text": "Hello World"}],
        20: []
    }
    
    # Mock translation_handler and prompt_composer
    composer = MagicMock()
    composer.prompt_composer._get_mempalace_client.return_value = mock_client
    composer.prompt_composer._get_wing_name.return_value = "tp"
    updater.mw.translation_handler = composer
    updater.mw.current_wing_name = "tp"
    
    # Mock selection handler resolve_bmg_id_to_indices
    updater.mw.list_selection_handler = MagicMock()
    updater.mw.list_selection_handler.resolve_bmg_id_to_indices.return_value = (0, 10)
    
    # Mock block list widget custom create_item method
    mock_item = QTreeWidgetItem()
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)
    
    # Populate blocks should fetch chapters and add tree nodes
    updater.populate_blocks()
    
    # Find "Chapters" root node in block list widget
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = None
    for r in root_items:
        if r.text(0) == "Chapters":
            chapters_root = r
            break
            
    assert chapters_root is not None
    assert chapters_root.childCount() == 2 # Act 1 and Act 2
    
    act1 = chapters_root.child(0)
    assert act1.text(0) == "Act 1"
    assert act1.childCount() == 1
    
    ch1 = act1.child(0)
    assert "Chapter 1: Ordon Village" in ch1.text(0)
    assert ch1.data(0, Qt.UserRole) == -2
    assert ch1.data(0, Qt.UserRole + 11) == 10
    assert ch1.data(0, Qt.ItemDataRole.UserRole + 13) == [(0, 10)]
    
    # Verify that no dialogue child rows are nested under ch1 (redundant to preview panel)
    assert ch1.childCount() == 0


def test_BlockListUpdater_compacted_folder_problem_count(updater):
    # Setup project with virtual folders
    project = MagicMock()
    updater.mw.project_manager.project = project
    updater.mw.translation_handler = None # Prevent chapters generation
    
    # folder with single block
    folder = MagicMock()
    folder.id = "folder_1"
    folder.name = "CompactFolder"
    folder.is_expanded = True
    folder.children = []
    folder.block_ids = ["block_0_id"]
    
    project.virtual_folders = [folder]
    project.metadata = {}
    
    block_obj = MagicMock()
    block_obj.id = "block_0_id"
    block_obj.source_file = "src/block0.txt"
    block_obj.categories = []
    project.blocks = [block_obj]
    
    updater.mw.block_to_project_file_map = {0: 0}
    updater.mw.data_store.block_names = {"0": "block0"}
    updater.mw.data_store.data = [["Str0"]]
    
    # We have problems
    updater.mw.data_store.problems_per_subline = {
        (0, 0, 0): {"prob1"},
    }
    
    problem_definitions = {
        "prob1": {"priority": 1, "name": "Width Error", "description": "Too long"}
    }
    updater.mw.current_game_rules.get_problem_definitions.return_value = problem_definitions
    
    # Run populate_blocks
    updater.populate_blocks()
    
    # The block list widget should have a top-level item (the compacted folder)
    # representing block 0 with the error count in brackets
    assert updater.mw.block_list_widget.topLevelItemCount() == 1
    item = updater.mw.block_list_widget.topLevelItem(0)
    
    assert item.text(0) == "CompactFolder / block0 (1)"
    assert "Width Error" in item.toolTip(0)


def test_MemePalaceChaptersLoadWorker():
    from core.mempalace_worker import MemePalaceChaptersLoadWorker
    mock_client = MagicMock()
    mock_client.get_all_chapters.return_value = [{"id": 1, "num": "Act 1, Ch 1"}]
    mock_client.get_all_chapter_mappings.return_value = {1: []}
    
    worker = MemePalaceChaptersLoadWorker(mock_client, "tp")
    
    signals_received = []
    def on_finished(chapters, mappings):
        signals_received.append((chapters, mappings))
        
    worker.finished_signal.connect(on_finished)
    worker.run() # Run synchronously for testing the run logic
    
    assert len(signals_received) == 1
    assert signals_received[0][0] == [{"id": 1, "num": "Act 1, Ch 1"}]
    assert signals_received[0][1] == {1: []}
    assert mock_client.get_all_chapters.called
    assert mock_client.get_all_chapter_mappings.called


def test_BlockListUpdater_async_chapters_loading(updater):
    # Setup Fake Client to bypass is_test check
    class FakeMemePalaceClient:
        def get_all_chapters(self, wing_name):
            return [{"id": 10, "num": "Act 1, Ch 1", "title": "Ordon Village"}]
        def get_all_chapter_mappings(self, wing_name):
            return {10: []}
            
    fake_client = FakeMemePalaceClient()
    
    # Mock translation_handler and prompt_composer
    composer = MagicMock()
    composer.prompt_composer._get_mempalace_client.return_value = fake_client
    composer.prompt_composer._get_wing_name.return_value = "tp"
    updater.mw.translation_handler = composer
    updater.mw._is_test_mode = False
    
    # Mock block list widget
    mock_item = QTreeWidgetItem()
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)

    
    # Run populate_blocks which starts the async load worker
    with patch('core.mempalace_worker.MemePalaceChaptersLoadWorker.start') as mock_start:
        updater.populate_blocks()
        assert mock_start.called # Worker start should be called
        
    # Check that tree shows loading placeholder
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = next((r for r in root_items if r.text(0) == "Chapters"), None)
    assert chapters_root is not None
    assert chapters_root.childCount() == 1
    assert chapters_root.child(0).text(0) == "Loading..."
    
    # Now simulate successful async load completion
    updater._on_chapters_loaded(
        [{"id": 10, "num": "Act 1, Ch 1", "title": "Ordon Village"}],
        {10: []}
    )
    
    # Re-fetch root items after populate_blocks is called again internally by slot
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = next((r for r in root_items if r.text(0) == "Chapters"), None)
    assert chapters_root is not None
    # Now the layout should have the actual chapter hierarchy populated from the cache
    assert chapters_root.childCount() == 1 # Act 1
    assert chapters_root.child(0).text(0) == "Act 1"
    
    # Now simulate load failure
    updater._on_chapters_load_failed("Network Timeout")
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = next((r for r in root_items if r.text(0) == "Chapters (Load Error)"), None)
    assert chapters_root is not None
    assert chapters_root.child(0).text(0) == "Error: Network Timeout"




