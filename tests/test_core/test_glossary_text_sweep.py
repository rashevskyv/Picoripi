"""Tests for the pass-1a chunk packer (core/glossary_build/text_sweep.py)."""
from core.glossary_build.text_sweep import (
    CHUNK_SIZE_PRESETS,
    DEFAULT_CHUNK_SIZE,
    SweepChunk,
    SweepItem,
    items_from_dataset,
    pack_chunks,
    resolve_chunk_size,
)


def _item(block, string, text):
    return SweepItem(block_idx=block, string_idx=string, text=text)


class TestResolveChunkSize:
    def test_preset_names_map_to_values(self):
        assert resolve_chunk_size("local") == CHUNK_SIZE_PRESETS["local"]
        assert resolve_chunk_size("balanced") == CHUNK_SIZE_PRESETS["balanced"]
        assert resolve_chunk_size("cloud") == CHUNK_SIZE_PRESETS["cloud"]

    def test_preset_is_case_insensitive(self):
        assert resolve_chunk_size("  CLOUD ") == CHUNK_SIZE_PRESETS["cloud"]

    def test_unknown_preset_falls_back_to_default(self):
        assert resolve_chunk_size("gigantic") == DEFAULT_CHUNK_SIZE

    def test_numeric_value_is_clamped(self):
        assert resolve_chunk_size(10) == 500  # below minimum
        assert resolve_chunk_size(999999) == 32000  # above maximum

    def test_non_positive_and_garbage_use_default(self):
        assert resolve_chunk_size(0) == DEFAULT_CHUNK_SIZE
        assert resolve_chunk_size(-5) == DEFAULT_CHUNK_SIZE
        assert resolve_chunk_size(None) == DEFAULT_CHUNK_SIZE


class TestPackChunks:
    def test_whole_items_packed_until_budget(self):
        items = [_item(0, i, "abcd") for i in range(6)]  # 4 chars each
        # budget 500 (min) fits all six with newline separators easily
        chunks = pack_chunks(items, 500)
        assert len(chunks) == 1
        assert len(chunks[0].items) == 6

    def test_new_chunk_starts_when_budget_would_be_exceeded(self):
        # Each item 400 chars; budget 500 -> only one per chunk.
        items = [_item(0, i, "x" * 400) for i in range(3)]
        chunks = pack_chunks(items, 500)
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk.items) == 1

    def test_item_is_never_split(self):
        # No fragment of an item's text should be cut: every item's text appears
        # whole inside exactly one chunk.
        items = [_item(0, i, f"term-{i}-" + "y" * 300) for i in range(5)]
        chunks = pack_chunks(items, 500)
        rejoined = [it.text for chunk in chunks for it in chunk.items]
        assert rejoined == [it.text for it in items]
        for chunk in chunks:
            for it in chunk.items:
                assert it.text in chunk.text

    def test_oversized_item_goes_alone_unsplit(self):
        big = _item(0, 0, "z" * 40000)  # exceeds max budget
        small = _item(0, 1, "small")
        chunks = pack_chunks([big, small], "balanced")
        assert chunks[0].items == (big,)
        assert chunks[0].text == big.text  # unsplit
        assert chunks[0].is_over_budget

    def test_empty_and_whitespace_items_skipped(self):
        items = [_item(0, 0, ""), _item(0, 1, "   "), _item(0, 2, "real")]
        chunks = pack_chunks(items, 500)
        assert len(chunks) == 1
        assert len(chunks[0].items) == 1
        assert chunks[0].items[0].text == "real"

    def test_empty_input_yields_no_chunks(self):
        assert pack_chunks([], 500) == []

    def test_provenance_preserved(self):
        items = [_item(3, 7, "hello"), _item(3, 9, "world")]
        chunks = pack_chunks(items, 500)
        coords = [(it.block_idx, it.string_idx) for it in chunks[0].items]
        assert coords == [(3, 7), (3, 9)]

    def test_custom_weigh_function(self):
        # Weigh every string as 100 regardless of length; budget 500 -> 5 per chunk
        items = [_item(0, i, "a") for i in range(11)]
        chunks = pack_chunks(items, 500, weigh=lambda _t: 100)
        # separator also weighs 100, so first item 100, each extra 200 -> 100+200*n<=500 => n<=2 -> 3 items
        sizes = [len(c.items) for c in chunks]
        assert sum(sizes) == 11
        assert max(sizes) <= 3


class TestItemsFromDataset:
    def test_flattens_all_blocks(self):
        dataset = [["a", "b"], ["c"]]
        items = items_from_dataset(dataset)
        assert [(i.block_idx, i.string_idx, i.text) for i in items] == [
            (0, 0, "a"),
            (0, 1, "b"),
            (1, 0, "c"),
        ]

    def test_block_indices_restricts_area(self):
        dataset = [["a"], ["b"], ["c"]]
        items = items_from_dataset(dataset, block_indices=[2, 0])
        assert [i.block_idx for i in items] == [2, 0]

    def test_out_of_range_block_indices_ignored(self):
        dataset = [["a"]]
        items = items_from_dataset(dataset, block_indices=[0, 99, -1])
        assert [i.block_idx for i in items] == [0]

    def test_none_and_blank_strings_skipped(self):
        dataset = [["keep", None, "  ", "also"]]
        items = items_from_dataset(dataset)
        assert [i.text for i in items] == ["keep", "also"]

    def test_non_list_block_skipped(self):
        dataset = [["ok"], "not-a-block", ["fine"]]
        items = items_from_dataset(dataset)
        assert [i.block_idx for i in items] == [0, 2]
