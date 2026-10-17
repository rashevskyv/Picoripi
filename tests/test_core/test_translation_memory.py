"""A saved translation is found again by its source text, wherever in the project it was saved (WP4 4.2)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.data_state_processor import DataStateProcessor
from core.saved_translations_manager import MEMORY_VARIANTS, SavedTranslationsManager
from dialogs.cached_translation_dialog import CachedTranslationDialog
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation_handler import TranslationHandler


def _window(tmp_path, data):
    from conftest import MockMainWindow
    mw = MockMainWindow()
    mw.data_store = mw
    mw.data_store.data = data
    mw.data_store.edited_data = {}
    mw.data_store.edited_file_data = []
    mw.data_store.unsaved_changes = False
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.block_names = {str(index): f"Block{index}" for index in range(len(data))}
    mw.data_store.current_chapter_id = None
    mw.data_store.current_category_name = None
    blocks = [
        SimpleNamespace(name=f"Block{index}", source_file=f"src/block{index}.json", internal_key="", metadata={})
        for index in range(len(data))
    ]
    mw.project_manager = MagicMock()
    mw.project_manager.project_dir = str(tmp_path)
    mw.project_manager.project = SimpleNamespace(blocks=blocks, name="P", metadata={}, virtual_folders=[])
    mw.block_to_project_file_map = {index: index for index in range(len(data))}
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    mw.default_tag_mappings = {}
    mw.string_metadata = {}
    mw.icon_sequences = []
    mw.game_dialog_max_width_pixels = 9999
    mw.line_width_warning_threshold_pixels = 9999
    mw.lines_per_page = 99
    mw.prompt_editor_enabled = False
    mw.translation_config = {"provider": "disabled", "workers": 1}
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.convert_editor_text_to_data.side_effect = lambda text: text
    mw.current_game_rules.get_text_representation_for_editor.side_effect = lambda text: text
    mw.current_game_rules.get_shift_enter_char.return_value = "\n"
    mw.saved_translations_manager = SavedTranslationsManager(mw)
    return mw


@pytest.fixture
def window(tmp_path):
    data = [["A", "B", "C", "Yes"]] + [["x"] * 11 for _ in range(7)]
    data[7][10] = "Yes"
    data[3][2] = "[Color:Red]YES[/Color]"
    return _window(tmp_path, data)


class TestStore:
    def test_a_translation_saved_at_one_place_is_found_by_its_source_text(self, window, tmp_path):
        manager = window.saved_translations_manager

        manager.save_translation(0, 3, "Так")

        assert manager.find_by_source("Yes") == "Так"
        assert manager.find_by_source("No") is None
        on_disk = json.loads((tmp_path / "translation_memory.json").read_text(encoding="utf-8"))
        assert list(on_disk.values()) == [[{"source": "Yes", "translation": "Так"}]]
        # the positions file is what it always was
        assert json.loads((tmp_path / "saved_translations.json").read_text(encoding="utf-8")) == {"src/block0.json::::3": "Так"}

    def test_it_survives_a_restart(self, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")

        assert SavedTranslationsManager(window).find_by_source("Yes") == "Так"

    def test_restoring_needs_exactly_the_same_text_the_prompt_hint_does_not(self, window):
        manager = window.saved_translations_manager
        manager.save_translation(0, 3, "Так")

        assert manager.find_by_source("[Color:Red]YES[/Color]") is None            # other tags: not restorable
        assert manager.similar_by_source("[Color:Red]YES[/Color]") == [{"source": "Yes", "translation": "Так"}]

    def test_the_newest_translation_of_a_source_wins_and_old_spellings_are_capped(self, window):
        manager = window.saved_translations_manager
        manager.save_translation(0, 3, "Так")
        manager.save_translations_bulk(7, [(10, "Авжеж")])

        assert manager.find_by_source("Yes") == "Авжеж"
        assert len(manager.similar_by_source("Yes")) == 1                          # one row per exact source

        memory = manager.load_translation_memory()
        for index in range(MEMORY_VARIANTS + 3):
            manager._remember(memory, f"yes{' ' * index}", f"так-{index}")
        assert len(manager.similar_by_source("Yes")) == MEMORY_VARIANTS

    def test_empty_text_and_rows_that_do_not_exist_are_not_remembered(self, window):
        manager = window.saved_translations_manager

        manager.save_translations_bulk(0, [(3, "   "), (99, "Так")])

        assert manager.load_translation_memory() == {}

    def test_a_project_saved_before_the_memory_existed_gets_it_from_its_saved_translations(self, window, tmp_path):
        (tmp_path / "saved_translations.json").write_text(
            json.dumps({"src/block0.json::::3": "Так", "src/block0.json::::0": "А"}), encoding="utf-8"
        )

        manager = SavedTranslationsManager(window)

        assert manager.find_by_source("Yes") == "Так" and manager.find_by_source("A") == "А"
        assert not (tmp_path / "translation_memory.json").exists()                  # written with the next save


@pytest.fixture
def handler(window):
    processor = DataStateProcessor(window)
    window.data_processor = processor
    with patch('handlers.translation.facade.handler.TranslationUIHandler'), \
         patch('PyQt6.QtCore.QTimer.singleShot'):
        translation_handler = TranslationHandler(window, processor, window.ui_updater)
    translation_handler.ui_handler = MagicMock()
    assert isinstance(translation_handler.prompt_composer, AIPromptComposer)
    return translation_handler


class TestRestore:
    def test_the_same_text_at_another_place_is_restored_without_a_request(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")
        items = [{"id": 0, "text": "Yes"}, {"id": 1, "text": "x"}]
        places = {0: (7, 10), 1: (7, 9)}

        with patch.object(CachedTranslationDialog, 'exec', return_value=1), \
             patch.object(CachedTranslationDialog, '__init__', autospec=True, side_effect=CachedTranslationDialog.__init__) as dialog:
            remaining, remaining_places = handler._filter_already_saved_translations(items, places)

        assert dialog.call_args.args[2] == [
            {'block_idx': 7, 'block_name': 'Block7', 'string_idx': 10, 'text': 'Так', 'from_memory': True, 'origin': 'memory'}
        ]
        assert remaining == [{"id": 1, "text": "x"}] and remaining_places == {1: (7, 9)}
        assert window.data_processor.get_current_string_text(7, 10)[0] == "Так"

    def test_the_row_s_own_saved_translation_comes_first(self, handler, window):
        manager = window.saved_translations_manager
        manager.save_translation(7, 10, "Атож")
        manager.save_translation(0, 3, "Так")           # newer, and for the same text elsewhere

        with patch.object(CachedTranslationDialog, 'exec', return_value=1), \
             patch.object(CachedTranslationDialog, '__init__', autospec=True, side_effect=CachedTranslationDialog.__init__) as dialog:
            handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert dialog.call_args.args[2][0]['text'] == "Атож" and dialog.call_args.args[2][0]['from_memory'] is False

    def test_a_remembered_text_that_does_not_fit_the_row_is_not_offered(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")

        offers = []
        with patch.object(handler.batch_translator, '_cached_translation_matches_layout', return_value=False), \
             patch.object(CachedTranslationDialog, 'exec', new=lambda self, *a: offers.append(self) or 1):
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert offers == []
        assert remaining == [{"id": 0, "text": "Yes"}]

    def test_translate_anew_keeps_every_string(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")

        with patch.object(CachedTranslationDialog, 'exec', return_value=2), \
             patch.object(CachedTranslationDialog, '__init__', return_value=None):
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert remaining == [{"id": 0, "text": "Yes"}]
        assert window.data_processor.get_current_string_text(7, 10)[0] == "Yes"


class TestSingleStringPrompt:
    def _compose(self, handler, request_type='translation'):
        _system, user = handler.prompt_composer.compose_variation_request(
            "system prompt", "Yes", block_idx=7, string_idx=10, expected_lines=1,
            current_translation="", request_type=request_type,
        )
        return user

    def test_a_translation_request_shows_what_was_saved_for_the_same_source(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")
        window.saved_translations_manager.save_translation(3, 2, "ТАК")

        user = self._compose(handler)

        assert 'TRANSLATION MEMORY (same source elsewhere;' in user
        assert '- "Yes" -> "Так"' in user and '- "[Color:Red]YES[/Color]" -> "ТАК"' in user

    def test_nothing_saved_means_no_section(self, handler):
        assert 'TRANSLATION MEMORY' not in self._compose(handler)

    def test_a_request_for_variations_is_not_steered_towards_the_saved_wording(self, handler, window):
        window.saved_translations_manager.save_translation(0, 3, "Так")

        assert 'TRANSLATION MEMORY' not in self._compose(handler, request_type='variation_list')


def _speaker_context(speakers):
    """An explicit stand-in for the composer's context: the speaker of each (block, string) is given."""
    def context(block_idx, string_idx, source):
        speaker = speakers[(block_idx, string_idx)]
        return {"speaker": speaker, "addressee": "", "fold": f"fold-{speaker}"}
    return context


