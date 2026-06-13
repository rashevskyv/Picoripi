# Picoripi API Reference (Automatically Extracted)

This document list all classes, public methods, and top-level functions inside the key components of the Picoripi project.

## Component: `core`

### File: [bfn_core.py](../../core/bfn_core.py)

#### Functions

- **`align_to(value, alignment)`**
  *Description*: Align to.

#### Class: `Class BfnCore`

*Bfn core implementation.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`load_file(self, path)`**
  *Description*: Load file.

- **`load(self, data)`**
  *Description*: Load .

- **`save(self)`**
  *Description*: Save .

- **`to_font_map(self, translation_map)`**
  *Description*: Convert BFN metrics to Picoripi-compatible font_map dictionary: { "char": { "width": width_in_pixels } }

- **`get_sheets_qimages(self)`**
  *Description*: Decode the binary sheets (texture sheets) from GLY1 chunk using I4 or IA4 formats directly into PyQt6 QImage objects. Results are cached.

- **`layout_text(self, text, translation_map, line_spacing)`**
  *Description*: Compute layout positions for each character in text based on current BFN font metrics. Returns:     - List of dictionaries representing laid out glyphs.     - total width of text block     - total height of text block



---

### File: [context.py](../../core/context.py)

#### Class: `Class UIProvider(Protocol)`

*U i provider implementation.*


##### Methods

- **`statusBar(self)`**
  *Description*: Statusbar.

- **`force_focus(self)`**
  *Description*: Force focus.

- **`preview_text_edit(self)`**
  *Description*: Preview text edit.

- **`original_text_edit(self)`**
  *Description*: Original text edit.

- **`edited_text_edit(self)`**
  *Description*: Edited text edit.

- **`block_list_widget(self)`**
  *Description*: Block list widget.

- **`search_panel_widget(self)`**
  *Description*: Search panel widget.

- **`open_glossary_button(self)`**
  *Description*: Open glossary button.

- **`show_message(self, title, text, type)`**
  *Description*: Show message.

- **`ask_yes_no(self, title, text, default_yes)`**
  *Description*: Ask yes no.

- **`show_archive_size_warning(self, archive_rel_path, new_size, orig_size)`**
  *Description*: Show archive size warning.

- **`create_progress_tracker(self, title, message, max_val)`**
  *Description*: Create progress tracker.



#### Class: `Class ProjectContext(Protocol)`

*Project context implementation.*


##### Methods

- **`state(self)`**
  *Description*: State.

- **`data_store(self)`**
  *Description*: Data store.

- **`project_manager(self)`**
  *Description*: Project manager.

- **`settings_manager(self)`**
  *Description*: Settings manager.

- **`data_processor(self)`**
  *Description*: Data processor.

- **`saved_translations_manager(self)`**
  *Description*: Saved translations manager.

- **`ui_updater(self)`**
  *Description*: Ui updater.

- **`undo_manager(self)`**
  *Description*: Undo manager.

- **`spellchecker_manager(self)`**
  *Description*: Spellchecker manager.

- **`list_selection_handler(self)`**
  *Description*: List selection handler.

- **`editor_operation_handler(self)`**
  *Description*: Editor operation handler.

- **`app_action_handler(self)`**
  *Description*: App action handler.

- **`project_action_handler(self)`**
  *Description*: Project action handler.

- **`issue_scan_handler(self)`**
  *Description*: Issue scan handler.

- **`search_handler(self)`**
  *Description*: Search handler.

- **`string_settings_handler(self)`**
  *Description*: String settings handler.

- **`translation_handler(self)`**
  *Description*: Translation handler.

- **`text_analysis_handler(self)`**
  *Description*: Text analysis handler.

- **`ai_chat_handler(self)`**
  *Description*: Ai chat handler.

- **`bookmark_handler(self)`**
  *Description*: Bookmark handler.

- **`saved_translations_handler(self)`**
  *Description*: Saved translations handler.

- **`ui_provider(self)`**
  *Description*: Ui provider.

- **`preview_text_edit(self)`**
  *Description*: Preview text edit.

- **`original_text_edit(self)`**
  *Description*: Original text edit.

- **`edited_text_edit(self)`**
  *Description*: Edited text edit.

- **`block_list_widget(self)`**
  *Description*: Block list widget.

- **`search_panel_widget(self)`**
  *Description*: Search panel widget.

- **`open_glossary_button(self)`**
  *Description*: Open glossary button.

- **`data(self)`**
  *Description*: Data.

- **`edited_file_data(self)`**
  *Description*: Edited file data.

- **`edited_data(self)`**
  *Description*: Edited data.

- **`current_block_idx(self)`**
  *Description*: Current block idx.

- **`current_string_idx(self)`**
  *Description*: Current string idx.

- **`current_game_rules(self)`**
  *Description*: Current game rules.

- **`active_game_plugin(self)`**
  *Description*: Active game plugin.

- **`block_to_project_file_map(self)`**
  *Description*: Block to project file map.

- **`unsaved_changes(self)`**
  *Description*: Unsaved changes.

- **`unsaved_changes(self, value)`**
  *Description*: Unsaved changes.

- **`update_title(self)`**
  *Description*: Update the title.

- **`autofix_enabled(self)`**
  *Description*: Autofix enabled.

- **`autofix_enabled(self, value)`**
  *Description*: Autofix enabled.

- **`detection_enabled(self)`**
  *Description*: Detection enabled.

- **`detection_enabled(self, value)`**
  *Description*: Detection enabled.

- **`line_width_warning_threshold_pixels(self)`**
  *Description*: Line width warning threshold pixels.

- **`game_dialog_max_width_pixels(self)`**
  *Description*: Game dialog max width pixels.

- **`show_width_guideline(self)`**
  *Description*: Show width guideline.

- **`spellchecker_enabled(self)`**
  *Description*: Spellchecker enabled.

- **`spellchecker_language(self)`**
  *Description*: Spellchecker language.

- **`newline_display_symbol(self)`**
  *Description*: Newline display symbol.

- **`newline_color_rgba(self)`**
  *Description*: Newline color rgba.

- **`newline_bold(self)`**
  *Description*: Newline bold.

- **`newline_italic(self)`**
  *Description*: Newline italic.

- **`newline_underline(self)`**
  *Description*: Newline underline.

- **`tag_color_rgba(self)`**
  *Description*: Tag color rgba.

- **`tag_bold(self)`**
  *Description*: Tag bold.

- **`tag_italic(self)`**
  *Description*: Tag italic.

- **`tag_underline(self)`**
  *Description*: Tag underline.

- **`newline_css(self)`**
  *Description*: Newline css.

- **`tag_css(self)`**
  *Description*: Tag css.

- **`space_dot_color_hex(self)`**
  *Description*: Space dot color hex.

- **`preview_wrap_lines(self)`**
  *Description*: Preview wrap lines.

- **`editors_wrap_lines(self)`**
  *Description*: Editors wrap lines.

- **`bracket_tag_color_hex(self)`**
  *Description*: Bracket tag color hex.

- **`font_combobox(self)`**
  *Description*: Font combobox.

- **`width_spinbox(self)`**
  *Description*: Width spinbox.

- **`apply_width_button(self)`**
  *Description*: Apply width button.

- **`auto_fix_button(self)`**
  *Description*: Auto fix button.

- **`ai_translate_button(self)`**
  *Description*: Ai translate button.

- **`ai_variation_button(self)`**
  *Description*: Ai variation button.

- **`status_label_part1(self)`**
  *Description*: Status label part1.

- **`status_label_part2(self)`**
  *Description*: Status label part2.

- **`status_label_part3(self)`**
  *Description*: Status label part3.

- **`plugin_status_label(self)`**
  *Description*: Plugin status label.

- **`statusBar(self)`**
  *Description*: Statusbar.

- **`close_project_action(self)`**
  *Description*: Close project action.

- **`prompt_editor_enabled(self)`**
  *Description*: Prompt editor enabled.

- **`string_metadata(self)`**
  *Description*: String metadata.

- **`current_font_map(self)`**
  *Description*: Current font map.

- **`font_map(self)`**
  *Description*: Font map.

- **`lines_per_page(self)`**
  *Description*: Lines per page.

- **`default_tag_mappings(self)`**
  *Description*: Default tag mappings.

- **`get_service(self, service_type)`**
  *Description*: Get the service.



---

### File: [data_manager.py](../../core/data_manager.py)

#### Functions

- **`load_json_file(file_path)`**
  *Description*: Load json file.

- **`save_json_file(file_path, data_to_save)`**
  *Description*: Save json file.

- **`load_text_file(file_path)`**
  *Description*: Load text file.

- **`save_text_file(file_path, text_content)`**
  *Description*: Save text file.

---

### File: [data_state_processor.py](../../core/data_state_processor.py)

#### Class: `Class DataStateProcessor`

*Data state processor implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initializes the DataStateProcessor with a reference to the MainWindow.  Args:     main_window (Any): Reference to the central GUI window (MainWindow) containing shared state.

- **`_show_message(self, title, text, type)`**
  *Description*: Internal helper to display diagnostic or information messages to the user. Delegates to the UIProvider show_message method or logs the info/error if headless.  Args:     title (str): Title of the message box.     text (str): Main text content to display.     type (str): Type of message - can be 'info', 'warning', or 'error'.

- **`_ask_yes_no(self, title, text, default_yes)`**
  *Description*: Displays an interactive dialog box asking the user a binary (Yes/No) question.  Args:     title (str): Dialog box title.     text (str): Prompt question text.     default_yes (bool): Default answer if dialog is bypassed or headless.      Returns:     bool: True if the user clicks Yes, False if No.

- **`_get_string_from_source(self, block_idx, string_idx, source_data, source_name)`**
  *Description*: Extracts a single dialogue string safely from a target multi-dimensional source list.  Args:     block_idx (int): The index of the file block.     string_idx (int): The line index within the block.     source_data (List[Any]): The array of string lists to extract from.     source_name (str): Label used for debugging/tracing.      Returns:     Optional[str]: The dialogue string if found within boundaries, else None.

- **`get_current_string_text(self, block_idx, string_idx)`**
  *Description*: Retrieves the current text for a specific dialogue string by checking three state levels: 1. In-memory unsaved edits (edited_data). 2. Saved file edits (edited_file_data). 3. Raw original source data (original_data).  Args:     block_idx (int): The index of the file block.     string_idx (int): The line index within the block.      Returns:     Tuple[str, str]: A tuple containing the text string and a label indicating its source.

- **`get_block_texts(self, block_idx)`**
  *Description*: Collects all current texts (applying edits) for an entire dialogue block.  Args:     block_idx (int): The block index to extract texts from.      Returns:     List[str]: A list of all dialogue strings within that block.

- **`string_needs_translation(self, block_idx, string_idx)`**
  *Description*: Checks whether a string needs manual translation. A string does not need translation if its original source text is empty  or contains only tags and whitespace.

- **`is_string_translated(self, block_idx, string_idx)`**
  *Description*: Checks whether a string has a valid translation. A string is considered translated if its original text needs translation and its current edited translation is non-empty and differs from the original source text.

- **`update_edited_data(self, block_idx, string_idx, new_text, action_type, skip_ui_refresh)`**
  *Description*: Updates the in-memory translation state for a single dialogue line. If the new text matches the saved file data, any in-memory edit key is cleaned up. Otherwise, the edit is stored, metadata (e.g. AI model name, timestamp) is recorded,  and the action is pushed to the UndoManager.  Args:     block_idx (int): The index of the file block.     string_idx (int): The line index within the block.     new_text (str): The updated translation text string.     action_type (str): Type of edit action (e.g., 'TEXT_EDIT', 'TRANSLATE', 'REVERT') for Undo tracking.     skip_ui_refresh (bool): If True, suppresses triggering live UI refreshes.      Returns:     bool: True if the global unsaved changes status changed, else False.

- **`revert_strings_to_original(self, block_idx, string_indices, progress_dialog, progress_offset)`**
  *Description*: Reverts multiple strings in a block to their original state (from the loaded file).

- **`perform_revert_strings(self, block_idx, string_indices, confirm)`**
  *Description*: Unified wrapper method to revert a list of strings within a block. Displays an optional confirmation dialog box before applying changes. Groups the reverts in a single undo group transaction if multiple strings are affected.  Args:     block_idx (int): The index of the file block, or -2 if reverting a virtual chapter.     string_indices (List[Any]): List of line indices or list of (block_idx, string_idx) tuples.     confirm (bool): If True, prompts the user for verification.

- **`revert_blocks_to_original(self, block_indices)`**
  *Description*: Reverts entire dialogue blocks back to their original file contents. Auto-saves current user edits to database, initializes an UndoManager transaction, and triggers full UI tree and preview updates.  Args:     block_indices (List[int]): The list of block indices to be reverted.

- **`_perform_save_impl(self, output_data_list, progress_callback)`**
  *Description*: Internal execution engine for the save sequence. Distinguishes between Project Mode (split saving and archive repacking) and  Single File Mode. Writes JSON, TXT, or BMG streams to disk. For archives, automatically builds Yaz0 compressed packages and reports sizing warnings.  Args:     output_data_list (List[Any]): Complete list of strings containing all translation updates.     progress_callback (Callable): Callback used to report completion rates to progress dialogs.      Returns:     Tuple[bool, List[Tuple[str, int, int]], List[str]]:         - bool: True if the file saving succeeded, False otherwise.         - List[Tuple[str, int, int]]: Warnings containing (archive_path, new_size, original_size).         - List[str]: Errors encountered during write operations.

- **`save_current_edits(self, ask_confirmation)`**
  *Description*: Main entry point for saving all unsaved user translations. Gathers memory edits, merges them with existing saved data/original data,  and triggers _perform_save_impl. Supports both Project Mode and single-file formats. Displays confirmation dialogues and triggers non-blocking Toast success notifications.  Args:     ask_confirmation (bool): If True, prompt the user for validation prior to file writes.      Returns:     bool: True if saving succeeded, else False.

- **`revert_edited_file_to_original(self)`**
  *Description*: Revert edited file to original.



---

### File: [data_store.py](../../core/data_store.py)

#### Class: `Class AppDataStore`

*Centralized store for application data. Decouples data state from MainWindow UI.*


##### Methods

- **`clear(self)`**
  *Description*: Reset all data to default state.

- **`mark_dirty(self, block_idx)`**
  *Description*: Mark a block as having unsaved changes.

- **`mark_clean(self, block_idx)`**
  *Description*: Mark a block or the entire store as clean.



---

### File: [glossary_manager.py](../../core/glossary_manager.py)

#### Functions

- **`preserve_case(match_text, replacement)`**
  *Description*: Detects the casing of match_text and returns replacement with the same casing. Supports ALL CAPS, Title Case (Capitalized), and lowercase.

- **`replace_preserve_case(text, find_word, replace_word)`**
  *Description*: Case-insensitive substring replacement that preserves the case of the matched portion.

#### Class: `Class GlossaryEntry`

*Single glossary record.*


##### Methods

- **`is_valid(self)`**
  *Description*: Check if is valid.



#### Class: `Class GlossaryMatch`

*Result of matching a glossary entry inside text.*




#### Class: `Class GlossaryOccurrence`

*Specific occurrence of a glossary entry in project data.*




#### Class: `Class GlossaryManager`

*Load and cache glossary entries for a plugin with search utilities.*


##### Methods

- **`__init__(self)`**
  *Description*: Initializes the GlossaryManager. Sets up the internal entries collection, caches for compiled patterns,  occurrence index maps, session modification tracking, and Aho-Corasick automaton structures.

- **`normalize_term(value)`**
  *Description*: Normalizes a glossary term for consistent stem lookup and regex matching. Strips accents/combining characters, normalizes unicode to NFKD, converts  characters to lowercase, replaces hashes with spaces, and collapses extra whitespaces.  Args:     value (str): The raw string term.      Returns:     str: Normalized lowercased search key.

- **`load_from_text(self)`**
  *Description*: Populates the glossary structure by parsing either JSON arrays or Markdown tables. Prepares high-performance search indices (Aho-Corasick automaton and regex dictionaries) to enable instant morphological highlighting.  Args:     plugin_name (Optional[str]): Active game plugin name.     glossary_path (Optional[Path]): File path of the glossary database on disk.     raw_text (str): The raw string buffer read from disk.

- **`refresh_from_disk(self)`**
  *Description*: Reloads the glossary from disk if the database path is configured. Otherwise, resets the glossary database to an empty state.

- **`get_raw_text(self)`**
  *Description*: Retrieves the raw text representation of the glossary.  Returns:     str: JSON or Markdown table string buffer.

- **`get_entries(self)`**
  *Description*: Returns a copy of all loaded glossary entries.  Returns:     Sequence[GlossaryEntry]: List of active GlossaryEntry instances.

- **`get_entry(self, term)`**
  *Description*: Find a glossary entry by its original term, ignoring case and spacing.

- **`get_entries_sorted_by_length(self)`**
  *Description*: Retrieves all glossary entries sorted by length in descending order. Useful for preventing partial word matches inside larger compounds.  Returns:     Sequence[GlossaryEntry]: Sorted list of glossary entries.

- **`get_compiled_pattern(self, entry)`**
  *Description*: Retrieves the compiled regex pattern corresponding to a glossary entry.  Args:     entry (GlossaryEntry): Target glossary entry.      Returns:     Optional[re.Pattern[str]]: Compiled regex pattern if exists, else None.

- **`iter_compiled(self)`**
  *Description*: Iterates over all loaded glossary entries that have a valid compiled regex pattern.  Yields:     Tuple[GlossaryEntry, re.Pattern[str]]: Tuple of the entry and its compiled pattern.

- **`find_matches(self, text)`**
  *Description*: Finds all glossary term occurrences inside the target text string. Utilizes a two-phase search strategy: 1. High-speed exact matching via Aho-Corasick automaton (case-insensitive). 2. RegEx fallback matching for terms containing inline layout tags or variable spacing.  Args:     text (str): Dialogue line text to scan.      Returns:     List[GlossaryMatch]: Sorted list of glossary matches with character offset offsets.

- **`build_occurrence_index(self, dataset)`**
  *Description*: Scans the entire dialogue dataset of the project and builds a global inverted index mapping glossary terms to their precise line occurrences (block, string, line number, character bounds).  Args:     dataset (Sequence): Multi-dimensional sequence containing all dialogue strings.      Returns:     Dict[str, List[GlossaryOccurrence]]: Map of term strings to lists of occurrences.

- **`update_occurrences_for_entry(self, dataset, old_term, new_entry)`**
  *Description*: Incrementally update the occurrence index for a single glossary entry change.

- **`get_occurrences_for(self, entry)`**
  *Description*: Retrieves all cached project occurrences mapped to a specific glossary entry.  Args:     entry (GlossaryEntry): Target glossary entry.      Returns:     List[GlossaryOccurrence]: List of line occurrences matching the term.

- **`get_occurrence_map(self)`**
  *Description*: Retrieves the entire inverted occurrence index.  Returns:     Dict[str, List[GlossaryOccurrence]]: Map of all term strings to their project occurrences.

- **`get_relevant_terms(self, text)`**
  *Description*: Find all glossary entries that appear in the given text.

- **`get_session_changes(self)`**
  *Description*: Return a copy of the session's glossary modifications.

- **`clear_session_changes(self)`**
  *Description*: Clear the tracked session glossary modifications.

- **`add_entry(self, original, translation, notes, section, profiled)`**
  *Description*: Creates and inserts a new term into the glossary database. Automatically updates session logs, rebuilds occurrence indexes, and persists changes. Redirects to update_entry if the term already exists.  Args:     original (str): The source glossary term.     translation (str): Semicolon-separated translations of the term.     notes (str): Usage notes or definitions.     section (Optional[str]): Semantic category tab for grouping.     profiled (bool): If True, designates a character cast member profile.      Returns:     Optional[GlossaryEntry]: The created entry, or None if parameters are empty.

- **`update_entry(self, original, translation, notes, section, profiled)`**
  *Description*: Updates an existing glossary term's properties (translations, notes, category, profiled status). Rebuilds occurrence indexes and persists changes to disk.  Args:     original (str): The original term to locate and update.     translation (str): Updated translations.     notes (str): Updated notes.     section (Optional[str]): Updated semantic category.     profiled (Optional[bool]): Updated profiling status.      Returns:     Optional[GlossaryEntry]: The updated entry if located, else None.

- **`delete_entry(self, original)`**
  *Description*: Deletes a term from the glossary database. Clears occurrence indexing, tracks the deletion in session changes, and writes to disk.  Args:     original (str): The term key to delete.      Returns:     bool: True if the entry was found and deleted, False otherwise.

- **`save_to_disk(self)`**
  *Description*: Writes the current glossary entries to the disk database path in JSON format. Does not trigger a full cache reload.

- **`_parse_markdown(self, text)`**
  *Description*: Internal helper to parse markdown.

- **`_table_lines(self, entries)`**
  *Description*: Internal helper to table lines.

- **`_generate_markdown(self)`**
  *Description*: Internal helper to generate markdown.

- **`_persist(self, write_only)`**
  *Description*: Internal helper to persist.

- **`_build_pattern_cache(self)`**
  *Description*: Internal helper to create pattern cache.

- **`_build_regex(term)`**
  *Description*: Internal helper to create regex.

- **`build_translation_regex(term)`**
  *Description*: Build a regex for a translated term that handles Slavic inflections. Supports multiple translations separated by semicolons (;).

- **`_get_word_stem_pattern(word)`**
  *Description*: Internal helper to get a stem pattern for a single word.

- **`global_replace(self, find_word, replace_word)`**
  *Description*: Replaces find_word with replace_word in all entries of the glossary (original, translation, notes), keeping the case. Returns a list of tuples: (old_entry, old_translation, new_entry) for entries where the translation has changed.



---

### File: [markdown_script_parser.py](../../core/markdown_script_parser.py)

#### Functions

- **`parse_markdown_script(file_path)`**
  *Description*: Parse a standardized Markdown game script file into structured data. Extracts global synopsis, characters cast with attributes, terms,  and chronological chapters with locations, actions, and dialogues.

---

### File: [mempalace_client.py](../../core/mempalace_client.py)

#### Class: `Class MemePalaceClient`

*Meme palace client implementation.*


##### Methods

- **`__init__(self, project_dir, server_url)`**
  *Description*: Initialize a new instance.

- **`preload_cache(self, force)`**
  *Description*: Preload all drawers from local DB and build high-performance in-memory indexes.

- **`get_cached_context(self, bmg_id, text)`**
  *Description*: MemePalace high-performance memory cache lookup by BMG ID or text string.

- **`_init_local_db(self)`**
  *Description*: Initialize the local SQLite database for local fallback mode.

- **`is_server_available(self)`**
  *Description*: Check if the external MemPalace server is up and responding.

- **`has_room(self, wing_name, room_name)`**
  *Description*: Check if visual scene context drawer already exists for a room in local database.

- **`add_wing(self, name, description, conn)`**
  *Description*: Create a new top-level container (Wing) for the project.

- **`add_room(self, wing_name, room_name, description, conn)`**
  *Description*: Add a specific room (location/scene category) to a wing.

- **`add_drawer(self, wing_name, room_name, drawer_name, content, metadata, conn)`**
  *Description*: Add a verbatim transcription or scene description (Drawer) to a room.

- **`add_relation(self, wing_name, source, relation, target, valid_from, conn)`**
  *Description*: Add relationship rule between characters or entities to temporal knowledge graph.

- **`search_context(self, wing_name, query, limit)`**
  *Description*: Search the MemPalace database for visual/story context related to the query string.

- **`get_room_visual_context(self, wing_name, room_name)`**
  *Description*: Retrieve visual_scene_context Drawer content for a given room in SQLite database.

- **`get_relations(self, wing_name)`**
  *Description*: Retrieve all character relations for a given wing from SQLite database.

- **`clear_wing(self, wing_name)`**
  *Description*: Clear all database entries (rooms, drawers, knowledge graph relations) for the given wing.

- **`clear_all_local_data(self)`**
  *Description*: Completely clear all data from all tables in the local SQLite database.

- **`get_wings(self)`**
  *Description*: Retrieve all Wings (game projects) from the local SQLite database.

- **`get_rooms(self, wing_name)`**
  *Description*: Retrieve all Rooms (scenes/timeline locations) for the given wing.

- **`get_room_drawers(self, wing_name, room_name)`**
  *Description*: Retrieve all Drawers (contents/transcripts) for the given room and wing.

- **`get_chapter_for_line(self, wing_name, line_num)`**
  *Description*: Find the script chapter containing the given script line number.

- **`get_script_mapping(self, wing_name, bmg_id)`**
  *Description*: Retrieve script mapping directly from script_mappings table.

- **`get_chapter_mappings(self, wing_name, chapter_id)`**
  *Description*: Retrieve all BMG mappings for a specific chapter.

- **`get_all_chapters(self, wing_name)`**
  *Description*: Retrieve all chapters and their mapping counts for a wing.

- **`save_chapter_summary(self, chapter_id, summary)`**
  *Description*: Update AI summary of a chapter.

- **`save_chapters_to_db(self, wing_name, chapters)`**
  *Description*: Save segmented chapters into local SQLite DB, clearing older chapters for the wing.

- **`save_mappings_to_db(self, wing_name, mappings)`**
  *Description*: Save BMG to script mappings into SQLite DB, clearing older mappings first.

- **`get_all_character_lines(self, wing_name)`**
  *Description*: Retrieve and group all dialogue lines spoken by each character from mapped drawers.



---

### File: [mempalace_worker.py](../../core/mempalace_worker.py)

#### Functions

- **`robust_json_loads(text)`**
  *Description*: Parse JSON from AI response text, stripping markdown code fences if present.

#### Class: `Class MemePalaceWorker(QThread)`

*Meme palace worker implementation.*


##### Methods

- **`__init__(self, client, bmg_strings, bmg_ids, transcript_data, ai_provider, wing_name, mapping_only, bmg_translation_states, target_lang, glossary_manager, glossary_entries)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`run(self)`**
  *Description*: Run.

- **`_weave_strings(self)`**
  *Description*: Map chronological transcript timeline to unordered BMG strings  by using the transcript sequence as the primary source of truth, deeply cleaning strings and matching them to BMG indices.

- **`_save_mapped_data_to_local_palace(self, mapped_scenes)`**
  *Description*: Quickly save mapped scenes directly to MemePalace client without AI additions.

- **`_save_single_scene_locally(self, scene, conn)`**
  *Description*: Helper to save a single scene directly without AI queries.

- **`_generate_palace_via_llm(self, mapped_scenes)`**
  *Description*: Query AI Provider to generate deep visual context and relation updates.



#### Class: `Class MemePalaceScriptAnalyzerWorker(QThread)`

*Meme palace script analyzer worker implementation.*


##### Methods

- **`__init__(self, client, file_path, ai_provider, wing_name, glossary_manager, target_lang, plugin_name, mw)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`_load_plugin_prompts(self)`**
  *Description*: Load prompts.json for active plugin if available.

- **`_get_mining_prompts(self, script_segment, prompts_data)`**
  *Description*: Resolve Mining prompts with per-plugin customizations and fallbacks.

- **`_get_synthesis_prompts(self, term_name, existing_notes, details, prompts_data)`**
  *Description*: Resolve Synthesis prompts with per-plugin customizations and fallbacks.

- **`_get_new_term_prompts(self, term_name, details, prompts_data)`**
  *Description*: Resolve New Term prompts with per-plugin customizations and fallbacks.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class MemePalaceChapterMapperWorker(QThread)`

*Meme palace chapter mapper worker implementation.*


##### Methods

- **`__init__(self, client, composer, wing_name)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class MemePalaceChapterAIAnalyzerWorker(QThread)`

*Meme palace chapter a i analyzer worker implementation.*


##### Methods

- **`__init__(self, client, ai_provider, chapter_id, num, title, content, start_line, target_lang, mw)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class MemePalaceCharacterProfilerWorker(QThread)`

*Meme palace character profiler worker implementation.*


##### Methods

- **`__init__(self, client, ai_provider, wing_name, glossary_manager, target_lang, plugin_name, composer, mw)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`_fetch_zelda_wiki_description(self, char_name)`**
  *Description*: Search and fetch character description from Zelda Fandom Wiki.

- **`_translate_wiki_to_target_lang(self, title, text)`**
  *Description*: Translate Zelda Wiki description to the target language immediately using AI.

- **`_load_plugin_prompts(self)`**
  *Description*: Load prompts.json for active plugin if available.

- **`_get_synthesis_prompts(self, term_name, existing_notes, details, prompts_data)`**
  *Description*: Resolve Synthesis prompts with per-plugin customizations and fallbacks.

- **`run(self)`**
  *Description*: Run.



---

### File: [project_manager.py](../../core/project_manager.py)

#### Class: `Class ProjectManager`

*Manager class for loading, saving, and manipulating projects.  The project structure on disk: project_folder/     project.uiproj          # Project metadata file     sources/                # Source files (read-only originals)         file1.txt         file2.txt     translation/            # Translation files (working copies)         file1.txt         file2.txt*


