import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import re

from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryMatch, GlossaryOccurrence

def test_GlossaryEntry_is_valid():
    assert GlossaryEntry("term", "term").is_valid()
    assert GlossaryEntry("term", "translation", "note").is_valid()
    assert not GlossaryEntry("", "translation").is_valid()
    assert not GlossaryEntry("term", "").is_valid()

@pytest.fixture
def manager():
    return GlossaryManager()

def test_GlossaryManager_normalize_term():
    assert GlossaryManager.normalize_term(None) == ""
    assert GlossaryManager.normalize_term("  Hello  World ") == "hello world"
    assert GlossaryManager.normalize_term("Pokémon") == "pokemon"
    assert GlossaryManager.normalize_term("HÉLLÔ") == "hello"
    assert GlossaryManager.normalize_term("CHILD #1") == "child 1"
    assert GlossaryManager.normalize_term("Дитина #1") == "дитина 1"

def test_GlossaryManager_load_from_text(manager):
    md = """# My Glossary
## Items
| Original | Translation | Notes |
|----------|-------------|-------|
| Apple | Яблуко | |
| Orange | Апельсин | note |

## Characters
| Hero | Герой | |
"""
    manager.load_from_text(plugin_name="plug", glossary_path=None, raw_text=md)
    entries = manager.get_entries()
    assert len(entries) == 3
    assert entries[0].original == "Apple"
    assert entries[1].section == "Items"
    assert entries[2].original == "Hero"
    assert entries[2].section == "Characters"

def test_GlossaryManager_load_from_text_tab_separated(manager):
    text = "Apple\tЯблуко\tnote\nOrange\tАпельсин"
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text=text)
    entries = manager.get_entries()
    assert len(entries) == 2
    assert entries[0].original == "Apple"
    assert entries[0].notes == "note"
    assert entries[1].original == "Orange"
    assert entries[1].notes == ""

def test_GlossaryManager_refresh_from_disk(manager, tmp_path):
    f = tmp_path / "glossary.md"
    f.write_text("Apple\tЯблуко", encoding="utf-8")
    manager._glossary_path = f
    manager.refresh_from_disk()
    assert len(manager.get_entries()) == 1
    
    # file deleted
    f.unlink()
    manager.refresh_from_disk()
    assert len(manager.get_entries()) == 0

def test_GlossaryManager_get_entry(manager):
    manager._entries = [GlossaryEntry("Apple", "Яблуко")]
    assert manager.get_entry("apple") is not None
    assert manager.get_entry("APPLE") is not None
    assert manager.get_entry("banana") is None
    assert manager.get_entry("") is None

def test_GlossaryManager_get_entries_sorted_by_length(manager):
    manager._entries = [
        GlossaryEntry("A", "А"),
        GlossaryEntry("Apple", "Яблуко")
    ]
    sorted_entries = manager.get_entries_sorted_by_length()
    assert sorted_entries[0].original == "Apple"

def test_GlossaryManager_find_matches(manager):
    manager._entries = [GlossaryEntry("magic potion", "магічне зілля")]
    manager._build_pattern_cache()
    
    # match is case-insensitive, ignores tags and extra spaces
    text = "Find the <tag>magic</tag>   potion!"
    matches = manager.find_matches(text)
    assert len(matches) == 1
    assert matches[0].entry.original == "magic potion"
    assert matches[0].start == 14
    assert matches[0].end == 34
    
    assert manager.find_matches("") == []

def test_GlossaryManager_build_occurrence_index(manager):
    manager._entries = [GlossaryEntry("Sword", "Меч")]
    manager._build_pattern_cache()
    
    dataset = [
        ["I have a sword.", "Nothing here"],
        ["Sword of destiny\nAnother sword"]
    ]
    
    manager.build_occurrence_index(dataset)
    occs = manager.get_occurrences_for(manager._entries[0])
    assert len(occs) == 3
    assert occs[0].block_idx == 0
    assert occs[0].string_idx == 0
    assert occs[1].block_idx == 1
    assert occs[1].line_idx == 0
    assert occs[2].block_idx == 1
    assert occs[2].line_idx == 1
    
    # Test empty datasets
    assert manager.build_occurrence_index([]) == {"Sword": []}
    manager._entries = []
    assert manager.build_occurrence_index(dataset) == {}

