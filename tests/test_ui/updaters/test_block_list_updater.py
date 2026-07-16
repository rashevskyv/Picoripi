import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from ui.updaters.block_list_updater import BlockListUpdater
from core.mempalace.story_timeline import (
    StoryVirtualFolder,
    StoryVirtualMapping,
    StoryVirtualProjection,
    StoryVirtualSpeaker,
)

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
    mw._is_test_mode = True
    from core.filter_query_api import FilterQueryAPI
    mw.filter_query_api = FilterQueryAPI(mw)
    mw.data_store.displayed_string_indices = []
    return mw

@pytest.fixture
def mock_dp(mock_mw):
    dp = MagicMock()
    dp.get_current_string_text.side_effect = lambda b, s: (f"Text {b} {s}", None)

    def ensure_index_warnings(block_idx):
        store = mock_mw.data_store
        if isinstance(getattr(store, '_index_warnings', None), MagicMock) or not hasattr(store, '_index_warnings'):
            store._index_warnings = {}
        if block_idx not in store._index_warnings:
            warn_dict = {}
            problems_dict = getattr(store, 'problems_per_subline', {})
            if isinstance(problems_dict, MagicMock):
                problems_dict = {}
            for (b_idx, s_idx, subline_idx), problems in problems_dict.items():
                if b_idx == block_idx:
                    for p_id in problems:
                        if p_id not in warn_dict:
                            warn_dict[p_id] = set()
                        warn_dict[p_id].add((s_idx, subline_idx))
            store._index_warnings[block_idx] = warn_dict

    def get_unsaved_set(block_idx):
        store = mock_mw.data_store
        unsaved_set = set()
        for (b_idx, s_idx) in getattr(store, 'edited_data', {}).keys():
            if b_idx == block_idx:
                unsaved_set.add(s_idx)
        return unsaved_set

    def get_empty_set(block_idx):
        store = mock_mw.data_store
        empty_set = set()
        if block_idx < len(store.data):
            block_data = store.data[block_idx]
            for s_idx in range(len(block_data)):
                orig = block_data[s_idx]
                curr = orig
                if (not orig or not orig.strip()) and (not curr or not str(curr).strip()):
                    empty_set.add(s_idx)
        return empty_set

    dp.ensure_index_warnings.side_effect = ensure_index_warnings
    dp.get_unsaved_set.side_effect = get_unsaved_set
    dp.get_empty_set.side_effect = get_empty_set
    return dp


def test_reference_item_mappings_are_separate_from_speakers(mock_mw, mock_dp):
    mock_mw.data_store.data = [["Wallet\nA wallet from your childhood.", "Unrelated dialogue"]]
    reference = MagicMock(name="reference")
    reference.name = "Wallet"
    reference.description = "A wallet from your childhood."
    client = MagicMock()
    client.get_reference_items.return_value = (reference,)
    updater = BlockListUpdater(mock_mw, mock_dp)

    mappings, reverse = updater._reference_item_mappings(client, 1)

    assert mappings == {"Wallet": [(0, 0)]}
    assert reverse == {(0, 0): "Wallet"}


def test_empty_virtual_leaf_is_not_added(updater):
    root = QTreeWidgetItem(["Root"])

    item = updater._add_virtual_role_leaf(
        root,
        "None",
        -3,
        Qt.UserRole + 15,
        "None",
        [],
    )

    assert item is None
    assert root.childCount() == 0

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

    # Find the normalized Story root node in the block list widget
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = None
    for r in root_items:
        if r.text(0) == "Story":
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