##### Methods

- **`__init__(self, project_path)`**
  *Description*: Initialize ProjectManager.  Args:     project_path: Path to the project directory or .uiproj file

- **`create_new_project(self, project_dir, name, plugin_name, description, source_path, translation_path, is_directory_mode, auto_create_translations)`**
  *Description*: Create a new project structure on disk.  Args:     project_dir: Directory where project file will be created     name: Project name     plugin_name: Active game plugin     description: Optional project description     source_path: External source file or directory     translation_path: External translation file or directory (optional if auto_create is True)     is_directory_mode: True if source_path/translation_path are directories     auto_create_translations: True to auto-create missing translation files  Returns:     True if successful, False otherwise

- **`load(self, path)`**
  *Description*: Load a project from disk.  Args:     path: Path to project directory or .uiproj file  Returns:     True if successful, False otherwise

- **`save(self)`**
  *Description*: Save the current project to disk.  Returns:     True if successful, False otherwise

- **`add_block(self, name, source_file_path, translation_file_path, internal_key, description, target_relative_path)`**
  *Description*: Register a new block (file pair) in the project. Does NOT copy files.  Args:     name: Display name for the block     source_file_path: Relative path to the source file     translation_file_path: Optional relative path to existing translation file     description: Optional block description     target_relative_path: Optional relative directory path (deprecated/ignored)  Returns:     The created Block object, or None on failure

- **`sync_project_files(self, plugin)`**
  *Description*: Synchronizes files from external directories with project blocks. Scans directories recursively for supported extensions, parses Nintendo archives (RARC/U8) in-memory to discover member blocks, explodes multi-block JSON arrays if supported by the plugin, registers newly discovered files as blocks, and removes obsolete blocks.  Args:     plugin (Any): Reference to the active game rules plugin for file formatting and explosions.

- **`import_directory(self, root_dir_path)`**
  *Description*: Legacy functionality for loose imports. Not used in normal external directory modes.

- **`get_uncategorized_lines(self, block_id, total_lines)`**
  *Description*: Get list of line indices that are not assigned to any category.  Args:     block_id: ID of the block     total_lines: Total number of lines in the block  Returns:     List of uncategorized line indices

- **`get_absolute_path(self, relative_path, is_translation)`**
  *Description*: Convert a block-relative path to an absolute path.  Args:     relative_path: Relative path within external source/translation directory     is_translation: Determine whether to use source_path or translation_path  Returns:     Absolute file path

- **`cleanup_temp_dir(self)`**
  *Description*: Clean up temporary resources (no-op since we use in-memory containers).

- **`get_archive_container(self, archive_rel_path, is_translation)`**
  *Description*: Get or open an archive container from cache or file.

- **`clear_archive_cache(self)`**
  *Description*: Clears the in-memory cache of opened archive containers (RARC/U8). Should be called when saving or reloading projects to release file handles and memory.

- **`get_relative_path(self, absolute_path, is_translation)`**
  *Description*: Convert an absolute path to a relative path against external directories.  Args:     absolute_path: Absolute file path     is_translation: True if checking against translation_path  Returns:     Relative path within project

- **`save_settings_to_project(self, main_window)`**
  *Description*: Save project-specific settings from MainWindow to project.metadata.  Args:     main_window: MainWindow instance with settings to save  Returns:     True if successful, False otherwise

- **`load_settings_from_project(self, main_window)`**
  *Description*: Load project-specific settings from project.metadata to MainWindow.  Args:     main_window: MainWindow instance to apply settings to  Returns:     True if successful, False otherwise

- **`current_project(self)`**
  *Description*: Get the currently loaded project.

- **`_migrate_file_structure_to_virtual_folders(self)`**
  *Description*: Builds the virtual folder structure (categories) from the physical file paths of registered blocks. Parses folders and files inside sources/translation directories, registers them as nested VirtualFolder objects, links blocks to their respective leaf folders, and sets project version to '1.1'.

- **`create_virtual_folder(self, name, parent_id)`**
  *Description*: Create a new virtual folder or return existing if name collision at same level.

- **`move_strings_to_category(self, block_idx, string_indices, category_name)`**
  *Description*: Group specific strings within a block into a named virtual category.

- **`merge_folders(self, source_id, target_id)`**
  *Description*: Move all contents from source folder to target folder and delete source.

- **`find_virtual_folder(self, folder_id, search_list)`**
  *Description*: Recursively find a virtual folder by ID.

- **`is_descendant_of(self, potential_child_id, potential_parent_id)`**
  *Description*: Check if folder A is a descendant of folder B.

- **`move_folder_to_folder(self, folder_id, target_folder_id)`**
  *Description*: Move a virtual folder to a new location with safety checks. Returns True if moved, False if skipped (e.g. circular reference).

- **`move_block_to_folder(self, block_id, target_folder_id)`**
  *Description*: Move a block from its current location to a new virtual folder.

- **`_remove_block_id_from_any_folder(self, block_id, search_list)`**
  *Description*: Recursively scans and removes a block ID from any virtual folders or the root block index list.  Args:     block_id (str): The unique ID of the block to remove.     search_list (Optional[List[VirtualFolder]]): The folder level being searched recursively.

- **`get_all_block_indices_under_folder(self, folder_id)`**
  *Description*: Collect indices of all project.blocks within a specific folder subtree.

- **`_remove_folder_from_anywhere(self, folder_id)`**
  *Description*: Recursively searches and removes a virtual folder ID from either the root levels or subfolder children arrays.  Args:     folder_id (str): The unique ID of the folder to delete.      Returns:     bool: True if the folder was successfully located and removed, False otherwise.



---

### File: [project_models.py](../../core/project_models.py)

#### Class: `Class Category`

*Virtual category for organizing strings within a block. Categories exist only as metadata and don't modify source files.*


##### Methods

- **`to_dict(self)`**
  *Description*: Convert category to dictionary for JSON serialization.

- **`from_dict(data)`**
  *Description*: Create category from dictionary.

- **`add_child(self, child)`**
  *Description*: Add a child category.

- **`remove_child(self, child_id)`**
  *Description*: Remove a child category by ID.

- **`find_category(self, category_id)`**
  *Description*: Recursively find a category by ID.



#### Class: `Class VirtualFolder`

*Virtual folder for organizing blocks in the project. Exists only as metadata in .uiproj and does not affect physical layout.*


##### Methods

- **`to_dict(self)`**
  *Description*: To dict.

- **`from_dict(data)`**
  *Description*: From dict.



#### Class: `Class Block`

*Represents a physical file pair (source and translation). This is the main unit of content in a project.*


##### Methods

- **`to_dict(self)`**
  *Description*: Convert block to dictionary for JSON serialization.

- **`from_dict(data)`**
  *Description*: Create block from dictionary.

- **`add_category(self, category)`**
  *Description*: Add a root category to this block.

- **`remove_category(self, category_id)`**
  *Description*: Remove a category by ID.

- **`find_category(self, category_id)`**
  *Description*: Find a category by ID (searches recursively).

- **`get_all_categories_flat(self)`**
  *Description*: Get all categories in a flat list (recursively).

- **`_get_children_recursive(self, category)`**
  *Description*: Helper method to recursively get all children.

- **`get_categorized_line_indices(self)`**
  *Description*: Get all line indices that belong to any category.



#### Class: `Class Project`

*Top-level project container. Represents the entire workspace with all blocks and configuration.*


##### Methods

- **`to_dict(self)`**
  *Description*: Convert project to dictionary for JSON serialization.

- **`from_dict(data)`**
  *Description*: Create project from dictionary.

- **`add_block(self, block)`**
  *Description*: Add a block to the project.

- **`remove_block(self, block_id)`**
  *Description*: Remove a block by ID.

- **`find_block(self, block_id)`**
  *Description*: Find a block by ID.

- **`find_block_by_name(self, name)`**
  *Description*: Find a block by name.



---

### File: [saved_translations_manager.py](../../core/saved_translations_manager.py)

#### Class: `Class SavedTranslationsManager`

*Manager class for saved translations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`_get_saved_translations_path(self)`**
  *Description*: Internal helper to get the saved translations path.

- **`_get_string_unique_key(self, block_idx, string_idx)`**
  *Description*: Internal helper to get the string unique key.

- **`load_all_saved_translations(self)`**
  *Description*: Load all saved translations.

- **`save_all_saved_translations(self, data)`**
  *Description*: Save all saved translations.

- **`has_saved_translation(self, block_idx, string_idx)`**
  *Description*: Check if has saved translation.

- **`get_saved_translation(self, block_idx, string_idx)`**
  *Description*: Get the saved translation.

- **`save_translation(self, block_idx, string_idx, text)`**
  *Description*: Save translation.

- **`save_translations_bulk(self, block_idx, string_indices_and_texts)`**
  *Description*: Save translations bulk.



---

### File: [script_segmenter.py](../../core/script_segmenter.py)

#### Functions

- **`clean_chapter_title(raw_title)`**
  *Description*: Clean up spaced-out letters in chapter titles. e.g. 'S u b s e r v i e n t  T w i l i g h t' -> 'Subservient Twilight'

- **`segment_script_file(script_path)`**
  *Description*: Segment the text script into structured chapters.

---

### File: [service_container.py](../../core/service_container.py)

#### Class: `Class ServiceContainer`

*Service container implementation.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`register(self, service_type, instance)`**
  *Description*: Registers a service instance in the container.

- **`get(self, service_type)`**
  *Description*: Retrieves a registered service instance from the container by its type. Raises KeyError if the service is not registered.



---

### File: [settings_manager.py](../../core/settings_manager.py)

#### Class: `Class SettingsManager`

*Manager class for settings.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`get(self, key, default)`**
  *Description*: Get a setting value from the centralized storage.

- **`set(self, key, value)`**
  *Description*: Set a setting value in the centralized storage.

- **`load_settings(self)`**
  *Description*: Load settings.

- **`save_settings(self, save_project_settings)`**
  *Description*: Save settings.

- **`load_unsaved_session(self)`**
  *Description*: Load unsaved session.

- **`load_all_font_maps(self)`**
  *Description*: Load all font maps.

- **`add_recent_project(self, project_path, max_recent)`**
  *Description*: Add recent project.

- **`remove_recent_project(self, project_path)`**
  *Description*: Remove recent project.

- **`clear_recent_projects(self)`**
  *Description*: Remove recent projects.

- **`save_block_names(self)`**
  *Description*: Save block names.

- **`_update_icon_sequences_cache(self)`**
  *Description*: Internal helper to update the icon sequences cache.

- **`_refresh_icon_highlighting(self)`**
  *Description*: Internal helper to update the icon highlighting.



---

### File: [spellchecker_manager.py](../../core/spellchecker_manager.py)

#### Class: `Class SpellcheckWorker(QObject)`

*Spellcheck worker implementation.*


##### Methods

- **`__init__(self, spellchecker_manager)`**
  *Description*: Initialize a new instance.

- **`process_queue(self)`**
  *Description*: Process queue.

- **`stop(self)`**
  *Description*: Stop.

- **`enqueue(self, word)`**
  *Description*: Enqueue.



#### Class: `Class SpellcheckerManager(QObject)`

*Manager class for spellchecker.*


##### Methods

- **`__init__(self, main_window, language, custom_dict_path)`**
  *Description*: Initialize a new instance.

- **`prepare_to_close(self)`**
  *Description*: Prepare to close.

- **`__del__(self)`**
  *Description*: Internal helper to  del  .

- **`_setup_prefetch_worker(self)`**
  *Description*: Internal helper to setup prefetch worker.

- **`_on_spellcheck_results_ready(self, spell_results, sugg_results)`**
  *Description*: Internal helper to handle the spellcheck results ready event.

- **`_trigger_rehighlight(self)`**
  *Description*: Internal helper to trigger rehighlight.

- **`enqueue_word(self, word)`**
  *Description*: Enqueue word.

- **`_initialize_spellchecker(self)`**
  *Description*: Internal helper to initialize spellchecker.

- **`_load_dictionary_async(self)`**
  *Description*: Internal helper to load dictionary async.

- **`_on_dictionary_loaded(self, hunspell_dict)`**
  *Description*: Internal helper to handle the dictionary loaded event.

- **`_do_initialize_spellchecker(self)`**
  *Description*: Internal helper to do initialize spellchecker.

- **`reload_dictionary(self, language, custom_dict_path)`**
  *Description*: Update the dictionary.

- **`set_enabled(self, enabled)`**
  *Description*: Set the enabled.

- **`scan_local_dictionaries(self)`**
  *Description*: Scans for .dic files and returns a map of language code to full path.

- **`_load_user_dictionary(self)`**
  *Description*: Internal helper to load user dictionary.

- **`reload_glossary_words(self)`**
  *Description*: Public method to reload glossary words. Called after glossary is initialized.

- **`_load_persistent_cache(self)`**
  *Description*: Loads spell check results from a JSON file.

- **`_save_persistent_cache(self)`**
  *Description*: Saves current memory spell cache to disk.

- **`_load_glossary_words(self)`**
  *Description*: Load all words from glossary translations into custom dictionary.

- **`add_to_custom_dictionary(self, word)`**
  *Description*: Add to custom dictionary.

- **`is_misspelled(self, word)`**
  *Description*: Check if is misspelled.

- **`get_suggestions(self, word)`**
  *Description*: Get the suggestions.



---

### File: [state_manager.py](../../core/state_manager.py)

#### Class: `Class AppState(Enum)`

*Enum representing all possible states of the application. This replaces the 46+ boolean flags in MainWindow:  1. is_adjusting_cursor 2. is_adjusting_selection 3. is_programmatically_changing_text 4. is_restart_in_progress 5. is_closing 6. is_loading_data 7. is_saving_data 8. is_reverting_data 9. is_reloading_data 10. is_pasting_block 11. is_undoing_paste 12. is_auto_fixing*




#### Class: `Class StateManager`

*Centralized manager for application states. Prevents recursive events and tracks long-running operations.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`enter(self, state)`**
  *Description*: Context manager to safely enter and exit a state. Usage: with state_manager.enter(AppState.LOADING): ...

- **`is_active(self, state)`**
  *Description*: Check if a specific state is currently active.

- **`any_of(self)`**
  *Description*: Check if any of the given states are active.

- **`set_active(self, state, active)`**
  *Description*: Manually set a state (use sparingly, context manager is preferred).

- **`clear(self)`**
  *Description*: Reset all states.



---

### File: [tag_utils.py](../../core/tag_utils.py)

#### Functions

- **`apply_default_mappings_only(text_segment, default_mappings)`**
  *Description*: Apply default mappings only.

---

### File: [undo_manager.py](../../core/undo_manager.py)

#### Functions

- **`_compress_any(data)`**
  *Description*: Compress data if it's large (strings or dicts).

- **`_decompress_any(data, is_snapshot)`**
  *Description*: Decompress data back to its original form.

#### Class: `Class UndoAction`

*Undo action implementation.*


##### Methods

- **`__init__(self, action_type, block_idx, string_idx, old_text, new_text, timestamp, cursor_pos, metadata)`**
  *Description*: Initialize a new instance.

- **`old_text(self)`**
  *Description*: Old text.

- **`old_text(self, value)`**
  *Description*: Old text.

- **`new_text(self)`**
  *Description*: New text.

- **`new_text(self, value)`**
  *Description*: New text.



#### Class: `Class GroupAction`

*Group action implementation.*




#### Class: `Class StructuralAction`

*Structural action implementation.*


##### Methods

- **`__init__(self, action_type, before_snapshot, after_snapshot, label, timestamp)`**
  *Description*: Initialize a new instance.

- **`before_snapshot(self)`**
  *Description*: Before snapshot.

- **`after_snapshot(self)`**
  *Description*: After snapshot.



#### Class: `Class UndoManager`

*Manager class for undo.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initializes the UndoManager. Maintains the undo and redo execution stacks, sets character-edit grouping thresholds, and manages composite transaction groups.  Args:     main_window (Any): Reference to the central MainWindow controller.

- **`begin_group(self)`**
  *Description*: Begins a new composite transaction group. All subsequent actions recorded prior to end_group will be batched together into a single GroupAction (enabling bulk undo/redo).

- **`end_group(self, action_type)`**
  *Description*: Closes the active transaction group. Bundles all gathered sub-actions into a GroupAction and pushes it to the undo stack.  Args:     action_type (str): Label describing the bulk operation.

- **`_is_word_char(self, c)`**
  *Description*: Internal helper checking if a character belongs to a standard word pattern.  Args:     c (str): Single-character string.      Returns:     bool: True if alphanumeric or underscore, else False.

- **`record_action(self, action_type, block_idx, string_idx, old_text, new_text, metadata)`**
  *Description*: Records a translation text or navigation action and pushes it to the undo stack. For character-by-character typing edits, automatically groups sequential keypresses  occurring within the grouping threshold (3.5 seconds) to avoid cluttering the undo stack.  Args:     action_type (str): Action category (e.g., 'TEXT_EDIT', 'TRANSLATE', 'NAVIGATE').     block_idx (int): The index of the file block.     string_idx (int): The line index within the block.     old_text (str): Prior text state.     new_text (str): Updated text state.     metadata (dict): Optional dictionary of additional action properties.

- **`get_project_snapshot(self)`**
  *Description*: Capture current project + block_names structure for undo purposes.

- **`record_structural_action(self, before_snapshot, action_type, label)`**
  *Description*: Record a structural change (rename, move, folder) for undo/redo.

- **`_apply_project_snapshot(self, snapshot)`**
  *Description*: Restore project structure from a snapshot and refresh UI.

- **`record_navigation(self, block_idx, string_idx, prev_block_idx, prev_string_idx, category, prev_category)`**
  *Description*: Record navigation.

- **`undo(self)`**
  *Description*: Pops the last recorded action or action group from the undo stack, applies the previous text/structural state, registers the item on the redo stack, and refreshes the interface views.

- **`redo(self)`**
  *Description*: Pops the last undone action or group from the redo stack, re-applies the newer text/structural state, returns the item to the undo stack, and refreshes the interface views.

- **`_get_item_location(self, item, is_undo)`**
  *Description*: Internal helper to find the targeted block and string indices of an action.  Args:     item (Any): Target UndoAction or GroupAction.     is_undo (bool): Direction of navigation check.      Returns:     tuple[int, int]: Tuple of (block_idx, string_idx).

- **`_navigate_to(self, block_idx, string_idx, category)`**
  *Description*: Triggers workspace navigation updates to focus the specified block, string, and category.  Args:     block_idx (int): Target block index.     string_idx (int): Target string index.     category (str): Target virtual category.

- **`_apply_data(self, block_idx, string_idx, text, cursor_pos)`**
  *Description*: Applies a text rollback or redo update to both data state and UI widgets.  Args:     block_idx (int): Target block index.     string_idx (int): Target string index.     text (str): Rollback or rollforward text string.     cursor_pos (Optional[int]): Restored cursor position in editor.

- **`clear(self)`**
  *Description*: Clears both the undo and redo stack buffers to release memory snapshots.



---

### File: [base_container.py](../../core/containers/base_container.py)

#### Class: `Class BaseArchiveContainer(ABC)`

*Abstract interface for reading and writing game archive files in-memory.  Implementations must support: - Detecting supported archive formats via can_handle() - Listing all file paths within the archive - Reading individual file contents - Writing (patching) individual file contents in-memory - Packing the (potentially modified) archive back to bytes*


##### Methods

- **`can_handle(cls, data)`**
  *Description*: Return True if this container implementation can parse the given raw bytes.  Args:     data: Raw bytes of the archive file (may be compressed).  Returns:     True if this implementation can handle the format.

- **`__init__(self, data)`**
  *Description*: Initialize and parse the archive from raw bytes.  Args:     data: Raw bytes of the archive file.

- **`list_files(self)`**
  *Description*: Return a list of all file paths within the archive, using forward-slash separators. Does not include directory entries or special entries (., ..).  Returns:     List of unix-style relative paths, e.g. ["Bmgres/bootUp.bmg", "Bmgres/getItem.bmg"]

- **`read_file(self, path)`**
  *Description*: Read the contents of a file from the archive.  If the file was previously modified via write_file(), returns the modified version.  Args:     path: Unix-style path as returned by list_files().  Returns:     Raw bytes of the file.  Raises:     KeyError: If the path does not exist in the archive.

- **`write_file(self, path, data)`**
  *Description*: Stage updated contents for a file in the archive (in-memory only).  The change is not persisted until pack() is called.  Args:     path: Unix-style path as returned by list_files().     data: New raw bytes to store for this file.  Raises:     KeyError: If the path does not exist in the archive.

- **`pack(self)`**
  *Description*: Assemble and return the complete archive as bytes, incorporating any changes made via write_file().  If the original archive was compressed (e.g. Yaz0), the output will also be in the same compressed format.  Returns:     Complete archive bytes ready to be written to disk.

- **`has_pending_changes(self)`**
  *Description*: Return True if any files have been staged for writing.



---

### File: [container_manager.py](../../core/containers/container_manager.py)

#### Class: `Class ContainerManager`

*Factory that selects the appropriate archive container implementation based on the magic bytes of the given raw data.*


##### Methods

- **`open(data)`**
  *Description*: Detect the archive format and return an initialised container instance.  Args:     data: Raw bytes of the archive file (may be Yaz0-compressed).  Returns:     An initialised BaseArchiveContainer subclass, or None if the format     is not recognised.

- **`is_supported(data)`**
  *Description*: Return True if the raw bytes represent a recognised archive format.  Args:     data: Raw bytes of the archive file.  Returns:     True if ContainerManager.open() would succeed.



---

### File: [rarc_container.py](../../core/containers/rarc_container.py)

#### Class: `Class RarcContainer(BaseArchiveContainer)`

*In-memory reader/writer for RARC (and Yaz0-wrapped RARC) archives.  The archive is fully parsed into Python objects on construction. Individual files can be read or replaced (write_file). pack() reassembles the archive bytes, updating data offsets and sizes but preserving the directory/node/string-table structure unchanged.*


##### Methods

- **`can_handle(cls, data)`**
  *Description*: Check if can handle.

- **`__init__(self, data)`**
  *Description*: Initialize a new instance.

- **`_parse(self)`**
  *Description*: Internal helper to parse.

- **`_get_string(self, str_off)`**
  *Description*: Read a null-terminated ASCII string from the string table.

- **`_traverse_node(self, node_idx, prefix, visited)`**
  *Description*: Recursively walk the node tree and populate self._file_paths.

- **`list_files(self)`**
  *Description*: List files.

- **`read_file(self, path)`**
  *Description*: Read file.

- **`write_file(self, path, data)`**
  *Description*: Write file.

- **`pack(self)`**
  *Description*: Reassemble the archive, incorporating any staged writes.  Strategy:   - The structural prefix (RARC header + data header + nodes +     file entries + string table) is copied verbatim.   - File entry data_off and size fields are patched in-place for     changed files.   - The file data section is rebuilt from scratch, with files laid     out in their original order and each aligned to _FILE_DATA_ALIGN.   - RARC header fields (file_size, total_data_size, mram_size) are     updated to reflect the new data section size.  Returns:     Complete RARC bytes (or Yaz0-wrapped RARC if the source was Yaz0).



---

### File: [u8_container.py](../../core/containers/u8_container.py)

#### Class: `Class U8Container(BaseArchiveContainer)`

*In-memory reader/writer for U8 archives (and Yaz0-wrapped U8 archives).*


##### Methods

- **`can_handle(cls, data)`**
  *Description*: Check if can handle.

- **`__init__(self, data)`**
  *Description*: Initialize a new instance.

- **`_parse(self)`**
  *Description*: Internal helper to parse.

- **`_get_string(self, name_off)`**
  *Description*: Internal helper to get the string.

- **`_traverse_dir(self, node_idx, prefix)`**
  *Description*: Internal helper to traverse dir.

- **`list_files(self)`**
  *Description*: List files.

- **`read_file(self, path)`**
  *Description*: Read file.

- **`write_file(self, path, data)`**
  *Description*: Write file.

- **`pack(self)`**
  *Description*: Reassemble the U8 archive, incorporating any staged writes.  Strategy: keep node array and string table verbatim; rebuild the file data section, patching each modified file node's data_off and size.



---

### File: [yaz0.py](../../core/containers/yaz0.py)

#### Functions

- **`decompress(data)`**
  *Description*: Decompress Yaz0-encoded data.  Args:     data: Raw Yaz0-compressed bytes (must start with b"Yaz0").  Returns:     Decompressed bytes.  Raises:     ValueError: If magic bytes are incorrect or data is malformed.

- **`compress(data, max_candidates)`**
  *Description*: Compress data using Yaz0 encoding with a fast LZ77 sliding window algorithm and lazy evaluation (lookahead matching).  This produces highly compressed, valid Yaz0 archives that closely match the compression ratio of official Nintendo tools. This prevents buffer overflows and memory exhaustion crashes in games on real console hardware and emulators.  Args:     data: Raw bytes to compress.     max_candidates: Maximum number of match candidates to evaluate (None for unlimited).  Returns:     Yaz0-compressed bytes starting with the b"Yaz0" magic header.

---

### File: [font_map_loader.py](../../core/settings/font_map_loader.py)

#### Class: `Class FontMapLoader`

*Font map loader implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`load_all_font_maps(self)`**
  *Description*: Load all font maps.

- **`_parse_new_font_format(self, font_data)`**
  *Description*: Parses the new font format and returns a font_map.

- **`_load_font_overrides(self, plugin_name)`**
  *Description*: Internal helper to load font overrides.

- **`_apply_font_overrides(self, overrides)`**
  *Description*: Internal helper to apply font overrides.

- **`refresh_icon_highlighting(self)`**
  *Description*: Update the icon highlighting.

- **`update_icon_sequences_cache(self)`**
  *Description*: Update the icon sequences cache.



---

### File: [global_settings.py](../../core/settings/global_settings.py)

#### Class: `Class GlobalSettings`

*Global settings implementation.*


##### Methods

- **`__init__(self, main_window, settings_file_path)`**
  *Description*: Initialize a new instance.

- **`_get_defaults(self)`**
  *Description*: Internal helper to get the defaults.

- **`load(self, settings_dict)`**
  *Description*: Loads global settings into the provided settings_dict and updates MainWindow.

- **`save(self, settings_dict)`**
  *Description*: Saves current global settings to settings.json.



---

### File: [plugin_settings.py](../../core/settings/plugin_settings.py)

#### Class: `Class PluginSettings`

*Plugin settings implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`_get_plugin_config_path(self)`**
  *Description*: Internal helper to get the plugin config path.

- **`_get_project_settings_path(self)`**
  *Description*: Internal helper to get the project settings path.

- **`_substitute_env_vars(self, data)`**
  *Description*: Recursively substitute environment variables in data structure.

- **`load(self, settings_dict)`**
  *Description*: Loads plugin-specific settings.

- **`_migrate_legacy_styles(self, plugin_data)`**
  *Description*: Internal helper to migrate legacy styles.

- **`save(self)`**
  *Description*: Saves current settings to project_settings.json inside the project directory.

- **`save_block_names(self)`**
  *Description*: Save block names.



---

### File: [recent_projects_manager.py](../../core/settings/recent_projects_manager.py)

#### Class: `Class RecentProjectsManager`

*Manager class for recent projects.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`add_recent_project(self, project_path, max_recent)`**
  *Description*: Add a project to the recent projects list.

- **`remove_recent_project(self, project_path)`**
  *Description*: Remove a project from the recent projects list.

- **`clear_recent_projects(self)`**
  *Description*: Clear all recent projects.



---

### File: [session_state_manager.py](../../core/settings/session_state_manager.py)

#### Class: `Class SessionStateManager`

*Manages the UI session state (expanded nodes, selection, etc.)*


##### Methods

- **`__init__(self, settings_file_path)`**
  *Description*: Initialize a new instance.

- **`load(self)`**
  *Description*: Load .

- **`save(self)`**
  *Description*: Save .

- **`get_state_for_file(self, file_path_key)`**
  *Description*: Returns the state dictionary for a specific file/project path.

- **`set_state_for_file(self, file_path_key, state_data)`**
  *Description*: Set the state for file.

- **`cleanup_old_states(self, max_entries)`**
  *Description*: Cleanup old states.



---

### File: [config.py](../../core/translation/config.py)

#### Functions

- **`merge_translation_config(base, custom)`**
  *Description*: Recursively merge custom config into base, avoiding deep mutation.

- **`build_default_translation_config()`**
  *Description*: Create default translation config.

---

### File: [providers.py](../../core/translation/providers.py)

#### Functions

- **`create_translation_provider(provider_key, settings)`**
  *Description*: Factory function to create a translation provider instance.

- **`get_provider_for_config(config)`**
  *Description*: Initializes and returns a translation provider based on a configuration dictionary. This is intended for one-off tasks like glossary building.

#### Class: `Class TranslationProviderError(Exception)`

*Custom exception for provider-related errors.*




#### Class: `Class ProviderResponse`

