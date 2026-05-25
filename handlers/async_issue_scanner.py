# --- START OF FILE handlers/async_issue_scanner.py ---
from PyQt5.QtCore import QThread, pyqtSignal
from typing import Any, List
import re
from utils.logging_utils import log_error

class AsyncIssueScanner(QThread):
    """
    Background worker that runs line-width calculations, syntax warning analysis,
    glossary matching, and spellcheck analysis in a separate thread.
    This prevents any lags in the UI text editor.
    """
    # Signals block_idx, string_idx, text, problems_in_string, glossary_matches, translation_matches, spellcheck_matches
    finished_scan = pyqtSignal(int, int, str, list, list, list, list)

    def __init__(self, block_idx: int, string_idx: int, text: str, font_map: dict, width_threshold: int, analyzer: Any,
                 glossary_manager: Any = None, spellchecker_manager: Any = None, source_text: str = "", active_word: str = ""):
        super().__init__()
        self.block_idx = block_idx
        self.string_idx = string_idx
        self.text = text
        self.font_map = font_map
        self.width_threshold = width_threshold
        self.analyzer = analyzer
        self.glossary_manager = glossary_manager
        self.spellchecker_manager = spellchecker_manager
        self.source_text = source_text
        self.active_word = active_word

    def run(self):
        try:
            sublines = self.text.split('\n')
            problems_in_string = []
            
            # 1. Run the appropriate plugin analysis method
            if hasattr(self.analyzer, 'analyze_data_string'):
                problems_in_string = self.analyzer.analyze_data_string(self.text, self.font_map, self.width_threshold)
            elif hasattr(self.analyzer, 'analyze_subline'):
                for i, subline in enumerate(sublines):
                    next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                    problems = self.analyzer.analyze_subline(
                        text=subline,
                        next_text=next_subline,
                        subline_number_in_data_string=i,
                        qtextblock_number_in_editor=i,
                        is_last_subline_in_data_string=(i == len(sublines) - 1),
                        editor_font_map=self.font_map,
                        editor_line_width_threshold=self.width_threshold,
                        full_data_string_text_for_logical_check=self.text
                    )
                    problems_in_string.append(problems)
            
            # 2. Async Glossary analysis
            glossary_matches = []
            if self.glossary_manager and self.glossary_manager.get_entries():
                try:
                    matches = self.glossary_manager.find_matches(self.text)
                    for m in matches:
                        glossary_matches.append({
                            'start': m.start,
                            'end': m.end,
                            'original': m.entry.original,
                            'translation': m.entry.translation,
                            'notes': m.entry.notes
                        })
                except Exception:
                    pass

            # 3. Async Translation Glossary Bridge analysis
            translation_matches = []
            if self.glossary_manager and self.source_text:
                try:
                    source_matches = self.glossary_manager.get_relevant_terms(self.source_text)
                    for entry in source_matches:
                        regex = self.glossary_manager.build_translation_regex(entry.translation)
                        if regex:
                            for match in regex.finditer(self.text):
                                translation_matches.append({
                                    'start': match.start(),
                                    'end': match.end(),
                                    'original': entry.original,
                                    'translation': entry.translation,
                                    'notes': entry.notes
                                })
                except Exception:
                    pass

            # 4. Async Spellcheck analysis
            spellcheck_matches = []
            if self.spellchecker_manager and self.spellchecker_manager.enabled and self.spellchecker_manager.hunspell:
                try:
                    text_with_spaces = self.text.replace('·', ' ')
                    WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
                    for match in WORD_PATTERN.finditer(text_with_spaces):
                        word = match.group(0)
                        cleaned_word = word.strip("'·")
                        
                        if self.active_word and cleaned_word.lower() == self.active_word.lower():
                            continue
                        if len(cleaned_word) < 3:  # MIN_WORD_LENGTH
                            continue
                        if cleaned_word.isdigit():
                            continue
                        
                        lower_word = cleaned_word.lower()
                        if lower_word in self.spellchecker_manager.custom_words:
                            continue
                            
                        if lower_word in self.spellchecker_manager._spell_cache:
                            is_misspelled = self.spellchecker_manager._spell_cache[lower_word]
                        else:
                            is_correct = self.spellchecker_manager.hunspell.lookup(cleaned_word)
                            is_misspelled = not is_correct
                            self.spellchecker_manager._spell_cache[lower_word] = is_misspelled
                        
                        if is_misspelled:
                            spellcheck_matches.append((match.start(), match.end() - match.start()))
                            if lower_word not in self.spellchecker_manager._suggestions_cache:
                                try:
                                    suggestions = []
                                    res = self.spellchecker_manager.hunspell.suggest(cleaned_word)
                                    if hasattr(res, '__next__') or (hasattr(res, '__iter__') and not isinstance(res, list)):
                                        gen = iter(res)
                                        for _ in range(7):
                                            try:
                                                suggestions.append(next(gen))
                                            except StopIteration:
                                                break
                                    else:
                                        suggestions = list(res)[:7]
                                    self.spellchecker_manager._suggestions_cache[lower_word] = suggestions
                                except Exception:
                                    pass
                except Exception:
                    pass

            if not isinstance(problems_in_string, list):
                problems_in_string = []
            if not isinstance(glossary_matches, list):
                glossary_matches = []
            if not isinstance(translation_matches, list):
                translation_matches = []
            if not isinstance(spellcheck_matches, list):
                spellcheck_matches = []

            self.finished_scan.emit(
                self.block_idx, self.string_idx, self.text, 
                problems_in_string, glossary_matches, translation_matches, spellcheck_matches
            )
        except Exception as e:
            log_error(f"AsyncIssueScanner error: {e}", exc_info=True)
            self.finished_scan.emit(self.block_idx, self.string_idx, self.text, [], [], [], [])
