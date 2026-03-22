import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from core.spellchecker_manager import SpellcheckerManager, LOCAL_DICT_PATH, CUSTOM_DICT_FILENAME

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.edited_text_edit = MagicMock()
    mw.edited_text_edit.highlighter = MagicMock()
    mw.translation_handler = MagicMock()
    mw.translation_handler.glossary_handler = MagicMock()
    mw.translation_handler.glossary_handler.glossary_manager = MagicMock()
    return mw

@patch('core.spellchecker_manager.Dictionary.from_files')
def test_SpellcheckerManager_init(mock_from_files, mock_mw, tmp_path):
    dict_dir = tmp_path / "dict"
    dict_dir.mkdir()
    (dict_dir / "uk.dic").touch()
    (dict_dir / "uk.aff").touch()
    
    mock_from_files.return_value = MagicMock()
    
    sm = SpellcheckerManager(mock_mw, language='uk', custom_dict_path=dict_dir)
    assert sm.language == 'uk'
    assert sm.custom_dict_path == dict_dir
    assert sm.hunspell is not None
    mock_from_files.assert_called_once_with(str(dict_dir / "uk"))

@patch('core.spellchecker_manager.Dictionary.from_files')
def test_SpellcheckerManagerinitialize_spellchecker(mock_from_files, mock_mw, tmp_path):
    # Test file not found scenario
    sm = SpellcheckerManager(mock_mw, language='uk', custom_dict_path=tmp_path)
    # the files don't exist -> hunspell should be None
    assert sm.hunspell is None
    mock_from_files.assert_not_called()

@patch('core.spellchecker_manager.Dictionary.from_files')
def test_SpellcheckerManager_reload_dictionary(mock_from_files, mock_mw, tmp_path):
    sm = SpellcheckerManager(mock_mw, language='uk', custom_dict_path=tmp_path)
    sm.enabled = True
    
    dict_dir = tmp_path / "new_dict"
    dict_dir.mkdir()
    (dict_dir / "en.dic").touch()
    (dict_dir / "en.aff").touch()
    
    sm.reload_dictionary('en', str(dict_dir))
    
    assert sm.language == 'en'
    assert sm.custom_dict_path == dict_dir
    mock_from_files.assert_called_once_with(str(dict_dir / "en"))
    mock_mw.edited_text_edit.highlighter.rehighlight.assert_called_once()

def test_SpellcheckerManager_set_enabled(mock_mw):
    sm = SpellcheckerManager(mock_mw)
    sm.set_enabled(True)
    assert sm.enabled is True
    mock_mw.edited_text_edit.highlighter.set_spellchecker_enabled.assert_called_with(True)
    
    sm.set_enabled(False)
    assert sm.enabled is False
    mock_mw.edited_text_edit.highlighter.set_spellchecker_enabled.assert_called_with(False)

@patch('core.spellchecker_manager.LOCAL_DICT_PATH')
def test_SpellcheckerManager_scan_local_dictionaries(mock_local_path, mock_mw, tmp_path):
    mock_local_path.exists.return_value = True
    mock_local_path.iterdir.return_value = [
        tmp_path / "en.dic",
        tmp_path / "en.aff",
        tmp_path / "fr.dic" # fr.aff missing
    ]
    
    # Needs to actually mock the existence logic of .aff correctly
    with patch.object(Path, 'exists', side_effect=lambda: True):
        # wait, we can just create actual files instead of mocking Path
        pass
        
    # Better approach: actually create files in tmp_path and point LOCAL_DICT_PATH to it
    import core.spellchecker_manager
    core.spellchecker_manager.LOCAL_DICT_PATH = tmp_path
    
    (tmp_path / "de.dic").touch()
    (tmp_path / "de.aff").touch()
    (tmp_path / "es.dic").touch() # missing aff
    
    sm = SpellcheckerManager(mock_mw)
    dicts = sm.scan_local_dictionaries()
    
    assert 'de' in dicts
    assert 'es' not in dicts
    
    core.spellchecker_manager.LOCAL_DICT_PATH = LOCAL_DICT_PATH # restore

