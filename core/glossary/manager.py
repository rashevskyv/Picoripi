"""GlossaryManager composition and core getters."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import ahocorasick
import re
import unicodedata

from core.glossary.models import GlossaryEntry, GlossaryOccurrence
from core.glossary.mutation_mixin import MutationMixin
from core.glossary.occurrence_mixin import OccurrenceMixin
from core.glossary.parse_mixin import ParseMixin
from core.glossary.pattern_mixin import PatternMixin


class GlossaryManager(
    ParseMixin,
    OccurrenceMixin,
    PatternMixin,
    MutationMixin,
):
    """Load and cache glossary entries for a plugin with search utilities."""

    def __init__(self) -> None:
        """Initialize a new instance."""
        self._entries: List[GlossaryEntry] = []
        self._raw_text: str = ""
        self._compiled_patterns: Dict[str, re.Pattern[str]] = {}
        self._glossary_path: Optional[Path] = None
        self._plugin_name: Optional[str] = None
        self._occurrence_index: Dict[str, List[GlossaryOccurrence]] = {}
        self._header_lines: List[str] = []
        self._section_order: List[str] = []
        self._session_changes: Dict[str, Optional[GlossaryEntry]] = {}

        # Optimization structures for fast pattern matching
        self._automaton: Optional[ahocorasick.Automaton] = None
        self._first_word_index: Dict[str, List[Tuple[GlossaryEntry, re.Pattern[str]]]] = {}
        self._non_word_patterns: List[Tuple[GlossaryEntry, re.Pattern[str]]] = []
        self._word_finder = re.compile(r'\w+')
        # Optional project context so a character term whose name never appears
        # in dialogue still owns the rows it actually speaks / the block named
        # after it. Without this, "VILLAGE GORON #2" shows Occurrences: 0
        # while the block list shows three lines.
        self._block_names: Dict[int, str] = {}
        self._speaker_for: Optional[Callable[[int, int], Optional[str]]] = None
        self._speaker_aliases: Dict[str, str] = {}
        self._speaker_pool: Optional[Dict[Tuple[int, int], str]] = None

    @staticmethod
    def normalize_term(value: str) -> str:
        """Normalize term."""
        if value is None:
            return ""
        cleaned = unicodedata.normalize('NFKD', value)
        stripped = ''.join(ch for ch in cleaned if not unicodedata.combining(ch))
        stripped = stripped.lower().replace('#', ' ')
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def get_entries(self) -> Sequence[GlossaryEntry]:
        """Get the entries."""
        return list(self._entries)

    def get_entry(self, term: str) -> Optional[GlossaryEntry]:
        """Find a glossary entry by its original term, ignoring case and spacing."""
        if not term:
            return None
        normalized_term = self.normalize_term(term)
        for entry in self._entries:
            if self.normalize_term(entry.original) == normalized_term:
                return entry
        return None

    def get_entries_sorted_by_length(self) -> Sequence[GlossaryEntry]:
        """Get the entries sorted by length."""
        return sorted(self._entries, key=lambda item: len(item.original or ""), reverse=True)
