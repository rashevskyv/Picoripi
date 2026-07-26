"""Tests for the pass-1a sweep driver (core/glossary_build/sweep_driver.py)."""
from core.glossary_build.sweep_driver import (
    AggregatedTerm,
    RawTerm,
    sweep_terms,
)
from core.glossary_build.text_sweep import SweepChunk, SweepItem


def _chunk(text):
    return SweepChunk(items=(SweepItem(0, 0, text),), text=text)


class TestMerging:
    def test_same_term_across_chunks_merges(self):
        chunks = [_chunk("c1"), _chunk("c2")]
        script = {
            "c1": [RawTerm("Spring Goron", "Characters", "found near the spring")],
            "c2": [RawTerm("spring goron", "Characters", "runs the hot spring")],
        }
        result = sweep_terms(chunks, lambda ch: script[ch.text])
        assert len(result) == 1
        term = next(iter(result.values()))
        assert term.mentions == 2
        assert len(term.fragments) == 2

    def test_display_form_is_first_seen(self):
        chunks = [_chunk("c1"), _chunk("c2")]
        script = {
            "c1": [RawTerm("Spring Goron")],
            "c2": [RawTerm("SPRING GORON")],
        }
        result = sweep_terms(chunks, lambda ch: script[ch.text])
        assert next(iter(result.values())).term == "Spring Goron"

    def test_distinct_terms_kept_separate(self):
        chunk = _chunk("c")
        raws = [RawTerm("Link"), RawTerm("Midna"), RawTerm("Zelda")]
        result = sweep_terms([chunk], lambda ch: raws)
        assert len(result) == 3


class TestSectionVoting:
    def test_most_common_section_wins(self):
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        script = {
            "a": [RawTerm("Ordon", "Places")],
            "b": [RawTerm("Ordon", "Places")],
            "c": [RawTerm("Ordon", "Characters")],
        }
        result = sweep_terms(chunks, lambda ch: script[ch.text])
        assert result[GlossaryKey("Ordon")].section == "Places"

    def test_no_section_yields_empty(self):
        result = sweep_terms([_chunk("a")], lambda ch: [RawTerm("Ordon")])
        assert result[GlossaryKey("Ordon")].section == ""


class TestFragments:
    def test_duplicate_fragments_deduped(self):
        chunks = [_chunk("a"), _chunk("b")]
        script = {
            "a": [RawTerm("X", fragment="same text")],
            "b": [RawTerm("X", fragment="same text")],
        }
        result = sweep_terms(chunks, lambda ch: script[ch.text])
        assert len(result[GlossaryKey("X")].fragments) == 1

    def test_fragment_ceiling_enforced(self):
        chunks = [_chunk(str(i)) for i in range(50)]
        script = {str(i): [RawTerm("Hero", fragment=f"frag {i}")] for i in range(50)}
        result = sweep_terms(chunks, lambda ch: script[ch.text], max_fragments=30)
        term = result[GlossaryKey("Hero")]
        assert term.mentions == 50  # every mention counted
        assert len(term.fragments) == 30  # but fragments capped

    def test_empty_fragment_skipped(self):
        result = sweep_terms([_chunk("a")], lambda ch: [RawTerm("X", fragment="  ")])
        assert result[GlossaryKey("X")].fragments == []


class TestEdgeCases:
    def test_blank_terms_ignored(self):
        result = sweep_terms([_chunk("a")], lambda ch: [RawTerm("   "), RawTerm("Real")])
        assert list(result) == [GlossaryKey("Real")]

    def test_no_chunks(self):
        assert sweep_terms([], lambda ch: []) == {}

    def test_custom_normalizer_controls_identity(self):
        # normalizer that collapses everything -> all terms merge into one
        result = sweep_terms(
            [_chunk("a")],
            lambda ch: [RawTerm("A"), RawTerm("B")],
            normalize=lambda _t: "same",
        )
        assert len(result) == 1


def GlossaryKey(term):
    """Helper: the normalized key the driver uses, for lookups in assertions."""
    from core.glossary_manager import GlossaryManager

    return GlossaryManager.normalize_term(term)
