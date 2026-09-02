"""Highlight mixin for JsonTagHighlighter."""
from __future__ import annotations

import re
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QFont

from utils.utils import SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN, get_tag_width
from core.glossary_manager import GlossaryMatch, GlossaryEntry

_COLOR_TAG_PATTERN = re.compile(
    r"(\[(Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White|Gray|Grey)\])|"
    r"(\[/C\])|"
    r"(\{\s*Color\s*:\s*(Red|Green|Blue|White|Yellow|Purple|Orange|Grey|Gray)\s*\})",
    re.IGNORECASE
)

_PLACEHOLDER_PATTERN = re.compile(r"^\[\d+-\d+\] \d+ empty line\(s\)$")

_WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")

_DOUBLE_SPACE_PATTERN = re.compile(r"[ ·]{2,}")
_LEADING_SPACE_PATTERN = re.compile(r"^(?:\{(?!f:|F:)[^}]*\}|\[[^\]]*\])*([ ·]+)")
_TAG_SPLIT_SPACE_PATTERN = re.compile(r"[ ·](?:\{(?!f:|F:)[^}]*\}|\[[^\]]*\])+[ ·]")


class HighlightMixin:
    def _should_highlight_icons(self) -> bool:
        """Internal helper to check if should highlight icons."""
        doc = self.document()
        if not doc:
            return False
        editor_widget = doc.parent()
        if hasattr(editor_widget, 'objectName') and editor_widget.objectName() == 'preview_text_edit':
            return False
        return True

    def _should_check_spelling(self) -> bool:
        """Check if spellchecking should be performed for this widget."""
        if not self._spellchecker_enabled:
            return False

        # Use stored editor widget reference
        if self._editor_widget_ref:
            editor_name = self._editor_widget_ref.objectName() if hasattr(self._editor_widget_ref, 'objectName') else 'unknown'
            return editor_name in ('edited_text_edit', 'variations_preview_text_edit', 'comparison_editor_text_edit')

        return False

    def _extract_words_from_text(self, text: str) -> List[Tuple[int, int, str]]:
        """Extract words from text, returning (start, end, word) tuples."""
        # Replace middle dots with spaces for word detection
        text_with_spaces = text.replace('·', ' ')

        words = []
        for match in _WORD_PATTERN.finditer(text_with_spaces):
            words.append((match.start(), match.end(), match.group(0)))
        return words

    def _is_forced_alias(self, tag: str) -> bool:
        """Internal helper to check if is forced alias."""
        if tag.lower().startswith("{f:"):
            return True
        mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
        if mappings:
            for alias, original in mappings.items():
                if original == tag and alias.lower().startswith("{f:"):
                    return True
        return False

    def _tag_has_length(self, tag: str) -> bool:
        """Internal helper to tag has length."""
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        width = get_tag_width(tag, default_tag_mappings, font_map, icon_sequences=icon_sequences)
        return width > 0

    def _is_visible_tag(self, tag: str) -> bool:
        """Internal helper to check if is visible tag."""
        from utils.utils import is_visible_tag
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = self._get_icon_sequences()
        return is_visible_tag(tag, default_tag_mappings, font_map, icon_sequences)

    def highlightBlock(self, text):
        # In preview_text_edit each line is an independent game string,
        # so color must NOT bleed from one string to the next.
        """Highlightblock."""
        _is_preview_widget = (
            self._editor_widget_ref is not None
            and hasattr(self._editor_widget_ref, 'objectName')
            and self._editor_widget_ref.objectName() == 'preview_text_edit'
        )
        if _is_preview_widget and _PLACEHOLDER_PATTERN.match(text):
            self.setFormat(0, len(text), self.placeholder_format)
            self.setCurrentBlockState(self.STATE_DEFAULT)
            return

        # While the user is typing, skip glossary, spellcheck, tag/icon rules
        # and spacing analysis. Qt already shows the glyphs; those passes run
        # after PREVIEW_UPDATE_DELAY once typing_mode is cleared.
        if getattr(self, '_typing_mode', False) and not _is_preview_widget:
            self.setFormat(0, len(text), self.color_default_format)
            self.setCurrentBlockState(self.STATE_DEFAULT)
            return

        if _is_preview_widget:
            previous_color_state = self.STATE_DEFAULT
        else:
            previous_color_state = self.previousBlockState()
            if previous_color_state == -1: previous_color_state = self.STATE_DEFAULT

        format_map = {
            self.STATE_DEFAULT: self.color_default_format,
            self.STATE_RED: self.red_text_format,
            self.STATE_GREEN: self.green_text_format,
            self.STATE_BLUE: self.blue_text_format,
            self.STATE_YELLOW: self.yellow_text_format,
            self.STATE_LBLUE: self.lblue_text_format,
            self.STATE_PURPLE: self.purple_text_format,
            self.STATE_SILVER: self.silver_text_format,
            self.STATE_ORANGE: self.orange_text_format,
        }
        self.setFormat(0, len(text), format_map.get(previous_color_state, self.color_default_format))
        
        last_pos = 0
        current_block_color_state = previous_color_state
        for match in _COLOR_TAG_PATTERN.finditer(text):
            start, end = match.span()
            
            format_to_apply = format_map.get(current_block_color_state, self.color_default_format)
            if start > last_pos:
                self.setFormat(last_pos, start - last_pos, format_to_apply)
            
            ww_color_name = match.group(2)
            ww_closing_tag = match.group(3)
            mc_color_name = match.group(5)

            if ww_color_name:
                color = ww_color_name.lower()
                if color == 'red': current_block_color_state = self.STATE_RED
                elif color == 'green': current_block_color_state = self.STATE_GREEN
                elif color == 'blue': current_block_color_state = self.STATE_BLUE
                elif color == 'yellow': current_block_color_state = self.STATE_YELLOW
                elif color == 'l_blue': current_block_color_state = self.STATE_LBLUE
                elif color == 'purple': current_block_color_state = self.STATE_PURPLE
                elif color in ('silver', 'grey', 'gray'): current_block_color_state = self.STATE_SILVER
                elif color == 'orange': current_block_color_state = self.STATE_ORANGE
                else: current_block_color_state = self.STATE_DEFAULT # White
            elif ww_closing_tag:
                current_block_color_state = self.STATE_DEFAULT
            elif mc_color_name:
                color = mc_color_name.lower()
                if color == 'red': current_block_color_state = self.STATE_RED
                elif color == 'green': current_block_color_state = self.STATE_GREEN
                elif color == 'blue': current_block_color_state = self.STATE_BLUE
                elif color == 'yellow': current_block_color_state = self.STATE_YELLOW
                elif color == 'purple': current_block_color_state = self.STATE_PURPLE
                elif color == 'orange': current_block_color_state = self.STATE_ORANGE
                elif color in ('grey', 'gray'): current_block_color_state = self.STATE_SILVER
                else: current_block_color_state = self.STATE_DEFAULT # White
            
            last_pos = end
        
        if last_pos < len(text):
            final_format = format_map.get(current_block_color_state, self.color_default_format)
            self.setFormat(last_pos, len(text) - last_pos, final_format)

        # Glossary and spellcheck highlighting (run BEFORE tag rules so that tags can clean up formats on top)
        all_matches_for_tooltip = []
        
        block = self.currentBlock()
        if not block or not block.isValid():
            block_pos = 0
            block_number = -1
        else:
            block_pos = block.position()
            block_number = block.blockNumber()
            
        block_len = len(text)
        block_end = block_pos + block_len

        # 1. Glossary highlighting (Aho-Corasick)
        glossary_matches_to_apply = []
        if self._glossary_enabled and block_number != -1:
            if self._async_glossary_matches is not None:
                for m in self._async_glossary_matches:
                    m_start = m['start']
                    m_end = m['end']
                    overlap_start = max(m_start, block_pos)
                    overlap_end = min(m_end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_pos
                        local_length = overlap_end - overlap_start
                        entry = GlossaryEntry(original=m['original'], translation=m['translation'], notes=m['notes'])
                        glossary_matches_to_apply.append(GlossaryMatch(entry=entry, start=local_start, end=local_start + local_length))
            elif not self._typing_mode:
                # Synchronous fallback for startup and unit tests
                self._rebuild_glossary_cache()
                if block_number in self._glossary_matches_cache:
                    for local_start, local_length, match in self._glossary_matches_cache[block_number]:
                        glossary_matches_to_apply.append(GlossaryMatch(entry=match.entry, start=local_start, end=local_start + local_length))

        if glossary_matches_to_apply:
            underline_style = self._glossary_format.underlineStyle()
            underline_color = self._glossary_format.underlineColor()
            has_custom_color = underline_color.isValid()
            for m in glossary_matches_to_apply:
                existing_format = self.format(m.start)
                existing_format.setFontUnderline(True)
                existing_format.setUnderlineStyle(underline_style)
                if has_custom_color:
                    existing_format.setUnderlineColor(underline_color)
                self.setFormat(m.start, m.end - m.start, existing_format)
                all_matches_for_tooltip.append(m)

        # 2. Translation Glossary Bridge highlighting
        translation_matches_to_apply = []
        if self._is_translation_mode and block_number != -1:
            # log_debug(f"highlightBlock: translation mode active, block_num={block_number}, text={repr(text)}, async_matches={self._async_translation_matches is not None}, typing={self._typing_mode}")
            if self._async_translation_matches is not None:
                for m in self._async_translation_matches:
                    m_start = m['start']
                    m_end = m['end']
                    overlap_start = max(m_start, block_pos)
                    overlap_end = min(m_end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_pos
                        local_length = overlap_end - overlap_start
                        entry = GlossaryEntry(original=m['original'], translation=m['translation'], notes=m['notes'])
                        translation_matches_to_apply.append(GlossaryMatch(entry=entry, start=local_start, end=local_start + local_length))
            elif not self._typing_mode:
                # Synchronous fallback for startup and unit tests
                self._rebuild_translation_glossary_cache()
                if block_number in self._translation_matches_cache:
                    for local_start, local_length, match in self._translation_matches_cache[block_number]:
                        translation_matches_to_apply.append(GlossaryMatch(entry=match.entry, start=local_start, end=local_start + local_length))

        if translation_matches_to_apply:
            underline_style = self._glossary_format.underlineStyle()
            underline_color = self._glossary_format.underlineColor()
            has_custom_color = underline_color.isValid()
            for m in translation_matches_to_apply:
                existing_format = self.format(m.start)
                existing_format.setFontUnderline(True)
                existing_format.setUnderlineStyle(underline_style)
                if has_custom_color:
                    existing_format.setUnderlineColor(underline_color)
                self.setFormat(m.start, m.end - m.start, existing_format)
                all_matches_for_tooltip.append(m)

        if all_matches_for_tooltip:
            self.setCurrentBlockUserData(self.GlossaryBlockData(all_matches_for_tooltip))
        else:
            self.setCurrentBlockUserData(None)

        # 3. Spellchecker highlighting
        spellcheck_matches_to_apply = []
        if not self._typing_mode and self._should_check_spelling() and block_number != -1:
            if self._async_spellcheck_matches is not None:
                spellcheck_matches_to_apply = self._async_spellcheck_matches
            else:
                editor_name = self._editor_widget_ref.objectName() if (self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName')) else ''
                if editor_name in ('variations_preview_text_edit', 'comparison_editor_text_edit'):
                    sm = self.mw.spellchecker_manager if (self.mw and hasattr(self.mw, 'spellchecker_manager')) else None
                    if sm and sm.enabled and sm.hunspell:
                        text_with_spaces = text.replace("·", " ")
                        for match in _WORD_PATTERN.finditer(text_with_spaces):
                            word = match.group(0)
                            cleaned_word = word.strip("'·")
                            if len(cleaned_word) < 3 or cleaned_word.isdigit():
                                continue
                            lower_word = cleaned_word.lower()
                            if lower_word in sm.custom_words:
                                continue
                            
                            if lower_word in sm._spell_cache:
                                is_misspelled = sm._spell_cache[lower_word]
                            else:
                                is_correct = sm.hunspell.lookup(cleaned_word)
                                is_misspelled = not is_correct
                                sm._spell_cache[lower_word] = is_misspelled
                                
                            if is_misspelled:
                                spellcheck_matches_to_apply.append((block_pos + match.start(), match.end() - match.start()))

        if spellcheck_matches_to_apply:
            underline_style = self._spellchecker_format.underlineStyle()
            underline_color = self._spellchecker_format.underlineColor()
            has_custom_color = underline_color.isValid()
            
            for m_start, m_length in spellcheck_matches_to_apply:
                m_end = m_start + m_length
                
                overlap_start = max(m_start, block_pos)
                overlap_end = min(m_end, block_end)
                if overlap_end > overlap_start:
                    local_start = overlap_start - block_pos
                    local_length = overlap_end - overlap_start
                    
                    existing_format = self.format(local_start)
                    existing_format.setFontUnderline(True)
                    existing_format.setUnderlineStyle(underline_style)
                    if has_custom_color:
                        existing_format.setUnderlineColor(underline_color)
                    self.setFormat(local_start, local_length, existing_format)

        # Apply custom rules from the game plugin
        rules_to_apply = self._compiled_custom_rules_all
        
        # Performance optimization for the preview window by not highlighting bracket tags (controller buttons)
        doc = self.document()
        if doc:
            editor_widget = doc.parent()
            if hasattr(editor_widget, 'objectName') and editor_widget.objectName() == 'preview_text_edit':
                rules_to_apply = self._compiled_custom_rules_preview
        
        for compiled_pattern, fmt in rules_to_apply:
            try:
                for match in compiled_pattern.finditer(text):
                    self.setFormat(match.start(), match.end() - match.start(), fmt)
            except Exception as e:
                pass # Already precompiled, shouldn't fail runtime
                
        hide_tags_enabled = False
        if self.mw and hasattr(self.mw, 'data_store'):
            editor_name = ""
            if self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName'):
                editor_name = self._editor_widget_ref.objectName()
            
            if editor_name == 'original_text_edit':
                hide_tags_enabled = getattr(self.mw.data_store, 'hide_original_tags', getattr(self.mw.data_store, 'hide_tags', False))
            else:
                hide_tags_enabled = getattr(self.mw.data_store, 'hide_translation_tags', getattr(self.mw.data_store, 'hide_tags', False))
        
        for compiled_pattern, fmt in self._compiled_all_rules_builtin:
            for match in compiled_pattern.finditer(text):
                is_tag_pattern = fmt in (self.curly_tag_format, self.bracket_tag_format)
                if is_tag_pattern and hide_tags_enabled:
                    tag = match.group(1)
                    if not (self._is_visible_tag(tag) or self._tag_has_length(tag) or tag.lower() in ('{*}', '{tab}', '{escape:6:000a}', '{escape:6:000b}')):
                        self.setFormat(match.start(), match.end() - match.start(), self.hide_tag_format)
                        continue
                self.setFormat(match.start(), match.end() - match.start(), fmt)

        icon_sequences = self._get_icon_sequences()
        if icon_sequences and self._should_highlight_icons():
            matches = self._get_icon_matches_for_block(icon_sequences)
            for start, length in matches:
                existing_format = self.format(start)
                combined_format = QTextCharFormat(existing_format)
                icon_bg = self.icon_sequence_format.background()
                if icon_bg.style() != Qt.BrushStyle.NoBrush:
                    combined_format.setBackground(icon_bg)
                if self.icon_sequence_format.fontWeight() != QFont.Weight.Normal.value:
                    combined_format.setFontWeight(self.icon_sequence_format.fontWeight())
                self.setFormat(start, length, combined_format)

        # Highlight bad spacing: double spaces, leading spaces, and spaces split by tags
        # (Only in the editor text edits, not in preview_text_edit)
        if _is_preview_widget is False and not self._typing_mode:
            def apply_bad_spacing_format(start_idx, length):
                for idx in range(start_idx, start_idx + length):
                    char = text[idx]
                    if char == SPACE_DOT_SYMBOL:
                        fmt = QTextCharFormat(self.bad_spacing_format)
                        fmt.setForeground(self.space_dot_format.foreground())
                        self.setFormat(idx, 1, fmt)
                    else:
                        self.setFormat(idx, 1, self.bad_spacing_format)

            # 1. Double spaces
            for match in _DOUBLE_SPACE_PATTERN.finditer(text):
                start, end = match.span()
                apply_bad_spacing_format(start, end - start)
            # 2. Leading spaces
            for match in _LEADING_SPACE_PATTERN.finditer(text):
                start, end = match.span(1)
                prefix = text[:start]
                tags = ALL_TAGS_PATTERN.findall(prefix)
                has_forced = False
                for tag in tags:
                    if self._is_visible_tag(tag):
                        has_forced = True
                        break
                if not has_forced:
                    apply_bad_spacing_format(start, end - start)
            # 3. Tag split spaces
            for match in _TAG_SPLIT_SPACE_PATTERN.finditer(text):
                start, end = match.span()
                match_text = text[start:end]
                tags = ALL_TAGS_PATTERN.findall(match_text)
                has_forced = False
                for tag in tags:
                    if self._is_visible_tag(tag):
                        has_forced = True
                        break
                if not has_forced:
                    apply_bad_spacing_format(start, 1)
                    apply_bad_spacing_format(end - 1, 1)

            # 4. Missing space before/after visible tags
            missing_spacing_id = None
            if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
                missing_spacing_id = getattr(self.mw.current_game_rules, 'PROBLEM_MISSING_ICON_SPACING', None)
            
            if missing_spacing_id:
                enabled = True
                if self.mw and hasattr(self.mw, 'detection_enabled'):
                    enabled = self.mw.detection_enabled.get(missing_spacing_id, True)
                
                if enabled:
                    from utils.utils import find_missing_icon_spacing_spans
                    font_map = getattr(self.mw, "font_map", None) if self.mw else None
                    mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
                    icons = self._get_icon_sequences()
                    spans = find_missing_icon_spacing_spans(text, self._is_visible_tag, font_map, mappings, icons)
                    for start, end in spans:
                        self.setFormat(start, end - start, self.missing_icon_spacing_format)

        # In preview_text_edit, never carry colour state to the next line.
        self.setCurrentBlockState(self.STATE_DEFAULT if _is_preview_widget else current_block_color_state)
