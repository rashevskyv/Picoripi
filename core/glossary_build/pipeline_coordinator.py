"""Coordinator: run the glossary build passes and write to the glossary.

Ties the drivers together and persists results through GlossaryManager. Kept
free of Qt: it takes one raw AI text call ``call(messages) -> str`` and drives
the passes sequentially, so it is fully testable with a fake call and an
in-memory manager. The Qt worker wraps this with a provider-backed call, a
cancel flag, and progress signals.

Build modes (roadmap section 5), each doing one thing:
- ``seed``: take the terms the game names itself and stop. No AI call at all.
- ``thorough``: sweep -> seed -> describe (status ends at synthesized).
- ``draft``: sweep -> seed with the sweep fragment as a rough description
  (status fragments, flagged unconfirmed), no describe pass.
- ``augment``: no sweep; describe existing seeded/draft entries from the text.

Translation (pass 3) is a separate step run on demand: ``run_translate``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Sequence

from core.glossary_manager import (
    STATUS_FRAGMENTS,
    STATUS_SEEDED,
    STATUS_SYNTHESIZED,
    STATUS_TRANSLATED,
    GlossaryManager,
)
from .ai_adapters import (
    make_extract,
    make_fold,
    make_name_suggester,
    make_propose,
    make_synthesize_stack,
)
from .describe_driver import DescribeResult, describe_term
from .occurrence_bridge import occurrences_by_term
from .parallel import DEFAULT_RETRY_DELAY, DEFAULT_WORKERS, run_with_retry_pass
from .sweep_driver import AggregatedTerm, merge_raw_terms
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
# The user-facing path: structural seeds -> AI sweep -> descriptions. The worker
# immediately follows it with translation proposals, so the model never pauses
# for decisions halfway through a long project.
MODE_AUTO = "auto"

# Statuses whose entries still want a description (targets of the describe pass).
_DESCRIBE_TARGETS = frozenset({STATUS_SEEDED, STATUS_FRAGMENTS})


def is_unnamed_voice_term(term: str) -> bool:
    """Game voice-bank ids ("Voice 70") are not character names.

    They get real names via Merge Speakers from Script. Running describe/translate
    on them produces "Голос 70" and burns AI calls on identifiers.
    """
    return (term or "").strip().lower().startswith("voice ")


@dataclass
class BuildResult:
    """Counts from a build run."""

    seeded: int = 0
    seeded_structural: int = 0
    # Terms offered per glossary section, whether or not they were new. A run
    # that adds nothing is otherwise unreadable: "Items" missing because the
    # source produced none looks exactly like "Items" missing because they were
    # already there, and the user cannot tell which without this.
    offered_by_section: Dict[str, int] = field(default_factory=dict)
    described: int = 0
    # Placeholder terms the AI proposed a real name for, awaiting a person.
    names_suggested: int = 0
    translated: int = 0
    # Units still failing after the retry pass: their entries got nothing.
    failed: int = 0
    cancelled: bool = False


class GlossaryBuildStoppedError(RuntimeError):
    """Raised when an AI glossary pass is stopped early due to consecutive backend failures."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        completed: int = 0,
        total: int = 0,
        failed: int = 0,
        consecutive_failures: int = 0,
        last_error: Optional[BaseException] = None,
        result: Optional[BuildResult] = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.completed = completed
        self.total = total
        self.failed = failed
        self.consecutive_failures = consecutive_failures
        self.last_error = last_error
        self.result = result


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
        on_log: Optional[Callable[[str], None]] = None,
        weigh: Callable[[str], int] = len,
        structural_seeds: Optional[Sequence[Dict[str, Any]]] = None,
        workers: int = DEFAULT_WORKERS,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        sleep: Callable[[float], None] = time.sleep,
        max_consecutive_failures: int = 0,
    ) -> None:
        self.manager = manager
        self.call = call
        self.prompts = prompts
        self.target_lang = target_lang
        self.chunk_size = chunk_size
        self.mask = mask
        self._is_cancelled = is_cancelled
        self._on_progress = on_progress
        self._on_log = on_log
        self.weigh = weigh
        self.structural_seeds = list(structural_seeds or ())
        self.workers = max(1, int(workers))
        self.retry_delay = float(retry_delay)
        self.sleep = sleep
        self.max_consecutive_failures = max(0, int(max_consecutive_failures))
        self.last_result: Optional[BuildResult] = None

    def _cancelled(self) -> bool:
        return bool(self._is_cancelled and self._is_cancelled())

    def _progress(self, stage: str, done: int, total: int) -> None:
        if self._on_progress:
            self._on_progress(stage, done, total)

    def _log(self, message: str) -> None:
        if self._on_log:
            self._on_log(message)

    def _pooled(self, stage: str, items, work, on_result, result: BuildResult) -> None:
        """Run one pass's AI calls in parallel and write results as they land.

        ``on_result`` runs on this thread, so the passes keep writing to the
        manager exactly as they did when they were loops -- and since every
        manager write persists immediately, a stopped run keeps what it finished.
        """
        outcome = run_with_retry_pass(
            items,
            work,
            workers=self.workers,
            retry_delay=self.retry_delay,
            sleep=self.sleep,
            on_result=on_result,
            on_progress=lambda done, total: self._progress(stage, done, total),
            is_cancelled=self._is_cancelled,
            max_consecutive_failures=self.max_consecutive_failures,
            on_log=self._log,
        )
        result.failed += len(outcome.failed)
        if outcome.stop_error is not None:
            completed_count = getattr(outcome, "completed", 0)
            total_count = len(items)
            msg = (
                f"AI backend is not responding: {self.max_consecutive_failures} calls in a "
                f"row failed during the {stage} pass ({completed_count}/{total_count} completed). "
                f"Stopped so the rest of the run is not spent waiting. "
                f"Entries finished before this point are saved. "
                f"Last error: {outcome.stop_error}"
            )
            raise GlossaryBuildStoppedError(
                msg,
                stage=stage,
                completed=completed_count,
                total=total_count,
                failed=len(outcome.failed),
                consecutive_failures=self.max_consecutive_failures,
                last_error=outcome.stop_error,
                result=result,
            ) from outcome.stop_error

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
        self.last_result = result
        if mode == MODE_TRANSLATE:
            # Nothing to build; the caller runs the translate pass.
            return result

        # Structural seeding is its own mode and nothing else's prelude. Running
        # it inside a sweep bought nothing -- the sweep is not told what is
        # already seeded, so it costs exactly the same either way -- while in
        # draft mode it actively lost work, replacing the game's own item text
        # with a rougher sweep fragment. Keeping the modes apart also means the
        # seeded count says what the AI actually found.
        if mode == MODE_SEED:
            self._seed_structural(result, block_indices)
            result.cancelled = self._cancelled()
            return result

        if mode == MODE_AUTO:
            self._seed_structural(result)
            if self._cancelled():
                result.cancelled = True
                return result
            aggregated = self._sweep(dataset, block_indices, result)
            if self._cancelled():
                result.cancelled = True
                return result
            self._seed_all(aggregated, MODE_THOROUGH, result)
            if self._cancelled():
                result.cancelled = True
                return result
            self._describe_all(dataset, result)
            result.cancelled = self._cancelled()
            return result

        if mode in (MODE_THOROUGH, MODE_DRAFT):
            aggregated = self._sweep(dataset, block_indices, result)
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
        result = result or self.last_result or BuildResult()
        self.last_result = result
        propose = make_propose(self.call, self.prompts, target_lang=self.target_lang)

        # An entry needs translating when it has something to translate from (a
        # description) and no translation yet. Deliberately not keyed on status:
        # entries added by hand or by older tools carry no status but still
        # qualify. Entries that already have a translation are left alone --
        # replacing a decided translation is not this pass's job.
        targets = [
            e
            for e in self.manager.get_entries()
            if e.notes and not e.translation and not is_unnamed_voice_term(e.original)
        ]

        def translate(entry):
            return propose_translations(
                entry.original,
                entry.notes,
                propose,
                normalize=self.manager.normalize_term,
            )

        def store(entry, tr):
            if not tr.active:
                return
            self.manager.update_entry(
                entry.original,
                translation=tr.active,
                notes=entry.notes,
                status=STATUS_TRANSLATED,
                translation_variants=tuple(tr.variants),
            )
            result.translated += 1

        self._pooled("translate", targets, translate, store, result)
        if self._cancelled():
            result.cancelled = True
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
            section = seed.get("section") or None
            # Counted before any skip: the question this answers is "did the
            # source produce Items at all", which a run that skipped them all
            # as already-decided must still answer yes to.
            label = section or "(no section)"
            result.offered_by_section[label] = result.offered_by_section.get(label, 0) + 1
            existing = self.manager.get_entry(term)
            if existing is not None and existing.translation and not existing.is_unconfirmed:
                continue
            description = str(seed.get("description") or "").strip()
            status = STATUS_FRAGMENTS if description else STATUS_SEEDED
            if existing is None:
                self.manager.seed_entry(
                    term,
                    section=section,
                    status=status,
                    description=description,
                    icon=str(seed.get("icon") or ""),
                    # A term the source could only give as an internal id. It
                    # is a stand-in for a name nobody has decided yet, and the
                    # glossary has to say so rather than presenting "CLERK_B"
                    # as though it were the character's name.
                    provisional=bool(seed.get("provisional")),
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

    def _sweep(self, dataset, block_indices, result: BuildResult) -> Dict[str, AggregatedTerm]:
        items = items_from_dataset(dataset, block_indices=block_indices)
        chunks = pack_chunks(items, self.chunk_size, weigh=self.weigh)
        extract = make_extract(
            self.call, self.prompts, target_lang=self.target_lang, mask=self.mask
        )
        aggregated: Dict[str, AggregatedTerm] = {}
        self._pooled(
            "sweep",
            chunks,
            extract,
            lambda chunk, raws: merge_raw_terms(
                aggregated, raws, normalize=self.manager.normalize_term
            ),
            result,
        )
        return aggregated

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
            # A fragment is one chunk's impression of a term. It fills a gap; it
            # never replaces a description that is already there -- least of all
            # one the game itself wrote.
            description = ""
            if mode == MODE_DRAFT and agg.fragment_texts and not (existing and existing.notes):
                description = agg.fragment_texts[0]
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
        targets = [
            e for e in self.manager.get_entries()
            if e.status in _DESCRIBE_TARGETS and not is_unnamed_voice_term(e.original)
        ]

        def describe(entry) -> DescribeResult:
            occurrences = occ_by_term.get(entry.original, [])
            fold = make_fold(self.call, self.prompts, term=entry.original, target_lang=self.target_lang)
            if occurrences:
                synthesize = make_synthesize_stack(
                    self.call, self.prompts, term=entry.original, target_lang=self.target_lang
                )
                return describe_term(dataset, occurrences, synthesize, fold=fold, weigh=self.weigh)
            if entry.notes:
                # A term the text never spells out -- a speaker identifier, say --
                # has no occurrences to read, but a seeder may have handed over
                # evidence in its notes. Fold that into prose instead of skipping
                # the entry, which would leave it raw forever.
                return DescribeResult(description=fold([entry.notes]))
            return DescribeResult(description="")

        def store(entry, described: DescribeResult) -> None:
            if not described.description:
                return
            self.manager.update_entry(
                entry.original,
                translation=entry.translation,
                notes=described.description,
                status=STATUS_SYNTHESIZED,
            )
            result.described += 1

        self._pooled("describe", targets, describe, store, result)
        self._suggest_names(result)

    def _suggest_names(self, result: BuildResult) -> None:
        """Read a real name out of each placeholder term's own description.

        A character's lines give them away -- they say their own name, they are
        addressed by name, they advertise the shop they keep -- and the
        description is written from exactly those lines. So the answer is
        already sitting in the glossary; this asks for it as a field instead of
        leaving a person to read three hundred descriptions looking for it.

        Suggestions only. Renaming a character rewrites every line they speak,
        so nothing here is applied without a person saying so.
        """
        targets = [
            entry for entry in self.manager.get_entries()
            if entry.provisional and entry.notes and not entry.suggested_name
            and not is_unnamed_voice_term(entry.original)
        ]
        if not targets:
            return
        suggest = make_name_suggester(self.call, self.prompts, target_lang=self.target_lang)

        def ask(entry):
            return suggest(entry.original, entry.notes)

        def store(entry, guess) -> None:
            if guess is None or not guess.name:
                return
            self.manager.suggest_name(entry.original, guess.name, guess.evidence)
            result.names_suggested += 1

        self._pooled("name", targets, ask, store, result)
