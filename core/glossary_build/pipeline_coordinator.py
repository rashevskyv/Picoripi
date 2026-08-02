"""Coordinator: run the glossary build passes and write to the glossary.

Ties the drivers together and persists results through GlossaryManager. Kept
free of Qt: it takes one raw AI text call ``call(messages) -> str`` and drives
the passes sequentially, so it is fully testable with a fake call and an
in-memory manager. The Qt worker wraps this with a provider-backed call, a
cancel flag, and progress signals.

Three build modes (roadmap section 5):
- ``thorough``: sweep -> seed -> describe (status ends at synthesized).
- ``draft``: sweep -> seed with the sweep fragment as a rough description
  (status fragments, flagged unconfirmed), no describe pass.
- ``augment``: no sweep; describe existing seeded/draft entries from the text.

Translation (pass 3) is a separate step run on demand: ``run_translate``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from core.glossary_manager import (
    STATUS_FRAGMENTS,
    STATUS_SEEDED,
    STATUS_SYNTHESIZED,
    STATUS_TRANSLATED,
    GlossaryManager,
)
from .ai_adapters import make_extract, make_fold, make_propose, make_synthesize_stack
from .describe_driver import DescribeResult, describe_term
from .occurrence_bridge import occurrences_by_term
from .sweep_driver import AggregatedTerm, sweep_terms
from .text_sweep import DEFAULT_CHUNK_SIZE, items_from_dataset, pack_chunks
from .translate_driver import propose_translations


MODE_THOROUGH = "thorough"
MODE_DRAFT = "draft"
MODE_AUGMENT = "augment"
# Translate only: no sweep, no describe — just propose translations for entries
# that already have a description but no translation.
MODE_TRANSLATE = "translate"
# Structural seed only: take the terms the game names itself and stop. Makes no
# AI call at all, so it costs nothing and works with the model offline.
MODE_SEED = "seed"

# Statuses whose entries still want a description (targets of the describe pass).
_DESCRIBE_TARGETS = frozenset({STATUS_SEEDED, STATUS_FRAGMENTS})


@dataclass
class BuildResult:
    """Counts from a build run."""

    seeded: int = 0
    seeded_structural: int = 0
    described: int = 0
    translated: int = 0
    cancelled: bool = False


class GlossaryBuildCoordinator:
    """Run glossary build passes against a GlossaryManager."""

    def __init__(
        self,
        manager: GlossaryManager,
        call: Callable[[list], str],
        prompts: Dict[str, Any],
        *,
        target_lang: str = "Ukrainian",
        chunk_size=DEFAULT_CHUNK_SIZE,
        mask: Optional[Callable[[str], str]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
        weigh: Callable[[str], int] = len,
        structural_seeds: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> None:
        self.manager = manager
        self.call = call
        self.prompts = prompts
        self.target_lang = target_lang
        self.chunk_size = chunk_size
        self.mask = mask
        self._is_cancelled = is_cancelled
        self._on_progress = on_progress
        self.weigh = weigh
        self.structural_seeds = list(structural_seeds or ())

    def _cancelled(self) -> bool:
        return bool(self._is_cancelled and self._is_cancelled())

    def _progress(self, stage: str, done: int, total: int) -> None:
        if self._on_progress:
            self._on_progress(stage, done, total)

    # -- public API ---------------------------------------------------------

    def build(
        self,
        dataset: Sequence[Sequence[object]],
        mode: str,
        *,
        block_indices: Optional[Sequence[int]] = None,
    ) -> BuildResult:
        """Run a build in the given mode."""
        result = BuildResult()
        if mode == MODE_TRANSLATE:
            # Nothing to build; the caller runs the translate pass.
            return result

        # Terms the game names itself cost nothing to take, so every build that
        # is allowed to add entries starts with them.
        if mode in (MODE_SEED, MODE_THOROUGH, MODE_DRAFT):
            self._seed_structural(result, block_indices)
            if mode == MODE_SEED or self._cancelled():
                result.cancelled = self._cancelled()
                return result

        if mode in (MODE_THOROUGH, MODE_DRAFT):
            aggregated = self._sweep(dataset, block_indices)
            if self._cancelled():
                result.cancelled = True
                return result
            self._seed_all(aggregated, mode, result)
            if self._cancelled():
                result.cancelled = True
                return result
            if mode == MODE_DRAFT:
                return result

        # thorough and augment both run the describe pass over pending entries
        self._describe_all(dataset, result)
        result.cancelled = self._cancelled()
        return result

    def run_translate(self, result: Optional[BuildResult] = None) -> BuildResult:
        """Propose translations for entries that have a description but none yet."""
        result = result or BuildResult()
        propose = make_propose(self.call, self.prompts, target_lang=self.target_lang)

        # An entry needs translating when it has something to translate from (a
        # description) and no translation yet. Deliberately not keyed on status:
        # entries added by hand or by older tools carry no status but still
        # qualify. Entries that already have a translation are left alone --
        # replacing a decided translation is not this pass's job.
        targets = [
            e
            for e in self.manager.get_entries()
            if e.notes and not e.translation
        ]
        total = len(targets)
        for index, entry in enumerate(targets):
            if self._cancelled():
                result.cancelled = True
                break
            tr = propose_translations(
                entry.original,
                entry.notes,
                propose,
                normalize=self.manager.normalize_term,
            )
            if tr.active:
                self.manager.update_entry(
                    entry.original,
                    translation=tr.active,
                    notes=entry.notes,
                    status=STATUS_TRANSLATED,
                    translation_variants=tuple(tr.variants),
                )
                result.translated += 1
            self._progress("translate", index + 1, total)
        return result

    # -- passes -------------------------------------------------------------

    def _seed_structural(self, result: BuildResult, block_indices=None) -> None:
        """Write the plugin's structural seeds into the glossary.

        Gap-filling only, like every other seed: an entry that already carries a
        decided translation is left exactly as it is.
        """
        seeds = self._seeds_in_area(block_indices)
        total = len(seeds)
        for index, seed in enumerate(seeds):
            if self._cancelled():
                return
            term = str(seed.get("term") or "").strip()
            if not term:
                continue
            existing = self.manager.get_entry(term)
            if existing is not None and existing.translation and not existing.is_unconfirmed:
                continue
            description = str(seed.get("description") or "").strip()
            section = seed.get("section") or None
            status = STATUS_FRAGMENTS if description else STATUS_SEEDED
            if existing is None:
                self.manager.seed_entry(
                    term,
                    section=section,
                    status=status,
                    description=description,
                    icon=str(seed.get("icon") or ""),
                )
                result.seeded += 1
                result.seeded_structural += 1
            elif description and not existing.notes:
                self.manager.update_entry(
                    term,
                    translation=existing.translation,
                    notes=description,
                    section=section,
                    status=status,
                )
                result.seeded += 1
                result.seeded_structural += 1
            self._progress("structural seed", index + 1, total)

    def _seeds_in_area(self, block_indices) -> list:
        """Seeds belonging to the blocks this build was asked to cover.

        Choosing one block and getting the whole game's terms is not what the
        area selector promises. A seed that records no block is kept: the plugin
        could not say where it came from, so scoping it would silently drop it.
        """
        if block_indices is None:
            return list(self.structural_seeds)
        wanted = {int(b) for b in block_indices}
        kept = []
        for seed in self.structural_seeds:
            blocks = seed.get("blocks")
            if not blocks or wanted.intersection(int(b) for b in blocks):
                kept.append(seed)
        return kept

    def _sweep(self, dataset, block_indices) -> Dict[str, AggregatedTerm]:
        items = items_from_dataset(dataset, block_indices=block_indices)
        chunks = pack_chunks(items, self.chunk_size, weigh=self.weigh)
        extract = make_extract(
            self.call, self.prompts, target_lang=self.target_lang, mask=self.mask
        )
        return sweep_terms(
            chunks,
            extract,
            normalize=self.manager.normalize_term,
            is_cancelled=self._is_cancelled,
            on_chunk=lambda done, total: self._progress("sweep", done, total),
        )

    def _seed_all(self, aggregated: Dict[str, AggregatedTerm], mode: str, result: BuildResult) -> None:
        terms = list(aggregated.values())
        total = len(terms)
        status = STATUS_FRAGMENTS if mode == MODE_DRAFT else STATUS_SEEDED
        for index, agg in enumerate(terms):
            if self._cancelled():
                return
            existing = self.manager.get_entry(agg.term)
            # Never overwrite a real, already-decided entry; only fill gaps.
            if existing is not None and existing.translation and not existing.is_unconfirmed:
                continue
            description = agg.fragment_texts[0] if (mode == MODE_DRAFT and agg.fragment_texts) else ""
            self._write_seed(agg, status=status, description=description)
            result.seeded += 1
            self._progress("seed", index + 1, total)

    def _write_seed(self, agg: AggregatedTerm, *, status: str, description: str) -> None:
        term = agg.term
        section = agg.section or None
        existing = self.manager.get_entry(term)
        if existing is None:
            self.manager.seed_entry(term, section=section, status=status, description=description)
            existing = self.manager.get_entry(term)
        self.manager.update_entry(
            term,
            translation=existing.translation,
            notes=description or existing.notes,
            section=section,
            status=status,
            fragments=tuple(agg.fragments) or existing.fragments,
        )

    def _describe_all(self, dataset, result: BuildResult) -> None:
        occ_by_term = occurrences_by_term(self.manager, dataset)
        targets = [e for e in self.manager.get_entries() if e.status in _DESCRIBE_TARGETS]
        total = len(targets)
        for index, entry in enumerate(targets):
            if self._cancelled():
                return
            occurrences = occ_by_term.get(entry.original, [])
            fold = make_fold(self.call, self.prompts, term=entry.original, target_lang=self.target_lang)
            if occurrences:
                synthesize = make_synthesize_stack(
                    self.call, self.prompts, term=entry.original, target_lang=self.target_lang
                )
                described = describe_term(dataset, occurrences, synthesize, fold=fold, weigh=self.weigh)
            elif entry.notes:
                # A term the text never spells out -- a speaker identifier, say --
                # has no occurrences to read, but a seeder may have handed over
                # evidence in its notes. Fold that into prose instead of skipping
                # the entry, which would leave it raw forever.
                described = DescribeResult(description=fold([entry.notes]))
            else:
                continue
            if described.description:
                self.manager.update_entry(
                    entry.original,
                    translation=entry.translation,
                    notes=described.description,
                    status=STATUS_SYNTHESIZED,
                )
                result.described += 1
            self._progress("describe", index + 1, total)
