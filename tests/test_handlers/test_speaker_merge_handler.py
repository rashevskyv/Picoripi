"""Wiring for the script/game-data speaker join: inputs, refusals, and saving."""
import json
from unittest.mock import MagicMock, patch

import pytest

from core.speaker_alias_merge import ALIAS_FILENAME
from handlers.speaker_merge_handler import SpeakerMergeHandler


LONG_A = "I am worried about the Zoras of Lake Hylia right now"
LONG_B = "Go around through the tunnel in the woods while you can"


def _write_markup(tmp_path, pairs):
    """A Script Markup Studio project marking ``pairs`` as SPEAKER + TEXT."""
    from core.script_markup.hierarchy_markup import default_type_definitions
    from core.script_markup.hierarchy_ai_jobs import (
        HIERARCHY_FORMAT_VERSION,
        HIERARCHY_PROJECT_FORMAT,
    )

    lines, marks = [], []
    for speaker, text in pairs:
        for type_id, value in (("speaker", speaker), ("text", text)):
            marks.append({
                "start_line": len(lines), "end_line": len(lines), "depth": 0,
                "type_id": type_id, "approved": True, "origin": "manual",
            })
            lines.append(value)
    payload = {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "raw_text": "\n".join(lines or ["placeholder"]),
        "type_definitions": [
            {"type_id": d.type_id, "label": d.label,
             "description": d.description, "color": d.color}
            for d in default_type_definitions().values()
        ],
        "hierarchy_marks": marks,
    }
    (tmp_path / "script_markup_project.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _mw(tmp_path, *, rows=None, codes=None, script=None, has_project=True):
    mw = MagicMock()
    mw.project_manager.project_dir = str(tmp_path) if has_project else None

    rows = rows if rows is not None else {(0, 0): LONG_A, (0, 1): LONG_B}
    codes = codes if codes is not None else {(0, 0): "Voice 41", (0, 1): "Voice 41"}
    width = max((s for _, s in rows), default=-1) + 1
    mw.data_store.data = [[rows.get((0, i), "") for i in range(width)]]
    mw.current_game_rules.get_speaker_for_string = lambda b, s: codes.get((b, s))
    # The plugin decides what is still an internal id; "System" never is.
    mw.current_game_rules.is_placeholder_speaker = lambda name: name != "System"

    mw.translation_handler.prompt_composer = MagicMock()
    # A real path, so looking for the markup project beside it is a real lookup.
    mw.translation_handler.prompt_composer._find_script_path.return_value = str(
        tmp_path / "script.txt"
    )
    mw._script = script if script is not None else [("RENADO", LONG_A), ("RENADO", LONG_B)]
    return mw


@pytest.fixture
def no_dialog():
    with patch("handlers.speaker_merge_handler.QMessageBox") as box, \
            patch("handlers.speaker_merge_handler.SpeakerMergeDialog") as report:
        # An unmarked script asks before guessing; answer yes unless a test
        # overrides it, so the merging tests exercise the merge.
        box.warning.return_value = box.StandardButton.Ok
        box.report = report
        yield box


def _run(mw, script):
    with patch("handlers.speaker_merge_handler.script_speaker_lines", return_value=script):
        SpeakerMergeHandler(mw).merge_from_script()


def _apply_from_dialog(no_dialog, chosen=None):
    call = no_dialog.report.call_args
    on_apply = call.kwargs.get("on_apply") if call and "on_apply" in call.kwargs else None
    if not on_apply and call and len(call.args) >= 3:
        on_apply = call.args[2]
    if on_apply:
        result = call.args[0]
        names = chosen if chosen is not None else result.resolved
        on_apply(names)


class TestRefusals:
    def test_without_a_project_nothing_happens(self, tmp_path, no_dialog):
        mw = _mw(tmp_path, has_project=False)
        _run(mw, mw._script)

        no_dialog.information.assert_called_once()
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_empty_script_rows_still_opens_dialog_with_manual_rows(self, tmp_path, no_dialog):
        """No script matched or no script found opens dialog with manual rows."""
        mw = _mw(tmp_path)
        _run(mw, [])

        no_dialog.report.assert_called_once()
        result = no_dialog.report.call_args.args[0]
        assert result.codes_seen == 1
        assert "Voice 41" in result.all_placeholders
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_without_plugin_attribution_nothing_happens(self, tmp_path, no_dialog):
        mw = _mw(tmp_path, codes={})
        _run(mw, mw._script)

        no_dialog.information.assert_called_once()
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_an_identity_the_plugin_calls_a_display_name_is_left_alone(self, tmp_path, no_dialog):
        """"System" is the game narrating; no character may be voted onto it."""
        mw = _mw(tmp_path, codes={(0, 0): "System", (0, 1): "System"})
        _run(mw, [("MAYOR BO", LONG_A), ("MAYOR BO", LONG_B)])

        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_an_already_named_code_is_not_revisited(self, tmp_path, no_dialog):
        (tmp_path / ALIAS_FILENAME).write_text(
            json.dumps({"Voice 41": "Renado"}), encoding="utf-8"
        )
        mw = _mw(tmp_path)
        _run(mw, [("TELMA", LONG_A), ("TELMA", LONG_B)])

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "Renado"}