def test_GlossaryManager_get_relevant_terms(manager):
    e1 = GlossaryEntry("Sword", "Меч")
    e2 = GlossaryEntry("Shield", "Щит")
    manager._entries = [e1, e2]
    manager._build_pattern_cache()
    
    terms = manager.get_relevant_terms("I have a sword and another sword")
    assert len(terms) == 1
    assert terms[0].original == "Sword"
    
    assert manager.get_relevant_terms("") == []

def test_GlossaryManager_session_changes(manager):
    manager.add_entry("Apple", "Яблуко", "Note")
    assert "Apple" in manager.get_session_changes()
    manager.clear_session_changes()
    assert not manager.get_session_changes()

def test_GlossaryManager_crud_entry(manager):
    manager.add_entry("", "Empty", "")
    assert len(manager.get_entries()) == 0
    
    e1 = manager.add_entry("Apple", "Яблуко", "Note1")
    assert e1.original == "Apple"
    
    # Add existing should update
    e2 = manager.add_entry("Apple", "Яблучко", "Note2")
    assert e2.translation == "Яблучко"
    assert len(manager.get_entries()) == 1
    
    # Update explicitly
    manager.update_entry("Apple", "Яблуко3", "Note3")
    assert manager.get_entry("Apple").translation == "Яблуко3"
    assert manager.update_entry("", "T", "") is None
    assert manager.update_entry("Missing", "T", "") is None
    
    # Delete
    assert manager.delete_entry("Apple") is True
    assert len(manager.get_entries()) == 0
    assert manager.delete_entry("Apple") is False
    assert manager.delete_entry("") is False

def test_GlossaryManager_persist(manager, tmp_path):
    f = tmp_path / "glossary.json"
    manager._glossary_path = f
    
    manager.add_entry("Apple", "Яблуко", "")
    manager._section_order = ["Fruits"]
    manager.add_entry("Orange", "Апельсин", "", section="Fruits")
    manager.save_to_disk()
    
    text = f.read_text(encoding="utf-8")
    assert "Apple" in text
    assert "Яблуко" in text
    assert "Fruits" in text
    assert "Orange" in text
    assert manager._raw_text == text


def test_GlossaryManager_persist_new_sections(manager, tmp_path):
    f = tmp_path / "glossary.json"
    manager._glossary_path = f
    
    manager.add_entry("Apple", "Яблуко", "")
    manager._section_order = ["Fruits"]
    manager.add_entry("Orange", "Апельсин", "", section="Fruits")
    
    # Add a brand new section not present in _section_order
    manager.add_entry("Sword", "Меч", "", section="Weapons")
    manager.save_to_disk()
    
    text = f.read_text(encoding="utf-8")
    assert "Apple" in text
    assert "Fruits" in text
    assert "Orange" in text
    assert "Weapons" in text
    assert "Sword" in text


def test_GlossaryManager_build_regex():
    pat = GlossaryManager._build_regex("magic potion")
    assert pat.search("magic potion")
    assert pat.search("magic   potion")
    assert pat.search("magic<color=red>potion")
    assert not pat.search("magical potion")

    assert GlossaryManager._build_regex("").pattern == "(?!x)x"
    assert GlossaryManager._build_regex("  ").pattern == "(?!x)x"
    
    # Test non-alphanumeric term
    pat_punct = GlossaryManager._build_regex("...")
    assert pat_punct.search("Hey...")

def test_GlossaryManager_prefilter_logic(manager):
    # Test our First-Word Pre-filter optimization specifically
    manager._entries = [
        GlossaryEntry("Master Sword", "Майстер Меч"),
        GlossaryEntry("+1 Shield", "Щит +1"),
        GlossaryEntry("!!!", "Обережно"),
    ]
    manager._build_pattern_cache()
    
    # 1. Term basic
    assert len(manager.find_matches("I found the Master Sword!")) == 1
    
    # 2. Term split by invisible chars/tags
    assert len(manager.find_matches("I found the Master{Color:Red} Sword!")) == 1
    
    # 3. Term starting with non-letter but having a digit (digit is a word char \w)
    # The word finder extracts '1' as the first word
    assert len(manager.find_matches("Here is a +1 Shield")) == 1
    
    # 4. Purely non-word term (!!! -> should be in _non_word_patterns)
    assert len(manager.find_matches("Watch out!!! It's dangerous!")) == 1
    
    # 5. Multiple matches
    matches = manager.find_matches("Master Sword !!! +1 Shield")
    assert len(matches) == 3