@patch('core.spellchecker_manager.LOCAL_DICT_PATH')
def test_SpellcheckerManagerload_user_dictionary(mock_local_path, mock_mw, tmp_path):
    mock_local_path.return_value = tmp_path
    mock_local_path.__truediv__.return_value = tmp_path / CUSTOM_DICT_FILENAME
    
    # Create temp user dict
    custom_dict_file = tmp_path / CUSTOM_DICT_FILENAME
    custom_dict_file.write_text("Hello\nWORLD\n   \nTest", encoding='utf-8')
    
    # We patch Local Dict Path internally
    import core.spellchecker_manager
    core.spellchecker_manager.LOCAL_DICT_PATH = tmp_path
    
    sm = SpellcheckerManager(mock_mw)
    sm._load_user_dictionary()
    
    assert sm.custom_words == {"hello", "world", "test"}
    core.spellchecker_manager.LOCAL_DICT_PATH = LOCAL_DICT_PATH

def test_SpellcheckerManager_reload_glossary_words(mock_mw):
    sm = SpellcheckerManager(mock_mw)
    sm.enabled = True
    sm._load_glossary_words = MagicMock()
    
    sm.reload_glossary_words()
    sm._load_glossary_words.assert_called_once()
    mock_mw.edited_text_edit.highlighter.rehighlight.assert_called_once()

def test_SpellcheckerManagerload_glossary_words(mock_mw):
    sm = SpellcheckerManager(mock_mw)
    
    class FakeEntry:
        def __init__(self, trans):
            self.translation = trans
            
    # Setup mocks
    mock_gm = mock_mw.translation_handler.glossary_handler.glossary_manager
    mock_gm.get_entries.return_value = [
        FakeEntry("Це 'переклад' (тест)"),
        FakeEntry("another translation  123"), # 123 shouldn't be loaded (no digits)
        FakeEntry("too") # too short (<3)
    ]
    
    sm._load_glossary_words()
    
    # words expect length >= 3 and stripped apostrophes
    assert "переклад" in sm.custom_words
    assert "тест" in sm.custom_words
    assert "another" in sm.custom_words
    assert "translation" in sm.custom_words
    assert "це" not in sm.custom_words # len 2
    assert "too" in sm.custom_words # valid length 3
    assert "123" not in sm.custom_words # digits not matching WORD_PATTERN

@patch('core.spellchecker_manager.LOCAL_DICT_PATH')
def test_SpellcheckerManager_add_to_custom_dictionary(mock_local_path, mock_mw, tmp_path):
    mock_local_path.return_value = tmp_path
    mock_local_path.__truediv__.return_value = tmp_path / CUSTOM_DICT_FILENAME
    
    import core.spellchecker_manager
    core.spellchecker_manager.LOCAL_DICT_PATH = tmp_path
    
    sm = SpellcheckerManager(mock_mw)
    sm.hunspell = MagicMock() # required for add to custom dict to work
    
    sm.add_to_custom_dictionary("'Зілля'")
    assert "зілля" in sm.custom_words
    assert (tmp_path / CUSTOM_DICT_FILENAME).read_text(encoding='utf-8').strip() == "зілля"
    
    core.spellchecker_manager.LOCAL_DICT_PATH = LOCAL_DICT_PATH

def test_SpellcheckerManager_is_misspelled(mock_mw):
    sm = SpellcheckerManager(mock_mw)
    sm.enabled = True
    sm.hunspell = MagicMock()
    sm.hunspell.lookup.return_value = False # By default hunspell says everything is wrong
    
    # Test skipping logic
    assert sm.is_misspelled("no") is False # length < 3
    assert sm.is_misspelled("123") is False # digit
    sm.custom_words.add("customword")
    
    # Test custom word
    assert sm.is_misspelled("CustomWord") is False 
    
    # Test hunspell lookup (mocked to false -> so misspelled is True)
    assert sm.is_misspelled("WrongWord") is True
    sm.hunspell.lookup.assert_called_with("WrongWord")
    
    # Disabled check
    sm.enabled = False
    assert sm.is_misspelled("WrongWord") is False

def test_SpellcheckerManager_get_suggestions(mock_mw):
    sm = SpellcheckerManager(mock_mw)
    sm.enabled = True
    sm.hunspell = MagicMock()
    
    # Returns an iterator/generator in real life, so mock a list
    sm.hunspell.suggest.return_value = ["test1", "test2"]
    
    suggestions = sm.get_suggestions("'hello·") # strip dots and quotes
    assert suggestions == ["test1", "test2"]
    sm.hunspell.suggest.assert_called_with("hello")

