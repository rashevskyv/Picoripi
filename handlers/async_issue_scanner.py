"""Background scanner that runs line-width analysis, glossary matching, and
spellcheck off the UI thread.

Historically this was a fresh QThread spawned on every keystroke debounce tick;
the previous thread was simply abandoned into an "_orphaned_threads" list and
kept running until it finished naturally. That meant every keystroke could
queue an unbounded number of scans behind it and there was no way to actually
stop a scan that was no longer relevant.

The current implementation uses a single shared QThreadPool with one slot
plus cooperative cancellation. Each scan is a QRunnable that checks a
threading.Event between phases; when a newer scan starts, the previous one is
asked to cancel and the pool slot is reused as soon as it cooperates.
"""
import re
import threading
from typing import Any, Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from utils.logging_utils import log_error


class _ScannerSignals(QObject):
    """QRunnable can't carry signals itself; this QObject is its signal sink."""

    # block_idx, string_idx, text, problems_in_string,
    # glossary_matches, translation_matches, spellcheck_matches
    finished_scan = pyqtSignal(int, int, str, list, list, list, list)


class AsyncIssueScanner(QRunnable):
    """Background worker that runs the per-string analysis pipeline.

    Cooperative cancellation: callers may invoke ``cancel()`` to ask the
    runnable to exit at the next checkpoint. The runnable never emits its
    ``finished_scan`` signal after being cancelled, so the caller does not
    need to disconnect from it; just call ``cancel()`` and drop the reference.
    """

    def __init__(
        self,
        block_idx: int,
        string_idx: int,
        text: str,
        font_map: dict,
        width_threshold: int,
        analyzer: Any,
        glossary_manager: Any = None,
        spellchecker_manager: Any = None,
        source_text: str = "",
        active_word: str = "",
        warnings_enabled: bool = True,
        glossary_enabled: bool = True,
        editor_text: str = "",
        logical_hard_limit: Optional[int] = None,
    ):
        """Initialize a new instance."""
        super().__init__()
        self.setAutoDelete(True)
        self.signals = _ScannerSignals()

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
        self.warnings_enabled = warnings_enabled
        self.glossary_enabled = glossary_enabled
        self.editor_text = editor_text if editor_text else text
        self.logical_hard_limit = logical_hard_limit

        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------ public

    def cancel(self) -> None:
        """Ask the runnable to stop ASAP. The runnable will not emit its
        finished_scan signal after this is called."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        """Check if is cancelled."""
        return self._cancel_event.is_set()

    # Backwards-compatible shim: callers used to introspect a QThread.
    def isRunning(self) -> bool:  # noqa: N802 - matches Qt naming
        """Isrunning."""
        return not self._cancel_event.is_set()

    @property
    def finished_scan(self):  # noqa: D401 - simple proxy
        """Expose the underlying signal as if it lived on the runnable.

        TextOperationHandler historically did
        ``self.current_scanner_thread.finished_scan.connect(...)``; preserve
        that ergonomics so we don't have to touch all the call sites.
        """
        return self.signals.finished_scan

    # ---------------------------------------------------------------- internal

    def run(self) -> None:  # noqa: D401 - QRunnable entry point
        """Run."""
        try:
            if self.is_cancelled():
                return

            problems_in_string = self._run_warnings()
            if self.is_cancelled():
                return

            glossary_matches = self._run_glossary_matches()
            if self.is_cancelled():
                return

            translation_matches = self._run_translation_matches()
            if self.is_cancelled():
                return

            spellcheck_matches = self._run_spellcheck()
            if self.is_cancelled():
                return

            # Defensive: callers expect each field to be a list, never None.
            if not isinstance(problems_in_string, list):
                problems_in_string = []
            if not isinstance(glossary_matches, list):
                glossary_matches = []
            if not isinstance(translation_matches, list):
                translation_matches = []
            if not isinstance(spellcheck_matches, list):
                spellcheck_matches = []

            self.signals.finished_scan.emit(
                self.block_idx,
                self.string_idx,
                self.text,
                problems_in_string,
                glossary_matches,
                translation_matches,
                spellcheck_matches,
            )
        except Exception as e:  # pragma: no cover - defensive
            log_error(f"AsyncIssueScanner error: {e}", exc_info=True)
            if not self.is_cancelled():
                self.signals.finished_scan.emit(
                    self.block_idx, self.string_idx, self.text, [], [], [], []
                )

    # 1. Warnings (line width, etc.) — plugin-defined.
    def _run_warnings(self) -> list:
        """Internal helper to run warnings."""
        if not self.warnings_enabled:
            return []

        # Set block and string index on analyzer for context-aware validation
        self.analyzer._current_scan_block_idx = self.block_idx
        self.analyzer._current_scan_string_idx = self.string_idx

        problems_in_string = []
        if hasattr(self.analyzer, "analyze_data_string"):
            problems = self.analyzer.analyze_data_string(
                self.text, self.font_map, self.width_threshold, self.logical_hard_limit
            )
            problems_in_string = problems if isinstance(problems, list) else []
        elif hasattr(self.analyzer, "analyze_subline"):
            sublines = self.text.split("\n")
            problems_in_string = []
            for i, subline in enumerate(sublines):
                if self.is_cancelled():
                    return problems_in_string
                next_subline = sublines[i + 1] if i + 1 < len(sublines) else None
                problems = self.analyzer.analyze_subline(
                    text=subline,
                    next_text=next_subline,
                    subline_number_in_data_string=i,
                    qtextblock_number_in_editor=i,
                    is_last_subline_in_data_string=(i == len(sublines) - 1),
                    editor_font_map=self.font_map,
                    editor_line_width_threshold=self.width_threshold,
                    full_data_string_text_for_logical_check=self.text,
                    logical_hard_limit=self.logical_hard_limit,
                )
                problems_in_string.append(problems)

        # Run tag mismatch check off the main thread
        if self.source_text and hasattr(self.analyzer, "check_tags_mismatch"):
            if self.analyzer.check_tags_mismatch(self.source_text, self.text) is True:
                tag_warning_id = getattr(self.analyzer.problem_ids, 'PROBLEM_TAG_WARNING', None)
                if not tag_warning_id and isinstance(self.analyzer.problem_ids, dict):
                    tag_warning_id = self.analyzer.problem_ids.get('TAG', None)
                if not tag_warning_id:
                    # Fallback
                    for pid in getattr(self.analyzer, 'problem_definitions', {}).keys():
                        if pid.endswith('_TAG_WARNING'):
                            tag_warning_id = pid
                            break
                            
                if tag_warning_id and isinstance(tag_warning_id, str):
                    # Ensure problems_in_string has at least one subline set
                    if not problems_in_string:
                        problems_in_string = [set()]
                    # Convert to set if it's not
                    if not isinstance(problems_in_string[0], set):
                        problems_in_string[0] = set(problems_in_string[0])
                    problems_in_string[0].add(tag_warning_id)

        return problems_in_string

    # 2. Glossary occurrences in the edited text.
    def _run_glossary_matches(self) -> list:
        """Internal helper to run glossary matches."""
        if not (
            self.glossary_enabled
            and self.glossary_manager
            and self.glossary_manager.get_entries()
        ):
            return []
        try:
            matches = self.glossary_manager.find_matches(self.editor_text)
        except Exception:
            return []
        out = []
        for m in matches:
            out.append(
                {
                    "start": m.start,
                    "end": m.end,
                    "original": m.entry.original,
                    "translation": m.entry.translation,
                    "notes": m.entry.notes,
                }
            )
        return out

    # 3. Translation-glossary bridge: terms from the source text reflected
    # in the edited text via the glossary's translation regex.
    def _run_translation_matches(self) -> list:
        """Internal helper to run translation matches."""
        if not (self.glossary_enabled and self.glossary_manager and self.source_text):
            return []
        translation_matches: list = []
        try:
            from utils.utils import convert_dots_to_spaces_from_editor
            source_text_clean = convert_dots_to_spaces_from_editor(self.source_text)
            source_matches = self.glossary_manager.get_relevant_terms(source_text_clean)
            for entry in source_matches:
                if self.is_cancelled():
                    return translation_matches
                regex = self.glossary_manager.build_translation_regex(entry.translation)
                if regex:
                    for match in regex.finditer(self.editor_text):
                        translation_matches.append(
                            {
                                "start": match.start(),
                                "end": match.end(),
                                "original": entry.original,
                                "translation": entry.translation,
                                "notes": entry.notes,
                            }
                        )
        except Exception:
            pass
        return translation_matches

    # 4. Spellcheck: walk word tokens, consult hunspell, cache results.
    def _run_spellcheck(self) -> list:
        """Internal helper to run spellcheck."""
        sm = self.spellchecker_manager
        if not (sm and sm.enabled and sm.hunspell):
            return []

        WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
        spellcheck_matches: list = []
        try:
            text_with_spaces = self.editor_text.replace("·", " ")
            for match in WORD_PATTERN.finditer(text_with_spaces):
                if self.is_cancelled():
                    return spellcheck_matches
                word = match.group(0)
                cleaned_word = word.strip("'·")

                if self.active_word and cleaned_word.lower() == self.active_word.lower():
                    continue
                if len(cleaned_word) < 3:  # MIN_WORD_LENGTH
                    continue
                if cleaned_word.isdigit():
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

                if not is_misspelled:
                    continue

                spellcheck_matches.append(
                    (match.start(), match.end() - match.start())
                )
                if lower_word not in sm._suggestions_cache:
                    try:
                        suggestions: list = []
                        res = sm.hunspell.suggest(cleaned_word)
                        if hasattr(res, "__next__") or (
                            hasattr(res, "__iter__") and not isinstance(res, list)
                        ):
                            gen = iter(res)
                            for _ in range(7):
                                try:
                                    suggestions.append(next(gen))
                                except StopIteration:
                                    break
                        else:
                            suggestions = list(res)[:7]
                        sm._suggestions_cache[lower_word] = suggestions
                    except Exception:
                        pass
        except Exception:
            pass
        return spellcheck_matches


_pool_singleton: Optional[QThreadPool] = None


def get_scanner_thread_pool() -> QThreadPool:
    """Shared single-slot thread pool for AsyncIssueScanner.

    A single max-thread slot is enough because scans are debounced per
    keystroke and superseded by newer scans via cooperative cancellation.
    Anything more would just waste CPU racing the latest input.
    """
    global _pool_singleton
    if _pool_singleton is None:
        pool = QThreadPool()
        pool.setMaxThreadCount(1)
        # We rely on cooperative cancellation so the pool can exit promptly
        # when shut down. We keep expiry off so the worker thread stays warm
        # across keystrokes instead of being respawned each time.
        pool.setExpiryTimeout(-1)
        _pool_singleton = pool
    return _pool_singleton
