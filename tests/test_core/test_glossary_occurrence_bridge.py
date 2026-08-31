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


class TestOwnedRows:
    """A character block whose label never appears in the lines still owns them."""

    def test_block_name_owns_rows_when_term_is_absent_from_text(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("VILLAGE GORON #2", "", "", section="Characters")

        class Store:
            block_names = {"0": "Seira", "1": "VILLAGE GORON #2"}

        m.bind_project_rows(Store(), None)
        dataset = [
            ["Hello from Seira"],
            ["You saved our chief, Brother!", "Stop by sometime, Brother!"],
        ]
        result = occurrences_by_term(m, dataset)
        assert result["VILLAGE GORON #2"] == [Occurrence(1, 0), Occurrence(1, 1)]
        raw = m.get_occurrences_for(m.get_entry("VILLAGE GORON #2"))
        assert all(o.kind == "spoken" for o in raw)
        assert len(raw) == 2

    def test_speaker_id_owns_rows_when_term_is_absent_from_text(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("Voice 70", "", "", section="Characters")

        class Rules:
            def get_speaker_for_string(self, block_idx, string_idx):
                if block_idx == 0:
                    return "Voice 70"
                return "System"

        m.bind_project_rows(None, Rules())
        dataset = [["Hmm...", "You saved our chief, Brother!"], ["unrelated"]]
        result = occurrences_by_term(m, dataset)
        assert result["Voice 70"] == [Occurrence(0, 0), Occurrence(0, 1)]

    def test_generic_block_labels_do_not_own_rows(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("Block 0", "", "")

        class Store:
            block_names = {"0": "Block 0"}

        m.bind_project_rows(Store(), None)
        result = occurrences_by_term(m, [["hello"]])
        assert result["Block 0"] == []


    def test_mention_and_spoken_are_both_kept_on_the_same_row(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("Seira", "", "", section="Characters")

        class Store:
            block_names = {"0": "Seira"}

        m.bind_project_rows(Store(), None)
        dataset = [["Seira keeps the shop."]]
        occs = m.build_occurrence_index(dataset)["Seira"]
        kinds = sorted(o.kind for o in occs)
        assert kinds == ["mention", "spoken"]
        # describe still gets one window for that row, spoken first
        assert occurrences_by_term(m, dataset)["Seira"] == [Occurrence(0, 0)]

    def test_shared_voice_alias_owns_rows_for_each_named_character(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("SPRING ZORA #1", "", "", section="Characters")
        m.add_entry("SPRING ZORA #2", "", "", section="Characters")

        class Rules:
            def get_speaker_for_string(self, block_idx, string_idx):
                return "zrSPA"

        m.bind_project_rows(
            None,
            Rules(),
            speaker_aliases={"zrSPA": "SPRING ZORA #1 / SPRING ZORA #2"},
        )
        dataset = [["The spring is still.", "We wait for the hero."]]
        result = occurrences_by_term(m, dataset)
        assert result["SPRING ZORA #1"] == [Occurrence(0, 0), Occurrence(0, 1)]
        assert result["SPRING ZORA #2"] == [Occurrence(0, 0), Occurrence(0, 1)]

    def test_speaker_pool_owns_all_seven_physical_rows_for_agithas_stalker(self):
        """A marked-script speaker owning 7 rows gets 7 spoken occurrences."""
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("AGITHA'S STALKER", "", "", section="Characters")

        pool = {(0, i): "AGITHA'S STALKER" for i in range(7)}
        m.bind_project_rows(None, None, speaker_pool=pool)
        dataset = [["Dialogue line without the speaker name"] * 7]

        result = occurrences_by_term(m, dataset)
        assert len(result["AGITHA'S STALKER"]) == 7
        assert result["AGITHA'S STALKER"] == [Occurrence(0, i) for i in range(7)]

        raw = m.get_occurrences_for(m.get_entry("AGITHA'S STALKER"))
        assert len(raw) == 7
        assert all(o.kind == "spoken" for o in raw)

    def test_speaker_pool_takes_priority_over_rules_getter(self):
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        m.add_entry("REAL_SPEAKER", "", "", section="Characters")
        m.add_entry("OLD_CODE", "", "", section="Characters")

        class Rules:
            def get_speaker_for_string(self, _b, _s):
                return "OLD_CODE"

        pool = {(0, 0): "REAL_SPEAKER"}
        m.bind_project_rows(None, Rules(), speaker_pool=pool)
        dataset = [["Some line"]]

        result = occurrences_by_term(m, dataset)
        assert result["REAL_SPEAKER"] == [Occurrence(0, 0)]
        assert result["OLD_CODE"] == []
