"""Interface words fixed by the glossary are filled without a request; a single request names the addressee (WP4 4.4)."""
from unittest.mock import MagicMock, patch

import pytest

from core.data_state_processor import DataStateProcessor
from core.glossary.models import STATUS_CONFIRMED, STATUS_TRANSLATED, GlossaryEntry
from core.translation.config import build_default_translation_config
from core.translation.fixed_output import DEFAULT_SECTIONS, fixed_output_sections, fixed_translation
from dialogs.cached_translation_dialog import CachedTranslationDialog
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation_handler import TranslationHandler


class _Glossary:
    """get_entry as GlossaryManager does it: by the term or an alias, ignoring case and spacing."""

    def __init__(self, *entries):
        self.entries = list(entries)

    def get_entry(self, term):
        wanted = " ".join(str(term).split()).casefold()
        for entry in self.entries:
            if wanted in {entry.original.casefold(), *(alias.casefold() for alias in entry.aliases)}:
                return entry
        return None

    def get_relevant_terms(self, _text, **_options):
        return []

    def get_entries(self):
        return list(self.entries)


OK = GlossaryEntry("OK", "Гаразд", section="UI", status=STATUS_CONFIRMED, aliases=("Okay",))
BACK = GlossaryEntry("Back", "Назад", section="ui")                       # a legacy entry without a status
SWORD = GlossaryEntry("Sword", "Меч", section="Items", status=STATUS_CONFIRMED)
SUGGESTED = GlossaryEntry("Cancel", "Скасувати", section="UI", status=STATUS_TRANSLATED)
GLOSSARY = _Glossary(OK, BACK, SWORD, SUGGESTED)


class TestFixedTranslation:
    def test_a_string_that_is_exactly_a_term_of_the_ui_section_is_fixed(self):
        assert fixed_translation("OK", GLOSSARY) == "Гаразд"
        assert fixed_translation("Back", GLOSSARY) == "Назад"
        assert fixed_translation("Okay", GLOSSARY) == "Гаразд"              # an alias, exactly

    @pytest.mark.parametrize("text", ["ok", "OK!", " OK", "OK\n", "It is OK", "", None])
    def test_anything_else_goes_to_the_model(self, text):
        assert fixed_translation(text, GLOSSARY) is None

    def test_other_sections_and_unconfirmed_suggestions_fix_nothing(self):
        assert fixed_translation("Sword", GLOSSARY) is None
        assert fixed_translation("Cancel", GLOSSARY) is None

    def test_the_sections_come_from_the_translation_config(self):
        assert fixed_output_sections(build_default_translation_config()) == DEFAULT_SECTIONS == ("UI",)
        assert fixed_output_sections({"fixed_output_sections": ["Items", " "]}) == ("Items",)
        assert fixed_output_sections({"fixed_output_sections": []}) == ()
        assert fixed_translation("Sword", GLOSSARY, ("Items",)) == "Меч"
        assert fixed_translation("OK", GLOSSARY, ()) is None

    def test_no_glossary_or_a_mock_fixes_nothing(self):
        assert fixed_translation("OK", None) is None
        assert fixed_translation("OK", MagicMock()) is None


@pytest.fixture
def window():
    from conftest import MockMainWindow
    mw = MockMainWindow()
    mw.data_store = mw
    mw.data_store.data = [["OK", "Hello there", "Back", "OK", "ok", "Sword"]]
    mw.data_store.edited_data = {}
    mw.data_store.unsaved_changes = False
    mw.data_store.edited_file_data = []
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.block_names = {"0": "Block0"}
    mw.data_store.current_chapter_id = None
    mw.data_store.current_category_name = None
    mw.project_manager = None
    mw.block_to_project_file_map = {0: 0}
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    mw.saved_translations_manager = None
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
    mw.current_game_rules.get_display_name.return_value = "Test Game"
    return mw


