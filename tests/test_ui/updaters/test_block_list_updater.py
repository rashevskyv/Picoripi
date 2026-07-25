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


def test_virtual_parent_collects_all_unique_descendant_rows(mock_mw, mock_dp):
    updater = BlockListUpdater(mock_mw, mock_dp)
    root = QTreeWidgetItem(["Windows"])
    boss = QTreeWidgetItem(root, ["Boss name"])
    story = QTreeWidgetItem(boss, ["Story"])
    scene = QTreeWidgetItem(story, ["Scene"])
    scene.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2)])
    speakers = QTreeWidgetItem(boss, ["Speakers"])
    midna = QTreeWidgetItem(speakers, ["MIDNA"])
    midna.setData(0, Qt.UserRole + 13, [(0, 2), (1, 0)])

    assert updater._set_virtual_folder_mappings(root) == [(0, 1), (0, 2), (1, 0)]
    assert root.data(0, Qt.UserRole + 18) == "aggregate"
    assert boss.data(0, Qt.UserRole + 13) == [(0, 1), (0, 2), (1, 0)]
    assert story.data(0, Qt.UserRole + 13) == [(0, 1), (0, 2)]
    assert speakers.data(0, Qt.UserRole + 13) == [(0, 2), (1, 0)]


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


def test_manual_item_override_can_reassign_or_force_none(mock_mw, mock_dp):
    updater = BlockListUpdater(mock_mw, mock_dp)
    block = mock_mw.project_manager.project.blocks[0]
    block.metadata = {
        "story_context_assignments": {"0": {"item": "None"}}
    }

    assert updater._apply_manual_item_overrides({"Wallet": [(0, 0)]}) == {}

    block.metadata["story_context_assignments"]["0"]["item"] = "Boss Names"
    assert updater._apply_manual_item_overrides({"Wallet": [(0, 0)]}) == {
        "Boss Names": [(0, 0)]
    }


def test_manual_story_none_suppresses_normalized_story_link(mock_mw, mock_dp):
    updater = BlockListUpdater(mock_mw, mock_dp)
    mapping = StoryVirtualMapping("0", "Block Zero_Str_0", 0)
    folder = StoryVirtualFolder(10, "scene", "Scene", (), (mapping,))
    projection = StoryVirtualProjection(1, (folder,), ())
    mock_mw.project_manager.project.blocks[0].metadata = {
        "story_context_assignments": {"0": {"structure_id": "story:none"}}
    }

    assert updater._story_linked_rows(projection) == set()

    parent = QTreeWidgetItem(["Story"])
    assert updater._add_story_folder_item(parent, folder, None, hide_empty=True) is False


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


def test_virtual_block_cache_round_trips_without_requery(updater, mock_mw, mock_dp):
    mapping = StoryVirtualMapping("0", "zel_00_Str_1", 1)
    folder = StoryVirtualFolder(7, "chapter", "Intro", (), (mapping,))
    projection = StoryVirtualProjection(
        11,
        (folder,),
        (StoryVirtualSpeaker("MIDNA", (mapping,)),),
    )
    updater._story_projection_cache = projection
    updater._window_kind_groups_cache = {"Dialogue": {(0, 0), (1, 1)}}

    updater._persist_virtual_cache("tp", {"Wallet": [(1, 0)]})

    restored = BlockListUpdater(mock_mw, mock_dp)
    assert restored._restore_persisted_virtual_cache("tp") is True
    assert restored._story_projection_cache == projection
    assert restored._reference_item_groups_cache == {"Wallet": [(1, 0)]}
    assert restored._window_kind_groups_cache == {"Dialogue": {(0, 0), (1, 1)}}


def test_virtual_ready_callback_waits_for_story_worker(updater):
    callback = MagicMock()
    updater._is_loading_chapters = True

    updater.when_virtual_blocks_ready(callback)
    callback.assert_not_called()

    updater._notify_virtual_blocks_ready()
    callback.assert_called_once_with()


def test_story_worker_starts_while_startup_splash_exists(updater):
    worker = MagicMock()
    worker.isRunning.return_value = False
    updater._chapters_load_worker = worker
    updater.mw._startup_splash = MagicMock()

    updater._start_chapters_worker_when_ready()

    worker.start.assert_called_once_with()

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
                "translator_note": "System status text",
                "notated": True,
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
    descriptions = next(
        windows_root.child(i)
        for i in range(windows_root.childCount())
        if windows_root.child(i).text(0) == "Descriptions / save"
    )
    description_children = [
        descriptions.child(i).text(0) for i in range(descriptions.childCount())
    ]
    assert "Story" in description_children
    assert "Speakers" in description_children
    assert "Items" not in description_children

    dialogue = next(
        windows_root.child(i)
        for i in range(windows_root.childCount())
        if windows_root.child(i).text(0) == "Dialogue"
    )
    dialogue_children = [
        dialogue.child(i).text(0) for i in range(dialogue.childCount())
    ]
    assert "Story" not in dialogue_children
    assert "Speakers" not in dialogue_children

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
    assert unbound.data(0, Qt.UserRole + 17) == "unbound"

    notated_root = next(item for item in roots if item.text(0) == "Notated")
    noted = next(
        notated_root.child(i)
        for i in range(notated_root.childCount())
        if notated_root.child(i).text(0) == "Notated"
    )
    assert noted.data(0, Qt.UserRole) == -5
    assert noted.data(0, Qt.UserRole + 13) == [(0, 0)]

    nested_notated = next(
        descriptions.child(i)
        for i in range(descriptions.childCount())
        if descriptions.child(i).text(0) == "Notated"
    )
    assert nested_notated.child(0).data(0, Qt.UserRole + 13) == [(0, 0)]


def test_BlockListUpdater_hides_virtual_folders_that_only_contain_none(updater):
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
    assert all(item.text(0) not in {"Story", "Speakers", "Items"} for item in roots)

    windows_root = next(item for item in roots if item.text(0) == "Windows")
    window_kind = windows_root.child(0)
    assert window_kind.childCount() == 1
    window_none = window_kind.child(0)
    assert window_none.text(0) == "None"
    assert window_none.data(0, Qt.UserRole + 13) == [(0, 0), (1, 0), (1, 1)]


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
