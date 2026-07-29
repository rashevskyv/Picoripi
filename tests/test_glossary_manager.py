"""
Tests for core/glossary_manager.py — glossary loading, matching, CRUD.
Safety net for refactoring: TranslationHandler split (Issue #3).
"""
import pytest
from core.glossary_manager import GlossaryManager


@pytest.fixture
def manager_with_data(sample_glossary_md):
    """A GlossaryManager loaded with sample data."""
    gm = GlossaryManager()
    gm.load_from_text(plugin_name="test", glossary_path=None, raw_text=sample_glossary_md)
    return gm


# ── Loading & Parsing ───────────────────────────────────────────────

class TestGlossaryLoading:
    def test_load_from_text(self, manager_with_data):
        """Loading markdown populates entries."""
        entries = manager_with_data.get_entries()
        assert len(entries) == 4

    def test_entry_fields(self, manager_with_data):
        """Entries have correct original/translation/notes."""
        entry = manager_with_data.get_entry("Link")
        assert entry is not None
        assert entry.original == "Link"
        assert entry.translation == "Лінк"
        assert "героя" in entry.notes

    def test_empty_glossary(self):
        """Loading empty text produces no entries."""
        gm = GlossaryManager()
        gm.load_from_text(plugin_name="test", glossary_path=None, raw_text="")
        assert gm.get_entries() == []

    def test_raw_text_preserved(self, manager_with_data, sample_glossary_md):
        """Raw text is accessible after loading."""
        assert manager_with_data.get_raw_text() == sample_glossary_md


# ── Get / Find ──────────────────────────────────────────────────────

class TestGlossaryLookup:
    def test_get_entry_case_insensitive(self, manager_with_data):
        """Lookup by original term is case-insensitive."""
        assert manager_with_data.get_entry("link") is not None
        assert manager_with_data.get_entry("LINK") is not None

    def test_get_entry_nonexistent(self, manager_with_data):
        """Non-existent term returns None."""
        assert manager_with_data.get_entry("Ganondorf") is None

    def test_get_entries_sorted_by_length(self, manager_with_data):
        """Sorted entries have longer originals first."""
        sorted_entries = manager_with_data.get_entries_sorted_by_length()
        lengths = [len(e.original) for e in sorted_entries]
        assert lengths == sorted(lengths, reverse=True)

    def test_get_relevant_terms(self, manager_with_data):
        """Find all glossary entries appearing in given text."""
        text = "Link went to Hyrule to find Zelda"
        relevant = manager_with_data.get_relevant_terms(text)
        originals = {e.original for e in relevant}
        assert "Link" in originals
        assert "Hyrule" in originals
        assert "Zelda" in originals
        assert "Rupee" not in originals


# ── Matching ────────────────────────────────────────────────────────

class TestGlossaryMatching:
    def test_find_matches_basic(self, manager_with_data):
        """Find matches returns correct positions."""
        matches = manager_with_data.find_matches("Hello Link!")
        assert len(matches) == 1
        assert matches[0].entry.original == "Link"
        assert matches[0].start == 6
        assert matches[0].end == 10

    def test_find_matches_multiple(self, manager_with_data):
        """Multiple terms in one text are all found."""
        matches = manager_with_data.find_matches("Link visited Hyrule")
        originals = {m.entry.original for m in matches}
        assert "Link" in originals
        assert "Hyrule" in originals

    def test_find_matches_no_result(self, manager_with_data):
        """Text without any glossary terms returns empty list."""
        matches = manager_with_data.find_matches("Nothing special here")
        assert matches == []


# ── CRUD Operations ─────────────────────────────────────────────────

class TestGlossaryCRUD:
    def test_add_entry(self, manager_with_data):
        """Adding a new entry increases count."""
        initial_count = len(manager_with_data.get_entries())
        manager_with_data.add_entry("Ganon", "Ганон", "Головний антагоніст")
        assert len(manager_with_data.get_entries()) == initial_count + 1
        assert manager_with_data.get_entry("Ganon") is not None

    def test_add_duplicate_entry(self, manager_with_data):
        """Adding duplicate original should not create second entry."""
        initial_count = len(manager_with_data.get_entries())
        manager_with_data.add_entry("Link", "Другий Лінк", "Дублікат")
        assert len(manager_with_data.get_entries()) == initial_count

    def test_update_entry(self, manager_with_data):
        """Updating translation changes the entry."""
        manager_with_data.update_entry("Link", "Лінк (оновлено)", "Нові нотатки")
        entry = manager_with_data.get_entry("Link")
        assert entry.translation == "Лінк (оновлено)"
        assert entry.notes == "Нові нотатки"

    def test_update_nonexistent(self, manager_with_data):
        """Updating a non-existent entry does nothing (no crash)."""
        initial_count = len(manager_with_data.get_entries())
        manager_with_data.update_entry("FakeTerm", "Fake", "")
        assert len(manager_with_data.get_entries()) == initial_count

    def test_delete_entry(self, manager_with_data):
        """Deleting an entry removes it."""
        initial_count = len(manager_with_data.get_entries())
        manager_with_data.delete_entry("Link")
        assert len(manager_with_data.get_entries()) == initial_count - 1
        assert manager_with_data.get_entry("Link") is None

    def test_delete_nonexistent(self, manager_with_data):
        """Deleting non-existent entry does nothing."""
        count = len(manager_with_data.get_entries())
        manager_with_data.delete_entry("FakeTerm")
        assert len(manager_with_data.get_entries()) == count


# ── Normalization ───────────────────────────────────────────────────

class TestGlossaryNormalization:
    def test_normalize_term_basic(self):
        assert GlossaryManager.normalize_term("  Hello  ") == "hello"

    def test_normalize_term_whitespace(self):
        assert GlossaryManager.normalize_term("Hello  World") == "hello world"

    def test_normalize_empty(self):
        assert GlossaryManager.normalize_term("") == ""


# ── Session Changes ─────────────────────────────────────────────────

class TestGlossarySession:
    def test_session_changes_tracked(self, manager_with_data):
        """CRUD ops are tracked as session changes."""
        manager_with_data.clear_session_changes()
        manager_with_data.add_entry("NewTerm", "Новий", "")
        changes = manager_with_data.get_session_changes()
        assert len(changes) > 0

    def test_clear_session(self, manager_with_data):
        manager_with_data.add_entry("X", "Y", "")
        manager_with_data.clear_session_changes()
        assert len(manager_with_data.get_session_changes()) == 0
