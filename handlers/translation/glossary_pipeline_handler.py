"""Wire the Build-Glossary-from-Text action to the pipeline worker.

Resolves options from the launch dialog, reuses the same provider configuration
as the per-block AI Build Glossary action, runs GlossaryBuildWorker, and reports
progress through the shared AIStatusDialog.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import QMessageBox

from components.ai_status_dialog import AIStatusDialog
from core.glossary_manager import (
    STATUS_FRAGMENTS,
    STATUS_SEEDED,
    possible_duplicate_pairs,
)
from core.translation.providers import get_provider_for_config
from handlers.translation.glossary_ai_config import resolve_glossary_ai_config
from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from core.glossary_build.pipeline_coordinator import MODE_AUGMENT, MODE_AUTO, MODE_SEED
from core.glossary_build.script_seeds import seeds_from_markup
from core.speaker_resolution import build_speaker_pool
from core.speaker_alias_merge import (
    find_markup_project,
    is_applyable_speaker_alias,
    load_speaker_aliases,
    split_shared_speaker_names,
)
from ui.glossary_build_dialog import (
    AREA_PROJECT,
    AREA_SELECTED,
    GlossaryBuildDialog,
)
from ui.glossary_stopped_dialog import (
    ACTION_RESUME,
    ACTION_REVIEW,
    GlossaryStoppedDialog,
)
from utils.logging_utils import log_debug, log_error


class GlossaryPipelineHandler:
    """Runs the text-sweep glossary build for the whole project or a subset."""

    def __init__(self, main_window):
        self.mw = main_window
        self._worker: Optional[GlossaryBuildWorker] = None
        self._status: Optional[AIStatusDialog] = None
        self._pending_scan_state: Optional[dict] = None
        self._stopped_retry_count: int = 0
        self._prevent_sleep: bool = True
        self._sleep_after: bool = False
        self._last_options: Optional[dict] = None

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
            if is_applyable_speaker_alias(name):
                # One voice can name several characters. Seed each name, never
                # one glossary term called "A / B".
                for part in split_shared_speaker_names(name):
                    renamed.append({**seed, "term": part, "provisional": False})
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
        for key, name in (
            ("workers", "workers"),
            ("retry_delay", "retry_delay"),
            ("max_consecutive_failures", "max_consecutive_failures"),
            ("timeout", "timeout"),
        ):
            try:
                value = config.get(key)
                if value is not None:
                    options[name] = float(value) if key == "retry_delay" else int(value)
            except (TypeError, ValueError):
                pass  # a corrupt setting falls back to the worker's default
        if "max_consecutive_failures" not in options:
            options["max_consecutive_failures"] = 5
        if "timeout" not in options:
            # The local proxy retries across accounts; 60s is not enough for
            # Parallel Requests > 1 plus the per-IP pace gap.
            try:
                resolved = resolve_glossary_ai_config(self.mw)
                t = resolved.get("timeout")
                if t is not None:
                    options["timeout"] = max(180, int(t))
                else:
                    options["timeout"] = 180
            except (TypeError, ValueError, AttributeError):
                pass
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

    @staticmethod
    def _fingerprint_block(block) -> str:
        payload = json.dumps(block, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _scan_state_path(self, manager) -> Optional[Path]:
        glossary_path = getattr(manager, "glossary_path", None)
        return Path(glossary_path).with_suffix(".scan.json") if glossary_path else None

    def _load_scan_state(self, manager) -> dict:
        path = self._scan_state_path(manager)
        if path is None or not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_scan_state(self, manager, state: dict) -> None:
        path = self._scan_state_path(manager)
        if path is None:
            return
        try:
            path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            log_error(f"GlossaryPipelineHandler: saving incremental scan state failed: {exc}")

    @staticmethod
    def _seeds_for_scope(seeds, block_indices):
        """Keep global seeds for whole-project runs and placed seeds for subsets."""
        if block_indices is None:
            return list(seeds)
        wanted = set(block_indices)
        return [
            seed for seed in seeds
            if seed.get("blocks") and wanted.intersection(int(i) for i in seed["blocks"])
        ]

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
        entries = list(manager.get_entries() or []) if manager is not None else []
        existing_count = len(entries)
        undescribed_count = sum(
            1 for e in entries if not e.notes or e.status in {STATUS_SEEDED, STATUS_FRAGMENTS}
        )
        untranslated_count = sum(1 for e in entries if e.notes and not e.translation)

        return GlossaryBuildDialog(
            parent if parent is not None else self.mw,
            has_selection=bool(self._selected_block_indices()),
            current_block_label=current_label,
            can_seed_structurally=bool(self._structural_seeds()),
            existing_entries=existing_count,
            pending_description_count=undescribed_count,
            pending_translation_count=untranslated_count,
            on_build=on_build,
            target_step=target_step,
            block_labels=[
                (
                    index,
                    block_names.get(str(index))
                    or getattr(self.mw.data_store, "block_names", {}).get(str(index))
                    or f"Block {index + 1}",
                )
                for index, _block in enumerate(getattr(self.mw.data_store, "data", None) or [])
            ],
        )

    def build_from_text(self) -> None:
        """Show the launch dialog and start a build."""
        manager = self._ready_to_build()
        if manager is None:
            return
        dialog = self.make_dialog(target_step="auto")
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
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        try:
            aliases = load_speaker_aliases(project_dir)
        except Exception:
            aliases = {}

        raw_pool = build_speaker_pool(self.mw, raw=True)
        manager.bind_project_rows(
            getattr(self.mw, "data_store", None),
            getattr(self.mw, "current_game_rules", None),
            speaker_aliases=aliases,
            speaker_pool=raw_pool,
        )
        dataset = getattr(self.mw.data_store, "data", None)

        if options.get("resume_pending"):
            options["mode"] = MODE_AUGMENT

        provider = None
        if options["mode"] != MODE_SEED:
            provider = self._resolve_provider()
            if provider is None:
                return

        block_indices = self._resolve_area(options["area"])
        structural_seeds = self._structural_seeds()
        self._pending_scan_state = None
        if options["mode"] == MODE_AUTO:
            selected = options.get("block_indices")
            requested = list(range(len(dataset))) if selected is None else list(selected)
            current = {
                str(index): self._fingerprint_block(dataset[index])
                for index in requested
                if 0 <= index < len(dataset)
            }
            previous = self._load_scan_state(manager)
            block_indices = requested if options.get("full_rescan") else [
                index for index in requested
                if previous.get(str(index)) != current.get(str(index))
            ]
            self._pending_scan_state = {**previous, **current}
            structural_seeds = self._seeds_for_scope(structural_seeds, selected)
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str):
            target_lang = "Ukrainian"

        self._last_options = dict(options)
        self._prevent_sleep = options.get("prevent_sleep", self._prevent_sleep)
        self._sleep_after = options.get("sleep_after", self._sleep_after)

        self._status = AIStatusDialog(self.mw)
        self._status.prevent_sleep_checkbox.setChecked(self._prevent_sleep)
        self._status.sleep_after_checkbox.setChecked(self._sleep_after)
        if options["mode"] == MODE_SEED:
            title = "Glossary Seeding (game data)"
        elif options["mode"] == MODE_AUGMENT:
            title = "AI Glossary Build (describing & translating terms)"
        else:
            title = "AI Glossary Build (text sweep)"
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
            structural_seeds=structural_seeds,
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
                self._prevent_sleep = self._status.prevent_sleep_checkbox.isChecked()
                self._sleep_after = self._status.sleep_after_checkbox.isChecked()
            except Exception:
                pass
            try:
                self._status.finish(show_popup=False)
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

        last_result = getattr(self._worker, "last_result", None)
        stopped_error = getattr(self._worker, "stopped_error", None)
        is_cancelled = getattr(self._worker, "_cancel", False) or getattr(last_result, "cancelled", False)

        if (
            success
            and self._pending_scan_state is not None
            and not getattr(last_result, "failed", 0)
            and not getattr(last_result, "cancelled", False)
            and manager is not None
        ):
            self._save_scan_state(manager, self._pending_scan_state)
        self._pending_scan_state = None

        if success:
            self._stopped_retry_count = 0
            self._show_report(summary, manager)
        elif is_cancelled:
            self._stopped_retry_count = 0
            QMessageBox.information(self.mw, "Build Glossary", "Glossary build was cancelled.")
        else:
            self._show_stopped_dialog(summary, manager, stopped_error=stopped_error, last_result=last_result)

        self._worker = None

    def _show_stopped_dialog(
        self,
        summary: str,
        manager,
        *,
        stopped_error=None,
        last_result=None,
    ) -> None:
        entries = list(manager.get_entries() or []) if manager is not None else []
        total_entries = len(entries)
        described_count = sum(
            1 for e in entries if e.notes and e.status not in {STATUS_SEEDED, STATUS_FRAGMENTS}
        )
        undescribed_count = sum(
            1 for e in entries if not e.notes or e.status in {STATUS_SEEDED, STATUS_FRAGMENTS}
        )
        untranslated_count = sum(1 for e in entries if e.notes and not e.translation)

        stage_name = getattr(stopped_error, "stage", "") if stopped_error else ""
        completed_units = getattr(stopped_error, "completed", 0) if stopped_error else 0
        total_units = getattr(stopped_error, "total", 0) if stopped_error else 0
        err_msg = str(getattr(stopped_error, "last_error", "") or summary)

        can_resume = (
            undescribed_count > 0
            or untranslated_count > 0
            or (total_units > 0 and completed_units < total_units)
            or bool(stage_name)
            or bool(self._last_options)
        )

        parsed_retry = 0
        import re
        match = re.search(r"[Rr]etry after (\d+(?:\.\d+)?)s", err_msg)
        if match:
            try:
                parsed_retry = int(float(match.group(1))) + 5
            except ValueError:
                pass

        if parsed_retry > 0:
            auto_retry_delay = parsed_retry
        else:
            auto_retry_delay = 600 if self._stopped_retry_count >= 1 else 300

        dialog = GlossaryStoppedDialog(
            self.mw,
            stage_name=stage_name,
            summary=summary,
            total_entries=total_entries,
            described_count=described_count,
            undescribed_count=undescribed_count,
            untranslated_count=untranslated_count,
            completed_units=completed_units,
            total_units=total_units,
            last_error=err_msg,
            auto_retry_delay=auto_retry_delay,
            can_resume=can_resume,
            prevent_sleep=self._prevent_sleep,
            sleep_after=self._sleep_after,
            translate=bool((self._last_options or {}).get("translate", True)),
        )
        dialog.exec()

        self._prevent_sleep = dialog.prevent_sleep_checkbox.isChecked()
        self._sleep_after = dialog.sleep_after_checkbox.isChecked()

        if dialog.action == ACTION_RESUME:
            self._stopped_retry_count += 1
            if self._last_options:
                resume_options = dict(self._last_options)
            else:
                resume_options = {
                    "mode": MODE_AUGMENT,
                    "area": AREA_PROJECT,
                    "chunk_size": "balanced",
                    "translate": True,
                }
            resume_options["prevent_sleep"] = self._prevent_sleep
            resume_options["sleep_after"] = self._sleep_after
            self.start_build(resume_options, manager=manager)
        elif dialog.action == ACTION_REVIEW:
            self._stopped_retry_count = 0
            glossary_handler = getattr(
                getattr(self.mw, "translation_handler", None), "glossary_handler", None
            )
            opener = getattr(glossary_handler, "show_glossary_dialog", None)
            if callable(opener):
                opener()
        else:
            self._stopped_retry_count = 0

    def _show_report(self, summary: str, manager) -> None:
        entries = list(manager.get_entries() or []) if manager is not None else []
        review = sum(1 for entry in entries if entry.is_unconfirmed)
        ambiguous = sum(1 for entry in entries if len(entry.translation_variants) > 1)
        untranslated = sum(1 for entry in entries if not entry.translation)
        undescribed = sum(1 for entry in entries if not entry.notes)
        duplicates = len(possible_duplicate_pairs(entries))
        box = QMessageBox(self.mw)
        box.setWindowTitle("Automatic glossary pass completed")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("The automatic pass completed. The glossary is not treated as finished.")
        box.setInformativeText(
            f"{summary}\n\nReview backlog: {review}\n"
            f"Ambiguous translations: {ambiguous}\n"
            f"Untranslated entries: {untranslated}\n"
            f"Entries without a description: {undescribed}\n"
            f"Possible duplicates: {duplicates}"
        )
        review_button = box.addButton("Review glossary", QMessageBox.ButtonRole.ActionRole)
        editor_button = box.addButton("Continue in editor", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        clicked = box.clickedButton()
        if clicked is review_button:
            glossary_handler = getattr(
                getattr(self.mw, "translation_handler", None), "glossary_handler", None
            )
            opener = getattr(glossary_handler, "show_glossary_dialog", None)
            if callable(opener):
                opener()
        elif clicked is editor_button:
            self.mw.raise_()
            self.mw.activateWindow()

    def prepare_to_close(self) -> None:
        """Cancel any in-flight build before shutdown."""
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker = None
