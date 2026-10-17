"""Saved translations: by position (the backup a string is restored from) and by source text (the memory)."""
from utils.atomic_io import atomic_write_json
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Callable

from core.translation.run_memory import normalize_source
from core.translation.series_memory import source_hash as _source_hash
from plugins.common.series_tags import TagMap, carry, neutral_key, neutral_of, tag_fields
from utils.logging_utils import log_info, log_error, log_warning

# Translations kept per source text (the newest last): the same words in another
# place of the game may have been translated differently on purpose.
MEMORY_VARIANTS = 5


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
        # Filled when a project loads (core/translation/series_memory.py): what the other projects
        # of the series translated, and where each source text sits in this project.
        self.series_memory: Dict[str, List[Dict[str, str]]] = {}
        self.source_positions: Dict[str, List[Tuple[int, int]]] = {}
        # Set by the translation handler: (block, string, source) -> {"speaker", "addressee", "fold"}, the
        # context a translation is made under (the same key the duplicate fold uses). See context_of().
        self.context_for: Optional[Callable[[int, int, str], Optional[Dict[str, str]]]] = None
        # The tag kinds of this game (plugins/common/series_tags.py), set when a project loads, and the series rows
        # that carry a neutral text (core/translation/series_memory.index_neutral_rows).
        self.series_tag_map: Optional[TagMap] = None
        self.series_neutral: Dict[str, List[Dict[str, Any]]] = {}

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

    def _tag_fields(self, source: Optional[str]) -> Dict[str, Any]:
        """The tag kinds a row of ``source`` keeps (``syntax``, ``tags``, ``neutral``); empty without a tag map."""
        return tag_fields(source, self.series_tag_map) if source else {}

    @staticmethod
    def _remember(memory: Dict[str, List[Dict[str, str]]], source: Optional[str], translation: str,
                  context: Optional[Dict[str, str]] = None, tags: Optional[Dict[str, Any]] = None) -> bool:
        """Add a row for ``source``. ``context`` (speaker, addressee, fold) and ``tags`` (the tag kinds) are stored with the row when given.

        One row per exact source and context: the newest. The same text said under another speaker keeps its own row.
        """
        if not source or not normalize_source(source) or not str(translation or "").strip():
            return False
        rows = memory.setdefault(_source_hash(source), [])
        row: Dict[str, Any] = {"source": source, "translation": translation}
        if context:
            row.update({key: str(context.get(key) or "") for key in ("speaker", "addressee", "fold")})
        if tags:
            row.update(tags)
        if rows and rows[-1] == row:
            return False
        fold = row.get("fold")
        kept = [existing for existing in rows
                if not (existing.get("source") == source and existing.get("fold") == fold)]
        if fold:
            # One row per context, never trimmed: a line said by six speakers keeps six rows.
            rows[:] = kept + [row]
        else:
            # Rows without a context keep the cap they always had, among themselves.
            rows[:] = [r for r in kept if r.get("fold")] + [r for r in kept if not r.get("fold")][-(MEMORY_VARIANTS - 1):] + [row]
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
                    self._remember(memory, source, text, tags=self._tag_fields(source))
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

    def rows_by_source(self, source: Any) -> List[Dict[str, str]]:
        """Saved rows of exactly this source text, newest first. Each row has its context fields when it was saved with them."""
        if not isinstance(source, str) or not normalize_source(source):
            return []
        return [row for row in reversed(self.load_translation_memory().get(_source_hash(source), []))
                if isinstance(row, dict) and row.get("source") == source and isinstance(row.get("translation"), str)]

    def acceptable_rows(self, block_idx: int, string_idx: int, source: Any) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """``(own rows, series rows)`` this string may take, newest first (the context rule of D41).

        A text that occurs once in the project takes its newest own row. A repeated text takes an own row only under the
        same fold key, and a series row only under the same speaker and addressee. A series row is an exact translation
        of another game, or one carried to this game's tags (``series_mapped_for``) that could be carried.
        """
        own_all = self.rows_by_source(source)
        series_all = self.series_by_source(source)
        mapped_all = self.series_mapped_by_source(source)
        if not own_all and not series_all and not mapped_all:
            return [], []
        repeats = self.repeats_in_project(source)
        context = self.context_of(block_idx, string_idx, source) if (repeats or series_all or mapped_all) else None
        own = [row for row in own_all
               if not repeats or (context is not None and row.get("fold") == context.get("fold"))]
        series = [row for row in series_all
                  if context is not None and "speaker" in row and row.get("speaker") == context.get("speaker")
                  and row.get("addressee") == context.get("addressee")]
        series += [row for row in mapped_all
                   if row["translation"].strip() and context is not None and "speaker" in row
                   and row.get("speaker") == context.get("speaker") and row.get("addressee") == context.get("addressee")]
        return own, series

    def series_mapped_by_source(self, source: Any) -> List[Dict[str, Any]]:
        """What the other games of the series translated for this text, in this game's tags (plugins/common/series_tags.py).

        Each row has ``translation`` (empty when it cannot be carried), ``project``, ``origin`` ``series_mapped``, the
        ``speaker`` and ``addressee`` it was saved with, and ``reason`` (empty when carried, else why not). A row with
        the same text is left to ``series_by_source``. Nearest level first, as the exact rows are.
        """
        if self.series_tag_map is None or not isinstance(source, str) or not normalize_source(source):
            return []
        neutral = neutral_of(source, self.series_tag_map)
        if neutral is None:
            return []
        found: List[Dict[str, Any]] = []
        for row in self.series_neutral.get(neutral_key(neutral), []):
            if row.get("source") == source or not isinstance(row.get("translation"), str):
                continue
            translation, reason = carry(row["translation"], row, source, self.series_tag_map)
            mapped: Dict[str, Any] = {"source": row.get("source", ""), "translation": translation or "",
                                      "project": str(row.get("project") or ""), "origin": "series_mapped",
                                      "reason": reason}
            mapped.update({key: row[key] for key in ("speaker", "addressee") if key in row})
            found.append(mapped)
        return found

    def blocked_series_reason(self, block_idx: int, string_idx: int, source: Any) -> Optional[Tuple[str, str]]:
        """``(project, reason)`` of a series text of the same context that could not be carried to this game's tags, or None."""
        blocked = [row for row in self.series_mapped_by_source(source) if not row["translation"]]
        context = self.context_of(block_idx, string_idx, source) if blocked else None
        if context is None:
            return None
        for row in blocked:
            if "speaker" in row and row.get("speaker") == context.get("speaker") and row.get("addressee") == context.get("addressee"):
                return row["project"], row["reason"]
        return None

    def places_with_same_context(self, block_idx: int, string_idx: int, source: Any) -> List[Tuple[int, int]]:
        """The other places of this project where this exact text is said under the same context (the same fold key)."""
        if not isinstance(source, str) or not normalize_source(source):
            return []
        others = [place for place in self.positions_of_source(source) if place != (block_idx, string_idx)]
        context = self.context_of(block_idx, string_idx, source) if others else None
        if context is None:
            return []
        found = []
        for other_block, other_string in others:
            other = self.context_of(other_block, other_string, source)
            if other is not None and other.get("fold") == context.get("fold"):
                found.append((other_block, other_string))
        return found

    def repeats_in_project(self, source: Any) -> bool:
        """Whether this exact source text sits at more than one place in the project (only then the context matters)."""
        return len(self.positions_of_source(source)) > 1

    def context_of(self, block_idx: int, string_idx: int, source: str) -> Optional[Dict[str, str]]:
        """``{"speaker", "addressee", "fold"}`` of a string, or None when no context can be read (see context_for)."""
        if self.context_for is None:
            return None
        try:
            return self.context_for(block_idx, string_idx, source)
        except Exception as exc:  # a memory row without context is still a row; the save must not fail
            log_warning(f"Translation memory: no context for ({block_idx}, {string_idx}): {exc}")
            return None

    def _context_to_save(self, block_idx: int, string_idx: int, source: Optional[str]) -> Optional[Dict[str, str]]:
        """The context stored with a row: read only for a text that repeats, the one case a fold or a restore can confuse."""
        if not source or not self.repeats_in_project(source):
            return None
        return self.context_of(block_idx, string_idx, source)

    def similar_by_source(self, source: Any) -> List[Dict[str, str]]:
        """Saved translations of this source and of its spellings that differ in tags, case or spacing; newest first."""
        if not isinstance(source, str) or not normalize_source(source):
            return []
        rows = self.load_translation_memory().get(_source_hash(source), [])
        return [row for row in reversed(rows) if isinstance(row, dict) and isinstance(row.get("translation"), str)]

    def series_by_source(self, source: Any, exact: bool = True) -> List[Dict[str, str]]:
        """Translations of this source text in the other projects of the series, nearest level first.

        Each row has ``source``, ``translation`` and ``project``. ``exact=False``
        also gives spellings that differ in tags, case or spacing.
        """
        if not isinstance(source, str) or not normalize_source(source):
            return []
        rows = self.series_memory.get(_source_hash(source), [])
        return [row for row in rows if not exact or row.get("source") == source]

    def positions_of_source(self, source: Any) -> List[Tuple[int, int]]:
        """Every ``(block_idx, string_idx)`` of this project with exactly this source text."""
        if not isinstance(source, str) or not normalize_source(source):
            return []
        data = getattr(getattr(self.mw, 'data_store', None), 'data', None)
        found = []
        for block_idx, string_idx in self.source_positions.get(_source_hash(source), []):
            try:
                if data[block_idx][string_idx] == source:
                    found.append((block_idx, string_idx))
            except (TypeError, IndexError, KeyError):
                continue
        return found

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
        source = self._source_text(block_idx, string_idx)
        remembered = self._remember(self.load_translation_memory(), source, text,
                                    self._context_to_save(block_idx, string_idx, source), self._tag_fields(source))
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
                source = self._source_text(block_idx, string_idx)
                if self._remember(memory, source, text, self._context_to_save(block_idx, string_idx, source),
                                  self._tag_fields(source)):
                    any_remembered = True
        if any_saved:
            self.save_all_saved_translations(translations)
        if any_remembered or (any_saved and self._memory_unsaved):
            self._save_translation_memory()
        if any_saved:
            log_info(f"Bulk saved {len(string_indices_and_texts)} translations for block {block_idx}")
