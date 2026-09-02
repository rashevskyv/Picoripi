"""Context menu and related actions."""
from __future__ import annotations

from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import Qt

from utils.utils import is_control_modifier_pressed


class ContextMixin:
    """Context menu and related actions."""

    def eventFilter(self, obj, event):
        """Capture Ctrl state at the moment of right mouse button press for context menu."""
        from PyQt6.QtCore import QEvent as _QEvent
        from PyQt6.QtCore import Qt as _Qt
        if hasattr(self, 'matches_list') and obj is self.matches_list.viewport():
            if event.type() == _QEvent.Type.MouseButtonPress:
                if event.button() == _Qt.MouseButton.RightButton:
                    self._ctrl_was_pressed_at_right_click = bool(
                        event.modifiers() & _Qt.KeyboardModifier.ControlModifier
                    )
        return super().eventFilter(obj, event)

    def show_context_menu(self, pos):
        selected_items = self.matches_list.selectedItems()
        if not selected_items:
            item = self.matches_list.itemAt(pos)
            if item:
                selected_items = [item]

        if not selected_items:
            return

        is_ctrl_at_populate = getattr(self, '_ctrl_was_pressed_at_right_click', False)
        self._ctrl_was_pressed_at_right_click = False  # Reset after reading

        def check_ctrl_now():
            return is_control_modifier_pressed()

        pairs = []
        seen = set()
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and isinstance(data, tuple) and len(data) >= 2:
                b_idx, string_idx = data[0], data[1]
                pair = (b_idx, string_idx)
                if pair not in seen:
                    seen.add(pair)
                    pairs.append(pair)

        if not pairs:
            return

        menu = QMenu(self)
        count = len(pairs)

        # Define icons using theme with a style-based standardIcon fallback
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QStyle

        def get_icon(theme_name, fallback_pixmap):
            ico = QIcon.fromTheme(theme_name)
            if ico.isNull() or ico.name() == "":
                return self.style().standardIcon(fallback_pixmap)
            return ico

        icon_translate = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        icon_spellcheck = get_icon("tools-check-spelling", QStyle.StandardPixmap.SP_DialogHelpButton)
        icon_move = get_icon("go-jump", QStyle.StandardPixmap.SP_ArrowForward)
        icon_font = get_icon("preferences-desktop-font", QStyle.StandardPixmap.SP_FileDialogListView)
        icon_width = get_icon("format-justify-fill", QStyle.StandardPixmap.SP_FileDialogListView)
        icon_autofix = get_icon("document-edit", QStyle.StandardPixmap.SP_DialogYesButton)
        icon_revert = get_icon("document-revert", QStyle.StandardPixmap.SP_BrowserReload)
        icon_restore = get_icon("edit-redo", QStyle.StandardPixmap.SP_ArrowForward)

        # Build user-friendly action texts depending on the count (singular/plural)
        if count > 1:
            txt_translate = f"AI Translate {count} Selected Lines (UA)"
            txt_spellcheck = f"Spellcheck {count} Selected Lines"
            txt_move = f"Move {count} Selected Lines to Virtual Block..."
            txt_font = f"Set Font for {count} Selected Lines..."
            txt_width = f"Set Width for {count} Selected Lines..."
            txt_autofix = f"AutoFix {count} Selected Lines..."
            txt_revert = f"Revert {count} Selected Lines to Original"
            txt_restore = f"Restore Translated for {count} Selected Lines"
        else:
            txt_translate = "AI Translate Selected Line (UA)"
            txt_spellcheck = "Spellcheck Selected Line"
            txt_move = "Move Selected Line to Virtual Block..."
            txt_font = "Set Font for Selected Line..."
            txt_width = "Set Width for Selected Line..."
            txt_autofix = "AutoFix Selected Line..."
            txt_revert = "Revert Selected Line to Original"
            txt_restore = "Restore Translated for Selected Line"

        # 1. AI Translate
        action_translate = menu.addAction(icon_translate, txt_translate)
        action_translate.triggered.connect(lambda checked=False: self._ctx_ai_translate(pairs, force_prompt=is_ctrl_at_populate or check_ctrl_now()))

        # 2. Spellcheck
        action_spellcheck = menu.addAction(icon_spellcheck, txt_spellcheck)
        action_spellcheck.triggered.connect(lambda: self._ctx_spellcheck(pairs))

        # 3. Move
        action_move = menu.addAction(icon_move, txt_move)
        action_move.triggered.connect(lambda: self._ctx_move_to_category(pairs))

        menu.addSeparator()

        # 4. Set Font
        action_set_font = menu.addAction(icon_font, txt_font)
        action_set_font.triggered.connect(lambda: self._ctx_set_font(pairs))

        # 5. Set Width
        action_set_width = menu.addAction(icon_width, txt_width)
        action_set_width.triggered.connect(lambda: self._ctx_set_width(pairs))

        menu.addSeparator()

        # 6. AutoFix
        action_autofix = menu.addAction(icon_autofix, txt_autofix)
        action_autofix.triggered.connect(lambda: self._ctx_autofix(pairs))

        # 7. Revert
        action_revert = menu.addAction(icon_revert, txt_revert)
        action_revert.triggered.connect(lambda: self._ctx_revert(pairs))

        # 8. Restore
        action_restore = menu.addAction(icon_restore, txt_restore)
        action_restore.triggered.connect(lambda: self._ctx_restore(pairs))

        menu.exec(self.matches_list.viewport().mapToGlobal(pos))

    def _ctx_ai_translate(self, pairs, force_prompt=False):
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'translation_handler'):
            desc = "Selected search lines"
            main_window.translation_handler.translate_specific_strings(pairs, desc, force_prompt=force_prompt)

    def _ctx_spellcheck(self, pairs):
        main_window = self._find_main_window()
        spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
        if not spellchecker_manager or not spellchecker_manager.enabled:
            return

        text_parts = []
        block_indices = []
        line_numbers = []
        for b_idx, s_idx in pairs:
            text, _ = main_window.data_processor.get_current_string_text(b_idx, s_idx)
            if text is None:
                text = ""
            text_parts.append(text)
            block_indices.append(b_idx)
            line_numbers.append(s_idx)

        text_to_check = '\n'.join(text_parts)
        if not text_to_check.strip():
            return

        from dialogs.spellcheck_dialog import SpellcheckDialog
        dialog = SpellcheckDialog(
            self,
            text_to_check,
            spellchecker_manager,
            line_numbers=line_numbers,
            block_idx=self.block_idx,
            block_indices=block_indices
        )

        if dialog.exec():
            corrected_text = dialog.get_corrected_text()
            corrected_lines = corrected_text.split('\n')

            has_undo = hasattr(main_window, 'undo_manager')
            if has_undo:
                main_window.undo_manager.begin_group()

            try:
                for i, (b_idx, s_idx) in enumerate(pairs):
                    if i < len(corrected_lines):
                        new_text = corrected_lines[i]
                        main_window.data_processor.update_edited_data(
                            b_idx, s_idx, new_text, action_type="SPELLCHECK", skip_ui_refresh=True
                        )
                        if hasattr(main_window, 'text_operation_handler') and main_window.text_operation_handler:
                            main_window.text_operation_handler._rescan_issues_for_current_string(b_idx, s_idx, new_text)
            finally:
                if has_undo:
                    main_window.undo_manager.end_group("SPELLCHECK")

            modified_blocks = {b_idx for b_idx, _ in pairs}
            for m_block in modified_blocks:
                main_window.ui_updater.update_block_item_text_with_problem_count(m_block)

            current_view_block = main_window.data_store.current_block_idx
            if main_window.data_store.current_chapter_id is not None:
                current_view_block = -2
            main_window.ui_updater.populate_strings_for_block(
                current_view_block, getattr(main_window.data_store, 'current_category_name', None), force=True
            )
            main_window.ui_updater.update_text_views()
            main_window.ui_updater.update_title()

            self.refresh_from_project()

    def _ctx_move_to_category(self, pairs):
        main_window = self._find_main_window()
        pm = main_window.project_manager
        if not pm or not pm.project:
            return

        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Move to Virtual Block", "Enter Category Name:", text="New Category")
        if not ok or not name.strip():
            return

        category_name = name.strip()

        by_block = {}
        for b_idx, s_idx in pairs:
            if b_idx not in by_block:
                by_block[b_idx] = []
            by_block[b_idx].append(s_idx)

        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()

        try:
            block_map = getattr(main_window, 'block_to_project_file_map', {})
            for b_idx, s_indices in by_block.items():
                proj_b_idx = block_map.get(b_idx, b_idx)
                if proj_b_idx < len(pm.project.blocks):
                    pm.move_strings_to_category(proj_b_idx, s_indices, category_name)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("MOVE_TO_CATEGORY")

        main_window.ui_updater.populate_blocks()
        current_view_block = main_window.data_store.current_block_idx
        if main_window.data_store.current_chapter_id is not None:
            current_view_block = -2
        main_window.ui_updater.populate_strings_for_block(
            current_view_block, getattr(main_window.data_store, 'current_category_name', None), force=True
        )
        main_window.ui_updater.update_text_views()
        self.refresh_from_project()

    def _ctx_set_font(self, pairs):
        main_window = self._find_main_window()
        from components.editor.mass_font_dialog import MassFontDialog
        dialog = MassFontDialog(main_window)
        if dialog.exec():
            font_file = dialog.get_selected_font()
            for b_idx, s_idx in pairs:
                key = (b_idx, s_idx)
                if font_file == "default":
                    if key in main_window.string_metadata:
                        if "font_file" in main_window.string_metadata[key]:
                            del main_window.string_metadata[key]["font_file"]
                        if not main_window.string_metadata[key]:
                            del main_window.string_metadata[key]
                else:
                    if key not in main_window.string_metadata:
                        main_window.string_metadata[key] = {}
                    main_window.string_metadata[key]["font_file"] = font_file

            if hasattr(main_window, 'settings_manager'):
                main_window.settings_manager.save_settings()

            if hasattr(main_window.string_settings_handler, '_apply_and_rescan'):
                main_window.string_settings_handler._apply_and_rescan()
            self.refresh_from_project()

    def _ctx_set_width(self, pairs):
        main_window = self._find_main_window()
        from components.editor.mass_width_dialog import MassWidthDialog
        dialog = MassWidthDialog(main_window)
        if dialog.exec():
            is_auto = dialog.is_auto_width()
            width = dialog.get_width()

            for b_idx, s_idx in pairs:
                key = (b_idx, s_idx)
                if is_auto:
                    original_text = main_window.data_processor._get_string_from_source(b_idx, s_idx, main_window.data_store.data, "original")
                    calculated_width = main_window.text_analysis_handler.calculate_text_width(original_text) if hasattr(main_window, 'text_analysis_handler') else 0
                    if calculated_width > 0:
                        if key not in main_window.string_metadata:
                            main_window.string_metadata[key] = {}
                        main_window.string_metadata[key]["width"] = calculated_width
                else:
                    is_default = (width == 0 or width == main_window.game_dialog_max_width_pixels)
                    if is_default:
                        if key in main_window.string_metadata:
                            if "width" in main_window.string_metadata[key]:
                                del main_window.string_metadata[key]["width"]
                            if not main_window.string_metadata[key]:
                                del main_window.string_metadata[key]
                    else:
                        if key not in main_window.string_metadata:
                            main_window.string_metadata[key] = {}
                        main_window.string_metadata[key]["width"] = width

            if hasattr(main_window, 'settings_manager'):
                main_window.settings_manager.save_settings()

            if hasattr(main_window.string_settings_handler, '_apply_and_rescan'):
                main_window.string_settings_handler._apply_and_rescan()
            self.refresh_from_project()

    def _ctx_autofix(self, pairs):
        main_window = self._find_main_window()
        if hasattr(main_window, 'text_operation_handler') and main_window.text_operation_handler:
            main_window.text_operation_handler.fix_all_strings(pairs)
            self.refresh_from_project()

    def _ctx_revert(self, pairs):
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'data_processor'):
            main_window.data_processor.perform_revert_strings(-2, pairs)
            self.refresh_from_project()

    def _ctx_restore(self, pairs):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'saved_translations_handler'):
            return

        by_block = {}
        for b_idx, s_idx in pairs:
            if b_idx not in by_block:
                by_block[b_idx] = []
            by_block[b_idx].append(s_idx)

        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()

        try:
            for b_idx, s_indices in by_block.items():
                main_window.saved_translations_handler.restore_translations_for_strings(b_idx, s_indices)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("RESTORE_STRINGS")

        self.refresh_from_project()
