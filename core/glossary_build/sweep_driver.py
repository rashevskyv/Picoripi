"""Pass 1a driver: sweep chunks and merge found terms deterministically.

The AI call is injected as ``extract`` so the whole sweep-and-merge sequence is
testable without a model (the same pattern as the rolling synthesizer). Term
identity is decided by deterministic normalization -- two spellings that
normalize equal are one term -- leaving the AI responsible only for meaning
(roadmap section 5, confirmed design).

Each chunk returns raw terms ``{term, section, fragment}``; the driver folds them
by normalized key, votes on the section, and accumulates distinct description
fragments up to a ceiling so a frequent term cannot balloon the aggregate.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Sequence

from core.glossary_manager import DescriptionFragment, GlossaryManager
from .text_sweep import SweepChunk


# Ceiling on distinct fragments kept per term during the sweep. Frequent terms
# converge on meaning quickly; extra fragments only inflate the later synthesis.
DEFAULT_MAX_FRAGMENTS = 30


@dataclass(frozen=True)
class RawTerm:
    """One term as returned by the AI for a single chunk."""

    term: str
    section: str = ""
    fragment: str = ""


@dataclass
class AggregatedTerm:
    """A term merged across every chunk that mentioned it."""

    term: str  # display form: the first spelling seen
    normalized: str
    mentions: int = 0
    _sections: Counter = field(default_factory=Counter)
    fragments: List[DescriptionFragment] = field(default_factory=list)

    @property
    def section(self) -> str:
        """The most-mentioned section, or empty if none was ever given."""
        if not self._sections:
            return ""
        return self._sections.most_common(1)[0][0]

    @property
    def fragment_texts(self) -> List[str]:
        return [f.text for f in self.fragments]


def sweep_terms(
    chunks: Sequence[SweepChunk],
    extract: Callable[[SweepChunk], Iterable[RawTerm]],
    *,
    normalize: Callable[[str], str] = GlossaryManager.normalize_term,
    max_fragments: int = DEFAULT_MAX_FRAGMENTS,
) -> Dict[str, AggregatedTerm]:
    """Sweep every chunk and merge the raw terms by normalized key.

    Returns ``{normalized_key: AggregatedTerm}``. ``extract`` is the injected AI
    call (chunk -> raw terms); it receives the whole ``SweepChunk`` so a real
    implementation can send ``chunk.text`` and, if it wishes, use provenance.
    Sweep fragments carry no precise coordinates -- exact occurrence positions
    come later from the occurrence index (pass 1b) / describe pass.
    """
    aggregated: Dict[str, AggregatedTerm] = {}

    for chunk in chunks:
        for raw in extract(chunk):
            term = (raw.term or "").strip()
            key = normalize(term)
            if not key:
                continue

            entry = aggregated.get(key)
            if entry is None:
                entry = AggregatedTerm(term=term, normalized=key)
                aggregated[key] = entry

            entry.mentions += 1
            section = (raw.section or "").strip()
            if section:
                entry._sections[section] += 1

            fragment = (raw.fragment or "").strip()
            if fragment and len(entry.fragments) < max_fragments:
                if all(existing.text != fragment for existing in entry.fragments):
                    entry.fragments.append(DescriptionFragment(text=fragment))

    return aggregated
