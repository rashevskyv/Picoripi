"""Hierarchy AI markup lifecycle, payloads, and apply helpers."""
from __future__ import annotations

import time

from PyQt6.QtWidgets import (
    QMessageBox,
)
from PyQt6.QtCore import QThread
from core.script_markup import (
    HierarchyMark, HierarchyType, HierarchyTypeDefinition,
    default_type_definitions, mark_text,
    build_hierarchy_auto_markup_messages,
    infer_hierarchy_marks_from_examples,
)
from core.script_markup.hierarchy_ai_jobs import (
    HIERARCHY_FORMAT_VERSION as _HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT as _HIERARCHY_PROJECT_FORMAT,
    HierarchyAIPrepareWorker as _HierarchyAIPrepareWorker,
    HierarchyAIWorker as _HierarchyAIWorker,
    prepare_hierarchy_ai_jobs_from_snapshot as _prepare_hierarchy_ai_jobs_from_snapshot,
)
from core.translation.config import build_default_translation_config, merge_translation_config
from core.translation.providers import TranslationProviderError, create_translation_provider
from components.ai_status_dialog import AIStatusDialog
from core.i18n import tr

from ui.script_markup.constants import (
    _HIERARCHY_TEMPLATE_FORMAT,
    _TEXT_CONTAINER_TYPES,
)


