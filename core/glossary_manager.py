"""Glossary management helpers: loading, caching, and pattern matching."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Callable
import re
import unicodedata
import ahocorasick

from utils.logging_utils import log_debug


# Lifecycle status of a glossary entry (roadmap section 3). An empty string is a
# legacy entry with no explicit status, treated as already usable.
STATUS_SEEDED = "seeded"            # term only
STATUS_FRAGMENTS = "fragments"      # description fragments accumulated
STATUS_SYNTHESIZED = "synthesized"  # fragments folded into one description
STATUS_TRANSLATED = "translated"    # one or more translation variants proposed
STATUS_CONFIRMED = "confirmed"      # user picked the active translation

# Descriptions are written before a translation is chosen, so a note must not
# bake in one particular rendering of the term: the build prompts write this
# placeholder wherever the term itself is named, and it is substituted with
# whichever variant the user settles on.
#
# The substitution is literal. Ukrainian and other Slavic targets decline nouns,
# so the prompts ask for phrasing that keeps the placeholder in the nominative;
# declining an arbitrary noun phrase by rule is not something this layer can do
# honestly. A note that needs the term in an oblique case should be rewritten
# (the AI Variations button) rather than patched by string surgery.
TERM_PLACEHOLDER = "{{TERM}}"


def render_notes(notes: str, *, translation: str = "", original: str = "") -> str:
    """Substitute the term placeholder with the chosen translation.

    Falls back to the source term, and finally leaves the placeholder visible,
    so a note never silently loses the subject of its own sentence.
    """
    if not notes or TERM_PLACEHOLDER not in notes:
        return notes or ""
    replacement = (translation or "").strip() or (original or "").strip()
    return notes.replace(TERM_PLACEHOLDER, replacement) if replacement else notes


# Statuses whose entries still await a confirmed human decision; the UI
# highlights these as unconfirmed (roadmap section 7).
UNCONFIRMED_STATUSES = frozenset(
    {STATUS_SEEDED, STATUS_FRAGMENTS, STATUS_SYNTHESIZED, STATUS_TRANSLATED}
)


@dataclass(frozen=True)
class DescriptionFragment:
    """One description fragment for a term, tagged with its source row."""

    text: str
    block_idx: int = -1
    string_idx: int = -1


@dataclass(frozen=True)
class TranslationVariant:
    """A candidate translation with the rationale the AI gave for it."""

    translation: str
    rationale: str = ""


@dataclass(frozen=True)
class GlossaryEntry:
    """Single glossary record."""

    original: str
    translation: str
    notes: str = ""
    section: Optional[str] = None
    profiled: bool = False
    status: str = ""
    icon: str = ""
    fragments: Tuple[DescriptionFragment, ...] = ()
    translation_variants: Tuple[TranslationVariant, ...] = ()

    def is_valid(self) -> bool:
        """Whether the entry should load and appear.

        A legacy entry needs both a term and a translation. A seeded entry has a
        term and a lifecycle status but no translation yet (roadmap section 6),
        so a status alone also makes it valid.
        """
        return bool(self.original) and (bool(self.translation) or bool(self.status))

    @property
    def is_unconfirmed(self) -> bool:
        """True while the entry still awaits a confirmed human decision."""
        return self.status in UNCONFIRMED_STATUSES


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


def _fragments_from_raw(raw) -> Tuple[DescriptionFragment, ...]:
    """Parse serialized description fragments back into typed objects."""
    if not isinstance(raw, list):
        return ()
    out: List[DescriptionFragment] = []
    for item in raw:
        if isinstance(item, dict):
            def _coord(key: str) -> int:
                try:
                    return int(item.get(key, -1))
                except (TypeError, ValueError):
                    return -1
            out.append(
                DescriptionFragment(
                    text=str(item.get("text", "") or ""),
                    block_idx=_coord("block_idx"),
                    string_idx=_coord("string_idx"),
                )
            )
        elif isinstance(item, str):
            out.append(DescriptionFragment(text=item))
    return tuple(out)


def _variants_from_raw(raw) -> Tuple[TranslationVariant, ...]:
    """Parse serialized translation variants back into typed objects."""
    if not isinstance(raw, list):
        return ()
    out: List[TranslationVariant] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(
                TranslationVariant(
                    translation=str(item.get("translation", "") or ""),
                    rationale=str(item.get("rationale", "") or ""),
                )
            )
        elif isinstance(item, str):
            out.append(TranslationVariant(translation=item))
    return tuple(out)


def _entry_to_dict(entry: GlossaryEntry) -> Dict[str, Any]:
    """Serialize an entry, emitting new lifecycle fields only when set.

    Keeping default-valued fields out of the JSON preserves the existing file
    shape for legacy glossaries and avoids churning every entry on save.
    """
    out: Dict[str, Any] = {
        "original": entry.original,
        "translation": entry.translation,
        "notes": entry.notes,
        "section": entry.section,
        "profiled": entry.profiled,
    }
    if entry.status:
        out["status"] = entry.status
    if entry.icon:
        out["icon"] = entry.icon
    if entry.fragments:
        out["fragments"] = [
            {"text": f.text, "block_idx": f.block_idx, "string_idx": f.string_idx}
            for f in entry.fragments
        ]
    if entry.translation_variants:
        out["translation_variants"] = [
            {"translation": v.translation, "rationale": v.rationale}
            for v in entry.translation_variants
        ]
    return out


class GlossaryManager:
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

    def load_from_text(
        self,
        *,
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
        raw_text: str,
    ) -> None:
        """Populate glossary from text buffer (either JSON or Markdown)."""
        self._plugin_name = plugin_name
        self._glossary_path = glossary_path
        sanitized_text = (raw_text or "").replace('\uFEFF', '')
        self._raw_text = sanitized_text
        
        # Check if text is JSON
        is_json = False
        if glossary_path and glossary_path.suffix.lower() == '.json':
            is_json = True
        elif not glossary_path and sanitized_text.strip().startswith(('[', '{')):
            is_json = True
            
        if is_json:
            try:
                import json
                data = json.loads(sanitized_text) if sanitized_text.strip() else []
                self._entries = []
                self._section_order = []
                sections_seen = set()
                for item in data:
                    entry = GlossaryEntry(
                        original=item.get("original", ""),
                        translation=item.get("translation", ""),
                        notes=item.get("notes", ""),
                        section=item.get("section"),
                        profiled=bool(item.get("profiled", False)),
                        status=str(item.get("status", "") or ""),
                        icon=str(item.get("icon", "") or ""),
                        fragments=_fragments_from_raw(item.get("fragments")),
                        translation_variants=_variants_from_raw(item.get("translation_variants")),
                    )
                    if entry.is_valid():
                        self._entries.append(entry)
                        sec = entry.section
                        if sec and sec not in sections_seen:
                            sections_seen.add(sec)
                            self._section_order.append(sec)
            except Exception as e:
                log_debug(f"GlossaryManager: Failed to parse JSON glossary: {e}")
                self._entries = []
        else:
            self._entries = self._parse_markdown(self._raw_text)
            
        self._build_pattern_cache()
        log_debug(
            f"GlossaryManager: loaded {len(self._entries)} entries for plugin "
            f"{plugin_name or '<global>'} from {str(glossary_path) if glossary_path else '<memory>'}"
        )

    def refresh_from_disk(self) -> None:
        """Update the from disk."""
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
        """Get the raw text."""
        return self._raw_text

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

    def find_matches(self, text: str) -> List[GlossaryMatch]:
        """Find matches."""
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

    def build_occurrence_index(self, dataset: Sequence, is_cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, List[GlossaryOccurrence]]:
        """Create occurrence index."""
        occurrences: Dict[str, List[GlossaryOccurrence]] = {entry.original: [] for entry in self._entries}
        if not dataset:
            self._occurrence_index = occurrences
            return occurrences

        compiled_entries = list(self.iter_compiled())
        if not compiled_entries:
            self._occurrence_index = occurrences
            return occurrences

        for block_idx, block in enumerate(dataset):
            if is_cancelled and is_cancelled():
                return {}
            if not isinstance(block, list):
                continue
            for string_idx, value in enumerate(block):
                if is_cancelled and is_cancelled():
                    return {}
                text = '' if value is None else str(value)
                if not text:
                    continue
                lines = text.split('\n')
                for line_idx, line in enumerate(lines):
                    if is_cancelled and is_cancelled():
                        return {}
                    if not line:
                        continue
                        
                    # Use the AC-optimized find_matches
                    matches = self.find_matches(line)
                    if is_cancelled and is_cancelled():
                        return {}
                    for match in matches:
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

    def update_occurrences_for_entry(self, dataset: Sequence, old_term: Optional[str], new_entry: Optional[GlossaryEntry]) -> None:
        """Incrementally update the occurrence index for a single glossary entry change."""
        if not self._occurrence_index and self._entries:
            self.build_occurrence_index(dataset)
            return

        if old_term:
            self._occurrence_index.pop(old_term, None)

        if new_entry and new_entry.original:
            pattern = self._compiled_patterns.get(new_entry.original)
            if not pattern:
                pattern = self._build_regex(new_entry.original)

            term_occurrences = []
            if dataset:
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
                            for match in pattern.finditer(line):
                                occ = GlossaryOccurrence(
                                    entry=new_entry,
                                    start=match.span()[0],
                                    end=match.span()[1],
                                    block_idx=block_idx,
                                    string_idx=string_idx,
                                    line_idx=line_idx,
                                    line_text=line,
                                )
                                term_occurrences.append(occ)
            self._occurrence_index[new_entry.original] = term_occurrences

    def get_occurrences_for(self, entry: GlossaryEntry) -> List[GlossaryOccurrence]:
        """Get the occurrences for."""
        if entry is None or not entry.original:
            return []
        return list(self._occurrence_index.get(entry.original, []))

    def get_occurrence_map(self) -> Dict[str, List[GlossaryOccurrence]]:
        """Get the occurrence map."""
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


    def add_entry(self, original: str, translation: str, notes: str, section: Optional[str] = None, profiled: bool = False) -> Optional[GlossaryEntry]:
        """Add entry."""
        original_key = (original or '').strip()
        if not original_key:
            return None
        existing = next((entry for entry in self._entries if entry.original == original_key), None)
        if existing:
            return self.update_entry(
                original_key, translation, notes, section=section, profiled=profiled
            )
        new_entry = GlossaryEntry(
            original=original_key,
            translation=translation.strip(),
            notes=notes.strip(),
            section=section,
            profiled=profiled
        )
        self._session_changes[original_key] = new_entry
        new_entries = list(self._entries)
        new_entries.append(new_entry)
        self._entries = new_entries
        self._occurrence_index = {}
        self._persist()
        return new_entry

    def update_entry(
        self,
        original: str,
        translation: str,
        notes: str,
        section: Optional[str] = None,
        profiled: Optional[bool] = None,
        *,
        status: Optional[str] = None,
        icon: Optional[str] = None,
        fragments: Optional[Tuple[DescriptionFragment, ...]] = None,
        translation_variants: Optional[Tuple[TranslationVariant, ...]] = None,
    ) -> Optional[GlossaryEntry]:
        """Update the entry, preserving lifecycle fields unless overridden.

        Lifecycle fields (``status``, ``icon``, ``fragments``,
        ``translation_variants``) are carried over from the existing entry when
        not passed, so a plain edit never silently drops them.
        """
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
                    section=section if section is not None else entry.section,
                    profiled=profiled if profiled is not None else entry.profiled,
                    status=status if status is not None else entry.status,
                    icon=icon if icon is not None else entry.icon,
                    fragments=fragments if fragments is not None else entry.fragments,
                    translation_variants=(
                        translation_variants
                        if translation_variants is not None
                        else entry.translation_variants
                    ),
                )
                new_entries = list(self._entries)
                new_entries[idx] = updated_entry
                self._entries = new_entries
                self._occurrence_index = {}
                self._session_changes[original_key] = updated_entry
                self._persist()
                return updated_entry
        return None

    def seed_entry(
        self,
        original: str,
        section: Optional[str] = None,
        *,
        icon: str = "",
        status: str = STATUS_SEEDED,
        description: str = "",
    ) -> Optional[GlossaryEntry]:
        """Insert a term-only seed entry when the term is not already present.

        Seeding fills gaps; it never overwrites an existing entry, which may
        already carry a translation or a richer description (roadmap section 4).
        Returns the entry now representing the term, or None for a blank term.
        """
        original_key = (original or '').strip()
        if not original_key:
            return None

        existing = next((e for e in self._entries if e.original == original_key), None)
        if existing is not None:
            return existing

        new_entry = GlossaryEntry(
            original=original_key,
            translation="",
            notes=(description or "").strip(),
            section=section,
            status=status,
            icon=(icon or "").strip(),
        )
        self._session_changes[original_key] = new_entry
        self._entries = list(self._entries) + [new_entry]
        self._occurrence_index = {}
        self._persist()
        return new_entry

    def delete_entry(self, original: str) -> bool:
        """Remove entry."""
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

    @property
    def glossary_path(self) -> Optional[Path]:
        """The file this glossary persists to, or None when memory-only.

        None means every write is dropped on the next reload, so callers that
        are about to produce a lot of entries should check it first.
        """
        return self._glossary_path

    def clear_all(self) -> int:
        """Remove every entry, returning how many were removed.

        The glossary file is copied to ``<name>.bak`` first: this wipes work that
        has no undo, and the copy costs nothing.
        """
        removed = len(self._entries)
        if not removed:
            return 0
        self.backup_file()
        for entry in self._entries:
            self._session_changes[entry.original] = None
        self._entries = []
        self._occurrence_index = {}
        self._persist()
        return removed

    def backup_file(self) -> Optional[Path]:
        """Copy the glossary file to ``<name>.bak``. Returns the backup path."""
        path = self._glossary_path
        if not path or not path.exists():
            return None
        backup = path.with_suffix(path.suffix + '.bak')
        try:
            backup.write_bytes(path.read_bytes())
            return backup
        except Exception as exc:
            log_debug(f"GlossaryManager: failed to back up {path.name}: {exc}")
            return None

    def save_to_disk(self) -> None:
        """Save to disk."""
        self._persist(write_only=True)

    def _parse_markdown(self, text: str) -> List[GlossaryEntry]:
        """Internal helper to parse markdown."""
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
                if header_check[0] in {'оригінал', 'original'} and header_check[1] in {'переклад', 'translation'}:
                    continue
                original, translation = parts[0], parts[1]
                notes = parts[2] if len(parts) >= 3 else ""
                # Replace <br> / <br/> with \n to restore newlines inside notes
                notes = re.sub(r'<br\s*/?>', '\n', notes, flags=re.IGNORECASE)
                notes = notes.replace(r'\|', '|')
                
                original = original.replace(r'\|', '|')
                translation = translation.replace(r'\|', '|')
                
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
                notes = re.sub(r'<br\s*/?>', '\n', notes, flags=re.IGNORECASE)
                notes = notes.replace(r'\|', '|')
                
                original = original.replace(r'\|', '|')
                translation = translation.replace(r'\|', '|')
                
                entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
                if entry.is_valid():
                    entries.append(entry)

        return entries

    def _table_lines(self, entries: Sequence[GlossaryEntry]) -> List[str]:
        """Internal helper to table lines."""
        lines = ['| Original | Translation | Notes |', '|----------|-------------|-------|']
        for entry in entries:
            # Escape newlines as <br> and pipe characters as \| inside markdown table cells
            safe_notes = (entry.notes or "").replace('\n', '<br>')
            safe_notes = safe_notes.replace('|', r'\|')
            
            # Keep original and translation single-line and pipe-safe just in case
            safe_orig = (entry.original or "").replace('\n', ' ').replace('|', r'\|')
            safe_trans = (entry.translation or "").replace('\n', ' ').replace('|', r'\|')
            
            lines.append(f"| {safe_orig} | {safe_trans} | {safe_notes} |")
        return lines

    def _generate_markdown(self) -> str:
        """Internal helper to generate markdown."""
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

        # Collect active sections preserving original order and appending new ones dynamically
        all_sections_present = {entry.section for entry in self._entries if entry.section}
        active_sections = []
        for s in self._section_order:
            if s in all_sections_present:
                active_sections.append(s)
        for s in sorted(all_sections_present):
            if s not in active_sections:
                active_sections.append(s)

        for section in active_sections:
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
        """Internal helper to persist."""
        if self._glossary_path:
            # Migration logic: if current path is .md, migrate it to .json!
            if self._glossary_path.suffix.lower() == '.md':
                json_path = self._glossary_path.with_suffix('.json')
                
                # Create .bak file for safety before deleting
                bak_path = self._glossary_path.with_suffix('.md.bak')
                try:
                    if self._glossary_path.exists():
                        if bak_path.exists():
                            bak_path.unlink()
                        self._glossary_path.rename(bak_path)
                        log_debug(f"GlossaryManager: Renamed legacy glossary {self._glossary_path.name} to backup {bak_path.name}")
                except Exception as e:
                    log_debug(f"GlossaryManager: Failed to rename legacy glossary to backup: {e}")
                
                self._glossary_path = json_path

            # Serialize entries to JSON
            import json
            data_to_save = [_entry_to_dict(entry) for entry in self._entries]
            
            try:
                raw_json = json.dumps(data_to_save, ensure_ascii=False, indent=2) + "\n"
                self._glossary_path.write_text(raw_json, encoding='utf-8')
                self._raw_text = raw_json
                log_debug(f"GlossaryManager: Persisted {len(self._entries)} entries to {self._glossary_path}")
            except Exception as e:
                log_debug(f"GlossaryManager: Failed to write JSON glossary: {e}")
                
            if not write_only:
                try:
                    self.load_from_text(
                        plugin_name=self._plugin_name,
                        glossary_path=self._glossary_path,
                        raw_text=self._raw_text,
                    )
                except Exception:
                    pass
        else:
            # In-memory only (e.g. tests)
            # Make sure _raw_text is in sync (we generate Markdown for compatibility/tests that check get_raw_text)
            #
            # Markdown carries no status column and the parser drops rows with an
            # empty translation, so a seed-only entry does not survive a round
            # trip through this text. Anything running the build pipeline must
            # bind a real file first -- say so loudly instead of losing the work.
            if self._entries:
                log_debug(
                    f"GlossaryManager: {len(self._entries)} entries kept in memory only "
                    "(no glossary path bound); they will not survive a reload"
                )
            self._raw_text = self._generate_markdown()
            self._build_pattern_cache()

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
                parts = [GlossaryManager._get_word_stem_pattern(word) for word in words]
                patterns.append(rf"(?<!\w){sep.join(parts)}(?!\w)")
            else:
                # Single-word variation logic
                patterns.append(rf"(?<!\w){GlossaryManager._get_word_stem_pattern(var)}(?!\w)")
        
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

    def global_replace(self, find_word: str, replace_word: str) -> List[Tuple[GlossaryEntry, str, GlossaryEntry]]:
        """
        Replaces find_word with replace_word in all entries of the glossary
        (original, translation, notes), keeping the case.
        Returns a list of tuples: (old_entry, old_translation, new_entry)
        for entries where the translation has changed.
        """
        if not find_word:
            return []

        modified_entries: List[Tuple[GlossaryEntry, str, GlossaryEntry]] = []
        new_entries: List[GlossaryEntry] = []

        for entry in self._entries:
            has_find = (
                re.search(re.escape(find_word), entry.original, re.IGNORECASE) is not None
                or re.search(re.escape(find_word), entry.translation, re.IGNORECASE) is not None
                or re.search(re.escape(find_word), entry.notes, re.IGNORECASE) is not None
            )

            if has_find:
                new_original = replace_preserve_case(entry.original, find_word, replace_word)
                new_translation = replace_preserve_case(entry.translation, find_word, replace_word)
                new_notes = replace_preserve_case(entry.notes, find_word, replace_word)

                new_entry = GlossaryEntry(
                    original=new_original,
                    translation=new_translation,
                    notes=new_notes,
                    section=entry.section,
                    profiled=entry.profiled
                )

                new_entries.append(new_entry)

                # Record in session changes
                if entry.original != new_original:
                    self._session_changes[entry.original] = None
                    self._session_changes[new_original] = new_entry
                else:
                    self._session_changes[entry.original] = new_entry

                # Track all modified entries (original, translation, or notes)
                modified_entries.append((entry, entry.translation, new_entry))
            else:
                new_entries.append(entry)

        if modified_entries or len(new_entries) != len(self._entries) or any(e1 != e2 for e1, e2 in zip(self._entries, new_entries)):
            self._entries = new_entries
            self._occurrence_index = {}
            self._persist()

        return modified_entries


def preserve_case(match_text: str, replacement: str) -> str:
    """
    Detects the casing of match_text and returns replacement with the same casing.
    Supports ALL CAPS, Title Case (Capitalized), and lowercase.
    """
    if not match_text or not replacement:
        return replacement
    if match_text.isupper():
        return replacement.upper()
    if match_text.islower():
        return replacement.lower()
    if match_text[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def replace_preserve_case(text: str, find_word: str, replace_word: str) -> str:
    """
    Case-insensitive substring replacement that preserves the case of the matched portion.
    """
    if not text or not find_word:
        return text
    
    pattern = re.compile(re.escape(find_word), re.IGNORECASE)
    
    def repl(match):
        """Repl."""
        return preserve_case(match.group(0), replace_word)
        
    return pattern.sub(repl, text)
