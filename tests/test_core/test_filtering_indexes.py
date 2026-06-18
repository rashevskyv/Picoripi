import pytest
from unittest.mock import MagicMock
from core.data_store import AppDataStore, IndexingDict
from core.data_state_processor import DataStateProcessor

def test_indexing_dict_callbacks():
    callback_keys = []
    def callback(key):
        callback_keys.append(key)

    d = IndexingDict(on_change_callback=callback)

    # Test setitem
    d["test_key"] = "value"
    assert callback_keys == ["test_key"]

    # Test delitem
    del d["test_key"]
    assert callback_keys == ["test_key", "test_key"]

    # Test clear
    d["another"] = 123
    callback_keys.clear()
    d.clear()
    assert callback_keys == [None]

    # Test update
    callback_keys.clear()
    d.update({"a": 1})
    assert callback_keys == [None]

def test_lazy_index_initialization():
    mw = MagicMock()
    store = AppDataStore()
    mw.data_store = store

    # Set mock data: 2 blocks
    store.data = [
        ["Line 0", "", "Line 2"],
        ["Another 0", "Another 1"]
    ]

    # Set default values for metadata & settings
    mw.default_font_file = "default"
    mw.game_dialog_max_width_pixels = 300
    mw.string_metadata = {}

    # Set project manager Mock
    pm = MagicMock()
    pm.project = MagicMock()
    block0 = MagicMock()
    block0.get_categorized_line_indices.return_value = {2}
    pm.project.blocks = [block0]
    mw.project_manager = pm
    mw.block_to_project_file_map = {0: 0}

    processor = DataStateProcessor(mw)

    # 1. Test empty set
    empty_set = processor.get_empty_set(0)
    assert empty_set == {1}
    assert 0 in store._index_empty
    assert store._index_empty[0] == {1}

    # 2. Test translated set (no translations yet, needs translation is True for non-empty)
    # mock needs_translation and is_string_translated
    processor.string_needs_translation = MagicMock(return_value=True)
    processor.is_string_translated = MagicMock(side_effect=lambda b, s: s == 2)

    translated_set = processor.get_translated_set(0)
    assert translated_set == {2}
    assert store._index_translated[0] == {2}

    # 3. Test unsaved set
    store.edited_data[(0, 0)] = "Edited Line 0"
    unsaved_set = processor.get_unsaved_set(0)
    assert unsaved_set == {0}
    assert store._index_unsaved[0] == {0}

    # 4. Test overrides set
    mw.string_metadata[(0, 2)] = {"width": 150} # Has custom width override
    overrides_set = processor.get_overrides_set(0)
    assert overrides_set == {2}
    assert store._index_overrides[0] == {2}

    # 5. Test categorized set
    cat_set = processor.get_categorized_set(0)
    assert cat_set == {2}
    assert store._index_categorized[0] == {2}

def test_index_invalidation_on_data_change():
    store = AppDataStore()
    store._index_empty[0] = {1}
    store._index_translated[0] = {2}

    # Write to data property
    store.data = [["new"]]

    # Verify indexes are cleared
    assert len(store._index_empty) == 0
    assert len(store._index_translated) == 0

def test_incremental_index_updates():
    mw = MagicMock()
    store = AppDataStore()
    mw.data_store = store

    # String 0: original empty, but has active unsaved translation
    # String 1: original non-empty, no translation
    store.data = [
        ["", "Original 1"]
    ]
    store.edited_data[(0, 0)] = "Not empty translation"

    processor = DataStateProcessor(mw)

    # Trigger lazy load
    processor.get_empty_set(0)
    processor.get_translated_set(0)
    processor.get_unsaved_set(0)

    assert store._index_empty[0] == set()  # since string 0 has a translation
    assert store._index_translated[0] == set()
    assert store._index_unsaved[0] == {0}

    # Update string 0 to empty string (which removes it from edited_data as it matches empty original)
    processor.update_edited_data(0, 0, "", skip_ui_refresh=True)
    assert 0 in store._index_empty[0]
    assert 0 not in store._index_unsaved[0]

    # Update string 1 to translated string
    processor.is_string_translated = MagicMock(return_value=True)
    processor.update_edited_data(0, 1, "Translated 1", skip_ui_refresh=True)
    assert 1 in store._index_translated[0]
    assert 1 in store._index_unsaved[0]

def test_warnings_index_lazy_and_invalidation():
    mw = MagicMock()
    store = AppDataStore()
    mw.data_store = store

    processor = DataStateProcessor(mw)

    # Populate problems
    store.problems_per_subline[(0, 0, 0)] = {"Width"}
    store.problems_per_subline[(0, 1, 0)] = {"TagError"}

    # Ensure index built
    processor.ensure_index_warnings(0)
    assert store._index_warnings[0]["Width"] == {(0, 0)}
    assert store._index_warnings[0]["TagError"] == {(1, 0)}

    # Invalidate by editing problems dict
    store.problems_per_subline[(0, 0, 0)] = {"Width", "TagError"}
    assert 0 not in store._index_warnings

    # Rebuild
    processor.ensure_index_warnings(0)
    assert store._index_warnings[0]["Width"] == {(0, 0)}
    assert store._index_warnings[0]["TagError"] == {(0, 0), (1, 0)}
