import pytest
from core.data_store import AppDataStore, ViewKind


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
    assert store.current_view_kind == ViewKind.PHYSICAL
    assert store.is_virtual_view is False
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
    assert store.current_view_kind == ViewKind.PHYSICAL
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


def test_AppDataStore_displayed_string_indices_properties(store):
    # Test default
    assert store.displayed_string_indices == []

    # Test setting and O(1) map generation
    test_indices = [0, 5, (1, 2), 10]
    store.displayed_string_indices = test_indices
    assert store.displayed_string_indices == test_indices

    # Verify positions
    assert store.get_displayed_index_pos(0) == 0
    assert store.get_displayed_index_pos(5) == 1
    assert store.get_displayed_index_pos((1, 2)) == 2
    assert store.get_displayed_index_pos(10) == 3
    assert store.get_displayed_index_pos(99) == -1  # Not found


def test_AppDataStore_displayed_string_indices_preserves_list_index_semantics(store):
    store.displayed_string_indices = [5, 7, 5]

    assert store.displayed_string_indices.index(5) == 0
    assert store.get_displayed_index_pos(5) == 0


@pytest.mark.parametrize(
    ("kind", "token"),
    [
        (ViewKind.PHYSICAL, 7),
        (ViewKind.CATEGORY, 7),
        (ViewKind.CHAPTER, -2),
        (ViewKind.SPEAKER, -3),
        (ViewKind.ITEM, -4),
        (ViewKind.NOTATED, -5),
    ],
)
def test_view_kind_never_replaces_physical_address(store, kind, token):
    store.physical_block_idx = 7
    store.current_string_idx = 12

    store.set_view_kind(kind)

    assert store.current_block_idx == 7
    assert store.physical_block_idx == 7
    assert store.current_string_idx == 12
    assert store.view_block_token == token
    assert store.is_virtual_view is (kind != ViewKind.PHYSICAL)


def test_physical_block_setter_keeps_canonical_addresses_in_sync(store):
    store.set_view_kind(ViewKind.SPEAKER)

    store.physical_block_idx = 9

    assert store.current_block_idx == 9
    assert store.physical_block_idx == 9
    assert store.view_block_token == -3


@pytest.mark.parametrize("kind", list(ViewKind))
def test_session_snapshot_round_trips_view_and_physical_identity(store, kind):
    store.physical_block_idx = 4
    store.current_string_idx = 8
    store.set_view_kind(kind)
    store.current_chapter_id = 77
    store.current_speaker_name = "MIDNA"
    store.chapter_mappings = [(4, 8), (6, 2)]

    restored = AppDataStore()
    assert restored.restore_from_snapshot(store.get_session_snapshot()) is True

    assert restored.current_block_idx == 4
    assert restored.physical_block_idx == 4
    assert restored.current_string_idx == 8
    assert restored.current_view_kind == kind
    assert restored.current_chapter_id == 77
    assert restored.current_speaker_name == "MIDNA"
    assert restored.chapter_mappings == [(4, 8), (6, 2)]


@pytest.mark.parametrize(
    ("legacy_block", "kind"),
    [
        (-2, ViewKind.CHAPTER),
        (-3, ViewKind.SPEAKER),
        (-4, ViewKind.ITEM),
        (-5, ViewKind.NOTATED),
    ],
)
def test_legacy_negative_session_migrates_to_explicit_view(store, legacy_block, kind):
    snapshot = store.get_session_snapshot()
    snapshot.pop("current_view_kind")
    snapshot["current_block_idx"] = legacy_block
    snapshot["_physical_block_idx"] = 5
    snapshot["current_string_idx"] = 3

    restored = AppDataStore()
    assert restored.restore_from_snapshot(snapshot) is True

    assert restored.current_block_idx == 5
    assert restored.physical_block_idx == 5
    assert restored.current_string_idx == 3
    assert restored.current_view_kind == kind
    assert restored.view_block_token == legacy_block


def test_session_restore_clears_show_unsaved_only_filters(store):
    store.show_unsaved_only = True
    store.show_unsaved_blocks_only = True
    snapshot = store.get_session_snapshot()
    assert snapshot["show_unsaved_only"] is True
    assert snapshot["show_unsaved_blocks_only"] is True

    restored = AppDataStore()
    assert restored.restore_from_snapshot(snapshot) is True
    assert restored.show_unsaved_only is False
    assert restored.show_unsaved_blocks_only is False