class TestWhatCountsAsACode:
    """A game spells its actors in its own terms, and only it knows which."""

    def test_a_placement_name_from_the_game_is_named_too(self, tmp_path, no_dialog):
        """CLERK_B groups the lines correctly and tells a reader nothing."""
        mw = _mw(tmp_path, codes={(0, 0): "CLERK_B", (0, 1): "CLERK_B"})
        _run(mw, [("BARNES", LONG_A), ("BARNES", LONG_B)])
        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"CLERK_B": "BARNES"}

    def test_a_plugin_without_the_hook_offers_every_identity(self, tmp_path, no_dialog):
        """The safe default: a plugin returning raw ids must not be second-guessed."""
        mw = _mw(tmp_path, codes={(0, 0): "GER_A", (0, 1): "GER_A"})
        del mw.current_game_rules.is_placeholder_speaker
        mw.current_game_rules.mock_add_spec(["get_speaker_for_string"])
        mw.current_game_rules.get_speaker_for_string = lambda b, s: (
            "GER_A" if (b, s) in {(0, 0), (0, 1)} else None
        )
        _run(mw, [("GERUDO", LONG_A), ("GERUDO", LONG_B)])
        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"GER_A": "GERUDO"}


class TestUnmarkedScript:
    """Guessing the speakers is a worse input, so say so before doing it."""

    def test_the_user_is_warned_before_a_guessed_merge(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        no_dialog.warning.assert_called_once()
        assert "marked up" in no_dialog.warning.call_args.args[-3]

    def test_declining_the_warning_saves_nothing(self, tmp_path, no_dialog):
        no_dialog.warning.return_value = no_dialog.StandardButton.Cancel
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        assert not (tmp_path / ALIAS_FILENAME).exists()
        no_dialog.report.assert_not_called()

    def test_a_marked_up_script_is_used_and_never_guessed(self, tmp_path, no_dialog):
        """Approved SPEAKER/TEXT marks beat the ALL-CAPS heuristic."""
        _write_markup(tmp_path, [("RENADO", LONG_A), ("RENADO", LONG_B)])
        mw = _mw(tmp_path)

        # The raw-script reading would name it TELMA; the markup must win.
        _run(mw, [("TELMA", LONG_A), ("TELMA", LONG_B)])

        no_dialog.warning.assert_not_called()
        _apply_from_dialog(no_dialog)
        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_markup_without_any_speaker_falls_back_and_warns(self, tmp_path, no_dialog):
        """A project that exists but marks no speech is not an attribution."""
        _write_markup(tmp_path, [])
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        no_dialog.warning.assert_called_once()
        _apply_from_dialog(no_dialog)
        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}


