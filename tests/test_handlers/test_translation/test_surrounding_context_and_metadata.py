import pytest
from unittest.mock import MagicMock
from core.data_state_processor import DataStateProcessor
from handlers.translation.ai_prompt_composer import AIPromptComposer
from core.project_models import Project, Block
from core.translation.session_manager import TranslationSessionState

def test_DataStateProcessor_is_string_translated():
    # Setup mock MainWindow and DataStore
    mw = MagicMock()
    ds = MagicMock()
    ds.data = [["Original Text 1", "Original Text 2", "", "{escape:0014} [PLAYER]"]]
    ds.edited_file_data = [["Original Text 1", "Original Text 2", "", "{escape:0014} [PLAYER]"]]
    ds.edited_data = {}
    mw.data_store = ds
    
    dsp = DataStateProcessor(mw)
    
    # 1. Initially it should not be translated for standard text
    assert not dsp.is_string_translated(0, 0)
    
    # 2. Add an identical text, should still be False
    ds.edited_data[(0, 0)] = "Original Text 1"
    assert not dsp.is_string_translated(0, 0)
    
    # 3. Add an empty translation, should still be False
    ds.edited_data[(0, 0)] = ""
    assert not dsp.is_string_translated(0, 0)
    
    # 4. Add a valid translation, should be True
    ds.edited_data[(0, 0)] = "Перекладений текст 1"
    assert dsp.is_string_translated(0, 0)

    # 5. Empty original strings should immediately return True (doesn't need translation)
    assert dsp.is_string_translated(0, 2)

    # 6. Tag-only/whitespace original strings should immediately return True (doesn't need translation)
    assert dsp.is_string_translated(0, 3)

def test_DataStateProcessor_update_edited_data_metadata():
    mw = MagicMock()
    ds = MagicMock()
    ds.data = [["Original Text 1"]]
    ds.edited_file_data = [["Original Text 1"]]
    ds.edited_data = {}
    ds.unsaved_changes = False
    ds.unsaved_block_indices = set()
    mw.data_store = ds
    
    # Mock project
    project = Project(name="TestProj")
    block = Block(name="Block1", source_file="src.json", translation_file="tr.json")
    project.blocks = [block]
    
    pm = MagicMock()
    pm.project = project
    mw.project_manager = pm
    mw.block_to_project_file_map = {0: 0}
    
    # Mock translation handler and lifecycle manager active model
    th = MagicMock()
    th.ai_lifecycle_manager._active_model_name = "AI Model"
    mw.translation_handler = th
    
    dsp = DataStateProcessor(mw)
    
    # Update with new translated text
    dsp.update_edited_data(0, 0, "Translated Text 1", action_type="TRANSLATE")
    
    # Check that metadata has been created
    assert "translation_status" in block.metadata
    assert "0" in block.metadata["translation_status"]
    status = block.metadata["translation_status"]["0"]
    assert status["approved"] is False
    assert status["ai_model"] == "AI Model"  # fallback since lifecycle manager is mock

def test_AIPromptComposer_compose_messages_surrounding_context():
    mw = MagicMock()
    ds = MagicMock()
    ds.data = [["Row 0", "Row 1", "Target Row", "Row 3"]]
    ds.edited_file_data = [["Row 0", "Row 1", "Target Row", "Row 3"]]
    ds.edited_data = {}
    mw.data_store = ds
    
    dsp = MagicMock()
    # Mock get_current_string_text
    def mock_get_text(block_idx, string_idx):
        if (block_idx, string_idx) in ds.edited_data:
            return ds.edited_data[(block_idx, string_idx)], "edited_data"
        return ds.data[block_idx][string_idx], "original_data"
    
    def mock_is_translated(block_idx, string_idx):
        if (block_idx, string_idx) in ds.edited_data:
            return ds.edited_data[(block_idx, string_idx)] != ds.data[block_idx][string_idx]
        return False
        
    dsp.get_current_string_text.side_effect = mock_get_text
    dsp.is_string_translated.side_effect = mock_is_translated
    mw.data_processor = dsp
    
    main_handler = MagicMock()
    main_handler.mw = mw
    main_handler.data_processor = dsp
    main_handler._glossary_manager = None
    
    composer = AIPromptComposer(main_handler)
    
    # Set translation for row 1
    ds.edited_data[(0, 1)] = "Translated Row 1"
    
    system_p, user_p = composer.compose_messages(
        system_prompt="Translate this",
        source_text="Target Row",
        block_idx=0,
        string_idx=2,
        expected_lines=1,
        mode_description="test"
    )
    
    # Verify that surrounding context is formatted
    assert "Surrounding Dialogue Context:" in user_p
    assert "[Row #0] (Original): \"Row 0\"" in user_p
    assert "[Row #1] (Original): \"Row 1\"" in user_p
    assert "(Current Translation): \"Translated Row 1\"" in user_p
    assert "[Row #2] (Target - Translate this now): \"Target Row\"" in user_p
    assert "[Row #3] (Original): \"Row 3\"" in user_p
