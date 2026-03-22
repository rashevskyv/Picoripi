# --- START OF FILE components/custom_list_widget.py ---
# --- START OF FILE components/CustomListWidget.py ---
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QSize, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from .custom_list_item_delegate import CustomListItemDelegate
from utils.logging_utils import log_debug, log_error

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.setUniformItemSizes(False) 
        
        delegate = CustomListItemDelegate(self)
        self.setItemDelegate(delegate)
        self.viewport().setMouseTracking(True)

        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
            # Можна додати більше кольорів тут
        }

    def _create_color_icon(self, color: QColor, size: int = 12) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen) 
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item
    
    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        main_window = self.window()
        menu = QMenu(self)

        # "Add Block" option (always available if project is loaded)
        if hasattr(main_window, 'project_manager') and main_window.project_manager:
            add_block_action = menu.addAction("Add Block...")
            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'import_block_action'):
                add_block_action.triggered.connect(main_window.app_action_handler.import_block_action)
            menu.addSeparator()

        # Block-specific options (only if item exists)
        if not item:
            menu.exec_(self.mapToGlobal(pos))
            return

        self.setCurrentItem(item)
        block_idx = item.data(Qt.UserRole)
        block_name = item.text()
        if hasattr(main_window, 'block_names'):
            block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}")

        rename_action = menu.addAction(f"Rename '{block_name}'")
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            rename_action.triggered.connect(lambda checked=False, item_to_rename=item: main_window.list_selection_handler.rename_block(item_to_rename))

        menu.addSeparator()

        marker_definitions = {}
        if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            marker_definitions = main_window.current_game_rules.get_color_marker_definitions()

        current_markers = main_window.block_handler.get_block_color_markers(block_idx)
        for color_name, q_color in self.color_marker_definitions.items():
            label = marker_definitions.get(color_name, color_name.capitalize())
            action = QAction(self._create_color_icon(q_color), f"Mark '{label}'", menu)
            action.setCheckable(True)
            action.setChecked(color_name in current_markers)
            action.triggered.connect(lambda checked, b_idx=block_idx, c_name=color_name: main_window.block_handler.toggle_block_color_marker(b_idx, c_name))
            menu.addAction(action)

        menu.addSeparator()

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Issues in '{block_name}'")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.issue_scan_handler.rescan_issues_for_single_block(idx))

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'calculate_widths_for_block_action'):
            calc_widths_action = menu.addAction(f"Calculate Line Widths for Block '{block_name}'")
            calc_widths_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.calculate_widths_for_block_action(idx))

        # Spellcheck action
        spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
        if spellchecker_manager and spellchecker_manager.enabled:
            menu.addSeparator()
            spellcheck_action = menu.addAction(f"Spellcheck Block '{block_name}'")
            spellcheck_action.triggered.connect(lambda checked=False, idx=block_idx: self._open_spellcheck_for_block(idx, None))

        translator = getattr(main_window, 'translation_handler', None)
        if translator:
            menu.addSeparator()

            progress = translator.translation_progress.get(block_idx)
            if progress and progress['completed_chunks'] and len(progress['completed_chunks']) < progress['total_chunks']:
                resume_action = menu.addAction(f"Resume Translation for '{block_name}'")
                resume_action.triggered.connect(lambda checked=False, idx=block_idx: translator.resume_block_translation(idx))
            else:
                translate_block = menu.addAction(f"AI Translate Block '{block_name}' (UA)")
                translate_block.triggered.connect(lambda checked=False, idx=block_idx: translator.translate_current_block(idx))

            generate_glossary = menu.addAction(f"AI Build Glossary for '{block_name}'")
            generate_glossary.triggered.connect(lambda checked=False, idx=block_idx: main_window.build_glossary_with_ai(idx))
        menu.exec_(self.mapToGlobal(pos))

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            log_debug(f"CustomListWidget: viewport ToolTip event at {event.pos()}")
            index = self.indexAt(event.pos())
            if index.isValid():
                delegate = self.itemDelegate(index)
                if delegate:
                    option = self.viewOptions()
                    option.rect = self.visualRect(index)
                    if delegate.helpEvent(event, self, option, index):
                        return True
        return super().viewportEvent(event)

    def _open_spellcheck_for_block(self, block_idx: int, category_name: str = None):
        """Open spellcheck dialog for a specific block."""
        log_debug(f"CustomListWidget: _open_spellcheck_for_block called for block_idx={block_idx}, category={category_name}")

        try:
            main_window = self.window()
            log_debug(f"CustomListWidget: Got main_window: {main_window}")

            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            log_debug(f"CustomListWidget: spellchecker_manager={spellchecker_manager}, enabled={spellchecker_manager.enabled if spellchecker_manager else 'N/A'}")

            if not spellchecker_manager:
                log_debug("CustomListWidget: No spellchecker_manager, returning")
                return

            # Get all lines from the block
            if not hasattr(main_window, 'data') or block_idx >= len(main_window.data):
                log_debug(f"CustomListWidget: Invalid block_idx or no data. has_data={hasattr(main_window, 'data')}, block_idx={block_idx}")
                return

            block_data = main_window.data[block_idx]
            log_debug(f"CustomListWidget: block_data type={type(block_data)}, len={len(block_data) if isinstance(block_data, list) else 'N/A'}")

            if not isinstance(block_data, list):
                log_debug("CustomListWidget: block_data is not a list, returning")
                return

            # Get translated text using same logic as data_state_processor.get_current_string_text()
            # Priority: edited_data (in-memory) > edited_file_data (saved translations) > data (original)
            edited_data = getattr(main_window, 'edited_data', {})
            edited_file_data = getattr(main_window, 'edited_file_data', [])

            log_debug(f"CustomListWidget: edited_data has {len(edited_data)} in-memory entries")
            log_debug(f"CustomListWidget: edited_file_data has {len(edited_file_data)} blocks")
            log_debug(f"CustomListWidget: Sample edited_data keys: {list(edited_data.keys())[:5]}")

            # First pass: collect all translated lines and check for misspellings
            all_translated_lines = []  # (string_idx, text)

            valid_indices = None
            if category_name and hasattr(main_window, 'project_manager') and main_window.project_manager.project:
                project = main_window.project_manager.project
                proj_block_idx = block_idx
                if hasattr(main_window, 'block_to_project_file_map'):
                    proj_block_idx = main_window.block_to_project_file_map.get(block_idx, block_idx)
                if proj_block_idx < len(project.blocks):
                    block = project.blocks[proj_block_idx]
                    for cat in block.categories:
                        if cat.name == category_name:
                            valid_indices = set(cat.line_indices)
                            break

            for string_idx in range(len(block_data)):
                if valid_indices is not None and string_idx not in valid_indices:
                    continue

                key = (block_idx, string_idx)
                text = None

                # Priority 1: Check in-memory edits
                if key in edited_data:
                    text = edited_data[key]
                # Priority 2: Check saved translation file
                elif edited_file_data and block_idx < len(edited_file_data):
                    edited_block = edited_file_data[block_idx]
                    if isinstance(edited_block, list) and string_idx < len(edited_block):
                        text = edited_block[string_idx]

                # Collect if we found a translation (don't fall back to original)
                if text and text.strip():
                    all_translated_lines.append((string_idx, text))

            log_debug(f"CustomListWidget: Found {len(all_translated_lines)} translated lines in block")

            # Second pass: filter to only lines with spelling errors
            import re
            word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')

            text_parts = []
            line_numbers = []  # Real STRING numbers (not subline numbers) from the block

            for string_idx, text in all_translated_lines:
                # Replace middle dots with spaces for word detection
                text_with_spaces = text.replace('·', ' ')

                # Check if this line contains any misspelled words
                has_misspellings = False
                for match in word_pattern.finditer(text_with_spaces):
                    word = match.group(0).strip("'")
                    if word and spellchecker_manager.is_misspelled(word):
                        has_misspellings = True
                        break

                # Only include lines with misspellings
                if has_misspellings:
                    text_parts.append(text)

                    # For each subline in this string, add the string index
                    # This ensures line_numbers[subline_idx] = string_idx
                    subline_count = text.count('\n') + 1
                    for _ in range(subline_count):
                        line_numbers.append(string_idx)

                    log_debug(f"CustomListWidget: String {string_idx} - has misspellings, adding {subline_count} sublines")

            log_debug(f"CustomListWidget: Found {len(text_parts)} lines with misspellings (out of {len(all_translated_lines)} translated lines)")

            text_to_check = '\n'.join(text_parts)
            if not text_to_check.strip():
                log_debug("CustomListWidget: No lines with misspellings found")
                from PyQt5.QtWidgets import QMessageBox
                if len(all_translated_lines) == 0:
                    QMessageBox.information(self, "Spellcheck", "Немає перекладеного тексту для перевірки.\nСпочатку перекладіть текст у цьому блоці.")
                else:
                    QMessageBox.information(self, "Spellcheck", f"Орфографічні помилки не знайдено!\nПеревірено {len(all_translated_lines)} перекладених рядків.")
                return

            log_debug(f"CustomListWidget: Opening SpellcheckDialog with {len(line_numbers)} lines")

            # Import and open dialog
            from dialogs.spellcheck_dialog import SpellcheckDialog
            dialog = SpellcheckDialog(self, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers)
            log_debug("CustomListWidget: SpellcheckDialog created, calling exec_()")

            if dialog.exec_():
                log_debug("CustomListWidget: Dialog accepted, applying corrections")
                corrected_text = dialog.get_corrected_text()
                corrected_lines = corrected_text.split('\n')

                # Apply corrections back to edited_data
                log_debug("CustomListWidget: Applying corrections to edited_data")
                for i, corrected_line in enumerate(corrected_lines):
                    if i < len(line_numbers):
                        string_idx = line_numbers[i]
                        key = (block_idx, string_idx)  # Use tuple key!
                        if corrected_line != text_parts[i]:
                            edited_data[key] = corrected_line
                            main_window.unsaved_changes = True
                            main_window.unsaved_block_indices.add(block_idx)
                            log_debug(f"CustomListWidget: Updated line {string_idx} in edited_data")

                # Refresh UI if this is the current block
                current_block_idx = getattr(main_window, 'current_block_index', -1)
                if current_block_idx == block_idx and hasattr(main_window, 'ui_updater'):
                    log_debug("CustomListWidget: Refreshing UI for current block")
                    main_window.ui_updater.populate_strings_for_block(block_idx)
                    main_window.ui_updater.update_text_views()
                    main_window.ui_updater.update_block_item_text_with_problem_count(block_idx)

                log_debug("CustomListWidget: Corrections applied successfully")
            else:
                log_debug("CustomListWidget: Dialog cancelled")

        except Exception as e:
            log_error(f"CustomListWidget: Error in _open_spellcheck_for_block: {e}", exc_info=True)