class TestContextOfARow:
    """OPEN_ITEMS 4.2: a text that repeats in the project is restored only under the context it was saved under."""

    @pytest.fixture
    def repeated(self, window):
        from core.translation.series_memory import index_source_positions
        window.saved_translations_manager.source_positions = index_source_positions(window.data_store.data)
        window.saved_translations_manager.context_for = _speaker_context({(0, 3): "Ann", (7, 10): "Bob"})
        return window

    def test_the_same_text_said_by_another_speaker_is_not_offered(self, handler, repeated):
        repeated.saved_translations_manager.save_translation(0, 3, "Так")  # said by Ann

        with patch.object(CachedTranslationDialog, 'exec', side_effect=AssertionError("no offer expected")):
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert remaining == [{"id": 0, "text": "Yes"}]
        assert repeated.data_processor.get_current_string_text(7, 10)[0] == "Yes"

    def test_the_same_speaker_gets_the_saved_text_and_the_row_says_so(self, handler, repeated):
        repeated.saved_translations_manager.save_translation(0, 3, "Так")
        repeated.saved_translations_manager.context_for = _speaker_context({(0, 3): "Ann", (7, 10): "Ann"})

        with patch.object(CachedTranslationDialog, 'exec', return_value=1), \
             patch.object(CachedTranslationDialog, '__init__', autospec=True, side_effect=CachedTranslationDialog.__init__) as dialog:
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert dialog.call_args.args[2][0]["origin"] == "memory" and remaining == []
        assert repeated.data_processor.get_current_string_text(7, 10)[0] == "Так"

    def test_an_unchecked_line_is_translated_anew_and_the_others_are_restored(self, handler, repeated):
        manager = repeated.saved_translations_manager
        manager.context_for = _speaker_context({(0, 3): "Ann", (7, 10): "Ann", (3, 2): "Ann"})
        manager.save_translation(0, 3, "Так")
        manager.save_translation(7, 10, "Так, знову")

        def exec_with_second_unchecked(self):
            self._row_boxes[1][1].setChecked(False)
            return 1

        items = [{"id": 0, "text": "Yes"}, {"id": 1, "text": "Yes"}]
        with patch.object(CachedTranslationDialog, 'exec', new=exec_with_second_unchecked):
            remaining, remaining_places = handler._filter_already_saved_translations(items, {0: (0, 3), 1: (7, 10)})

        assert remaining == [{"id": 1, "text": "Yes"}] and remaining_places == {1: (7, 10)}
        assert repeated.data_processor.get_current_string_text(0, 3)[0] == "Так"

    def test_a_row_saved_before_contexts_existed_is_not_offered_for_a_repeated_text(self, handler, repeated):
        manager = repeated.saved_translations_manager
        from core.translation.series_memory import source_hash
        manager._memory = {source_hash("Yes"): [{"source": "Yes", "translation": "Так"}]}  # no context fields
        manager._memory_path_loaded = manager._memory_path()

        with patch.object(CachedTranslationDialog, 'exec', side_effect=AssertionError("no offer expected")):
            remaining, _ = handler._filter_already_saved_translations([{"id": 0, "text": "Yes"}], {0: (7, 10)})

        assert remaining == [{"id": 0, "text": "Yes"}]


class TestRememberKeepsContexts:
    def test_one_row_per_source_and_context_the_newest_wins(self):
        from core.saved_translations_manager import SavedTranslationsManager as Manager
        memory = {}
        Manager._remember(memory, "Yes", "Так", {"speaker": "Ann", "addressee": "", "fold": "a"})
        Manager._remember(memory, "Yes", "Ні", {"speaker": "Bob", "addressee": "", "fold": "b"})
        Manager._remember(memory, "Yes", "Так, знову", {"speaker": "Ann", "addressee": "", "fold": "a"})

        rows = memory[next(iter(memory))]
        assert [(r["translation"], r["fold"]) for r in rows] == [("Ні", "b"), ("Так, знову", "a")]