@pytest.fixture
def handler(window):
    processor = DataStateProcessor(window)
    window.data_processor = processor
    with patch('handlers.translation.facade.handler.TranslationUIHandler'), \
         patch('PyQt6.QtCore.QTimer.singleShot'):
        translation_handler = TranslationHandler(window, processor, window.ui_updater)
    translation_handler.ui_handler = MagicMock()
    translation_handler._glossary_manager = GLOSSARY
    assert isinstance(translation_handler.prompt_composer, AIPromptComposer)
    return translation_handler


def _items(window):
    return [{"id": index, "text": text} for index, text in enumerate(window.data_store.data[0])]


class TestPrePass:
    def test_fixed_strings_are_filled_and_never_reach_the_model(self, handler, window):
        with patch.object(CachedTranslationDialog, 'exec') as asked:
            remaining, _ = handler._filter_already_saved_translations(_items(window), {})

        asked.assert_not_called()                                            # nothing to confirm: the glossary decided
        assert [item["text"] for item in remaining] == ["Hello there", "ok", "Sword"]
        rows = [window.data_processor.get_current_string_text(0, index)[0] for index in range(6)]
        assert rows == ["Гаразд", "Hello there", "Назад", "Гаразд", "ok", "Sword"]
        window.undo_manager.end_group.assert_called_once_with("FIXED_OUTPUT")

    def test_a_run_over_several_blocks_places_each_row(self, handler, window):
        window.data_store.data.append(["x", "OK"])
        items = [{"id": 0, "text": "OK"}, {"id": 1, "text": "x"}]

        remaining, places = handler._filter_already_saved_translations(items, {0: (1, 1), 1: (1, 0)})

        assert remaining == [{"id": 1, "text": "x"}] and places == {1: (1, 0)}
        assert window.data_processor.get_current_string_text(1, 1)[0] == "Гаразд"

    def test_a_row_that_already_has_a_translation_is_left_as_it_is(self, handler, window):
        window.data_processor.update_edited_data(0, 0, "Добре", action_type="EDIT", skip_ui_refresh=True)

        remaining, _ = handler._filter_already_saved_translations(_items(window), {})

        assert window.data_processor.get_current_string_text(0, 0)[0] == "Добре"
        assert remaining[0] == {"id": 0, "text": "OK"}                        # it goes on as any translated row does

    def test_a_glossary_text_that_does_not_fit_the_row_is_not_forced_in(self, handler, window):
        with patch.object(handler.batch_translator, '_cached_translation_matches_layout', return_value=False):
            remaining, _ = handler._filter_already_saved_translations(_items(window), {})

        assert len(remaining) == 6
        assert window.data_processor.get_current_string_text(0, 0)[0] == "OK"

    def test_the_feature_is_off_with_an_empty_section_list(self, handler, window):
        window.translation_config["fixed_output_sections"] = []

        remaining, _ = handler._filter_already_saved_translations(_items(window), {})

        assert len(remaining) == 6

    def test_when_everything_is_fixed_nothing_is_left_to_translate(self, handler, window):
        remaining, places = handler._filter_already_saved_translations([{"id": 0, "text": "OK"}], {})

        assert remaining == [] and places == {}


class TestSingleRequestAddressee:
    def _compose(self, handler):
        _system, user = handler.prompt_composer.compose_variation_request(
            "system prompt", "Hello there", block_idx=0, string_idx=1, expected_lines=1,
            current_translation="", request_type='translation',
        )
        return user

    def test_the_addressee_the_plugin_reports_is_in_the_request(self, handler, window):
        window.current_game_rules.get_addressee_for_string.return_value = "Ilia"

        user = self._compose(handler)

        assert "Addressee: Ilia" in user
        assert window.current_game_rules.get_addressee_for_string.call_args.args == (0, 1)

    def test_no_addressee_no_line(self, handler, window):
        window.current_game_rules.get_addressee_for_string.return_value = None

        assert "Addressee:" not in self._compose(handler)

    def test_the_rules_tell_the_model_what_the_line_is_for(self):
        from handlers.translation.prompt_composer.instructions import single_rules

        assert 'ADDRESSEE: If an "Addressee:" line is present' in single_rules('translation')
