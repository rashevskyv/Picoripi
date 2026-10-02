"""What a translation run has already translated, by source text -- and the folding of exact duplicates.

Two things keep one source from getting two translations in the same run:

* ``fold_duplicates`` sends one of several identical strings to the model; the
  others receive its translation when the reply arrives.
* ``RunMemory`` remembers every translation of the run, so that a later chunk
  whose string differs only in tags, case or spacing is shown the wording
  already chosen.
"""
from __future__ import annotations

import re
import threading
from collections import Counter
from typing import Any, Callable, Dict, Hashable, Iterable, List, Optional, Tuple

from core.tag_utils import strip_tags

# How many remembered rows a single request may carry.
MEMORY_ROWS_PER_REQUEST = 10

_SPACES = re.compile(r"\s+")


def normalize_source(text: Any) -> str:
    """The text two sources share when they differ only in tags, case or spacing."""
    return _SPACES.sub(" ", strip_tags(str(text or ""))).strip().casefold()


class RunMemory:
    """Source text -> the translations it received in this run. Written by the GUI thread, read by workers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: Dict[str, List[Tuple[str, str]]] = {}

    def remember(self, source: str, translation: str) -> None:
        key = normalize_source(source)
        if not key or not str(translation or "").strip():
            return
        row = (str(source), str(translation))
        with self._lock:
            rows = self._rows.setdefault(key, [])
            if row not in rows:
                rows.append(row)

    def similar(self, sources: Iterable[Any], limit: int = MEMORY_ROWS_PER_REQUEST) -> List[Dict[str, str]]:
        """Remembered rows whose source matches one of ``sources`` after normalisation, oldest first."""
        found: List[Dict[str, str]] = []
        seen = set()
        with self._lock:
            for source in sources:
                key = normalize_source(source)
                if not key or key in seen:
                    continue
                seen.add(key)
                for text, translation in self._rows.get(key, ()):
                    found.append({"text": text, "translation": translation})
                    if len(found) >= limit:
                        return found
        return found

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def __len__(self) -> int:
        with self._lock:
            return sum(len(rows) for rows in self._rows.values())


def fold_duplicates(
    items: List[Any],
    context_key: Optional[Callable[[Dict[str, Any]], Hashable]] = None,
) -> Tuple[List[Any], Dict[Any, List[Any]]]:
    """``(items to send, {id of a sent item: ids of the items that take its translation})``.

    Two items fold only when their raw text is identical -- tags, case and
    spacing included -- and ``context_key`` says they are translated under the
    same conditions (speaker, addressee, window). The key is asked only for
    texts that occur more than once. The first occurrence is the one sent.
    """
    texts = Counter(
        item.get("text") for item in items
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    )
    representatives: Dict[Tuple[str, Hashable], Any] = {}
    kept: List[Any] = []
    followers: Dict[Any, List[Any]] = {}
    for item in items:
        text = item.get("text") if isinstance(item, dict) else None
        if not isinstance(text, str) or "id" not in item or not text.strip() or texts[text] < 2:
            kept.append(item)
            continue
        key = (text, context_key(item) if context_key else None)
        if key in representatives:
            followers.setdefault(representatives[key], []).append(item["id"])
        else:
            representatives[key] = item["id"]
            kept.append(item)
    return kept, followers