class TestMerging:
    def test_merge_never_writes_file_before_apply(self, tmp_path, no_dialog):
        """Strict manual decision boundary: running merge must not save aliases."""
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_a_resolved_code_is_saved_after_apply(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        assert not (tmp_path / ALIAS_FILENAME).exists()

        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_earlier_names_survive_a_later_merge(self, tmp_path, no_dialog):
        (tmp_path / ALIAS_FILENAME).write_text(
            json.dumps({"Voice 9": "Ilia"}), encoding="utf-8"
        )
        mw = _mw(tmp_path)
        _run(mw, mw._script)
        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 9": "Ilia", "Voice 41": "RENADO"}

    def test_empty_rows_are_never_matched(self, tmp_path, no_dialog):
        mw = _mw(
            tmp_path,
            rows={(0, 0): LONG_A, (0, 1): "", (0, 2): LONG_B},
            codes={(0, 0): "Voice 41", (0, 1): "Voice 41", (0, 2): "Voice 41"},
        )
        _run(mw, mw._script)
        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_the_folders_are_rebuilt_on_apply(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        mw.ui_updater.block_list_updater.refresh_virtual_folder_labels.assert_not_called()
        _apply_from_dialog(no_dialog)
        mw.ui_updater.block_list_updater.refresh_virtual_folder_labels.assert_called_once()

    def test_a_voice_two_characters_share_is_saved_under_both_names(self, tmp_path, no_dialog):
        """Refusing to name it threw away a correct answer about the game."""
        mw = _mw(tmp_path)
        _run(mw, [("RENADO", LONG_A), ("TELMA", LONG_B)])
        _apply_from_dialog(no_dialog)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO / TELMA"}

    def test_the_result_reaches_the_report_dialog(self, tmp_path, no_dialog):
        """The report is a dialog over the result, not a string built here."""
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        result = no_dialog.report.call_args.args[0]
        assert result.resolved == {"Voice 41": "RENADO"}
        assert [v.text for v in result.evidence["Voice 41"]] == [LONG_A, LONG_B]
        # Shown, not exec'd: a modal report would freeze the wizard behind it.
        no_dialog.report.return_value.show.assert_called_once()
        no_dialog.report.return_value.exec.assert_not_called()

    def test_unmatched_codes_and_game_display_names_reach_dialog_result(self, tmp_path, no_dialog):
        mw = _mw(
            tmp_path,
            rows={(0, 0): LONG_A, (0, 1): LONG_B, (0, 2): "Unmatched line", (0, 3): "Narration"},
            codes={(0, 0): "Voice 41", (0, 1): "Voice 41", (0, 2): "Voice 99", (0, 3): "System"},
        )
        _run(mw, [("RENADO", LONG_A), ("RENADO", LONG_B)])

        result = no_dialog.report.call_args.args[0]
        assert "Voice 99" in result.all_placeholders
        assert "System" in result.game_display_names
        assert result.codes_seen == 2
        assert "1 of 2 speaker code(s) named" in result.summary


class TestSuggestionsFromTheGlossary:
    """A code the script never matched may still be named in its description."""

    def _mw_with_entry(self, tmp_path, **fields):
        from types import SimpleNamespace

        mw = _mw(tmp_path, codes={(0, 0): "Bans", (0, 1): "Bans"})
        entry = SimpleNamespace(
            original="Bans", notes="Advertises the bombs at Barnes's shop.", **fields
        )
        mw.translation_handler.glossary_handler.glossary_manager.get_entries.return_value = [entry]
        return mw

    def test_a_glossary_suggestion_reaches_the_report(self, tmp_path, no_dialog):
        mw = self._mw_with_entry(
            tmp_path, suggested_name="BARNES", suggested_name_evidence="Barnes's shop"
        )
        # No script line matches, so the join itself finds nothing for this code.
        _run(mw, [("SOMEONE ELSE", "A line that is nowhere in the game text")])

        result = no_dialog.report.call_args.args[0]
        assert result.unproven["Bans"] == {"BARNES": 1}
        assert "glossary description" in result.evidence["Bans"][0].text

    def test_the_scripts_own_evidence_outranks_a_reading_of_prose(self, tmp_path, no_dialog):
        mw = self._mw_with_entry(tmp_path, suggested_name="BARNES")
        _run(mw, [("RENADO", LONG_A)])   # one real match: script wins

        result = no_dialog.report.call_args.args[0]
        assert "BARNES" not in result.unproven.get("Bans", {})

    def test_an_entry_without_a_suggestion_adds_nothing(self, tmp_path, no_dialog):
        mw = self._mw_with_entry(tmp_path, suggested_name="")
        _run(mw, [("SOMEONE ELSE", "A line that is nowhere in the game text")])

        result = no_dialog.report.call_args.args[0]
        assert "Bans" not in result.unproven


class TestGlossaryMigrationOnApply:
    def test_save_names_migrates_glossary_entries_and_refreshes_views(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        glossary_handler = MagicMock()
        manager = MagicMock()
        manager.get_raw_text.return_value = "raw text"
        glossary_handler.glossary_manager = manager
        mw.translation_handler.glossary_handler = glossary_handler

        _run(mw, mw._script)
        _apply_from_dialog(no_dialog, chosen={"Voice 41": "RENADO"})

        manager.rename_original.assert_called_once_with("Voice 41", "RENADO")
        glossary_handler._update_glossary_highlighting.assert_called_once()
        glossary_handler.refresh_open_dialog.assert_called_once()
        assert (tmp_path / ALIAS_FILENAME).exists()

    def test_save_names_succeeds_even_if_glossary_manager_is_unavailable(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        mw.translation_handler = None

        _run(mw, mw._script)
        _apply_from_dialog(no_dialog, chosen={"Voice 41": "RENADO"})

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_save_names_empty_mapping_is_true_noop(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        glossary_handler = MagicMock()
        manager = MagicMock()
        glossary_handler.glossary_manager = manager
        mw.translation_handler.glossary_handler = glossary_handler

        _run(mw, mw._script)
        _apply_from_dialog(no_dialog, chosen={})

        assert not (tmp_path / ALIAS_FILENAME).exists()
        mw.ui_updater.block_list_updater.refresh_virtual_folder_labels.assert_not_called()
        manager.rename_original.assert_not_called()
        glossary_handler._update_glossary_highlighting.assert_not_called()
        glossary_handler.refresh_open_dialog.assert_not_called()

    def test_public_save_names_helper_returns_bool_success(self, tmp_path):
        mw = _mw(tmp_path)
        glossary_handler = MagicMock()
        manager = MagicMock()
        glossary_handler.glossary_manager = manager
        mw.translation_handler.glossary_handler = glossary_handler

        handler = SpeakerMergeHandler(mw)

        # Success path returns True
        res = handler.save_names({"Voice 41": "RENADO"})
        assert res is True
        assert json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8")) == {"Voice 41": "RENADO"}
        manager.rename_original.assert_called_once_with("Voice 41", "RENADO")

        # Empty mapping returns False
        assert handler.save_names({}) is False

        # Missing project dir returns False
        no_proj_mw = _mw(tmp_path, has_project=False)
        no_proj_handler = SpeakerMergeHandler(no_proj_mw)
        assert no_proj_handler.save_names({"Voice 41": "RENADO"}) is False
