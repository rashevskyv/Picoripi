"""Text-view update mixin for PreviewUpdater."""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor

from utils.utils import (
    convert_spaces_to_dots_for_display,
    calculate_strict_string_width,
)
from ui.components.bfn_preview_widget import _looks_like_bfn_editor
from core.data_store import store_is_virtual_view


class TextViewsMixin:
    """Updates original/edited/preview text editors for the current string."""

    def update_text_views(self, *, heavy: bool = True):
        """Update the text views.

        ``heavy=False`` fills the editors only so a row click can paint
        immediately. BFN layout, width math and problem overlays run after
        the first frame via ``schedule_row_paint_followup``.
        """
        if getattr(self, '_in_update_text_views', False):
            return
        self._in_update_text_views = True
        is_programmatic_call_flag_original = self.mw.is_programmatically_changing_text

        self.mw.is_programmatically_changing_text = True
        try:
            self._do_update_text_views(is_programmatic_call_flag_original, heavy=heavy)
        finally:
            self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original
            self._in_update_text_views = False

    def _set_editor_highlighters_typing_mode(self, enabled: bool) -> None:
        for name in ('edited_text_edit', 'original_text_edit'):
            widget = getattr(self.mw, name, None)
            highlighter = getattr(widget, 'highlighter', None) if widget is not None else None
            if highlighter is not None:
                highlighter.set_typing_mode(enabled, trigger_rehighlight=False)

    def _do_update_text_views(self, is_programmatic_call_flag_original, *, heavy: bool = True):
        """Internal helper to do update text views."""
        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx, self.mw.data_store.data,
                "original_data_for_readonly_view"
            )
            if original_text_raw is None: original_text_raw = ""
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
            if edited_text_raw is None: edited_text_raw = ""

        # Skip rewriting the strings-list line on a light fill. The clicked
        # row already shows the right text; mutating the preview document here
        # re-highlights a block before the editors can paint.
        if heavy and self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            preview_edit = getattr(self.mw, 'preview_text_edit', None)
            if preview_edit:
                is_virtual = store_is_virtual_view(self.mw.data_store)
                displayed_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])

                preview_idx = -1
                if is_virtual:
                    target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                    if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                        res = self.mw.data_store.get_displayed_index_pos(target_tuple)
                        if isinstance(res, int) and not isinstance(res, bool):
                            preview_idx = res
                    if preview_idx == -1 and target_tuple in displayed_indices:
                        preview_idx = displayed_indices.index(target_tuple)
                else:
                    if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                        res = self.mw.data_store.get_displayed_index_pos(self.mw.data_store.current_string_idx)
                        if isinstance(res, int) and not isinstance(res, bool):
                            preview_idx = res
                    if preview_idx == -1 and self.mw.data_store.current_string_idx in displayed_indices:
                        preview_idx = displayed_indices.index(self.mw.data_store.current_string_idx)

                if preview_idx != -1:
                    if self.mw.current_game_rules:
                        preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(edited_text_raw))
                    else:
                        preview_line_text = str(edited_text_raw)

                    self.update_cached_string(
                        self.mw.data_store.current_block_idx,
                        self.mw.data_store.current_string_idx,
                        preview_line_text,
                        physical_block_idx=self.mw.data_store.physical_block_idx
                    )

                    doc = preview_edit.document()
                    block = doc.findBlockByNumber(preview_idx)
                    if block.isValid() and block.text() != preview_line_text:
                        _saved_prog = self.mw.is_programmatically_changing_text
                        self.mw.is_programmatically_changing_text = True
                        try:
                            cursor = QTextCursor(doc)
                            cursor.setPosition(block.position())
                            cursor.setPosition(block.position() + len(block.text()), QTextCursor.MoveMode.KeepAnchor)
                            cursor.insertText(preview_line_text)
                        finally:
                            self.mw.is_programmatically_changing_text = _saved_prog

                    if hasattr(preview_edit, 'lineNumberArea') and preview_edit.lineNumberArea:
                        preview_edit.lineNumberArea.update()
                    preview_edit.viewport().update()

        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            original_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(original_text_raw)))
            edited_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(edited_text_raw)))
        else:
            original_text_for_display_processed = str(original_text_raw)
            edited_text_for_display_processed = str(edited_text_raw)

        original_text_for_display = convert_spaces_to_dots_for_display(original_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(edited_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)

        if not heavy:
            self._set_editor_highlighters_typing_mode(True)

        orig_edit = self.mw.original_text_edit
        if orig_edit:
            if orig_edit.toPlainText() != original_text_for_display:
                orig_text_edit_cursor_pos = int(orig_edit.textCursor().position())
                orig_anchor_pos = int(orig_edit.textCursor().anchor())
                orig_has_selection = bool(orig_edit.textCursor().hasSelection())
                orig_edit.setPlainText(original_text_for_display)
                new_orig_cursor = orig_edit.textCursor()
                new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
                if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.MoveMode.KeepAnchor)
                else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
                orig_edit.setTextCursor(new_orig_cursor)

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            # Remember which row the editor is now showing. Edits are only ever
            # attributed to this row, so a stale or not-yet-filled editor can
            # never be written over a different string (see text_edited).
            self.mw.data_store.editor_bound_row = (
                self.mw.data_store.physical_block_idx,
                self.mw.data_store.current_string_idx,
            )
            if edited_widget.toPlainText() != edited_text_for_display_converted:
                saved_edited_cursor_pos = int(edited_widget.textCursor().position())
                saved_edited_anchor_pos = int(edited_widget.textCursor().anchor())
                saved_edited_has_selection = bool(edited_widget.textCursor().hasSelection())

                edited_widget.setPlainText(edited_text_for_display_converted)

                if heavy and self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                    if hasattr(self.mw, 'text_operation_handler'):
                        self.mw.text_operation_handler.sync_subline_asterisks(
                            self.mw.data_store.physical_block_idx,
                            self.mw.data_store.current_string_idx,
                            edited_text_raw
                        )

                restored_cursor = edited_widget.textCursor()
                new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
                new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
                restored_cursor.setPosition(new_edited_anchor_pos)
                if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.MoveMode.KeepAnchor)
                else: restored_cursor.setPosition(new_edited_cursor_pos)
                edited_widget.setTextCursor(restored_cursor)

        if hasattr(self.mw, 'dictionary_tooltip') and self.mw.dictionary_tooltip:
             self.mw.dictionary_tooltip.hide()

        if not heavy:
            return

        self._apply_editor_fonts()
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            self.mw.ui_updater.update_status_bar()
        else:
            self.mw.ui_updater.clear_status_bar()

        self._apply_heavy_text_view_overlays(
            original_text_raw, edited_text_raw, highlights=True, bfn=True
        )

    def schedule_row_paint_followup(self) -> None:
        """After the editors paint: overlays and BFN on the next frame."""
        row = (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )
        self._pending_row_followup = row
        self._followup_gen = getattr(self, '_followup_gen', 0) + 1
        gen = self._followup_gen
        QTimer.singleShot(16, lambda g=gen: self._row_paint_followup(g))

    def _followup_row_is_current(self, gen: int) -> bool:
        if gen != getattr(self, '_followup_gen', 0):
            return False
        pending = getattr(self, '_pending_row_followup', None)
        current = (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )
        return pending == current

    def _current_row_texts(self):
        current = (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )
        original_text_raw = ""
        edited_text_raw = ""
        if current[0] != -1 and current[1] != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                current[0], current[1], self.mw.data_store.data,
                "original_data_for_readonly_view"
            )
            if original_text_raw is None:
                original_text_raw = ""
            edited_text_raw, _ = self.data_processor.get_current_string_text(
                current[0], current[1]
            )
            if edited_text_raw is None:
                edited_text_raw = ""
        return original_text_raw, edited_text_raw

    def _row_paint_followup(self, gen: int = 0) -> None:
        if not self._followup_row_is_current(gen):
            return

        original_text_raw, edited_text_raw = self._current_row_texts()
        self._apply_editor_fonts()
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            self.mw.ui_updater.update_status_bar()
        else:
            self.mw.ui_updater.clear_status_bar()
        self._apply_heavy_text_view_overlays(
            original_text_raw, edited_text_raw, highlights=False, bfn=False
        )
        handler = getattr(self.mw, 'editor_operation_handler', None)
        if handler is not None and hasattr(handler, 'launch_async_scanner_immediate'):
            handler.launch_async_scanner_immediate()
        edited = getattr(self.mw, 'edited_text_edit', None)
        if edited is not None and hasattr(edited, 'recalculate_guidelines'):
            edited.recalculate_guidelines()
        if (
            self.mw.data_store.physical_block_idx != -1
            and self.mw.data_store.current_string_idx != -1
            and hasattr(self.mw, 'text_operation_handler')
        ):
            self.mw.text_operation_handler.sync_subline_asterisks(
                self.mw.data_store.physical_block_idx,
                self.mw.data_store.current_string_idx,
                edited_text_raw,
            )
        self._sync_bfn_previews(original_text_raw, edited_text_raw)

    def _apply_editor_fonts(self) -> None:
        if self.mw.data_store.physical_block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
        if not self.mw.current_game_rules:
            return
        font_info = self.mw.current_game_rules.get_font_for_block(self.mw.data_store.physical_block_idx)
        if not font_info:
            return
        orig_name = font_info.get('original_font_name')
        edited_name = font_info.get('font_name')
        if orig_name and orig_name != getattr(self, '_applied_original_font', None):
            custom_font_original = self.mw.helper.get_font_for_name(orig_name)
            if custom_font_original:
                self.mw.original_text_edit.setDocumentFont(custom_font_original)
                self._applied_original_font = orig_name
        if edited_name and edited_name != getattr(self, '_applied_edited_font', None):
            custom_font_edited = self.mw.helper.get_font_for_name(edited_name)
            if custom_font_edited:
                self.mw.edited_text_edit.setDocumentFont(custom_font_edited)
                self._applied_edited_font = edited_name
        if getattr(self.mw, 'string_settings_handler', None) and edited_name:
            setattr(self.mw.data_store, 'current_font_name', edited_name)

    def _apply_heavy_text_view_overlays(
        self, original_text_raw, edited_text_raw, *, highlights: bool = True, bfn: bool = True
    ) -> None:
        """Width labels, optional problem overlays, BFN preview, Font Editor sim."""
        if hasattr(self.mw, 'original_width_label'):
            if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                font_map_for_string = self.mw.helper.get_font_map_for_string(
                    self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx
                )
                icon_sequences = getattr(self.mw, 'icon_sequences', [])

                original_lines = str(original_text_raw).split('\n')
                widths = []
                for line in original_lines:
                    w = calculate_strict_string_width(line, font_map_for_string, icon_sequences=icon_sequences)
                    if w is None:
                        widths = None
                        break
                    widths.append(w)

                strict_width = max(widths) if widths is not None and widths else None

                if strict_width is not None:
                    self.mw.original_width_label.setText(f"{strict_width} px")
                    self.mw.original_width_label.show()
                else:
                    self.mw.original_width_label.setText("")
                    self.mw.original_width_label.hide()
            else:
                self.mw.original_width_label.setText("")
                self.mw.original_width_label.hide()

        if highlights and self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
             self._apply_highlights_to_editor(
                 self.mw.edited_text_edit,
                 self.mw.data_store.physical_block_idx,
                 self.mw.data_store.current_string_idx,
             )
             self._apply_highlights_to_editor(
                 self.mw.original_text_edit,
                 self.mw.data_store.physical_block_idx,
                 self.mw.data_store.current_string_idx,
             )

        if bfn:
            self._sync_bfn_previews(original_text_raw, edited_text_raw)

    def _sync_bfn_previews(self, original_text_raw, edited_text_raw) -> None:
        preview_enabled = getattr(self.mw, 'preview_enabled', True)
        toggle_action = getattr(self.mw, 'toggle_preview_action', None)
        show_preview = preview_enabled and (toggle_action.isChecked() if toggle_action else True)

        if hasattr(self.mw, 'bfn_preview_widget') and self.mw.bfn_preview_widget:
            preview_widget = self.mw.bfn_preview_widget
            preview_host = self._preview_visibility_host(preview_widget, self.mw)
            if show_preview:
                if preview_host.isHidden():
                    preview_host.show()
                if preview_host is not preview_widget and preview_widget.isHidden():
                    preview_widget.show()
                preview_widget.update_preview_text(edited_text_raw, original=original_text_raw)
            else:
                if not preview_host.isHidden():
                    preview_host.hide()

        editor = getattr(self.mw, '_bfn_editor_window', None)
        if _looks_like_bfn_editor(editor):
            try:
                if not editor.isHidden():
                    sync_enabled = True
                    if hasattr(editor, 'chk_sync_sim_text'):
                        sync_enabled = editor.chk_sync_sim_text.isChecked()
                    if sync_enabled:
                        editor.sim_input.blockSignals(True)
                        editor.sim_input.setPlainText(edited_text_raw)
                        editor.sim_input.blockSignals(False)
                        editor.update_simulation()
            except RuntimeError:
                self.mw._bfn_editor_window = None
            except Exception:
                pass

