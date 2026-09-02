"""Dialogue mapping / review mixin for MemePalaceBuilderDialog."""
import html
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import pyqtSlot

from core.mempalace.dialogue_alignment import GameMessage
from core.mempalace.dialogue_mapping import DialogueMappingInput
from core.mempalace.dialogue_mapping_worker import DialogueAlignmentWorker
from ui.mempalace.mempalace_ui import SECONDARY_BUTTON_STYLE, WORKFLOW_BUTTON_STYLE
from core.i18n import tr


class MemePalaceDialogueMixin:
    """Dialogue node matching, review table, approve/reject, Markup Studio jump."""

    def _game_messages_for_story_alignment(self, data) -> list[GameMessage]:
        """Build alignment inputs while honoring plugin window-type exclusions."""
        game_messages = []
        store = getattr(self.mw, "data_store", None)
        block_names = getattr(store, "block_names", {}) or {}
        rules = getattr(self.mw, "current_game_rules", None)
        eligible = getattr(rules, "should_auto_match_story_context", None)
        for block_index, block in enumerate(data):
            if not isinstance(block, list):
                continue
            try:
                block_name = str(self.composer._get_block_label(block_index))
            except Exception:
                block_name = str(
                    block_names.get(
                        str(block_index),
                        block_names.get(block_index, f"Block_{block_index}"),
                    )
                )
            for string_index, value in enumerate(block):
                text = str(value or "")
                if not text.strip():
                    continue
                if callable(eligible):
                    try:
                        if eligible(block_index, string_index) is False:
                            continue
                    except Exception:
                        pass
                game_messages.append(GameMessage(
                    message_id=len(game_messages),
                    block_id=str(block_index),
                    block_name=block_name,
                    string_index=string_index,
                    stable_id=f"{block_name}_Str_{string_index}",
                    text=text,
                ))
        return game_messages

    @pyqtSlot()
    def _start_dialogue_node_mapping(self) -> None:
        if self.story_document_id is None:
            QMessageBox.warning(
                self,
                tr('Story tree required'),
                tr('Import a Markup Studio Project before matching game strings.'),
            )
            return
        store = getattr(self.mw, "data_store", None)
        data = getattr(store, "data", None)
        if not isinstance(data, list) or not data:
            QMessageBox.warning(self, tr('Open project required'), tr('Open a game project first.'))
            return
        game_messages = self._game_messages_for_story_alignment(data)
        if not game_messages:
            QMessageBox.information(
                self, tr('Nothing to match'), tr('The open project has no eligible dialogue strings.')
            )
            return

        self.match_dialogue_btn.setEnabled(False)
        self.dialogue_mapping_progress.setRange(0, 0)
        self.dialogue_mapping_progress.setVisible(True)
        self.dialogue_mapping_summary_label.setText(
            tr('Aligning marked dialogue with the open game project…')
        )
        self.worker = DialogueAlignmentWorker(
            self.client,
            self.story_document_id,
            game_messages,
            parent=self,
        )
        self.worker.completed.connect(self._handle_dialogue_mapping_completed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    @pyqtSlot(int, int)
    def _handle_dialogue_mapping_progress(self, current: int, total: int) -> None:
        self.dialogue_mapping_progress.setRange(0, total)
        self.dialogue_mapping_progress.setValue(current)

    @pyqtSlot(bool, object, str)
    def _handle_dialogue_mapping_completed(self, success: bool, summary, error: str) -> None:
        self.worker = None
        self.dialogue_mapping_progress.setVisible(False)
        self.match_dialogue_btn.setEnabled(True)
        if not success:
            self.dialogue_mapping_summary_label.setText(error or "Matching stopped.")
            self.dialogue_mapping_summary_label.setStyleSheet("color: #a80000;")
            if error and "cancelled" not in error.lower():
                QMessageBox.warning(self, tr('Dialogue matching failed'), error)
            return
        spoken = summary["spoken_only"]
        coverage = spoken["supported_relation_coverage"]
        review_count = len(self.client.get_dialogue_mappings(
            self.story_document_id, review_status="needs_review"
        ))
        self.dialogue_mapping_summary_label.setText(
            f"Marked dialogue coverage: {coverage:.1f}% "
            f"({spoken['confident_tokens']} directly confirmed tokens; "
            f"{spoken['recoverable_tokens']} found with candidates). "
            f"Saved context links: {summary.get('saved_relations', 0)}. "
            f"Need your decision: {review_count}. "
            f"Stage directions kept separate: {summary['stage_direction_nodes']}. "
            f"Tag meanings inferred: {len(summary['inferred_tag_equivalents'])}."
        )
        color = "#107c41" if coverage >= 95.0 else "#a15c00"
        self.dialogue_mapping_summary_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self._refresh_dialogue_review_table()
        self._set_saved_dialogue_search_actions(review_count == 0)
        self._refresh_main_story_folders()
        updater = getattr(self.mw, "string_settings_updater", None)
        if updater is not None:
            updater.update_string_settings_panel()

    def _set_saved_dialogue_search_actions(self, complete: bool) -> None:
        """Make rerunning secondary once durable search results exist."""
        self.match_dialogue_btn.setText(tr('Recheck After Changes'))
        self.match_dialogue_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.story_context_done_btn.setVisible(complete)
        if complete:
            self.story_context_completion_label.setText(
                tr('All context decisions are saved. These links are already available to AI translation; rerun the search only after the script or game text changes.')
            )

    def _restore_dialogue_mapping_state(self) -> None:
        """Restore persisted context-search status when Builder is reopened."""
        if self.story_document_id is None:
            return
        state = self.client.get_dialogue_mapping_state(self.story_document_id)
        if not state.has_results:
            self.match_dialogue_btn.setText(tr('Find Context Automatically'))
            self.match_dialogue_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
            self.story_context_done_btn.setVisible(False)
            return
        self._refresh_dialogue_review_table()
        if state.needs_review:
            self.dialogue_mapping_summary_label.setText(
                f"Saved search restored: {state.automatic} automatically matched; "
                f"{state.reviewed} reviewed; {state.context_links} active context links. "
                f"Need your decision: {state.needs_review}."
            )
            self.dialogue_mapping_summary_label.setStyleSheet(
                "color: #a15c00; font-weight: bold;"
            )
        else:
            self.dialogue_mapping_summary_label.setText(
                f"Story context is ready. Saved results: {state.automatic} automatically "
                f"matched; {state.reviewed} reviewed; "
                f"{state.context_links} active context links."
            )
            self.dialogue_mapping_summary_label.setStyleSheet(
                "color: #107c41; font-weight: bold;"
            )
        self._set_saved_dialogue_search_actions(state.is_complete)

    def _invalidate_dialogue_review_cache(self) -> None:
        self._dialogue_review_cache_document_id = None
        self._dialogue_review_nodes = {}
        self._dialogue_review_dialogues = ()
        self._dialogue_review_index_by_id = {}

    def _ensure_dialogue_review_cache(self):
        if (
            getattr(self, "_dialogue_review_cache_document_id", None)
            == self.story_document_id
        ):
            return self._dialogue_review_nodes
        timeline = self.client.get_story_timeline(self.story_document_id)
        nodes = {node.id: node for node in timeline}
        dialogues = tuple(node for node in timeline if node.node_type == "dialogue")
        self._dialogue_review_cache_document_id = self.story_document_id
        self._dialogue_review_nodes = nodes
        self._dialogue_review_dialogues = dialogues
        self._dialogue_review_index_by_id = {
            node.id: index for index, node in enumerate(dialogues)
        }

        self.mapping_dialogue_combo.blockSignals(True)
        self.mapping_dialogue_combo.clear()
        for node in dialogues:
            speaker, path = self._dialogue_metadata(node, nodes)
            line = node.start_line + 1 if node.start_line is not None else "?"
            text = " ".join((node.text or "(empty dialogue)").split())
            if len(text) > 110:
                text = text[:107] + "…"
            details = " › ".join(path)
            label = f"Line {line} · {speaker}: {text}"
            if details:
                label += f" · {details}"
            self.mapping_dialogue_combo.addItem(label, node.id)
        self.mapping_dialogue_combo.setCurrentIndex(-1)
        self.mapping_dialogue_combo.setEditText("")
        self.mapping_dialogue_combo.blockSignals(False)
        return nodes

    @staticmethod
    def _short_story_node_text(node) -> str:
        value = node.title or node.text or node.node_type.replace("_", " ").title()
        return value.splitlines()[0].strip()

    def _dialogue_metadata(self, dialogue, nodes) -> tuple[str, tuple[str, ...]]:
        speaker = "Unknown speaker"
        structural = []
        current = dialogue
        visited = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            if current.node_type == "speaker":
                speaker = self._short_story_node_text(current)
            elif current.node_type in {"act", tr('chapter'), "scene"}:
                structural.append(self._short_story_node_text(current))
            current = nodes.get(current.parent_id)
        structural.reverse()
        return speaker, tuple(structural)

    def _set_dialogue_candidate(self, candidate) -> None:
        if candidate is None:
            self._current_candidate_node_id = None
            self.mapping_review_candidate_label.setText(tr('No reliable script place selected'))
            self.mapping_review_location_label.setText(
                tr('Choose a marked line below to compare its surrounding dialogue.')
            )
            self.mapping_context_preview.setHtml(
                "<p><b>No context selected.</b></p>"
                "<p>The program could not prove which repeated occurrence is correct. "
                "It has not selected the first occurrence automatically.</p>"
            )
            self.approve_mapping_btn.setEnabled(False)
            self.open_mapping_in_studio_btn.setEnabled(False)
            return

        nodes = self._dialogue_review_nodes
        speaker, path = self._dialogue_metadata(candidate, nodes)
        self._current_candidate_node_id = candidate.id
        self.mapping_review_candidate_label.setText(
            candidate.text or candidate.title or "(empty script line)"
        )
        location_parts = [*path, f"Speaker: {speaker}"]
        if candidate.start_line is not None:
            location_parts.append(f"source line {candidate.start_line + 1}")
        self.mapping_review_location_label.setText(
            "Location: " + " › ".join(location_parts)
        )

        index = self._dialogue_review_index_by_id.get(candidate.id)
        if index is None:
            nearby = (candidate,)
        else:
            nearby = self._dialogue_review_dialogues[
                max(0, index - 2):min(len(self._dialogue_review_dialogues), index + 3)
            ]
        rows = []
        for node in nearby:
            row_speaker, _row_path = self._dialogue_metadata(node, nodes)
            selected = node.id == candidate.id
            background = "#dff0ff" if selected else "transparent"
            marker = "▶ " if selected else ""
            line = node.start_line + 1 if node.start_line is not None else "?"
            text = html.escape(node.text or "(empty dialogue)").replace("\n", "<br>")
            rows.append(
                f'<div style="background:{background}; padding:6px; margin:2px 0;">'
                f'<b>{marker}{html.escape(row_speaker)}</b> '
                f'<span style="color:#666;">(line {line})</span><br>{text}</div>'
            )
        self.mapping_context_preview.setHtml("".join(rows))
        self.approve_mapping_btn.setEnabled(True)
        self.open_mapping_in_studio_btn.setEnabled(candidate.start_line is not None)

    def _refresh_dialogue_review_table(self) -> None:
        if self.story_document_id is None:
            return
        mappings = [
            *self.client.get_dialogue_mappings(
                self.story_document_id, review_status="needs_review"
            ),
        ]
        nodes = self._ensure_dialogue_review_cache()
        self._review_mappings = mappings
        current_index = min(
            getattr(self, "_current_review_index", 0),
            max(0, len(mappings) - 1),
        )
        self._current_review_index = current_index
        self.mapping_review_actions.setVisible(bool(mappings))
        self.story_context_completion_label.setVisible(not mappings)
        self.mapping_review_table.setVisible(False)
        if mappings:
            self._show_dialogue_review(current_index, nodes=nodes)
        else:
            self.approve_mapping_btn.setEnabled(False)
            self.open_mapping_in_studio_btn.setEnabled(False)
            self.mapping_dialogue_choice_widget.setVisible(False)

    def _show_dialogue_review(self, index: int, *, nodes=None) -> None:
        mappings = getattr(self, "_review_mappings", [])
        if not mappings:
            self.approve_mapping_btn.setEnabled(False)
            return
        index = max(0, min(index, len(mappings) - 1))
        self._current_review_index = index
        mapping = mappings[index]
        if nodes is None:
            nodes = self._ensure_dialogue_review_cache()
        candidate = nodes.get(mapping.dialogue_node_id)
        self.mapping_review_counter_label.setText(
            f"Decision {index + 1} of {len(mappings)}"
        )
        self.mapping_review_source_label.setText(mapping.source_text_snapshot or "(empty text)")
        self.mapping_review_explanation_label.setText(
            "The text is similar to this marked line, but the match is not certain."
            if candidate is not None
            else "This text appears in more than one marked place, and its neighbors did not "
                 "prove which occurrence is correct."
        )
        if mapping.dialogue_node_id is not None:
            combo_index = self.mapping_dialogue_combo.findData(mapping.dialogue_node_id)
            if combo_index >= 0:
                self.mapping_dialogue_combo.setCurrentIndex(combo_index)
        else:
            self.mapping_dialogue_combo.setCurrentIndex(-1)
            self.mapping_dialogue_combo.setEditText("")
        self.mapping_dialogue_choice_widget.setVisible(False)
        self._set_dialogue_candidate(candidate)
        self.mapping_review_previous_btn.setEnabled(index > 0)
        self.mapping_review_next_btn.setEnabled(index + 1 < len(mappings))

    @pyqtSlot(int)
    def _on_dialogue_choice_changed(self, _index: int) -> None:
        if not getattr(self, "_review_mappings", []):
            return
        node_id = self.mapping_dialogue_combo.currentData()
        if not isinstance(node_id, int):
            self._set_dialogue_candidate(None)
            return
        nodes = self._ensure_dialogue_review_cache()
        candidate = nodes.get(node_id)
        self._set_dialogue_candidate(candidate)

    @pyqtSlot()
    def _show_dialogue_candidate_picker(self) -> None:
        self.mapping_dialogue_choice_widget.setVisible(True)
        if self.mapping_dialogue_combo.currentIndex() < 0:
            mappings = getattr(self, "_review_mappings", [])
            index = getattr(self, "_current_review_index", 0)
            if 0 <= index < len(mappings):
                self.mapping_dialogue_combo.setEditText(
                    mappings[index].source_text_snapshot
                )
        self.mapping_dialogue_combo.setFocus()
        if self.mapping_dialogue_combo.lineEdit() is not None:
            self.mapping_dialogue_combo.lineEdit().selectAll()
        self.mapping_dialogue_combo.completer().complete()

    @pyqtSlot()
    def _open_current_dialogue_in_markup_studio(self) -> None:
        node_id = getattr(self, "_current_candidate_node_id", None)
        node = self._dialogue_review_nodes.get(node_id)
        if node is None or node.start_line is None:
            QMessageBox.information(
                self,
                tr('Choose a script place'),
                tr('Choose a marked script line before opening Markup Studio.'),
            )
            return
        actions = getattr(self.mw, "actions", None)
        open_studio = getattr(actions, "open_script_markup_studio", None)
        if not callable(open_studio):
            QMessageBox.warning(
                self, tr('Markup Studio unavailable'), tr('Could not open Script Markup Studio.')
            )
            return
        open_studio()
        studio = getattr(self.mw, "script_markup_studio_dialog", None)
        navigate = getattr(studio, "open_hierarchy_project_at_line", None)
        project_path = self.hierarchy_project_path_edit.text().strip()
        if studio is None or not callable(navigate) or not navigate(
            project_path, node.start_line
        ):
            QMessageBox.warning(
                self,
                tr('Could not show script line'),
                tr('Markup Studio opened, but the selected source line could not be shown.'),
            )
            return
        studio.show()
        studio.raise_()
        studio.activateWindow()

    @pyqtSlot()
    def _show_previous_dialogue_review(self) -> None:
        self._show_dialogue_review(getattr(self, "_current_review_index", 0) - 1)

    @pyqtSlot()
    def _show_next_dialogue_review(self) -> None:
        self._show_dialogue_review(getattr(self, "_current_review_index", 0) + 1)

    @pyqtSlot(bool)
    def _toggle_story_structure(self, checked: bool) -> None:
        self.story_group.setVisible(checked)
        if checked:
            self.chapters_splitter.setSizes(
                getattr(self, "_saved_chapters_splitter_sizes", [390, 260])
            )
        self.toggle_story_btn.setText(
            "Hide imported structure" if checked else "Show imported structure"
        )

    @pyqtSlot()
    def _approve_selected_dialogue_mapping(self) -> None:
        mappings = getattr(self, "_review_mappings", [])
        index = getattr(self, "_current_review_index", 0)
        if index < 0 or index >= len(mappings):
            return
        dialogue_node_id = self.mapping_dialogue_combo.currentData()
        if not isinstance(dialogue_node_id, int):
            return
        mapping = mappings[index]
        self.client.upsert_dialogue_mapping(
            DialogueMappingInput(
                document_id=mapping.document_id,
                game_block_id=mapping.game_block_id,
                game_block_name=mapping.game_block_name,
                string_index=mapping.string_index,
                game_string_id=mapping.game_string_id,
                source_text_snapshot=mapping.source_text_snapshot,
                dialogue_node_id=dialogue_node_id,
                match_method="manual",
                confidence=1.0,
                review_status="approved",
                reviewed_by="user",
                locked=True,
            ),
            allow_locked_override=True,
        )
        self.client.lock_dialogue_relation_choice(
            mapping.document_id,
            mapping.game_block_id,
            mapping.string_index,
            dialogue_node_id,
        )
        self._restore_dialogue_mapping_state()
        self._refresh_main_story_folders()

    @pyqtSlot()
    def _reject_selected_dialogue_mapping(self) -> None:
        mappings = getattr(self, "_review_mappings", [])
        index = getattr(self, "_current_review_index", 0)
        if index < 0 or index >= len(mappings):
            return
        mapping = mappings[index]
        self.client.upsert_dialogue_mapping(
            DialogueMappingInput(
                document_id=mapping.document_id,
                game_block_id=mapping.game_block_id,
                game_block_name=mapping.game_block_name,
                string_index=mapping.string_index,
                game_string_id=mapping.game_string_id,
                source_text_snapshot=mapping.source_text_snapshot,
                dialogue_node_id=None,
                match_method="manual",
                confidence=1.0,
                review_status="rejected",
                reviewed_by="user",
                locked=True,
            ),
            allow_locked_override=True,
        )
        self.client.lock_dialogue_relation_choice(
            mapping.document_id,
            mapping.game_block_id,
            mapping.string_index,
            None,
        )
        self._restore_dialogue_mapping_state()
        self._refresh_main_story_folders()

