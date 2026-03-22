# --- START OF FILE core/spellchecker_manager.py ---
# /home/runner/work/RAG_project/RAG_project/core/spellchecker_manager.py
import re
from pathlib import Path
from typing import List, Optional, Dict
from utils.logging_utils import log_debug, log_warning, log_error
from spylls.hunspell import Dictionary

CUSTOM_DICT_FILENAME = "custom_dictionary.txt"
LOCAL_DICT_PATH = Path("resources/spellchecker")
MIN_WORD_LENGTH = 3
WORD_PATTERN = re.compile(r"^[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")

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

        self._initialize_spellchecker()

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
        if lower_word in self._spell_cache:
            return self._spell_cache[lower_word]

        # Check if word is in custom dictionary (includes glossary words)
        if lower_word in self.custom_words:
            self._spell_cache[lower_word] = False
            return False

        is_correct = self.hunspell.lookup(cleaned_word)
        is_misspelled = not is_correct
        self._spell_cache[lower_word] = is_misspelled
        return is_misspelled

    def get_suggestions(self, word: str) -> List[str]:
        if not self.enabled or not self.hunspell:
            return []

        # Strip apostrophes and middle dot (·) before getting suggestions
        cleaned_word = word.strip("'·")

        # Convert generator to list
        if cleaned_word.lower() in self._suggestions_cache:
            return self._suggestions_cache[cleaned_word.lower()]

        suggestions = list(self.hunspell.suggest(cleaned_word.lower()))
        self._suggestions_cache[cleaned_word.lower()] = suggestions
        log_debug(f"Spellchecker: Got {len(suggestions)} suggestions for '{word}' (cleaned: '{cleaned_word}'): {suggestions[:5]}")
        return suggestions
