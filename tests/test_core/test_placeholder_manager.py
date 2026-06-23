import pytest
from unittest.mock import MagicMock, patch
from core.translation.placeholder_manager import AIPlaceholderManager

def test_placeholder_manager_prepare_text_for_translation():
    pm = AIPlaceholderManager()
    txt, mapping = pm.prepare_text_for_translation("Hello", [])
    assert txt == "Hello"
    assert mapping == {}

def test_placeholder_manager_restore_placeholders_empty():
    pm = AIPlaceholderManager()
    assert pm.restore_placeholders("", None) == ""

def test_placeholder_manager_restore_placeholders_normal_tags():
    pm = AIPlaceholderManager()
    default_tag_mappings = {
        "{tag1}": "<TAG1>",
        "{tag2}": "<TAG2>"
    }
    res = pm.restore_placeholders("Translated {tag1} and {tag2}", None, default_tag_mappings=default_tag_mappings)
    assert res == "Translated <TAG1> and <TAG2>"

def test_placeholder_manager_restore_placeholders_force_aliases():
    pm = AIPlaceholderManager()
    
    mock_mapping = MagicMock()
    mock_mapping.word = "Sword"
    
    placeholder_map = {
        42: [mock_mapping]
    }
    
    mock_entry = MagicMock()
    mock_entry.translation = "Меч"
    glossary_manager = MagicMock()
    glossary_manager.get_entry.return_value = mock_entry
    
    with patch('utils.force_alias.restore_force_aliases_in_translation', return_value="Translated Меч") as mock_restore:
        res = pm.restore_placeholders(
            "Translated Sword",
            placeholder_map,
            key=42,
            glossary_manager=glossary_manager
        )
        assert res == "Translated Меч"
        mock_restore.assert_called_once_with(
            "Translated Sword",
            [mock_mapping],
            {"sword": "Меч"}
        )
