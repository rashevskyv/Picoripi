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

from core.glossary_build.parallel import DEFAULT_RETRY_DELAY, DEFAULT_WORKERS
from core.glossary_build.pipeline_coordinator import (
    MODE_THOROUGH,
    BuildResult,
    GlossaryBuildCoordinator,
)
from core.tag_utils import mask_all_tags_including_visual_markers
from utils.logging_utils import log_error


_PROMPTS_PATH = "translation_prompts/glossary_pipeline_prompts.json"

# A normal reply takes 3-25s: the endpoint may work through several accounts
# inside a single request before it answers. A tighter timeout does not "detect
# hangs sooner", it just throws away requests that were about to succeed.
DEFAULT_TIMEOUT = 120


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
        max_consecutive_failures: int = 3,
        workers: int = DEFAULT_WORKERS,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
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
        self._max_consecutive_failures = max(1, int(max_consecutive_failures))
        self._workers = max(1, int(workers))
        self._retry_delay = float(retry_delay)
        self._timeout = max(90, int(timeout))
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

    def _call(self, messages: list) -> str:
        """One AI call, from whichever pool thread is running this unit.

        No retry loop and no backoff live here on purpose. The endpoint already
        retries internally across the accounts it holds, so a client-side loop on
        top of that is just the same address hammering a service that already
        said no -- which is how it got blocked before. A failure is raised, the
        pool records it against its unit, and the retry pass picks it up once,
        quietly.
        """
        response = self.provider.translate(
            messages, session=None, settings_override={"timeout": self._timeout}
        )
        return getattr(response, "text", "") or ""

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
                on_log=self.log.emit,
                structural_seeds=self.structural_seeds,
                workers=self._workers,
                retry_delay=self._retry_delay,
                sleep=self._sleep,
                max_consecutive_failures=self._max_consecutive_failures,
            )
            result = coordinator.build(self.dataset, self.mode, block_indices=self.block_indices)
            if self.translate and not result.cancelled:
                coordinator.run_translate(result)

            # Losing some units is a partial result; losing *every* unit is a
            # failed run wearing a success message. Only report success when
            # something was produced, or when nothing failed in the first place
            # (an augment/translate pass with no pending entries is a fine no-op).
            produced = result.seeded or result.described or result.translated
            success = not result.cancelled and bool(produced or not result.failed)
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
        if result.failed:
            # Lead with the problem; buried at the end it reads as a footnote.
            parts.append(
                f"{result.failed} request(s) still failed after the retry pass "
                "(rate limited?) — those entries contributed nothing"
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
        summary = ", ".join(parts)
        if result.offered_by_section:
            # What each section actually offered, so "Items are missing" can be
            # told apart from "Items were all already there" without guessing.
            breakdown = ", ".join(
                f"{name} {count}"
                for name, count in sorted(result.offered_by_section.items())
            )
            summary += f"\n\nFound in the sources: {breakdown}"
        return summary
