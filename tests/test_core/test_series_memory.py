"""Series translation memory: the registry beside a series glossary, reading other projects' memories,
reuse in a batch run and in prompts, and the bar above the editor."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.data_state_processor import DataStateProcessor
from core.translation.series_memory import (
    index_source_positions,
    load_series_memory,
    register_project,
    registry_path,
    source_hash,
)
from dialogs.cached_translation_dialog import CachedTranslationDialog
from handlers.translation_handler import TranslationHandler
from test_core.test_translation_memory import _speaker_context, _window
from ui.components.memory_banner import MemoryBanner


def _memory_file(path: Path, rows: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({source_hash(k): v for k, v in rows.items()}, ensure_ascii=False), encoding="utf-8")
    return path


class TestFiles:
    def test_a_project_registers_itself_beside_each_series_glossary_and_only_writes_on_change(self, tmp_path):
        series = tmp_path / "Zelda" / "_glossary" / "glossary.json"
        game = tmp_path / "Zelda" / "TP" / "_glossary" / "glossary.json"
        for path in (series, game):
            path.parent.mkdir(parents=True)
            path.write_text("[]", encoding="utf-8")

        register_project([game, series], "TP GC", tmp_path / "tp" / "translation_memory.json")
        stamp = registry_path(series).stat().st_mtime_ns
        register_project([game, series], "TP GC", tmp_path / "tp" / "translation_memory.json")

        assert json.loads(registry_path(series).read_text(encoding="utf-8")) == {
            "TP GC": str(tmp_path / "tp" / "translation_memory.json")
        }
        assert json.loads(registry_path(game).read_text(encoding="utf-8")) == json.loads(
            registry_path(series).read_text(encoding="utf-8")
        )
        assert registry_path(series).stat().st_mtime_ns == stamp

    def test_the_memory_of_every_other_registered_project_is_read_nearest_level_first(self, tmp_path):
        series = tmp_path / "Zelda" / "_glossary" / "glossary.json"
        game = tmp_path / "Zelda" / "TP" / "_glossary" / "glossary.json"
        for path in (series, game):
            path.parent.mkdir(parents=True)
            path.write_text("[]", encoding="utf-8")
        mine = _memory_file(tmp_path / "tp_gc" / "translation_memory.json", {"Yes": [{"source": "Yes", "translation": "Моє"}]})
        hd = _memory_file(tmp_path / "tp_hd" / "translation_memory.json", {"Yes": [{"source": "Yes", "translation": "Так (HD)"}]})
        ww = _memory_file(tmp_path / "ww" / "translation_memory.json", {
            "Yes": [{"source": "yes", "translation": "Атож"}, {"source": "Yes", "translation": "Так (WW)"}],
            "No": [{"source": "No", "translation": "Ні"}],
        })
        register_project([game, series], "TP GC", mine)
        register_project([game], "TP HD", hd)
        register_project([series], "WW", ww)
        (tmp_path / "gone").mkdir()
        register_project([series], "Gone", tmp_path / "gone" / "translation_memory.json")  # file never written

        memory = load_series_memory([game, series], mine)

        assert memory[source_hash("Yes")] == [
            {"source": "Yes", "translation": "Так (HD)", "project": "TP HD"},
            {"source": "yes", "translation": "Атож", "project": "WW"},
            {"source": "Yes", "translation": "Так (WW)", "project": "WW"},
        ]
        assert memory[source_hash("No")] == [{"source": "No", "translation": "Ні", "project": "WW"}]
        assert load_series_memory([], mine) == {}

    def test_source_positions_index_every_place_of_a_text(self):
        positions = index_source_positions([["Yes", "x", "yes"], ["Yes", ""], "not a block"])
        assert positions[source_hash("Yes")] == [(0, 0), (0, 2), (1, 0)]
        assert source_hash("") not in positions


@pytest.fixture
def window(tmp_path):
    data = [["A", "B", "C", "Yes"]] + [["x"] * 11 for _ in range(7)]
    data[7][10] = "Yes"
    data[3][2] = "Yes"
    mw = _window(tmp_path, data)
    manager = mw.saved_translations_manager
    # Rows carry the speaker and addressee they were saved under; this window resolves no speaker ("NONE").
    manager.series_memory = {source_hash("Yes"): [
        {"source": "Yes", "translation": "Так (HD)", "project": "TP HD", "speaker": "NONE", "addressee": ""},
        {"source": "yes", "translation": "атож", "project": "WW", "speaker": "NONE", "addressee": ""},
    ]}
    manager.source_positions = index_source_positions(data)
    return mw


@pytest.fixture
def handler(window):
    processor = DataStateProcessor(window)
    window.data_processor = processor
    with patch('handlers.translation.facade.handler.TranslationUIHandler'), \
         patch('PyQt6.QtCore.QTimer.singleShot'):
        translation_handler = TranslationHandler(window, processor, window.ui_updater)
    translation_handler.ui_handler = MagicMock()
    return translation_handler


class TestLookup:
    def test_exact_rows_by_default_similar_spellings_on_request(self, window):
        manager = window.saved_translations_manager
        assert [r["translation"] for r in manager.series_by_source("Yes")] == ["Так (HD)"]
        assert [r["translation"] for r in manager.series_by_source("Yes", exact=False)] == ["Так (HD)", "атож"]
        assert manager.series_by_source("No") == [] and manager.series_by_source(None) == []

    def test_positions_of_a_source_are_every_exact_copy_in_the_project(self, window):
        assert window.saved_translations_manager.positions_of_source("Yes") == [(0, 3), (3, 2), (7, 10)]
        assert window.saved_translations_manager.positions_of_source("x")[:2] == [(1, 0), (1, 1)]


class TestBatchRun:
    def test_a_text_another_game_translated_is_restored_without_a_request(self, handler, window):
        with patch.object(CachedTranslationDialog, 'exec', return_value=1), \
             patch.object(CachedTranslationDialog, '__init__', autospec=True, side_effect=CachedTranslationDialog.__init__) as dialog:
            remaining, _ = handler._filter_already_saved_translations(
                [{"id": 0, "text": "Yes"}, {"id": 1, "text": "x"}], {0: (7, 10), 1: (7, 9)}
            )

        assert dialog.call_args.args[2][0]['text'] == "Так (HD)" and dialog.call_args.args[2][0]['from_memory'] is True
        assert remaining == [{"id": 1, "text": "x"}]
        assert window.data_processor.get_current_string_text(7, 10)[0] == "Так (HD)"

    def test_the_project_s_own_memory_comes_before_the_series(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")

        with patch.object(CachedTranslationDialog, 'exec', return_value=1), \
             patch.object(CachedTranslationDialog, '__init__', autospec=True, side_effect=CachedTranslationDialog.__init__) as dialog:
            handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert dialog.call_args.args[2][0]['text'] == "Так"


class TestPrompts:
    def test_a_single_string_request_lists_the_other_games_rows(self, handler):
        _system, user = handler.prompt_composer.compose_variation_request(
            "system prompt", "Yes", block_idx=7, string_idx=10, expected_lines=1,
            current_translation="", request_type='translation',
        )
        assert '"in <project>" = another game of the series' in user
        assert '- "Yes" -> "Так (HD)" (in TP HD)' in user and '- "yes" -> "атож" (in WW)' in user

    def test_a_chunk_request_carries_one_row_per_source_the_series_knows(self, handler):
        composer = handler.prompt_composer
        composer._get_mempalace_client = MagicMock(return_value=None)
        composer._find_speaker_in_script = MagicMock(return_value=None)
        composer._fetch_story_context = MagicMock(return_value=None)
        composer._get_structured_story_context = MagicMock(return_value={})
        items = [{"id": 0, "text": "Yes"}, {"id": 1, "text": "x"}]

        _system, user, _ = composer.compose_batch_request("system", items, items, block_idx=7, mode_description="t")

        payload = json.loads(user[user.index("{"):user.rindex("}") + 1])
        assert payload["translated_in_other_games_of_the_series"] == [
            {"text": "Yes", "translation": "Так (HD)", "project": "TP HD"}
        ]


class TestBanner:
    def _banner(self, qtbot, window):
        window.data_processor = DataStateProcessor(window)
        banner = MemoryBanner(window)
        qtbot.addWidget(banner)
        return banner

    def test_it_offers_the_series_translation_and_applies_it_here(self, qtbot, handler, window):
        banner = self._banner(qtbot, window)

        banner.refresh(7, 10)

        assert not banner.isHidden()
        assert banner.label.text() == 'Translated in TP HD: "Так (HD)"'
        assert banner.apply_all_button.text() == "Apply to places with the same context"
        banner.apply_here()
        assert window.data_processor.get_current_string_text(7, 10)[0] == "Так (HD)"
        assert window.data_processor.get_current_string_text(0, 3)[0] == "Yes"

    def test_the_project_s_own_memory_wins_and_apply_everywhere_fills_every_copy(self, qtbot, handler, window):
        banner = self._banner(qtbot, window)
        window.saved_translations_manager.save_translation(0, 3, "Так")

        banner.refresh(7, 10)
        assert banner.label.text() == 'Translated in this project: "Так"'
        banner.apply_everywhere()

        assert [window.data_processor.get_current_string_text(b, s)[0] for b, s in ((0, 3), (3, 2), (7, 10))] == ["Так"] * 3

    def test_a_translated_text_with_copies_offers_to_spread_its_own_translation(self, qtbot, handler, window):
        banner = self._banner(qtbot, window)
        window.saved_translations_manager.series_memory = {}
        window.data_processor.update_edited_data(7, 10, "Еге ж")

        banner.refresh(7, 10)

        assert banner.label.text() == "The same text is in 2 other place(s) of this project."
        assert banner.apply_button.isHidden()
        banner.apply_everywhere()
        assert window.data_processor.get_current_string_text(3, 2)[0] == "Еге ж"

    def test_nothing_known_hides_the_bar(self, qtbot, window):
        banner = self._banner(qtbot, window)
        window.saved_translations_manager.series_memory = {}
        banner.refresh(7, 10)
        banner.refresh(1, 0)  # "x": copies exist, but no translation yet
        assert banner.isHidden()

    def test_apply_everywhere_skips_a_copy_said_by_another_speaker(self, qtbot, handler, window):
        banner = self._banner(qtbot, window)
        window.saved_translations_manager.context_for = _speaker_context({(0, 3): "Ann", (3, 2): "Bob", (7, 10): "Ann"})
        window.data_processor.update_edited_data(7, 10, "Еге ж")

        banner.refresh(7, 10)
        banner.apply_everywhere()

        assert window.data_processor.get_current_string_text(0, 3)[0] == "Еге ж"
        assert window.data_processor.get_current_string_text(3, 2)[0] == "Yes"


class TestSeriesRowsNeedTheSameSpeaker:
    def test_a_series_row_said_by_another_speaker_is_not_offered(self, handler, window):
        window.saved_translations_manager.context_for = _speaker_context({(7, 10): "Bob"})  # the series rows say "NONE"

        with patch.object(CachedTranslationDialog, 'exec', side_effect=AssertionError("no offer expected")):
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert remaining == [{"id": 0, "text": "Yes"}]
