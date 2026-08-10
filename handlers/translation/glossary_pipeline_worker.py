"""QThread worker driving the glossary build pipeline against a real provider.

Thin adapter: it turns the AI provider into the single ``call(messages) -> str``
the coordinator wants, forwards cancel and progress, and runs off the UI thread.
All the logic lives in ``core/glossary_build`` and is tested without Qt; this
layer is only wiring.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from PyQt6.QtCore import QThread, pyqtSignal

from core.glossary_build.pipeline_coordinator import (
    MODE_THOROUGH,
    BuildResult,
    GlossaryBuildCoordinator,
)
from core.glossary_build.retry import call_with_retry, is_transient
from core.tag_utils import mask_all_tags_including_visual_markers
from utils.logging_utils import log_error


_PROMPTS_PATH = "translation_prompts/glossary_pipeline_prompts.json"


class GlossaryBuildWorker(QThread):
    """Runs a glossary build (and optional translate pass) in the background."""

    progress = pyqtSignal(str, int, int)   # stage, done, total
    log = pyqtSignal(str)
    build_finished = pyqtSignal(bool, str)  # success, summary  (QThread.finished is taken)

    def __init__(
        self,
        manager,
        provider,
        dataset: Sequence[Sequence[object]],
        *,
        mode: str = MODE_THOROUGH,
        block_indices: Optional[Sequence[int]] = None,
        target_lang: str = "Ukrainian",
        chunk_size: Any = "balanced",
        translate: bool = False,
        prompts: Optional[dict] = None,
        retry_attempts: int = 6,
        max_consecutive_failures: int = 3,
        structural_seeds=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.provider = provider
        self.dataset = dataset
        self.mode = mode
        self.block_indices = block_indices
        self.target_lang = target_lang
        self.chunk_size = chunk_size
        self.translate = translate
        self._prompts = prompts
        self.structural_seeds = list(structural_seeds or ())
        self._retry_attempts = retry_attempts
        self._max_consecutive_failures = max(1, int(max_consecutive_failures))
        self._skipped_calls = 0
        self._consecutive_failures = 0
        self._cancel = False

    def cancel(self) -> None:
        """Request cooperative cancellation."""
        self._cancel = True

    def _sleep(self, seconds: float) -> None:
        """Back off in short slices so cancelling stays responsive."""
        remaining = max(0.0, float(seconds))
        while remaining > 0 and not self._cancel:
            slice_ms = int(min(0.25, remaining) * 1000)
            self.msleep(max(1, slice_ms))
            remaining -= 0.25

    def _request(self, messages: list) -> str:
        response = self.provider.translate(messages, session=None)
        return getattr(response, "text", "") or ""

    def _call(self, messages: list) -> str:
        """One AI call, retried through transient failures.

        Every pass funnels through here, so this is the single place the whole
        pipeline gets its rate-limit tolerance. When the retries are spent on a
        transient failure the call is skipped rather than aborting: an empty
        reply parses as "nothing found" for this chunk, which costs one chunk's
        terms instead of the entire run. A non-transient error still aborts --
        a bad key or model will not fix itself on chunk 400.

        Skipping is for a flaky call, not a dead backend. Several give-ups in a
        row mean the model is not coming back within this run, so the build stops
        rather than grinding through hundreds of chunks that can only fail --
        slowly producing nothing while every backoff is paid in full.
        """
        try:
            text = call_with_retry(
                lambda: self._request(messages),
                attempts=self._retry_attempts,
                sleep=self._sleep,
                is_cancelled=lambda: self._cancel,
                on_retry=lambda attempt, delay, exc: self.log.emit(
                    f"AI call failed ({exc}); retry {attempt} in {delay:.0f}s"
                ),
            )
        except Exception as exc:
            if not is_transient(exc) or self._cancel:
                raise
            self._skipped_calls += 1
            self._consecutive_failures += 1
            log_error(f"GlossaryBuildWorker: skipping chunk after retries: {exc}")
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise RuntimeError(
                    f"AI backend is not responding: {self._consecutive_failures} calls in "
                    f"a row failed, each retried {self._retry_attempts} times. Stopped so "
                    f"the rest of the run is not spent waiting. Entries finished before "
                    f"this point are saved. Last error: {exc}"
                ) from exc
            self.log.emit(
                f"Chunk skipped after {self._retry_attempts} attempts; continuing"
            )
            return ""
        self._consecutive_failures = 0
        return text

    def _load_prompts(self) -> dict:
        if self._prompts is not None:
            return self._prompts
        return json.loads(Path(_PROMPTS_PATH).read_text(encoding="utf-8"))

    def run(self) -> None:
        try:
            prompts = self._load_prompts()
            coordinator = GlossaryBuildCoordinator(
                self.manager,
                self._call,
                prompts,
                target_lang=self.target_lang,
                chunk_size=self.chunk_size,
                mask=mask_all_tags_including_visual_markers,
                is_cancelled=lambda: self._cancel,
                on_progress=self.progress.emit,
                structural_seeds=self.structural_seeds,
            )
            result = coordinator.build(self.dataset, self.mode, block_indices=self.block_indices)
            if self.translate and not result.cancelled:
                coordinator.run_translate(result)

            # Skipping chunks is a partial result; skipping *every* chunk is a
            # failed run wearing a success message. Only report success when
            # something was produced, or when nothing failed in the first place
            # (an augment/translate pass with no pending entries is a fine no-op).
            produced = result.seeded or result.described or result.translated
            success = not result.cancelled and bool(produced or not self._skipped_calls)
            self.build_finished.emit(success, self._summarize(result))
        except Exception as exc:  # provider / parse failures abort the run
            if self._cancel:
                # Cancelling mid-request surfaces as a provider error; report the
                # reason the user actually gave.
                self.build_finished.emit(False, self._summarize(BuildResult(cancelled=True)))
                return
            log_error(f"GlossaryBuildWorker failed: {exc}", exc_info=True)
            self.build_finished.emit(False, str(exc))

    def _summarize(self, result: BuildResult) -> str:
        parts = []
        if self._skipped_calls:
            # Lead with the problem; buried at the end it reads as a footnote.
            parts.append(
                f"{self._skipped_calls} AI call(s) gave up after retries "
                "(rate limited?) — those chunks contributed nothing"
            )
        # Split the seed count: a run that found 3 terms with AI and took 200
        # from the game data reads as "seeded 203" otherwise, which hides
        # exactly the number the user is trying to judge.
        seeded = f"seeded {result.seeded}"
        if result.seeded_structural:
            from_ai = result.seeded - result.seeded_structural
            seeded = (
                f"seeded {result.seeded} "
                f"({from_ai} from text, {result.seeded_structural} from game data)"
            )
        parts += [
            seeded,
            f"described {result.described}",
            f"translated {result.translated}",
        ]
        if result.names_suggested:
            parts.append(
                f"{result.names_suggested} placeholder name(s) have a suggestion "
                "waiting in Merge Speakers"
            )
        if result.cancelled:
            parts.append("(cancelled)")
        return ", ".join(parts)
