"""GlossaryManager composition and core getters."""
from __future__ import annotations

from functools import lru_cache
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


_ARTICLES = frozenset({"the", "a", "an"})
# Words that end in "s" without being plurals.
_NOT_PLURAL = frozenset({"lens", "series", "species", "chaos", "news", "always", "perhaps", "yes"})


def _fold_plural(token: str) -> str:
    """The singular of an English plural; anything else is returned unchanged."""
    if len(token) <= 3 or not token.isascii() or not token.isalpha() or token in _NOT_PLURAL:
        return token
    if token.endswith(("ss", "us", "is")):
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("ses", "xes", "zes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s"):
        return token[:-1]
    return token


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
    @lru_cache(maxsize=16384)
    def normalize_term(value: str) -> str:
        """Normalize term."""
        if value is None:
            return ""
        cleaned = unicodedata.normalize('NFKD', value)
        stripped = ''.join(ch for ch in cleaned if not unicodedata.combining(ch))
        stripped = stripped.lower().replace('#', ' ')
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    @staticmethod
    @lru_cache(maxsize=16384)
    def canonical_key(value: str) -> str:
        """One key for every spelling of the same term.

        ``normalize_term`` plus: punctuation and possessives dropped, a leading
        article dropped, English plurals folded ("Hylian Shields" and "hylian
        shield", "The Postman" and "POSTMAN", "Fairy's Tears" and "fairy tear"
        share a key). It decides whether a *new* term is one the glossary
        already has; it is not a display form and it never merges existing
        entries by itself -- two entries that share a key but mean different
        things ("Clawshot" / "Clawshots") stay two entries until a person or
        the reconcile pass says otherwise.
        """
        text = GlossaryManager.normalize_term(value)
        text = re.sub(r"['’]s\b", "", text)        # possessive
        text = re.sub(r"[^\w\s]|_", " ", text)          # punctuation
        tokens = text.split()
        if len(tokens) > 1 and tokens[0] in _ARTICLES:
            tokens = tokens[1:]
        return " ".join(_fold_plural(token) for token in tokens)

    def canonical_groups(self) -> List[List[GlossaryEntry]]:
        """Entries that share a canonical key, as groups of two or more, in key order."""
        groups: Dict[str, List[GlossaryEntry]] = {}
        for entry in self._entries:
            key = self.canonical_key(entry.original)
            if key:
                groups.setdefault(key, []).append(entry)
        return [groups[key] for key in sorted(groups) if len(groups[key]) > 1]

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
        for entry in self._entries:
            if any(self.normalize_term(alias) == normalized_term for alias in entry.aliases):
                return entry
        return None

    def find_entry(self, term: str) -> Optional[GlossaryEntry]:
        """The entry a build would write ``term`` into: exact, then by case and
        spacing, then by alias, then by canonical key (plural, article, possessive)."""
        index = self._index_of(term)
        return self._entries[index] if index is not None else None

    def get_entries_sorted_by_length(self) -> Sequence[GlossaryEntry]:
        """Get the entries sorted by length."""
        return sorted(self._entries, key=lambda item: len(item.original or ""), reverse=True)
