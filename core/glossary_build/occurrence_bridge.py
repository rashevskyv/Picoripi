"""Pass 1b bridge: glossary occurrences -> describe-driver Occurrences.

The occurrence index already exists on GlossaryManager (Aho-Corasick, exact
coordinates), so pass 1b needs no new search -- only a thin, deterministic
adapter (roadmap section 5, pass 1b).

Multiple hits in the same row collapse to one Occurrence: the describe pass
builds one centered window per row, so two hits in a row would build identical
windows and waste the stack budget.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from core.glossary_manager import GlossaryManager, GlossaryOccurrence
from .context_window import Occurrence


def to_occurrences(occurrences: Iterable[GlossaryOccurrence]) -> List[Occurrence]:
    """Convert glossary occurrences to describe Occurrences, one per row."""
    seen = set()
    out: List[Occurrence] = []
    for occ in occurrences:
        key = (occ.block_idx, occ.string_idx)
        if key in seen:
            continue
        seen.add(key)
        out.append(Occurrence(block_idx=occ.block_idx, string_idx=occ.string_idx))
    return out


def occurrences_by_term(
    manager: GlossaryManager,
    dataset: Sequence[Sequence[object]],
) -> Dict[str, List[Occurrence]]:
    """Build ``{term_original: [Occurrence, ...]}`` for every glossary term.

    Uses the manager's existing occurrence index; rows are deduped per term.
    """
    index = manager.build_occurrence_index(dataset)
    return {term: to_occurrences(occs) for term, occs in index.items()}
