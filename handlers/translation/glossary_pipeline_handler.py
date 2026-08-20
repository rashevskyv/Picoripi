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
from handlers.translation.glossary_ai_config import resolve_glossary_ai_config
from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from core.glossary_build.pipeline_coordinator import MODE_SEED
from core.glossary_build.script_seeds import seeds_from_markup
from core.speaker_alias_merge import find_markup_project, is_confirmed_speaker_alias, load_speaker_aliases
from ui.glossary_build_dialog import (
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

    def _structural_seeds(self):
        """Glossary material already written down somewhere, needing no AI.

        Two sources, both optional and both gap-filling, so a project with only
        one of them still gets everything that one knows:

        * the game's own data, if the plugin can read it;
        * the marked-up script, which names the cast the way a reader does.
        """
        return self._apply_speaker_names(self._plugin_seeds() + self._markup_seeds())

    def _apply_speaker_names(self, seeds):
        """Seed a character under the name we decided for them.

        The plugin names a character the way the game's files do -- "Bou",
        "CLERK_B" -- because that is all the files have. The Merge Speakers step
        then works out that Bou is MAYOR BO, and that decision has to reach the
        glossary too: otherwise the same character is seeded twice, once under
        an identifier nobody recognises and once under their name, and the
        evidence the plugin gathered stays attached to the wrong one.
        """
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        try:
            aliases = load_speaker_aliases(project_dir)
        except Exception as exc:
            log_error(f"GlossaryPipelineHandler: reading speaker names failed: {exc}")
            return seeds
        renamed = []
        for seed in seeds:
            term = str(seed.get("term") or "").strip()
            name = (aliases or {}).get(term)
            if is_confirmed_speaker_alias(name):
                # Decided: it is a name now, not a stand-in.
                renamed.append({**seed, "term": name, "provisional": False})
            elif self._is_placeholder(term):
                renamed.append({**seed, "provisional": True})
            else:
                renamed.append(seed)
        return renamed

    def _is_placeholder(self, term: str) -> bool:
        """Whether this term is the game's internal id rather than a name."""
        hook = getattr(
            getattr(self.mw, "current_game_rules", None), "is_placeholder_speaker", None
        )
        if not callable(hook):
            return False
        try:
            return bool(hook(term))
        except Exception:
            return False

    def _plugin_seeds(self):
        """Glossary material the active plugin can read out of the game data."""
        rules = getattr(self.mw, "current_game_rules", None)
        getter = getattr(rules, "get_glossary_seed_entries", None)
        if not callable(getter):
            return []
        try:
            seeds = getter()
        except Exception as exc:
            log_error(f"GlossaryPipelineHandler: plugin seeding failed: {exc}")
            return []
        return [s for s in (seeds or []) if isinstance(s, dict)]

    def _markup_seeds(self):
        """Characters the marked-up script names, if there is one."""
        composer = getattr(
            getattr(self.mw, "translation_handler", None), "prompt_composer", None
        )
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        try:
            finder = getattr(composer, "_find_script_path", None)
            script_path = finder() if callable(finder) else None
            return seeds_from_markup(find_markup_project(script_path, project_dir))
        except Exception as exc:
            log_error(f"GlossaryPipelineHandler: script seeding failed: {exc}")
            return []

    def _concurrency_options(self) -> dict:
        """How wide to run and how long to wait before retrying failures.

        Read from ``glossary_ai`` directly rather than the resolved provider
        config: these are the tool's own knobs, and they must survive the
        fallback to the AI Translation provider's settings.
        """
        config = getattr(self.mw, "glossary_ai", {}) or {}
        options = {}
        for key, name in (("workers", "workers"), ("retry_delay", "retry_delay")):
            try:
                value = config.get(key)
                if value is not None:
                    options[name] = float(value) if key == "retry_delay" else int(value)
            except (TypeError, ValueError):
                pass  # a corrupt setting falls back to the worker's default
        return options

    def _resolve_provider(self):
        config = resolve_glossary_ai_config(self.mw)
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
        # physical_block_idx, not current_block_idx: in a virtual folder view the
        # latter is a negative view marker (-2..-5), which would fall through to
        # "whole project" and quietly sweep everything.
        current = getattr(self.mw.data_store, "physical_block_idx", -1)
        return [current] if current is not None and current >= 0 else None

    def _bind_glossary_file(self, manager) -> bool:
        """Ensure the glossary is bound to the project file before building.

        Launched from the Tools menu in a fresh session, nothing has resolved
        ``<project>/glossary.json`` yet. The manager then persists to nowhere:
        the build seeds hundreds of entries into memory, ``get_raw_text()``
        renders them as Markdown that carries no status and drops untranslated
        rows, and the next reload parses that back into an empty glossary --
        the whole run silently gone.

        Binding resolves the path fresh and creates the file when it does not
        exist yet, so a first build on a new project works without the user
        having to seed the file by hand.
        """
        # Already bound: nothing to resolve, and re-resolving on every check
        # would run the binder twice for one build.
        if getattr(manager, "glossary_path", None) is not None:
            return True

        glossary_handler = getattr(
            getattr(self.mw, "translation_handler", None), "glossary_handler", None
        )
        binder = getattr(glossary_handler, "bind_glossary_for_write", None)
        if callable(binder):
            try:
                if binder() is not None:
                    return True
            except Exception as exc:
                log_error(f"GlossaryPipelineHandler: binding the glossary failed: {exc}")
        if getattr(manager, "glossary_path", None) is not None:
            return True

        # No project directory means nowhere to put a project-scoped glossary.
        QMessageBox.warning(
            self.mw,
            "Build Glossary",
            "No open project to store the glossary in.\n\n"
            "The glossary belongs to the project and lives beside it as "
            "glossary.json, so a build now would be discarded when the glossary "
            "next reloads. Open or create a project, then run the build again.",
        )
        return False

    # -- entry point --------------------------------------------------------

    def make_dialog(
        self,
        parent=None,
        on_build=None,
        *,
        target_step: Optional[str] = None,
    ) -> GlossaryBuildDialog:
        """The options form, told what this project can actually offer."""
        current_idx = getattr(self.mw.data_store, "physical_block_idx", -1)
        block_names = getattr(self.mw, "block_names", {}) or {}
        current_label = block_names.get(str(current_idx)) or (
            f"Block {current_idx + 1}" if current_idx is not None and current_idx >= 0 else ""
        )
        manager = self._glossary_manager()
        try:
            entries = len(manager.get_entries() or []) if manager is not None else 0
        except Exception:
            entries = 0
        return GlossaryBuildDialog(
            parent if parent is not None else self.mw,
            has_selection=bool(self._selected_block_indices()),
            current_block_label=current_label,
            can_seed_structurally=bool(self._structural_seeds()),
            existing_entries=entries,
            on_build=on_build,
            target_step=target_step,
        )

    def build_from_text(self) -> None:
        """Show the launch dialog and start a build."""
        manager = self._ready_to_build()
        if manager is None:
            return
        dialog = self.make_dialog()
        if not dialog.exec():
            return
        self.start_build(dialog.options(), manager=manager)

    def _ready_to_build(self):
        """The glossary manager, once every refusal has had its say."""
        if not getattr(self.mw.data_store, "data", None):
            QMessageBox.information(self.mw, "Build Glossary", "Open a project first.")
            return None
        manager = self._glossary_manager()
        if manager is None:
            QMessageBox.warning(self.mw, "Build Glossary", "Glossary manager is not available.")
            return None
        if not self._bind_glossary_file(manager):
            return None
        return manager

    def seed_from_game_data(self) -> None:
        """Run structural seeding directly from game data and script markup."""
        manager = self._ready_to_build()
        if manager is None:
            return
        self.start_build(
            {
                "mode": MODE_SEED,
                "area": AREA_PROJECT,
                "chunk_size": "balanced",
                "translate": False,
            },
            manager=manager,
        )

    def start_build(self, options: dict, manager=None) -> None:
        """Run a build with options already chosen."""
        manager = manager if manager is not None else self._ready_to_build()
        if manager is None:
            return
        dataset = getattr(self.mw.data_store, "data", None)

        provider = None
        if options["mode"] != MODE_SEED:
            provider = self._resolve_provider()
            if provider is None:
                return

        block_indices = self._resolve_area(options["area"])
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str):
            target_lang = "Ukrainian"

        self._status = AIStatusDialog(self.mw)
        title = (
            "Glossary Seeding (game data)"
            if options["mode"] == MODE_SEED
            else "AI Glossary Build (text sweep)"
        )
        self._status.start(title, is_chunked=True)

        self._worker = GlossaryBuildWorker(
            manager,
            provider,
            dataset,
            mode=options["mode"],
            block_indices=block_indices,
            target_lang=target_lang,
            chunk_size=options["chunk_size"],
            translate=options["translate"],
            structural_seeds=self._structural_seeds(),
            parent=self.mw,
            **self._concurrency_options(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.build_finished.connect(self._on_finished)
        self._status.cancelled.connect(self._worker.cancel)
        self._worker.start()

    # -- signals ------------------------------------------------------------

    def _on_log(self, message: str) -> None:
        """Surface retry / backoff notices instead of dropping them."""
        log_debug(f"Glossary build: {message}")
        if self._status:
            self._status.update_step(1, message, AIStatusDialog.STATUS_IN_PROGRESS)

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
                handler.glossary_handler.refresh_open_dialog()
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
