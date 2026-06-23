# ui/main_window/mempalace_actions.py
import os
import json
from PyQt6.QtWidgets import QMessageBox
from utils.logging_utils import log_info, log_error

class MempalaceActions:
    """Helper class containing MemePalace action methods for MainWindow."""
    def __init__(self, main_window):
        self.mw = main_window

    def open_mempalace_builder(self):
        """Open the MemePalace Context Builder dialog in modeless mode."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_builder_dialog') and self.mw.mempalace_builder_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_builder_dialog):
                    self.mw.mempalace_builder_dialog.show()
                    self.mw.mempalace_builder_dialog.raise_()
                    self.mw.mempalace_builder_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_builder_dialog = None

        from ui.mempalace_builder_dialog import MemePalaceBuilderDialog
        dialog = MemePalaceBuilderDialog(self.mw)
        self.mw.mempalace_builder_dialog = dialog
        dialog.show()

    def open_mempalace_viewer(self):
        """Open the MemePalace Database Viewer dialog."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_viewer_dialog') and self.mw.mempalace_viewer_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_viewer_dialog):
                    self.mw.mempalace_viewer_dialog.show()
                    self.mw.mempalace_viewer_dialog.raise_()
                    self.mw.mempalace_viewer_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_viewer_dialog = None

        from ui.mempalace_viewer_dialog import MemePalaceViewerDialog
        dialog = MemePalaceViewerDialog(self.mw)
        self.mw.mempalace_viewer_dialog = dialog
        dialog.show()

    def inspect_story_context(self):
        """Query and display visual context/timeline for the selected row from MemePalace without translating."""
        # 1. Verify that a project is loaded and a row is selected
        ds = getattr(self.mw, 'data_store', None)
        if not ds or ds.current_block_idx == -1 or ds.current_string_idx == -1:
            QMessageBox.warning(self.mw, "Story Inspector", "Please select a dialogue row to inspect.")
            return

        # 2. Get the current original text and IDs
        block_idx = ds.current_block_idx
        s_idx = ds.current_string_idx
        text, _ = self.mw.data_processor.get_current_string_text(block_idx, s_idx)
        if not text:
            QMessageBox.warning(self.mw, "Story Inspector", "Selected row is empty.")
            return

        # 3. Retrieve context via AIPromptComposer
        composer = None
        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
            
        if not composer:
            # Fallback to create composer if not present
            from handlers.translation.ai_prompt_composer import AIPromptComposer
            class DummyHandler:
                def __init__(self, mw):
                    self.mw = mw
                    self.data_processor = mw.data_processor
                    self.ui_updater = mw.ui_updater
                    self._glossary_manager = None
                    if hasattr(mw, 'translation_handler') and mw.translation_handler:
                        self._glossary_manager = getattr(mw.translation_handler, '_glossary_manager', None)
                def __getattr__(self, name):
                    return getattr(self.mw, name)
            composer = AIPromptComposer(DummyHandler(self.mw))
            
        story_context = composer._fetch_story_context(block_idx, s_idx, text)

        # Fetch character relations for the detected speaker(s)
        relations_html = ""
        script_res = composer._find_speaker_in_script(block_idx, s_idx, text)
        if not isinstance(script_res, (tuple, list)) or len(script_res) != 2:
            script_res = None
        client = composer._get_mempalace_client()
        
        # Deduce script line number and find Chapter AI Summary
        chapter_html = ""
        line_num = None
        if script_res and len(script_res) == 2:
            _, lines_str = script_res
            if lines_str and lines_str != "NONE":
                try:
                    line_num = int(lines_str.split(",")[0].strip())
                except Exception:
                    pass

        if line_num and client:
            wing_name = composer._get_wing_name()
            chapter_info = client.get_chapter_for_line(wing_name, line_num)
            if chapter_info:
                ch_title = f"Chapter {chapter_info['num']}: {chapter_info['title']}"
                ai_sum = chapter_info.get("ai_summary")
                if ai_sum:
                    events_list = None
                    try:
                        cleaned_json = ai_sum.strip()
                        if cleaned_json.startswith("```"):
                            lines_json = cleaned_json.splitlines()
                            if lines_json[0].startswith("```"):
                                lines_json = lines_json[1:]
                            if lines_json and lines_json[-1].startswith("```"):
                                lines_json = lines_json[:-1]
                            cleaned_json = "\n".join(lines_json).strip()
                        events_list = json.loads(cleaned_json)
                    except Exception:
                        events_list = None

                    if isinstance(events_list, list):
                        current_event = None
                        for ev in events_list:
                            if isinstance(ev, dict) and "start_line" in ev and "end_line" in ev:
                                if ev["start_line"] <= line_num <= ev["end_line"]:
                                    current_event = ev
                                    break
                        
                        events_html = ""
                        if current_event:
                            events_html += (
                                f"<div style='background-color: #e6f4ea; border-left: 4px solid #137333; padding: 8px; margin-bottom: 8px; border-radius: 4px;'>"
                                f"<b style='color: #137333;'>👉 Поточна подія (Current Event): {current_event.get('event_name', 'Без назви')} (Lines {current_event['start_line']}-{current_event['end_line']})</b><br>"
                                f"<span style='color: #202124;'>{current_event.get('summary_ukrainian', '')}</span>"
                                f"</div>"
                            )
                        else:
                            events_html += (
                                f"<div style='background-color: #fce8e6; border-left: 4px solid #c5221f; padding: 8px; margin-bottom: 8px; border-radius: 4px;'>"
                                f"<span style='color: #c5221f;'>Поточну подію для рядка {line_num} не знайдено в хронології.</span>"
                                f"</div>"
                            )
                            
                        timeline_items = []
                        for ev in events_list:
                            if isinstance(ev, dict) and "event_name" in ev:
                                is_current = (current_event and ev.get('event_name') == current_event.get('event_name') and ev.get('start_line') == current_event.get('start_line'))
                                marker = "<b>👉 [Поточна подія]</b> " if is_current else "• "
                                style = " style='background-color: #e2f0d9; padding: 4px 6px; border-radius: 3px; font-weight: bold;'" if is_current else ""
                                timeline_items.append(
                                    f"<div{style} style='padding: 2px 4px; margin-bottom: 2px;'>"
                                    f"{marker}{ev['event_name']} (Lines {ev.get('start_line')}-{ev.get('end_line')}): "
                                    f"<span style='color: #5f6368;'>{ev.get('summary_ukrainian', '')}</span>"
                                    f"</div>"
                                )
                        
                        timeline_html = "<br><b>Хронологія розділу (Timeline):</b><br>" + "".join(timeline_items)
                        
                        chapter_html = (
                            f"<div style='background-color: #f0f4f9; border-left: 4px solid #0078d7; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                            f"<b style='color: #0078d7; font-size: 14px;'>{ch_title}</b><br><br>"
                            f"{events_html}"
                            f"{timeline_html}"
                            f"</div>"
                        )
                    else:
                        chapter_html = (
                            f"<div style='background-color: #f0f4f9; border-left: 4px solid #0078d7; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                            f"<b style='color: #0078d7;'>{ch_title} (AI Summary):</b><br>"
                            f"<span style='font-style: italic; color: #333333;'>{ai_sum.replace(chr(10), '<br>')}</span>"
                            f"</div>"
                        )
                else:
                    chapter_html = (
                        f"<div style='background-color: #f3f3f3; border-left: 4px solid #cccccc; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                        f"<b style='color: #666666;'>{ch_title}</b> (AI Summary not analyzed yet)<br>"
                        f"</div>"
                    )

        if script_res and client:
            raw_spk, _ = script_res
            if raw_spk and raw_spk != "NONE":
                detected_speakers = [s.strip().upper() for s in raw_spk.split(",") if s.strip()]
                wing_name = composer._get_wing_name()
                all_relations = client.get_relations(wing_name)
                relevant_relations = []
                for r in all_relations:
                    src = r.get("source", "").strip().upper()
                    tgt = r.get("target", "").strip().upper()
                    if any(spk in src or spk in tgt for spk in detected_speakers):
                        relevant_relations.append(r)
                
                if relevant_relations:
                    relations_html = "<b>Character Relations (Відношення персонажів):</b><br>"
                    for r in relevant_relations:
                        src_trans = composer._translate_speaker(r['source'])
                        tgt_trans = composer._translate_speaker(r['target'])
                        rel_trans = r['relation']
                        if rel_trans == "addresses_informally":
                            rel_display = "звертається на 'ти' до"
                        elif rel_trans == "addresses_respectfully":
                            rel_display = "звертається на 'ви' до"
                        else:
                            rel_display = rel_trans
                        relations_html += f"• {src_trans} ({r['source']}) — <i>{rel_display}</i> —> {tgt_trans} ({r['target']})<br>"
                    relations_html += "<hr>"

        # 4. Display result
        if story_context:
            # Beautiful HTML-formatted dialogue box
            formatted_text = story_context.replace("\n", "<br>")
            
            QMessageBox.information(
                self.mw, 
                "Story Context Inspector",
                f"<h3>Story Context for Row #{s_idx + 1}</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{formatted_text}"
                f"</div>"
            )
        elif chapter_html:
            # We have no visual room context, but chapter timeline was successfully resolved
            raw_spk = "NONE"
            lines_str = "NONE"
            if script_res:
                raw_spk, lines_str = script_res
            
            trans_spk = composer._translate_speaker(raw_spk) if raw_spk != "NONE" else "NONE"
            spk_display = f"{trans_spk} ({raw_spk})" if raw_spk != "NONE" else "NONE"
            
            fallback_text = (
                f"<b>Location/Timeline Mapped from Script Chapter:</b><br>"
                f"• Speaker: <code>{spk_display}</code><br>"
                f"• Script Line: <code>{lines_str}</code><br>"
                f"• Timeline: Mapped from script sequence (No detailed visual context generated)."
            )
            
            QMessageBox.information(
                self.mw,
                "Story Context Inspector",
                f"<h3>Story Context for Row #{s_idx + 1}</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{fallback_text}"
                f"</div>"
            )
        else:
            # Gather debug variables
            db_path = client.db_path if client else "None"
            wing_name = composer._get_wing_name()
            block_label = composer._get_block_label(block_idx)
            bmg_id = f"{block_label}_Str_{s_idx}"
            
            script_info = ""
            if script_res:
                raw_spk, lines_str = script_res
                trans_spk = composer._translate_speaker(raw_spk) if raw_spk != "NONE" else "NONE"
                spk_display = f"{trans_spk} ({raw_spk})" if raw_spk != "NONE" else "NONE"
                script_info = (
                    f"<b>[Disk Script Fallback]</b><br>"
                    f"• Speaker: <code>{spk_display}</code><br>"
                    f"• Script Line: <code>{lines_str}</code><br><br>"
                )
            
            debug_info = (
                f"<b>[DEBUG INFO]</b><br>"
                f"• Client DB Path: <code>{db_path}</code><br>"
                f"• Wing Name: <code>{wing_name}</code><br>"
                f"• Block Label: <code>{block_label}</code><br>"
                f"• BMG ID Searched: <code>{bmg_id}</code><br>"
                f"• SQLite File Exists: <code>{os.path.exists(db_path) if db_path != 'None' else 'False'}</code>"
            )
            
            QMessageBox.information(
                self.mw,
                "Story Context Inspector",
                f"<h3>No Context Found</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{script_info}"
                f"{debug_info}<br><br>"
                f"Please ensure you selected the correct file/block and active game plugin!"
                f"</div>"
            )
