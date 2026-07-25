import pytest
from unittest.mock import MagicMock, patch
from handlers.translation_handler import TranslationHandler
from core.saved_translations_manager import SavedTranslationsManager
from core.data_state_processor import DataStateProcessor
from dialogs.cached_translation_dialog import CachedTranslationDialog

@pytest.fixture
def mock_mw():
    from conftest import MockMainWindow
    mw = MockMainWindow()
    
    # Setup data_store
    mw.data_store = mw
    mw.data_store.data = [["original_0", "original_1"]]
    mw.data_store.edited_file_data = []
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.block_names = {"0": "Block0"}
    mw.data_store.displayed_string_indices = [0, 1]
    mw.data_store.current_chapter_id = None
    mw.data_store.current_category_name = None
    
    # Setup project_manager
    mw.project_manager = MagicMock()
    mw.project_manager.project_dir = "/dummy/project/dir"
    mw.project_manager.project = MagicMock()
    mw.project_manager.project.name = "TestProject"
    
    # Mock blocks for project
    block = MagicMock()
    block.source_file = "src/block0.json"
    block.internal_key = "bk0"
    mw.project_manager.project.blocks = [block]
    mw.block_to_project_file_map = {0: 0}
    
    # Setup managers & handlers
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    mw.saved_translations_manager = SavedTranslationsManager(mw)
    mw.default_tag_mappings = {}
    mw.string_metadata = {}
    mw.icon_sequences = []
    
    # Set width thresholds to prevent unexpected formatting wrapping
    mw.game_dialog_max_width_pixels = 9999
    mw.line_width_warning_threshold_pixels = 9999
    mw.lines_per_page = 99
    
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mw.current_game_rules.get_shift_enter_char.return_value = "\n"
    
    return mw


@pytest.fixture
def translation_handler(mock_mw):
    dsp = DataStateProcessor(mock_mw)
    mock_mw.data_processor = dsp
    
    # Avoid doing QTimer single shot in unit tests if not needed
    with patch('handlers.translation_handler.TranslationUIHandler'), \
         patch('handlers.translation_handler.AIPromptComposer'), \
         patch('PyQt6.QtCore.QTimer.singleShot'):
        handler = TranslationHandler(mock_mw, dsp, mock_mw.ui_updater)
        handler.ui_handler = MagicMock()
        handler.prompt_composer = MagicMock()
        handler.prompt_composer.restore_placeholders.side_effect = lambda text, *args, **kwargs: text
    return handler


def test_filter_already_saved_translations_none(translation_handler, mock_mw):
    # Prepare some source items
    source_items = [{"id": 0, "text": "original_0"}, {"id": 1, "text": "original_1"}]
    temp_id_map = {0: (0, 0), 1: (0, 1)}
    
    # No saved translations exist
    with patch.object(mock_mw.saved_translations_manager, 'load_all_saved_translations', return_value={}):
        filtered_items, filtered_map = translation_handler._filter_already_saved_translations(source_items, temp_id_map)
        
        assert len(filtered_items) == 2
        assert filtered_items == source_items
        assert filtered_map == temp_id_map

def test_filter_already_saved_translations_partial(translation_handler, mock_mw):
    source_items = [{"id": 0, "text": "original_0"}, {"id": 1, "text": "original_1"}]
    temp_id_map = {0: (0, 0), 1: (0, 1)}
    
    # "src/block0.json::bk0::0" has a saved translation, string 1 does not
    saved_db = {"src/block0.json::bk0::0": "Saved Translation 0"}
    
    with patch.object(mock_mw.saved_translations_manager, 'load_all_saved_translations', return_value=saved_db), \
         patch.object(translation_handler.data_processor, 'update_edited_data') as mock_update, \
         patch.object(CachedTranslationDialog, 'exec', return_value=1):
         
        filtered_items, filtered_map = translation_handler._filter_already_saved_translations(source_items, temp_id_map)
        
        # String 0 should be applied locally
        mock_update.assert_called_once_with(0, 0, "Saved Translation 0", action_type="RESTORE", skip_ui_refresh=True)
        
        # Remaining items to send to AI
        assert len(filtered_items) == 1
        assert filtered_items[0]["id"] == 1
        assert filtered_map == {1: (0, 1)}

def test_filter_already_saved_translations_all(translation_handler, mock_mw):
    source_items = [{"id": 0, "text": "original_0"}]
    temp_id_map = {0: (0, 0)}
    
    saved_db = {"src/block0.json::bk0::0": "Saved Translation 0"}
    
    with patch.object(mock_mw.saved_translations_manager, 'load_all_saved_translations', return_value=saved_db), \
         patch.object(translation_handler.data_processor, 'update_edited_data') as mock_update, \
         patch.object(CachedTranslationDialog, 'exec', return_value=1):
         
        filtered_items, filtered_map = translation_handler._filter_already_saved_translations(source_items, temp_id_map)
        
        mock_update.assert_called_once_with(0, 0, "Saved Translation 0", action_type="RESTORE", skip_ui_refresh=True)
        assert len(filtered_items) == 0
        assert len(filtered_map) == 0