def test_BlockListUpdater_populates_normalized_story_and_speaker_folders(updater):
    updater.mw.data_store.data[1].append("Loose")
    mapping = StoryVirtualMapping("1", "zel_01_Str_1", 1)
    scene = StoryVirtualFolder(30, "scene", "Scene One", (), (mapping,))
    chapter = StoryVirtualFolder(20, "chapter", "Chapter One", (scene,), (mapping,))
    act = StoryVirtualFolder(10, "act", "Act One", (chapter,), (mapping,))
    projection = StoryVirtualProjection(
        1,
        (act,),
        (StoryVirtualSpeaker("MIDNA", (mapping,)),),
    )
    client = MagicMock()
    client.get_story_virtual_projection.return_value = projection
    reference = MagicMock()
    reference.name = "Str1"
    reference.description = ""
    client.get_reference_items.return_value = (reference,)
    composer = MagicMock()
    composer.prompt_composer._get_mempalace_client.return_value = client
    composer.prompt_composer._get_wing_name.return_value = "tp"
    updater.mw.translation_handler = composer
    updater.mw.data_store.current_block_idx = -1
    updater.mw.data_store.current_chapter_id = None
    updater.mw.data_store.current_speaker_name = None
    updater.mw.data_store.show_unsaved_blocks_only = False
    updater.mw.data_store.edited_data = {}
    updater.mw.current_game_rules.get_preview_window_style.side_effect = (
        lambda block_idx, string_idx: {
            "kind_name": (
                "Descriptions / save"
                if (block_idx, string_idx) in {(0, 0), (1, 1)}
                else "Dialogue"
            )
        }
    )
    updater.mw.project_manager.project.blocks[0].metadata = {
        "character_assignments": {"0": "STALE SPEAKER"},
        "story_context_assignments": {
            "0": {
                "speaker": "SYSTEM",
                "structure_id": 30,
                "structure_path": ["Act One", "Chapter One", "Scene One"],
            }
        },
    }

    updater.populate_blocks()

    roots = [
        updater.mw.block_list_widget.topLevelItem(i)
        for i in range(updater.mw.block_list_widget.topLevelItemCount())
    ]
    story_root = next(item for item in roots if item.text(0) == "Story")
    scene_item = story_root.child(0).child(0).child(0)
    assert scene_item.text(0) == "Scene One"
    assert scene_item.data(0, Qt.UserRole) == -2
    assert scene_item.data(0, Qt.UserRole + 11) == 30
    assert scene_item.data(0, Qt.UserRole + 13) == [(1, 1), (0, 0)]

    speakers_root = next(item for item in roots if item.text(0) == "Speakers")
    midna = next(
        speakers_root.child(i)
        for i in range(speakers_root.childCount())
        if speakers_root.child(i).text(0) == "MIDNA"
    )
    assert midna.data(0, Qt.UserRole + 13) == [(1, 1)]
    system = next(
        speakers_root.child(i)
        for i in range(speakers_root.childCount())
        if speakers_root.child(i).data(0, Qt.UserRole + 15) == "SYSTEM"
    )
    assert system.data(0, Qt.UserRole + 13) == [(0, 0)]
    unassigned = next(
        speakers_root.child(i)
        for i in range(speakers_root.childCount())
        if speakers_root.child(i).data(0, Qt.UserRole + 15) == "None"
    )
    assert unassigned.data(0, Qt.UserRole + 13) == [(1, 0), (1, 2)]
    assert all(
        speakers_root.child(i).text(0) != "STALE SPEAKER"
        for i in range(speakers_root.childCount())
    )

    story_none = next(
        story_root.child(i)
        for i in range(story_root.childCount())
        if story_root.child(i).text(0) == "None"
    )
    assert story_none.data(0, Qt.UserRole + 13) == [(1, 0), (1, 2)]

    items_root = next(item for item in roots if item.text(0) == "Items")
    item_str1 = next(
        items_root.child(i)
        for i in range(items_root.childCount())
        if items_root.child(i).data(0, Qt.UserRole + 16) == "Str1"
    )
    assert item_str1.data(0, Qt.UserRole + 13) == [(1, 0)]
    items_none = next(
        items_root.child(i)
        for i in range(items_root.childCount())
        if items_root.child(i).data(0, Qt.UserRole + 16) == "None"
    )
    assert items_none.data(0, Qt.UserRole + 13) == [(0, 0), (1, 1), (1, 2)]

    # Every row has a Window binding, so an empty global None is omitted.
    assert all(item.text(0) != "None" for item in roots)

    windows_root = next(item for item in roots if item.text(0) == "Windows")
    dialogue = next(
        windows_root.child(i)
        for i in range(windows_root.childCount())
        if windows_root.child(i).text(0) == "Dialogue"
    )
    nested_story = next(
        dialogue.child(i)
        for i in range(dialogue.childCount())
        if dialogue.child(i).text(0) == "Story"
    )
    nested_story_none = next(
        nested_story.child(i)
        for i in range(nested_story.childCount())
        if nested_story.child(i).text(0) == "None"
    )
    assert nested_story_none.data(0, Qt.UserRole + 13) == [(1, 0), (1, 2)]

    nested_speakers = next(
        dialogue.child(i)
        for i in range(dialogue.childCount())
        if dialogue.child(i).text(0) == "Speakers"
    )
    nested_speaker_none = nested_speakers.child(0)
    assert nested_speaker_none.data(0, Qt.UserRole + 15) == "None"
    assert nested_speaker_none.data(0, Qt.UserRole + 13) == [(1, 0), (1, 2)]

    nested_items = next(
        dialogue.child(i)
        for i in range(dialogue.childCount())
        if dialogue.child(i).text(0) == "Items"
    )
    nested_items_none = nested_items.child(0)
    assert nested_items_none.data(0, Qt.UserRole + 16) == "None"
    assert nested_items_none.data(0, Qt.UserRole + 13) == [(1, 2)]

    unbound = next(
        dialogue.child(i)
        for i in range(dialogue.childCount())
        if dialogue.child(i).text(0) == "None"
    )
    assert unbound.data(0, Qt.UserRole + 13) == [(1, 2)]


