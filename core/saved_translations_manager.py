"""Saved translations: by position (the backup a string is restored from) and by source text (the memory)."""
from utils.atomic_io import atomic_write_json
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from core.translation.run_memory import normalize_source
from utils.logging_utils import log_info, log_error

# Translations kept per source text (the newest last): the same words in another
# place of the game may have been translated differently on purpose.
MEMORY_VARIANTS = 5


def _source_hash(source: str) -> str:
    return hashlib.sha1(normalize_source(source).encode("utf-8")).hexdigest()


class SavedTranslationsManager:
    """Saved translations of a project.

    ``saved_translations.json`` maps a position (file, block key, string index)
    to its translation. ``translation_memory.json`` next to it maps a source
    text -- hashed after tags, case and spacing are normalised -- to the
    translations it received anywhere in the project.
    """
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window
        self._cache: Optional[Dict[str, str]] = None
        self._cache_path: Optional[Path] = None
        self._memory: Optional[Dict[str, List[Dict[str, str]]]] = None
        self._memory_path_loaded: Optional[Path] = None
        # True while the memory exists only here: built from the saved translations, not yet written.
        self._memory_unsaved = False

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache = None
        self._cache_path = None
        self._memory = None
        self._memory_path_loaded = None

    # ------------------------------------------------------- memory by source text

    def _memory_path(self) -> Optional[Path]:
        path = self._get_saved_translations_path()
        if not path:
            return None
        return path.with_name(path.name.replace("saved_translations", "translation_memory"))

    def _source_text(self, block_idx: Any, string_idx: Any) -> Optional[str]:
        """The original text at a position, or ``None`` when there is no such row."""
        data = getattr(getattr(self.mw, 'data_store', None), 'data', None)
        try:
            value = data[block_idx][string_idx]
        except (TypeError, IndexError, KeyError):
            return None
        return value if isinstance(value, str) else None

    @staticmethod
    def _remember(memory: Dict[str, List[Dict[str, str]]], source: Optional[str], translation: str) -> bool:
        if not source or not normalize_source(source) or not str(translation or "").strip():
            return False
        rows = memory.setdefault(_source_hash(source), [])
        row = {"source": source, "translation": translation}
        if rows and rows[-1] == row:
            return False
        # one translation per exact source: the newest; other spellings of the source keep theirs
        rows[:] = [existing for existing in rows if existing.get("source") != source][-(MEMORY_VARIANTS - 1):] + [row]
        return True

    def _memory_from_saved_translations(self) -> Dict[str, List[Dict[str, str]]]:
        """Build the memory of a project that was saved before it existed."""
        memory: Dict[str, List[Dict[str, str]]] = {}
        saved = self.load_all_saved_translations()
        data = getattr(getattr(self.mw, 'data_store', None), 'data', None)
        if not saved or not isinstance(data, list):
            return memory
        for block_idx, block in enumerate(data):
            if not isinstance(block, list):
                continue
            for string_idx, source in enumerate(block):
                text = saved.get(self._get_string_unique_key(block_idx, string_idx))
                if isinstance(source, str) and isinstance(text, str):
                    self._remember(memory, source, text)
        return memory

    def load_translation_memory(self) -> Dict[str, List[Dict[str, str]]]:
        path = self._memory_path()
        if not path:
            return {}
        if self._memory is not None and self._memory_path_loaded == path:
            return self._memory
        memory: Optional[Dict[str, List[Dict[str, str]]]] = None
        if path.exists():
            try:
                with path.open('r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    memory = loaded
            except Exception as e:
                log_error(f"Failed to load the translation memory: {e}")
        self._memory_unsaved = memory is None
        if memory is None:
            memory = self._memory_from_saved_translations()
        self._memory, self._memory_path_loaded = memory, path
        return memory

    def _save_translation_memory(self) -> None:
        path = self._memory_path()
        if not path or self._memory is None:
            return
        try:
            atomic_write_json(path, self._memory, ensure_ascii=False, indent=1)
            self._memory_unsaved = False
        except Exception as e:
            log_error(f"Failed to save the translation memory to {path}: {e}")

    def find_by_source(self, source: Any) -> Optional[str]:
        """The newest saved translation of exactly this source text, wherever it was saved."""
        if not isinstance(source, str) or not normalize_source(source):
            return None
        for row in reversed(self.load_translation_memory().get(_source_hash(source), [])):
            if isinstance(row, dict) and row.get("source") == source and isinstance(row.get("translation"), str):
                return row["translation"]
        return None

    def similar_by_source(self, source: Any) -> List[Dict[str, str]]:
        """Saved translations of this source and of its spellings that differ in tags, case or spacing; newest first."""
        if not isinstance(source, str) or not normalize_source(source):
            return []
        rows = self.load_translation_memory().get(_source_hash(source), [])
        return [row for row in reversed(rows) if isinstance(row, dict) and isinstance(row.get("translation"), str)]

    def _get_saved_translations_path(self) -> Optional[Path]:
        """Internal helper to get the saved translations path."""
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_dir:
            return Path(self.mw.project_manager.project_dir) / "saved_translations.json"
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.json_path:
            p = Path(self.mw.data_store.json_path)
            return p.parent / f"{p.stem}_saved_translations.json"
        return None

    def _get_string_unique_key(self, block_idx: int, string_idx: int) -> str:
        """Internal helper to get the string unique key."""
        block_source_file = "single_file"
        block_internal_key = ""
        if hasattr(self.mw, 'block_to_project_file_map') and self.mw.block_to_project_file_map:
            p_b_idx = self.mw.block_to_project_file_map.get(block_idx)
            if p_b_idx is not None and self.mw.project_manager and self.mw.project_manager.project and p_b_idx < len(self.mw.project_manager.project.blocks):
                block = self.mw.project_manager.project.blocks[p_b_idx]
                block_source_file = block.source_file
                block_internal_key = block.internal_key or ""
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
            block_source_file = self.mw.data_store.block_names.get(str(block_idx), f"block_{block_idx}")
            
        return f"{block_source_file}::{block_internal_key}::{string_idx}"

    def load_all_saved_translations(self) -> Dict[str, str]:
        """Load all saved translations."""
        path = self._get_saved_translations_path()
        if not path:
            return {}
            
        # Return cache if valid and path hasn't changed
        if self._cache is not None and self._cache_path == path:
            return self._cache
            
        if not path.exists():
            self._cache = {}
            self._cache_path = path
            return self._cache
            
        try:
            with path.open('r', encoding='utf-8') as f:
                self._cache = json.load(f)
                self._cache_path = path
                return self._cache
        except Exception as e:
            log_error(f"Failed to load saved translations: {e}")
            return {}

    def save_all_saved_translations(self, data: Dict[str, str]) -> bool:
        """Save all saved translations."""
        path = self._get_saved_translations_path()
        if not path:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(path, data, ensure_ascii=False, indent=4)
            # Update cache
            self._cache = data
            self._cache_path = path
            return True
        except Exception as e:
            log_error(f"Failed to save translations to {path}: {e}")
            return False

    def has_saved_translation(self, block_idx: int, string_idx: int) -> bool:
        """Check if has saved translation."""
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return key in translations

    def get_saved_translation(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Get the saved translation."""
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return translations.get(key)

    def save_translation(self, block_idx: int, string_idx: int, text: str) -> None:
        """Save translation."""
        if not text or not text.strip():
            return
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        translations[key] = text
        self.save_all_saved_translations(translations)
        remembered = self._remember(self.load_translation_memory(), self._source_text(block_idx, string_idx), text)
        if remembered or self._memory_unsaved:
            self._save_translation_memory()
        log_info(f"Saved translation for key {key}")

    def save_translations_bulk(self, block_idx: int, string_indices_and_texts: List[Tuple[int, str]]) -> None:
        """Save translations bulk."""
        translations = self.load_all_saved_translations()
        memory = self.load_translation_memory()
        any_saved = False
        any_remembered = False
        for string_idx, text in string_indices_and_texts:
            if text and text.strip():
                key = self._get_string_unique_key(block_idx, string_idx)
                translations[key] = text
                any_saved = True
                if self._remember(memory, self._source_text(block_idx, string_idx), text):
                    any_remembered = True
        if any_saved:
            self.save_all_saved_translations(translations)
        if any_remembered or (any_saved and self._memory_unsaved):
            self._save_translation_memory()
        if any_saved:
            log_info(f"Bulk saved {len(string_indices_and_texts)} translations for block {block_idx}")
