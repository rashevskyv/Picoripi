"""Wire the Build-Glossary-from-Text action to the pipeline worker.

Resolves options from the launch dialog, reuses the same provider configuration
as the per-block AI Build Glossary action, runs GlossaryBuildWorker, and reports
progress through the shared AIStatusDialog.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtWidgets import QMessageBox

from components.ai_status_dialog import AIStatusDialog
from core.translation.providers import get_provider_for_config
from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from ui.glossary_build_dialog import (
    AREA_CURRENT,
    AREA_PROJECT,
    AREA_SELECTED,
    GlossaryBuildDialog,
)
from utils.logging_utils import log_debug, log_error


class GlossaryPipelineHandler:
    """Runs the text-sweep glossary build for the whole project or a subset."""

    def __init__(self, main_window):
        self.mw = main_window
        self._worker: Optional[GlossaryBuildWorker] = None
        self._status: Optional[AIStatusDialog] = None

    # -- helpers ------------------------------------------------------------

    def _glossary_manager(self):
        handler = getattr(self.mw, "translation_handler", None)
        if handler is not None:
            glossary_handler = getattr(handler, "glossary_handler", None)
            if glossary_handler is not None:
                return getattr(glossary_handler, "glossary_manager", None)
        return getattr(self.mw, "glossary_manager", None)

    def _selected_block_indices(self) -> List[int]:
        """Blocks currently selected in the project tree, if any."""
        getter = getattr(self.mw, "get_selected_block_indices", None)
        if callable(getter):
            try:
                return [int(i) for i in (getter() or [])]
            except Exception:
                return []
        return []

    def _resolve_provider(self):
        config = dict(getattr(self.mw, "glossary_ai", {}) or {})
        if not config:
            config = dict(getattr(self.mw, "translation_config", {}) or {})
        try:
            return get_provider_for_config(config)
        except Exception as exc:
            log_error(f"GlossaryPipelineHandler: provider init failed: {exc}")
            QMessageBox.critical(self.mw, "AI Error", f"Failed to initialize AI provider: {exc}")
            return None

    def _resolve_area(self, area: str) -> Optional[List[int]]:
        """Map the chosen area to block indices (None means the whole project)."""
        if area == AREA_PROJECT:
            return None
        if area == AREA_SELECTED:
            selected = self._selected_block_indices()
            return selected or None
        current = getattr(self.mw.data_store, "current_block_idx", -1)
        return [current] if current is not None and current >= 0 else None

    # -- entry point --------------------------------------------------------

    def build_from_text(self) -> None:
        """Show the launch dialog and start a build."""
        dataset = getattr(self.mw.data_store, "data", None)
        if not dataset:
            QMessageBox.information(self.mw, "Build Glossary", "Open a project first.")
            return

        manager = self._glossary_manager()
        if manager is None:
            QMessageBox.warning(self.mw, "Build Glossary", "Glossary manager is not available.")
            return

        current_idx = getattr(self.mw.data_store, "current_block_idx", -1)
        block_names = getattr(self.mw, "block_names", {}) or {}
        current_label = block_names.get(str(current_idx)) or (
            f"Block {current_idx + 1}" if current_idx is not None and current_idx >= 0 else ""
        )

        dialog = GlossaryBuildDialog(
            self.mw,
            has_selection=bool(self._selected_block_indices()),
            current_block_label=current_label,
        )
        if not dialog.exec():
            return

        options = dialog.options()
        provider = self._resolve_provider()
        if provider is None:
            return

        block_indices = self._resolve_area(options["area"])
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str):
            target_lang = "Ukrainian"

        self._status = AIStatusDialog(self.mw)
        self._status.start("AI Glossary Build (text sweep)", is_chunked=True)

        self._worker = GlossaryBuildWorker(
            manager,
            provider,
            dataset,
            mode=options["mode"],
            block_indices=block_indices,
            target_lang=target_lang,
            chunk_size=options["chunk_size"],
            translate=options["translate"],
            parent=self.mw,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.build_finished.connect(self._on_finished)
        self._status.cancelled.connect(self._worker.cancel)
        self._worker.start()

    # -- signals ------------------------------------------------------------

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        if not self._status:
            return
        if total:
            self._status.setup_progress_bar(total, 0)
            self._status.update_progress(done)
        self._status.update_step(1, f"{stage.capitalize()} {done}/{total}", AIStatusDialog.STATUS_IN_PROGRESS)

    def _on_finished(self, success: bool, summary: str) -> None:
        log_debug(f"Glossary build finished: success={success} summary={summary}")
        if self._status:
            try:
                self._status.finish()
            except Exception:
                pass
            self._status = None

        manager = self._glossary_manager()
        handler = getattr(self.mw, "translation_handler", None)
        if manager is not None and handler is not None:
            try:
                manager.save_to_disk()
                handler._cached_glossary = manager.get_raw_text()
                handler.glossary_handler._update_glossary_highlighting()
            except Exception as exc:
                log_error(f"Failed to refresh glossary after build: {exc}")

        if success:
            QMessageBox.information(self.mw, "Build Glossary", f"Finished: {summary}")
        else:
            QMessageBox.warning(self.mw, "Build Glossary", f"Stopped: {summary}")

        self._worker = None

    def prepare_to_close(self) -> None:
        """Cancel any in-flight build before shutdown."""
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker = None
