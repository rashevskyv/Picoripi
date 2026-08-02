"""Joining a marked-up script onto the speaker codes the game data produced."""
from core.speaker_alias_merge import merge_script_speakers, normalize_line


class TestNormalizeLine:
    def test_tags_and_wrapping_do_not_block_a_match(self):
        game = "Hurry to the {color:red}spring{color:white},\nchild!"
        script = "Hurry to the spring, child!"
        assert normalize_line(game) == normalize_line(script)

    def test_a_player_name_placeholder_is_ignored(self):
        """The game substitutes the player's name; a script spells it out."""
        assert normalize_line("Be careful, {escape:0:0000}!") == "be careful"

    def test_punctuation_and_case_do_not_matter(self):
        assert normalize_line("So... YOU'RE back?!") == normalize_line("so you re back")

    def test_empty_text_is_empty(self):
        assert normalize_line("") == ""
        assert normalize_line(None) == ""


LONG_A = "I am worried about the Zoras of Lake Hylia right now"
LONG_B = "Go around through the tunnel in the woods while you can"
LONG_C = "When I grow up I want to be a swordsman just like you"


class TestMerge:
    def test_a_code_takes_the_name_its_lines_carry(self):
        result = merge_script_speakers(
            script_rows=[("Renado", LONG_A), ("Renado", LONG_B)],
            game_rows={(0, 1): LONG_A, (0, 2): LONG_B},
            row_codes={(0, 1): "Voice 41", (0, 2): "Voice 41"},
        )

        assert result.resolved == {"Voice 41": "Renado"}
        assert result.conflicts == {}
        assert result.matched_script_lines == 2

    def test_one_matching_line_is_not_enough(self):
        """A single line is a coincidence waiting to happen."""
        result = merge_script_speakers(
            script_rows=[("Renado", LONG_A)],
            game_rows={(0, 1): LONG_A},
            row_codes={(0, 1): "Voice 41"},
        )

        assert result.resolved == {}
        assert result.conflicts == {"Voice 41": {"Renado": 1}}

    def test_disagreement_is_reported_rather_than_guessed(self):
        result = merge_script_speakers(
            script_rows=[("Renado", LONG_A), ("Telma", LONG_B), ("Ilia", LONG_C)],
            game_rows={(0, 1): LONG_A, (0, 2): LONG_B, (0, 3): LONG_C},
            row_codes={(0, 1): "Voice 41", (0, 2): "Voice 41", (0, 3): "Voice 41"},
        )

        assert result.resolved == {}
        assert set(result.conflicts["Voice 41"]) == {"Renado", "Telma", "Ilia"}

    def _one_code(self, pairs):
        """All ``(speaker, text)`` pairs land on rows sharing one code."""
        rows = {(0, i): text for i, (_, text) in enumerate(pairs)}
        return merge_script_speakers(
            script_rows=pairs,
            game_rows=rows,
            row_codes={row: "Voice 41" for row in rows},
        )

    def test_a_clear_majority_wins(self):
        extra = "He is the shaman of this village and its healer"
        result = self._one_code([
            ("Renado", LONG_A), ("Renado", LONG_B), ("Renado", LONG_C),
            ("Renado", "Come to the sanctuary when you are ready"),
            ("Telma", extra),
        ])

        assert result.resolved == {"Voice 41": "Renado"}   # 4 of 5

    def test_a_bare_majority_is_not_enough(self):
        """A wrong name here would be stamped on every line of that code, so
        three-to-one is reported for review rather than accepted."""
        extra = "He is the shaman of this village and its healer"
        result = self._one_code([
            ("Renado", LONG_A), ("Renado", LONG_B), ("Renado", LONG_C),
            ("Telma", extra),
        ])

        assert result.resolved == {}
        assert result.conflicts["Voice 41"] == {"Renado": 3, "Telma": 1}

    def test_short_lines_never_vote(self):
        """"Yes." is said by everyone and would swamp the real evidence."""
        result = merge_script_speakers(
            script_rows=[("Renado", "Yes."), ("Telma", "Yes."), ("Ilia", "Hmm...")],
            game_rows={(0, 1): "Yes.", (0, 2): "Hmm..."},
            row_codes={(0, 1): "Voice 41", (0, 2): "Voice 41"},
        )

        assert result.resolved == {}
        assert result.conflicts == {}
        assert result.matched_script_lines == 0

    def test_a_line_shared_by_two_codes_proves_nothing(self):
        result = merge_script_speakers(
            script_rows=[("Renado", LONG_A)],
            game_rows={(0, 1): LONG_A, (0, 2): LONG_A},
            row_codes={(0, 1): "Voice 41", (0, 2): "Voice 77"},
        )

        assert result.resolved == {}
        assert result.ambiguous_script_lines == 1

    def test_script_lines_absent_from_the_game_are_counted(self):
        """Surfaces a dump mismatch or a markup mistake instead of hiding it."""
        result = merge_script_speakers(
            script_rows=[("Renado", "This line is not in the game at all")],
            game_rows={(0, 1): LONG_A},
            row_codes={(0, 1): "Voice 41"},
        )

        assert result.unmatched_script_lines == 1
        assert result.matched_script_lines == 0

    def test_only_the_requested_codes_are_touched(self):
        """Real names resolved from game data must not be voted over."""
        result = merge_script_speakers(
            script_rows=[("Mayor Bo", LONG_A), ("Mayor Bo", LONG_B)],
            game_rows={(0, 1): LONG_A, (0, 2): LONG_B},
            row_codes={(0, 1): "Bou", (0, 2): "Bou"},
            codes_to_resolve=["Voice 41"],
        )

        assert result.resolved == {}
        assert result.codes_seen == 0

    def test_the_summary_states_what_was_and_was_not_decided(self):
        result = merge_script_speakers(
            script_rows=[("Renado", LONG_A), ("Renado", LONG_B), ("Telma", LONG_C)],
            game_rows={(0, 1): LONG_A, (0, 2): LONG_B, (0, 3): LONG_C},
            row_codes={(0, 1): "Voice 41", (0, 2): "Voice 41", (0, 3): "Voice 77"},
        )

        assert result.resolved == {"Voice 41": "Renado"}
        assert "1 of 2 speaker code(s) named" in result.summary