*Standardized response from a translation provider.*




#### Class: `Class BaseTranslationProvider`

*Base translation provider implementation.*


##### Methods

- **`__init__(self, settings)`**
  *Description*: Initialize a new instance.

- **`translate(self, messages, session, settings_override)`**
  *Description*: Translate.

- **`translate_stream(self, messages, session, settings_override)`**
  *Description*: Translate stream.



#### Class: `Class OpenAIProvider(BaseTranslationProvider)`

*Open a i provider implementation.*


##### Methods

- **`__init__(self, settings)`**
  *Description*: Initialize a new instance.

- **`_prepare_body(self, messages, current_settings)`**
  *Description*: Internal helper to prepare body.

- **`translate(self, messages, session, settings_override)`**
  *Description*: Translate.

- **`translate_stream(self, messages, session, settings_override)`**
  *Description*: Translate stream.



#### Class: `Class OllamaChatProvider(BaseTranslationProvider)`

*Ollama chat provider implementation.*


##### Methods

- **`__init__(self, settings)`**
  *Description*: Initialize a new instance.

- **`translate(self, messages, session, settings_override)`**
  *Description*: Translate.

- **`translate_stream(self, messages, session, settings_override)`**
  *Description*: Translate stream.



#### Class: `Class GeminiProvider(BaseTranslationProvider)`

*Gemini provider implementation.*


##### Methods

- **`__init__(self, settings)`**
  *Description*: Initialize a new instance.

- **`start_new_chat_session(self)`**
  *Description*: If using a custom base URL, attempts to start a new chat session.

- **`translate(self, messages, session, settings_override)`**
  *Description*: Translate.

- **`translate_stream(self, messages, session, settings_override)`**
  *Description*: Translate stream.

- **`_translate_via_openai_compat(self, messages, headers, current_settings, timeout)`**
  *Description*: Internal helper to translate via openai compat.

- **`_translate_via_native_api(self, messages, headers, current_settings, timeout)`**
  *Description*: Internal helper to translate via native api.

- **`_translate_via_native_stream(self, messages, headers, current_settings, timeout)`**
  *Description*: Internal helper to translate via native stream.



---

### File: [session_manager.py](../../core/translation/session_manager.py)

#### Class: `Class TranslationSessionState`

*Active provider session state.*


##### Methods

- **`set_instructions(self, instructions)`**
  *Description*: Set the instructions.

- **`prepare_request(self, user_message)`**
  *Description*: Return request messages and optional session payload.

- **`record_exchange(self)`**
  *Description*: Record the exchange and persist the conversation identifier.

- **`compress_history(self, provider)`**
  *Description*: Compress the oldest part of the history when it exceeds limits using the provider.



#### Class: `Class TranslationSessionManager`

*Manage creation and reset of translation sessions.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`reset(self)`**
  *Description*: Reset.

- **`ensure_session(self)`**
  *Description*: Ensure session.

- **`get_state(self)`**
  *Description*: Get the state.



---

## Component: `handlers`

### File: [ai_chat_handler.py](../../handlers/ai_chat_handler.py)

#### Class: `Class AIChatHandler(BaseHandler)`

*Handler for a i chat operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_get_available_providers(self)`**
  *Description*: Internal helper to get the available providers.

- **`show_chat_window(self, initial_text)`**
  *Description*: Show chat window.

- **`_add_new_chat_session(self)`**
  *Description*: Internal helper to add new chat session.

- **`_handle_tab_closed(self, index)`**
  *Description*: Internal helper to handle tab closed.

- **`_handle_send_message(self, tab_index, message, provider_key, web_search_enabled)`**
  *Description*: Internal helper to handle send message.

- **`_process_annotations(self, text, annotations)`**
  *Description*: Internal helper to process annotations.

- **`_format_ai_response_for_display(self, text, annotations)`**
  *Description*: Internal helper to format ai response for display.

- **`_on_ai_chunk_received(self, context, chunk)`**
  *Description*: Internal helper to handle the ai chunk received event.

- **`_on_ai_stream_finished(self, response, context)`**
  *Description*: Internal helper to handle the ai stream finished event.

- **`_on_ai_chat_success(self, response, context)`**
  *Description*: Internal helper to handle the ai chat success event.

- **`_on_ai_error(self, message, context)`**
  *Description*: Internal helper to handle the ai error event.

- **`_cleanup_worker(self)`**
  *Description*: Internal helper to cleanup worker.

- **`prepare_to_close(self)`**
  *Description*: Prepare to close.



---

### File: [app_action_handler.py](../../handlers/app_action_handler.py)

#### Class: `Class SaveWorker(QThread)`

*Save worker implementation.*


##### Methods

- **`__init__(self, data_processor, output_data_list)`**
  *Description*: Initialize a new instance.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class AppActionHandler(BaseHandler)`

*Handler for app action operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater, game_rules_plugin)`**
  *Description*: Initialize a new instance.

- **`rescan_all_tags(self)`**
  *Description*: Rescan all tags.

- **`handle_close_event(self, event)`**
  *Description*: Handle close event.

- **`_derive_edited_path(self, original_path)`**
  *Description*: Internal helper to derive edited path.

- **`open_file_dialog_action(self)`**
  *Description*: Open file dialog action.

- **`open_changes_file_dialog_action(self)`**
  *Description*: Open changes file dialog action.

- **`save_data_action(self, ask_confirmation)`**
  *Description*: High-level save action that delegates to the data processor.

- **`perform_async_save_flow(self, output_data_list, ask_confirmation)`**
  *Description*: Perform async save flow.

- **`save_as_dialog_action(self)`**
  *Description*: Save as dialog action.

- **`load_all_data_for_path(self, original_file_path, manually_set_edited_path, is_initial_load_from_settings)`**
  *Description*: Load all data for path.

- **`reload_original_data_action(self)`**
  *Description*: Update the original data action.

- **`calculate_widths_for_block_action(self, block_idx, category_name)`**
  *Description*: Calculate widths for block action.

- **`_perform_initial_silent_scan_all_issues(self)`**
  *Description*: Internal helper to perform initial silent scan all issues.



---

### File: [async_issue_scanner.py](../../handlers/async_issue_scanner.py)

#### Functions

- **`get_scanner_thread_pool()`**
  *Description*: Shared single-slot thread pool for AsyncIssueScanner.  A single max-thread slot is enough because scans are debounced per keystroke and superseded by newer scans via cooperative cancellation. Anything more would just waste CPU racing the latest input.

#### Class: `Class _ScannerSignals(QObject)`

*QRunnable can't carry signals itself; this QObject is its signal sink.*




#### Class: `Class AsyncIssueScanner(QRunnable)`

*Background worker that runs the per-string analysis pipeline.  Cooperative cancellation: callers may invoke ``cancel()`` to ask the runnable to exit at the next checkpoint. The runnable never emits its ``finished_scan`` signal after being cancelled, so the caller does not need to disconnect from it; just call ``cancel()`` and drop the reference.*


##### Methods

- **`__init__(self, block_idx, string_idx, text, font_map, width_threshold, analyzer, glossary_manager, spellchecker_manager, source_text, active_word, warnings_enabled, glossary_enabled, editor_text, logical_hard_limit)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Ask the runnable to stop ASAP. The runnable will not emit its finished_scan signal after this is called.

- **`is_cancelled(self)`**
  *Description*: Check if is cancelled.

- **`isRunning(self)`**
  *Description*: Isrunning.

- **`finished_scan(self)`**
  *Description*: Expose the underlying signal as if it lived on the runnable.  TextOperationHandler historically did ``self.current_scanner_thread.finished_scan.connect(...)``; preserve that ergonomics so we don't have to touch all the call sites.

- **`run(self)`**
  *Description*: Run.

- **`_run_warnings(self)`**
  *Description*: Internal helper to run warnings.

- **`_run_glossary_matches(self)`**
  *Description*: Internal helper to run glossary matches.

- **`_run_translation_matches(self)`**
  *Description*: Internal helper to run translation matches.

- **`_run_spellcheck(self)`**
  *Description*: Internal helper to run spellcheck.



---

### File: [base_handler.py](../../handlers/base_handler.py)

#### Class: `Class BaseHandler`

*Handler for base operations.*


##### Methods

- **`__init__(self, context, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`mw(self)`**
  *Description*: Temporary property for backward compatibility during refactoring.

- **`state(self)`**
  *Description*: State.

- **`data_store(self)`**
  *Description*: Data store.



---

### File: [bookmark_handler.py](../../handlers/bookmark_handler.py)

#### Class: `Class BookmarkHandler(BaseHandler)`

*Handler for managing and navigating text line bookmarks. Bookmarks are saved persistently inside settings.json.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`add_bookmark(self)`**
  *Description*: Create a new bookmark at the current line of the active block.

- **`jump_to_bookmark(self, bookmark_id)`**
  *Description*: Navigate to the block and line index specified by the bookmark.

- **`clear_bookmarks(self)`**
  *Description*: Clear all saved bookmarks after user confirmation.

- **`delete_bookmark(self, bookmark_id)`**
  *Description*: Delete a single bookmark by ID after user confirmation.

- **`update_bookmarks_menu(self)`**
  *Description*: Redraw bookmarks dynamically in the Bookmarks menu.



---

### File: [issue_scan_handler.py](../../handlers/issue_scan_handler.py)

#### Class: `Class IssueScanHandler(BaseHandler)`

*Handler for issue scan operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_get_string_thresholds(self, block_idx, string_idx)`**
  *Description*: Internal helper to get the string thresholds.

- **`_get_block_file_for_mtime(self, block_idx)`**
  *Description*: Internal helper to get the block file for mtime.

- **`_get_cache_path(self)`**
  *Description*: Internal helper to get the cache path.

- **`_save_issues_cache(self)`**
  *Description*: Internal helper to save issues cache.

- **`_load_issues_cache(self)`**
  *Description*: Internal helper to load issues cache.

- **`_perform_issues_scan_for_block(self, block_idx, is_single_block_scan, use_default_mappings_in_scan)`**
  *Description*: Internal helper to perform issues scan for block.

- **`_show_scan_progress_dialog(self, pending_scan_indices)`**
  *Description*: Internal helper to show scan progress dialog.

- **`_perform_initial_silent_scan_all_issues(self)`**
  *Description*: Start (or restart) an scan of all blocks, loading from cache if valid.

- **`_scan_next_batch(self)`**
  *Description*: Process one batch of blocks and schedule the next batch.

- **`rescan_issues_for_single_block(self, block_idx, show_message_on_completion, use_default_mappings)`**
  *Description*: Rescan issues for single block.

- **`rescan_all_tags(self)`**
  *Description*: Rescan all tags.



---

### File: [list_selection_handler.py](../../handlers/list_selection_handler.py)

#### Class: `Class ListSelectionHandler(BaseHandler)`

*Handler for list selection operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`navigate_between_blocks(self, forward)`**
  *Description*: Handle global Alt+Shift+Up/Down to jump to next/prev block in the tree.

- **`navigate_between_folders(self, forward)`**
  *Description*: Handle global Alt+Shift+Left/Right to jump to next/prev folder in the tree.

- **`block_selected(self, current_item, previous_item)`**
  *Description*: Block selected.

- **`_restore_block_selection(self)`**
  *Description*: Internal helper to restore block selection.

- **`_update_block_toolbar_button_states(self, block_idx)`**
  *Description*: Update the enabled/disabled state of toolbar buttons based on selection and position.

- **`resolve_bmg_id_to_indices(self, bmg_id)`**
  *Description*: Resolve a BMG ID like 'main_Str_125' to (block_idx, string_idx).

- **`select_string_by_absolute_index(self, absolute_idx)`**
  *Description*: Select a string using its absolute index in block data, handling relative mapping automatically.

- **`string_selected_from_preview(self, line_number, is_manual_click)`**
  *Description*: String selected from preview.

- **`rename_block(self, item)`**
  *Description*: Rename block.

- **`handle_block_item_text_changed(self, item, column)`**
  *Description*: Handle inline renaming of block or folder.

- **`_data_string_has_any_problem(self, block_idx, string_idx)`**
  *Description*: Internal helper to data string has any problem.

- **`navigate_to_problem_string(self, direction_down)`**
  *Description*: Navigate to problem string.

- **`handle_preview_selection_changed(self, selected_lines)`**
  *Description*: Handle preview selection changed.

- **`move_selection_to_category(self)`**
  *Description*: Move selected strings to a virtual block (Category).

- **`rename_category(self, block_idx, old_name)`**
  *Description*: Rename a virtual block.

- **`delete_category(self, block_idx, category_name)`**
  *Description*: Remove a virtual block (the strings remain in the block).

- **`toggle_highlight_categorized(self, checked)`**
  *Description*: Toggle highlighting of categorized strings in parent block.

- **`toggle_hide_categorized(self, checked)`**
  *Description*: Toggle hiding of categorized strings in parent block.

- **`toggle_hide_empty_strings(self, checked)`**
  *Description*: Toggle hiding of empty strings in preview list.

- **`toggle_hide_translated(self, checked)`**
  *Description*: Toggle hiding of translated strings in preview list.

- **`toggle_show_overrides_only(self, checked)`**
  *Description*: Toggle showing only strings with layout overrides in preview list.

- **`toggle_hide_original_tags(self, checked)`**
  *Description*: Toggle hiding of tags in the original text edit.

- **`toggle_hide_translation_tags(self, checked)`**
  *Description*: Toggle hiding of tags in the translation and preview text edits.

- **`scroll_to_current_string_in_preview(self)`**
  *Description*: Scroll and focus the preview text edit to the currently selected string.

- **`_get_displayed_indices(self)`**
  *Description*: Internal helper to get the displayed indices.



---

### File: [project_action_handler.py](../../handlers/project_action_handler.py)

#### Class: `Class ProjectActionHandler(BaseHandler)`

