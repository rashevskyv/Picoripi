"""Reading a project's pipeline progress: the state, and the count behind it."""
from types import SimpleNamespace

from core.glossary_manager import STATUS_CONFIRMED, STATUS_SEEDED
from core.pipeline_status import (
    DONE,
    NOT_STARTED,
    PARTIAL,
    counted,
    glossary_states,
    markup_state,
    overall,
    present,
    speaker_names_state,
    structural_seed_state,
    translation_state,
)



class TestCounted:
    def test_a_partial_step_carries_its_numbers(self):
        """The whole point: a yellow light that says how yellow."""
        state = counted(147, 210, "terms translated")

        assert state.state == PARTIAL
        assert state.detail == "147 / 210 terms translated"

    def test_everything_done_is_done(self):
        assert counted(210, 210, "terms").state == DONE

    def test_more_than_total_still_reads_as_done(self):
        assert counted(3, 2, "terms").state == DONE

    def test_nothing_done_shows_the_work_waiting(self):
        state = counted(0, 210, "terms")

        assert state.state == NOT_STARTED
        assert state.detail == "0 / 210 terms"

    def test_nothing_to_do_is_not_secretly_finished(self):
        """An empty glossary is not a translated glossary."""
        state = counted(0, 0, "terms")

        assert state.state == NOT_STARTED
        assert state.detail == "no terms yet"

    def test_present_is_for_genuinely_binary_steps(self):
        assert present(True, "built", "not built").detail == "built"
        assert present(False, "built", "not built").state == NOT_STARTED


class TestMarkup:
    @staticmethod
    def _project(lines, ranges):
        return SimpleNamespace(
            raw_text="\n".join(lines),
            approved_marks=tuple(
                SimpleNamespace(
                    start_line=r[0], end_line=r[1],
                    type_id=r[2] if len(r) > 2 else "text",
                )
                for r in ranges
            ),
        )

    def test_a_blank_line_is_not_work_left_to_do(self):
        """One stray empty line held a finished 15k-line script at 15821/15822."""
        state = self._project(["a", "", "c"], [(0, 0), (2, 2)])

        assert markup_state(state).detail == "2 / 2 lines marked up"
        assert markup_state(state).state == DONE

    def test_a_range_marked_unmarked_is_not_marked_up(self):
        """That type means 'still needs a decision' -- it is the work, not the answer."""
        state = markup_state(self._project(["a", "b"], [(0, 0), (1, 1, "unmarked")]))

        assert state.detail == "1 / 2 lines marked up"

    def test_progress_is_measured_in_lines_not_marks(self):
        state = markup_state(self._project(["a", "b", "c", "d"], [(0, 1)]))

        assert state.detail == "2 / 4 lines marked up"
        assert state.state == PARTIAL

    def test_overlapping_marks_count_a_line_once(self):
        state = markup_state(self._project(["a", "b", "c", "d"], [(0, 2), (1, 2)]))

        assert state.detail == "3 / 4 lines marked up"

    def test_a_script_nobody_marked_up_says_so(self):
        assert markup_state(None).state == NOT_STARTED
        assert "not marked up" in markup_state(None).detail


class TestSpeakerNames:
    CODES = {f"Voice {i}" for i in range(1, 5)}

    def test_some_named_is_not_all_named(self):
        """"27 named" read as finished; 27 of 59 is what was actually true."""
        state = speaker_names_state({"Voice 1": "ZANT", "Voice 2": "GANON"}, self.CODES)

        assert state.state == PARTIAL
        assert state.detail == "2 / 4 speaker codes named"

    def test_naming_every_code_finishes_the_step(self):
        aliases = {code: code.upper() for code in self.CODES}

        assert speaker_names_state(aliases, self.CODES).state == DONE

    def test_a_name_for_a_code_the_game_no_longer_reports_does_not_count(self):
        """Stale entries in the alias file must not inflate the numerator."""
        state = speaker_names_state({"Voice 99": "OLD"}, self.CODES)

        assert state.detail == "0 / 4 speaker codes named"

    def test_no_names_yet(self):
        assert speaker_names_state({}, self.CODES).state == NOT_STARTED
        assert speaker_names_state(None, self.CODES).detail == "0 / 4 speaker codes named"

    def test_nothing_to_name_is_not_progress(self):
        assert speaker_names_state({"Voice 1": "ZANT"}, set()).state == NOT_STARTED
        assert "no speaker codes found" in speaker_names_state({}, None).detail


