# --- START OF FILE core/spellchecker_manager.py ---
# /home/runner/work/RAG_project/RAG_project/core/spellchecker_manager.py
import re
import time
from pathlib import Path
from typing import List, Optional, Dict
from utils.logging_utils import log_debug, log_warning, log_error
from spylls.hunspell import Dictionary
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

CUSTOM_DICT_FILENAME = "custom_dictionary.txt"
LOCAL_DICT_PATH = Path("resources/spellchecker")
MIN_WORD_LENGTH = 3
WORD_PATTERN = re.compile(r"^[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
SUGGESTION_LIMIT = 7

class SpellcheckWorker(QObject):
    finished = pyqtSignal()
    spellcheck_results_ready = pyqtSignal(dict, dict) # word -> is_misspelled, word -> suggestions

    def __init__(self, spellchecker_manager):
        super().__init__()
        self.sm = spellchecker_manager
        self._queue = []
        self._queue_set = set() # For O(1) checks
        self._is_running = True

    @pyqtSlot()
    def process_queue(self):
        while self._is_running:
            if self._queue:
                batch_size = min(len(self._queue), 20)
                results_spell = {}
                results_sugg = {}
                
                for _ in range(batch_size):
                    word = self._queue.pop(0)
                    self._queue_set.discard(word)
                    
                    if not self.sm.hunspell:
                        continue
                        
                    # 1. Check spelling
                    is_misspelled = False
                    if word not in self.sm._spell_cache:
                        try:
                            is_correct = self.sm.hunspell.lookup(word)
                            is_misspelled = not is_correct
                            results_spell[word] = is_misspelled
                        except Exception as e:
                            log_debug(f"SpellcheckWorker: Error checking '{word}': {e}")
                            continue
                    else:
                        is_misspelled = self.sm._spell_cache.get(word, False)
                    
                    # 2. Fetch suggestions if misspelled
                    if is_misspelled and word not in self.sm._suggestions_cache:
                        try:
                            suggestions = []
                            res = self.sm.hunspell.suggest(word)
                            if hasattr(res, '__next__') or (hasattr(res, '__iter__') and not isinstance(res, list)):
                                gen = iter(res)
                                for _ in range(SUGGESTION_LIMIT):
                                    try:
                                        suggestions.append(next(gen))
                                    except StopIteration:
                                        break
                            else:
                                suggestions = list(res)[:SUGGESTION_LIMIT]
                            results_sugg[word] = suggestions
                        except Exception as e:
                            log_debug(f"SpellcheckWorker: Error suggesting for '{word}': {e}")
                            
                if results_spell or results_sugg:
                    self.spellcheck_results_ready.emit(results_spell, results_sugg)
            else:
                time.sleep(0.05)
        self.finished.emit()

    def stop(self):
        self._is_running = False

    def enqueue(self, word):
        if word not in self._queue_set:
            self._queue.append(word)
            self._queue_set.add(word)

class SpellcheckerManager:
    def __init__(self, main_window, language='uk', custom_dict_path=None):
        self.mw = main_window
        self.language = language
        self.custom_dict_path = Path(custom_dict_path) if custom_dict_path else LOCAL_DICT_PATH
        self.hunspell: Optional['Dictionary'] = None
        self.enabled = False
        self.custom_words = set()
        self._spell_cache: Dict[str, bool] = {}
        self._suggestions_cache: Dict[str, List[str]] = {}
        self._cache_file = LOCAL_DICT_PATH / "spell_cache.json"

        self._initialize_spellchecker()
        self._load_persistent_cache()
        self._setup_prefetch_worker()

    def __del__(self):
        try:
            self._save_persistent_cache()
        except:
            pass
            
        try:
            if hasattr(self, 'thread') and self.thread.isRunning():
                if hasattr(self, 'worker'):
                    self.worker.stop()
                self.thread.quit()
                self.thread.wait()
        except Exception:
            pass

    def _setup_prefetch_worker(self):
        if not self.hunspell:
            return
        self.thread = QThread()
        self.worker = SpellcheckWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.process_queue)
        self.worker.spellcheck_results_ready.connect(self._on_spellcheck_results_ready)
        self.thread.start()

    def _on_spellcheck_results_ready(self, spell_results: dict, sugg_results: dict):
        cache_updated = False
        for word, is_misspelled in spell_results.items():
            if word not in self._spell_cache:
                self._spell_cache[word] = is_misspelled
                if is_misspelled:
                    cache_updated = True
                
        for word, suggestions in sugg_results.items():
            if word not in self._suggestions_cache:
                self._suggestions_cache[word] = suggestions
                
        if cache_updated:
            # Do NOT call rehighlight() here. It processes every block in the
            # document and freezes the UI for large files. Instead, misspelled
            # words will be underlined naturally on the next highlightBlock pass
            # (next keystroke, scroll, or focus change).
            pass

    def enqueue_word(self, word):
        if not self.enabled or not self.hunspell:
            return
        
        cleaned_word = word.strip("'·").lower()
        if len(cleaned_word) < MIN_WORD_LENGTH:
            return
            
        if hasattr(self, 'worker'):
            self.worker.enqueue(cleaned_word)

    def _initialize_spellchecker(self):
        log_debug("Attempting to initialize spellchecker...")
        try:
            dictionary_name = self.language
            search_path = self.custom_dict_path
            
            dictionary_basename = search_path / dictionary_name
            log_debug(f"Loading dictionary from basename: '{dictionary_basename}'")

            dic_path = dictionary_basename.with_suffix('.dic')
            aff_path = dictionary_basename.with_suffix('.aff')

            if not dic_path.exists() or not aff_path.exists():
                log_warning(f"Dictionary files (.dic, .aff) for basename '{dictionary_basename}' not found. Spellchecker will be inactive.")
                self.hunspell = None
                return

            self.hunspell = Dictionary.from_files(str(dictionary_basename))
            log_debug(f"spylls Dictionary object created successfully for language '{dictionary_name}'.")
            self._spell_cache.clear()
            self._suggestions_cache.clear()
            self._load_user_dictionary()
            self._load_glossary_words()

        except Exception as e:
            log_error(f"Failed to initialize spylls for '{self.language}': {e}", exc_info=True)
            self.hunspell = None

    def reload_dictionary(self, language: str, custom_dict_path: Optional[str] = None):
        self.language = language
        self.custom_dict_path = Path(custom_dict_path) if custom_dict_path else self.custom_dict_path
        self._initialize_spellchecker()
        log_debug(f"Spellchecker reloaded with language='{language}' and custom_dict='{self.custom_dict_path}'.")

        # Trigger rehighlight in edited_text_edit if spellchecker is enabled
        if self.enabled and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            if hasattr(self.mw.edited_text_edit, 'highlighter') and self.mw.edited_text_edit.highlighter:
                self.mw.edited_text_edit.highlighter.rehighlight()
                log_debug(f"Rehighlighting after dictionary reload")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        log_debug(f"Spellchecker {'enabled' if enabled else 'disabled'}.")

        # Update highlighter in edited_text_edit
        if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            if hasattr(self.mw.edited_text_edit, 'highlighter') and self.mw.edited_text_edit.highlighter:
                self.mw.edited_text_edit.highlighter.set_spellchecker_enabled(enabled)
                log_debug(f"Spellchecker highlighting updated in edited_text_edit")

    def scan_local_dictionaries(self) -> Dict[str, str]:
        """Scans for .dic files and returns a map of language code to full path."""
        if not LOCAL_DICT_PATH.exists():
            return {}
        
        dictionaries = {}
        for font_file in LOCAL_DICT_PATH.iterdir():
            if font_file.suffix.lower() == ".dic":
                lang_code = font_file.stem
                aff_path = LOCAL_DICT_PATH / f"{lang_code}.aff"
                if aff_path.exists():
                    dictionaries[lang_code] = str(font_file)
        
        log_debug(f"Found local dictionaries: {list(dictionaries.keys())}")
        return dictionaries

    def _load_user_dictionary(self):
        custom_dict_path = LOCAL_DICT_PATH / CUSTOM_DICT_FILENAME
        if not custom_dict_path.exists():
            custom_dict_path.parent.mkdir(parents=True, exist_ok=True)
            return
        try:
            with custom_dict_path.open('r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]
                self.custom_words = set(word.lower() for word in words)

            log_debug(f"Loaded {len(self.custom_words)} words from user dictionary.")
        except Exception as e:
            log_error(f"Failed to load user dictionary: {e}", exc_info=True)

    def reload_glossary_words(self):
        """Public method to reload glossary words. Called after glossary is initialized."""
        self._load_glossary_words()

        # Trigger rehighlight in edited_text_edit if spellchecker is enabled
        if self.enabled and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            if hasattr(self.mw.edited_text_edit, 'highlighter') and self.mw.edited_text_edit.highlighter:
                self.mw.edited_text_edit.highlighter.rehighlight()
                log_debug("Rehighlighting after glossary words reload")

    def _load_persistent_cache(self):
        """Loads spell check results from a JSON file."""
        if not self._cache_file.exists():
            return
        try:
            import json
            with self._cache_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._spell_cache.update(data)
            log_debug(f"Loaded {len(data)} cached spell entries from disk.")
        except Exception as e:
            log_warning(f"Failed to load persistent spell cache: {e}")

    def _save_persistent_cache(self):
        """Saves current memory spell cache to disk."""
        if not self._spell_cache:
            return
        try:
            import json
            # Save only entries with reasonable keys
            to_save = {k: v for k, v in self._spell_cache.items() if len(k) < 32}
            # Limit cache size to avoid huge files (e.g. 20k entries)
            if len(to_save) > 20000:
                # Keep only newest or just truncate
                to_save = dict(list(to_save.items())[:20000])
                
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_file.open('w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=0)
            log_debug(f"Saved {len(to_save)} spell cache entries to disk.")
        except Exception as e:
            log_error(f"Failed to save persistent spell cache: {e}")

    def _load_glossary_words(self):
        """Load all words from glossary translations into custom dictionary."""
        if not hasattr(self.mw, 'translation_handler') or not self.mw.translation_handler:
            log_debug("_load_glossary_words: translation_handler not available yet")
            return

        # Access glossary_manager through glossary_handler
        glossary_handler = getattr(self.mw.translation_handler, 'glossary_handler', None)
        if not glossary_handler:
            log_debug("_load_glossary_words: glossary_handler not available yet")
            return

        glossary_manager = getattr(glossary_handler, 'glossary_manager', None)
        if not glossary_manager:
            log_debug("_load_glossary_words: glossary_manager not available yet")
            return

        # Get all glossary entries
        entries = glossary_manager.get_entries()
        if not entries:
            log_debug("_load_glossary_words: no glossary entries found")
            return

        # Extract all words from translations and add them to custom_words
        word_pattern = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
        glossary_words_count = 0

        for entry in entries:
            # Extract words from translation
            translation_words = word_pattern.findall(entry.translation)
            for word in translation_words:
                # Strip apostrophes and normalize
                cleaned_word = word.strip("'").lower()
                if len(cleaned_word) >= MIN_WORD_LENGTH and cleaned_word not in self.custom_words:
                    self.custom_words.add(cleaned_word)
                    self._spell_cache[cleaned_word] = False
                    if cleaned_word in self._suggestions_cache:
                        del self._suggestions_cache[cleaned_word]
                    glossary_words_count += 1

        log_debug(f"Loaded {glossary_words_count} words from glossary into spellchecker dictionary.")

    def add_to_custom_dictionary(self, word: str):
        if not self.hunspell:
            return
        # Strip apostrophes and middle dot (·) before adding to dictionary
        cleaned_word = word.strip("'·")
        normalized_word = cleaned_word.lower()
        if normalized_word not in self.custom_words:
            self.custom_words.add(normalized_word)
            self._spell_cache[normalized_word] = False
            if normalized_word in self._suggestions_cache:
                del self._suggestions_cache[normalized_word]

            custom_dict_path = LOCAL_DICT_PATH / CUSTOM_DICT_FILENAME
            try:
                with custom_dict_path.open('a', encoding='utf-8') as f:
                    f.write(normalized_word + "\n")
                log_debug(f"Added '{normalized_word}' to user dictionary file.")
                # Trigger rehighlight to update UI
                if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
                    if hasattr(self.mw.edited_text_edit, 'highlighter') and self.mw.edited_text_edit.highlighter:
                        self.mw.edited_text_edit.highlighter.rehighlight()
            except Exception as e:
                log_error(f"Failed to save user dictionary: {e}", exc_info=True)
        
        self._save_persistent_cache()

    def is_misspelled(self, word: str) -> bool:
        if not self.enabled:
            return False
        if not self.hunspell:
            return False

        # Strip apostrophes and middle dot (·) which represents spaces in editor
        cleaned_word = word.strip("'·")

        if len(cleaned_word) < MIN_WORD_LENGTH:
            return False
        if cleaned_word.isdigit():
            return False
        if not WORD_PATTERN.match(cleaned_word):
            return False

        # Check memory cache first
        lower_word = cleaned_word.lower()

        # Check if word is in custom dictionary (includes glossary words)
        if lower_word in self.custom_words:
            self._spell_cache[lower_word] = False
            return False

        if lower_word in self._spell_cache:
            return self._spell_cache[lower_word]

        # NON-BLOCKING: If word is unknown, assume correct for UI speed,
        # but enqueue it into the background worker for real check.
        self.enqueue_word(lower_word)
        return False

    def get_suggestions(self, word: str) -> List[str]:
        if not self.enabled or not self.hunspell:
            return []

        cleaned_word = word.strip("'·").lower()
        
        if cleaned_word in self._suggestions_cache:
            return self._suggestions_cache[cleaned_word]

        # If it's not in cache, request it asynchronously and return empty
        self.enqueue_word(cleaned_word)
        return []
