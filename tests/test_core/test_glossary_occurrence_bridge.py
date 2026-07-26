"""Tests for the pass-1b occurrence bridge (core/glossary_build/occurrence_bridge.py)."""
from core.glossary_build.context_window import Occurrence
from core.glossary_build.occurrence_bridge import occurrences_by_term, to_occurrences
from core.glossary_manager import GlossaryManager, GlossaryOccurrence, GlossaryEntry


def _occ(block, string):
    entry = GlossaryEntry(original="X", translation="Х")
    return GlossaryOccurrence(
        entry=entry, block_idx=block, string_idx=string, line_idx=0, start=0, end=1, line_text=""
    )


class TestToOccurrences:
    def test_converts_coordinates(self):
        result = to_occurrences([_occ(1, 2), _occ(3, 4)])
        assert result == [Occurrence(1, 2), Occurrence(3, 4)]

    def test_dedups_same_row(self):
        # two hits in block 0 string 5 -> one Occurrence
        result = to_occurrences([_occ(0, 5), _occ(0, 5)])
        assert result == [Occurrence(0, 5)]

    def test_empty(self):
        assert to_occurrences([]) == []


class TestOccurrencesByTerm:
    def _manager(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("Link", "Лінк", "")
        m.add_entry("Midna", "Мідна", "")
        return m

    def test_finds_occurrences_across_blocks(self):
        m = self._manager()
        dataset = [
            ["Link runs", "nothing here"],
            ["Midna and Link", "Midna again"],
        ]
        result = occurrences_by_term(m, dataset)
        assert Occurrence(0, 0) in result["Link"]
        assert Occurrence(1, 0) in result["Link"]
        assert Occurrence(1, 0) in result["Midna"]
        assert Occurrence(1, 1) in result["Midna"]

    def test_absent_term_has_no_occurrences(self):
        m = self._manager()
        dataset = [["Midna only"]]
        result = occurrences_by_term(m, dataset)
        assert result["Link"] == []

    def test_rows_deduped_per_term(self):
        m = self._manager()
        # "Link" twice in the same string -> one Occurrence for that row
        dataset = [["Link and Link again"]]
        result = occurrences_by_term(m, dataset)
        assert result["Link"] == [Occurrence(0, 0)]
