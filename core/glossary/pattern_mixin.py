"""Regex / automaton pattern cache helpers for GlossaryManager."""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

import ahocorasick
import re

from core.glossary.models import GlossaryEntry


class PatternMixin:
    """Regex / automaton pattern cache helpers."""

    def get_compiled_pattern(self, entry: GlossaryEntry) -> Optional[re.Pattern[str]]:
        """Get the compiled pattern."""
        if not entry or not entry.original:
            return None
        return self._compiled_patterns.get(entry.original)

    def iter_compiled(self) -> Iterable[Tuple[GlossaryEntry, re.Pattern[str]]]:
        """Iter compiled."""
        for entry in self._entries:
            pattern = self._compiled_patterns.get(entry.original)
            if pattern:
                yield entry, pattern

    def _build_pattern_cache(self) -> None:
        """Internal helper to create pattern cache."""
        self._compiled_patterns.clear()
        self._first_word_index.clear()
        self._non_word_patterns.clear()
        
        # Use a fresh automaton
        self._automaton = ahocorasick.Automaton()
        
        for entry in self._entries:
            if not entry.original:
                continue
            
            pattern = self._build_regex(entry.original)
            self._compiled_patterns[entry.original] = pattern
            
            # 1. Add to Aho-Corasick for exact matching
            # We use the lowercased version since we search in lowercase
            normalized = entry.original.lower()
            if normalized:
                # Store (entry, length) so find_matches can reconstruct the match
                self._automaton.add_word(normalized, (entry, len(normalized)))

            # 2. Index optimization for regex (case with tags/extra spaces)
            words = self._word_finder.findall(entry.original)
            if words:
                first_word = words[0].lower()
                self._first_word_index.setdefault(first_word, []).append((entry, pattern))
            else:
                self._non_word_patterns.append((entry, pattern))
        
        self._automaton.make_automaton()

    @staticmethod
    def _build_regex(term: str) -> re.Pattern[str]:
        """Internal helper to create regex."""
        if not term:
            return re.compile(r"(?!x)x")

        separator_pattern = r"(?:\s+|·|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"
        
        parts = [p for p in re.split(r'\s+', term) if p]
        if not parts:
            return re.compile(r"(?!x)x")

        escaped_parts = [re.escape(part) for part in parts]
        pattern_body = separator_pattern.join(escaped_parts)

        prefix = r'(?<!\w)'
        suffix = r'(?!\w)'
        if not term[0].isalnum():
            prefix = ''
        if not term[-1].isalnum():
            suffix = ''

        pattern = f"{prefix}{pattern_body}{suffix}"
        return re.compile(pattern, re.IGNORECASE)

    @staticmethod
    def build_translation_regex(term: str) -> Optional[re.Pattern[str]]:
        """
        Build a regex for a translated term that handles Slavic inflections.
        Supports multiple translations separated by semicolons (;).
        """
        if not term or not term.strip():
            return None

        # Split into variations by semicolon
        variations = [v.strip() for v in term.split(';') if v.strip()]
        if not variations:
            return None

        patterns = []
        sep = r"(?:\s+|·|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"

        for var in variations:
            words = var.split()
            if len(words) > 1:
                # Multi-word variation logic
                parts = [PatternMixin._get_word_stem_pattern(word) for word in words]
                patterns.append(rf"(?<!\w){sep.join(parts)}(?!\w)")
            else:
                # Single-word variation logic
                patterns.append(rf"(?<!\w){PatternMixin._get_word_stem_pattern(var)}(?!\w)")
        
        # Combine all variations into a single OR pattern
        combined_pattern = f"(?:{'|'.join(patterns)})"
        return re.compile(combined_pattern, re.IGNORECASE)

    @staticmethod
    def _get_word_stem_pattern(word: str) -> str:
        """Internal helper to get a stem pattern for a single word."""
        if len(word) <= 2:
            return re.escape(word)

        # Common Slavic endings to strip to get a 'soft' stem
        # This is a heuristic, not a full linguistic stemmer
        endings = ['а', 'е', 'и', 'і', 'о', 'у', 'я', 'ь', 'ий', 'ій', 'ая', 'яя', 'ое', 'ее']
        
        stem = word
        for e in sorted(endings, key=len, reverse=True):
            if word.lower().endswith(e):
                stem = word[:-len(e)]
                break
        
        # If stem is too short, fall back to a safer N-character prefix
        if len(stem) < 2:
             stem = word[:3] if len(word) > 3 else word
             
        # Pattern: Stem + any trailing Cyrillic characters (optional)
        # We use [а-яА-ЯіїІїЄєґҐ']* to match optional endings
        return rf"{re.escape(stem)}[а-яА-ЯіїІїЄєґҐ']*"
