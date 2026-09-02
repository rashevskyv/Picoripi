"""Occurrence indexing and match helpers for GlossaryManager."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import re

from core.glossary.models import (
    OCC_MENTION,
    OCC_SPOKEN,
    GlossaryEntry,
    GlossaryMatch,
    GlossaryOccurrence,
)
from core.speaker_alias_merge import split_shared_speaker_names


class OccurrenceMixin:
    """Occurrence indexing and match helpers."""

    _GENERIC_BLOCK_NAME = re.compile(r"^(block\s*\d+|message id\s*:)", re.I)

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
                            kind=OCC_MENTION,
                        )
                        occurrences.setdefault(match.entry.original, []).append(occ)

        self._append_owned_occurrences(dataset, occurrences, is_cancelled)
        self._occurrence_index = occurrences
        return occurrences

    def _append_owned_occurrences(self, dataset, occurrences, is_cancelled=None) -> None:
        """Attach rows a term owns by block name or speaker id, not by spelling.

        Searching the line for "VILLAGE GORON #2" finds nothing: the character
        never says their internal label. The three messages in that block are
        still theirs, and the describe pass needs those rows as evidence.
        """
        if not dataset or (
            not self._block_names
            and self._speaker_for is None
            and not self._speaker_pool
        ):
            return
        by_norm: Dict[str, List[GlossaryEntry]] = {}
        for entry in self._entries:
            key = self.normalize_term(entry.original)
            if key:
                by_norm.setdefault(key, []).append(entry)
        if not by_norm:
            return
        for block_idx, block in enumerate(dataset):
            if is_cancelled and is_cancelled():
                return
            if not isinstance(block, list):
                continue
            block_label = self._block_names.get(block_idx, "")
            block_key = ""
            if block_label and not self._GENERIC_BLOCK_NAME.match(block_label.strip()):
                block_key = self.normalize_term(block_label)
            for string_idx, value in enumerate(block):
                if is_cancelled and is_cancelled():
                    return
                text = "" if value is None else str(value)
                if not text.strip():
                    continue
                owners: List[GlossaryEntry] = []
                if block_key:
                    owners.extend(by_norm.get(block_key, ()))
                if self._speaker_pool is not None:
                    speaker = self._speaker_pool.get((block_idx, string_idx))
                    if speaker:
                        speaker_key = self.normalize_term(speaker)
                        if speaker_key:
                            owners.extend(by_norm.get(speaker_key, ()))
                        for part in split_shared_speaker_names(speaker):
                            part_key = self.normalize_term(part)
                            if part_key and part_key != speaker_key:
                                owners.extend(by_norm.get(part_key, ()))
                elif self._speaker_for is not None:
                    try:
                        speaker = self._speaker_for(block_idx, string_idx)
                    except Exception:
                        speaker = None
                    speaker_key = self.normalize_term(speaker or "")
                    if speaker_key:
                        owners.extend(by_norm.get(speaker_key, ()))
                    alias = self._speaker_aliases.get(speaker or "")
                    if alias:
                        for part in split_shared_speaker_names(alias):
                            owners.extend(by_norm.get(self.normalize_term(part), ()))
                if not owners:
                    continue
                line = text.split("\n", 1)[0]
                seen_terms = set()
                for entry in owners:
                    term = entry.original
                    if term in seen_terms:
                        continue
                    seen_terms.add(term)
                    bucket = occurrences.setdefault(term, [])
                    if any(
                        o.block_idx == block_idx
                        and o.string_idx == string_idx
                        and o.kind == OCC_SPOKEN
                        for o in bucket
                    ):
                        continue
                    bucket.append(
                        GlossaryOccurrence(
                            entry=entry,
                            start=0,
                            end=len(line),
                            block_idx=block_idx,
                            string_idx=string_idx,
                            line_idx=0,
                            line_text=line,
                            kind=OCC_SPOKEN,
                        )
                    )

    def _append_owned_occurrences_for_entry(
        self, dataset: Sequence, entry: GlossaryEntry, bucket: List[GlossaryOccurrence]
    ) -> None:
        if not dataset or not entry or not entry.original:
            return
        entry_key = self.normalize_term(entry.original)
        if not entry_key:
            return
        for block_idx, block in enumerate(dataset):
            if not isinstance(block, list):
                continue
            block_label = self._block_names.get(block_idx, "")
            block_key = ""
            if block_label and not self._GENERIC_BLOCK_NAME.match(block_label.strip()):
                block_key = self.normalize_term(block_label)
            for string_idx, value in enumerate(block):
                text = "" if value is None else str(value)
                if not text.strip():
                    continue
                matched = False
                if block_key and block_key == entry_key:
                    matched = True
                if not matched and self._speaker_pool is not None:
                    speaker = self._speaker_pool.get((block_idx, string_idx))
                    if speaker:
                        spk_key = self.normalize_term(speaker)
                        if spk_key == entry_key:
                            matched = True
                        if not matched:
                            for part in split_shared_speaker_names(speaker):
                                if self.normalize_term(part) == entry_key:
                                    matched = True
                                    break
                elif not matched and self._speaker_for is not None:
                    try:
                        speaker = self._speaker_for(block_idx, string_idx)
                    except Exception:
                        speaker = None
                    spk_key = self.normalize_term(speaker or "")
                    if spk_key == entry_key:
                        matched = True
                    if not matched:
                        alias = self._speaker_aliases.get(speaker or "")
                        if alias:
                            for part in split_shared_speaker_names(alias):
                                if self.normalize_term(part) == entry_key:
                                    matched = True
                                    break
                if matched:
                    if any(
                        o.block_idx == block_idx
                        and o.string_idx == string_idx
                        and o.kind == OCC_SPOKEN
                        for o in bucket
                    ):
                        continue
                    line = text.split("\n", 1)[0]
                    bucket.append(
                        GlossaryOccurrence(
                            entry=entry,
                            start=0,
                            end=len(line),
                            block_idx=block_idx,
                            string_idx=string_idx,
                            line_idx=0,
                            line_text=line,
                            kind=OCC_SPOKEN,
                        )
                    )

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
                if self._block_names or self._speaker_pool or self._speaker_for is not None:
                    self._append_owned_occurrences_for_entry(dataset, new_entry, term_occurrences)
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