class TestPersistence:
    def test_a_saved_map_round_trips(self, tmp_path):
        from core.speaker_alias_merge import load_speaker_aliases, save_speaker_aliases

        assert save_speaker_aliases(tmp_path, {"Voice 41": "Renado"})
        assert load_speaker_aliases(tmp_path) == {"Voice 41": "Renado"}

    def test_a_project_without_the_file_has_no_aliases(self, tmp_path):
        from core.speaker_alias_merge import load_speaker_aliases

        assert load_speaker_aliases(tmp_path) == {}

    def test_blank_and_malformed_entries_are_ignored(self, tmp_path):
        import json
        from core.speaker_alias_merge import ALIAS_FILENAME, load_speaker_aliases

        (tmp_path / ALIAS_FILENAME).write_text(
            json.dumps({"Voice 41": "Renado", "Voice 9": "  ", "": "X"}),
            encoding="utf-8",
        )
        assert load_speaker_aliases(tmp_path) == {"Voice 41": "Renado"}

    def test_a_corrupt_file_is_not_fatal(self, tmp_path):
        from core.speaker_alias_merge import ALIAS_FILENAME, load_speaker_aliases

        (tmp_path / ALIAS_FILENAME).write_text("not json at all", encoding="utf-8")
        assert load_speaker_aliases(tmp_path) == {}

    def test_no_project_means_nothing_to_load_or_save(self):
        from core.speaker_alias_merge import load_speaker_aliases, save_speaker_aliases

        assert load_speaker_aliases(None) == {}
        assert save_speaker_aliases(None, {"a": "b"}) is None


class TestReadingTheScript:
    """The script is ALL-CAPS headings, [directions], and lines in between."""

    def _composer(self, tmp_path, text):
        path = tmp_path / "script.txt"
        path.write_text(text, encoding="utf-8")

        class _Composer:
            _script_lines_cache = None

            def _find_script_path(self):
                return str(path)

        return _Composer()

    def test_lines_belong_to_the_heading_above_them(self, tmp_path):
        from core.speaker_alias_merge import script_speaker_lines

        composer = self._composer(tmp_path, (
            "RENADO\n"
            "Welcome to Kakariko Village.\n"
            "The spirits are restless.\n"
            "TELMA\n"
            "Come in and sit down, honey.\n"
        ))

        assert script_speaker_lines(composer) == [
            ("RENADO", "Welcome to Kakariko Village."),
            ("RENADO", "The spirits are restless."),
            ("TELMA", "Come in and sit down, honey."),
        ]

    def test_stage_directions_and_headings_are_not_speech(self, tmp_path):
        from core.speaker_alias_merge import script_speaker_lines

        composer = self._composer(tmp_path, (
            "[Link enters the sanctuary]\n"
            "RENADO\n"
            "[he turns slowly]\n"
            "You have returned.\n"
        ))

        assert script_speaker_lines(composer) == [("RENADO", "You have returned.")]

    def test_text_before_any_heading_belongs_to_nobody(self, tmp_path):
        from core.speaker_alias_merge import script_speaker_lines

        composer = self._composer(tmp_path, "A prologue with no speaker\nRENADO\nHello there\n")

        assert script_speaker_lines(composer) == [("RENADO", "Hello there")]

    def test_a_missing_script_is_not_an_error(self, tmp_path):
        from core.speaker_alias_merge import script_speaker_lines

        class _Composer:
            def _find_script_path(self):
                return str(tmp_path / "nope.txt")

        assert script_speaker_lines(_Composer()) == []