def test_cached_translation_with_extra_lines_can_be_restored(
    translation_handler, mock_mw
):
    source_items = [{"id": 0, "text": "one\ntwo\nthree"}]
    temp_id_map = {0: (0, 0)}
    saved_db = {
        "src/block0.json::bk0::0": "one\ntwo\nthree\nfour\nfive"
    }

    with patch.object(
        mock_mw.saved_translations_manager,
        'load_all_saved_translations',
        return_value=saved_db,
    ), patch.object(
        translation_handler.data_processor, 'update_edited_data'
    ) as mock_update, patch.object(
        CachedTranslationDialog, 'exec', return_value=1
    ) as mock_dialog:
        filtered_items, filtered_map = (
            translation_handler._filter_already_saved_translations(
                source_items, temp_id_map
            )
        )

    mock_update.assert_called_once_with(
        0,
        0,
        "one\ntwo\nthree\nfour\nfive",
        action_type="RESTORE",
        skip_ui_refresh=True,
    )
    mock_dialog.assert_called_once()
    assert filtered_items == []
    assert filtered_map == {}

def test_translate_and_apply_cache_hit(translation_handler, mock_mw):
    # Test that _translate_and_apply immediately applies a saved translation and skips AI
    saved_db = {"src/block0.json::bk0::0": "Saved Translation 0"}
    
    with patch.object(mock_mw.saved_translations_manager, 'load_all_saved_translations', return_value=saved_db), \
         patch.object(translation_handler.data_processor, 'update_edited_data') as mock_update, \
         patch.object(translation_handler, '_run_ai_task') as mock_run_ai, \
         patch.object(CachedTranslationDialog, 'exec', return_value=1):
         
        translation_handler._translate_and_apply(
            source_text="original_0",
            expected_lines=1,
            mode_description="test",
            block_idx=0,
            string_idx=0
        )
        
        # Should apply locally
        mock_update.assert_called_once_with(0, 0, "Saved Translation 0", action_type="RESTORE", skip_ui_refresh=True)
        # Should not launch AI task
        mock_run_ai.assert_not_called()

def test_handle_single_translation_success_saves_cache(translation_handler, mock_mw):
    response = MagicMock()
    context = {"placeholder_map": {}}
    
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    
    with patch.object(translation_handler.ai_lifecycle_manager, '_clean_model_output', return_value="AI Result"), \
         patch.object(translation_handler, '_format_and_wrap_translation', return_value="AI Result"), \
         patch.object(mock_mw.saved_translations_manager, 'save_translation') as mock_save:
         
        translation_handler._handle_single_translation_success(response, context)
        
        # Verify that translation is saved to SavedTranslationsManager
        mock_save.assert_called_once_with(0, 0, "AI Result")

def test_handle_chunk_translated_saves_cache_bulk(translation_handler, mock_mw):
    chunk_text = '{"translated_strings": [{"id": 0, "translation": "AI Chunk 0"}, {"id": 1, "translation": "AI Chunk 1"}]}'
    context = {
        "block_idx": 0,
        "temp_id_map": {0: (0, 0), 1: (0, 1)},
        "calculated_chunks": [[
            {"id": 0, "text": "Source 0"},
            {"id": 1, "text": "Source 1"},
        ]],
        "placeholder_map": {}
    }
    
    with patch.object(mock_mw.saved_translations_manager, 'save_translations_bulk') as mock_bulk_save:
        translation_handler._handle_chunk_translated(0, chunk_text, context)
        
        # Verify bulk save is called with correct indices and translations
        mock_bulk_save.assert_called_once_with(0, [(0, "AI Chunk 0"), (1, "AI Chunk 1")])

def test_handle_preview_translation_success_saves_cache_bulk(translation_handler, mock_mw):
    response = MagicMock()
    context = {
        "block_idx": 0,
        "source_items": [
            {"id": 0, "text": "Source 0"},
            {"id": 1, "text": "Source 1"},
        ],
        "temp_id_map": {0: (0, 0), 1: (0, 1)},
        "placeholder_map": {}
    }
    
    cleaned_json = '{"translated_strings": [{"id": 0, "translation": "AI Prev 0"}, {"id": 1, "translation": "AI Prev 1"}]}'
    
    with patch.object(translation_handler.ai_lifecycle_manager, '_clean_model_output', return_value=cleaned_json), \
         patch.object(mock_mw.saved_translations_manager, 'save_translations_bulk') as mock_bulk_save:
         
        translation_handler._handle_preview_translation_success(response, context)
        
        # Verify bulk save is called for preview success
        mock_bulk_save.assert_called_once_with(0, [(0, "AI Prev 0"), (1, "AI Prev 1")])
