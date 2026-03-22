import pytest
from core.glossary_manager import GlossaryManager, GlossaryEntry, GlossaryOccurrence

@pytest.fixture
def gm():
    return GlossaryManager()

def test_GlossaryManager_normalize_term(gm):
    assert gm.normalize_term("  Word  ") == "word"
    assert gm.normalize_term("Multi-Line\nText") == "multi-line text"
    # Unicode normalization check (NFKD)
    assert gm.normalize_term("n\u0303") == "n" # n + tilde -> n (if normalization removes combining marks as per line 68)

def test_GlossaryManager_parse_markdown(gm):
    text = """# Header
## Section 1
| Original | Translation | Notes |
|----------|-------------|-------|
| Sword    | Меч         | Weapon|
| Shield   | Щит         | Armor |
"""
    gm.load_from_text(plugin_name="test", glossary_path=None, raw_text=text)
    entries = gm.get_entries()
    assert len(entries) == 2
    assert entries[0].original == "Sword"
    assert entries[0].section == "Section 1"

def test_GlossaryManager_regex_matching(gm):
    pattern = gm._build_regex("Forest Temple")
    assert pattern.search("Welcome to the Forest Temple!") is not None
    assert pattern.search("forest   temple") is not None # case insensitive + flexible spaces
    # Should not match substrings of words
    assert pattern.search("ForestTemple") is None # word boundaries (?<!\w)

def test_GlossaryManager_build_occurrence_index(gm):
    gm.add_entry("Hero", "Герой", "Main char")
    dataset = [
        ["I am the Hero.", "Not me."],
        ["Hero says hello."]
    ]
    index = gm.build_occurrence_index(dataset)
    hero_occs = index.get("Hero", [])
    assert len(hero_occs) == 2
    assert hero_occs[0].block_idx == 0
    assert hero_occs[0].string_idx == 0
    assert hero_occs[1].block_idx == 1
    assert hero_occs[1].string_idx == 0

def test_GlossaryManager_session_changes_tracking(gm):
    gm.add_entry("New", "Новий", "Note")
    changes = gm.get_session_changes()
    assert "New" in changes
    assert changes["New"].translation == "Новий"
    
    gm.delete_entry("New")
    changes = gm.get_session_changes()
    assert "New" in changes
    assert changes["New"] is None # Deleted marker
