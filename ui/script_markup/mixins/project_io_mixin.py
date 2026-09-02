"""Project/template/recipe IO, export, progress, and autosave tick."""
from __future__ import annotations

import os
import json
import copy
from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox, QTreeWidgetItem,
)
from PyQt6.QtCore import QPoint
from core.script_markup import (
    HierarchyMark, HierarchyType,
)
from core.script_markup.markup_recipe import MarkupRecipe
from core.script_markup.hierarchy_ai_jobs import (
    HIERARCHY_PROJECT_FORMAT as _HIERARCHY_PROJECT_FORMAT,
)
from utils.logging_utils import log_info
from core.i18n import tr

from ui.script_markup.constants import (
    _OUTLINE_MARK_KEY_ROLE,
    _HIERARCHY_TEMPLATE_FORMAT,
)


class ProjectIoMixin:
    """Project/template/recipe IO, export, progress, and autosave tick."""

    def _write_json_payload(self, title: str, default_name: str, payload: dict) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, "JSON (*.json)")
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self._last_json_payload_path = str(Path(path).resolve())
            log_info(f"ScriptMarkupStudio: saved {payload.get('format', 'json')} to {path}")
            QMessageBox.information(self, tr('Saved'), f"Saved to:\n{path}")
            return True
        except Exception as e:
            QMessageBox.warning(self, tr('Save failed'), f"Could not write file:\n{e}")
            return False

    def _save_hierarchy_project(self):
        self._refresh()
        saved = self._write_json_payload(
            "Save markup project",
            self._default_hierarchy_project_save_path(),
            self._hierarchy_project_payload(),
        )
        if saved:
            self._publish_active_hierarchy_project_path(
                self._last_json_payload_path, apply_to_mempalace=True
            )
            self._last_saved_state = copy.deepcopy(self._history_snapshot())
            self._is_autosaved_dirty = False
            self._update_save_status()
        return saved

    def _finish_markup_for_mempalace(self) -> bool:
        """Accept all completed marks and save one import-ready project snapshot."""
        self._refresh()
        unmarked = self._unmarked_ranges(self.raw_edit.toPlainText().splitlines())
        if unmarked:
            QMessageBox.warning(
                self,
                tr('Markup is not complete'),
                f"There are still {len(unmarked)} unmarked text ranges. "
                "Finish or ignore them before preparing the project for MemPalace.",
            )
            return False

        pending = [mark for mark in self.hierarchy_marks if not mark.approved]
        if pending:
            reply = QMessageBox.question(
                self,
                tr('Finish markup for MemPalace?'),
                f"This will accept {len(pending)} visible Auto-fill nodes as correct "
                "and save the complete project for MemPalace. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            for mark in pending:
                mark.approved = True
            self._refresh()
            self._record_history()

        return self._save_hierarchy_project()

    def _default_hierarchy_project_save_path(self) -> str:
        if self.current_hierarchy_project_path:
            return self.current_hierarchy_project_path
        if self.current_raw_path:
            return str(Path(self.current_raw_path).with_name("script_markup_project.json"))
        project_manager = getattr(self.mw, "project_manager", None)
        project_dir = getattr(project_manager, "project_dir", "")
        if isinstance(project_dir, (str, os.PathLike)) and str(project_dir):
            return str(Path(project_dir) / "script_markup_project.json")
        return "script_markup_project.json"

    def _save_hierarchy_template(self):
        self._refresh()
        return self._write_json_payload(
            "Save template",
            "script_markup_template.json",
            self._hierarchy_template_payload(),
        )

    def _read_json_payload(self, title: str) -> dict | None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", "JSON (*.json)")
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Top-level JSON value must be an object.")
            self._last_json_payload_path = str(Path(path).resolve())
            return data
        except Exception as e:
            QMessageBox.warning(self, tr('Load failed'), f"Could not read file:\n{e}")
            return None

    def _apply_hierarchy_project_payload(self, data: dict) -> bool:
        if data.get("format") != _HIERARCHY_PROJECT_FORMAT:
            QMessageBox.warning(self, tr('Load failed'), tr('This is not a hierarchy markup project.'))
            return False
        self._set_history_suspended(True)
        try:
            self._switch_to_hierarchy_mode()
            self._apply_hierarchy_type_payload(data.get("type_definitions", []))
            marks = [
                self._hierarchy_mark_from_dict(item)
                for item in data.get("hierarchy_marks", [])
                if isinstance(item, dict)
            ]
            for idx, mark in enumerate(marks, start=1):
                if mark.order <= 0:
                    mark.order = idx
            self.hierarchy_marks = marks
            self._hierarchy_mark_order = max((mark.order for mark in marks), default=0)
            self.manual_marks = {}
            self.current_raw_path = str(data.get("source_path") or "")
            self.path_label.setText(self.current_raw_path or "Opened markup project")
            self._stop_range_edit()
            self.raw_edit.setUpdatesEnabled(False)
            self.raw_edit.setPlainText(str(data.get("raw_text") or ""))
            self.raw_edit.setUpdatesEnabled(True)
            self._debounce.stop()
            self._reset_search_state(clear_highlight=True)
            self._refresh()
        finally:
            self.raw_edit.setUpdatesEnabled(True)
            self._set_history_suspended(False)
        self._record_history()
        return True

    def _load_hierarchy_project(self):
        data = self._read_json_payload("Open markup project")
        if data is None:
            return False
        loaded = self._apply_hierarchy_project_payload(data)
        if loaded:
            self._publish_active_hierarchy_project_path(self._last_json_payload_path)
            self._last_saved_state = copy.deepcopy(self._history_snapshot())
            self._is_autosaved_dirty = False
            self._update_save_status()
        return loaded

    def open_hierarchy_project_at_line(
        self,
        project_path: str,
        line_index: int,
        column: int | None = None,
    ) -> bool:
        """Open the Builder's markup project and reveal one zero-based source line."""
        try:
            resolved = str(Path(project_path).resolve())
            target_line = int(line_index)
        except (TypeError, ValueError, OSError):
            return False
        if target_line < 0 or not Path(resolved).is_file():
            return False

        current = str(Path(self.current_hierarchy_project_path).resolve()) \
            if self.current_hierarchy_project_path else ""
        if current and os.path.normcase(current) != os.path.normcase(resolved):
            reply = QMessageBox.question(
                self,
                tr('Open another markup project?'),
                tr("Markup Studio currently has another project open. Opening the Builder's project will replace the current editor contents. Continue?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if os.path.normcase(current) != os.path.normcase(resolved):
            try:
                with open(resolved, "r", encoding="utf-8") as project_file:
                    data = json.load(project_file)
                if not isinstance(data, dict) or not self._apply_hierarchy_project_payload(data):
                    return False
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                QMessageBox.warning(
                    self,
                    tr('Could not open markup project'),
                    f"The Builder project could not be opened:\n{exc}",
                )
                return False
            self._last_json_payload_path = resolved
            self._publish_active_hierarchy_project_path(resolved)

        self._jump_raw_line_to_outline(target_line, column)
        return self._jump_to_line_no(target_line + 1)

    def assign_speaker_at_line(
        self,
        project_path: str,
        line_index: int,
        speaker_name: str,
    ) -> bool:
        """Change the owning speaker of one marked dialogue and save immediately."""
        speaker_name = str(speaker_name or "").strip()
        if not speaker_name or speaker_name.casefold() == "none":
            return False
        if not self.open_hierarchy_project_at_line(project_path, line_index):
            return False

        ordered = sorted(
            self.hierarchy_marks,
            key=lambda mark: (
                mark.start_line,
                mark.start_col if mark.start_col is not None else -1,
                mark.depth,
                -mark.end_line,
                mark.order,
            ),
        )
        target = next(
            (
                mark for mark in ordered
                if mark.type_id == HierarchyType.TEXT
                and mark.start_line <= line_index <= mark.end_line
            ),
            None,
        )
        if target is None:
            return False

        stack: dict[int, HierarchyMark] = {}
        owner = None
        for mark in ordered:
            if mark is target:
                owner = next(
                    (
                        stack[depth]
                        for depth in range(target.depth - 1, -1, -1)
                        if depth in stack
                        and stack[depth].type_id == HierarchyType.SPEAKER
                    ),
                    None,
                )
                break
            stack[mark.depth] = mark
            for depth in tuple(stack):
                if depth > mark.depth:
                    del stack[depth]
        if owner is None:
            return False

        owner.text = speaker_name
        owner.label = ""
        owner.origin = "speaker_assignment"
        self._refresh()
        self._record_history()
        try:
            resolved = str(Path(project_path).resolve())
            with open(resolved, "w", encoding="utf-8") as project_file:
                json.dump(
                    self._hierarchy_project_payload(),
                    project_file,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError as exc:
            QMessageBox.warning(self, tr('Save failed'), f"Could not update the project:\n{exc}")
            return False
        self._last_json_payload_path = resolved
        self._last_saved_state = copy.deepcopy(self._history_snapshot())
        self._is_autosaved_dirty = False
        self._update_save_status()
        self._publish_active_hierarchy_project_path(
            resolved, apply_to_mempalace=True
        )
        return True

    def _publish_active_hierarchy_project_path(
        self,
        path: str,
        *,
        apply_to_mempalace: bool = False,
    ) -> None:
        resolved = str(Path(path).resolve()) if path else ""
        self.current_hierarchy_project_path = resolved
        if hasattr(self, "project_state_label"):
            self.project_state_label.setText(
                f"Markup project: {resolved}" if resolved else "Markup project: Not saved"
            )
        if self.mw is None:
            return
        setattr(self.mw, "script_markup_studio_project_path", resolved)
        builder = getattr(self.mw, "mempalace_builder_dialog", None)
        if apply_to_mempalace:
            apply_saved = getattr(builder, "apply_saved_markup_studio_project", None)
            if resolved and callable(apply_saved):
                apply_saved(resolved)
        refresh = getattr(builder, "_load_active_markup_studio_project", None)
        if resolved and callable(refresh):
            refresh()

    def _apply_hierarchy_template_payload(self, data: dict) -> bool:
        if data.get("format") != _HIERARCHY_TEMPLATE_FORMAT:
            QMessageBox.warning(self, tr('Load failed'), tr('This is not a hierarchy template.'))
            return False
        self._set_history_suspended(True)
        try:
            self._switch_to_hierarchy_mode()
            self._apply_hierarchy_type_payload(data.get("type_definitions", []))
            self._refresh()
        finally:
            self._set_history_suspended(False)
        self._record_history()
        return True

    def _load_hierarchy_template(self):
        data = self._read_json_payload("Open template")
        if data is None:
            return False
        return self._apply_hierarchy_template_payload(data)

    def _default_export_name(self) -> str:
        try:
            if self.mw.current_game_rules:
                name = self.mw.current_game_rules.get_display_name()
                clean = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()
                return f"{clean}_script.md"
        except Exception:
            pass
        return "game_script.md"

    def _export(self):
        if not (self._psm_text or "").strip():
            QMessageBox.information(self, tr('Nothing to export'), tr('Load and mark up a script first.'))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export standardized script", self._default_export_name(),
            "Markdown script (*.md);;Text (*.txt)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._psm_text)
            QMessageBox.information(self, tr('Exported'), f"Saved standardized script to:\n{path}")
            log_info(f"ScriptMarkupStudio: exported standardized script to {path}")
        except Exception as e:
            QMessageBox.warning(self, tr('Export failed'), f"Could not write file:\n{e}")

    def _save_recipe(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save recipe", "markup_recipe.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.recipe.to_dict(), f, indent=2, ensure_ascii=False)
            log_info(f"ScriptMarkupStudio: saved recipe to {path}")
        except Exception as e:
            QMessageBox.warning(self, tr('Save failed'), f"Could not write recipe:\n{e}")

    def _load_recipe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load recipe", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.recipe = MarkupRecipe.from_dict(data)
            self.cb_gutter.blockSignals(True)
            self.cb_continuation.blockSignals(True)
            try:
                self.cb_gutter.setChecked(self.recipe.gutter_speakers)
                self.cb_continuation.setChecked(self.recipe.continuation)
            finally:
                self.cb_gutter.blockSignals(False)
                self.cb_continuation.blockSignals(False)
            self._refresh()
            self._record_history()
        except Exception as e:
            QMessageBox.warning(self, tr('Load failed'), f"Could not read recipe:\n{e}")

    def _quick_save_project(self) -> bool:
        self._refresh()
        if self.current_hierarchy_project_path:
            try:
                payload = self._hierarchy_project_payload()
                with open(self.current_hierarchy_project_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                self._last_json_payload_path = self.current_hierarchy_project_path
                self._last_saved_state = copy.deepcopy(self._history_snapshot())
                self._is_autosaved_dirty = False
                self._update_save_status()
                log_info(f"ScriptMarkupStudio: quick saved project to {self.current_hierarchy_project_path}")
                return True
            except Exception as e:
                QMessageBox.warning(self, tr('Save failed'), f"Could not write file:\n{e}")
                return False
        else:
            return self._save_hierarchy_project()

    def _set_rules_mode(self, mode: str):
        self.mode = mode
        self._on_mode_changed()

    def _toggle_legacy_controls(self, checked: bool):
        self.show_legacy_controls_action.setChecked(checked)
        self._update_mode_controls()

    def _update_progress_and_next_action(self):
        if not hasattr(self, "stage_source_label"):
            return

        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()

        has_source = bool(raw_text.strip())
        has_approved = any(mark.approved for mark in self.hierarchy_marks)
        unapproved_marks = [mark for mark in self.hierarchy_marks if not mark.approved]
        unmarked_ranges = self._unmarked_ranges(raw_lines)

        review_complete = has_approved and not unapproved_marks
        markup_complete = review_complete and not unmarked_ranges

        # 1. Update Progress Bar
        if has_source:
            self.stage_source_label.setText(tr('1. Source ✓'))
            self.stage_source_label.setStyleSheet("color: #107c41;")
        else:
            self.stage_source_label.setText(tr('1. Source'))
            self.stage_source_label.setStyleSheet("color: #0f6cbd;")

        if has_approved:
            self.stage_markup_label.setText(tr('2. Markup ✓'))
            self.stage_markup_label.setStyleSheet("color: #107c41;")
        elif has_source:
            self.stage_markup_label.setText(tr('2. Markup'))
            self.stage_markup_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_markup_label.setText(tr('2. Markup'))
            self.stage_markup_label.setStyleSheet("color: #8a8a8a;")

        if review_complete:
            self.stage_review_label.setText(tr('3. Review ✓'))
            self.stage_review_label.setStyleSheet("color: #107c41;")
        elif has_approved:
            self.stage_review_label.setText(tr('3. Review'))
            self.stage_review_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_review_label.setText(tr('3. Review'))
            self.stage_review_label.setStyleSheet("color: #8a8a8a;")

        is_project_saved = self.current_hierarchy_project_path and (self._last_saved_state is not None and self._history_snapshot() == self._last_saved_state)
        if markup_complete and is_project_saved:
            self.stage_mempalace_label.setText(tr('4. MemPalace ✓'))
            self.stage_mempalace_label.setStyleSheet("color: #107c41;")
        elif markup_complete:
            self.stage_mempalace_label.setText(tr('4. MemPalace'))
            self.stage_mempalace_label.setStyleSheet("color: #0f6cbd;")
        else:
            self.stage_mempalace_label.setText(tr('4. MemPalace'))
            self.stage_mempalace_label.setStyleSheet("color: #8a8a8a;")

        # 2. Update Next Action
        self.next_action_secondary_btn.setVisible(False)
        self.next_action_btn.setEnabled(True)

        if not has_source:
            self.next_action_desc_label.setText(tr('No script or project loaded yet. Load your walkthrough script to begin.'))
            self.next_action_btn.setText(tr('Open Script or Project…'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif not has_approved:
            self.next_action_desc_label.setText(tr('Please mark at least one text selection manually to create an example for Auto-fill.'))
            self.next_action_btn.setText(tr('Mark the First Example'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif unmarked_ranges and not unapproved_marks:
            self.next_action_desc_label.setText(tr('You have marked examples. You can now use Auto-fill to analyze remaining text ranges locally or with AI.'))
            self.next_action_btn.setText(tr('Continue from My Examples'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
            self.next_action_secondary_btn.setText(tr('AI Fill Remaining…'))
            self.next_action_secondary_btn.setVisible(True)
        elif unapproved_marks:
            self.next_action_desc_label.setText(f"Auto-fill has suggested {len(unapproved_marks)} marks. Please review, approve, or correct them.")
            self.next_action_btn.setText(tr('Review Suggestions →'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif unmarked_ranges:
            self.next_action_desc_label.setText(f"There are still {len(unmarked_ranges)} unmarked text ranges. Focus and resolve them.")
            self.next_action_btn.setText(tr('Go to Next Unmarked Range →'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #115ea3; }"
            )
        elif markup_complete and not is_project_saved:
            self.next_action_desc_label.setText(tr('Markup complete — all nodes approved, no unmarked text. Save the project and transfer context to MemPalace.'))
            self.next_action_btn.setText(tr('Save and Continue to MemPalace →'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #107c41; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #138a49; }"
            )
        else:
            self.next_action_desc_label.setText(tr('Markup complete and project successfully saved. You can proceed directly to MemePalace Builder.'))
            self.next_action_btn.setText(tr('Open MemPalace Builder →'))
            self.next_action_btn.setStyleSheet(
                "QPushButton { background: #107c41; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 6px 16px; min-height: 28px; }"
                "QPushButton:hover { background: #138a49; }"
            )

    def _on_next_action_clicked(self):
        raw_text = self.raw_edit.toPlainText()
        raw_lines = raw_text.splitlines()

        has_source = bool(raw_text.strip())
        has_approved = any(mark.approved for mark in self.hierarchy_marks)
        unapproved_marks = [mark for mark in self.hierarchy_marks if not mark.approved]
        unmarked_ranges = self._unmarked_ranges(raw_lines)

        review_complete = has_approved and not unapproved_marks
        markup_complete = review_complete and not unmarked_ranges

        if not has_source:
            self.file_menu.exec(self.next_action_btn.mapToGlobal(QPoint(0, self.next_action_btn.height())))
        elif not has_approved:
            QMessageBox.information(
                self,
                tr('Mark the First Example'),
                tr("To get started:\n\n1. Select a block of text in the 'Raw script' editor on the left.\n2. Press Ctrl+M (or right-click and select 'Apply mark') to create your first approved hierarchy node.\n3. Repeat this for a couple of different examples (e.g. Dialogue, Actions, Chapters) so the Auto-fill engine can learn from them.")
            )
        elif unmarked_ranges and not unapproved_marks:
            self._continue_hierarchy_from_examples()
        elif unapproved_marks:
            unapproved_marks.sort(key=lambda m: m.start_line)
            first = unapproved_marks[0]
            self._jump_to_line_no(first.start_line)

            item = self._find_tree_item_by_mark_key(first.key)
            if item:
                self.flags_list.clearSelection()
                item.setSelected(True)
                self.flags_list._set_current_without_selection_change(item)
                self.flags_list.scrollToItem(item)
        elif unmarked_ranges:
            cursor = self.raw_edit.textCursor()
            curr_line = cursor.blockNumber()

            target_range = None
            for start, end in unmarked_ranges:
                if start >= curr_line:
                    target_range = (start, end)
                    break
            if not target_range and unmarked_ranges:
                target_range = unmarked_ranges[0]

            if target_range:
                self._jump_to_line_no(target_range[0] + 1)
        elif markup_complete and not (self.current_hierarchy_project_path and self._last_saved_state is not None and self._history_snapshot() == self._last_saved_state):
            saved = self._finish_markup_for_mempalace()
            if saved and self.mw is not None:
                self.mw.actions.open_mempalace_builder()
        else:
            if self.mw is not None:
                self.mw.actions.open_mempalace_builder()

    def _find_tree_item_by_mark_key(self, mark_key: str) -> QTreeWidgetItem | None:
        def walk(item):
            if item.data(0, _OUTLINE_MARK_KEY_ROLE) == mark_key:
                return item
            for i in range(item.childCount()):
                res = walk(item.child(i))
                if res:
                    return res
            return None

        for i in range(self.flags_list.topLevelItemCount()):
            res = walk(self.flags_list.topLevelItem(i))
            if res:
                return res
        return None

    def _update_save_status(self):
        if not hasattr(self, "save_status_label"):
            return

        current_state = self._history_snapshot()

        if not self.current_hierarchy_project_path:
            if self._is_autosaved_dirty:
                self.save_status_label.setText(tr('Unsaved changes *'))
                self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #d83b01;")
            else:
                self.save_status_label.setText(tr('Autosaved'))
                self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #8a8a8a;")
            return

        is_saved = False
        if self._last_saved_state is not None:
            is_saved = (current_state == self._last_saved_state)

        if is_saved:
            self.save_status_label.setText(tr('Project saved ✓'))
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #107c41;")
        elif self._is_autosaved_dirty:
            self.save_status_label.setText(tr('Unsaved changes *'))
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #d83b01;")
        else:
            self.save_status_label.setText(tr('Autosaved'))
            self.save_status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0f6cbd;")

    def _autosave_session_tick(self):
        saved = self._save_autosaved_session()
        if saved:
            self._is_autosaved_dirty = False
            self._update_save_status()