def test_GlossaryManager_multiline_notes_and_pipe_escaping(manager, tmp_path):
    g_path = tmp_path / "glossary.json"
    manager._glossary_path = g_path
    
    entry_original = "WHITE CUCCO"
    entry_translation = "Білий Куко"
    entry_notes = "📌 **Хто цей персонаж (Загальний опис та роль)**:\nЦе біла курка.\n\n🎭 **Характер**:\nСпокійний."
    
    manager.add_entry(entry_original, entry_translation, entry_notes)
    
    persisted_text = g_path.read_text(encoding="utf-8")
    assert "WHITE CUCCO" in persisted_text
    
    manager.refresh_from_disk()
    loaded_entry = manager.get_entry(entry_original)
    
    assert loaded_entry is not None
    assert loaded_entry.notes == entry_notes
    assert "\n" in loaded_entry.notes


def test_GlossaryManager_profiled_field(manager, tmp_path):
    f = tmp_path / "glossary.json"
    manager._glossary_path = f
    
    # 1. Add entry with profiled=True
    manager.add_entry("Apple", "Яблуко", "Note", profiled=True)
    assert manager.get_entry("Apple").profiled is True
    
    # 2. Add entry with default profiled (False)
    manager.add_entry("Banana", "Банан", "Note")
    assert manager.get_entry("Banana").profiled is False
    
    # 3. Update entry to profiled=False
    manager.update_entry("Apple", "Яблуко", "Note", profiled=False)
    assert manager.get_entry("Apple").profiled is False
    
    # 4. Save and reload from disk
    manager.save_to_disk()
    manager.refresh_from_disk()
    assert manager.get_entry("Apple").profiled is False
    
    # 5. Set profiled=True and save again
    manager.update_entry("Apple", "Яблуко", "Note", profiled=True)
    manager.save_to_disk()
    manager.refresh_from_disk()
    assert manager.get_entry("Apple").profiled is True


def test_preserve_case():
    from core.glossary_manager import preserve_case
    assert preserve_case("ГОРОН", "ґорон") == "ҐОРОН"
    assert preserve_case("Горон", "ґорон") == "Ґорон"
    assert preserve_case("горон", "ґорон") == "ґорон"
    assert preserve_case("", "ґорон") == "ґорон"
    assert preserve_case("Горон", "") == ""
    assert preserve_case("GoRoN", "ґорон") == "Ґорон"


def test_replace_preserve_case():
    from core.glossary_manager import replace_preserve_case
    text = "Я зустрів Горона, а також ГОРОН і горонські скелі."
    replaced = replace_preserve_case(text, "горон", "ґорон")
    assert replaced == "Я зустрів Ґорона, а також ҐОРОН і ґоронські скелі."
    
    assert replace_preserve_case("", "горон", "ґорон") == ""
    assert replace_preserve_case("тест", "", "ґорон") == "тест"


def test_GlossaryManager_global_replace(manager):
    e1 = GlossaryEntry("Link", "Лінк", "Горонський герой")
    e2 = GlossaryEntry("Goron Elder", "Старійшина Горонів", "Старійшина")
    manager._entries = [e1, e2]
    
    modified = manager.global_replace("горон", "ґорон")
    
    assert len(manager.get_entries()) == 2
    assert manager.get_entry("Link").notes == "Ґоронський герой"
    assert manager.get_entry("Goron Elder").translation == "Старійшина Ґоронів"
    
    assert len(modified) == 2
    # e1 notes modified, translation unchanged
    assert modified[0][0].original == "Link"
    assert modified[0][1] == "Лінк"
    assert modified[0][2].translation == "Лінк"
    # e2 translation modified
    assert modified[1][0].original == "Goron Elder"
    assert modified[1][1] == "Старійшина Горонів"
    assert modified[1][2].translation == "Старійшина Ґоронів"


