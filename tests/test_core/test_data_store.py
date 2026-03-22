import pytest
from core.data_store import AppDataStore


@pytest.fixture
def store():
    return AppDataStore()


def test_AppDataStore_defaults(store):
    assert store.json_path is None
    assert store.edited_json_path is None
    assert store.data == []
    assert store.edited_data == {}
    assert store.unsaved_changes is False
    assert store.unsaved_block_indices == set()
    assert store.current_block_idx == -1
    assert store.current_string_idx == -1


def test_AppDataStore_mark_dirty(store):
    store.mark_dirty(0)
    assert store.unsaved_changes is True
    assert 0 in store.unsaved_block_indices

    store.mark_dirty(3)
    assert 3 in store.unsaved_block_indices
    assert 0 in store.unsaved_block_indices


def test_AppDataStore_mark_clean_single_block(store):
    store.mark_dirty(0)
    store.mark_dirty(1)
    store.mark_clean(0)
    assert 0 not in store.unsaved_block_indices
    assert 1 in store.unsaved_block_indices
    assert store.unsaved_changes is True  # Still dirty because block 1 remains


def test_AppDataStore_mark_clean_all_blocks(store):
    store.mark_dirty(0)
    store.mark_dirty(1)
    store.mark_clean()
    assert store.unsaved_changes is False
    assert store.unsaved_block_indices == set()


def test_AppDataStore_mark_clean_last_block_clears_unsaved(store):
    store.mark_dirty(5)
    store.mark_clean(5)
    assert store.unsaved_changes is False
    assert store.unsaved_block_indices == set()


def test_AppDataStore_clear(store):
    store.json_path = "/some/path.json"
    store.data = [["line1", "line2"]]
    store.edited_data = {0: ["edited"]}
    store.unsaved_changes = True
    store.unsaved_block_indices = {0}
    store.current_block_idx = 2
    store.current_string_idx = 1
    store.problems_per_subline = {0: {"TOO_LONG"}}

    store.clear()

    assert store.json_path is None
    assert store.data == []
    assert store.edited_data == {}
    assert store.unsaved_changes is False
    assert store.unsaved_block_indices == set()
    assert store.current_block_idx == -1
    assert store.current_string_idx == -1
    assert store.problems_per_subline == {}


def test_AppDataStore_mark_dirty_multiple_blocks(store):
    for i in range(10):
        store.mark_dirty(i)
    assert len(store.unsaved_block_indices) == 10
    assert store.unsaved_changes is True


def test_AppDataStore_mark_clean_nonexistent_block(store):
    # Should not raise an error when block isn't in the set
    store.mark_clean(999)
    assert store.unsaved_changes is False
