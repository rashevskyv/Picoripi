from unittest.mock import MagicMock
from core.translation.block_classifier import classify_project_items, ClassifiedProjectItems


def test_classify_empty_data():
    res = classify_project_items([])
    assert isinstance(res, ClassifiedProjectItems)
    assert len(res.story_items) == 0
    assert len(res.semantic_items) == 0
    assert res.total_count == 0


def test_classify_by_script_mapping():
    data = [
        ["Line 0 from Block 0", "Line 1 from Block 0"],
        ["Line 0 from Block 1", "Line 1 from Block 1"],
    ]

    mock_client = MagicMock()
    # Mock script lines: Block 1 Str 0 comes first in script (line 10), Block 0 Str 1 is line 20,
    # Block 0 Str 0 is unmapped (None), Block 1 Str 1 is 999999
    def mock_get_mapping(wing, bmg_id):
        if bmg_id == "Block 2_Str_0":
            return {"script_line": 10}
        if bmg_id == "Block 1_Str_1":
            return {"script_line": 20}
        return None

    mock_client.get_script_mapping.side_effect = mock_get_mapping

    mock_composer = MagicMock()
    mock_composer._get_mempalace_client.return_value = mock_client
    mock_composer._get_wing_name.return_value = "zelda_wing"
    mock_composer._get_block_label.side_effect = lambda idx: f"Block {idx + 1}"

    mock_mw = MagicMock()
    mock_mw.translation_handler.prompt_composer = mock_composer

    res = classify_project_items(data, mock_mw)

    assert res.has_story
    assert res.has_semantic
    # Story items should have Block 1 Str 0 first, then Block 0 Str 1
    assert len(res.story_items) == 2
    # Coordinates of first story item
    first_story_coords = res.story_temp_id_map[0]
    assert first_story_coords == (1, 0)
    second_story_coords = res.story_temp_id_map[1]
    assert second_story_coords == (0, 1)

    # Remaining items should be in semantic items
    assert len(res.semantic_items) == 2


def test_classify_by_block_name_heuristics():
    # When no client is present, semantic names are classified accordingly
    data = [
        ["Buy a potion", "10 Rupees"],  # Block 0: shop
        ["Welcome, hero!", "The world needs you."],  # Block 1: story
    ]

    mock_mw = MagicMock()
    mock_mw.translation_handler.prompt_composer._get_mempalace_client.return_value = None
    mock_mw.data_store.block_names = {"0": "Shop_Bazaar", "1": "Story_Intro"}

    res = classify_project_items(data, mock_mw)
    assert len(res.story_items) == 2
    assert len(res.semantic_items) == 2
    assert res.story_items[0]["text"] == "Welcome, hero!"
    assert res.semantic_items[0]["text"] == "Buy a potion"
