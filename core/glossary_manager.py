# --- START OF FILE core/glossary_manager.py ---
"""Glossary management helpers: loading, caching, and pattern matching."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import re
import unicodedata
import ahocorasick

from utils.logging_utils import log_debug


@dataclass(frozen=True)
class GlossaryEntry:
    """Single glossary record."""

    original: str
    translation: str
    notes: str = ""
    section: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.original and self.translation)


@dataclass(frozen=True)
class GlossaryMatch:
    """Result of matching a glossary entry inside text."""

    entry: GlossaryEntry
    start: int
    end: int


@dataclass(frozen=True)
class GlossaryOccurrence:
    """Specific occurrence of a glossary entry in project data."""

    entry: GlossaryEntry
    block_idx: int
    string_idx: int
    line_idx: int
    start: int
    end: int
    line_text: str


class GlossaryManager:
    """Load and cache glossary entries for a plugin with search utilities."""

    def __init__(self) -> None:
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

    @staticmethod
    def normalize_term(value: str) -> str:
        if value is None:
            return ""
        cleaned = unicodedata.normalize('NFKD', value)
        stripped = ''.join(ch for ch in cleaned if not unicodedata.combining(ch))
        stripped = stripped.lower()
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def load_from_text(
        self,
        *,
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
        raw_text: str,
    ) -> None:
        """Populate glossary from text buffer."""
        self._plugin_name = plugin_name
        self._glossary_path = glossary_path
        sanitized_text = (raw_text or "").replace('\uFEFF', '')
        self._raw_text = sanitized_text
        self._entries = self._parse_markdown(self._raw_text)
        self._build_pattern_cache()
        log_debug(
            f"GlossaryManager: loaded {len(self._entries)} entries for plugin "
            f"{plugin_name or '<global>'} from {str(glossary_path) if glossary_path else '<memory>'}"
        )

    def refresh_from_disk(self) -> None:
        if self._glossary_path and self._glossary_path.exists():
            text = self._glossary_path.read_text(encoding='utf-8')
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text=text,
            )
        else:
            # No glossary file - reset cache to empty
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text="",
            )

    def get_raw_text(self) -> str:
        return self._raw_text

    def get_entries(self) -> Sequence[GlossaryEntry]:
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
        return sorted(self._entries, key=lambda item: len(item.original or ""), reverse=True)

    def get_compiled_pattern(self, entry: GlossaryEntry) -> Optional[re.Pattern[str]]:
        if not entry or not entry.original:
            return None
        return self._compiled_patterns.get(entry.original)

    def iter_compiled(self) -> Iterable[Tuple[GlossaryEntry, re.Pattern[str]]]:
        for entry in self._entries:
            pattern = self._compiled_patterns.get(entry.original)
            if pattern:
                yield entry, pattern

    def find_matches(self, text: str) -> List[GlossaryMatch]:
        if not text:
            return []
            
        matches: List[GlossaryMatch] = []
        seen_ranges: set[Tuple[int, int, str]] = set()

        # Phase 1: Aho-Corasick for exact matches (extremely fast)
        if self._automaton:
            # We search in lowercase for case-insensitivity
            # Note: The automaton was built using normalize_term(original)
            search_text = text.lower()
            for end_pos, (entry, length) in self._automaton.iter(search_text):
                start_pos = end_pos - length + 1
                
                # Verify word boundaries for exact matches
                is_start_boundary = (start_pos == 0 or not text[start_pos-1].isalnum())
                is_end_boundary = (end_pos == len(text)-1 or not text[end_pos+1].isalnum())
                
                if is_start_boundary and is_end_boundary:
                    matches.append(GlossaryMatch(entry=entry, start=start_pos, end=end_pos + 1))
                    seen_ranges.add((start_pos, end_pos + 1, entry.original))

        # Phase 2: Regex fallback for matches with tags/spaces (the current strategy)
        # We only check patterns that haven't been fully satisfied by AC 
        # OR patterns that commonly contain tags.
        text_words = {m.group(0).lower() for m in self._word_finder.finditer(text)}
        
        patterns_to_check = list(self._non_word_patterns)
        for word in text_words:
            if word in self._first_word_index:
                patterns_to_check.extend(self._first_word_index[word])
                
        for entry, pattern in patterns_to_check:
            for match in pattern.finditer(text):
                m_start, m_end = match.span()
                if (m_start, m_end, entry.original) not in seen_ranges:
                    matches.append(GlossaryMatch(entry=entry, start=m_start, end=m_end))
                
        return sorted(matches, key=lambda m: m.start)

    def build_occurrence_index(self, dataset: Sequence) -> Dict[str, List[GlossaryOccurrence]]:
        occurrences: Dict[str, List[GlossaryOccurrence]] = {entry.original: [] for entry in self._entries}
        if not dataset:
            self._occurrence_index = occurrences
            return occurrences

        compiled_entries = list(self.iter_compiled())
        if not compiled_entries:
            self._occurrence_index = occurrences
            return occurrences

        for block_idx, block in enumerate(dataset):
            if not isinstance(block, list):
                continue
            for string_idx, value in enumerate(block):
                text = '' if value is None else str(value)
                if not text:
                    continue
                lines = text.split('\n')
                for line_idx, line in enumerate(lines):
                    if not line:
                        continue
                        
                    # Use the AC-optimized find_matches
                    for match in self.find_matches(line):
                        occ = GlossaryOccurrence(
                            entry=match.entry,
                            start=match.start,
                            end=match.end,
                            block_idx=block_idx,
                            string_idx=string_idx,
                            line_idx=line_idx,
                            line_text=line,
                        )
                        occurrences.setdefault(match.entry.original, []).append(occ)

        self._occurrence_index = occurrences
        return occurrences

    def get_occurrences_for(self, entry: GlossaryEntry) -> List[GlossaryOccurrence]:
        if entry is None or not entry.original:
            return []
        return list(self._occurrence_index.get(entry.original, []))

    def get_occurrence_map(self) -> Dict[str, List[GlossaryOccurrence]]:
        return {key: list(value) for key, value in self._occurrence_index.items()}

    def get_relevant_terms(self, text: str) -> List[GlossaryEntry]:
        """Find all glossary entries that appear in the given text."""
        if not text:
            return []
        matches = self.find_matches(text)
        seen_originals = set()
        relevant_entries = []
        for match in matches:
            if match.entry.original not in seen_originals:
                relevant_entries.append(match.entry)
                seen_originals.add(match.entry.original)
        return relevant_entries

    def get_session_changes(self) -> Dict[str, Optional[GlossaryEntry]]:
        """Return a copy of the session's glossary modifications."""
        return self._session_changes.copy()

    def clear_session_changes(self) -> None:
        """Clear the tracked session glossary modifications."""
        self._session_changes.clear()


    def add_entry(self, original: str, translation: str, notes: str, section: Optional[str] = None) -> Optional[GlossaryEntry]:
        original_key = (original or '').strip()
        if not original_key:
            return None
        existing = next((entry for entry in self._entries if entry.original == original_key), None)
        if existing:
            return self.update_entry(original_key, translation, notes)
        new_entry = GlossaryEntry(
            original=original_key,
            translation=translation.strip(),
            notes=notes.strip(),
            section=section,
        )
        self._session_changes[original_key] = new_entry
        new_entries = list(self._entries)
        new_entries.append(new_entry)
        self._entries = new_entries
        self._occurrence_index = {}
        self._persist()
        return new_entry

    def update_entry(self, original: str, translation: str, notes: str) -> Optional[GlossaryEntry]:
        original_key = (original or '').strip()
        updated_translation = translation.strip()
        updated_notes = notes.strip()
        if not original_key:
            return None

        for idx, entry in enumerate(self._entries):
            if entry.original == original_key:
                updated_entry = GlossaryEntry(
                    original=entry.original,
                    translation=updated_translation,
                    notes=updated_notes,
                    section=entry.section,
                )
                new_entries = list(self._entries)
                new_entries[idx] = updated_entry
                self._entries = new_entries
                self._occurrence_index = {}
                self._session_changes[original_key] = updated_entry
                self._persist()
                return updated_entry
        return None

    def delete_entry(self, original: str) -> bool:
        original_key = (original or '').strip()
        if not original_key:
            return False
        index = next((idx for idx, entry in enumerate(self._entries) if entry.original == original_key), None)
        if index is None:
            return False
        new_entries = list(self._entries)
        del new_entries[index]
        self._entries = new_entries
        self._occurrence_index = {}
        self._session_changes[original_key] = None
        self._persist()
        return True

    def save_to_disk(self) -> None:
        self._persist(write_only=True)

    def _parse_markdown(self, text: str) -> List[GlossaryEntry]:
        self._header_lines = []
        self._section_order = []
        if not text:
            return []

        entries: List[GlossaryEntry] = []
        current_section: Optional[str] = None
        seen_sections: set[str] = set()
        header_phase = True

        for raw_line in text.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                if header_phase:
                    self._header_lines.append(raw_line)
                continue

            if stripped.startswith('## '):
                header_phase = False
                current_section = stripped[3:].strip()
                if current_section and current_section not in seen_sections:
                    seen_sections.add(current_section)
                    self._section_order.append(current_section)
                continue

            if header_phase and (stripped.startswith('#') or stripped.startswith('>')):
                self._header_lines.append(raw_line)
                continue

            if stripped.startswith('|'):
                header_phase = False
                if stripped.startswith('|-'):
                    continue
                parts = [part.strip() for part in stripped.strip('|').split('|')]
                if len(parts) < 3:
                    continue
                header_check = [p.lower() for p in parts[:3]]
                if header_check[0] in {'\u043e\u0440\u0438\u0433\u0456\u043d\u0430\u043b', 'original'} and header_check[1] in {'\u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434', 'translation'}:
                    continue
                original, translation = parts[0], parts[1]
                notes = parts[2] if len(parts) >= 3 else ""
                entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
                if entry.is_valid():
                    entries.append(entry)
                continue

            if '	' in raw_line:
                header_phase = False
                segments = raw_line.split('	')
                while len(segments) < 3:
                    segments.append('')
                original, translation, notes = [segment.strip() for segment in segments[:3]]
                entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
                if entry.is_valid():
                    entries.append(entry)

        return entries

    def _table_lines(self, entries: Sequence[GlossaryEntry]) -> List[str]:
        lines = ['| Original | Translation | Notes |', '|----------|-------------|-------|']
        for entry in entries:
            lines.append(f"| {entry.original} | {entry.translation} | {entry.notes} |")
        return lines

    def _generate_markdown(self) -> str:
        lines: List[str] = []
        if self._header_lines:
            lines.extend(self._header_lines)
            if lines and lines[-1].strip():
                lines.append('')

        default_entries = [entry for entry in self._entries if not entry.section]
        if default_entries:
            lines.extend(self._table_lines(default_entries))
            lines.append('')

        section_to_entries: Dict[str, List[GlossaryEntry]] = {}
        for entry in self._entries:
            if entry.section:
                section_to_entries.setdefault(entry.section, []).append(entry)

        for section in self._section_order:
            section_entries = section_to_entries.get(section, [])
            if not section_entries:
                continue
            if lines and lines[-1].strip():
                lines.append('')
            lines.append(f'## {section}')
            lines.append('')
            lines.extend(self._table_lines(section_entries))
            lines.append('')

        markdown_lines = [line.rstrip() for line in lines if line is not None]
        markdown = "\n".join(markdown_lines).strip("\n") + "\n"
        return markdown

    def _persist(self, write_only: bool = False) -> None:
        markdown = self._generate_markdown()
        self._raw_text = markdown
        if self._glossary_path:
            self._glossary_path.write_text(markdown, encoding='utf-8')
            if not write_only:
                self.load_from_text(
                    plugin_name=self._plugin_name,
                    glossary_path=self._glossary_path,
                    raw_text=markdown,
                )
        else:
            self._build_pattern_cache()

    def _build_pattern_cache(self) -> None:
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
        if not term:
            return re.compile(r"(?!x)x")

        separator_pattern = r"(?:\s+|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"
        
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
        It uses a simple 'stemming' approach to allow for case endings.
        """
        if not term or not term.strip():
            return None

        # 1. Clean up and lower
        term = term.strip()
        
        # 2. Handle multi-word terms
        words = term.split()
        if len(words) > 1:
            parts = [GlossaryManager._get_word_stem_pattern(word) for word in words]
            sep = r"(?:\s+|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"
            pattern = rf"(?<!\w){sep.join(parts)}(?!\w)"
            return re.compile(pattern, re.IGNORECASE)
        
        # 3. Handle single word
        pattern = rf"(?<!\w){GlossaryManager._get_word_stem_pattern(term)}(?!\w)"
        return re.compile(pattern, re.IGNORECASE)

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