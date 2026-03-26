# components/tree_spellcheck_mixin.py
"""Spellcheck and Reveal-in-Explorer mixin for CustomTreeWidget."""
import platform
import re
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox

from utils.logging_utils import log_debug, log_error


class TreeSpellcheckMixin:
    """Context-menu helpers: reveal block file in OS Explorer and block-level spellcheck."""

    # ─────────────────────────────────────────────────────────────────────────
    # Reveal in Explorer
    # ─────────────────────────────────────────────────────────────────────────

    def _reveal_in_explorer(self, block_idx: int, is_translation: bool = False):
        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)

        if not pm:
            # Fallback: single-file mode
            ds = getattr(main_window, 'data_store', None)
            path = (ds.edited_json_path if is_translation else ds.json_path) if ds else None
            if path and Path(path).exists():
                self._open_explorer_at_path(path)
            return

        project = pm.project
        if not project:
            return

        project_block_idx = block_idx
        block_map = getattr(main_window, 'block_to_project_file_map', {})
        project_block_idx = block_map.get(block_idx, block_idx)

        if project_block_idx >= len(project.blocks):
            return

        block = project.blocks[project_block_idx]
        abs_path = (
            pm.get_absolute_path(block.translation_file, is_translation=True)
            if is_translation
            else pm.get_absolute_path(block.source_file)
        )
        if abs_path and Path(abs_path).exists():
            self._open_explorer_at_path(abs_path)

    def _open_explorer_at_path(self, abs_path: str):
        path_obj = Path(abs_path)
        if not path_obj.exists():
            QMessageBox.warning(self, "Reveal", f"File not found:\n{abs_path}")
            return
        if platform.system() == "Windows":
            subprocess.Popen(['explorer', '/select,', str(path_obj)])
        elif platform.system() == "Darwin":
            subprocess.Popen(['open', '-R', str(path_obj)])
        else:
            subprocess.Popen(['xdg-open', str(path_obj.parent)])

    # ─────────────────────────────────────────────────────────────────────────
    # Block-level spellcheck
    # ─────────────────────────────────────────────────────────────────────────

    def _open_spellcheck_for_block(self, block_idx: int, category_name: str = None):
        log_debug(f"CustomTreeWidget: spellcheck block={block_idx} category={category_name!r}")
        try:
            main_window = self.window()
            scm = getattr(main_window, 'spellchecker_manager', None)
            if not scm:
                return

            ds = getattr(main_window, 'data_store', None)
            if not ds or block_idx >= len(ds.data):
                return

            block_data = ds.data[block_idx]
            if not isinstance(block_data, list):
                return

            # Determine which string indices are relevant (category filter)
            valid_indices = None
            pm = getattr(main_window, 'project_manager', None)
            if category_name and pm and pm.project:
                block_map = getattr(main_window, 'block_to_project_file_map', {})
                proj_block_idx = block_map.get(block_idx, block_idx)
                if proj_block_idx < len(pm.project.blocks):
                    for cat in pm.project.blocks[proj_block_idx].categories:
                        if cat.name == category_name:
                            valid_indices = set(cat.line_indices)
                            break

            all_translated_lines = []
            for string_idx in range(len(block_data)):
                if valid_indices is not None and string_idx not in valid_indices:
                    continue
                text, _ = main_window.data_processor.get_current_string_text(block_idx, string_idx)
                if text and text.strip():
                    all_translated_lines.append((string_idx, text))

            word_pattern = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
            text_parts = []
            line_numbers = []

            for string_idx, text in all_translated_lines:
                text_with_spaces = text.replace('·', ' ')
                if any(
                    scm.is_misspelled(m.group(0).strip("'"))
                    for m in word_pattern.finditer(text_with_spaces)
                    if m.group(0).strip("'")
                ):
                    text_parts.append(text)
                    for _ in range(text.count('\n') + 1):
                        line_numbers.append(string_idx)

            text_to_check = '\n'.join(text_parts)
            if not text_to_check.strip():
                if not all_translated_lines:
                    QMessageBox.information(self, "Spellcheck", "No text found to check in this block.")
                else:
                    QMessageBox.information(
                        self, "Spellcheck",
                        f"No spelling errors found!\nChecked {len(all_translated_lines)} lines.",
                    )
                return

            from dialogs.spellcheck_dialog import SpellcheckDialog
            dialog = SpellcheckDialog(
                self, text_to_check, scm, starting_line_number=0, line_numbers=line_numbers
            )
            if not dialog.exec_():
                return

            corrected_text = dialog.get_corrected_text()
            corrected_lines = corrected_text.split('\n')
            edited_data = getattr(main_window, 'edited_data', {})

            for i, corrected_line in enumerate(corrected_lines):
                if i < len(line_numbers) and corrected_line != text_parts[i]:
                    string_idx = line_numbers[i]
                    edited_data[(block_idx, string_idx)] = corrected_line
                    ds.unsaved_changes = True
                    ds.unsaved_block_indices.add(block_idx)

            current_block_idx = getattr(main_window.data_store, 'current_block_idx', -1)
            if current_block_idx == block_idx:
                ui = getattr(main_window, 'ui_updater', None)
                if ui:
                    ui.populate_strings_for_block(block_idx)
                    ui.update_text_views()
                    ui.update_block_item_text_with_problem_count(block_idx)

        except Exception as e:
            log_error(f"CustomTreeWidget: _open_spellcheck_for_block error: {e}", exc_info=True)
