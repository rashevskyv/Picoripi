"""Tooltips, classified overlays, file load, and mode controls."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)
from core.script_markup import (
    LineKind,
    HierarchyMark, HierarchyType, build_hierarchy_tree,
)
from utils.logging_utils import log_info, log_error
from core.i18n import tr

from ui.script_markup.constants import (
    _KIND_TITLES,
)


class OverlayMixin:
    """Tooltips, classified overlays, file load, and mode controls."""

    def _tooltip_for_raw_position(self, pos) -> str:
        block = self.raw_edit.cursorForPosition(pos).block()
        if not block.isValid():
            return ""
        idx = block.blockNumber()
        if self.mode == "hierarchy":
            return self._hierarchy_tooltip_for_line(idx)

        kind = self.highlighter.line_kinds.get(idx)
        if not kind or kind == LineKind.BLANK:
            return ""

        label = _KIND_TITLES.get(kind, str(kind).title())
        lines = [f"Marked as {label}"]
        speaker = self.highlighter.line_speakers.get(idx)
        if speaker:
            lines.append(f"Speaker: {speaker}")
        if idx in self.manual_marks:
            lines.append("Manual mark")
        return "\n".join(lines)

    def _hierarchy_tooltip_for_line(self, idx: int) -> str:
        marks = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= idx <= mark.end_line
        ]
        if not marks:
            block = self.raw_edit.document().findBlockByNumber(idx)
            if block.isValid() and block.text().strip():
                path = self._hierarchy_path_for_line(idx)
                lines = [
                    "Type: Unmarked",
                    f"Range: line {idx + 1}",
                    "This line still needs a hierarchy decision.",
                ]
                if path:
                    lines.append("Hierarchy:")
                    lines.extend(f"  {entry}" for entry in path)
                return "\n".join(lines)
            return ""
        mark = max(marks, key=lambda m: (m.depth, m.start_line, -m.end_line, m.order))
        type_def = self.hierarchy_type_definitions.get(mark.type_id)
        label = type_def.label if type_def else str(mark.type_id).title()
        lines = [
            f"Type: {label}",
            f"Depth: {mark.depth}",
            f"Range: lines {mark.start_line + 1}-{mark.end_line + 1}",
        ]
        if type_def and type_def.description:
            lines.append(type_def.description)
        path = self._hierarchy_path_for_line(idx)
        if path:
            lines.append("Hierarchy:")
            lines.extend(f"  {entry}" for entry in path)
        return "\n".join(lines)

    def _hierarchy_path_for_line(self, idx: int) -> list[str]:
        candidates = [
            mark for mark in self.hierarchy_marks
            if mark.start_line <= idx <= mark.end_line
            and mark.type_id not in (HierarchyType.IGNORE, HierarchyType.UNMARKED)
        ]
        if not candidates:
            return []

        # A line range is only visual/source coverage, not parentage. Ranges of
        # sibling structures can overlap after manual edits, so collecting every
        # covering mark invents paths that do not exist in the outline. Select the
        # actual node at this position, then read its real parent chain from the
        # same depth/source-order tree used by the outline.
        target = max(
            candidates,
            key=lambda mark: (mark.depth, mark.start_line, -mark.end_line, mark.order),
        )
        marks = list(
            self._hierarchy_paths_by_key().get(self._hierarchy_mark_key(target), ())
        )
        if not marks:
            return []

        path: list[str] = []
        for mark in marks:
            type_def = self.hierarchy_type_definitions.get(mark.type_id)
            label = type_def.label if type_def else str(mark.type_id).title()
            title = self._hierarchy_mark_display_text(mark, limit=48)
            suffix = f": {title}" if title else ""
            path.append(f"[{mark.depth}] {label}{suffix}")
        return path

    def _hierarchy_paths_by_key(self) -> dict[str, tuple[HierarchyMark, ...]]:
        if self._hierarchy_paths_by_key_cache is not None:
            return self._hierarchy_paths_by_key_cache

        paths: dict[str, tuple[HierarchyMark, ...]] = {}
        root = build_hierarchy_tree(self.hierarchy_marks)

        def visit(node, parents: tuple[HierarchyMark, ...]):
            mark = node.mark
            current = parents if mark is None else (*parents, mark)
            if mark is not None:
                paths[self._hierarchy_mark_key(mark)] = current
            for child in node.children:
                visit(child, current)

        visit(root, ())
        self._hierarchy_paths_by_key_cache = paths
        return paths

    def _manual_action_groups(self, raw_lines: list[str], base_offset: int = 0) -> tuple[dict[int, str], set[int]]:
        first_text: dict[int, str] = {}
        skip: set[int] = set()
        i = 0
        while i < len(raw_lines):
            idx = base_offset + i
            mark = self.manual_marks.get(idx)
            if not mark or mark.get("kind") != LineKind.ACTION:
                i += 1
                continue

            group = [i]
            j = i + 1
            while j < len(raw_lines):
                next_mark = self.manual_marks.get(base_offset + j)
                if not next_mark or next_mark.get("kind") != LineKind.ACTION:
                    break
                group.append(j)
                j += 1

            text = self._clean_mark_text(" ".join(raw_lines[g] for g in group))
            first_text[base_offset + group[0]] = text
            skip.update(base_offset + g for g in group[1:])
            i = j
        return first_text, skip

    def _apply_manual_marks_to_classified(self, classified, raw_lines: list[str]):
        action_first, action_skip = self._manual_action_groups(raw_lines)
        for cl in classified:
            idx = cl.line_no - 1
            mark = self.manual_marks.get(idx)
            if not mark:
                continue

            kind = str(mark.get("kind") or "")
            if kind == LineKind.ACTION:
                cl.kind = LineKind.ACTION
                cl.payload = {"text": action_first.get(idx, ""), "emit": idx not in action_skip}
            elif kind == LineKind.CHAPTER:
                cl.kind = LineKind.CHAPTER
                cl.payload = {"title": str(mark.get("text") or "").strip()}
            elif kind == LineKind.LOCATION:
                cl.kind = LineKind.LOCATION
                cl.payload = {"name": str(mark.get("text") or "").strip()}
            elif kind == LineKind.IGNORE:
                cl.kind = LineKind.IGNORE
                cl.payload = {}
            elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                cl.kind = kind
                cl.payload = {
                    "speaker": str(mark.get("speaker") or "").strip(),
                    "text": str(mark.get("text") or "").strip(),
                }

    def _classified_summary(self, classified):
        stats: dict[str, int] = {}
        speakers: list[str] = []
        seen = set()
        for cl in classified:
            stats[cl.kind] = stats.get(cl.kind, 0) + 1
            if cl.kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                spk = str(cl.payload.get("speaker") or "")
                if spk and spk not in seen:
                    seen.add(spk)
                    speakers.append(spk)
        return speakers, stats

    def _line_maps_from_classified(self, classified):
        line_kinds = {}
        line_speakers = {}
        current_speaker = None
        for cl in classified:
            idx = cl.line_no - 1
            line_kinds[idx] = cl.kind
            if cl.kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                current_speaker = cl.payload.get("speaker")
                line_speakers[idx] = current_speaker
            elif cl.kind == LineKind.DIALOGUE_CONT and current_speaker:
                line_speakers[idx] = current_speaker
            else:
                current_speaker = None
        return line_kinds, line_speakers

    def _apply_manual_marks_to_parse_text(self, text: str, base_offset: int = 0) -> str:
        raw_lines = text.splitlines()
        action_first, action_skip = self._manual_action_groups(raw_lines, base_offset=base_offset)
        out: list[str] = []

        for rel_idx, raw in enumerate(raw_lines):
            idx = base_offset + rel_idx
            mark = self.manual_marks.get(idx)
            if not mark:
                out.append(raw)
                continue

            kind = str(mark.get("kind") or "")
            if idx in action_skip:
                out.append("")
            elif kind == LineKind.ACTION:
                out.append(f"{{Action: {action_first.get(idx, '')}}}")
            elif kind == LineKind.CHAPTER:
                out.append(f"[Chapter: {str(mark.get('text') or '').strip()}]")
            elif kind == LineKind.LOCATION:
                out.append(f"[Location: {str(mark.get('text') or '').strip()}]")
            elif kind == LineKind.IGNORE:
                out.append("")
            elif kind == LineKind.SPEAKER:
                speaker = str(mark.get("speaker") or "").strip()
                body = str(mark.get("text") or "").strip()
                out.append(f"{speaker}: {body}".rstrip())
            elif kind == LineKind.GUTTER_SPEAKER:
                out.append(str(mark.get("speaker") or "").strip())
            else:
                out.append(raw)

        return "\n".join(out)

    def _overlay_manual_marks_on_lines(self, line_kinds: dict, line_speakers: dict, raw_lines: list[str]):
        action_first, action_skip = self._manual_action_groups(raw_lines)
        for idx, mark in self.manual_marks.items():
            if idx < 0 or idx >= len(raw_lines):
                continue
            kind = str(mark.get("kind") or "")
            if kind == LineKind.ACTION:
                line_kinds[idx] = LineKind.ACTION
                line_speakers.pop(idx, None)
            elif kind in (LineKind.CHAPTER, LineKind.LOCATION, LineKind.IGNORE):
                line_kinds[idx] = kind
                line_speakers.pop(idx, None)
            elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
                line_kinds[idx] = kind
                speaker = str(mark.get("speaker") or "").strip()
                if speaker:
                    line_speakers[idx] = speaker
        for idx in action_skip:
            if 0 <= idx < len(raw_lines):
                line_kinds[idx] = LineKind.ACTION
                line_speakers.pop(idx, None)
        return action_first

    # ------------------------------------------------------------- loading
    def _auto_discover_script(self):
        try:
            composer = None
            if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
                composer = getattr(self.mw.translation_handler, "prompt_composer", None)
            path = composer._find_script_path() if composer else None
            if isinstance(path, str) and path and os.path.exists(path):
                self._load_path(path)
        except Exception as e:
            log_error(f"ScriptMarkupStudio: auto-discover failed: {e}")

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open raw walkthrough", "",
            "Scripts (*.txt *.md *.text);;All files (*)",
        )
        if path:
            self._load_path(path)

    def _load_path(self, path: str):
        try:
            try:
                with open(path, "r", encoding="cp1252", errors="replace") as f:
                    text = f.read()
            except Exception:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except Exception as e:
            QMessageBox.warning(self, tr('Load failed'), f"Could not read file:\n{e}")
            return
        self._set_history_suspended(True)
        try:
            self._publish_active_hierarchy_project_path("")
            self.current_raw_path = path
            self.path_label.setText(path)
            self.manual_marks = {}
            self.hierarchy_marks = []
            self._hierarchy_mark_order = 0
            self._collapsed_hierarchy_keys.clear()
            self._stop_range_edit()
            self.raw_edit.setUpdatesEnabled(False)
            self.raw_edit.setPlainText(text)
            self.raw_edit.setUpdatesEnabled(True)
            self._debounce.stop()
            log_info(f"ScriptMarkupStudio: loaded {os.path.basename(path)} ({len(text)} chars)")
            self._refresh()
        finally:
            self.raw_edit.setUpdatesEnabled(True)
            self._set_history_suspended(False)
        self._record_history()

    # --------------------------------------------------------------- modes
    def _on_mode_changed(self):
        self.mode = self.mode_combo.currentData() or "hierarchy"
        self._update_mode_controls()
        self._refresh()
        self._record_history()

    def _update_mode_controls(self):
        custom = self.mode == "custom"
        hierarchy = self.mode == "hierarchy"
        show_legacy = self.show_legacy_controls_action.isChecked() or not hierarchy

        self.recipe_box.setVisible(show_legacy and custom)
        self.recipe_box.setEnabled(custom)
        self.teach_box.setVisible(show_legacy and custom)
        self.teach_box.setEnabled(custom)

        self.hierarchy_box.setVisible(hierarchy)
        self.hierarchy_box.setEnabled(hierarchy)

        self.load_markup_btn.setVisible(hierarchy)
        self.save_markup_btn.setVisible(hierarchy)
        self.load_template_btn.setVisible(hierarchy)
        self.save_template_btn.setVisible(hierarchy)

        # Legacy compat updates (to satisfy existing test assertions)
        self.save_project_primary_btn.setVisible(hierarchy)
        self.finish_mempalace_btn.setVisible(hierarchy)
        self.project_menu_btn.setVisible(hierarchy)
        self.template_menu_btn.setVisible(hierarchy)
        self.auto_markup_menu_btn.setVisible(hierarchy)
        self.recipe_menu_btn.setVisible(custom)
        self.load_recipe_btn.setVisible(custom)
        self.save_recipe_btn.setVisible(custom)
        self.reset_markup_btn.setVisible(hierarchy)
        self.continue_examples_btn.setVisible(hierarchy)

        if hasattr(self, "join_structures_btn") and self.join_structures_btn is not None:
            self.join_structures_btn.setVisible(hierarchy)
        if hasattr(self, "ai_markup_btn") and self.ai_markup_btn is not None:
            self.ai_markup_btn.setVisible(hierarchy)

        self.range_panel.setVisible(show_legacy)

        if not hierarchy and self._is_hierarchy_editing():
            self._stop_range_edit()
            self._apply_raw_extra_selections()
            self._update_hierarchy_edit_controls()

        if hasattr(self, "raw_label"):
            if hierarchy and self._range_edit_mark_key:
                self._update_range_edit_label()
            else:
                if hierarchy:
                    self.raw_label.setText("")
                else:
                    self.raw_label.setText(tr('⚙️ Automatic rule preview'))
                    self.raw_label.setStyleSheet("color: #4b5563; font-style: italic;")
        self.outline_label.setText(
            "Script tree (double-click to jump):"
            if hierarchy else
            "Review queue (double-click to jump):"
        )
        if hasattr(self, "expand_tree_btn"):
            self.expand_tree_btn.setVisible(hierarchy)
            self.collapse_tree_btn.setVisible(hierarchy)
        self._update_legend()

    def _on_flag_changed(self):
        self.recipe.gutter_speakers = self.cb_gutter.isChecked()
        self.recipe.continuation = self.cb_continuation.isChecked()
        self._refresh()
        self._record_history()

    def _resolve_game_rules(self):
        rules = getattr(self.mw, "current_game_rules", None)
        if rules is not None and hasattr(rules, "parse_walkthrough_transcript"):
            return rules
        try:
            from plugins.base_game_rules import BaseGameRules
            return BaseGameRules(self.mw)
        except Exception:
            return None