class TestGlossary:
    @staticmethod
    def _entries():
        return [
            SimpleNamespace(notes="a note", translation="переклад", status=STATUS_CONFIRMED),
            SimpleNamespace(notes="a note", translation="переклад", status=STATUS_SEEDED),
            SimpleNamespace(notes="", translation="", status=STATUS_SEEDED),
        ]

    def test_each_stage_is_counted_separately(self):
        states = glossary_states(self._entries())

        assert states["seed"].detail == "3 / 3 terms"
        assert states["describe"].detail == "2 / 3 terms described"
        assert states["translate"].detail == "2 / 3 terms translated"
        assert states["confirm"].detail == "1 / 3 terms confirmed"

    def test_translated_but_unconfirmed_is_not_confirmed(self):
        states = glossary_states(self._entries())

        assert states["translate"].state == PARTIAL
        assert states["confirm"].state == PARTIAL

    def test_an_empty_glossary_has_not_been_seeded(self):
        states = glossary_states([])

        assert states["seed"].state == NOT_STARTED
        assert states["seed"].detail == "glossary is empty"
        assert states["describe"].state == NOT_STARTED


class TestTranslationProgress:
    def test_a_row_that_changed_counts_as_translated(self):
        state = translation_state(
            data=[["Hello", "Goodbye"]],
            edited_file_data=[["Вітаю", "Goodbye"]],
        )

        assert state.detail == "1 / 2 rows translated"

    def test_empty_rows_are_not_work(self):
        state = translation_state(data=[["Hello", "", "   "]], edited_file_data=[["Вітаю"]])

        assert state.detail == "1 / 1 rows translated"
        assert state.state == DONE

    def test_unsaved_edits_count_too(self):
        """Progress the user can see on screen must not read as zero."""
        state = translation_state(
            data=[["Hello", "Goodbye"]],
            edited_file_data=[],
            edited_data={(0, 0): "Вітаю"},
        )

        assert state.detail == "1 / 2 rows translated"

    def test_an_unsaved_edit_wins_over_the_saved_text(self):
        state = translation_state(
            data=[["Hello"]],
            edited_file_data=[["Вітаю"]],
            edited_data={(0, 0): "Hello"},
        )

        assert state.detail == "0 / 1 rows translated"

    def test_no_project_is_not_a_finished_project(self):
        assert translation_state(None).state == NOT_STARTED


class TestOverall:
    def test_the_headline_counts_finished_steps(self):
        from core.pipeline_status import StepState

        state = overall([
            StepState(DONE), StepState(PARTIAL), StepState(NOT_STARTED),
        ])

        assert state.detail == "1 / 3 steps complete"
        assert state.state == PARTIAL


class TestStructuralSeed:
    @staticmethod
    def _seeds():
        return [
            {"term": "Master Sword"},
            {"term": "Hylian Shield"},
            {"term": "Ordon Village"},
        ]

    def test_no_seeds_available(self):
        assert structural_seed_state([], []).state == NOT_STARTED
        assert "no game data seeds available" in structural_seed_state(None, []).detail

    def test_unseeded_game_data(self):
        state = structural_seed_state(self._seeds(), [])
        assert state.state == NOT_STARTED
        assert state.detail == "0 / 3 game terms seeded"

    def test_partially_seeded_game_data(self):
        entries = [SimpleNamespace(original="Master Sword")]
        state = structural_seed_state(self._seeds(), entries)
        assert state.state == PARTIAL
        assert state.detail == "1 / 3 game terms seeded"

    def test_fully_seeded_game_data(self):
        entries = [
            SimpleNamespace(original="Master Sword"),
            SimpleNamespace(original="Hylian Shield"),
            SimpleNamespace(original="Ordon Village"),
        ]
        state = structural_seed_state(self._seeds(), entries)
        assert state.state == DONE
        assert state.detail == "3 / 3 game terms seeded"
