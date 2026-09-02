"""Cache mixin for JsonTagHighlighter."""
from __future__ import annotations

from typing import Dict, List, Tuple

from utils.logging_utils import log_debug
from utils.utils import convert_dots_to_spaces_from_editor
from core.glossary_manager import GlossaryMatch


class CacheMixin:
    def _invalidate_icon_cache(self) -> None:
        """Internal helper to invalidate icon cache."""
        self._icon_sequences_cache.clear()
        self._icon_cache_revision = None
        self._icon_sequences_snapshot = ()

    def _rebuild_glossary_cache(self) -> None:
        """Internal helper to rebuild glossary cache."""
        doc = self.document()
        if not doc:
            self._glossary_matches_cache.clear()
            self._glossary_cache_revision = None
            return
        revision = doc.revision()
        if self._glossary_cache_revision == revision:
            return

        self._glossary_cache_revision = revision
        self._glossary_matches_cache.clear()

        if not (self._glossary_enabled and self._glossary_manager):
            return

        full_text = doc.toPlainText()
        try:
            matches = self._glossary_manager.find_matches(full_text)
        except Exception as exc:
            log_debug(f"Glossary highlight error: {exc}")
            matches = []

        for match in matches:
            start = match.start
            end = match.end
            if end <= start:
                continue
            block = doc.findBlock(start)
            if not block.isValid():
                continue
            while block.isValid() and start < end:
                block_start = block.position()
                block_length = block.length()
                block_end = block_start + block_length
                overlap_start = max(start, block_start)
                overlap_end = min(end, block_end)
                if overlap_end > overlap_start:
                    local_start = overlap_start - block_start
                    local_length = overlap_end - overlap_start
                    self._glossary_matches_cache.setdefault(block.blockNumber(), []).append(
                        (local_start, local_length, match)
                    )
                if block_end >= end:
                    break
                block = block.next()
                if not block.isValid():
                    break

    def _rebuild_translation_glossary_cache(self) -> None:
        """Rebuilds the bridge translation glossary cache for the whole document."""
        doc = self.document()
        if not doc or not self._is_translation_mode or not self._source_editor_ref or not self._glossary_manager:
            self._translation_matches_cache.clear()
            self._translation_cache_revision = None
            return

        revision = doc.revision()
        if self._translation_cache_revision == revision:
            return

        self._translation_cache_revision = revision
        self._translation_matches_cache.clear()

        source_text_raw = self._source_editor_ref.toPlainText()
        source_text = convert_dots_to_spaces_from_editor(source_text_raw)
        # Find entries that occur in the source document
        source_matches = self._glossary_manager.get_relevant_terms(source_text)
        log_debug(f"Glossary bridge: source text='{source_text}', found relevant source terms={[m.original for m in source_matches]}")
        if not source_matches:
            return

        full_text = doc.toPlainText()
        for entry in source_matches:
            # Build and search for translation regex
            # Note: build_translation_regex handles multi-line/fuzzy Slavic terms
            regex = self._glossary_manager.build_translation_regex(entry.translation)
            if not regex:
                continue
            
            matches = list(regex.finditer(full_text))
            log_debug(f"Glossary bridge: checking translation term='{entry.translation}' via regex='{regex.pattern}' on target text='{full_text}', found matches={len(matches)}")
            
            for match in regex.finditer(full_text):
                start, end = match.start(), match.end()
                if end <= start:
                    continue
                
                block = doc.findBlock(start)
                if not block.isValid():
                    continue
                
                while block.isValid() and start < end:
                    block_start = block.position()
                    block_length = block.length()
                    block_end = block_start + block_length
                    overlap_start = max(start, block_start)
                    overlap_end = min(end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_start
                        local_length = overlap_end - overlap_start
                        self._translation_matches_cache.setdefault(block.blockNumber(), []).append(
                            (local_start, local_length, GlossaryMatch(entry=entry, start=start, end=end))
                        )
                    if block_end >= end:
                        break
                    block = block.next()
                    if not block.isValid():
                        break

    def _ensure_icon_cache(self, sequences: List[str]) -> None:
        # Keep as no-op for backwards compatibility. Matches are now processed
        # locally for the current block in _get_icon_matches_for_block.
        """Internal helper to ensure icon cache."""
        pass

    def _get_icon_matches_for_text(self, text: str, sequences: List[str]) -> List[Tuple[int, int]]:
        """Internal helper to get the icon matches for text."""
        if not sequences or not text:
            return []
            
        first_char_map: Dict[str, List[str]] = {}
        for token in sequences:
            if not token:
                continue
            first_char_map.setdefault(token[0], []).append(token)
        for token_list in first_char_map.values():
            token_list.sort(key=len, reverse=True)

        matches: List[Tuple[int, int]] = []
        index = 0
        text_length = len(text)
        while index < text_length:
            char = text[index]
            candidates = first_char_map.get(char)
            matched = False
            if candidates:
                for token in candidates:
                    token_len = len(token)
                    if token_len <= 0 or index + token_len > text_length:
                        continue
                    if text.startswith(token, index):
                        matches.append((index, token_len))
                        index += token_len
                        matched = True
                        break
            if not matched:
                index += 1
        return matches

    def _get_icon_matches_for_block(self, sequences: List[str]) -> List[Tuple[int, int]]:
        """Internal helper to get the icon matches for block."""
        if not sequences:
            return []
        block = self.currentBlock()
        if not block or not block.isValid():
            return []
            
        block_text = ""
        # Handle cases where block text is not a callable or doesn't return a string
        if hasattr(block, 'text') and callable(block.text):
            try:
                val = block.text()
                if isinstance(val, str):
                    block_text = val
            except Exception:
                pass
                
        if not block_text:
            doc = self.document()
            if doc:
                try:
                    block_num = block.blockNumber()
                    try:
                        block_num_int = int(block_num)
                    except (TypeError, ValueError):
                        block_num_int = 0
                    block_text = doc.findBlockByNumber(block_num_int).text()
                except Exception:
                    block_text = ""
                    
        return self._get_icon_matches_for_text(block_text, sequences)


    def _get_icon_sequences(self) -> List[str]:
        """Internal helper to get the icon sequences."""
        main_window = self.mw
        sequences = getattr(main_window, 'icon_sequences', None) if main_window else None
        if isinstance(sequences, list):
            return sequences
        return []