def test_BlockListUpdater_shows_none_when_no_rows_have_speakers(updater):
    projection = StoryVirtualProjection(1, (), ())
    client = MagicMock()
    client.get_story_virtual_projection.return_value = projection
    composer = MagicMock()
    composer.prompt_composer._get_mempalace_client.return_value = client
    composer.prompt_composer._get_wing_name.return_value = "tp"
    updater.mw.translation_handler = composer
    updater.mw.data_store.current_block_idx = -1
    updater.mw.data_store.current_chapter_id = None
    updater.mw.data_store.current_speaker_name = None
    updater.mw.data_store.show_unsaved_blocks_only = False
    updater.mw.data_store.edited_data = {}
    updater.mw.project_manager.project.blocks[0].metadata = {}

    updater.populate_blocks()

    roots = [
        updater.mw.block_list_widget.topLevelItem(i)
        for i in range(updater.mw.block_list_widget.topLevelItemCount())
    ]
    speakers_root = next(item for item in roots if item.text(0) == "Speakers")
    assert speakers_root.childCount() == 1
    none_item = speakers_root.child(0)
    assert none_item.data(0, Qt.UserRole + 15) == "None"
    assert none_item.data(0, Qt.UserRole + 13) == [(0, 0), (1, 0), (1, 1)]


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

    # The compacted folder remains present alongside the required Speakers/None block.
    item = next(
        updater.mw.block_list_widget.topLevelItem(i)
        for i in range(updater.mw.block_list_widget.topLevelItemCount())
        if updater.mw.block_list_widget.topLevelItem(i).text(0).startswith("CompactFolder")
    )

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
    chapters_root = next((r for r in root_items if r.text(0) == "Story"), None)
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
    chapters_root = next((r for r in root_items if r.text(0) == "Story"), None)
    assert chapters_root is not None
    # Now the layout should have the actual chapter hierarchy populated from the cache
    assert chapters_root.childCount() == 1 # Act 1
    assert chapters_root.child(0).text(0) == "Act 1"

    # Now simulate load failure
    updater._on_chapters_load_failed("Network Timeout")
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    chapters_root = next((r for r in root_items if r.text(0) == "Story (Load Error)"), None)
    assert chapters_root is not None
    assert chapters_root.child(0).text(0) == "Error: Network Timeout"


def test_BlockListUpdater_populate_blocks_show_unsaved_only(updater):
    # Setup mock item creator on main window's block list widget
    mock_item = QTreeWidgetItem()
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)

    # 1. Enable show_unsaved_blocks_only filter
    updater.mw.data_store.show_unsaved_blocks_only = True
    # Mark block 0 as unsaved, block 1 remains clean
    updater.mw.data_store.unsaved_block_indices = {0}
    updater.mw.data_store.edited_data = {(0, 0): "Edited string"}

    # Run in Legacy mode (project_manager is None)
    updater.mw.project_manager = None
    updater.mw.translation_handler = None

    updater.populate_blocks()

    # create_item should be called only 1 time (for block 0) because block 1 is clean and filtered out
    assert updater.mw.block_list_widget.create_item.call_count == 1

    # Reset mock and widget state
    updater.mw.block_list_widget.create_item.reset_mock()
    updater.mw.block_list_widget.clear()

    # 2. Run in Virtual structure mode
    pm = MagicMock()
    pm.project.blocks = []

    block0 = MagicMock()
    block0.id = "b0"
    block0.source_file = "src/block0.txt"
    pm.project.blocks.append(block0)

    block1 = MagicMock()
    block1.id = "b1"
    block1.source_file = "src/block1.txt"
    pm.project.blocks.append(block1)

    # Clean folder (should be filtered out because it only has clean block 1)
    folder1 = MagicMock()
    folder1.id = "folder_1"
    folder1.name = "CleanFolder"
    folder1.is_expanded = True
    folder1.children = []
    folder1.block_ids = ["b1"]

    # Dirty folder (should be shown because it contains dirty block 0)
    folder0 = MagicMock()
    folder0.id = "folder_0"
    folder0.name = "DirtyFolder"
    folder0.is_expanded = True
    folder0.children = []
    folder0.block_ids = ["b0"]

    pm.project.virtual_folders = [folder1, folder0]
    pm.project.metadata = {}
    pm.SOURCES_DIR = "src"
    updater.mw.project_manager = pm

    # Mock create_item to return a fresh item each time so it can be added to tree
    updater.mw.block_list_widget.create_item = MagicMock(side_effect=lambda name, idx, role: QTreeWidgetItem([name]))

    updater.populate_blocks()

    # Let's verify topLevelItems
    root_items = [updater.mw.block_list_widget.topLevelItem(i) for i in range(updater.mw.block_list_widget.topLevelItemCount())]
    # CleanFolder should be omitted completely, DirtyFolder (which compacts with block0) should be present
    folder_names = [r.text(0) for r in root_items]
    assert any("DirtyFolder" in f for f in folder_names)
    assert not any("CleanFolder" in f for f in folder_names)
