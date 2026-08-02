"""Wiring for the script/game-data speaker join: inputs, refusals, and saving."""
import json
from unittest.mock import MagicMock, patch

import pytest

from core.speaker_alias_merge import ALIAS_FILENAME
from handlers.speaker_merge_handler import SpeakerMergeHandler


LONG_A = "I am worried about the Zoras of Lake Hylia right now"
LONG_B = "Go around through the tunnel in the woods while you can"


def _mw(tmp_path, *, rows=None, codes=None, script=None, has_project=True):
    mw = MagicMock()
    mw.project_manager.project_dir = str(tmp_path) if has_project else None

    rows = rows if rows is not None else {(0, 0): LONG_A, (0, 1): LONG_B}
    codes = codes if codes is not None else {(0, 0): "Voice 41", (0, 1): "Voice 41"}
    width = max((s for _, s in rows), default=-1) + 1
    mw.data_store.data = [[rows.get((0, i), "") for i in range(width)]]
    mw.current_game_rules.get_speaker_for_string = lambda b, s: codes.get((b, s))

    mw.translation_handler.prompt_composer = MagicMock()
    mw._script = script if script is not None else [("RENADO", LONG_A), ("RENADO", LONG_B)]
    return mw


@pytest.fixture
def no_dialog():
    with patch("handlers.speaker_merge_handler.QMessageBox") as box:
        yield box


def _run(mw, script):
    with patch("handlers.speaker_merge_handler.script_speaker_lines", return_value=script):
        SpeakerMergeHandler(mw).merge_from_script()


class TestRefusals:
    def test_without_a_project_nothing_happens(self, tmp_path, no_dialog):
        mw = _mw(tmp_path, has_project=False)
        _run(mw, mw._script)

        no_dialog.information.assert_called_once()
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_without_a_script_nothing_happens(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, [])

        no_dialog.information.assert_called_once()
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_without_plugin_attribution_nothing_happens(self, tmp_path, no_dialog):
        mw = _mw(tmp_path, codes={})
        _run(mw, mw._script)

        no_dialog.information.assert_called_once()
        assert not (tmp_path / ALIAS_FILENAME).exists()

    def test_names_from_game_data_are_left_alone(self, tmp_path, no_dialog):
        """"Bou" came from the game and is already right; do not vote over it."""
        mw = _mw(tmp_path, codes={(0, 0): "Bou", (0, 1): "Bou"})
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


class TestMerging:
    def test_a_resolved_code_is_saved(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_earlier_names_survive_a_later_merge(self, tmp_path, no_dialog):
        (tmp_path / ALIAS_FILENAME).write_text(
            json.dumps({"Voice 9": "Ilia"}), encoding="utf-8"
        )
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 9": "Ilia", "Voice 41": "RENADO"}

    def test_empty_rows_are_never_matched(self, tmp_path, no_dialog):
        mw = _mw(
            tmp_path,
            rows={(0, 0): LONG_A, (0, 1): "", (0, 2): LONG_B},
            codes={(0, 0): "Voice 41", (0, 1): "Voice 41", (0, 2): "Voice 41"},
        )
        _run(mw, mw._script)

        saved = json.loads((tmp_path / ALIAS_FILENAME).read_text(encoding="utf-8"))
        assert saved == {"Voice 41": "RENADO"}

    def test_the_folders_are_rebuilt_so_names_show_at_once(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, mw._script)

        mw.ui_updater.block_list_updater.refresh_virtual_folder_labels.assert_called_once()

    def test_a_conflict_is_reported_and_not_saved(self, tmp_path, no_dialog):
        mw = _mw(tmp_path)
        _run(mw, [("RENADO", LONG_A), ("TELMA", LONG_B)])

        assert not (tmp_path / ALIAS_FILENAME).exists()
        report = no_dialog.information.call_args.args[-1]
        assert "Need your decision" in report
        assert "Nothing was saved." in report
