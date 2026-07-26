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
        self._cancel = False

    def cancel(self) -> None:
        """Request cooperative cancellation."""
        self._cancel = True

    def _call(self, messages: list) -> str:
        response = self.provider.translate(messages, session=None)
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
            )
            result = coordinator.build(self.dataset, self.mode, block_indices=self.block_indices)
            if self.translate and not result.cancelled:
                coordinator.run_translate(result)

            self.build_finished.emit(not result.cancelled, self._summarize(result))
        except Exception as exc:  # provider / parse failures abort the run
            log_error(f"GlossaryBuildWorker failed: {exc}", exc_info=True)
            self.build_finished.emit(False, str(exc))

    @staticmethod
    def _summarize(result: BuildResult) -> str:
        parts = [
            f"seeded {result.seeded}",
            f"described {result.described}",
            f"translated {result.translated}",
        ]
        if result.cancelled:
            parts.append("(cancelled)")
        return ", ".join(parts)
