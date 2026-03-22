import re
from PyQt5.QtWidgets import QMenu, QMainWindow, QWidget, QWidgetAction, QGridLayout, QStyle
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import Qt, QPoint
from ui.ui_utils import prettify_standard_context_menu
from utils.logging_utils import log_debug

class LNETContextMenuLogic:
    WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")

    def __init__(self, editor):
        self.editor = editor

    def populate(self, menu: QMenu, position_in_widget_coords: QPoint):
        log_debug(f"LNET ({self.editor.objectName()}): populateContextMenu called (delegated).")
        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow):
            return

        translator = getattr(main_window, 'translation_handler', None)
        custom_actions_added = False

        glossary_entry = None
        if self.editor.objectName() == "original_text_edit":
            cursor = self.editor.textCursor()
            selection_text = cursor.selectedText().replace('\u2029', '\r\n').strip()
            if selection_text:
                add_term_candidate = selection_text
                context_line = cursor.block().text().replace('\u2029', ' ').strip()
            else:
                cursor_at_pos = self.editor.cursorForPosition(position_in_widget_coords)
                cursor_at_pos.select(QTextCursor.WordUnderCursor)
                add_term_candidate = cursor_at_pos.selectedText().replace('\u2029', '\r\n').strip()
                context_line = cursor_at_pos.block().text().replace('\u2029', ' ').strip()

            context_line = context_line or ''

            glossary_entry = self.editor._find_glossary_entry_at(position_in_widget_coords)
            existing_entry = None
            if glossary_entry and translator is not None:
                existing_entry = glossary_entry
            elif translator is not None and add_term_candidate:
                existing_entry = translator.get_glossary_entry(add_term_candidate)

            if existing_entry and translator is not None:
                action = menu.addAction(main_window.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Edit Glossary Entry…")
                action.setEnabled(True)
                action.triggered.connect(
                    lambda checked=False, term=existing_entry.original: translator.edit_glossary_entry(term)
                )
            else:
                action = menu.addAction(main_window.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Add to Glossary…")
                action_enabled = bool(add_term_candidate) and translator is not None
                action.setEnabled(action_enabled)
                if action_enabled:
                    action.triggered.connect(
                        lambda checked=False, term=add_term_candidate, ctx=context_line: translator.add_glossary_entry(term, ctx)
                    )
            custom_actions_added = True
            if glossary_entry:
                menu.addSeparator()
                term_value = glossary_entry.original
                show_action = menu.addAction(
                    main_window.style().standardIcon(QStyle.SP_FileDialogDetailedView),
                    f"Show Glossary Entry for \"{term_value}\""
                )
                if translator:
                    show_action.triggered.connect(
                        lambda checked=False, term=term_value: translator.show_glossary_dialog(term)
                    )
                else:
                    show_action.setEnabled(False)
                menu.addSeparator()

        if self.editor.objectName() == "edited_text_edit" and not self.editor.isReadOnly():
            cursor = self.editor.textCursor()
            has_selection = cursor.hasSelection()

            # Spellchecker: Show suggestions and add to dictionary
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                if not has_selection:
                    cursor_at_pos = self.editor.cursorForPosition(position_in_widget_coords)
                    click_position = cursor_at_pos.position()
                    block = cursor_at_pos.block()
                    block_text = block.text()
                    position_in_block = click_position - block.position()
                    text_with_spaces = block_text.replace('·', ' ')

                    word_under_cursor = ""
                    word_start = 0
                    word_end = 0

                    for match in self.WORD_PATTERN.finditer(text_with_spaces):
                        if match.start() <= position_in_block < match.end():
                            word_under_cursor = match.group(0).strip("'")
                            word_start = match.start()
                            word_end = match.end()
                            break

                    word_cursor = QTextCursor(block)
                    word_cursor.setPosition(block.position() + word_start)
                    word_cursor.setPosition(block.position() + word_end, QTextCursor.KeepAnchor)
                else:
                    raw_text = cursor.selectedText().strip()
                    text_with_spaces = raw_text.replace('·', ' ')
                    word_under_cursor = text_with_spaces.split()[0].strip("'") if text_with_spaces.split() else ""
                    word_cursor = cursor

                if word_under_cursor and spellchecker_manager.is_misspelled(word_under_cursor):
                    if not custom_actions_added:
                        menu.addSeparator()
                        custom_actions_added = True

                    suggestions = spellchecker_manager.get_suggestions(word_under_cursor)
                    if suggestions:
                        for suggestion in suggestions[:5]:
                            suggestion_action = menu.addAction(f"→ {suggestion}")
                            suggestion_action.triggered.connect(
                                lambda checked=False, s=suggestion, c=word_cursor: self.editor._replace_word_at_cursor(c, s)
                            )
                        menu.addSeparator()
                    else:
                        no_suggestions_action = menu.addAction("(No suggestions)")
                        no_suggestions_action.setEnabled(False)
                        menu.addSeparator()

                    add_to_dict_action = menu.addAction(main_window.style().standardIcon(QStyle.SP_DialogHelpButton), f"Add \"{word_under_cursor}\" to Dictionary")
                    add_to_dict_action.triggered.connect(
                        lambda checked=False, word=word_under_cursor: spellchecker_manager.add_to_custom_dictionary(word)
                    )

            if translator and has_selection:
                if not custom_actions_added:
                    menu.addSeparator()
                    custom_actions_added = True

                variation_action = menu.addAction(main_window.style().standardIcon(QStyle.SP_MessageBoxInformation), "AI Variations for Selected")
                variation_action.triggered.connect(translator.generate_variation_for_current_string)

            # Dynamic Tags Section
            if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                tags_data = main_window.current_game_rules.get_custom_context_tags()
                tags_to_show = []
                if has_selection:
                    tags_to_show = tags_data.get("wrap_tags", [])
                else:
                    tags_to_show = tags_data.get("single_tags", [])
                
                if tags_to_show:
                    if not custom_actions_added:
                        menu.addSeparator()
                        custom_actions_added = True
                    
                    tag_widget_action = QWidgetAction(menu)
                    tag_palette_widget = QWidget(menu)
                    
                    palette_layout = QGridLayout(tag_palette_widget)
                    palette_layout.setContentsMargins(5, 3, 5, 3)
                    palette_layout.setSpacing(4)
                    
                    max_cols = 8
                    for i, tag_info in enumerate(tags_to_show):
                        disp = tag_info.get("display", "?")
                        if has_selection:
                            ot = tag_info.get("open", "")
                            ct = tag_info.get("close", "")
                            btn = self.editor._create_tag_button(tag_palette_widget, disp, ot, ct, menu)
                        else:
                            t = tag_info.get("tag", "")
                            btn = self.editor._create_tag_button(tag_palette_widget, disp, t, None, menu)
                            
                        row = i // max_cols
                        col = i % max_cols
                        palette_layout.addWidget(btn, row, col)
                    
                    tag_palette_widget.setLayout(palette_layout)
                    tag_widget_action.setDefaultWidget(tag_palette_widget)
                    menu.addAction(tag_widget_action)

            # Revert to Original option for edited_text_edit
            if main_window.current_block_idx != -1 and main_window.current_string_idx != -1:
                menu.addSeparator()
                revert_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_ArrowBack), "Revert String to Original")
                revert_action.triggered.connect(lambda: main_window.data_processor.perform_revert_strings(main_window.current_block_idx, [main_window.current_string_idx]))
        
        if self.editor.objectName() == "preview_text_edit":
            if not custom_actions_added: menu.addSeparator(); custom_actions_added = True

            translator = getattr(main_window, 'translation_handler', None)
            selected_lines = self.editor.get_selected_lines()

            if translator:
                if selected_lines:
                    num_selected = len(selected_lines)
                    action_text = f"AI Translate {num_selected} Lines (UA)" if num_selected > 1 else f"AI Translate Line {selected_lines[0] + 1} (UA)"
                else:
                    cursor = self.editor.cursorForPosition(position_in_widget_coords)
                    line_num = cursor.blockNumber()
                    action_text = f"AI Translate Line {line_num + 1} (UA)"

                translate_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_MessageBoxInformation), action_text)
                translate_action.triggered.connect(lambda: translator.translate_preview_selection(position_in_widget_coords))

                translate_block_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_MessageBoxInformation), "AI Translate Entire Block (UA)")
                translate_block_action.triggered.connect(lambda: translator.translate_current_block())

            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                menu.addSeparator()
                if selected_lines:
                    num_selected = len(selected_lines)
                    spellcheck_text = f"Spellcheck {num_selected} Lines" if num_selected > 1 else f"Spellcheck Line {selected_lines[0] + 1}"
                else:
                    cursor = self.editor.cursorForPosition(position_in_widget_coords)
                    line_num = cursor.blockNumber()
                    spellcheck_text = f"Spellcheck Line {line_num + 1}"

                spellcheck_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_DialogHelpButton), spellcheck_text)
                spellcheck_action.triggered.connect(
                    lambda: self.editor._open_spellcheck_dialog_for_selection(position_in_widget_coords)
                )

            if len(selected_lines) > 0:
                num_selected = len(selected_lines)
                menu.addSeparator()
                
                move_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_DirIcon), f"Move {num_selected} Line(s) to Virtual Block...")
                move_action.triggered.connect(main_window.list_selection_handler.move_selection_to_category)
                
                menu.addSeparator()
                set_font_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_FileDialogListView), f"Set Font for {num_selected} Line(s)...")
                set_font_action.triggered.connect(self.editor.handle_mass_set_font)
                set_width_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_FileDialogListView), f"Set Width for {num_selected} Line(s)...")
                set_width_action.triggered.connect(self.editor.handle_mass_set_width)

                # Revert to Original
                menu.addSeparator()
                real_indices = [main_window.displayed_string_indices[i] for i in selected_lines if i < len(main_window.displayed_string_indices)]
                if real_indices:
                    revert_action = menu.addAction(main_window.style().standardIcon(main_window.style().SP_ArrowBack), f"Revert {len(real_indices)} Line(s) to Original")
                    revert_action.triggered.connect(lambda: main_window.data_processor.perform_revert_strings(main_window.current_block_idx, real_indices))
            else:
                # No lines selected, try the line under cursor
                cursor = self.editor.cursorForPosition(position_in_widget_coords)
                line_val = cursor.blockNumber()
                if hasattr(main_window, 'displayed_string_indices') and line_val < len(main_window.displayed_string_indices):
                    real_idx = main_window.displayed_string_indices[line_val]
                    menu.addSeparator()
                    revert_action = menu.addAction(main_window.style().standardIcon(QStyle.SP_ArrowBack), f"Revert Line {line_val + 1} to Original")
                    revert_action.triggered.connect(lambda: main_window.data_processor.perform_revert_strings(main_window.current_block_idx, [real_idx]))

        prettify_standard_context_menu(menu, main_window.style())