class HierarchyAiMixin:
    """Hierarchy AI markup lifecycle, payloads, and apply helpers."""

    # ------------------------------------------------------------ export/IO
    def _switch_to_hierarchy_mode(self):
        idx = self.mode_combo.findData("hierarchy")
        old_blocked = self.mode_combo.blockSignals(True)
        try:
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        finally:
            self.mode_combo.blockSignals(old_blocked)
        self.mode = "hierarchy"
        self._update_mode_controls()

    def _hierarchy_type_to_dict(self, type_def: HierarchyTypeDefinition) -> dict[str, str]:
        return {
            "type_id": type_def.type_id,
            "label": type_def.label,
            "description": type_def.description,
            "color": type_def.color,
        }

    def _hierarchy_type_from_dict(self, data: dict) -> HierarchyTypeDefinition | None:
        type_id = str(data.get("type_id") or "").strip()
        label = str(data.get("label") or type_id).strip()
        if not type_id or not label:
            return None
        description = str(data.get("description") or f"Hierarchy type: {label}.").strip()
        color = str(data.get("color") or self._default_custom_type_color(label)).strip()
        return HierarchyTypeDefinition(type_id, label, description, color)

    def _hierarchy_type_definitions_payload(self) -> list[dict[str, str]]:
        return [
            self._hierarchy_type_to_dict(type_def)
            for type_def in self.hierarchy_type_definitions.values()
        ]

    def _rebuild_hierarchy_type_combo(self, selected_type_id: str | None = None):
        if not hasattr(self, "hierarchy_type_combo"):
            return
        selected = selected_type_id or self.hierarchy_type_combo.currentData() or HierarchyType.STRUCTURE
        role = self._role_for_hierarchy_type(selected)
        selected = self._visible_hierarchy_type_id(str(selected))
        old_blocked = self.hierarchy_type_combo.blockSignals(True)
        old_role_blocked = self.hierarchy_role_combo.blockSignals(True)
        try:
            self.hierarchy_type_combo.clear()
            for type_def in self.hierarchy_type_definitions.values():
                self._add_hierarchy_type_item(type_def)
            idx = self._hierarchy_type_index(selected)
            if idx < 0:
                idx = self._hierarchy_type_index(HierarchyType.STRUCTURE)
            if idx >= 0:
                self.hierarchy_type_combo.setCurrentIndex(idx)
            role_idx = self.hierarchy_role_combo.findData(role)
            if role_idx >= 0:
                self.hierarchy_role_combo.setCurrentIndex(role_idx)
        finally:
            self.hierarchy_type_combo.blockSignals(old_blocked)
            self.hierarchy_role_combo.blockSignals(old_role_blocked)
        self._on_hierarchy_type_changed()

    def _apply_hierarchy_type_payload(self, items, selected_type_id: str | None = None) -> None:
        selected = selected_type_id
        if selected is None and hasattr(self, "hierarchy_type_combo"):
            selected = self.hierarchy_type_combo.currentData()
        definitions = default_type_definitions()
        for item in items or []:
            if isinstance(item, dict):
                type_def = self._hierarchy_type_from_dict(item)
                if type_def is not None:
                    definitions[type_def.type_id] = type_def
        self.hierarchy_type_definitions = definitions
        self._rebuild_hierarchy_type_combo(str(selected) if selected else None)

    def _hierarchy_mark_from_dict(self, data: dict) -> HierarchyMark:
        start = max(0, int(data.get("start_line", 0)))
        end = max(start, int(data.get("end_line", start)))
        return HierarchyMark(
            start_line=start,
            end_line=end,
            depth=max(0, int(data.get("depth", 0))),
            type_id=str(data.get("type_id") or HierarchyType.TEXT),
            text=str(data.get("text") or ""),
            label=str(data.get("label") or ""),
            description=str(data.get("description") or ""),
            color=str(data.get("color") or ""),
            order=int(data.get("order", 0)),
            start_col=(None if data.get("start_col") is None else max(0, int(data["start_col"]))),
            end_col=(None if data.get("end_col") is None else max(0, int(data["end_col"]))),
            origin=str(data.get("origin") or "manual"),
            approved=bool(data.get("approved", True)),
        )

    def _hierarchy_mark_payload(self, mark: HierarchyMark, raw_lines: list[str]) -> dict:
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        return {
            "start_line": mark.start_line,
            "end_line": mark.end_line,
            "start_line_number": mark.start_line + 1,
            "end_line_number": mark.end_line + 1,
            "start_col": mark.start_col,
            "end_col": mark.end_col,
            "origin": mark.origin,
            "approved": mark.approved,
            "depth": mark.depth,
            "type_id": mark.type_id,
            "type_label": type_def.label if type_def else mark.type_id,
            "text": mark.text,
            "label": mark.label,
            "description": mark.description or (type_def.description if type_def else ""),
            "color": mark.color or (type_def.color if type_def else ""),
            "order": mark.order,
            "source_excerpt": mark_text(mark, raw_lines),
        }

    def _hierarchy_ai_instructions(self) -> list[str]:
        return [
            "Depth is the hierarchy index: 0 is top level, 1 is nested in the previous 0, "
            "2 is nested in the previous 1, and equal depths are siblings.",
            "Type names define semantics independently from depth; two nodes can share a "
            "depth and have different type_id values.",
            "Use the hierarchy_marks as user-approved examples, infer the same pattern, "
            "and produce equivalent marks for the unmarked_ranges.",
            "Mirror the observed type, depth, range, and label conventions when the source "
            "shape repeats. Do not invent a different taxonomy.",
            "Canonical Markdown renders structure as # headings, speaker+text as "
            "**SPEAKER**: text, dialogue contexts as speaker-nested conditions, "
            "actions as [*action*], notes as (note), breakers as "
            "~~~~~~~~~~~~~~~~~~~~~~~~, and narrator as bold text.",
            "Glossary nodes render as a Markdown # Glossary section. Direct children "
            "of Glossary are categories; use their labels as semantic hints such as "
            "Characters, Items, Locations, Terms, or a custom category.",
        ]

    def _hierarchy_unmarked_payload(self, raw_lines: list[str]) -> list[dict]:
        return [
            {
                "start_line": start,
                "end_line": end,
                "start_line_number": start + 1,
                "end_line_number": end + 1,
                "source_excerpt": self._source_text_for_lines(start, end, raw_lines),
            }
            for start, end in self._unmarked_ranges(raw_lines)
        ]

    def _hierarchy_project_payload(self) -> dict:
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        return {
            "format": _HIERARCHY_PROJECT_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "source_path": self.current_raw_path,
            "raw_text": raw_text,
            "type_definitions": self._hierarchy_type_definitions_payload(),
            "hierarchy_marks": [
                self._hierarchy_mark_payload(mark, raw_lines)
                for mark in sorted(self.hierarchy_marks, key=lambda m: (m.start_line, m.depth, m.order))
            ],
            "unmarked_ranges": self._hierarchy_unmarked_payload(raw_lines),
            "rendered_markdown": self._psm_text,
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _hierarchy_template_payload(self) -> dict:
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        return {
            "format": _HIERARCHY_TEMPLATE_FORMAT,
            "version": _HIERARCHY_FORMAT_VERSION,
            "type_definitions": self._hierarchy_type_definitions_payload(),
            "examples": [
                self._hierarchy_mark_payload(mark, raw_lines)
                for mark in sorted(self.hierarchy_marks, key=lambda m: (m.depth, m.type_id, m.order))
                if mark.approved
            ],
            "rendered_example_markdown": self._psm_text,
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _hierarchy_ai_is_running(self) -> bool:
        return self._hierarchy_ai_prepare_thread is not None or self._hierarchy_ai_thread is not None

    def _hierarchy_ai_snapshot(self, raw_text: str, raw_lines: list[str]) -> dict:
        return {
            "raw_text": raw_text,
            "raw_lines": list(raw_lines),
            "source_path": self.current_raw_path,
            "rendered_markdown": self._psm_text,
            "type_definitions": dict(self.hierarchy_type_definitions),
            "hierarchy_marks": [
                HierarchyMark(
                    start_line=mark.start_line,
                    end_line=mark.end_line,
                    depth=mark.depth,
                    type_id=mark.type_id,
                    text=mark.text,
                    label=mark.label,
                    description=mark.description,
                    color=mark.color,
                    order=mark.order,
                    start_col=mark.start_col,
                    end_col=mark.end_col,
                    origin=mark.origin,
                    approved=mark.approved,
                )
                for mark in self.hierarchy_marks
                if mark.approved
            ],
            "ai_instructions": self._hierarchy_ai_instructions(),
        }

    def _set_hierarchy_ai_actions_enabled(self, enabled: bool):
        for action_name in ("continue_examples_btn", "ai_markup_btn"):
            action = getattr(self, action_name, None)
            if action is not None:
                action.setEnabled(enabled)

    def _format_elapsed_time(self, started_at: float | None) -> str:
        if started_at is None:
            return "00:00"
        elapsed = max(0, int(time.monotonic() - started_at))
        minutes, seconds = divmod(elapsed, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _hierarchy_ai_detail_text(self) -> str:
        elapsed = self._format_elapsed_time(self._hierarchy_ai_started_at)
        if self._hierarchy_ai_progress_state is None:
            return f"Preparing examples and unmarked ranges... elapsed {elapsed}"
        current, total, scope_label = self._hierarchy_ai_progress_state
        if current <= 0:
            return f"Preparing {total} structure scope(s)... elapsed {elapsed}"
        return f"Scope {current}/{total}: {scope_label}\nWaiting for AI response... elapsed {elapsed}"

    def _update_hierarchy_ai_elapsed_detail(self):
        status = self._hierarchy_ai_status
        if status is None or not status.is_running:
            return
        status.set_detail_text(self._hierarchy_ai_detail_text())

    def _create_hierarchy_ai_provider(self):
        config = getattr(self.mw, "translation_config", None)
        if not isinstance(config, dict):
            config = {}
        config = merge_translation_config(build_default_translation_config(), config)
        provider_key = config.get("provider", "disabled")
        if not provider_key or provider_key == "disabled":
            QMessageBox.information(
                self,
                tr('AI markup'),
                tr('AI provider is disabled. Configure it in AI Translation settings first.'),
            )
            return None, "", ""
        provider_settings = config.get("providers", {}).get(provider_key, {})
        if not isinstance(provider_settings, dict) or not provider_settings:
            QMessageBox.warning(
                self,
                tr('AI markup'),
                f"No AI provider settings found for '{provider_key}'.",
            )
            return None, "", ""
        try:
            provider = create_translation_provider(provider_key, provider_settings)
            model_name = str(provider_settings.get("model") or provider_key)
            return provider, str(provider_key), model_name
        except TranslationProviderError as exc:
            QMessageBox.critical(self, tr('AI markup'), str(exc))
            return None, "", ""

    def _prepare_hierarchy_ai_jobs(self, raw_lines: list[str], unmarked_ranges: list[tuple[int, int]]):
        snapshot = self._hierarchy_ai_snapshot(self.raw_edit.toPlainText(), raw_lines)
        return _prepare_hierarchy_ai_jobs_from_snapshot(
            snapshot,
            unmarked_ranges,
            message_builder=build_hierarchy_auto_markup_messages,
        )

    def _continue_hierarchy_from_examples(self):
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        self._flush_pending_history()
        raw_text = self.raw_edit.toPlainText()
        if not raw_text.strip():
            QMessageBox.information(self, tr('Continue from marked examples'), tr('Load a raw script first.'))
            return
        if not any(
            mark.approved and mark.origin == "manual"
            for mark in self.hierarchy_marks
        ):
            QMessageBox.information(
                self,
                tr('Continue from marked examples'),
                tr('Mark at least one hierarchy example manually, then run this auto-fill again.'),
            )
            return
        raw_lines = raw_text.splitlines()
        result = infer_hierarchy_marks_from_examples(raw_text, self.hierarchy_marks)
        added, skipped = self._apply_hierarchy_candidate_marks(result.marks)
        if added <= 0:
            QMessageBox.information(
                self,
                tr('Continue from marked examples'),
                tr('No confident local patterns were found.\n\nMark one complete block first, such as one act with chapters, one chapter with scenes, or a speaker/text sequence, then run this again.'),
            )
            return

        details = [
            f"Added {added} local hierarchy marks.",
            "",
            f"Structures: {result.structures}",
            f"Speakers: {result.speakers}",
            f"Text blocks: {result.texts}",
            f"Actions: {result.actions}",
            f"Contexts: {result.contexts}",
            f"Items: {result.items}",
            f"Item descriptions: {result.item_descriptions}",
            f"Breakers: {result.breakers}",
            f"Ignored: {result.ignored}",
            f"Other/custom types: {result.other_types}",
        ]
        if skipped:
            details.append("")
            details.append(f"Skipped {skipped} duplicate or unsafe marks.")
        QMessageBox.information(self, tr('Continue from marked examples'), "\n".join(details))

    def _run_hierarchy_ai_markup(
        self,
        *,
        title: str = "AI markup",
        status_title: str = "AI hierarchy markup",
        require_examples: bool = False,
    ):
        if self._hierarchy_ai_is_running():
            return
        if self.mode != "hierarchy":
            self._switch_to_hierarchy_mode()
        self._flush_pending_history()
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()
        if not raw_text.strip():
            QMessageBox.information(self, title, tr('Load a raw script first.'))
            return
        if require_examples and not any(mark.approved for mark in self.hierarchy_marks):
            QMessageBox.information(
                self,
                title,
                tr('Mark or approve at least one hierarchy example first, then run this auto-fill again.'),
            )
            return
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        if not unmarked_ranges:
            QMessageBox.information(self, title, tr('There are no unmarked lines left.'))
            return

        provider, _provider_key, model_name = self._create_hierarchy_ai_provider()
        if provider is None:
            return

        self._hierarchy_ai_provider = provider
        self._hierarchy_ai_model_name = model_name
        self._set_hierarchy_ai_actions_enabled(False)
        self._hierarchy_ai_started_at = time.monotonic()
        self._hierarchy_ai_progress_state = None
        status = AIStatusDialog(self)
        self._hierarchy_ai_status = status
        status.start(status_title)
        status.update_step(0, "Preparing examples and unmarked ranges", AIStatusDialog.STATUS_IN_PROGRESS)
        status.set_detail_text(self._hierarchy_ai_detail_text())
        self._hierarchy_ai_elapsed_timer.start()

        snapshot = self._hierarchy_ai_snapshot(raw_text, raw_lines)
        thread = QThread(self)
        worker = _HierarchyAIPrepareWorker(snapshot, unmarked_ranges)
        self._hierarchy_ai_prepare_thread = thread
        self._hierarchy_ai_prepare_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.success.connect(self._on_hierarchy_ai_prepare_success)
        worker.error.connect(self._on_hierarchy_ai_prepare_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_hierarchy_ai_prepare_thread_finished)
        status.cancelled.connect(self._cancel_hierarchy_ai_markup)
        thread.start()

    def _on_hierarchy_ai_prepare_success(self, jobs: list):
        status = self._hierarchy_ai_status
        if status is None or getattr(status, "user_cancelled", False):
            return
        if not jobs:
            self._on_hierarchy_ai_prepare_error("No AI markup jobs were prepared.")
            return

        self._hierarchy_ai_progress_state = (0, len(jobs), "")
        status.set_detail_text(self._hierarchy_ai_detail_text())
        status.update_step(0, "Prepared current unmarked ranges for AI", AIStatusDialog.STATUS_DONE)
        status.set_model_name(self._hierarchy_ai_model_name)
        if len(jobs) > 1:
            status.setup_progress_bar(len(jobs), 0)
        status.update_step(
            1,
            f"Sending {len(jobs)} structure scope(s) to AI",
            AIStatusDialog.STATUS_IN_PROGRESS,
        )

        provider = self._hierarchy_ai_provider
        if provider is None:
            self._on_hierarchy_ai_prepare_error("AI provider is no longer available.")
            return

        raw_line_count = len(self.raw_edit.toPlainText().splitlines())
        thread = QThread(self)
        worker = _HierarchyAIWorker(
            provider,
            jobs,
            raw_line_count,
            dict(self.hierarchy_type_definitions),
        )
        self._hierarchy_ai_thread = thread
        self._hierarchy_ai_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_hierarchy_ai_progress)
        worker.success.connect(self._on_hierarchy_ai_success)
        worker.error.connect(self._on_hierarchy_ai_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_hierarchy_ai_thread_finished)
        thread.start()

    def _on_hierarchy_ai_prepare_error(self, message: str):
        status = self._hierarchy_ai_status
        if status is not None:
            status.update_step(0, "Could not prepare AI markup request", AIStatusDialog.STATUS_ERROR)
            status.finish(success=False, show_popup=False)
        self._hierarchy_ai_elapsed_timer.stop()
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)
        QMessageBox.warning(
            self,
            "AI markup request is too large" if "too large" in (message or "").lower() else "AI markup",
            message or "Could not prepare AI markup request.",
        )

    def _on_hierarchy_ai_prepare_thread_finished(self):
        self._hierarchy_ai_prepare_thread = None
        self._hierarchy_ai_prepare_worker = None
        status = self._hierarchy_ai_status
        if status is not None and status.is_running and getattr(status, "user_cancelled", False) and self._hierarchy_ai_thread is None:
            status.finish(success=False, show_popup=False)
            self._hierarchy_ai_elapsed_timer.stop()
            self._hierarchy_ai_status = None
            self._hierarchy_ai_started_at = None
            self._hierarchy_ai_progress_state = None
            self._hierarchy_ai_provider = None
            self._hierarchy_ai_model_name = ""
            self._set_hierarchy_ai_actions_enabled(True)

    def _mark_inside_ranges(
        self,
        mark: HierarchyMark,
        ranges: list[tuple[int, int]],
        raw_lines: list[str] | None = None,
    ) -> bool:
        if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.GLOSSARY):
            return not any(
                existing.type_id == mark.type_id
                and existing.depth == mark.depth
                and self._ranges_overlap(
                    existing.start_line,
                    existing.end_line,
                    mark.start_line,
                    mark.end_line,
                )
                for existing in self.hierarchy_marks
            )
        if any(start <= mark.start_line and mark.end_line <= end for start, end in ranges):
            return True
        if mark.type_id not in _TEXT_CONTAINER_TYPES:
            containing_text = any(
                existing.type_id == HierarchyType.TEXT
                and existing.start_line <= mark.start_line
                and mark.end_line <= existing.end_line
                for existing in self.hierarchy_marks
            )
            blocked = any(
                existing.type_id not in (
                    HierarchyType.STRUCTURE,
                    HierarchyType.SPEAKER,
                    HierarchyType.TEXT,
                )
                and self._ranges_overlap(
                    existing.start_line,
                    existing.end_line,
                    mark.start_line,
                    mark.end_line,
                )
                for existing in self.hierarchy_marks
            )
            if containing_text and not blocked:
                return True
        if (
            mark.type_id == HierarchyType.SPEAKER
            and mark.start_line == mark.end_line
            and raw_lines is not None
        ):
            line = mark.start_line
            blockers = []
            for existing in self.hierarchy_marks:
                if existing.type_id == HierarchyType.STRUCTURE:
                    if (
                        existing.start_line == line
                        and not self._structure_start_line_is_label(existing, raw_lines)
                    ):
                        continue
                    owns_line = existing.start_line == line
                elif existing.type_id == HierarchyType.SPEAKER:
                    owns_line = existing.start_line == line
                else:
                    owns_line = existing.start_line <= line <= existing.end_line
                if owns_line:
                    blockers.append(existing)
            return not blockers
        return False

    def _apply_hierarchy_candidate_marks(self, marks: list[HierarchyMark]) -> tuple[int, int]:
        raw_lines = self.raw_edit.toPlainText().splitlines()
        unmarked_ranges = self._unmarked_ranges(raw_lines)
        existing_keys = {
            (
                mark.start_line, mark.end_line, mark.depth, mark.type_id,
                mark.start_col, mark.end_col,
            )
            for mark in self.hierarchy_marks
        }
        added: list[HierarchyMark] = []
        skipped = 0
        for mark in marks:
            if (
                mark.start_line < 0
                or mark.end_line < mark.start_line
                or mark.start_line >= len(raw_lines)
                or mark.end_line >= len(raw_lines)
            ):
                skipped += 1
                continue
            key = (
                mark.start_line, mark.end_line, mark.depth, mark.type_id,
                mark.start_col, mark.end_col,
            )
            if key in existing_keys or not self._mark_inside_ranges(mark, unmarked_ranges, raw_lines):
                skipped += 1
                continue
            existing_keys.add(key)
            added.append(HierarchyMark(
                start_line=mark.start_line,
                end_line=mark.end_line,
                depth=mark.depth,
                type_id=mark.type_id,
                text=mark.text,
                label=mark.label,
                description=mark.description,
                color=mark.color,
                order=self._next_hierarchy_order(),
                start_col=mark.start_col,
                end_col=mark.end_col,
                origin=mark.origin,
                approved=mark.approved,
            ))
        if not added:
            return 0, skipped
        for mark in added:
            self._split_text_marks_around_mark(mark)
            self.hierarchy_marks.append(mark)
        self._auto_join_adjacent_duplicate_structures()
        self._apply_ignore_precedence()
        for mark in added:
            if mark.type_id == HierarchyType.IGNORE:
                self._outline_reveal_keys.update(
                    self._ignore_mark_keys_for_range(mark.start_line, mark.end_line)
                )
            else:
                self._outline_reveal_keys.add(self._hierarchy_mark_key(mark))
        self._refresh()
        self._record_history()
        return len(added), skipped

    def _apply_hierarchy_ai_marks(self, marks: list[HierarchyMark]) -> tuple[int, int]:
        return self._apply_hierarchy_candidate_marks(marks)

    def _on_hierarchy_ai_progress(self, current: int, total: int, scope_label: str):
        status = self._hierarchy_ai_status
        if status is None:
            return
        self._hierarchy_ai_progress_state = (current, total, scope_label)
        if total > 1:
            status.update_progress(max(0, current - 1))
        status.set_detail_text(self._hierarchy_ai_detail_text())
        status.update_step(
            1,
            f"Processing structure {current}/{total}",
            AIStatusDialog.STATUS_IN_PROGRESS,
        )

    def _on_hierarchy_ai_success(self, marks: list, warnings: list, response_text: str):
        self._hierarchy_ai_last_response = response_text
        status = self._hierarchy_ai_status
        if status is not None:
            if status.progress_bar.isVisible():
                status.update_progress(status.progress_bar.maximum())
            status.update_step(1, "AI response received", AIStatusDialog.STATUS_DONE)
            status.update_step(2, "Validated returned JSON", AIStatusDialog.STATUS_DONE)
            status.update_step(3, "Applying hierarchy marks", AIStatusDialog.STATUS_IN_PROGRESS)
        added, skipped = self._apply_hierarchy_ai_marks(marks)
        if status is not None:
            status.update_step(3, "Applied hierarchy marks", AIStatusDialog.STATUS_DONE)
            status.update_step(4, "Updated script tree and preview", AIStatusDialog.STATUS_DONE)
            status.finish(success=True, show_popup=False)

        details = [f"Added {added} hierarchy marks."]
        if skipped:
            details.append(f"Skipped {skipped} marks outside unmarked ranges or duplicates.")
        if warnings:
            details.append("")
            details.append("Warnings:")
            details.extend(f"- {warning}" for warning in warnings[:8])
            if len(warnings) > 8:
                details.append(f"- ...and {len(warnings) - 8} more.")
        QMessageBox.information(self, tr('AI markup finished'), "\n".join(details))

    def _on_hierarchy_ai_error(self, message: str):
        status = self._hierarchy_ai_status
        if status is not None:
            status.update_step(2, "AI response could not be used", AIStatusDialog.STATUS_ERROR)
            status.finish(success=False, show_popup=False)
        QMessageBox.warning(self, tr('AI markup failed'), message or "AI markup failed.")

    def _cancel_hierarchy_ai_markup(self):
        if self._hierarchy_ai_prepare_worker is not None:
            self._hierarchy_ai_prepare_worker.cancel()
        if self._hierarchy_ai_worker is not None:
            self._hierarchy_ai_worker.cancel()

    def _on_hierarchy_ai_thread_finished(self):
        self._hierarchy_ai_elapsed_timer.stop()
        if self._hierarchy_ai_status is not None and self._hierarchy_ai_status.is_running:
            self._hierarchy_ai_status.finish(success=False, show_popup=False)
        self._hierarchy_ai_thread = None
        self._hierarchy_ai_worker = None
        self._hierarchy_ai_status = None
        self._hierarchy_ai_started_at = None
        self._hierarchy_ai_progress_state = None
        self._hierarchy_ai_provider = None
        self._hierarchy_ai_model_name = ""
        self._set_hierarchy_ai_actions_enabled(True)