*Handler for project action operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_set_project_actions_enabled(self, enabled)`**
  *Description*: Enable or disable project-specific UI actions and update their tooltips.

- **`create_new_project_action(self)`**
  *Description*: Create new project action.

- **`open_project_action(self)`**
  *Description*: Open project action.

- **`close_project_action(self)`**
  *Description*: Close project action.

- **`import_block_action(self)`**
  *Description*: Import block action.

- **`import_directory_action(self)`**
  *Description*: Import directory action.

- **`delete_block_action(self)`**
  *Description*: Remove block action.

- **`move_block_action(self, direction)`**
  *Description*: direction: -1 for up, +1 for down.

- **`add_folder_action(self)`**
  *Description*: Add folder action.

- **`add_items_to_folder_action(self)`**
  *Description*: Add items to folder action.

- **`_populate_blocks_from_project(self)`**
  *Description*: Populate block list from current project and load data.

- **`_update_recent_projects_menu(self)`**
  *Description*: Update the Recent Projects submenu with current list.

- **`_open_recent_project(self, project_path)`**
  *Description*: Open a project from the recent projects list.

- **`_clear_recent_projects(self)`**
  *Description*: Clear all recent projects.

- **`expand_all_action(self)`**
  *Description*: Expand all nodes in the tree.

- **`collapse_all_action(self)`**
  *Description*: Collapse all nodes in the tree.

- **`_update_all_folder_expansion_state(self, expanded)`**
  *Description*: Internal helper to update the all folder expansion state.



---

### File: [saved_translations_handler.py](../../handlers/saved_translations_handler.py)

#### Class: `Class SavedTranslationsHandler(BaseHandler)`

*Handler for saved translations operations.*


##### Methods

- **`__init__(self, context, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`restore_translation(self, block_idx, string_idx)`**
  *Description*: Restore translation.

- **`restore_translations_for_strings(self, block_idx, string_indices)`**
  *Description*: Restore translations for strings.

- **`restore_translations_for_block(self, block_idx)`**
  *Description*: Restore translations for block.

- **`restore_all_saved_translations_action(self)`**
  *Description*: Restore all saved translations action.

- **`save_translation_action(self)`**
  *Description*: Save translation action.

- **`restore_translation_action(self)`**
  *Description*: Restore translation action.

- **`export_translations_to_json_action(self)`**
  *Description*: Export translations to json action.

- **`import_translations_from_json_action(self)`**
  *Description*: Import translations from json action.



---

### File: [search_handler.py](../../handlers/search_handler.py)

#### Class: `Class SearchHandler(BaseHandler)`

*Handler for search operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`get_current_search_params(self)`**
  *Description*: Get the current search params.

- **`_get_text_for_search(self, block_idx, string_idx, search_in_original_flag, ignore_tags_flag)`**
  *Description*: Internal helper to get the text for search.

- **`reset_search(self, new_query, new_case_sensitive, new_search_in_original, new_ignore_tags)`**
  *Description*: Reset search.

- **`_find_in_text(self, text_to_search_in, query_to_find, start_offset, case_sensitive, find_reverse, is_fuzzy)`**
  *Description*: Returns (match_position, matched_length) or (-1, 0) if not found.

- **`_update_search_state(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Internal helper to update the search state.

- **`find_next(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Find next.

- **`find_previous(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Find previous.

- **`_find(self, direction)`**
  *Description*: Internal helper to find.

- **`_find_nth_occurrence_in_display_text(self, display_text, display_query, target_occurrence, case_sensitive)`**
  *Description*: Internal helper to find nth occurrence in display text.

- **`_calculate_qtextblock_and_pos_in_block(self, raw_text_line_with_newlines, char_pos_in_raw_string_with_newlines)`**
  *Description*: Internal helper to calculate qtextblock and pos in block.

- **`_navigate_to_match(self, block_idx_match_in_data, string_idx_match_in_data, char_pos_in_search_text, match_len_in_search_text, was_search_tagless_and_newline_agnostic)`**
  *Description*: Internal helper to navigate to match.

- **`clear_all_search_highlights(self)`**
  *Description*: Remove all search highlights.



---

### File: [string_settings_handler.py](../../handlers/string_settings_handler.py)

#### Class: `Class StringSettingsHandler(BaseHandler)`

*Handler for string settings operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_apply_and_rescan(self)`**
  *Description*: Internal helper to apply and rescan.

- **`on_font_changed(self, index)`**
  *Description*: Handle the font changed event.

- **`on_width_changed(self, value)`**
  *Description*: Handle the width changed event.

- **`apply_settings_change(self)`**
  *Description*: Apply settings change.

- **`apply_font_to_range(self, start_line, end_line, font_file)`**
  *Description*: Apply font to range.

- **`apply_font_to_lines(self, line_indices, font_file)`**
  *Description*: Apply font to lines.

- **`apply_font_to_block(self, block_idx, font_file)`**
  *Description*: Apply font to block.

- **`apply_width_to_lines(self, line_indices, width)`**
  *Description*: Apply width to lines.

- **`apply_width_to_range(self, start_line, end_line, width)`**
  *Description*: Apply width to range.

- **`apply_auto_width_from_original_to_lines(self, line_indices)`**
  *Description*: Apply auto width from original to lines.



---

### File: [text_analysis_handler.py](../../handlers/text_analysis_handler.py)

#### Class: `Class TextAnalysisHandler(BaseHandler)`

*Builds data for the top longest lines and shows the dialog.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`ensure_menu_action(self)`**
  *Description*: Ensure menu action.

- **`analyze_original_text(self)`**
  *Description*: Analyze original text.

- **`_activate_entry(self, entry)`**
  *Description*: Internal helper to activate entry.

- **`show_diagnostic_analysis(self, entries, title, all_fonts_top_entries)`**
  *Description*: Show the analysis dialog with pre-calculated results for a block or fragment.



---

### File: [text_autofix_logic.py](../../handlers/text_autofix_logic.py)

#### Class: `Class TextAutofixLogic`

*Text autofix logic implementation.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_ends_with_sentence_punctuation(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation.

- **`_extract_first_word_with_tags(self, text)`**
  *Description*: Internal helper to extract first word with tags.

- **`_fix_empty_odd_sublines(self, text)`**
  *Description*: Internal helper to fix empty odd sublines.

- **`_fix_short_lines(self, text, width_threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines.

- **`_fix_width_exceeded(self, text, width_threshold)`**
  *Description*: Internal helper to fix width exceeded.

- **`_fix_blue_sublines(self, text)`**
  *Description*: Internal helper to fix blue sublines.

- **`_fix_leading_spaces_in_sublines(self, text)`**
  *Description*: Internal helper to fix leading spaces in sublines.

- **`_cleanup_spaces_around_tags(self, text)`**
  *Description*: Internal helper to cleanup spaces around tags.

- **`auto_fix_current_string(self)`**
  *Description*: Auto fix current string.



---

### File: [text_operation_handler.py](../../handlers/text_operation_handler.py)

#### Class: `Class TextOperationHandler(BaseHandler)`

*Handler for text operation operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`_get_string_thresholds(self, block_idx, string_idx)`**
  *Description*: Internal helper to get the string thresholds.

- **`_rescan_issues_for_current_string(self, block_idx, string_idx, new_text)`**
  *Description*: Internal helper to rescan issues for current string.

- **`_launch_async_scanner_for_fixed_text(self, block_idx, string_idx, fixed_data, font_map, width_threshold, logical_hard_limit)`**
  *Description*: Launch a new AsyncIssueScanner for the given (fixed) text.  Called after AutoFix completes (regardless of whether the text changed). The scanner updates glossary / spellcheck highlights in the background without blocking the UI. Because the sync rescan already populated problems_per_subline with the correct results, we keep the scanner output consistent by scanning the same fixed_data — the async result should match.

- **`_log_undo_state(self, editor, context_message)`**
  *Description*: Internal helper to log undo state.

- **`_update_preview_content(self)`**
  *Description*: Internal helper to update the preview content.

- **`stop_and_flush_editor_changes(self)`**
  *Description*: Stop and flush editor changes.

- **`text_edited(self)`**
  *Description*: Text edited.

- **`_on_preview_update_timer_timeout(self)`**
  *Description*: Internal helper to handle the preview update timer timeout event.

- **`_on_issue_scan_finished(self, block_idx, string_idx, text, problems_in_string, glossary_matches, translation_matches, spellcheck_matches)`**
  *Description*: Internal helper to handle the issue scan finished event.

- **`sync_subline_asterisks(self, block_idx, string_idx, current_text)`**
  *Description*: Compares the current text of a string with its original version from the file  and updates mw.data_store.edited_sublines to show asterisks (*) on modified sublines in the editor.

- **`paste_block_text(self)`**
  *Description*: Paste block text.

- **`revert_single_line(self, line_index)`**
  *Description*: Revert single line.

- **`calculate_width_for_data_line_action(self, data_line_idx)`**
  *Description*: Calculate width for data line action.

- **`auto_fix_current_string(self, from_button)`**
  *Description*: Auto fix current string.

- **`_auto_fix_current_string_impl(self, allowed_problems, page_local)`**
  *Description*: Internal helper to auto fix current string impl.

- **`fix_all_strings(self, target_strings)`**
  *Description*: Fix all strings.



---

### File: [translation_handler.py](../../handlers/translation_handler.py)

#### Class: `Class TranslationHandler(BaseHandler)`

*Handler for translation operations.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`save_progress_to_metadata(self, block_idx)`**
  *Description*: Saves translation progress for a single block into the block's project metadata.

- **`load_progress_from_metadata(self)`**
  *Description*: Loads translation progress for all blocks from their project metadata.

- **`initialize_glossary_highlighting(self)`**
  *Description*: Initialize glossary highlighting.

- **`show_glossary_dialog(self, initial_term)`**
  *Description*: Show glossary dialog.

- **`get_glossary_entry(self, term)`**
  *Description*: Get the glossary entry.

- **`add_glossary_entry(self, term, context, translation)`**
  *Description*: Add glossary entry.

- **`edit_glossary_entry(self, term, translation)`**
  *Description*: Edit glossary entry.

- **`append_selection_to_glossary(self)`**
  *Description*: Append selection to glossary.

- **`_prepare_provider(self, provider_key_override)`**
  *Description*: Internal helper to prepare provider.

- **`reset_translation_session(self)`**
  *Description*: Reset translation session.

- **`_maybe_edit_prompt(self)`**
  *Description*: Internal helper to maybe edit prompt.

- **`_should_use_session(self, task_type)`**
  *Description*: Internal helper to check if should use session.

- **`_prepare_session_for_request(self)`**
  *Description*: Internal helper to prepare session for request.

- **`_attach_session_to_task(self, task_details)`**
  *Description*: Internal helper to attach session to task.

- **`_set_notes_dialog_busy(self, dialog_obj, busy)`**
  *Description*: Internal helper to set the notes dialog busy.

- **`_run_ai_task(self, provider, task_details)`**
  *Description*: Internal helper to run ai task.

- **`_handle_ai_cancel(self, context)`**
  *Description*: Internal helper to handle ai cancel.

- **`prompt_for_revert_after_cancel(self)`**
  *Description*: Prompt for revert after cancel.

- **`_setup_progress_bar(self, total_chunks, completed_chunks)`**
  *Description*: Internal helper to setup progress bar.

- **`translate_current_string(self)`**
  *Description*: Translate current string.

- **`translate_preview_selection(self, context_menu_pos)`**
  *Description*: Translate preview selection.

- **`translate_current_block(self, block_idx, category_name, chapter_id)`**
  *Description*: Translate current block.

- **`resume_block_translation(self, block_idx)`**
  *Description*: Resume block translation.

- **`_on_chunk_timer_timeout(self)`**
  *Description*: Internal helper to handle the chunk timer timeout event.

- **`_resolve_base_timeout(self, provider)`**
  *Description*: Internal helper to resolve base timeout.

- **`_format_and_wrap_translation(self, text, block_idx, string_idx)`**
  *Description*: Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels  and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.

- **`_initiate_batch_translation(self, context)`**
  *Description*: Internal helper to initiate batch translation.

- **`_handle_chunk_translated(self, chunk_index, chunk_text, context)`**
  *Description*: Internal helper to handle chunk translated.

- **`_handle_preview_translation_success(self, response, context)`**
  *Description*: Internal helper to handle preview translation success.

- **`_handle_ai_error(self, error_msg, context)`**
  *Description*: Internal helper to handle ai error.

- **`_handle_single_translation_success(self, response, context)`**
  *Description*: Internal helper to handle single translation success.

- **`_on_task_finished(self, context)`**
  *Description*: Internal helper to handle the task finished event.

- **`generate_variation_for_current_string(self, force)`**
  *Description*: Generate variation for current string.

- **`_translate_and_apply(self)`**
  *Description*: Internal helper to translate and apply.

- **`_handle_block_translation_success(self, response, context)`**
  *Description*: Internal helper to handle block translation success.

- **`translate_selected_lines(self)`**
  *Description*: Translates the lines currently selected in the preview editor. If no lines are selected, translates the current string.

- **`translate_all_blocks_chronologically(self)`**
  *Description*: Translate all blocks chronologically.



---

### File: [virtual_folder_handler.py](../../handlers/virtual_folder_handler.py)

#### Class: `Class VirtualFolderHandler(BaseHandler)`

*Handles virtual folder management operations within projects,  such as folder creation, deletion, moving items, and managing expansion state.*


##### Methods

- **`__init__(self, main_window, data_processor, ui_updater)`**
  *Description*: Initialize a new instance.

- **`add_folder_action(self)`**
  *Description*: Add folder action.

- **`add_items_to_folder_action(self)`**
  *Description*: Move multiple selected items into a folder.

- **`delete_folder_action(self, folder_id, current_item)`**
  *Description*: Deletes a virtual folder from the project tree, optionally preserving or removing its content.

- **`update_all_folder_expansion_state(self, expanded)`**
  *Description*: Recursively update the is_expanded state for all virtual folders.



---

### File: [width_calculation_worker.py](../../handlers/width_calculation_worker.py)

#### Class: `Class WidthCalculationWorker(QThread)`

*Width calculation worker implementation.*


##### Methods

- **`__init__(self, block_idx, block_data, block_name, font_map_helper, data_processor, game_rules_plugin, mw_settings, all_font_maps, target_indices, parent)`**
  *Description*: Initialize a new instance.

- **`cancel(self)`**
  *Description*: Cancel.

- **`run(self)`**
  *Description*: Run.



---

### File: [ai_lifecycle_manager.py](../../handlers/translation/ai_lifecycle_manager.py)

#### Class: `Class AILifecycleManager(BaseTranslationHandler)`

*Manager class for a i lifecycle.*


##### Methods

- **`__init__(self, main_handler)`**
  *Description*: Initialize a new instance.

- **`register_handler(self, task_type, success_cb, error_cb, chunk_cb)`**
  *Description*: Register handler.

- **`_prepare_provider(self, provider_key_override)`**
  *Description*: Internal helper to prepare provider.

- **`run_ai_task(self, provider, task_details)`**
  *Description*: Run ai task.

- **`_on_thread_finished(self)`**
  *Description*: Internal helper to handle the thread finished event.

- **`_on_success(self, response, context)`**
  *Description*: Internal helper to handle the success event.

- **`_on_chunk_translated(self, chunk_index, chunk_text, context)`**
  *Description*: Internal helper to handle the chunk translated event.

- **`_on_worker_cancelled(self)`**
  *Description*: Internal helper to handle the worker cancelled event.

- **`_on_error(self, error_message, context)`**
  *Description*: Internal helper to handle the error event.

- **`_handle_task_error(self, error_message, context)`**
  *Description*: Internal helper to handle task error.

- **`_record_session_exchange(self)`**
  *Description*: Internal helper to record session exchange.

- **`_clean_model_output(self, raw_output, expect_json)`**
  *Description*: Internal helper to clean model output.

- **`_trim_trailing_whitespace_from_lines(self, text)`**
  *Description*: Internal helper to trim trailing whitespace from lines.

- **`_on_retry_timer_timeout(self)`**
  *Description*: Internal helper to handle the retry timer timeout event.

- **`_perform_retry(self)`**
  *Description*: Internal helper to perform retry.

- **`prepare_to_close(self)`**
  *Description*: Prepare to close.



---

### File: [ai_prompt_composer.py](../../handlers/translation/ai_prompt_composer.py)

#### Class: `Class AIPromptComposer(BaseTranslationHandler)`

*Compose prompts for AI translation/variation tasks and manage placeholders.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`prepare_text_for_translation(self, source_text, glossary_entries)`**
  *Description*: Prepare text for translation.

- **`restore_placeholders(self, translated_text, placeholder_map)`**
  *Description*: Restore placeholders.

- **`compose_batch_request(self, system_prompt, source_items, all_source_items)`**
  *Description*: Compose batch request.

- **`compose_variation_request(self, system_prompt, source_text)`**
  *Description*: Compose variation request.

- **`compose_messages(self, system_prompt, source_text)`**
  *Description*: Compose messages.

- **`compose_glossary_occurrence_update_request(self, system_prompt)`**
  *Description*: Compose glossary occurrence update request.

- **`compose_glossary_occurrence_batch_request(self, system_prompt)`**
  *Description*: Compose glossary occurrence batch request.

- **`compose_glossary_request(self, system_prompt, user_content)`**
  *Description*: Compose glossary request.

- **`_append_speaker_glossary_entries(self, relevant_entries, speaker_candidates)`**
  *Description*: Find speaker names in the glossary and append them to relevant_entries.

- **`_glossary_entries_to_text(entries)`**
  *Description*: Format glossary entries into a markdown table.

- **`_prepare_glossary_for_prompt(self, system_prompt, session_state, is_batch_translation)`**
  *Description*: Prepare the system prompt. Now returns the system prompt as-is for glossary unification.

- **`_get_mempalace_client(self)`**
  *Description*: Dynamically get or initialize MemePalaceClient for current project directory.

- **`_get_wing_name(self)`**
  *Description*: Deduce clean active wing/game identifier.

- **`_get_block_label(self, block_idx)`**
  *Description*: Get friendly display label for a project file block index.

- **`_fetch_story_context(self, block_idx, s_idx, text)`**
  *Description*: Query the local SQLite database for visual scene description, character status and timeline info.

- **`_find_script_path(self)`**
  *Description*: Find the absolute path to the game script file on disk.

- **`_translate_speaker(self, speaker)`**
  *Description*: Translate the character name using glossary if possible.

- **`_find_speaker_in_script(self, block_idx, s_idx, text)`**
  *Description*: Find speaker in the script file using direct DB mapping or middle third distilled matching.



---

### File: [ai_variations_handler.py](../../handlers/translation/ai_variations_handler.py)

#### Class: `Class AIVariationsHandler(BaseTranslationHandler)`

*Handler for a i variations operations.*


##### Methods

- **`__init__(self, main_handler)`**
  *Description*: Initialize a new instance.

- **`_handle_variation_success(self, response, context)`**
  *Description*: Internal helper to handle variation success.

- **`_apply_chosen_variation(self, chosen, is_inline, target_block_idx, target_string_idx)`**
  *Description*: Internal helper to apply chosen variation.

- **`generate_variation_for_current_string(self, force)`**
  *Description*: Generate variation for current string.



---

### File: [ai_worker.py](../../handlers/translation/ai_worker.py)

#### Class: `Class AIWorker(QObject)`

*A i worker implementation.*


##### Methods

- **`__init__(self, provider, prompt_composer, task_details, mw)`**
  *Description*: Initialize a new instance.

- **`mw(self)`**
  *Description*: Mw.

- **`_log_ai_traffic(self, messages, response_text, error)`**
  *Description*: Internal helper to log ai traffic.

- **`cancel(self)`**
  *Description*: Cancel.

- **`_remove_trailing_commas(self, json_str)`**
  *Description*: Internal helper to remove trailing commas.

- **`_clean_json_response(self, text)`**
  *Description*: Internal helper to clean json response.

- **`run(self)`**
  *Description*: Run.



---

### File: [base_translation_handler.py](../../handlers/translation/base_translation_handler.py)

#### Class: `Class BaseTranslationHandler`

*Handler for base translation operations.*


##### Methods

- **`__init__(self, main_handler)`**
  *Description*: Initialize a new instance.



---

### File: [glossary_builder_handler.py](../../handlers/translation/glossary_builder_handler.py)

#### Class: `Class GlossaryBuilderHandler`

*Handler for glossary builder operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`_load_prompts(self)`**
  *Description*: Internal helper to load prompts.

- **`_split_text_into_chunks(self, text, chunk_size)`**
  *Description*: Internal helper to split text into chunks.

- **`_mask_tags_for_ai(self, text)`**
  *Description*: Internal helper to mask tags for ai.

- **`_clean_json_response(self, text)`**
  *Description*: Internal helper to clean json response.

- **`_resolve_translation_credentials(self, provider_name)`**
  *Description*: Internal helper to resolve translation credentials.

- **`build_glossary_for_block(self, block_id, category_name)`**
  *Description*: Create glossary for block.

- **`_start_async_glossary_task(self, block_id, provider, glossary_ai_config, chunks)`**
  *Description*: Internal helper to start async glossary task.

- **`_on_glossary_success(self, response, task_details, status_bar)`**
  *Description*: Internal helper to handle the glossary success event.

- **`_on_glossary_error(self, message, status_bar)`**
  *Description*: Internal helper to handle the glossary error event.

- **`_on_glossary_cancelled(self, status_bar)`**
  *Description*: Internal helper to handle the glossary cancelled event.

- **`_cleanup_worker(self)`**
  *Description*: Internal helper to cleanup worker.



---

### File: [glossary_handler.py](../../handlers/translation/glossary_handler.py)

#### Class: `Class CategorySelectionDialog(QDialog)`

*Dialog for choosing and adding categories for glossary AI classification.*


##### Methods

- **`__init__(self, parent, categories)`**
  *Description*: Initialize a new instance.

- **`get_selected_categories(self)`**
  *Description*: Get the selected categories.



#### Class: `Class GlossaryOccurrenceWorker(QThread)`

*Glossary occurrence worker implementation.*


##### Methods

- **`__init__(self, glossary_manager, data_source)`**
  *Description*: Initialize a new instance.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class GlossaryHandler(BaseTranslationHandler)`

*Handler for glossary operations.*


##### Methods

- **`__init__(self, main_handler)`**
  *Description*: Initialize a new instance.

- **`_current_prompts_path(self)`**
  *Description*: Internal helper to current prompts path.

- **`translation_update_dialog(self)`**
  *Description*: Translation update dialog.

- **`translation_update_dialog(self, value)`**
  *Description*: Translation update dialog.

- **`load_prompts(self)`**
  *Description*: Load prompts.

- **`save_prompt_section(self, section, field, value)`**
  *Description*: Save prompt section.

- **`_get_glossary_prompt_template(self)`**
  *Description*: Internal helper to get the glossary prompt template.

- **`_update_glossary_highlighting(self)`**
  *Description*: Internal helper to update the glossary highlighting.

- **`_ensure_glossary_loaded(self)`**
  *Description*: Internal helper to ensure glossary loaded.

- **`request_glossary_occurrence_update(self)`**
  *Description*: Request glossary occurrence update.

- **`request_glossary_occurrence_batch_update(self)`**
  *Description*: Request glossary occurrence batch update.

- **`request_glossary_notes_variation(self)`**
  *Description*: Request glossary notes variation.

- **`_handle_occurrence_ai_result(self)`**
  *Description*: Internal helper to handle occurrence ai result.

- **`_handle_occurrence_batch_success(self)`**
  *Description*: Internal helper to handle occurrence batch success.

- **`_handle_occurrence_ai_error(self, message, from_batch)`**
  *Description*: Internal helper to handle occurrence ai error.

- **`_handle_glossary_occurrence_update_success(self, response, context)`**
  *Description*: Internal helper to handle glossary occurrence update success.

- **`_handle_glossary_occurrence_batch_success(self, response, context)`**
  *Description*: Internal helper to handle glossary occurrence batch success.

- **`install_menu_actions(self)`**
  *Description*: Install menu actions.

- **`initialize_glossary_highlighting(self)`**
  *Description*: Initialize glossary highlighting.

- **`_on_glossary_dialog_closed(self)`**
  *Description*: Internal helper to handle the glossary dialog closed event.

- **`show_glossary_dialog(self, initial_term)`**
  *Description*: Show glossary dialog.

- **`add_glossary_entry(self, term, context, translation)`**
  *Description*: Add glossary entry.

- **`edit_glossary_entry(self, term, is_new, context, translation)`**
  *Description*: Edit glossary entry.

- **`_create_edit_dialog(self, term, entry, context, initial_translation)`**
  *Description*: Internal helper to create edit dialog.

- **`_ai_fill_glossary_entry(self, term, context, dialog)`**
  *Description*: Internal helper to ai fill glossary entry.

- **`_handle_ai_fill_success(self, response, context)`**
  *Description*: Internal helper to handle ai fill success.

- **`_handle_ai_fill_error(self, error_message, context)`**
  *Description*: Internal helper to handle ai fill error.

- **`_set_notes_dialog_busy(self, dialog_obj, busy)`**
  *Description*: Internal helper to set the notes dialog busy.

- **`_start_glossary_notes_variation(self)`**
  *Description*: Internal helper to start glossary notes variation.

- **`_handle_notes_variation_from_dialog(self, entry)`**
  *Description*: Internal helper to handle notes variation from dialog.

- **`_handle_glossary_notes_variation_success(self, response, context)`**
  *Description*: Internal helper to handle glossary notes variation success.

- **`_get_original_string(self, block_idx, string_idx)`**
  *Description*: Internal helper to get the original string.

- **`_get_original_block(self, block_idx)`**
  *Description*: Internal helper to get the original block.

- **`_jump_to_occurrence(self, occurrence)`**
  *Description*: Internal helper to jump to occurrence.

- **`_handle_glossary_entry_update(self, original, translation, notes, profiled)`**
  *Description*: Internal helper to handle glossary entry update.

- **`_handle_glossary_entry_delete(self, original)`**
  *Description*: Internal helper to handle glossary entry delete.

- **`classify_glossary_via_ai(self)`**
  *Description*: Classify glossary via ai.

- **`_handle_classify_suggest_success(self, response, context)`**
  *Description*: Internal helper to handle classify suggest success.

- **`_handle_classify_apply_success(self, response, context)`**
  *Description*: Internal helper to handle classify apply success.

- **`_handle_classify_error(self, error_message, context)`**
  *Description*: Internal helper to handle classify error.

- **`global_replace_glossary(self, find_word, replace_word)`**
  *Description*: Global replace glossary.



---

### File: [glossary_occurrence_updater.py](../../handlers/translation/glossary_occurrence_updater.py)

#### Class: `Class GlossaryOccurrenceUpdater`

*Extracted from GlossaryHandler. Encapsulates all logic for updating existing translations when a glossary term's translation is changed.*


##### Methods

- **`__init__(self, glossary_handler)`**
  *Description*: Initialize a new instance.

- **`_mw(self)`**
  *Description*: Internal helper to mw.

- **`_main_handler(self)`**
  *Description*: Internal helper to main handler.

- **`show_translation_update_dialog(self)`**
  *Description*: Show translation update dialog.

- **`_on_dialog_closed(self)`**
  *Description*: Internal helper to handle the dialog closed event.

- **`_get_occurrence_original_text(self, occurrence)`**
  *Description*: Internal helper to get the occurrence original text.

- **`_get_occurrence_translation_text(self, occurrence)`**
  *Description*: Internal helper to get the occurrence translation text.

- **`_apply_occurrence_translation(self, occurrence, new_text)`**
  *Description*: Internal helper to apply occurrence translation.

- **`_request_ai_occurrence_update(self, occurrence, from_batch)`**
  *Description*: Internal helper to request ai occurrence update.

- **`request_glossary_occurrence_update(self)`**
  *Description*: Request glossary occurrence update.

- **`_start_ai_occurrence_batch(self, occurrences)`**
  *Description*: Internal helper to start ai occurrence batch.

- **`_resume_ai_occurrence_batch(self)`**
  *Description*: Internal helper to resume ai occurrence batch.

- **`request_glossary_occurrence_batch_update(self)`**
  *Description*: Request glossary occurrence batch update.

- **`handle_occurrence_ai_result(self)`**
  *Description*: Handle occurrence ai result.

- **`handle_occurrence_batch_success(self)`**
  *Description*: Handle occurrence batch success.

- **`_handle_occurrence_ai_error(self, message, from_batch)`**
  *Description*: Internal helper to handle occurrence ai error.

- **`handle_glossary_occurrence_update_success(self, response, context)`**
  *Description*: Handle glossary occurrence update success.

- **`handle_glossary_occurrence_batch_success(self, response, context)`**
  *Description*: Handle glossary occurrence batch success.

- **`request_glossary_notes_variation(self)`**
  *Description*: Request glossary notes variation.



---

### File: [glossary_prompt_manager.py](../../handlers/translation/glossary_prompt_manager.py)

#### Class: `Class GlossaryPromptManager`

*Handles reading/writing of prompts.json and glossary.md. Provides caching to avoid repeated file reads.*


##### Methods

- **`__init__(self, mw, main_handler, glossary_manager)`**
  *Description*: Initialize a new instance.

- **`_plugin_dir(self, plugin_name)`**
  *Description*: Internal helper to plugin dir.

- **`_fallback_dir(self)`**
  *Description*: Internal helper to fallback dir.

- **`_resolve_file(self, filename, plugin_name)`**
  *Description*: Internal helper to resolve file.

- **`_resolve_glossary_path(self, plugin_name)`**
  *Description*: Resolves the best available glossary path for the given plugin_name. Prioritizes the plugin directory, then common defaults, and finally global fallback. At each level, if both glossary.json and glossary.md exist, it returns the newer one.

- **`load_prompts(self)`**
  *Description*: Returns (system_prompt, glossary_text). Uses cached values when available. Shows QMessageBox on errors.

- **`initialize_highlighting(self)`**
  *Description*: Pre-load glossary text for syntax highlighting without a full prompts load.

- **`get_glossary_prompt_template(self)`**
  *Description*: Returns (template_string, prompts_path). Uses cache if plugin unchanged.

- **`save_prompt_section(self, section, field, value)`**
  *Description*: Persists one field of prompts.json and updates local caches.

- **`_extract_system_prompt(self, payload)`**
  *Description*: Internal helper to extract system prompt.

- **`_extract_glossary_prompt(self, payload)`**
  *Description*: Internal helper to extract glossary prompt.

- **`_ensure_glossary_loaded(self)`**
  *Description*: Internal helper to ensure glossary loaded.

- **`_update_glossary_highlighting(self)`**
  *Description*: Internal helper to update the glossary highlighting.



---

### File: [text_formatter.py](../../handlers/translation/text_formatter.py)

#### Class: `Class TextFormatter`

*Handles formatting, word wrapping, tag-aware sentence splitting, and pagination for translations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`format_and_wrap_translation(self, text, block_idx, string_idx)`**
  *Description*: Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels  and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.



---

### File: [translation_ui_handler.py](../../handlers/translation/translation_ui_handler.py)

#### Class: `Class TranslationUIHandler(BaseTranslationHandler)`

*Handler for translation u i operations.*


##### Methods

- **`__init__(self, main_handler)`**
  *Description*: Initialize a new instance.

- **`_set_ai_controls_enabled(self, enabled)`**
  *Description*: Internal helper to set the ai controls enabled.

- **`status_dialog(self)`**
  *Description*: Status dialog.

- **`show_variations_dialog(self, variations, show_refresh)`**
  *Description*: Show variations dialog.

- **`prompt_session_bootstrap(self, system_prompt)`**
  *Description*: Prompt session bootstrap.

- **`confirm_line_count(self, expected, translation)`**
  *Description*: Confirm line count.

- **`apply_full_translation(self, new_text)`**
  *Description*: Apply full translation.

- **`apply_inline_variation(self, variation)`**
  *Description*: Apply inline variation.

- **`apply_partial_translation(self, translated_segment, start_line, end_line)`**
  *Description*: Apply partial translation.

- **`normalize_line_count(self, translation, expected_lines, mode_label)`**
  *Description*: Normalize line count.

- **`parse_variation_payload(self, raw_text)`**
  *Description*: Parse variation payload.

- **`update_status_message(self, message)`**
  *Description*: Update the status message.

- **`clear_status_message(self)`**
  *Description*: Remove status message.

- **`start_ai_operation(self, title, is_chunked, model_name)`**
  *Description*: Start ai operation.

- **`_handle_dialog_rejection(self)`**
  *Description*: Internal helper to handle dialog rejection.

- **`update_ai_operation_step(self, step_index, text, status)`**
  *Description*: Update the ai operation step.

- **`finish_ai_operation(self, success, show_popup)`**
  *Description*: Finish ai operation.

- **`merge_session_instructions(self, instructions, message)`**
  *Description*: Merge session instructions.

- **`_activate_entry(self, entry)`**
  *Description*: Internal helper to activate entry.



---

## Component: `ui`

### File: [autofix_selection_dialog.py](../../ui/autofix_selection_dialog.py)

#### Class: `Class AutofixSelectionDialog(QDialog)`

*Dialog class for autofix selection.*


##### Methods

- **`__init__(self, problem_definitions, active_autofixes, parent)`**
  *Description*: Initialize a new instance.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_select_all(self)`**
  *Description*: Internal helper to select all.

- **`_select_none(self)`**
  *Description*: Internal helper to select none.

- **`accept(self)`**
  *Description*: Accept.

- **`get_selected_problems(self)`**
  *Description*: Get the selected problems.



---

### File: [mempalace_builder_dialog.py](../../ui/mempalace_builder_dialog.py)

#### Functions

- **`prevent_sleep()`**
  *Description*: Prevent sleep.

- **`restore_sleep()`**
  *Description*: Restore sleep.

- **`put_to_sleep()`**
  *Description*: Put to sleep.

#### Class: `Class MemePalaceBuilderDialog(QDialog)`

*Dialog class for meme palace builder.*


##### Methods

- **`__init__(self, main_window, parent)`**
  *Description*: Initialize a new instance.

- **`_init_composer_and_client(self)`**
  *Description*: Prepare local DB client and script composer.

- **`_save_pipeline_state(self)`**
  *Description*: Persist current pipeline session variables into global settings.

- **`_update_pipeline_btn_text(self)`**
  *Description*: Update Complete Pipeline button label based on saved session state.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_maybe_prevent_sleep(self)`**
  *Description*: Internal helper to maybe prevent sleep.

- **`_finish_and_maybe_sleep(self)`**
  *Description*: Internal helper to finish and maybe sleep.

- **`_handle_prevent_sleep_toggled(self, checked)`**
  *Description*: Internal helper to handle prevent sleep toggled.

- **`_handle_sleep_after_toggled(self, checked)`**
  *Description*: Internal helper to handle sleep after toggled.

- **`refresh_chapters_list(self)`**
  *Description*: Reload chapters from local DB.

- **`_browse_script_file(self)`**
  *Description*: Internal helper to browse script file.

- **`append_log(self, text)`**
  *Description*: Append log.

- **`_get_ai_provider_or_warn(self)`**
  *Description*: Internal helper to get the ai provider or warn.

- **`_pre_analyze_script_via_ai(self)`**
  *Description*: Mine characters and terminology from script introduction.

- **`_pre_analyze_script_via_ai_core(self, file_path, ai_provider)`**
  *Description*: Internal helper to pre analyze script via ai core.

- **`_handle_char_mining_finished(self, success, message)`**
  *Description*: Internal helper to handle char mining finished.

- **`_profile_characters_speech_via_ai(self)`**
  *Description*: Analyze character speech patterns and build rich glossary profiles via AI.

- **`_profile_characters_speech_via_ai_core(self, ai_provider)`**
  *Description*: Internal helper to profile characters speech via ai core.

- **`_handle_speech_profiling_finished(self, success, message)`**
  *Description*: Internal helper to handle speech profiling finished.

- **`_start_chapters_mapping(self)`**
  *Description*: Map BMG text items to chapters.

- **`_start_chapters_mapping_core(self, file_path)`**
  *Description*: Internal helper to start chapters mapping core.

- **`_handle_chapters_mapping_finished(self, success, message)`**
  *Description*: Internal helper to handle chapters mapping finished.

- **`_analyze_selected_chapter(self)`**
  *Description*: Generate AI overview for the selected chapters.

- **`_handle_chapter_analysis_finished(self, success, message)`**
  *Description*: Internal helper to handle chapter analysis finished.

- **`_analyze_all_chapters(self)`**
  *Description*: Setup queue to analyze all chapters.

- **`_analyze_all_chapters_core(self)`**
  *Description*: Internal helper to analyze all chapters core.

- **`_start_complete_pipeline(self)`**
  *Description*: Start or resume the complete MemePalace orchestration pipeline sequentially.

- **`_run_pipeline_current_step(self)`**
  *Description*: Internal helper to run pipeline current step.

- **`_advance_pipeline(self)`**
  *Description*: Internal helper to advance pipeline.

- **`_abort_pipeline(self, error_message)`**
  *Description*: Internal helper to abort pipeline.

- **`_process_analysis_queue(self)`**
  *Description*: Process queue sequentially.

- **`_handle_worker_progress(self, current, total, text)`**
  *Description*: Internal helper to handle worker progress.

- **`_set_ui_enabled(self, enabled)`**
  *Description*: Internal helper to set the ui enabled.

- **`_clear_database(self)`**
  *Description*: Clear mapped data from local database.

- **`_handle_close_or_cancel(self)`**
  *Description*: Internal helper to handle close or cancel.

- **`load_builder_settings(self)`**
  *Description*: Load recent dialog preferences from settings.json.

- **`save_builder_settings(self)`**
  *Description*: Save dialog preferences into settings.json.



---

### File: [mempalace_viewer_dialog.py](../../ui/mempalace_viewer_dialog.py)

#### Class: `Class MemePalaceViewerDialog(QDialog)`

*Dialog class for meme palace viewer.*


##### Methods

- **`__init__(self, main_window, parent)`**
  *Description*: Initialize a new instance.

- **`_init_client(self)`**
  *Description*: Locate the SQLite database using recursive project/single-file search logic.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_load_wings(self)`**
  *Description*: Fetch wings from SQLite and populate combo box.

- **`_load_rooms_and_relations(self)`**
  *Description*: Fetch all rooms and relations for the selected Wing.

- **`_handle_wing_changed(self, index)`**
  *Description*: Internal helper to handle wing changed.

- **`_handle_room_selected(self)`**
  *Description*: Triggered when a room is clicked in the left list widget.

- **`_refresh_data(self)`**
  *Description*: Force reload database file and refresh UI lists.

- **`closeEvent(self, event)`**
  *Description*: Clear reference in main window when closed.

- **`_handle_dialogue_double_clicked(self, row, column)`**
  *Description*: Triggered when a dialogue row is double-clicked. Parses the Line ID, searches for the matching block and row index in Picoripi, selects them, and raises the main window to the front.



---

### File: [settings_dialog.py](../../ui/settings_dialog.py)

#### Class: `Class ProviderTestWorker(QThread)`

*Provider test worker implementation.*


##### Methods

- **`__init__(self, provider_key, provider_settings)`**
  *Description*: Initialize a new instance.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class SettingsDialog(QDialog, SettingsDialogUiMixin)`

*Dialog class for settings.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`_get_lang_name(self, code)`**
  *Description*: Internal helper to get the lang name.

- **`_create_script_selector(self, line_edit)`**
  *Description*: Internal helper to create script selector.

- **`_browse_for_script(self, line_edit)`**
  *Description*: Internal helper to browse for script.

- **`_create_path_selector(self, line_edit)`**
  *Description*: Internal helper to create path selector.

- **`_browse_for_file(self, line_edit)`**
  *Description*: Internal helper to browse for file.

- **`_create_dir_selector(self, line_edit)`**
  *Description*: Internal helper to create dir selector.

- **`_browse_for_directory(self, line_edit)`**
  *Description*: Internal helper to browse for directory.

- **`_on_fonts_dir_changed(self)`**
  *Description*: Internal helper to handle the fonts dir changed event.

- **`_on_orig_fonts_dir_changed(self)`**
  *Description*: Internal helper to handle the orig fonts dir changed event.

- **`load_initial_settings(self)`**
  *Description*: Load initial settings.

- **`get_settings(self)`**
  *Description*: Get the settings.

- **`_get_tags_from_tables(self)`**
  *Description*: Internal helper to get the tags from tables.

- **`on_edit_prompts_clicked(self)`**
  *Description*: Handle the edit prompts clicked event.

- **`on_test_provider_clicked(self)`**
  *Description*: Handle the test provider clicked event.

- **`on_test_provider_finished(self, success, result)`**
  *Description*: Handle the test provider finished event.

- **`_apply_translation_config_to_ui(self, config)`**
  *Description*: Internal helper to apply translation config to ui.

- **`_get_translation_config_from_ui(self)`**
  *Description*: Internal helper to get the translation config from ui.

- **`on_preset_changed(self, index)`**
  *Description*: Handle the preset changed event.

- **`on_save_preset_clicked(self)`**
  *Description*: Handle the save preset clicked event.

- **`on_delete_preset_clicked(self)`**
  *Description*: Handle the delete preset clicked event.



---

### File: [ui_event_filters.py](../../ui/ui_event_filters.py)

#### Class: `Class TextEditEventFilter(QObject)`

*Text edit event filter implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`eventFilter(self, obj, event)`**
  *Description*: Eventfilter.



#### Class: `Class MainWindowEventFilter(QObject)`

*Main window event filter implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`eventFilter(self, obj, event)`**
  *Description*: Eventfilter.



---

### File: [ui_setup.py](../../ui/ui_setup.py)

#### Functions

- **`setup_main_window_ui(main_window)`**
  *Description*: Sets up the main window UI by delegating to specialized builders. This replaces the monolithic 470-line setup function.

---

### File: [ui_updater.py](../../ui/ui_updater.py)

#### Class: `Class UIUpdater`

*U i updater implementation.*


##### Methods

- **`__init__(self, main_window, data_processor)`**
  *Description*: Initialize a new instance.

- **`get_tree_state(self)`**
  *Description*: Get the tree state.

- **`apply_tree_state(self, state)`**
  *Description*: Apply tree state.

- **`highlight_glossary_occurrence(self, occurrence)`**
  *Description*: Highlight glossary occurrence.

- **`populate_blocks(self, override_folder_id, override_block_idx)`**
  *Description*: Populate blocks.

- **`update_block_item_text_with_problem_count(self, block_idx)`**
  *Description*: Update the block item text with problem count.

- **`update_status_bar(self)`**
  *Description*: Update the status bar.

- **`update_status_bar_selection(self)`**
  *Description*: Update the status bar selection.

- **`clear_status_bar(self)`**
  *Description*: Remove status bar.

- **`synchronize_original_cursor(self)`**
  *Description*: Synchronize original cursor.

- **`highlight_problem_block(self, block_idx, highlight, is_critical)`**
  *Description*: Highlight problem block.

- **`clear_all_problem_block_highlights_and_text(self)`**
  *Description*: Remove all problem block highlights and text.

- **`update_title(self)`**
  *Description*: Update the title.

- **`update_plugin_status_label(self)`**
  *Description*: Update the plugin status label.

- **`update_statusbar_paths(self)`**
  *Description*: Update the statusbar paths.

- **`populate_strings_for_block(self, block_idx, category_name, force)`**
  *Description*: Populate strings for block.

- **`update_text_views(self)`**
  *Description*: Update the text views.

- **`update_preview_visibility(self)`**
  *Description*: Update the preview visibility.



---

### File: [ui_utils.py](../../ui/ui_utils.py)

#### Functions

- **`prettify_standard_context_menu(menu, style)`**
  *Description*: Finds standard actions like Undo, Redo, Cut, Copy, Paste, etc.  in a QMenu and assigns them standard icons from QStyle if they are missing.

---

### File: [layout_builder.py](../../ui/builders/layout_builder.py)

#### Class: `Class LayoutBuilder`

*Layout builder implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`build(self)`**
  *Description*: Create .

- **`_build_left_panel(self)`**
  *Description*: Internal helper to create left panel.

- **`_build_right_panel(self)`**
  *Description*: Internal helper to create right panel.

- **`_build_original_panel(self)`**
  *Description*: Internal helper to create original panel.

- **`_build_middle_panel(self)`**
  *Description*: Internal helper to create middle panel.

- **`_build_edited_panel(self)`**
  *Description*: Internal helper to create edited panel.

- **`_create_header_button(self, icon, tooltip, text)`**
  *Description*: Internal helper to create header button.

- **`_create_toolbar_button(self, text, tooltip)`**
  *Description*: Internal helper to create toolbar button.



---

### File: [menu_builder.py](../../ui/builders/menu_builder.py)

#### Class: `Class MenuToolTipEventFilter(QObject)`

*Menu tool tip event filter implementation.*


##### Methods

- **`eventFilter(self, watched, event)`**
  *Description*: Eventfilter.



#### Class: `Class MenuBuilder`

*Menu builder implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`build_all(self)`**
  *Description*: Create all.

- **`_build_file_menu(self, menubar)`**
  *Description*: Internal helper to create file menu.

- **`_build_edit_menu(self, menubar)`**
  *Description*: Internal helper to create edit menu.

- **`_build_view_menu(self, menubar)`**
  *Description*: Internal helper to create view menu.

- **`_build_tools_menu(self, menubar)`**
  *Description*: Internal helper to create tools menu.

- **`_build_navigation_menu(self, menubar)`**
  *Description*: Internal helper to create navigation menu.

- **`_build_bookmarks_menu(self, menubar)`**
  *Description*: Internal helper to create bookmarks menu.

- **`_build_help_menu(self, menubar)`**
  *Description*: Internal helper to create help menu.



---

### File: [statusbar_builder.py](../../ui/builders/statusbar_builder.py)

#### Class: `Class StatusBarBuilder`

*Status bar builder implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`build(self)`**
  *Description*: Create .



---

### File: [toolbar_builder.py](../../ui/builders/toolbar_builder.py)

#### Class: `Class ToolBarBuilder`

*Tool bar builder implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`build(self)`**
  *Description*: Create .



---

### File: [bfn_preview_widget.py](../../ui/components/bfn_preview_widget.py)

#### Functions

- **`_looks_like_bfn_editor(editor)`**
  *Description*: Structural check that 'editor' is a real BFN editor window (not None / not a bare test mock).  The real BfnEditorWindow and the test DummyBfnEditor both expose a `metadata` dict and a `sheet_images` list. A bare MagicMock would have these attributes auto-created as Mock objects (not dict / not list), so it fails this check.

- **`_looks_like_bfn_core(bfn)`**
  *Description*: Structural check that 'bfn' is a real BfnCore-like object with a callable layout_text.

#### Class: `Class BfnSideButton(QPushButton)`

*A compact square icon button for the BFN preview sidebar.*


##### Methods

- **`__init__(self, icon_text, tooltip, checkable, parent)`**
  *Description*: Initialize a new instance.

- **`_apply_style(self, checked)`**
  *Description*: Internal helper to apply style.

- **`setActive(self, active)`**
  *Description*: Setactive.



#### Class: `Class BfnPreviewSideBar(QFrame)`

*Vertical toolbar pinned to the left side of BfnPreviewWidget.*


##### Methods

- **`__init__(self, preview_widget)`**
  *Description*: Initialize a new instance.

- **`_update_color_btn(self)`**
  *Description*: Tint the 'A' button background to reflect current text color.

- **`refresh_state(self)`**
  *Description*: Sync button visual states with current widget settings.

- **`_on_shadow_clicked(self, checked)`**
  *Description*: Open shadow dialog; if user cancels keep previous enabled state.

- **`_on_glow_clicked(self, checked)`**
  *Description*: Internal helper to handle the glow clicked event.

- **`_on_set_bg(self)`**
  *Description*: Internal helper to handle the set bg event.

- **`_on_hide_bg(self, checked)`**
  *Description*: Internal helper to handle the hide bg event.

- **`_on_set_spacing(self)`**
  *Description*: Internal helper to handle the set spacing event.



#### Class: `Class BfnEditorAdapter`

*Bfn editor adapter implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`gly1(self)`**
  *Description*: Gly1.

- **`map1(self)`**
  *Description*: Map1.

- **`wid1(self)`**
  *Description*: Wid1.

- **`inf1(self)`**
  *Description*: Inf1.

- **`get_sheets_qimages(self)`**
  *Description*: Get the sheets qimages.

- **`layout_text(self, text, translation_map, line_spacing)`**
  *Description*: Layout text.



#### Class: `Class BfnPreviewWidget(QWidget)`

*Widget component for bfn preview.*


##### Methods

- **`__init__(self, main_window, parent)`**
  *Description*: Initialize a new instance.

- **`load_translation_map(self)`**
  *Description*: Load translation map.

- **`update_preview_text(self, text)`**
  *Description*: Update the text and request redraw.

- **`get_bg_top_left(self)`**
  *Description*: Calculate the top-left position of the background image inside the widget.

- **`get_absolute_text_rect(self)`**
  *Description*: Get the text rect in absolute widget coordinates (relative to background's top-left).

- **`get_active_bfn_font(self)`**
  *Description*: Find the active BFN font for the current string.

- **`get_handles_dict(self)`**
  *Description*: Get the handles dict.

- **`get_handle_under_mouse(self, pos)`**
  *Description*: Get the handle under mouse.

- **`draw_bounding_box(self, painter)`**
  *Description*: Draw bounding box.

- **`_position_sidebar(self)`**
  *Description*: Pin the sidebar to the left edge, full height.

- **`resizeEvent(self, event)`**
  *Description*: Resizeevent.

- **`enterEvent(self, event)`**
  *Description*: Enterevent.

- **`leaveEvent(self, event)`**
  *Description*: Leaveevent.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`mouseMoveEvent(self, event)`**
  *Description*: Mousemoveevent.

- **`mouseReleaseEvent(self, event)`**
  *Description*: Mousereleaseevent.

- **`show_context_menu(self, pos)`**
  *Description*: Show context menu.

- **`_open_text_color_dialog(self)`**
  *Description*: Internal helper to open text color dialog.

- **`_open_shadow_dialog(self)`**
  *Description*: Internal helper to open shadow dialog.

- **`_open_glow_dialog(self)`**
  *Description*: Internal helper to open glow dialog.

- **`_save_effects_settings(self)`**
  *Description*: Persist all text effects settings to mw and settings_manager.

- **`_render_glyphs_to_image(self, glyphs, sheets, cell_h, fallback_font, fallback_fm, total_width, total_height, scale_factor, img_size)`**
  *Description*: Render all glyphs onto a transparent QImage of img_size. The painter transform (translate + scale) is applied identically to paintEvent. Returns a QImage with Format_ARGB32_Premultiplied for composition.

- **`_tint_image(self, src, color_hex, alpha)`**
  *Description*: Apply a color tint to a white/RGBA glyph image. Uses SourceIn composition: dst = src_alpha * tint_color. Returns a new QImage tinted with the given color and clamped alpha.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`_paint_event_impl(self, painter, event)`**
  *Description*: Internal helper to paint event impl.



---

### File: [text_effects_dialog.py](../../ui/components/text_effects_dialog.py)

#### Class: `Class AnglePickerWidget(QWidget)`

*Interactive wheel for choosing an angle (like in Photoshop).*


##### Methods

- **`__init__(self, parent, size)`**
  *Description*: Initialize a new instance.

- **`angle(self)`**
  *Description*: Angle.

- **`setAngle(self, angle)`**
  *Description*: Setangle.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`_update_angle_from_mouse(self, pos)`**
  *Description*: Internal helper to update the angle from mouse.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`mouseMoveEvent(self, event)`**
  *Description*: Mousemoveevent.



#### Class: `Class TextEffectsDialog(QDialog)`

*Generic dialog for configuring Drop Shadow or Outer Glow effect parameters.*


##### Methods

- **`__init__(self, mode, settings, parent)`**
  *Description*: Args:     mode: TextEffectsDialog.MODE_SHADOW or MODE_GLOW     settings: dict with current values:         For shadow: enabled, color (hex str), alpha (0-255), angle (0-360), distance (0-30)         For glow:   enabled, color (hex str), alpha (0-255), spread (1-20)

- **`_pick_color(self)`**
  *Description*: Internal helper to pick color.

- **`_on_accept(self)`**
  *Description*: Internal helper to handle the accept event.

- **`get_result(self)`**
  *Description*: Returns the result dict after dialog was accepted.



---

### File: [main_window_actions.py](../../ui/main_window/main_window_actions.py)

#### Class: `Class TagAliasDialog(QDialog)`

*Dialog class for tag alias.*


##### Methods

- **`__init__(self, parent, title, original_tag, current_alias, current_width)`**
  *Description*: Initialize a new instance.

- **`showEvent(self, event)`**
  *Description*: Showevent.

- **`_on_force_changed(self, state)`**
  *Description*: Internal helper to handle the force changed event.

- **`_on_text_changed(self, text)`**
  *Description*: Internal helper to handle the text changed event.

- **`get_data(self)`**
  *Description*: Get the data.



#### Class: `Class AliasUpdateWorker(QThread)`

*Alias update worker implementation.*


##### Methods

- **`__init__(self, edited_data_copy, data_copy, edited_file_data_copy, alias, original_tag)`**
  *Description*: Initialize a new instance.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class MainWindowActions`

*Main window actions implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`open_settings_dialog(self)`**
  *Description*: Open settings dialog.

- **`trigger_save_action(self)`**
  *Description*: Trigger save action.

- **`trigger_revert_action(self)`**
  *Description*: Trigger revert action.

- **`trigger_undo_paste_action(self)`**
  *Description*: Trigger undo paste action.

- **`trigger_reload_tag_mappings(self)`**
  *Description*: Trigger reload tag mappings.

- **`handle_add_tag_mapping_request(self, bracket_tag, curly_tag)`**
  *Description*: Handle add tag mapping request.

- **`show_shortcuts_help(self)`**
  *Description*: Show shortcuts help.

- **`open_mempalace_builder(self)`**
  *Description*: Open the MemePalace Context Builder dialog in modeless mode.

- **`open_mempalace_viewer(self)`**
  *Description*: Open the MemePalace Database Viewer dialog.

- **`inspect_story_context(self)`**
  *Description*: Query and display visual context/timeline for the selected row from MemePalace without translating.

- **`open_bfn_editor_standalone(self)`**
  *Description*: Open BFN Font Editor as a standalone window (no archive binding).

- **`open_bfn_editor_for_block(self, block_idx)`**
  *Description*: Open BFN Font Editor bound to a specific .bfn block (may be inside an archive). After saving, updates the archive in RAM and reloads font metrics.

- **`_bfn_font_sync(self)`**
  *Description*: Reload font metrics in Picoripi after BFN editor saves changes.

- **`export_current_bmg_to_json(self)`**
  *Description*: Export the currently selected BMG file's text content to a JSON file for inspection.

- **`import_current_bmg_from_json(self)`**
  *Description*: Import BMG text content from an exported JSON file into the currently selected block.

- **`trigger_recalculate_widths(self)`**
  *Description*: Force recalculate text widths and issues for the entire project.

- **`add_tag_alias(self, original_tag)`**
  *Description*: Add tag alias.

- **`edit_tag_alias(self, alias, original_tag)`**
  *Description*: Edit tag alias.

- **`remove_tag_alias(self, alias, original_tag)`**
  *Description*: Remove tag alias.

- **`_update_aliases_in_edited_data(self, alias, original_tag, on_complete_callback)`**
  *Description*: Clean up stale alias from in-memory edits in a background thread if needed.

- **`_refresh_editors_after_alias_change(self)`**
  *Description*: Internal helper to update the editors after alias change.

- **`_save_font_overrides_to_disk(self)`**
  *Description*: Internal helper to save font overrides to disk.

- **`run_external_script(self)`**
  *Description*: Asynchronously run configured external script (e.g. ROM builder / emulator)



---

### File: [main_window_block_handler.py](../../ui/main_window/main_window_block_handler.py)

#### Class: `Class MainWindowBlockHandler`

*Handler for main window block operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`get_block_color_markers(self, block_idx)`**
  *Description*: Get the block color markers.

- **`toggle_block_color_marker(self, block_idx, color_name)`**
  *Description*: Toggle block color marker.

- **`rebuild_unsaved_block_indices(self)`**
  *Description*: Rebuild unsaved block indices.



---

### File: [main_window_event_handler.py](../../ui/main_window/main_window_event_handler.py)

#### Class: `Class MainWindowEventHandler`

*Handler for main window event operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`connect_signals(self)`**
  *Description*: Connect signals.

- **`keyPressEvent(self, event)`**
  *Description*: Keypressevent.

- **`closeEvent(self, event)`**
  *Description*: Closeevent.

- **`disconnect_signals(self)`**
  *Description*: Disconnects all signals connected during initialization.

- **`handle_edited_cursor_position_changed(self)`**
  *Description*: Handle edited cursor position changed.

- **`handle_edited_selection_changed(self)`**
  *Description*: Handle edited selection changed.



---

### File: [main_window_helper.py](../../ui/main_window/main_window_helper.py)

#### Class: `Class MainWindowHelper`

*Main window helper implementation.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`get_font_map_for_string(self, block_idx, string_idx)`**
  *Description*: Get the font map for string.

- **`restart_application(self)`**
  *Description*: Restart application.

- **`rebuild_unsaved_block_indices(self)`**
  *Description*: Rebuild unsaved block indices.

- **`execute_find_next_shortcut(self)`**
  *Description*: Execute find next shortcut.

- **`execute_find_previous_shortcut(self)`**
  *Description*: Execute find previous shortcut.

- **`handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Handle panel find next.

- **`handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Handle panel find previous.

- **`toggle_search_panel(self)`**
  *Description*: Toggle search panel.

- **`hide_search_panel(self)`**
  *Description*: Hide search panel.

- **`open_advanced_search(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Open advanced search.

- **`load_all_data_for_path(self, original_file_path, manually_set_edited_path, is_initial_load_from_settings)`**
  *Description*: Load all data for path.

- **`apply_text_wrap_settings(self)`**
  *Description*: Apply text wrap settings.

- **`reconfigure_all_highlighters(self)`**
  *Description*: Reconfigure all highlighters.

- **`prepare_to_close(self)`**
  *Description*: Prepare to close.

- **`restore_state_after_settings_load(self)`**
  *Description*: Restore state after settings load.



---

### File: [main_window_plugin_handler.py](../../ui/main_window/main_window_plugin_handler.py)

#### Class: `Class MainWindowPluginHandler`

*Handler for main window plugin operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`setup_plugin_ui(self)`**
  *Description*: Setup plugin ui.

- **`load_game_plugin(self)`**
  *Description*: Load game plugin.

- **`_load_custom_aliases(self)`**
  *Description*: Internal helper to load custom aliases.

- **`_load_fallback_rules(self, error_message)`**
  *Description*: Internal helper to load fallback rules.

- **`trigger_check_tags_action(self)`**
  *Description*: Trigger check tags action.



---

### File: [main_window_ui_handler.py](../../ui/main_window/main_window_ui_handler.py)

#### Class: `Class MainWindowUIHandler`

*Handler for main window u i operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`update_editor_rules_properties(self)`**
  *Description*: Update the editor rules properties.

- **`apply_font_size(self, fast, target)`**
  *Description*: Apply font size.

- **`apply_text_wrap_settings(self)`**
  *Description*: Apply text wrap settings.

- **`reconfigure_all_highlighters(self)`**
  *Description*: Reconfigure all highlighters.

- **`force_focus(self)`**
  *Description*: Force focus.

- **`apply_theme(app, theme_name)`**
  *Description*: Apply theme.



---

### File: [settings_ui_setup.py](../../ui/settings/settings_ui_setup.py)

#### Class: `Class SettingsDialogUiMixin`

*Settings dialog ui mixin implementation.*


##### Methods

- **`setup_general_tab(self)`**
  *Description*: Setup general tab.

- **`setup_plugin_tab(self)`**
  *Description*: Setup plugin tab.

- **`rebuild_plugin_tabs(self)`**
  *Description*: Rebuild plugin tabs.

- **`setup_spelling_tab(self)`**
  *Description*: Setup spelling tab.

- **`_open_dictionary_manager(self)`**
  *Description*: Internal helper to open dictionary manager.

- **`populate_spellchecker_languages(self)`**
  *Description*: Populate spellchecker languages.

- **`_populate_font_list(self, plugin_dir_name)`**
  *Description*: Internal helper to populate font list.

- **`_setup_display_subtab(self, tab)`**
  *Description*: Internal helper to setup display subtab.

- **`on_rules_changed(self)`**
  *Description*: Handle the rules changed event.

- **`_setup_rules_subtab(self, tab)`**
  *Description*: Internal helper to setup rules subtab.

- **`_setup_context_tags_subtab(self, tab)`**
  *Description*: Internal helper to setup context tags subtab.

- **`_handle_table_double_click(self, event, table)`**
  *Description*: Internal helper to handle table double click.

- **`_show_table_context_menu(self, pos, table)`**
  *Description*: Internal helper to show table context menu.

- **`_add_table_row(self, table, display_text, col1, col2, insert_at_row)`**
  *Description*: Internal helper to add table row.

- **`_filter_tags_tables(self, text)`**
  *Description*: Internal helper to filter tags tables.

- **`_remove_table_row(self, table)`**
  *Description*: Internal helper to remove table row.

- **`_setup_paths_subtab(self, tab)`**
  *Description*: Internal helper to setup paths subtab.

- **`_on_dir_mode_changed(self, state)`**
  *Description*: Internal helper to handle the dir mode changed event.

- **`_on_auto_generate_changed(self, state)`**
  *Description*: Internal helper to handle the auto generate changed event.

- **`_update_auto_changes_path(self)`**
  *Description*: Internal helper to update the auto changes path.

- **`_populate_checkbox_subtab(self, tab, checkbox_dict, title)`**
  *Description*: Internal helper to populate checkbox subtab.

- **`_setup_detection_subtab(self, tab)`**
  *Description*: Internal helper to setup detection subtab.

- **`_setup_autofix_subtab(self, tab)`**
  *Description*: Internal helper to setup autofix subtab.

- **`on_provider_changed(self, index)`**
  *Description*: Handle the provider changed event.

- **`setup_ai_translation_tab(self)`**
  *Description*: Setup ai translation tab.

- **`setup_ai_glossary_tab(self)`**
  *Description*: Setup ai glossary tab.

- **`_set_glossary_api_key_text(self, value)`**
  *Description*: Internal helper to set the glossary api key text.

- **`_get_translation_credentials_for_glossary(self, provider_name)`**
  *Description*: Internal helper to get the translation credentials for glossary.

- **`_update_glossary_api_key_controls(self, provider_name)`**
  *Description*: Internal helper to update the glossary api key controls.

- **`_refresh_glossary_api_key_from_translation(self)`**
  *Description*: Internal helper to update the glossary api key from translation.

- **`_on_glossary_use_translation_key_changed(self, state)`**
  *Description*: Internal helper to handle the glossary use translation key changed event.

- **`_on_glossary_provider_changed(self, index)`**
  *Description*: Internal helper to handle the glossary provider changed event.

- **`_on_glossary_api_key_changed(self, text)`**
  *Description*: Internal helper to handle the glossary api key changed event.

- **`find_plugins(self)`**
  *Description*: Find plugins.

- **`populate_plugin_list(self)`**
  *Description*: Populate plugin list.

- **`setup_logging_tab(self)`**
  *Description*: Setup logging tab.

- **`on_theme_changed(self, index)`**
  *Description*: Handle the theme changed event.

- **`on_plugin_changed(self, index)`**
  *Description*: Handle the plugin changed event.

- **`_setup_aliases_subtab(self, tab)`**
  *Description*: Internal helper to setup aliases subtab.

- **`_populate_aliases_table(self)`**
  *Description*: Internal helper to populate aliases table.

- **`_add_alias_row(self, alias, orig_tag, insert_at_row)`**
  *Description*: Internal helper to add alias row.

- **`_remove_alias_row(self)`**
  *Description*: Internal helper to remove alias row.

- **`_filter_aliases_table(self, text)`**
  *Description*: Internal helper to filter aliases table.

- **`_handle_aliases_double_click(self, event)`**
  *Description*: Internal helper to handle aliases double click.

- **`_show_aliases_context_menu(self, pos)`**
  *Description*: Internal helper to show aliases context menu.

- **`_setup_font_map_subtab(self, tab)`**
  *Description*: Internal helper to setup font map subtab.

- **`_populate_font_map_table(self)`**
  *Description*: Internal helper to populate font map table.

- **`_add_font_map_row(self, char, width_val, insert_at_row)`**
  *Description*: Internal helper to add font map row.

- **`_remove_font_map_row(self)`**
  *Description*: Internal helper to remove font map row.

- **`_filter_font_map_table(self, text)`**
  *Description*: Internal helper to filter font map table.

- **`_handle_font_map_double_click(self, event)`**
  *Description*: Internal helper to handle font map double click.

- **`_show_font_map_context_menu(self, pos)`**
  *Description*: Internal helper to show font map context menu.



---

### File: [settings_widgets.py](../../ui/settings/settings_widgets.py)

#### Class: `Class ColorPickerButton(QPushButton)`

*Color picker button implementation.*


##### Methods

- **`__init__(self, initial_color, parent)`**
  *Description*: Initialize a new instance.

- **`color(self)`**
  *Description*: Color.

- **`setColor(self, color)`**
  *Description*: Setcolor.

- **`_update_style(self)`**
  *Description*: Internal helper to update the style.

- **`_get_contrasting_text_color(self, bg_color)`**
  *Description*: Internal helper to get the contrasting text color.

- **`pick_color(self)`**
  *Description*: Pick color.



#### Class: `Class TagDisplayWidget(QWidget)`

*Widget component for tag display.*


##### Methods

- **`__init__(self, initial_text, parent)`**
  *Description*: Initialize a new instance.

- **`_update_btn_color(self)`**
  *Description*: Internal helper to update the btn color.

- **`_pick_color(self)`**
  *Description*: Internal helper to pick color.

- **`text(self)`**
  *Description*: Text.



---

### File: [base_ui_updater.py](../../ui/updaters/base_ui_updater.py)

#### Class: `Class BaseUIUpdater`

*Base u i updater implementation.*


##### Methods

- **`__init__(self, main_window, data_processor)`**
  *Description*: Initialize a new instance.



---

### File: [block_list_updater.py](../../ui/updaters/block_list_updater.py)

#### Class: `Class BlockListUpdater(BaseUIUpdater)`

*Block list updater implementation.*


##### Methods

- **`__init__(self, main_window, data_processor)`**
  *Description*: Initialize a new instance.

- **`_set_item_style_icon(self, item, column, standard_icon_enum)`**
  *Description*: Internal helper to set the item style icon.

- **`_register_item_in_cache(self, item)`**
  *Description*: Internal helper to register item in cache.

- **`_get_block_display_name_with_ext(self, block_idx, base_display_name)`**
  *Description*: Internal helper to get the block display name with ext.

- **`get_tree_state(self)`**
  *Description*: Returns the current expansion and selection state of the block tree.

- **`apply_tree_state(self, state)`**
  *Description*: Restores the tree expansion and selection from state.

- **`_get_item_id(self, item)`**
  *Description*: Helper to generate consistent IDs for tree items.

- **`_get_aggregated_problems_for_block(self, block_idx, pre_aggregated_counts, category_name, chapter_id)`**
  *Description*: Internal helper to get the aggregated problems for block.

- **`_apply_issues_and_tooltip(self, item, base_display_name, problem_counts, problem_definitions)`**
  *Description*: Internal helper to apply issues and tooltip.

- **`_create_block_tree_item(self, block_idx, problem_definitions, pre_aggregated_counts)`**
  *Description*: Helper to create a single block tree item with issue counts and tooltips.

- **`_add_virtual_folder_to_tree(self, parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts, folder_id_to_select)`**
  *Description*: Recursively add virtual folders and their blocks to the tree with folder compaction (GitHub style).

- **`populate_blocks(self, override_folder_id, override_block_idx)`**
  *Description*: Populate blocks.

- **`update_block_item_text_with_problem_count(self, block_idx)`**
  *Description*: Update the block item text with problem count.

- **`highlight_problem_block(self, block_idx, highlight, is_critical)`**
  *Description*: Highlight problem block.

- **`clear_all_problem_block_highlights_and_text(self)`**
  *Description*: Remove all problem block highlights and text.



---

### File: [preview_updater.py](../../ui/updaters/preview_updater.py)

#### Class: `Class PreviewUpdater(BaseUIUpdater)`

*Preview updater implementation.*


##### Methods

- **`__init__(self, main_window, data_processor)`**
  *Description*: Initialize a new instance.

- **`get_cache_key(self, block_idx, category_name)`**
  *Description*: Get the cache key.

- **`update_cached_string(self, block_idx, string_idx, preview_line_text)`**
  *Description*: Update the preview text of a specific string in all cache entries for the given block.

- **`_block_has_overrides(self, block_idx)`**
  *Description*: Internal helper to block has overrides.

- **`schedule_pre_cache(self)`**
  *Description*: Schedule pre-caching of preview lines to avoid blocking startup with a blank window.

- **`pre_cache_all_blocks(self)`**
  *Description*: Pre-cache preview lines for all blocks to enable instantaneous switching.

- **`highlight_glossary_occurrence(self, occurrence)`**
  *Description*: Highlights a glossary occurrence in the original_text_edit.

- **`synchronize_original_cursor(self)`**
  *Description*: Synchronize original cursor.

- **`_apply_highlights_for_block(self, block_idx)`**
  *Description*: Internal helper to apply highlights for block.

- **`_apply_highlights_to_editor(self, editor, block_idx, string_idx)`**
  *Description*: Internal helper to apply highlights to editor.

- **`_get_all_categorized_indices_for_block(self, block_idx)`**
  *Description*: Get set of all string indices that are assigned to any virtual block (category).

- **`populate_strings_for_block(self, block_idx, category_name, force)`**
  *Description*: Populate strings for block.

- **`_load_next_preview_chunk(self)`**
  *Description*: Internal helper to load next preview chunk.

- **`update_text_views(self)`**
  *Description*: Update the text views.

- **`_do_update_text_views(self, is_programmatic_call_flag_original)`**
  *Description*: Internal helper to do update text views.

- **`update_preview_visibility(self)`**
  *Description*: Update visibility of the visual preview widget based on loaded fonts and menu toggle state.



---

### File: [string_settings_updater.py](../../ui/updaters/string_settings_updater.py)

#### Class: `Class StringSettingsUpdater(BaseUIUpdater)`

*String settings updater implementation.*


##### Methods

- **`__init__(self, main_window, data_processor)`**
  *Description*: Initialize a new instance.

- **`update_font_combobox(self)`**
  *Description*: Update the font combobox.

- **`update_string_settings_panel(self)`**
  *Description*: Update the string settings panel.



---

### File: [title_status_bar_updater.py](../../ui/updaters/title_status_bar_updater.py)

#### Class: `Class TitleStatusBarUpdater(BaseUIUpdater)`

*Title status bar updater implementation.*


##### Methods

- **`update_status_bar(self)`**
  *Description*: Update the status bar.

- **`update_status_bar_selection(self)`**
  *Description*: Update the status bar selection.

- **`clear_status_bar(self)`**
  *Description*: Remove status bar.

- **`update_title(self)`**
  *Description*: Update the title.

- **`update_plugin_status_label(self)`**
  *Description*: Update the plugin status label.

- **`update_statusbar_paths(self)`**
  *Description*: Update the statusbar paths.



---

## Component: `components`

### File: [ai_chat_dialog.py](../../components/ai_chat_dialog.py)

#### Class: `Class _ChatInputEventFilter(QObject)`

*_ chat input event filter implementation.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`eventFilter(self, obj, event)`**
  *Description*: Eventfilter.



#### Class: `Class _ChatTab(QWidget)`

*_ chat tab implementation.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`populate_models(self, providers_data)`**
  *Description*: Populate models.



#### Class: `Class AIChatDialog(QDialog)`

*Dialog class for a i chat.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_set_theme_styles(self)`**
  *Description*: Internal helper to set the theme styles.

- **`eventFilter(self, obj, event)`**
  *Description*: Eventfilter.

- **`add_new_tab(self)`**
  *Description*: Add new tab.

- **`remove_tab(self, index)`**
  *Description*: Remove tab.

- **`_emit_message_sent(self, tab_index)`**
  *Description*: Internal helper to emit message sent.

- **`append_to_history(self, tab_index, html_text)`**
  *Description*: Append to history.

- **`set_input_enabled(self, tab_index, enabled)`**
  *Description*: Set the input enabled.



---

### File: [ai_status_dialog.py](../../components/ai_status_dialog.py)

#### Functions

- **`prevent_sleep()`**
  *Description*: Prevent sleep.

- **`restore_sleep()`**
  *Description*: Restore sleep.

- **`put_to_sleep()`**
  *Description*: Put to sleep.

#### Class: `Class AIStatusDialog(QDialog)`

*Dialog class for a i status.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`on_cancel(self)`**
  *Description*: Handle the cancel event.

- **`reject(self)`**
  *Description*: Reject.

- **`closeEvent(self, event)`**
  *Description*: Closeevent.

- **`setup_progress_bar(self, total_chunks, completed_chunks)`**
  *Description*: Setup progress bar.

- **`update_progress(self, completed_chunks)`**
  *Description*: Update the progress.

- **`set_detail_text(self, text)`**
  *Description*: Set the detail text.

- **`showEvent(self, event)`**
  *Description*: Showevent.

- **`hideEvent(self, event)`**
  *Description*: Hideevent.

- **`start(self, title, is_chunked, model_name)`**
  *Description*: Start.

- **`finish(self, success, show_popup)`**
  *Description*: Finish.

- **`_handle_prevent_sleep_toggled(self, checked)`**
  *Description*: Internal helper to handle prevent sleep toggled.

- **`_handle_sleep_after_toggled(self, checked)`**
  *Description*: Internal helper to handle sleep after toggled.

- **`_set_model_name(self, model_name)`**
  *Description*: Internal helper to set the model name.

- **`update_step(self, step_index, text, status)`**
  *Description*: Update the step.

- **`_update_label_style(self, label, status, text)`**
  *Description*: Internal helper to update the label style.



---

### File: [block_properties_dialog.py](../../components/block_properties_dialog.py)

#### Class: `Class BlockPropertiesDialog(QDialog)`

*Dialog class for block properties.*


##### Methods

- **`__init__(self, parent, block_idx)`**
  *Description*: Initialize a new instance.

- **`add_form_row(self, layout, label_text, value_text)`**
  *Description*: Add form row.



---

### File: [custom_list_item_delegate.py](../../components/custom_list_item_delegate.py)

#### Class: `Class CustomListItemDelegate(QStyledItemDelegate)`

*Custom list item delegate implementation.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_get_current_number_area_width(self, option)`**
  *Description*: Internal helper to get the current number area width.

- **`_get_problem_indicator_zone_width(self)`**
  *Description*: Internal helper to get the problem indicator zone width.

- **`_get_color_marker_zone_width(self)`**
  *Description*: Internal helper to get the color marker zone width.

- **`sizeHint(self, option, index)`**
  *Description*: Sizehint.

- **`paint(self, painter, option, index)`**
  *Description*: Paint.

- **`handle_tooltip(self, event, view, option, index)`**
  *Description*: Handle tooltip.

- **`_get_problems_tooltip_text(self, main_window, index)`**
  *Description*: Internal helper to get the problems tooltip text.

- **`helpEvent(self, event, view, option, index)`**
  *Description*: Helpevent.

- **`setEditorData(self, editor, index)`**
  *Description*: Seteditordata.

- **`setModelData(self, editor, model, index)`**
  *Description*: Setmodeldata.

- **`updateEditorGeometry(self, editor, option, index)`**
  *Description*: Updateeditorgeometry.



---

### File: [custom_list_widget.py](../../components/custom_list_widget.py)

#### Class: `Class CustomListWidget(QListWidget)`

*Widget component for custom list.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_create_color_icon(self, color, size)`**
  *Description*: Internal helper to create color icon.

- **`create_item(self, text, data, role)`**
  *Description*: Create item.

- **`show_context_menu(self, pos)`**
  *Description*: Show context menu.

- **`viewportEvent(self, event)`**
  *Description*: Viewportevent.

- **`_open_spellcheck_for_block(self, block_idx, category_name)`**
  *Description*: Open spellcheck dialog for a specific block.



---

### File: [custom_tree_widget.py](../../components/custom_tree_widget.py)

#### Class: `Class CustomTreeWidget(TreeDragDropMixin, TreeContextMenuMixin, TreeFolderMixin, TreeNavigationMixin, TreeSpellcheckMixin, QTreeWidget)`

*QTreeWidget subclass for the project block tree.  All substantial behaviour is delegated to focused mixin classes:   - TreeDragDropMixin      — drag-and-drop   - TreeContextMenuMixin   — right-click context menu   - TreeFolderMixin        — virtual folder CRUD + PM sync + expansion state   - TreeNavigationMixin    — keyboard navigation + move-up/move-down   - TreeSpellcheckMixin    — spellcheck dialog + Reveal-in-Explorer*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`keyPressEvent(self, event)`**
  *Description*: Keypressevent.

- **`wheelEvent(self, event)`**
  *Description*: Wheelevent.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`event(self, event)`**
  *Description*: Event.

- **`viewportEvent(self, event)`**
  *Description*: Viewportevent.

- **`_create_color_icon(self, color, size)`**
  *Description*: Internal helper to create color icon.

- **`create_item(self, text, block_idx, role)`**
  *Description*: Create item.

- **`select_block_by_index(self, block_idx, category)`**
  *Description*: Select block by index.

- **`_get_next_unnamed_name(self, pm)`**
  *Description*: Return the next available 'Unnamed N' folder name.



---

### File: [dictionary_manager_dialog.py](../../components/dictionary_manager_dialog.py)

#### Class: `Class DownloadThread(QThread)`

*Download thread implementation.*


##### Methods

- **`__init__(self, downloads)`**
  *Description*: Initialize a new instance.

- **`run(self)`**
  *Description*: Run.



#### Class: `Class DictionaryManagerDialog(QDialog)`

*Dialog class for dictionary manager.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_get_lang_name(self, code)`**
  *Description*: Internal helper to get the lang name.

- **`load_dictionaries(self)`**
  *Description*: Load dictionaries.

- **`refresh_list(self)`**
  *Description*: Update the list.

- **`update_button_state(self)`**
  *Description*: Update the button state.

- **`download_selected(self)`**
  *Description*: Download selected.

- **`on_download_progress(self, message, value)`**
  *Description*: Handle the download progress event.

- **`on_download_finished(self, url, success, message)`**
  *Description*: Handle the download finished event.



---

### File: [glossary_dialog.py](../../components/glossary_dialog.py)

#### Class: `Class _RichTextItemDelegate(QStyledItemDelegate)`

*Render rich-text list items (e.g., occurrences list).*


##### Methods

- **`paint(self, painter, option, index)`**
  *Description*: Paint.

- **`sizeHint(self, option, index)`**
  *Description*: Sizehint.



#### Class: `Class GlossaryDialog(QDialog)`

*Show glossary entries with occurrences and allow navigation.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`_active_table(self)`**
  *Description*: Internal helper to active table.

- **`_on_tab_changed(self, index)`**
  *Description*: Internal helper to handle the tab changed event.

- **`_on_ai_classify_clicked(self)`**
  *Description*: Internal helper to handle the ai classify clicked event.

- **`_on_global_replace_clicked(self)`**
  *Description*: Internal helper to handle the global replace clicked event.

- **`_populate_entries(self, entries)`**
  *Description*: Internal helper to populate entries.

- **`_select_initial_term(self, term, switch_tab)`**
  *Description*: Internal helper to select initial term.

- **`_show_entry_for_row(self, row)`**
  *Description*: Internal helper to show entry for row.

- **`_on_entry_current_changed(self, row, _column, _prev_row, _prev_column)`**
  *Description*: Internal helper to handle the entry current changed event.

- **`_on_entry_selected(self, row, _column)`**
  *Description*: Internal helper to handle the entry selected event.

- **`_on_entry_edited(self, item)`**
  *Description*: Internal helper to handle the entry edited event.

- **`_activate_selected_occurrence(self, item)`**
  *Description*: Internal helper to activate selected occurrence.

- **`_set_notes_variation_busy(self, busy)`**
  *Description*: Internal helper to set the notes variation busy.

- **`apply_notes_variation(self, new_notes)`**
  *Description*: Apply notes variation.

- **`_on_notes_variation_clicked(self)`**
  *Description*: Internal helper to handle the notes variation clicked event.

- **`_on_editor_content_changed(self)`**
  *Description*: Internal helper to handle the editor content changed event.

- **`_mark_editor_dirty(self, dirty)`**
  *Description*: Internal helper to mark editor dirty.

- **`_update_editor_enabled_state(self)`**
  *Description*: Internal helper to update the editor enabled state.

- **`_save_editor_changes(self)`**
  *Description*: Internal helper to save editor changes.

- **`_attempt_entry_update(self, entry, new_translation, new_notes, profiled)`**
  *Description*: Internal helper to attempt entry update.

- **`_attempt_entry_delete(self, entry)`**
  *Description*: Internal helper to attempt entry delete.

- **`_on_entry_context_menu(self, pos)`**
  *Description*: Internal helper to handle the entry context menu event.

- **`_load_dialog_state(self)`**
  *Description*: Internal helper to load dialog state.

- **`_save_dialog_state(self)`**
  *Description*: Internal helper to save dialog state.

- **`_read_settings_file(self)`**
  *Description*: Internal helper to read settings file.

- **`_write_settings_file(self, data)`**
  *Description*: Internal helper to write settings file.

- **`_geometry_to_dict(rect)`**
  *Description*: Internal helper to geometry to dict.

- **`showEvent(self, event)`**
  *Description*: Showevent.

- **`closeEvent(self, event)`**
  *Description*: Closeevent.

- **`keyPressEvent(self, event)`**
  *Description*: Keypressevent.

- **`_update_occurrences(self, entry)`**
  *Description*: Internal helper to update the occurrences.

- **`_entry_for_row(self, row)`**
  *Description*: Internal helper to entry for row.

- **`_populate_entry_details(self, entry)`**
  *Description*: Internal helper to populate entry details.

- **`_clear_entry_details(self)`**
  *Description*: Internal helper to remove entry details.

- **`_apply_filter(self, text)`**
  *Description*: Internal helper to apply filter.

- **`reload_data(self, entries, occurrence_map)`**
  *Description*: Hot-reload entries and occurrences from external source and refresh UI.



---

### File: [glossary_edit_dialog.py](../../components/glossary_edit_dialog.py)

#### Class: `Class ReturnToAcceptFilter(QObject)`

*Convert plain Return/Enter key presses into dialog acceptance.*


##### Methods

- **`__init__(self, dialog)`**
  *Description*: Initialize a new instance.

- **`eventFilter(self, obj, event)`**
  *Description*: Eventfilter.



#### Class: `Class GlossaryEditDialog(QDialog)`

*Simple dialog for editing a glossary entry.  Shows term, optional context line, translation field (with optional AI Fill button), and notes field (with optional AI Variations button).*


##### Methods

- **`__init__(self, parent, term, translation, notes, context, ai_assist_callback, notes_variation_callback)`**
  *Description*: Initialize a new instance.

- **`set_values(self, translation, notes)`**
  *Description*: Set the values.

- **`get_values(self)`**
  *Description*: Get the values.

- **`set_ai_busy(self, busy)`**
  *Description*: Set the ai busy.



---

### File: [glossary_translation_update_dialog.py](../../components/glossary_translation_update_dialog.py)

#### Class: `Class GlossaryTranslationUpdateDialog(QDialog)`

*Manual updater for strings affected by a glossary translation change.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`_build_ui(self)`**
  *Description*: Internal helper to create ui.

- **`_populate_occurrences(self)`**
  *Description*: Internal helper to populate occurrences.

- **`_format_occurrence_label(self, number, occ)`**
  *Description*: Internal helper to format occurrence label.

- **`_refresh_occurrence_item(self, occ)`**
  *Description*: Internal helper to update the occurrence item.

- **`_load_occurrence(self, row)`**
  *Description*: Internal helper to load occurrence.

- **`_current_occurrence(self)`**
  *Description*: Internal helper to current occurrence.

- **`_suggest_translation(self, current_text)`**
  *Description*: Internal helper to suggest translation.

- **`_apply_current(self, next_item)`**
  *Description*: Internal helper to apply current.

- **`_update_text_highlights(self)`**
  *Description*: Applies green background highlighting to the target terms in both editors using fuzzy matching.

- **`_skip_current(self)`**
  *Description*: Internal helper to skip current.

- **`_select_next(self)`**
  *Description*: Internal helper to select next.

- **`_run_ai_for_current(self)`**
  *Description*: Internal helper to run ai for current.

- **`_run_ai_for_all(self)`**
  *Description*: Internal helper to run ai for all.

- **`set_ai_busy(self, busy)`**
  *Description*: Set the ai busy.

- **`set_batch_active(self, active)`**
  *Description*: Set the batch active.

- **`on_ai_result(self, occurrence, new_translation)`**
  *Description*: Handle the ai result event.

- **`on_ai_error(self, message)`**
  *Description*: Handle the ai error event.

- **`_run_quick_replace_all(self)`**
  *Description*: Internal helper to run quick replace all.

- **`_on_old_translation_changed(self, text)`**
  *Description*: Internal helper to handle the old translation changed event.



---

### File: [help_dialog.py](../../components/help_dialog.py)

#### Functions

- **`show_shortcuts_dialog(parent)`**
  *Description*: Show shortcuts dialog.

#### Class: `Class HelpShortcutsDialog(QDialog)`

*Dialog class for help shortcuts.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.



---

### File: [labeled_spinbox.py](../../components/labeled_spinbox.py)

#### Class: `Class LabeledSpinBox(QWidget)`

*Labeled spin box implementation.*


##### Methods

- **`__init__(self, label_text, min_val, max_val, initial_val, tooltip, parent)`**
  *Description*: Initialize a new instance.

- **`value(self)`**
  *Description*: Value.

- **`setValue(self, value)`**
  *Description*: Setvalue.



---

### File: [original_text_analysis_dialog.py](../../components/original_text_analysis_dialog.py)

#### Class: `Class _BarItem(QGraphicsRectItem)`

*Bar item storing its index for selection syncing.*


##### Methods

- **`__init__(self, index)`**
  *Description*: Initialize a new instance.



#### Class: `Class _AnalysisBarView(QGraphicsView)`

*Specialised bar chart view with zoom/pan and selection callback.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`wheelEvent(self, event)`**
  *Description*: Wheelevent.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`mouseMoveEvent(self, event)`**
  *Description*: Mousemoveevent.

- **`mouseReleaseEvent(self, event)`**
  *Description*: Mousereleaseevent.

- **`_scroll(self, delta)`**
  *Description*: Internal helper to scroll.

- **`resizeEvent(self, event)`**
  *Description*: Resizeevent.

- **`set_entries(self, entries)`**
  *Description*: Populate the scene with bar items.

- **`highlight_bar(self, index)`**
  *Description*: Highlight bar.

- **`_fit_view_to_scene(self)`**
  *Description*: Internal helper to fit view to scene.



#### Class: `Class OriginalTextAnalysisDialog(QDialog)`

*Dialog displaying the top 100 wide strings.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`set_custom_title(self, title)`**
  *Description*: Set the custom title.

- **`show_entries(self, raw_entries, font_maps, initial_font, precomputed_entries, title, all_fonts_top_entries)`**
  *Description*: Show entries.

- **`_apply_font(self, font_name)`**
  *Description*: Internal helper to apply font.

- **`_update_summary(self, entries)`**
  *Description*: Internal helper to update the summary.

- **`_handle_bar_selected_for_table(self, index, table, chart_view)`**
  *Description*: Internal helper to handle bar selected for table.

- **`_handle_table_selection_for_chart(self, table, chart_view)`**
  *Description*: Internal helper to handle table selection for chart.

- **`_handle_table_double_click_ext(self, item, entries)`**
  *Description*: Internal helper to handle table double click ext.

- **`_on_font_changed(self, font_name)`**
  *Description*: Internal helper to handle the font changed event.



---

### File: [project_dialogs.py](../../components/project_dialogs.py)

#### Class: `Class NewProjectDialog(QDialog)`

*Dialog for creating a new translation project.  Collects: - Project name - Project directory (where to create the project) - Active plugin - Optional description*


##### Methods

- **`__init__(self, parent, available_plugins)`**
  *Description*: Initialize a new instance.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_populate_plugins(self)`**
  *Description*: Populate plugin dropdown with available plugins.

- **`_scan_plugins(self)`**
  *Description*: Scan plugins directory to find available plugins.

- **`_on_mode_changed(self)`**
  *Description*: Internal helper to handle the mode changed event.

- **`_on_auto_create_toggled(self, checked)`**
  *Description*: Internal helper to handle the auto create toggled event.

- **`_get_start_dir(self, current_path_text)`**
  *Description*: Internal helper to get the start dir.

- **`_update_last_dir(self, path)`**
  *Description*: Internal helper to update the last dir.

- **`_browse_directory(self)`**
  *Description*: Open directory picker for project location.

- **`_browse_source(self)`**
  *Description*: Internal helper to browse source.

- **`_browse_translation(self)`**
  *Description*: Internal helper to browse translation.

- **`_validate_and_accept(self)`**
  *Description*: Validate inputs before accepting.

- **`get_project_info(self)`**
  *Description*: Get project information after dialog is accepted.  Returns:     dict: Project information or None if cancelled



#### Class: `Class OpenProjectDialog(QDialog)`

*Dialog for opening an existing project.  Currently simple: just pick a .uiproj file or project directory. Can be extended with recent projects list.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_browse_file(self)`**
  *Description*: Browse for .uiproj file.

- **`_validate_and_accept(self)`**
  *Description*: Validate selected path before accepting.

- **`get_project_path(self)`**
  *Description*: Get selected project path after dialog is accepted.  Returns:     str: Project path or None if cancelled



#### Class: `Class ImportBlockDialog(QDialog)`

*Dialog for importing a new block (file) into an existing project.  Collects: - Source file path - Translation file path (optional) - Block name (optional, defaults to filename) - Description (optional)*


##### Methods

- **`__init__(self, parent, project_manager)`**
  *Description*: Initialize a new instance.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_browse_source_file(self)`**
  *Description*: Browse for source file.

- **`_browse_translation_file(self)`**
  *Description*: Browse for translation file.

- **`_on_source_file_selected(self, file_path)`**
  *Description*: Auto-fill block name from filename if not already set.

- **`_validate_and_accept(self)`**
  *Description*: Validate inputs before accepting.

- **`get_block_info(self)`**
  *Description*: Get block information after dialog is accepted.  Returns:     dict: Block information or None if cancelled



#### Class: `Class MoveToFolderDialog(QDialog)`

*Dialog for moving items to a specific virtual folder using a tree view.*


##### Methods

- **`__init__(self, parent, project_manager, current_folder_id)`**
  *Description*: Initialize a new instance.

- **`_setup_ui(self)`**
  *Description*: Internal helper to setup ui.

- **`_populate_tree(self)`**
  *Description*: Internal helper to populate tree.

- **`_add_folders_recursive(self, parent_item, folders)`**
  *Description*: Internal helper to add folders recursive.

- **`_create_new_folder(self)`**
  *Description*: Internal helper to create new folder.

- **`_select_by_id(self, folder_id)`**
  *Description*: Internal helper to select by id.

- **`_validate_and_accept(self)`**
  *Description*: Internal helper to validate and accept.

- **`get_selected_folder_id(self)`**
  *Description*: Get the selected folder id.



---

### File: [prompt_editor_dialog.py](../../components/prompt_editor_dialog.py)

#### Class: `Class PromptEditorDialog(QDialog)`

*Allow users to preview/edit AI system+user prompts before sending.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.

- **`get_user_inputs(self)`**
  *Description*: Return edited system prompt, user prompt, and save flag.



---

### File: [report_dialog.py](../../components/report_dialog.py)

#### Class: `Class LargeTextReportDialog(QDialog)`

*Dialog class for large text report.*


##### Methods

- **`__init__(self, title, text, parent)`**
  *Description*: Initialize a new instance.



---

### File: [search_panel.py](../../components/search_panel.py)

#### Class: `Class SearchLineEdit(QLineEdit)`

*Search line edit implementation.*


##### Methods

- **`__init__(self, parent, main_window)`**
  *Description*: Initialize a new instance.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`_get_x_for_index(self, idx)`**
  *Description*: Internal helper to get the x for index.

- **`contextMenuEvent(self, event)`**
  *Description*: Contextmenuevent.

- **`_replace_word(self, start, end, new_word)`**
  *Description*: Internal helper to replace word.



#### Class: `Class SearchPanelWidget(QWidget)`

*Widget component for search panel.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`_on_find_next_from_combobox_activation(self, text)`**
  *Description*: Internal helper to handle the find next from combobox activation event.

- **`_add_to_history(self, query)`**
  *Description*: Internal helper to add to history.

- **`_update_combobox_items(self)`**
  *Description*: Internal helper to update the combobox items.

- **`load_history(self, history_list)`**
  *Description*: Load history.

- **`get_history(self)`**
  *Description*: Get the history.

- **`_on_find_next(self)`**
  *Description*: Internal helper to handle the find next event.

- **`_on_find_previous(self)`**
  *Description*: Internal helper to handle the find previous event.

- **`_on_advanced_clicked(self)`**
  *Description*: Internal helper to handle the advanced clicked event.

- **`get_search_parameters(self)`**
  *Description*: Get the search parameters.

- **`set_search_options(self, case_sensitive, search_in_original, ignore_tags, is_fuzzy)`**
  *Description*: Set the search options.

- **`set_status_message(self, message, is_error)`**
  *Description*: Set the status message.

- **`focus_search_input(self)`**
  *Description*: Focus search input.

- **`clear_status(self)`**
  *Description*: Remove status.

- **`get_query(self)`**
  *Description*: Get the query.

- **`set_query(self, query)`**
  *Description*: Set the query.

- **`trigger_spellcheck(self)`**
  *Description*: Trigger spellcheck.



---

### File: [session_bootstrap_dialog.py](../../components/session_bootstrap_dialog.py)

#### Class: `Class SessionBootstrapDialog(QDialog)`

*Dialog that shows the system prompt and collects optional session instructions.*


##### Methods

- **`__init__(self, parent, system_prompt)`**
  *Description*: Initialize a new instance.

- **`get_instructions(self)`**
  *Description*: Get the instructions.



---

### File: [toast.py](../../components/toast.py)

#### Class: `Class ToastNotification(QWidget)`

*Toast notification implementation.*


##### Methods

- **`__init__(self, parent, message, duration, toast_type)`**
  *Description*: Initialize a new instance.

- **`position_toast(self, parent)`**
  *Description*: Position toast.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`show_toast_notification(self)`**
  *Description*: Show toast notification.

- **`start_fade_out(self)`**
  *Description*: Start fade out.

- **`close_and_cleanup(self)`**
  *Description*: Close and cleanup.

- **`show_toast(cls, parent, message, duration, toast_type)`**
  *Description*: Show toast.



---

### File: [translation_variations_dialog.py](../../components/translation_variations_dialog.py)

#### Class: `Class VariationsListDelegate(QStyledItemDelegate)`

*Delegate for drawing progress background under variations list items.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`paint(self, painter, option, index)`**
  *Description*: Paint.



#### Class: `Class TranslationVariationsDialog(QDialog)`

*Show multiple translation options and allow the user to pick one.*


##### Methods

- **`__init__(self, parent, variations, show_refresh)`**
  *Description*: Initialize a new instance.

- **`_load_state(self)`**
  *Description*: Internal helper to load state.

- **`_save_state(self)`**
  *Description*: Internal helper to save state.

- **`done(self, r)`**
  *Description*: Done.

- **`_on_refresh(self)`**
  *Description*: Internal helper to handle the refresh event.

- **`_populate_variations(self, variations)`**
  *Description*: Internal helper to populate variations.

- **`_update_preview(self)`**
  *Description*: Internal helper to update the preview.

- **`_apply_current_selection(self)`**
  *Description*: Internal helper to apply current selection.



---

### File: [tree_context_menu_mixin.py](../../components/tree_context_menu_mixin.py)

#### Class: `Class TreeContextMenuMixin`

*Builds and shows the right-click context menu.*


##### Methods

- **`show_context_menu(self, pos)`**
  *Description*: Show context menu.

- **`_revert_selected_to_original(self)`**
  *Description*: Internal helper to revert selected to original.

- **`_show_block_properties(self, block_idx)`**
  *Description*: Internal helper to show block properties.

- **`_get_selected_strings_by_block(self)`**
  *Description*: Internal helper to get the selected strings by block.

- **`_restore_selected_translations(self)`**
  *Description*: Internal helper to restore selected translations.

- **`_revert_all_blocks_to_original(self)`**
  *Description*: Internal helper to revert all blocks to original.



---

### File: [tree_drag_drop_mixin.py](../../components/tree_drag_drop_mixin.py)

#### Class: `Class TreeDragDropMixin`

*Custom drag-and-drop logic: visual pixmap, above/on/below drop positions.*


##### Methods

- **`startDrag(self, supportedActions)`**
  *Description*: Capture selected items BEFORE Qt can change hover/current state.

- **`dragMoveEvent(self, event)`**
  *Description*: Dragmoveevent.

- **`dragLeaveEvent(self, event)`**
  *Description*: Dragleaveevent.

- **`dropEvent(self, event)`**
  *Description*: Dropevent.



---

### File: [tree_folder_mixin.py](../../components/tree_folder_mixin.py)

#### Class: `Class TreeFolderMixin`

*Handles folder create/rename/delete, sync_tree_to_project_manager, and expansion state.*


##### Methods

- **`_handle_item_changed(self, item, column)`**
  *Description*: Internal helper to handle item changed.

- **`_create_folder_at_cursor(self)`**
  *Description*: Internal helper to create folder at cursor.

- **`_rename_folder(self, item)`**
  *Description*: Trigger in-place edit (single, non-compacted folder).

- **`_rename_folder_by_id(self, folder_id, current_name)`**
  *Description*: Open a dialog to rename a folder (used for compacted items).

- **`_delete_folder(self, item)`**
  *Description*: Internal helper to remove folder.

- **`_delete_folder_by_id(self, item, folder_id)`**
  *Description*: Temporarily swap folder_id so the handler sees the right target folder.

- **`_create_subfolder(self, item)`**
  *Description*: Internal helper to create subfolder.

- **`_create_subfolder_by_id(self, folder_id)`**
  *Description*: Internal helper to create subfolder by id.

- **`_handle_item_state_changed(self, item)`**
  *Description*: Persist expand/collapse state to ProjectManager and refresh compaction.

- **`sync_tree_to_project_manager(self)`**
  *Description*: Rebuild the virtual folder structure in ProjectManager from the current tree layout.



---

### File: [tree_navigation_mixin.py](../../components/tree_navigation_mixin.py)

#### Class: `Class TreeNavigationMixin`

*Handles keyboard navigation between blocks/folders and toolbar move-up/down.*


##### Methods

- **`navigate_blocks(self, direction)`**
  *Description*: Navigate blocks.

- **`navigate_folders(self, direction)`**
  *Description*: Navigate folders.

- **`move_current_item(self, direction)`**
  *Description*: Move all selected items up (direction=-1) or down (direction=1).



---

### File: [tree_spellcheck_mixin.py](../../components/tree_spellcheck_mixin.py)

#### Class: `Class TreeSpellcheckMixin`

*Context-menu helpers: reveal block file in OS Explorer and block-level spellcheck.*


##### Methods

- **`_reveal_in_explorer(self, block_idx, is_translation)`**
  *Description*: Internal helper to reveal in explorer.

- **`_open_explorer_at_path(self, abs_path)`**
  *Description*: Internal helper to open explorer at path.

- **`_open_spellcheck_for_block(self, block_idx, category_name)`**
  *Description*: Internal helper to open spellcheck for block.



---

### File: [highlight_interface.py](../../components/editor/highlight_interface.py)

#### Class: `Class LNETHighlightInterface`

*L n e t highlight interface implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`_momentary_highlight_tag(self, block, start_in_block, length)`**
  *Description*: Internal helper to momentary highlight tag.

- **`_apply_all_extra_selections(self)`**
  *Description*: Internal helper to apply all extra selections.

- **`addCriticalProblemHighlight(self, line_number)`**
  *Description*: Addcriticalproblemhighlight.

- **`removeCriticalProblemHighlight(self, line_number)`**
  *Description*: Removecriticalproblemhighlight.

- **`clearCriticalProblemHighlights(self)`**
  *Description*: Clearcriticalproblemhighlights.

- **`hasCriticalProblemHighlight(self, line_number)`**
  *Description*: Hascriticalproblemhighlight.

- **`addWarningLineHighlight(self, line_number)`**
  *Description*: Addwarninglinehighlight.

- **`removeWarningLineHighlight(self, line_number)`**
  *Description*: Removewarninglinehighlight.

- **`clearWarningLineHighlights(self)`**
  *Description*: Clearwarninglinehighlights.

- **`hasWarningLineHighlight(self, line_number)`**
  *Description*: Haswarninglinehighlight.

- **`addWidthExceededHighlight(self, line_number)`**
  *Description*: Addwidthexceededhighlight.

- **`removeWidthExceededHighlight(self, line_number)`**
  *Description*: Removewidthexceededhighlight.

- **`clearWidthExceededHighlights(self)`**
  *Description*: Clearwidthexceededhighlights.

- **`hasWidthExceededHighlight(self, line_number)`**
  *Description*: Haswidthexceededhighlight.

- **`addShortLineHighlight(self, line_number)`**
  *Description*: Addshortlinehighlight.

- **`removeShortLineHighlight(self, line_number)`**
  *Description*: Removeshortlinehighlight.

- **`clearShortLineHighlights(self)`**
  *Description*: Clearshortlinehighlights.

- **`hasShortLineHighlight(self, line_number)`**
  *Description*: Hasshortlinehighlight.

- **`addEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Addemptyoddsublinehighlight.

- **`removeEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Removeemptyoddsublinehighlight.

- **`clearEmptyOddSublineHighlights(self)`**
  *Description*: Clearemptyoddsublinehighlights.

- **`hasEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Hasemptyoddsublinehighlight.

- **`setPreviewSelectedLineHighlight(self, line_number)`**
  *Description*: Setpreviewselectedlinehighlight.

- **`clearPreviewSelectedLineHighlight(self)`**
  *Description*: Clearpreviewselectedlinehighlight.

- **`setLinkedCursorPosition(self, line_number, column_number)`**
  *Description*: Setlinkedcursorposition.

- **`applyQueuedHighlights(self)`**
  *Description*: Applyqueuedhighlights.

- **`clearAllProblemTypeHighlights(self)`**
  *Description*: Clearallproblemtypehighlights.

- **`addProblemLineHighlight(self, line_number)`**
  *Description*: Addproblemlinehighlight.

- **`removeProblemLineHighlight(self, line_number)`**
  *Description*: Removeproblemlinehighlight.

- **`clearProblemLineHighlights(self)`**
  *Description*: Clearproblemlinehighlights.

- **`hasProblemHighlight(self, line_number)`**
  *Description*: Hasproblemhighlight.



---

### File: [line_number_area.py](../../components/editor/line_number_area.py)

#### Class: `Class LineNumberArea(QWidget)`

*Line number area implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`sizeHint(self)`**
  *Description*: Sizehint.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`mouseDoubleClickEvent(self, event)`**
  *Description*: Mousedoubleclickevent.

- **`mouseMoveEvent(self, event)`**
  *Description*: Mousemoveevent.

- **`leaveEvent(self, event)`**
  *Description*: Leaveevent.



---

### File: [line_number_area_paint_logic.py](../../components/editor/line_number_area_paint_logic.py)

#### Class: `Class LNETLineNumberAreaPaintLogic`

*L n e t line number area paint logic implementation.*


##### Methods

- **`__init__(self, editor, helpers, main_window)`**
  *Description*: Initialize a new instance.

- **`execute_paint_event(self, event, painter_device)`**
  *Description*: Execute paint event.



---

### File: [line_numbered_text_edit.py](../../components/editor/line_numbered_text_edit.py)

#### Class: `Class LineNumberedTextEdit(QPlainTextEdit)`

*Line numbered text edit implementation.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`handle_line_number_click(self, y_pos)`**
  *Description*: Handle line number click.

- **`handle_line_number_double_click(self, y_pos)`**
  *Description*: Handle line number double click.

- **`set_glossary_manager(self, manager)`**
  *Description*: Set the glossary manager.

- **`_replace_word_at_cursor(self, word_cursor, replacement)`**
  *Description*: Replace the word selected by the given cursor with the replacement text.

- **`_open_spellcheck_dialog_for_selection(self, position_in_widget_coords)`**
  *Description*: Internal helper to open spellcheck dialog for selection.

- **`_apply_corrected_text_to_editor(self, corrected_text, line_numbers)`**
  *Description*: Internal helper to apply corrected text to editor.

- **`mouseMoveEvent(self, event)`**
  *Description*: Mousemoveevent.

- **`setPlainText(self, text)`**
  *Description*: Setplaintext.

- **`calculate_block_guidelines(self, block, font_map, sequences, limit_px, default_tag_mappings)`**
  *Description*: Calculate block guidelines.

- **`recalculate_guidelines(self)`**
  *Description*: Recalculate guidelines.

- **`reset_selection_state(self)`**
  *Description*: Explicitly reset all selection tracking and visual highlights.

- **`handle_line_number_area_mouse_move(self, event)`**
  *Description*: Handle line number area mouse move.

- **`get_selected_lines(self)`**
  *Description*: Get the selected lines.

- **`set_selected_lines(self, lines)`**
  *Description*: Set the selected lines.

- **`clear_selection(self)`**
  *Description*: Remove selection.

- **`_update_selection_highlight(self)`**
  *Description*: Internal helper to update the selection highlight.

- **`_emit_selection_changed(self)`**
  *Description*: Internal helper to emit selection changed.

- **`leaveEvent(self, event)`**
  *Description*: Leaveevent.

- **`_find_glossary_entry_at(self, pos)`**
  *Description*: Internal helper to find glossary entry at.

- **`_find_warning_tooltip_at(self, pos)`**
  *Description*: Internal helper to find warning tooltip at.

- **`_set_theme_colors(self, main_window_ref)`**
  *Description*: Internal helper to set the theme colors.

- **`_create_tag_button(self, parent_widget, display, open_tag, close_tag, menu)`**
  *Description*: Internal helper to create tag button.

- **`populateContextMenu(self, menu, position_in_widget_coords)`**
  *Description*: Populatecontextmenu.

- **`_update_auxiliary_widths(self)`**
  *Description*: Internal helper to update the auxiliary widths.

- **`setFont(self, font)`**
  *Description*: Setfont.

- **`wheelEvent(self, event)`**
  *Description*: Wheelevent.

- **`keyPressEvent(self, event)`**
  *Description*: Keypressevent.

- **`setReadOnly(self, ro)`**
  *Description*: Setreadonly.

- **`lineNumberAreaWidth(self)`**
  *Description*: Linenumberareawidth.

- **`updateLineNumberAreaWidth(self, _)`**
  *Description*: Updatelinenumberareawidth.

- **`updateLineNumberArea(self, rect, dy)`**
  *Description*: Updatelinenumberarea.

- **`resizeEvent(self, event)`**
  *Description*: Resizeevent.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`lineNumberAreaPaintEvent(self, event, painter_device)`**
  *Description*: Linenumberareapaintevent.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.

- **`super_mousePressEvent(self, event)`**
  *Description*: Super mousepressevent.

- **`mouseReleaseEvent(self, event)`**
  *Description*: Mousereleaseevent.

- **`super_mouseReleaseEvent(self, event)`**
  *Description*: Super mousereleaseevent.

- **`mouseDoubleClickEvent(self, event)`**
  *Description*: Mousedoubleclickevent.

- **`super_mouseDoubleClickEvent(self, event)`**
  *Description*: Super mousedoubleclickevent.

- **`_get_icon_sequences(self)`**
  *Description*: Internal helper to get the icon sequences.

- **`_find_icon_sequence_in_block(self, block_text, sequences, position_in_block)`**
  *Description*: Internal helper to find icon sequence in block.

- **`_snap_cursor_out_of_icon_sequences(self, move_right)`**
  *Description*: Internal helper to snap cursor out of icon sequences.

- **`_momentary_highlight_tag(self, block, start_in_block, length)`**
  *Description*: Internal helper to momentary highlight tag.

- **`_apply_all_extra_selections(self)`**
  *Description*: Internal helper to apply all extra selections.

- **`addCriticalProblemHighlight(self, line_number)`**
  *Description*: Addcriticalproblemhighlight.

- **`removeCriticalProblemHighlight(self, line_number)`**
  *Description*: Removecriticalproblemhighlight.

- **`clearCriticalProblemHighlights(self)`**
  *Description*: Clearcriticalproblemhighlights.

- **`hasCriticalProblemHighlight(self, line_number)`**
  *Description*: Hascriticalproblemhighlight.

- **`addWarningLineHighlight(self, line_number)`**
  *Description*: Addwarninglinehighlight.

- **`removeWarningLineHighlight(self, line_number)`**
  *Description*: Removewarninglinehighlight.

- **`clearWarningLineHighlights(self)`**
  *Description*: Clearwarninglinehighlights.

- **`hasWarningLineHighlight(self, line_number)`**
  *Description*: Haswarninglinehighlight.

- **`addWidthExceededHighlight(self, line_number)`**
  *Description*: Addwidthexceededhighlight.

- **`removeWidthExceededHighlight(self, line_number)`**
  *Description*: Removewidthexceededhighlight.

- **`clearWidthExceededHighlights(self)`**
  *Description*: Clearwidthexceededhighlights.

- **`hasWidthExceededHighlight(self, line_number)`**
  *Description*: Haswidthexceededhighlight.

- **`addShortLineHighlight(self, line_number)`**
  *Description*: Addshortlinehighlight.

- **`removeShortLineHighlight(self, line_number)`**
  *Description*: Removeshortlinehighlight.

- **`clearShortLineHighlights(self)`**
  *Description*: Clearshortlinehighlights.

- **`hasShortLineHighlight(self, line_number)`**
  *Description*: Hasshortlinehighlight.

- **`addEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Addemptyoddsublinehighlight.

- **`removeEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Removeemptyoddsublinehighlight.

- **`clearEmptyOddSublineHighlights(self)`**
  *Description*: Clearemptyoddsublinehighlights.

- **`hasEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Hasemptyoddsublinehighlight.

- **`clearPreviewSelectedLineHighlight(self)`**
  *Description*: Clearpreviewselectedlinehighlight.

- **`setLinkedCursorPosition(self, line_number, column_number)`**
  *Description*: Setlinkedcursorposition.

- **`applyQueuedHighlights(self)`**
  *Description*: Applyqueuedhighlights.

- **`clearAllProblemTypeHighlights(self)`**
  *Description*: Clearallproblemtypehighlights.

- **`addProblemLineHighlight(self, line_number)`**
  *Description*: Addproblemlinehighlight.

- **`removeProblemLineHighlight(self, line_number)`**
  *Description*: Removeproblemlinehighlight.

- **`clearProblemLineHighlights(self)`**
  *Description*: Clearproblemlinehighlights.

- **`hasProblemHighlight(self, line_number)`**
  *Description*: Hasproblemhighlight.

- **`handle_mass_set_font(self)`**
  *Description*: Handle mass set font.

- **`handle_mass_set_width(self)`**
  *Description*: Handle mass set width.

- **`game_dialog_max_width_pixels(self)`**
  *Description*: Game dialog max width pixels.

- **`game_dialog_max_width_pixels(self, val)`**
  *Description*: Game dialog max width pixels.

- **`line_width_warning_threshold_pixels(self)`**
  *Description*: Line width warning threshold pixels.

- **`line_width_warning_threshold_pixels(self, val)`**
  *Description*: Line width warning threshold pixels.

- **`show_width_guideline(self)`**
  *Description*: Show width guideline.

- **`show_width_guideline(self, val)`**
  *Description*: Show width guideline.



---

### File: [lnet_context_menu_logic.py](../../components/editor/lnet_context_menu_logic.py)

#### Class: `Class LNETContextMenuLogic`

*L n e t context menu logic implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`_find_tag_at(self, position_in_widget_coords)`**
  *Description*: Internal helper to find tag at.

- **`populate(self, menu, position_in_widget_coords)`**
  *Description*: Populate.



---

### File: [lnet_dialogs.py](../../components/editor/lnet_dialogs.py)

#### Class: `Class MassFontDialog(QDialog)`

*Dialog class for mass font.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`populate_fonts(self, main_window)`**
  *Description*: Populate fonts.

- **`get_selected_font(self)`**
  *Description*: Get the selected font.



#### Class: `Class MassWidthDialog(QDialog)`

*Dialog class for mass width.*


##### Methods

- **`__init__(self, parent)`**
  *Description*: Initialize a new instance.

- **`get_width(self)`**
  *Description*: Get the width.

- **`set_default_width(self)`**
  *Description*: Set the default width.

- **`on_auto_width_toggled(self, checked)`**
  *Description*: Handle the auto width toggled event.

- **`is_auto_width(self)`**
  *Description*: Check if is auto width.



---

### File: [lnet_editor_setup.py](../../components/editor/lnet_editor_setup.py)

#### Functions

- **`set_theme_colors(editor, main_window_ref)`**
  *Description*: Apply theme-specific colors to the editor and its line number area.

- **`create_tag_button(editor, parent_widget, display, open_tag, close_tag, menu)`**
  *Description*: Create a small button for inserting or wrapping text with a game tag.

- **`update_auxiliary_widths(editor)`**
  *Description*: Recalculate pixel-width display area and preview indicator area widths.

---

### File: [lnet_highlight_wrappers.py](../../components/editor/lnet_highlight_wrappers.py)

#### Class: `Class LNETHighlightWrappers`

*L n e t highlight wrappers implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`addCriticalProblemHighlight(self, line_number)`**
  *Description*: Addcriticalproblemhighlight.

- **`removeCriticalProblemHighlight(self, line_number)`**
  *Description*: Removecriticalproblemhighlight.

- **`clearCriticalProblemHighlights(self)`**
  *Description*: Clearcriticalproblemhighlights.

- **`hasCriticalProblemHighlight(self, line_number)`**
  *Description*: Hascriticalproblemhighlight.

- **`addWarningLineHighlight(self, line_number)`**
  *Description*: Addwarninglinehighlight.

- **`removeWarningLineHighlight(self, line_number)`**
  *Description*: Removewarninglinehighlight.

- **`clearWarningLineHighlights(self)`**
  *Description*: Clearwarninglinehighlights.

- **`hasWarningLineHighlight(self, line_number)`**
  *Description*: Haswarninglinehighlight.

- **`addWidthExceededHighlight(self, line_number)`**
  *Description*: Addwidthexceededhighlight.

- **`removeWidthExceededHighlight(self, line_number)`**
  *Description*: Removewidthexceededhighlight.

- **`clearWidthExceededHighlights(self)`**
  *Description*: Clearwidthexceededhighlights.

- **`hasWidthExceededHighlight(self, line_number)`**
  *Description*: Haswidthexceededhighlight.

- **`addShortLineHighlight(self, line_number)`**
  *Description*: Addshortlinehighlight.

- **`removeShortLineHighlight(self, line_number)`**
  *Description*: Removeshortlinehighlight.

- **`clearShortLineHighlights(self)`**
  *Description*: Clearshortlinehighlights.

- **`hasShortLineHighlight(self, line_number)`**
  *Description*: Hasshortlinehighlight.

- **`addEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Addemptyoddsublinehighlight.

- **`removeEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Removeemptyoddsublinehighlight.

- **`clearEmptyOddSublineHighlights(self)`**
  *Description*: Clearemptyoddsublinehighlights.

- **`hasEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Hasemptyoddsublinehighlight.



---

### File: [lnet_keyboard_handler.py](../../components/editor/lnet_keyboard_handler.py)

#### Class: `Class LNETKeyboardHandler`

*Handles keyboard input for LineNumberedTextEdit.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`handle_key_press(self, event)`**
  *Description*: Process key press event. Returns True if the event was consumed.



---

### File: [lnet_spellcheck_logic.py](../../components/editor/lnet_spellcheck_logic.py)

#### Class: `Class LNETSpellcheckLogic`

*L n e t spellcheck logic implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`open_dialog_for_selection(self, position_in_widget_coords)`**
  *Description*: Open dialog for selection.

- **`apply_corrected_text(self, corrected_text, line_numbers)`**
  *Description*: Apply corrected text.



---

### File: [lnet_tag_helpers.py](../../components/editor/lnet_tag_helpers.py)

#### Class: `Class LNETTagHelpers`

*L n e t tag helpers implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`find_icon_sequence_in_block(self, block_text, sequences, position_in_block)`**
  *Description*: Find icon sequence in block.

- **`snap_cursor_out_of_icon_sequences(self, move_right)`**
  *Description*: Snap cursor out of icon sequences.



---

### File: [lnet_tooltips.py](../../components/editor/lnet_tooltips.py)

#### Class: `Class LNETTooltipLogic`

*L n e t tooltip logic implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`find_warning_tooltip_at(self, pos)`**
  *Description*: Find warning tooltip at.



---

### File: [mouse_handlers.py](../../components/editor/mouse_handlers.py)

#### Class: `Class LNETMouseHandlers`

*L n e t mouse handlers implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`_get_icon_sequences(self)`**
  *Description*: Internal helper to get the icon sequences.

- **`_find_icon_sequence_hit(self, cursor, sequences)`**
  *Description*: Internal helper to find icon sequence hit.

- **`_move_cursor_to_icon_sequence_end(self, block, start_in_block, end_in_block, token)`**
  *Description*: Internal helper to move cursor to icon sequence end.

- **`_wrap_selection_with_color(self, color_name)`**
  *Description*: Internal helper to wrap selection with color.

- **`insert_single_tag(self, tag)`**
  *Description*: Insert single tag.

- **`wrap_selection_with_custom_tags(self, open_tag, close_tag)`**
  *Description*: Wrap selection with custom tags.

- **`copy_tag_to_clipboard(self, tag_text_curly)`**
  *Description*: Copy tag to clipboard.

- **`get_tag_at_cursor(self, cursor, pattern)`**
  *Description*: Get the tag at cursor.

- **`showContextMenu(self, pos)`**
  *Description*: Showcontextmenu.

- **`mouseReleaseEvent(self, event)`**
  *Description*: Mousereleaseevent.

- **`handle_line_number_click(self, y_pos)`**
  *Description*: Handle a click on the line number area.

- **`handle_line_number_double_click(self, y_pos)`**
  *Description*: Handle a double-click on the line number area.

- **`handle_line_number_area_mouse_move(self, event)`**
  *Description*: Show tooltip when hovering over the line number area.

- **`_get_line_index_from_y(self, y)`**
  *Description*: Get the block number for a given y coordinate.

- **`mousePressEvent(self, event)`**
  *Description*: Mousepressevent.



---

### File: [paint_event_logic.py](../../components/editor/paint_event_logic.py)

#### Class: `Class LNETPaintEventLogic`

*L n e t paint event logic implementation.*


##### Methods

- **`__init__(self, editor, helpers)`**
  *Description*: Initialize a new instance.

- **`execute_paint_event(self, event)`**
  *Description*: Execute paint event.



---

### File: [paint_handlers.py](../../components/editor/paint_handlers.py)

#### Class: `Class LNETPaintHandlers`

*L n e t paint handlers implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`paintEvent(self, event)`**
  *Description*: Paintevent.

- **`lineNumberAreaPaintEvent(self, event, painter_device)`**
  *Description*: Linenumberareapaintevent.



---

### File: [paint_helpers.py](../../components/editor/paint_helpers.py)

#### Class: `Class LNETPaintHelpers`

*L n e t paint helpers implementation.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`_map_no_tag_index_to_raw_text_index(self, raw_qtextline_text, line_text_segment_no_tags, target_no_tag_index_in_segment)`**
  *Description*: Internal helper to map no tag index to raw text index.



---

### File: [text_highlight_manager.py](../../components/editor/text_highlight_manager.py)

#### Class: `Class TextHighlightManager`

*Manager class for text highlight.*


##### Methods

- **`__init__(self, editor)`**
  *Description*: Initialize a new instance.

- **`_create_block_background_selection(self, block, color, use_full_width)`**
  *Description*: Internal helper to create block background selection.

- **`_create_search_match_selection(self, block_number, start_char_in_block, length, color)`**
  *Description*: Internal helper to create search match selection.

- **`applyHighlights(self)`**
  *Description*: Applyhighlights.

- **`updateCurrentLineHighlight(self)`**
  *Description*: Updatecurrentlinehighlight.

- **`clearCurrentLineHighlight(self)`**
  *Description*: Clearcurrentlinehighlight.

- **`setLinkedCursorPosition(self, line_number, column_number)`**
  *Description*: Setlinkedcursorposition.

- **`clearLinkedCursorPosition(self)`**
  *Description*: Clearlinkedcursorposition.

- **`setPreviewSelectedLineHighlight(self, line_numbers)`**
  *Description*: Setpreviewselectedlinehighlight.

- **`set_background_for_lines(self, lines_to_highlight, lines_to_clear)`**
  *Description*: Set the background for lines.

- **`clearPreviewSelectedLineHighlight(self)`**
  *Description*: Clearpreviewselectedlinehighlight.

- **`setCategorizedLineHighlights(self, line_numbers, color)`**
  *Description*: Setcategorizedlinehighlights.

- **`clearCategorizedLineHighlights(self)`**
  *Description*: Clearcategorizedlinehighlights.

- **`addProblemLineHighlight(self, line_number)`**
  *Description*: Addproblemlinehighlight.

- **`addCriticalProblemHighlight(self, line_number, color)`**
  *Description*: Addcriticalproblemhighlight.

- **`removeCriticalProblemHighlight(self, line_number)`**
  *Description*: Removecriticalproblemhighlight.

- **`clearCriticalProblemHighlights(self)`**
  *Description*: Clearcriticalproblemhighlights.

- **`hasCriticalProblemHighlight(self, line_number)`**
  *Description*: Hascriticalproblemhighlight.

- **`addWarningLineHighlight(self, line_number, color)`**
  *Description*: Addwarninglinehighlight.

- **`removeWarningLineHighlight(self, line_number)`**
  *Description*: Removewarninglinehighlight.

- **`clearWarningLineHighlights(self)`**
  *Description*: Clearwarninglinehighlights.

- **`hasWarningLineHighlight(self, line_number)`**
  *Description*: Haswarninglinehighlight.

- **`momentaryHighlightTag(self, block, start_in_block, length)`**
  *Description*: Momentaryhighlighttag.

- **`clearTagInteractionHighlight(self)`**
  *Description*: Cleartaginteractionhighlight.

- **`add_search_match_highlight(self, block_number, start_char_in_block, length)`**
  *Description*: Add search match highlight.

- **`clear_search_match_highlights(self)`**
  *Description*: Remove search match highlights.

- **`add_width_exceed_char_highlight(self, block, char_index_in_block, color)`**
  *Description*: Add width exceed char highlight.

- **`clear_width_exceed_char_highlights(self)`**
  *Description*: Remove width exceed char highlights.

- **`addEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Addemptyoddsublinehighlight.

- **`removeEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Removeemptyoddsublinehighlight.

- **`clearEmptyOddSublineHighlights(self)`**
  *Description*: Clearemptyoddsublinehighlights.

- **`hasEmptyOddSublineHighlight(self, block_number)`**
  *Description*: Hasemptyoddsublinehighlight.

- **`clearAllProblemHighlights(self)`**
  *Description*: Clearallproblemhighlights.

- **`clearAllHighlights(self)`**
  *Description*: Clearallhighlights.

- **`update_zebra_stripes(self)`**
  *Description*: Update the zebra stripes.



---

## Component: `plugins`

### File: [base_game_rules.py](../../plugins/base_game_rules.py)

#### Class: `Class BaseGameRules`

*Base class for game-specific rules. Supports the 'Kruptar' format: strings delimited by {END} + empty line.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`load_data_from_json_obj(self, json_data)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, data, block_names)`**
  *Description*: Save data to json obj.

- **`get_enter_char(self)`**
  *Description*: Get the enter char.

- **`get_shift_enter_char(self)`**
  *Description*: Get the shift enter char.

- **`get_ctrl_enter_char(self)`**
  *Description*: Get the ctrl enter char.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.

- **`get_display_name(self)`**
  *Description*: Get the display name.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_color_marker_definitions(self)`**
  *Description*: Returns descriptions for manual color markers.

- **`get_spellcheck_ignore_pattern(self)`**
  *Description*: Returns a regex pattern of sequences to ignore during spellcheck (e.g. tags, control codes).

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process pasted segment.

- **`get_base_game_rules_class(self)`**
  *Description*: Get the base game rules class.

- **`get_default_tag_mappings(self)`**
  *Description*: Get the default tag mappings.

- **`get_dynamic_name_tags(self)`**
  *Description*: Return a mapping of {tag_string: replacement_name} for dynamic in-game names.  These tags are substituted *before* stripping tags during script-matching distillation, so that e.g. '{escape:0:0022}' in BMG text matches 'Epona' in the script. The dict key must be the exact tag string as it appears in editor text.

- **`get_tag_checker_handler(self)`**
  *Description*: Get the tag checker handler.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`get_plugin_actions(self)`**
  *Description*: Get the plugin actions.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`replace_tags_with_aliases(self, text)`**
  *Description*: Replace tags with aliases.

- **`replace_aliases_with_tags(self, text)`**
  *Description*: Replace aliases with tags.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`get_context_menu_actions(self, editor_widget, selected_text)`**
  *Description*: Get the context menu actions.

- **`calculate_string_width_override(self, text, font_map, default_char_width)`**
  *Description*: Calculate string width override.

- **`get_editor_page_size(self)`**
  *Description*: Get the editor page size.

- **`get_custom_context_tags(self)`**
  *Description*: Get the custom context tags.

- **`save_custom_context_tags(self, tags_data)`**
  *Description*: Save custom context tags.

- **`get_font_for_block(self, block_idx)`**
  *Description*: Returns a dict with 'original_font_name' and 'font_name' if block has specific font overrides.

- **`get_default_script_name(self)`**
  *Description*: Return the default script file name for this game. Override in subclasses if needed (e.g. 'zelda_mc_script.md').

- **`parse_walkthrough_transcript(self, file_path)`**
  *Description*: Parse game-specific walkthrough transcript text file into structured rooms and dialogue cues. Plugins should override this to handle custom separators, chapters, acts, speakers, etc.



---

### File: [config_factory.py](../../plugins/common/config_factory.py)

#### Functions

- **`generate_base_config(prefix, overrides, custom_problems)`**
  *Description*: Generate unified base problem configuration definitions for a plugin prefix.

---

### File: [problem_analyzer.py](../../plugins/common/problem_analyzer.py)

#### Class: `Class GenericProblemAnalyzer`

*Generic problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_check_bad_spacing(self, text)`**
  *Description*: Internal helper to check bad spacing.

- **`_check_missing_icon_spacing(self, text)`**
  *Description*: Internal helper to check missing icon spacing.

- **`_check_single_word_subline_generic(self, subline_text)`**
  *Description*: Internal helper to check single word subline generic.

- **`_is_single_word_ok_generic(self, subline_text)`**
  *Description*: Internal helper to check if is single word ok generic.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.



---

### File: [tag_manager.py](../../plugins/common/tag_manager.py)

#### Class: `Class GenericTagManager`

*Manager class for generic tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`reconfigure_styles(self)`**
  *Description*: Reconfigure styles.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`is_tag_legitimate(self, tag)`**
  *Description*: Check if is tag legitimate.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.



---

### File: [text_fixer.py](../../plugins/common/text_fixer.py)

#### Class: `Class GenericTextFixer`

*Generic text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_calculate_width(self, text, font_map)`**
  *Description*: Internal helper to calculate width.

- **`_extract_first_word_with_tags_generic(self, text)`**
  *Description*: Internal helper to extract first word with tags generic.

- **`_fix_width_exceeded_generic(self, text, font_map, threshold)`**
  *Description*: Internal helper to fix width exceeded generic.

- **`_fix_single_word_orphans_generic(self, text)`**
  *Description*: Internal helper to fix single word orphans generic.

- **`_merge_and_clean_pagination(self, text)`**
  *Description*: Internal helper to merge and clean pagination.

- **`_shift_split_sentences(self, text, lines_per_page, original_text, block_idx, string_idx)`**
  *Description*: Internal helper to shift split sentences.

- **`_compact_sentences_on_pages(self, text, font_map, threshold, lines_per_page)`**
  *Description*: Try to merge consecutive sentences onto the same page.  This step runs *after* _shift_split_sentences has already arranged text into pages (either via empty-line padding or via page-break escape codes).  Strategy: iterate over lines. Whenever line K ends a sentence and there are empty slot(s) remaining on the same physical page (K // lines_per_page), try to pull the next sentence onto that page by merging it with line K. If the merged+rewrapped text fits in the remaining page slots, keep the merge.  Otherwise leave everything unchanged.  This method NEVER pushes a sentence to a different page than the one it was placed on by _shift_split_sentences.  Sentence boundary: last visible character is one of ``.!?;`` (or a closing quote/paren after such char).  Lines containing page-break escape codes are always hard boundaries.

- **`autofix_page_local_wrapper(self, autofix_func, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx)`**
  *Description*: Autofix page local wrapper.



---

### File: [base_import_rules.py](../../plugins/import_plugins/base_import_rules.py)

#### Class: `Class BaseImportRules`

*Game rules and translation logic for Base import.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`parse_clipboard_text(self, clipboard_text)`**
  *Description*: Parse clipboard text.

- **`process_segment_for_insertion(self, segment_to_insert, original_data_string_for_context, game_rules, default_tag_mappings, editor_player_tag)`**
  *Description*: Process segment for insertion.

- **`apply_mappings_to_text(self, text_segment, mappings)`**
  *Description*: Застосовує надані мапінги до текстового сегмента. Повертає оброблений текст та прапорець, чи були зроблені зміни.



---

### File: [rules.py](../../plugins/import_plugins/kruptar_format/rules.py)

#### Functions

- **`_analyze_tags_for_issues_kruptar(processed_text, original_text, editor_player_tag)`**
  *Description*: Internal helper to analyze tags for issues kruptar.

#### Class: `Class ImportRules(BaseImportRules)`

*Game rules and translation logic for Import.*


##### Methods

- **`parse_clipboard_text(self, clipboard_text)`**
  *Description*: Parse clipboard text.

- **`process_segment_for_insertion(self, segment_to_insert, original_data_string_for_context, game_rules, default_tag_mappings, editor_player_tag)`**
  *Description*: Process segment for insertion.



---

### File: [problem_analyzer.py](../../plugins/plain_text/problem_analyzer.py)

#### Class: `Class ProblemAnalyzer(GenericProblemAnalyzer)`

*Problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_ends_with_sentence_punctuation_zww(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation zww.

- **`_check_short_line_zww(self, current_subline_text, next_subline_text, font_map, threshold)`**
  *Description*: Internal helper to check short line zww.

- **`check_for_empty_first_line_of_page(self, text)`**
  *Description*: Check for empty first line of page.

- **`analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit)`**
  *Description*: Analyze data string.

- **`analyze_subline(self)`**
  *Description*: Analyze subline.



---

### File: [rules.py](../../plugins/plain_text/rules.py)

#### Class: `Class ProblemIDs`

*Problem i ds implementation.*




#### Class: `Class GameRules(BaseGameRules)`

*Plain text game rules with problem detection and autofix.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize plain text game rules with problem analyzer and autofix.

- **`get_display_name(self)`**
  *Description*: Return the display name for this plugin.

- **`get_default_tag_mappings(self)`**
  *Description*: Get the default tag mappings.

- **`load_data_from_json_obj(self, json_obj)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, blocks, block_names)`**
  *Description*: Save data to json obj.

- **`get_tag_pattern(self)`**
  *Description*: Get the tag pattern.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`calculate_string_width_override(self, text, font_map, default_char_width)`**
  *Description*: Calculate string width override.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process pasted segment.



---

### File: [tag_logic.py](../../plugins/plain_text/tag_logic.py)

#### Functions

- **`_analyze_tags_for_issues_zww(processed_text, original_text)`**
  *Description*: Internal helper to analyze tags for issues zww.

- **`process_segment_tags_aggressively_zww(segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process segment tags aggressively zww.

---

### File: [tag_manager.py](../../plugins/plain_text/tag_manager.py)

#### Class: `Class TagManager(GenericTagManager)`

*Manager class for tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.



---

### File: [text_fixer.py](../../plugins/plain_text/text_fixer.py)

#### Class: `Class TextFixer(GenericTextFixer)`

*Text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_fix_empty_odd_sublines_zww(self, text)`**
  *Description*: Internal helper to fix empty odd sublines zww.

- **`_fix_short_lines_zww(self, text, font_map, threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines zww.

- **`_cleanup_spaces_around_tags_zww(self, text)`**
  *Description*: Internal helper to cleanup spaces around tags zww.

- **`fix_empty_first_line_of_page(self, text)`**
  *Description*: Fix empty first line of page.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.



---

### File: [problem_analyzer.py](../../plugins/pokemon_fr/problem_analyzer.py)

#### Class: `Class ProblemAnalyzer(GenericProblemAnalyzer)`

*Problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_get_sublines_from_data_string(self, data_string)`**
  *Description*: Internal helper to get the sublines from data string.

- **`_ends_with_sentence_punctuation(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation.

- **`_check_short_line(self, current_subline, next_subline, font_map, threshold)`**
  *Description*: Internal helper to check short line.

- **`analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit)`**
  *Description*: Analyze data string.

- **`analyze_subline(self, text)`**
  *Description*: Analyze subline.



---

### File: [rules.py](../../plugins/pokemon_fr/rules.py)

#### Class: `Class GameRules(BaseGameRules)`

*Game rules and translation logic for Game.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`load_data_from_json_obj(self, json_data)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, data, block_names)`**
  *Description*: Save data to json obj.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_enter_char(self)`**
  *Description*: Get the enter char.

- **`get_shift_enter_char(self)`**
  *Description*: Get the shift enter char.

- **`get_ctrl_enter_char(self)`**
  *Description*: Get the ctrl enter char.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_display_name(self)`**
  *Description*: Get the display name.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_default_tag_mappings(self)`**
  *Description*: Get the default tag mappings.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert)`**
  *Description*: Process pasted segment.



---

### File: [tag_manager.py](../../plugins/pokemon_fr/tag_manager.py)

#### Class: `Class TagManager(GenericTagManager)`

*Manager class for tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.



---

### File: [text_fixer.py](../../plugins/pokemon_fr/text_fixer.py)

#### Class: `Class TextFixer(GenericTextFixer)`

*Text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_get_sublines_with_tags(self, text)`**
  *Description*: Internal helper to get the sublines with tags.

- **`_reassemble_data_string(self, sublines_with_tags)`**
  *Description*: Internal helper to reassemble data string.

- **`_fix_width_exceeded(self, text, font_map, threshold)`**
  *Description*: Internal helper to fix width exceeded.

- **`_fix_short_lines(self, text, font_map, threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines.

- **`_fix_empty_sublines(self, text)`**
  *Description*: Internal helper to fix empty sublines.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.



---

### File: [problem_analyzer.py](../../plugins/zelda_bmg/problem_analyzer.py)

#### Class: `Class ProblemAnalyzer(GenericProblemAnalyzer)`

*Problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_ends_with_sentence_punctuation_zbmg(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation zbmg.

- **`_calculate_width(self, text, font_map)`**
  *Description*: Internal helper to calculate width.

- **`_check_short_line_zbmg(self, current_subline_text, next_subline_text, font_map, threshold)`**
  *Description*: Internal helper to check short line zbmg.

- **`check_for_empty_first_line_of_page(self, text)`**
  *Description*: Check for empty first line of page.

- **`analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit)`**
  *Description*: Analyze data string.

- **`analyze_subline(self)`**
  *Description*: Analyze subline.



---

### File: [rules.py](../../plugins/zelda_bmg/rules.py)

#### Class: `Class ProblemIDs`

*Problem i ds implementation.*




#### Class: `Class GameRules(BaseGameRules)`

*Game rules and translation logic for Game.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`get_dynamic_name_tags(self)`**
  *Description*: Twilight Princess BMG dynamic name escape tags.  In TP BMG files, the player name (Link) and the horse name (Epona) are stored as escape tags that the game replaces at runtime. These substitutions allow distilled script-matching to find strings that contain these tags by treating them as plain text.  Tag format in editor: {escape:<type>:<hex_data>}   - Link  -> {escape:0:0000} or {escape:0:0001}   - Epona -> {escape:0:0022}

- **`load_translation_map(self)`**
  *Description*: Load translation map.

- **`decode_string_with_mapping(self, s)`**
  *Description*: Decode CP1252 string (with active umlauts) into Ukrainian letters.

- **`encode_string_with_mapping(self, s)`**
  *Description*: Encode Ukrainian letters back into CP1252 characters for BMG compatibility.

- **`msg_to_editor_text(self, bmg_msg)`**
  *Description*: Convert BMG message parts to editor representation.

- **`editor_text_to_msg_content(self, text)`**
  *Description*: Convert editor representation back to BMG message parts list.

- **`load_data_from_json_obj(self, json_obj)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, data, block_names)`**
  *Description*: Save data to json obj.

- **`get_display_name(self)`**
  *Description*: Get the display name.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.

- **`get_spellcheck_ignore_pattern(self)`**
  *Description*: Get the spellcheck ignore pattern.

- **`get_editor_page_size(self)`**
  *Description*: Get the editor page size.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process pasted segment.

- **`calculate_string_width_override(self, text, font_map, default_char_width)`**
  *Description*: Calculate string width override.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.



---

### File: [tag_logic.py](../../plugins/zelda_bmg/tag_logic.py)

#### Functions

- **`_analyze_tags_for_issues_zbmg(processed_text, original_text)`**
  *Description*: Internal helper to analyze tags for issues zbmg.

- **`process_segment_tags_aggressively_zbmg(segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process segment tags aggressively zbmg.

---

### File: [tag_manager.py](../../plugins/zelda_bmg/tag_manager.py)

#### Class: `Class TagManager`

*Manager class for tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`reconfigure_styles(self)`**
  *Description*: Reconfigure styles.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.



---

### File: [text_fixer.py](../../plugins/zelda_bmg/text_fixer.py)

#### Class: `Class TextFixer(GenericTextFixer)`

*Text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_is_forced_alias(self, tag)`**
  *Description*: Internal helper to check if is forced alias.

- **`_fix_empty_odd_sublines_zbmg(self, text)`**
  *Description*: Internal helper to fix empty odd sublines zbmg.

- **`_fix_short_lines_zbmg(self, text, font_map, threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines zbmg.

- **`_cleanup_spaces_around_tags_zbmg(self, text)`**
  *Description*: Internal helper to cleanup spaces around tags zbmg.

- **`fix_empty_first_line_of_page(self, text)`**
  *Description*: Fix empty first line of page.

- **`_to_aliases(self, text)`**
  *Description*: Convert escape codes to user-facing {*} and {tab} aliases.

- **`_from_aliases(self, text)`**
  *Description*: Convert {*} and {tab} aliases back to escape codes.

- **`_split_into_star_sections(self, lines)`**
  *Description*: Split lines into sections: (is_star_section, [lines]). A star section starts at a line beginning with {*} and ends before the next {*} line. Lines before the first {*} form a plain section.

- **`_fix_star_section(self, section_lines, editor_font_map, threshold)`**
  *Description*: Merge all lines of a star section into clean text and re-split by width. First result line gets {*} prefix, subsequent lines get {tab} prefix. No space is inserted after {*} or {tab}.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.



---

### File: [problem_analyzer.py](../../plugins/zelda_mc/problem_analyzer.py)

#### Class: `Class ProblemAnalyzer(GenericProblemAnalyzer)`

*Problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_ends_with_sentence_punctuation_zmc(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation zmc.

- **`_check_short_line_zmc(self, current_subline_text, next_subline_text, font_map, threshold)`**
  *Description*: Internal helper to check short line zmc.

- **`_check_empty_odd_subline_display_zmc(self, subline_text, subline_qtextblock_number_in_editor, is_logically_single_and_empty_data_string)`**
  *Description*: Internal helper to check empty odd subline display zmc.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.



---

### File: [rules.py](../../plugins/zelda_mc/rules.py)

#### Class: `Class ProblemIDs`

*Problem i ds implementation.*




#### Class: `Class GameRules(BaseGameRules)`

*Game rules and translation logic for Game.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`load_data_from_json_obj(self, json_data)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, data, block_names)`**
  *Description*: Save data to json obj.

- **`get_display_name(self)`**
  *Description*: Get the display name.

- **`get_default_tag_mappings(self)`**
  *Description*: Get the default tag mappings.

- **`get_tag_checker_handler(self)`**
  *Description*: Get the tag checker handler.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_color_marker_definitions(self)`**
  *Description*: Get the color marker definitions.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`get_plugin_actions(self)`**
  *Description*: Get the plugin actions.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process pasted segment.

- **`get_base_game_rules_class(self)`**
  *Description*: Get the base game rules class.



---

### File: [tag_checker_handler.py](../../plugins/zelda_mc/tag_checker_handler.py)

#### Class: `Class TagCheckerHandler`

*Handler for tag checker operations.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`_get_initial_search_indices(self)`**
  *Description*: Internal helper to get the initial search indices.

- **`_get_tags_from_string(self, text)`**
  *Description*: Internal helper to get the tags from string.

- **`_find_tag_in_translation(self, original_tag_text, translation_line_text, used_translation_tag_spans)`**
  *Description*: No description.

- **`_highlight_mismatched_tag(self, original_block_idx_data, original_string_idx_data, tag_text, tag_start_char_in_string_data, tag_end_char_in_string_data)`**
  *Description*: Internal helper to highlight mismatched tag.

- **`_remove_mismatch_highlight(self)`**
  *Description*: Internal helper to remove mismatch highlight.

- **`_reset_search_state_and_ui(self)`**
  *Description*: Internal helper to reset search state and ui.

- **`_show_completion_popup(self, all_ok_during_run)`**
  *Description*: Internal helper to show completion popup.

- **`start_or_continue_check(self)`**
  *Description*: Start or continue check.



---

### File: [tag_logic.py](../../plugins/zelda_mc/tag_logic.py)

#### Functions

- **`analyze_tags_for_issues_zmc(processed_text, original_text, editor_player_tag)`**
  *Description*: Analyze tags for issues zmc.

- **`process_segment_tags_aggressively_zmc(segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process segment tags aggressively zmc.

---

### File: [tag_manager.py](../../plugins/zelda_mc/tag_manager.py)

#### Class: `Class TagManager(GenericTagManager)`

*Manager class for tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`reconfigure_styles(self)`**
  *Description*: Reconfigure styles.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`_ensure_exact_tags_loaded(self)`**
  *Description*: Internal helper to ensure exact tags loaded.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.



---

### File: [text_fixer.py](../../plugins/zelda_mc/text_fixer.py)

#### Class: `Class TextFixer(GenericTextFixer)`

*Text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_fix_empty_odd_sublines_zmc(self, text)`**
  *Description*: Internal helper to fix empty odd sublines zmc.

- **`_fix_short_lines_zmc(self, text, font_map, threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines zmc.

- **`_fix_blue_sublines_zmc(self, text)`**
  *Description*: Internal helper to fix blue sublines zmc.

- **`_fix_leading_spaces_in_sublines_zmc(self, text)`**
  *Description*: Internal helper to fix leading spaces in sublines zmc.

- **`_cleanup_spaces_around_tags_zmc(self, text)`**
  *Description*: Internal helper to cleanup spaces around tags zmc.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.



---

### File: [problem_analyzer.py](../../plugins/zelda_ww/problem_analyzer.py)

#### Class: `Class ProblemAnalyzer(GenericProblemAnalyzer)`

*Problem analyzer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)`**
  *Description*: Initialize a new instance.

- **`_ends_with_sentence_punctuation_zww(self, text_no_tags_stripped)`**
  *Description*: Internal helper to ends with sentence punctuation zww.

- **`_check_short_line_zww(self, current_subline_text, next_subline_text, font_map, threshold)`**
  *Description*: Internal helper to check short line zww.

- **`check_for_empty_first_line_of_page(self, text)`**
  *Description*: Check for empty first line of page.

- **`analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit)`**
  *Description*: Analyze data string.

- **`analyze_subline(self)`**
  *Description*: Analyze subline.



---

### File: [rules.py](../../plugins/zelda_ww/rules.py)

#### Class: `Class ProblemIDs`

*Problem i ds implementation.*




#### Class: `Class GameRules(BaseGameRules)`

*Game rules and translation logic for Game.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`load_data_from_json_obj(self, json_obj)`**
  *Description*: Load data from json obj.

- **`save_data_to_json_obj(self, data, block_names)`**
  *Description*: Save data to json obj.

- **`get_display_name(self)`**
  *Description*: Get the display name.

- **`get_problem_definitions(self)`**
  *Description*: Get the problem definitions.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.

- **`analyze_subline(self, text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug, logical_hard_limit)`**
  *Description*: Analyze subline.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.

- **`process_pasted_segment(self, segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process pasted segment.

- **`calculate_string_width_override(self, text, font_map, default_char_width)`**
  *Description*: Calculate string width override.

- **`get_short_problem_name(self, problem_id)`**
  *Description*: Get the short problem name.

- **`get_text_representation_for_preview(self, data_string)`**
  *Description*: Get the text representation for preview.

- **`get_text_representation_for_editor(self, data_string_subline)`**
  *Description*: Get the text representation for editor.

- **`convert_editor_text_to_data(self, text)`**
  *Description*: Convert editor text to data.

- **`get_enter_char(self)`**
  *Description*: Get the enter char.

- **`get_shift_enter_char(self)`**
  *Description*: Get the shift enter char.

- **`get_ctrl_enter_char(self)`**
  *Description*: Get the ctrl enter char.

- **`get_editor_page_size(self)`**
  *Description*: Get the editor page size.



---

### File: [tag_logic.py](../../plugins/zelda_ww/tag_logic.py)

#### Functions

- **`_analyze_tags_for_issues_zww(processed_text, original_text)`**
  *Description*: Internal helper to analyze tags for issues zww.

- **`process_segment_tags_aggressively_zww(segment_to_insert, original_text_for_tags, editor_player_tag_const)`**
  *Description*: Process segment tags aggressively zww.

---

### File: [tag_manager.py](../../plugins/zelda_ww/tag_manager.py)

#### Class: `Class TagManager`

*Manager class for tag.*


##### Methods

- **`__init__(self, main_window_ref)`**
  *Description*: Initialize a new instance.

- **`reconfigure_styles(self)`**
  *Description*: Reconfigure styles.

- **`get_syntax_highlighting_rules(self)`**
  *Description*: Get the syntax highlighting rules.

- **`get_legitimate_tags(self)`**
  *Description*: Get the legitimate tags.

- **`is_tag_legitimate(self, tag_to_check)`**
  *Description*: Check if is tag legitimate.



---

### File: [text_fixer.py](../../plugins/zelda_ww/text_fixer.py)

#### Class: `Class TextFixer(GenericTextFixer)`

*Text fixer implementation.*


##### Methods

- **`__init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref)`**
  *Description*: Initialize a new instance.

- **`_fix_empty_odd_sublines_zww(self, text)`**
  *Description*: Internal helper to fix empty odd sublines zww.

- **`_fix_short_lines_zww(self, text, font_map, threshold, logical_hard_limit)`**
  *Description*: Internal helper to fix short lines zww.

- **`_cleanup_spaces_around_tags_zww(self, text)`**
  *Description*: Internal helper to cleanup spaces around tags zww.

- **`fix_empty_first_line_of_page(self, text)`**
  *Description*: Fix empty first line of page.

- **`autofix_data_string(self, data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination)`**
  *Description*: Autofix data string.



---

## Component: `utils`

### File: [force_alias.py](../../utils/force_alias.py)

#### Functions

- **`apply_aliases_to_text(text, tag_mappings)`**
  *Description*: Replace original tags with their aliases in *text*.  ``tag_mappings`` maps ``{alias} -> {original_tag}``. We apply replacements longest-original-tag first to avoid partial substitutions.

- **`extract_force_aliases(text_with_aliases, tag_mappings)`**
  *Description*: Find Force aliases in *text_with_aliases* and replace them with plain words.  Returns ``(cleaned_text, mappings)`` where *cleaned_text* has Force alias tags replaced by their word values, and *mappings* records the association between each word and its original game tag.  Parameters ---------- text_with_aliases:     Text with aliases already applied (via :func:`apply_aliases_to_text`). tag_mappings:     The project's ``default_tag_mappings`` dict (``{alias: original_tag}``).

- **`prepare_text_for_ai(original_text, tag_mappings)`**
  *Description*: Full pipeline: apply aliases, then extract Force aliases into plain words.  Returns ``(text_with_force_words, force_mappings)``. The returned text still contains non-force tags (they are NOT stripped here; tag stripping is the responsibility of the caller or downstream logic).

- **`restore_force_aliases_in_translation(translated_text, force_mappings, glossary_translations)`**
  *Description*: For Force aliases, we do not perform any reverse restoration.  They remain as plain, translated text in the final output (e.g. 'Лінку'), which permanently freezes the dynamic name tag as plain text.

#### Class: `Class ForceAliasMapping`

*One resolved Force-alias entry.*




---

### File: [hotkey_manager.py](../../utils/hotkey_manager.py)

#### Class: `Class MSG(ctypes.Structure)`

*Windows MSG structure for parsing native events.*




#### Class: `Class HotkeyManager`

*Registers global hotkeys on Windows that bypass OS-level interception.*


##### Methods

- **`__init__(self, main_window)`**
  *Description*: Initialize a new instance.

- **`register(self)`**
  *Description*: Register all Alt+Shift hotkeys with Windows.

- **`unregister(self)`**
  *Description*: Unregister all hotkeys.

- **`handle_native_event(self, event_type, message)`**
  *Description*: Call this from MainWindow.nativeEvent(). Returns (handled: bool, result: int).

- **`_handle_repeat(self)`**
  *Description*: Poll keyboard state to emulate auto-repeat.

- **`_dispatch_hotkey(self, hid)`**
  *Description*: Dispatch the hotkey action to ListSelectionHandler.



---

### File: [logging_utils.py](../../utils/logging_utils.py)

#### Functions

- **`set_enabled_log_categories(categories)`**
  *Description*: Set the enabled log categories.

- **`update_logger_handlers(enable_console, enable_file, file_path)`**
  *Description*: Update the logger handlers.

- **`_should_log(category)`**
  *Description*: Internal helper to check if should log.

- **`_log_message(level, message, category, exc_info)`**
  *Description*: Internal helper to log message.

- **`log_debug(message, category)`**
  *Description*: Log debug.

- **`log_info(message, category)`**
  *Description*: Log info.

- **`log_warning(message, category)`**
  *Description*: Log warning.

- **`log_error(message, exc_info, category)`**
  *Description*: Log error.

- **`log_ai_traffic(mw, task_type, messages, response_text, error)`**
  *Description*: Log AI request and response traffic dynamically to both the main debug log (app_debug.txt) and a separate ai_traffic.log file in the workspace root if the 'log_ai_traffic' setting is enabled.

#### Class: `Class SafeRotatingFileHandler(RotatingFileHandler)`

*A robust subclass of RotatingFileHandler that gracefully handles PermissionError and OSError on Windows when the log file is locked by another process (e.g., during parallel pytest runs or multiple app instances). Instead of crashing or spamming stderr, it catches the error and continues writing to the current log file.*


##### Methods

- **`doRollover(self)`**
  *Description*: Dorollover.



#### Class: `Class DuplicateFilter(logging.Filter)`

*Filter that suppresses duplicate log messages that occur within a short time window. This prevents log spam from repeated identical messages.*


##### Methods

- **`__init__(self, time_window, max_history)`**
  *Description*: Initialize a new instance.

- **`filter(self, record)`**
  *Description*: Filter.



#### Class: `Class CategoryAdapter(logging.LoggerAdapter)`

*Category adapter implementation.*


##### Methods

- **`process(self, msg, kwargs)`**
  *Description*: Process.



---

### File: [syntax_highlighter.py](../../utils/syntax_highlighter.py)

#### Class: `Class JsonTagHighlighter(QSyntaxHighlighter)`

*Json tag highlighter implementation.*


##### Methods

- **`__init__(self, parent, main_window_ref, editor_widget_ref)`**
  *Description*: Initialize a new instance.

- **`on_contents_change(self, position, chars_removed, chars_added)`**
  *Description*: Handle the contents change event.

- **`set_glossary_manager(self, manager)`**
  *Description*: Set the glossary manager.

- **`set_spellchecker_enabled(self, enabled)`**
  *Description*: Enable or disable spellchecker highlighting.

- **`set_typing_mode(self, enabled, trigger_rehighlight)`**
  *Description*: Enable or disable typing mode which suppresses heavy checks like glossary and spellchecking.

- **`set_translation_mode(self, enabled, source_editor_ref)`**
  *Description*: Enable or disable translation-specific glossary highlighting.

- **`set_async_highlights(self, glossary_matches, translation_matches, spellcheck_matches)`**
  *Description*: Sets pre-calculated highlights from the background thread and triggers quick rehighlight.

- **`_apply_css_to_format(self, char_format, css_str, base_color)`**
  *Description*: Internal helper to apply css to format.

- **`reconfigure_styles(self, newline_symbol, newline_css_str, tag_css_str, show_multiple_spaces_as_dots, space_dot_color_hex, bracket_tag_color_hex)`**
  *Description*: Reconfigure styles.

- **`_invalidate_icon_cache(self)`**
  *Description*: Internal helper to invalidate icon cache.

- **`_rebuild_glossary_cache(self)`**
  *Description*: Internal helper to rebuild glossary cache.

- **`_rebuild_translation_glossary_cache(self)`**
  *Description*: Rebuilds the bridge translation glossary cache for the whole document.

- **`_ensure_icon_cache(self, sequences)`**
  *Description*: Internal helper to ensure icon cache.

- **`_get_icon_matches_for_text(self, text, sequences)`**
  *Description*: Internal helper to get the icon matches for text.

- **`_get_icon_matches_for_block(self, sequences)`**
  *Description*: Internal helper to get the icon matches for block.

- **`_get_icon_sequences(self)`**
  *Description*: Internal helper to get the icon sequences.

- **`_should_highlight_icons(self)`**
  *Description*: Internal helper to check if should highlight icons.

- **`_should_check_spelling(self)`**
  *Description*: Check if spellchecking should be performed for this widget.

- **`_extract_words_from_text(self, text)`**
  *Description*: Extract words from text, returning (start, end, word) tuples.

- **`_is_forced_alias(self, tag)`**
  *Description*: Internal helper to check if is forced alias.

- **`_tag_has_length(self, tag)`**
  *Description*: Internal helper to tag has length.

- **`_is_visible_tag(self, tag)`**
  *Description*: Internal helper to check if is visible tag.

- **`highlightBlock(self, text)`**
  *Description*: Highlightblock.



---

### File: [utils.py](../../utils/utils.py)

#### Functions

- **`remove_all_tags(text, tag_mappings)`**
  *Description*: Remove all tags.

- **`get_active_font_map()`**
  *Description*: Get the active font map.

- **`get_active_icon_sequences()`**
  *Description*: Get the active icon sequences.

- **`is_visible_tag(tag, mappings, font_map, icon_sequences)`**
  *Description*: Check if is visible tag.

- **`find_missing_icon_spacing_spans(text, is_visible_tag_func)`**
  *Description*: Find missing icon spacing spans.

- **`fix_missing_icon_spacing(text, is_visible_tag_func)`**
  *Description*: Fix missing icon spacing.

- **`clean_spaces(text)`**
  *Description*: Clean spaces.

- **`_get_trie_and_flat_map(font_map, default_char_width, icon_sequences, strict)`**
  *Description*: Internal helper to get the trie and flat map.

- **`get_active_tag_mappings()`**
  *Description*: Get the active tag mappings.

- **`get_tag_width(tag, default_tag_mappings, font_map, default_char_width, icon_sequences, strict)`**
  *Description*: Get the tag width.

- **`_calculate_string_width_impl(text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings)`**
  *Description*: Internal helper to calculate string width impl.

- **`calculate_string_width(text, font_map, default_char_width, icon_sequences, default_tag_mappings)`**
  *Description*: Calculate string width.

- **`calculate_strict_string_width(text, font_map, icon_sequences, default_tag_mappings)`**
  *Description*: Calculate strict string width.

- **`is_fuzzy_match(word1, word2, threshold)`**
  *Description*: Checks if two words are similar enough using SequenceMatcher. Ignores case.

- **`_make_replacer(line_len)`**
  *Description*: No docstring provided.

- **`convert_spaces_to_dots_for_display(text, enable_conversion)`**
  *Description*: Convert spaces to dots for display.

- **`convert_dots_to_spaces_from_editor(text)`**
  *Description*: Convert dots to spaces from editor.

- **`remove_curly_tags(text, tag_mappings)`**
  *Description*: Remove curly tags.

- **`convert_raw_to_display_text(raw_text, show_dots, newline_char_for_preview)`**
  *Description*: Convert raw to display text.

- **`prepare_text_for_tagless_search(text, keep_original_case)`**
  *Description*: Prepare text for tagless search.

- **`suggest_smart_translation(current_text, old_translation, new_translation)`**
  *Description*: Suggests a translation by replacing occurrences of the old translation with the new translation. Tries direct replacement first, then falls back to word-by-word morphological replacement. Supports case declensions for Slavic languages.

- **`shift_split_sentences(text, lines_per_page, prevent_empty_lines)`**
  *Description*: Shift split sentences.

- **`get_line_words_and_visible_tags(line, mw)`**
  *Description*: Get the line words and visible tags.

- **`shift_split_sentences_aligned(text, original_text, lines_per_page, prevent_empty_lines)`**
  *Description*: Shift split sentences aligned.

- **`extract_first_word_with_tags(text)`**
  *Description*: Extract first word with tags.

- **`has_visible_content(text, mappings, font_map, icon_sequences)`**
  *Description*: Check if has visible content.

- **`clean_and_map_punctuation(text)`**
  *Description*: Clean and map punctuation.

- **`find_smart_matches(text, query, case_sensitive)`**
  *Description*: Find smart matches.

#### Class: `Class TrieNode`

*Trie node implementation.*


##### Methods

- **`__init__(self)`**
  *Description*: Initialize a new instance.



---
