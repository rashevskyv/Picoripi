import re
import os
from pathlib import Path
from PyQt6.QtWidgets import QComboBox, QMainWindow
from PyQt6.QtGui import QColor, QPalette
from .base_ui_updater import BaseUIUpdater
from utils.utils import log_debug
from core.mempalace.story_timeline import StoryStringContext, StoryVirtualProjection
from core.story_context_overrides import get_story_context_override

class StringSettingsUpdater(BaseUIUpdater):
    """String settings updater implementation."""
    def __init__(self, main_window, data_processor):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor)
        self.highlight_style = (
            "QComboBox, QSpinBox { "
            "  border: 2px solid rgb(186, 85, 211); "
            "  background-color: rgba(186, 85, 211, 40); "
            "  border-radius: 3px; "
            "} "
            "QSpinBox QLineEdit { "
            "  background: transparent; "
            "  border: none; "
            "}"
        )
        self._story_context_cache = {}
        self._reference_items_cache = {}
        self._projection_context_indices = {}

    def clear_story_context_cache(self) -> None:
        self._story_context_cache.clear()
        self._reference_items_cache.clear()
        self._projection_context_indices.clear()

    def _projection_context_index(self, projection: StoryVirtualProjection):
        cached = self._projection_context_indices.get(projection.document_id)
        if cached is not None:
            return cached
        index = {}

        def visit(folder, path):
            current_path = path + (folder.title,)
            for mapping in folder.mappings:
                key = (str(mapping.game_block_id), int(mapping.string_index))
                index[key] = {
                    "structure_id": folder.id,
                    "path": current_path,
                    "speakers": [],
                }
            for child in folder.children:
                visit(child, current_path)

        for root in projection.roots:
            visit(root, ())
        for speaker in projection.speakers:
            for mapping in speaker.mappings:
                key = (str(mapping.game_block_id), int(mapping.string_index))
                entry = index.setdefault(key, {
                    "structure_id": None,
                    "path": (),
                    "speakers": [],
                })
                if speaker.name not in entry["speakers"]:
                    entry["speakers"].append(speaker.name)
        self._projection_context_indices[projection.document_id] = index
        return index

    @staticmethod
    def _story_structure_choices(projection: StoryVirtualProjection):
        """Return selectable structure ids and their full visible paths."""
        choices = []

        def visit(folder, path):
            current = path + (folder.title,)
            choices.append((folder.id, current))
            for child in folder.children:
                visit(child, current)

        for root in projection.roots:
            visit(root, ())
        return choices

    def _apply_normalized_story_speaker(self, block_idx: int, string_idx: int) -> None:
        """Make normalized Markup Studio relations the only visible speaker source."""
        composer_owner = getattr(self.mw, "translation_handler", None)
        prompt_composer = getattr(composer_owner, "prompt_composer", None)
        client = prompt_composer._get_mempalace_client() if prompt_composer else None

        projection = None
        ui_updater = getattr(self.mw, "ui_updater", None)
        block_updater = getattr(ui_updater, "block_list_updater", None)
        cached = getattr(block_updater, "_story_projection_cache", None)
        if isinstance(cached, StoryVirtualProjection):
            projection = cached
        elif client:
            candidate = client.get_story_virtual_projection()
            if isinstance(candidate, StoryVirtualProjection):
                projection = candidate

        speakers = ()
        contexts = ()
        item_name = None
        item_cache = getattr(block_updater, "_story_item_mappings_cache", {})
        if isinstance(item_cache, dict):
            item_name = item_cache.get((block_idx, string_idx))
        if client and projection and projection.document_id is not None:
            cache_key = (projection.document_id, block_idx, string_idx)
            contexts = self._story_context_cache.get(cache_key)
            if contexts is None:
                entry = self._projection_context_index(projection).get(
                    (str(block_idx), int(string_idx))
                )
                contexts = tuple(
                    StoryStringContext(
                        entry["structure_id"], tuple(entry["path"]), speaker
                    )
                    for speaker in (entry["speakers"] or [None])
                ) if entry is not None else ()
                self._story_context_cache[cache_key] = contexts
            speakers = tuple(dict.fromkeys(
                context.speaker_name
                for context in contexts
                if context.speaker_name
            ))
            if item_name:
                item_key = (projection.document_id, "item", item_name)
                item_context = self._story_context_cache.get(item_key)
                if item_context is None:
                    item_context = client.get_reference_item_context(
                        projection.document_id, item_name
                    )
                    self._story_context_cache[item_key] = item_context or False
                if item_context is False:
                    item_context = None
                contexts = (item_context,) if item_context is not None else ()
        role = "item" if item_name else "speaker"
        manual = get_story_context_override(self.mw, block_idx, string_idx)
        manual_speaker = str(manual.get("speaker") or "").strip()
        if manual_speaker and role == "speaker":
            speakers = (manual_speaker,)
        manual_structure_id = manual.get("structure_id")
        manual_structure_path = tuple(manual.get("structure_path") or ())
        if manual_structure_id is not None:
            contexts = (
                StoryStringContext(manual_structure_id, manual_structure_path, manual_speaker or None),
            )
        current = item_name or (", ".join(speakers) if speakers else "None")
        tooltip = (
            "Reference item from Markup Studio. Double-click to open its Items folder."
            if role == "item" else
            "Speaker from the current Markup Studio Story Context. "
            "Select another speaker here or open the linked line in Markup Studio."
        )

        combo = getattr(self.mw, "speaker_combobox", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("None")
            if role == "item" and projection and client:
                references = self._reference_items_cache.get(projection.document_id)
                if references is None:
                    references = client.get_reference_items(projection.document_id)
                    self._reference_items_cache[projection.document_id] = references
                for reference in references:
                    if reference.name != "None":
                        combo.addItem(reference.name)
            elif projection:
                for name in sorted(
                    (speaker.name for speaker in projection.speakers),
                    key=str.casefold,
                ):
                    if name != "None":
                        combo.addItem(name)
            current_index = combo.findText(current)
            if not isinstance(current_index, int) or current_index < 0:
                combo.addItem(current)
            combo.setCurrentText(current)
            combo._last_displayed_char = current
            combo._story_role = role
            combo.setEnabled(True)
            combo.setToolTip(tooltip)
            combo.blockSignals(False)

        chapter_label = getattr(self.mw, "chapter_value_label", None)
        if chapter_label is not None:
            context = next(
                (value for value in contexts if value.structure_id is not None),
                None,
            )
            structure_id = context.structure_id if context is not None else None
            display = " › ".join(context.structure_path) if context is not None else "No chapter"
            chapter_label.story_structure_id = structure_id
            if isinstance(chapter_label, QComboBox):
                chapter_label.blockSignals(True)
                chapter_label.clear()
                chapter_label.addItem("No chapter", None)
                if projection:
                    for folder_id, path in self._story_structure_choices(projection):
                        chapter_label.addItem(" › ".join(path), folder_id)
                selected = chapter_label.findData(structure_id)
                if selected < 0 and structure_id is not None:
                    chapter_label.addItem(display, structure_id)
                    selected = chapter_label.count() - 1
                chapter_label.setCurrentIndex(max(selected, 0))
                chapter_label.setEnabled(projection is not None)
                chapter_label.blockSignals(False)
            else:
                chapter_label.setText(display)
                chapter_label.setEnabled(context is not None)

        label = getattr(self.mw, "speaker_label", None)
        if label is not None:
            label.setText(f"Speaker: {current}")
            label.setToolTip(tooltip)
        select_label = getattr(self.mw, "speaker_select_label", None)
        if select_label is not None:
            select_label.setText("Item:" if role == "item" else "Speaker:")
            select_label.setToolTip(
                tooltip + " Double-click this label to open the matching virtual block."
            )
        studio_button = getattr(
            self.mw, "open_current_string_in_markup_studio_button", None
        )
        if studio_button is not None:
            studio_button.setEnabled(block_idx >= 0 and string_idx >= 0)

    def update_font_combobox(self):
        """Update the font combobox."""
        self.mw.font_combobox.blockSignals(True)
        self.mw.font_combobox.clear()

        default_font_display_text = f"Default ({self.mw.default_font_file or 'None'})"
        self.mw.font_combobox.addItem(default_font_display_text, "default")

        all_fonts = getattr(self.mw, 'all_font_maps', {})
        if all_fonts:
            for font_key in sorted(all_fonts.keys()):
                if font_key != self.mw.default_font_file:
                    self.mw.font_combobox.addItem(font_key, font_key)
        
        self.mw.font_combobox.blockSignals(False)

    def update_string_settings_panel(self):
        """Update the string settings panel."""
        default_style_sheet = self.mw.styleSheet() 

        block_idx = self.mw.data_store.physical_block_idx
        string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            self.mw.font_combobox.setEnabled(False)
            self.mw.width_spinbox.setEnabled(False)
            self.mw.apply_width_button.setEnabled(False)
            self.mw.font_combobox.setCurrentIndex(0)
            self.mw.width_spinbox.setValue(0)
            self.mw.width_spinbox.setStyleSheet("")
            self.mw.font_combobox.setStyleSheet("")
            if hasattr(self.mw, 'speaker_label') and self.mw.speaker_label:
                self.mw.speaker_label.setText("")
            if hasattr(self.mw, 'speaker_combobox') and self.mw.speaker_combobox:
                self.mw.speaker_combobox.blockSignals(True)
                self.mw.speaker_combobox.clear()
                self.mw.speaker_combobox.setEnabled(False)
                self.mw.speaker_combobox._last_displayed_char = None
                self.mw.speaker_combobox.setToolTip("Select or type speaker name for this string")
                self.mw.speaker_combobox.blockSignals(False)
            if hasattr(self.mw, 'speaker_select_label') and self.mw.speaker_select_label:
                self.mw.speaker_select_label.setToolTip("Select or type speaker name for this string")
            chapter_label = getattr(self.mw, "chapter_value_label", None)
            if chapter_label is not None:
                if isinstance(chapter_label, QComboBox):
                    chapter_label.blockSignals(True)
                    chapter_label.clear()
                    chapter_label.addItem("No chapter", None)
                    chapter_label.blockSignals(False)
                else:
                    chapter_label.setText("No chapter")
                chapter_label.story_structure_id = None
                chapter_label.setEnabled(False)
            window_value = getattr(self.mw, "window_kind_value_label", None)
            if window_value is not None:
                window_value.setText("Unknown")
            return

        self.mw.font_combobox.setEnabled(True)
        self.mw.width_spinbox.setEnabled(True)

        # Update speaker assignments
        if False and hasattr(self.mw, 'speaker_combobox') and self.mw.speaker_combobox is not None:
            self.mw.speaker_combobox.blockSignals(True)
            self.mw.speaker_combobox.clear()
            self.mw.speaker_combobox.setEnabled(True)
            
            unique_speakers = set()
            project = getattr(self.mw, 'project_manager', None) and self.mw.project_manager.project
            if project:
                for block in project.blocks:
                    assignments = block.metadata.get("character_assignments", {})
                    unique_speakers.update(assignments.values())
            
            # Query MemePalace for characters as well
            client = None
            composer = getattr(self.mw, "translation_handler", None)
            if composer and hasattr(composer, "prompt_composer"):
                client = composer.prompt_composer._get_mempalace_client()

            mempalace_speakers = set()
            if client:
                wing_name = composer.prompt_composer._get_wing_name() if hasattr(composer, "prompt_composer") else "Zelda_TP"
                if hasattr(client, "_bmg_to_context") and client._bmg_to_context:
                    for bmg_id_key, ctx_info in client._bmg_to_context.items():
                        if bmg_id_key.startswith("[") and bmg_id_key.endswith("]"):
                            continue
                        speaker = ctx_info.get("speaker")
                        if speaker and str(speaker).strip() and str(speaker).lower() not in ("unknown", "none"):
                            speaker_name = str(speaker).strip()
                            if hasattr(self.mw, 'list_selection_handler'):
                                indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id_key)
                                if indices:
                                    mempalace_speakers.add(speaker_name)
                
                # Fallback to loading script mappings + script file if cache is empty
                if not mempalace_speakers and hasattr(composer, "prompt_composer"):
                    script_path = composer.prompt_composer._find_script_path()
                    if script_path and os.path.exists(script_path):
                        line_to_speaker = getattr(composer.prompt_composer, "_line_to_speaker_cache", None)
                        cached_path = getattr(composer.prompt_composer, "_line_to_speaker_path", None)
                        if not line_to_speaker or cached_path != script_path:
                            try:
                                lines = getattr(composer.prompt_composer, "_script_lines_cache", None)
                                if not lines:
                                    try:
                                        with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                                            lines = f.readlines()
                                    except Exception:
                                        with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                                            lines = f.readlines()
                                    composer.prompt_composer._script_lines_cache = lines
                                
                                def line_strip_is_speaker(s: str) -> bool:
                                    return s.isupper() and len(s) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s) is not None

                                line_to_speaker = {}
                                current_speaker = None
                                for idx, line in enumerate(lines):
                                    line_strip = line.strip()
                                    if not line_strip:
                                        continue
                                    if line_strip.startswith("[") and line_strip.endswith("]"):
                                        continue
                                    if line_strip_is_speaker(line_strip):
                                        current_speaker = line_strip
                                    if current_speaker:
                                        line_to_speaker[idx + 1] = current_speaker
                                
                                composer.prompt_composer._line_to_speaker_cache = line_to_speaker
                                composer.prompt_composer._line_to_speaker_path = script_path
                            except Exception as e_parse:
                                from utils.logging_utils import log_error
                                log_error(f"Error building line_to_speaker map in string_settings_updater: {e_parse}")
                                line_to_speaker = None
                        
                        if line_to_speaker:
                            all_mappings = client.get_all_chapter_mappings(wing_name)
                            for ch_id, ch_maps in all_mappings.items():
                                for mapping in ch_maps:
                                    bmg_id_key = mapping.get("bmg_id")
                                    script_line = mapping.get("script_line")
                                    if bmg_id_key and script_line:
                                        speaker = line_to_speaker.get(script_line)
                                        if speaker and str(speaker).strip() and str(speaker).lower() not in ("unknown", "none"):
                                            speaker_name = str(speaker).strip()
                                            if hasattr(self.mw, 'list_selection_handler'):
                                                indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id_key)
                                                if indices:
                                                    mempalace_speakers.add(speaker_name)

            unique_speakers.update(mempalace_speakers)
            unique_speakers = {c for c in unique_speakers if c and str(c).strip()}
            
            self.mw.speaker_combobox.addItem("")
            self.mw.speaker_combobox.addItem("None")
            for c in sorted(unique_speakers):
                if c != "None":
                    self.mw.speaker_combobox.addItem(c)
                
            curr_speaker = ""
            if block_idx != -1 and string_idx != -1 and block_idx not in (-2, -3) and project:
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                # Fallback attribute verification to avoid comparison TypeError in tests
                try:
                    blocks_len = len(project.blocks)
                except Exception:
                    blocks_len = 1
                if proj_b_idx < blocks_len:
                    curr_speaker = project.blocks[proj_b_idx].metadata.get("character_assignments", {}).get(str(string_idx), "")
                
                # Fallback to MemePalace speaker if not assigned in project metadata
                if not curr_speaker and client:
                    # Resolve block label
                    block_label = ""
                    if proj_b_idx < blocks_len:
                        block_label = project.blocks[proj_b_idx].name
                    else:
                        name_key = str(block_idx)
                        if hasattr(self.mw, 'data_store') and self.mw.data_store and \
                           self.mw.data_store.block_names and name_key in self.mw.data_store.block_names:
                            b_desc = self.mw.data_store.block_names[name_key]
                            if "Message ID" in b_desc:
                                block_label = b_desc.partition("(")[0].strip()
                    if not block_label:
                        block_label = f"Block_{block_idx}"
                    
                    bmg_id = f"{block_label}_Str_{string_idx}"
                    ctx = client.get_cached_context(bmg_id, None)
                    if ctx and ctx.get("speaker"):
                        spk = str(ctx["speaker"]).strip()
                        if spk and spk.lower() not in ("unknown", "none"):
                            curr_speaker = spk
                            
                if not curr_speaker and composer and hasattr(composer, "prompt_composer"):
                    raw_text = ""
                    try:
                        if hasattr(self.mw, 'data_store') and self.mw.data_store.data:
                            if 0 <= block_idx < len(self.mw.data_store.data):
                                block_data = self.mw.data_store.data[block_idx]
                                if 0 <= string_idx < len(block_data):
                                    raw_text = block_data[string_idx] or ""
                    except Exception:
                        pass
                    result = composer.prompt_composer._find_speaker_in_script(block_idx, string_idx, raw_text)
                    if result and isinstance(result, (tuple, list)) and len(result) == 2:
                        raw_spk, _ = result
                        if raw_spk and raw_spk != "NONE" and raw_spk.lower() not in ("unknown", "none"):
                            curr_speaker = raw_spk

            if not curr_speaker:
                curr_speaker = "None"
            self.mw.speaker_combobox.setCurrentText(curr_speaker)
            self.mw.speaker_combobox._last_displayed_char = curr_speaker
            self.mw.speaker_combobox.blockSignals(False)

        # Update Speaker Label instantly from MemePalace cache
        if False and hasattr(self.mw, 'speaker_label') and self.mw.speaker_label:
            speaker_text = ""
            
            block_label = ""
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
               self.mw.project_manager.project and block_idx < len(self.mw.project_manager.project.blocks):
                block_label = self.mw.project_manager.project.blocks[block_idx].name
            else:
                name_key = str(block_idx)
                if hasattr(self.mw, 'data_store') and self.mw.data_store and \
                   self.mw.data_store.block_names and name_key in self.mw.data_store.block_names:
                    b_desc = self.mw.data_store.block_names[name_key]
                    if "Message ID" in b_desc:
                        block_label = b_desc.partition("(")[0].strip()
                
                if not block_label and hasattr(self.mw, 'data_store') and self.mw.data_store:
                    json_path = getattr(self.mw.data_store, "json_path", None)
                    if json_path and isinstance(json_path, (str, bytes)):
                        block_label = os.path.splitext(os.path.basename(json_path))[0]
                        
                if not block_label:
                    block_label = f"Block_{block_idx}"
            
            bmg_id = f"{block_label}_Str_{string_idx}"
            
            raw_text = ""
            try:
                if hasattr(self.mw, 'data_store') and self.mw.data_store.data:
                    if 0 <= block_idx < len(self.mw.data_store.data):
                        block_data = self.mw.data_store.data[block_idx]
                        if 0 <= string_idx < len(block_data):
                            raw_text = block_data[string_idx] or ""
            except Exception:
                pass
            
            composer = None
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
                
            if not composer:
                try:
                    from handlers.translation.ai_prompt_composer import AIPromptComposer
                    class DummyHandler:
                        def __init__(self, mw):
                            self.mw = mw
                            self.data_processor = mw.data_processor
                            self.ui_updater = mw.ui_updater
                            self._glossary_manager = getattr(mw, '_glossary_manager', None)
                        def __getattr__(self, name):
                            return getattr(self.mw, name)
                    if not hasattr(self.mw, '_temp_prompt_composer') or self.mw._temp_prompt_composer is None:
                        self.mw._temp_prompt_composer = AIPromptComposer(DummyHandler(self.mw))
                    composer = self.mw._temp_prompt_composer
                except Exception:
                    pass
                    
            if composer:
                result = composer._find_speaker_in_script(block_idx, string_idx, raw_text)
                if result and isinstance(result, (tuple, list)) and len(result) == 2:
                    raw_spk, matched_lines_str = result
                else:
                    raw_spk, matched_lines_str = "NONE", None

                if raw_spk == "NONE":
                    speaker_text = "Speaker: NONE"
                    tooltip_text = "Speaker for the current line mapped from MemePalace"
                else:
                    trans_spk = composer._translate_speaker(raw_spk)
                    speaker_text = f"Speaker: {trans_spk} ({raw_spk})"
                    
                    tooltip_text = ""
                    font_size = getattr(self.mw, 'tooltip_font_size', 11)
                    if matched_lines_str:
                        tooltip_text = f"<div style='font-size: {font_size}px;'>Matching lines in script: <font color='#2e7d32'><b>{matched_lines_str}</b></font></div>"
                    else:
                        tooltip_text = f"<div style='font-size: {font_size}px;'>Speaker for the current line mapped from MemePalace</div>"
                        
                    # Fetch speaker details from glossary
                    glossary_manager = None
                    if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                        glossary_manager = getattr(self.mw.translation_handler, '_glossary_manager', None)
                    if glossary_manager and raw_spk and raw_spk != "NONE":
                        spk_parts = [s.strip() for s in raw_spk.split(",") if s.strip()]
                        glossary_infos = []
                        for spk in spk_parts:
                            entry = glossary_manager.get_entry(spk)
                            if entry:
                                info = f"• <b>{entry.original}</b>"
                                if entry.translation:
                                    info += f" —> <font color='#2e7d32'><b>{entry.translation}</b></font>"
                                if entry.notes:
                                    try:
                                        import markdown
                                        notes_html = markdown.markdown(entry.notes, extensions=['nl2br'])
                                        info += f"<br><div style='margin-left: 15px; font-weight: normal;'>{notes_html}</div>"
                                    except Exception:
                                        info += f"<br><div style='margin-left: 15px; font-style: italic; font-weight: normal;'>{entry.notes}</div>"
                                glossary_infos.append(info)
                        if glossary_infos:
                            tooltip_text += f"<br><div style='font-size: {font_size}px;'><b>Glossary Info:</b><br>" + "<br>".join(glossary_infos) + "</div>"
            else:
                speaker_text = "Speaker: NONE"
                tooltip_text = "Speaker for the current line mapped from MemePalace"
            
            if hasattr(self.mw, 'speaker_label') and self.mw.speaker_label:
                self.mw.speaker_label.setToolTip(tooltip_text)
                self.mw.speaker_label.setText(speaker_text)
            if hasattr(self.mw, 'speaker_combobox') and self.mw.speaker_combobox:
                self.mw.speaker_combobox.setToolTip(tooltip_text)
            if hasattr(self.mw, 'speaker_select_label') and self.mw.speaker_select_label:
                self.mw.speaker_select_label.setToolTip(tooltip_text)

        # The normalized story model is authoritative. This intentionally overwrites
        # every legacy project/cache/regex value calculated above.
        self._apply_normalized_story_speaker(block_idx, string_idx)

        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})

        # Plugin window-kind layout for this string (widths/font/pagination)
        from utils.utils import resolve_string_layout
        rules = getattr(self.mw, 'current_game_rules', None)
        kind_layout = resolve_string_layout(rules, block_idx, string_idx)

        # Window kind label near the editors
        kind_value_label = getattr(self.mw, 'window_kind_value_label', None)
        if kind_value_label is not None:
            kind_name = None
            if rules is not None and hasattr(rules, 'get_preview_window_style'):
                try:
                    style = rules.get_preview_window_style(block_idx=block_idx, string_idx=string_idx)
                    if isinstance(style, dict):
                        val = style.get('kind_name')
                        if isinstance(val, str) and val:
                            kind_name = val
                except Exception:
                    kind_name = None
            if kind_name:
                kind_value_label.setText(kind_name)
            else:
                kind_value_label.setText("Unknown")

        # Update font: explicit override > window-kind font > default
        font_file = string_meta.get("font_file")
        layout_font = kind_layout.get("font_file")
        if not isinstance(layout_font, str) or not layout_font:
            layout_font = None
        if font_file and font_file != self.mw.default_font_file:
            index = self.mw.font_combobox.findData(font_file)
            if index != -1:
                self.mw.font_combobox.setCurrentIndex(index)
                self.mw.font_combobox.setStyleSheet(self.highlight_style)
            else:
                self.mw.font_combobox.setCurrentIndex(0)
                self.mw.font_combobox.setStyleSheet("")
        elif layout_font:
            index = self.mw.font_combobox.findData(layout_font)
            if index != -1:
                self.mw.font_combobox.setCurrentIndex(index)
                self.mw.font_combobox.setStyleSheet("")
            else:
                self.mw.font_combobox.setCurrentIndex(0)
                self.mw.font_combobox.setStyleSheet("")
        else:
            self.mw.font_combobox.setCurrentIndex(0)
            self.mw.font_combobox.setStyleSheet("")

        # Update width: explicit override > window-kind width > global setting
        width = string_meta.get("width")
        self.mw.width_spinbox.blockSignals(True)

        # Any stored positive value is an explicit override. A value equal to
        # the old global setting can still be custom for this window kind.
        if width:
            self.mw.width_spinbox.setValue(width)
            self.mw.width_spinbox.setStyleSheet(self.highlight_style)
        else:
            from utils.utils import resolve_width_limits
            _, effective_max = resolve_width_limits(
                string_meta, rules, block_idx, string_idx,
                getattr(self.mw, 'line_width_warning_threshold_pixels', 280),
                self.mw.game_dialog_max_width_pixels)
            self.mw.width_spinbox.setValue(effective_max)
            self.mw.width_spinbox.setStyleSheet("")
        self.mw.width_spinbox.blockSignals(False)
        self.mw.apply_width_button.setEnabled(False)

        # Update visibility of the Show Overrides Only checkbox dynamically when settings panel updates
        if hasattr(self.mw, 'show_overrides_only_checkbox') and hasattr(self.mw, 'ui_updater') and self.mw.ui_updater:
            preview_updater = getattr(self.mw.ui_updater, 'preview_updater', None)
            if preview_updater and hasattr(preview_updater, '_block_has_overrides'):
                show_overrides_only = getattr(self.mw.data_store, 'show_overrides_only', False)
                show_overrides_toggle = show_overrides_only or preview_updater._block_has_overrides(block_idx)
                self.mw.show_overrides_only_checkbox.setVisible(show_overrides_toggle)
