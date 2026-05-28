from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from core.translation.session_manager import TranslationSessionState
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug


class AIPromptComposer(BaseTranslationHandler):
    """Compose prompts for AI translation/variation tasks and manage placeholders."""

    # ------------------------------------------------------------------
    # Public API used by translation handler
    # ------------------------------------------------------------------
    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],  # kept for possible future use
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        return source_text or '', {}

    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
    ) -> str:
        return translated_text or ''

    # ------------------------------------------------------------------
    # Prompt composition helpers
    # ------------------------------------------------------------------
    def compose_batch_request(
        self,
        system_prompt: str,
        source_items: List[Dict],
        all_source_items: List[Dict],
        *,
        block_idx: Optional[int],
        mode_description: str,
        session_state: Optional[TranslationSessionState] = None,
        is_retry: bool = False,
        retry_reason: str = '',
    ) -> Tuple[str, str, Dict]:
        placeholder_map: Dict = {}
        
        # Create a map for quick lookup of items by id
        all_items_map = {item['id']: item for item in all_source_items}
        all_item_ids = [item['id'] for item in all_source_items]

        items_with_context = []
        glossary_manager = self.main_handler._glossary_manager

        for item in source_items:
            item_id = item['id']
            current_text = item.get('text', '')
            
            try:
                current_idx = all_item_ids.index(item_id)
                prev_idx = current_idx - 1
                next_idx = current_idx + 1

                context_before = all_source_items[prev_idx]['text'] if prev_idx >= 0 else ''
                context_after = all_source_items[next_idx]['text'] if next_idx < len(all_source_items) else ''
            except ValueError:
                context_before, context_after = '', ''

            # Find relevant glossary terms
            relevant_glossary_entries = []
            if glossary_manager:
                combined_text = '\n'.join([context_before, current_text, context_after])
                relevant_glossary_entries = glossary_manager.get_relevant_terms(combined_text)

            item_for_ai = {
                'id': item_id,
                'text': current_text,
                'context_before': context_before,
                'context_after': context_after,
                'relevant_glossary': self._glossary_entries_to_text(relevant_glossary_entries)
            }
            
            # Fetch story context from MemPalace if available
            story_context = self._fetch_story_context(block_idx, item_id, current_text)
            if story_context:
                item_for_ai['story_context'] = story_context
                
            items_with_context.append(item_for_ai)

        json_payload_for_ai = {'strings_to_translate': items_with_context}

        if not is_retry:
            instructions = [
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Use "context_before", "context_after", "story_context" (if present), and "relevant_glossary" to maintain consistency.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object in the returned array must have the original "id" (integer) and a "translation" (string) field.',
                'The number of objects in the "translated_strings" array must exactly match the number of objects provided in the input array.',
                'Follow the rules from the system prompt regarding tags and glossary.',
                'Do not add any explanations or text outside the JSON object.',
            ]
        else:
            instructions = [
                'Your previous response was invalid. Please correct it.',
                f'Error: {retry_reason}',
                'Follow these instructions carefully:',
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Use "context_before", "context_after", "story_context" (if present), and "relevant_glossary" to maintain consistency.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object must have the original "id" and a "translation" field.',
                'The number of objects must match the input.',
                'Follow the rules from the system prompt regarding tags and glossary.',
                'Do not add any explanations or text outside the JSON object.',
            ]

        # Add a note about text unity to the system prompt
        system_prompt_addition = (
            "IMPORTANT: All text chunks you receive in a single request are part of a larger, "
            "cohesive block of text. Ensure your translations are consistent in style, tone, "
            "and terminology across all chunks."
        )
        
        final_system_prompt = f"{system_prompt}\n\n{system_prompt_addition}"
        combined_system = self._prepare_glossary_for_prompt(final_system_prompt, session_state, is_batch_translation=True)

        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else 'Unknown game'
        context_lines = [
            f'Game: {game_name}',
            f'Mode: {mode_description}',
        ]
        if block_idx is not None:
            block_label = self.mw.data_store.block_names.get(str(block_idx), f'Block {block_idx}')
            context_lines.append(f'Block: {block_label} (#{block_idx})')

        user_sections = [
            '\n'.join(context_lines),
            'INSTRUCTIONS:\n' + '\n'.join(f'- {instr}' for instr in instructions),
            'JSON DATA TO PROCESS:\n' + json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False),
        ]
        user_content = '\n\n'.join(user_sections)

        log_debug(
            f'Composed batch request for AI. System prompt size: {len(combined_system)}, '
            f'User content size: {len(user_content)}'
        )
        return combined_system, user_content, placeholder_map

    def compose_variation_request(
        self,
        system_prompt: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        current_translation: str,
        request_type: str,
        session_state: Optional[TranslationSessionState] = None,
        mode_description: str = 'translation variations',
    ) -> Tuple[str, str]:
        combined_system, user_content = self.compose_messages(
            system_prompt,
            source_text,
            block_idx=block_idx,
            string_idx=string_idx,
            expected_lines=expected_lines,
            mode_description=mode_description,
            request_type=request_type,
            current_translation=current_translation,
            session_state=session_state,
        )
        return combined_system, user_content

    def compose_messages(
        self,
        system_prompt: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        mode_description: str,
        session_state: Optional[TranslationSessionState] = None,
        request_type: str = 'translation',
        current_translation: Optional[str] = None,
    ) -> Tuple[str, str]:
        combined_system = self._prepare_glossary_for_prompt(system_prompt, session_state)

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else 'Unknown game'
        context_lines.append(f'Game: {game_name}')
        if block_idx is not None and block_idx != -1:
            block_label = self._get_block_label(block_idx)
            context_lines.append(f'Block: {block_label} (#{block_idx})')
        if string_idx is not None and string_idx != -1:
            context_lines.append(f'Row: #{string_idx}')
        if mode_description:
            context_lines.append(f'Mode: {mode_description}')

        # Fetch story context from MemePalace if available
        if block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            story_context = self._fetch_story_context(block_idx, string_idx, source_text)
            if story_context:
                context_lines.append(f"Story Context:\n{story_context}")

        if request_type == 'variation_list':
            instructions = [
                'Generate 10 different Ukrainian translation alternatives for the provided text.',
                f'Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.',
                'Follow the glossary and preserve all tags exactly as they appear.',
                'Follow the tone of the original text.',
                'Return the response as a JSON array with 10 strings and no additional commentary.',
            ]
        elif request_type == 'glossary_notes_variation':
            instructions = [
                'Generate 5 alternative Ukrainian glossary descriptions for the provided term.',
                'Each description should be 1-2 sentences and stay under 60 words.',
                'Preserve any tags/placeholders exactly as provided.',
                'Keep the description informative and suitable for a glossary entry.',
                'Return the response as a JSON array with 5 strings and no additional commentary.',
            ]
        else:
            instructions = [
                'Translate the text into Ukrainian without altering the meaning.',
                f'Keep exactly {expected_lines} lines (including empty ones) and preserve their order.',
                'Use the provided glossary to translate terms. All other tags must be preserved exactly as they appear.',
                'The glossary has absolute priority.',
                'Do not add explanations or meta text; return only the translation.',
            ]

        user_sections: List[str] = ['\n'.join(context_lines), '\n'.join(instructions)]
        if request_type == 'variation_list' and current_translation:
            user_sections.append('Current translation:')
            user_sections.append(str(current_translation))
        elif request_type == 'glossary_notes_variation' and current_translation is not None:
            user_sections.append('Current description:')
            user_sections.append(str(current_translation or '(empty)'))

        user_sections.append('Input text:')
        user_sections.append(source_text)

        user_content = '\n\n'.join([section for section in user_sections if section])
        log_debug(
            f'Composed request for AI. Type={request_type}, System prompt size={len(combined_system)}, '
            f'User content size={len(user_content)}'
        )
        return combined_system, user_content

    def compose_glossary_occurrence_update_request(
        self,
        system_prompt: str,
        *,
        source_text: str,
        current_translation: str,
        original_text: str,
        term: str,
        old_translation: str,
        new_translation: str,
        expected_lines: int,
        session_state: Optional[TranslationSessionState] = None,
    ) -> Tuple[str, str]:
        combined_system = self._prepare_glossary_for_prompt(system_prompt, session_state)

        instructions = [
            "Update the existing Ukrainian translation to reflect the new glossary term translation.",
            "Preserve all tags, placeholders, punctuation, whitespace, and line breaks exactly as in the input.",
            f"Keep the total number of lines at {expected_lines}; do not add or remove lines.",
            "Use the new glossary translation naturally (adjust case/grammar if required by context).",
            "Return JSON only: {\"translation\": \"...\"} with the updated Ukrainian text.",
        ]

        user_sections = [
            "Context:",
            f"Term: {term}",
            f"Old translation: {old_translation or '[empty]'}",
            f"New translation: {new_translation or '[empty]'}",
            "",
            "Original text (reference only, do not translate it):",
            original_text or '[none]',
            "",
            "Current translation (update this, keep formatting):",
            source_text or '',
            "",
            "Instructions:",
            "\n".join(f"- {item}" for item in instructions),
        ]
        user_content = "\n".join(user_sections)
        return combined_system, user_content

    def compose_glossary_occurrence_batch_request(
        self,
        system_prompt: str,
        *,
        term: str,
        old_translation: str,
        new_translation: str,
        batch_items: List[Dict],
        session_state: Optional[TranslationSessionState] = None,
    ) -> Tuple[str, str]:
        combined_system = self._prepare_glossary_for_prompt(system_prompt, session_state)

        instructions = [
            "For each object in the JSON payload, update the Ukrainian translation to use the new glossary translation.",
            "Preserve all tags/placeholders, punctuation, whitespace, and line breaks exactly as provided.",
            "Keep the line count for each translation identical to the original.",
            "Return JSON only: {\"occurrences\": [{\"id\": string, \"translation\": string}, ...]}.",
        ]

        payload = {
            "term": term,
            "old_translation": old_translation or "[empty]",
            "new_translation": new_translation or "[empty]",
            "occurrences": batch_items,
        }

        user_sections = [
            "Instructions:\n" + "\n".join(f"- {item}" for item in instructions),
            "JSON DATA TO UPDATE:\n" + json.dumps(payload, indent=2, ensure_ascii=False),
        ]
        user_content = "\n\n".join(user_sections)
        log_debug(
            "Composed glossary batch update: "
            f"System prompt size={len(combined_system)}, User content size={len(user_content)}"
        )
        return combined_system, user_content

    def compose_glossary_request(self, system_prompt: str, user_content: str, **_: Dict) -> Tuple[str, str]:
        return system_prompt.strip(), user_content

    @staticmethod
    def _glossary_entries_to_text(entries: Sequence[GlossaryEntry]) -> str:
        """Format glossary entries into a markdown table."""
        if not entries:
            return ""
        lines = ["| Original | Translation | Notes |", "|---|---|---|"]
        for entry in entries:
            lines.append(f"| {entry.original} | {entry.translation} | {entry.notes} |")
        return "\n".join(lines)


    def _prepare_glossary_for_prompt(
        self,
        system_prompt: str,
        session_state: Optional[TranslationSessionState],
        is_batch_translation: bool = False,
    ) -> str:
        """Prepare the system prompt with the full glossary or just updates."""
        system_prompt = (system_prompt or "").strip()
        glossary_manager = self.main_handler._glossary_manager
        if not glossary_manager:
            return system_prompt

        # For batch translation, we assume relevant glossary is in the user prompt.
        if is_batch_translation:
            return system_prompt

        # Case 1: No session or glossary already sent, but there are updates.
        if session_state and session_state.glossary_sent:
            changes = glossary_manager.get_session_changes()
            if not changes:
                return system_prompt  # No updates to send

            added_updated = [v for v in changes.values() if v is not None]
            deleted_keys = [k for k, v in changes.items() if v is None]

            update_sections = []
            if added_updated:
                update_sections.append(
                    "GLOSSARY UPDATES (add or modify these terms):\n"
                    + self._glossary_entries_to_text(added_updated)
                )
            if deleted_keys:
                deleted_list = ", ".join(f'"{key}"' for key in deleted_keys)
                update_sections.append(f"GLOSSARY DELETIONS (remove these terms):\n{deleted_list}")

            # Append updates and clear them from the manager
            if update_sections:
                system_prompt += "\n\n" + "\n\n".join(update_sections)
            glossary_manager.clear_session_changes()
            return system_prompt

        # Case 2: First time sending in a session, or no session. Send full glossary.
        full_glossary_text = self._glossary_entries_to_text(glossary_manager.get_entries())
        if not full_glossary_text:
            return system_prompt  # Nothing to send

        if session_state:
            session_state.glossary_sent = True
        glossary_manager.clear_session_changes()  # Clear any pending changes

        return (
            f"{system_prompt}\n\n"
            f"GLOSSARY (use with absolute priority):\n{full_glossary_text}"
        )

    def _get_mempalace_client(self) -> Optional[MemePalaceClient]:
        """Dynamically get or initialize MemePalaceClient for current project directory."""
        import os
        project_dir = None
        if hasattr(self.mw, "project_manager") and self.mw.project_manager:
            proj_dir = getattr(self.mw.project_manager, "project_dir", None)
            if proj_dir and isinstance(proj_dir, (str, bytes)):
                project_dir = proj_dir
        
        if not project_dir:
            if hasattr(self.mw, "data_store") and self.mw.data_store:
                project_file = getattr(self.mw.data_store, "project_file", None)
                json_path = getattr(self.mw.data_store, "json_path", None)
                if project_file and isinstance(project_file, (str, bytes)):
                    project_dir = os.path.dirname(project_file)
                elif json_path and isinstance(json_path, (str, bytes)):
                    project_dir = os.path.dirname(json_path)
            if not project_dir or not isinstance(project_dir, (str, bytes)):
                project_dir = os.getcwd()
        
        # Verify if the db exists or search in parent/adjacent directories up to 4 levels
        db_file = "mempalace_local.db"
        resolved_db = os.path.join(project_dir, db_file) if project_dir else ""
        
        if not project_dir or not os.path.exists(resolved_db):
            candidates = [os.getcwd()]
            if hasattr(self.mw, "data_store") and self.mw.data_store:
                json_path = getattr(self.mw.data_store, "json_path", None)
                if json_path and isinstance(json_path, (str, bytes)):
                    candidates.append(os.path.dirname(json_path))
                
            found_dir = None
            for cand in candidates:
                if not cand: continue
                curr = os.path.abspath(cand)
                # Check up to 4 levels of parent directories
                for _ in range(5):
                    # Check current directory
                    test_path = os.path.join(curr, db_file)
                    if os.path.exists(test_path):
                        found_dir = curr
                        break
                    # Also check immediately adjacent sibling folders
                    parent_dir = os.path.dirname(curr)
                    if parent_dir and parent_dir != curr:
                        for sibling in os.listdir(parent_dir):
                            sibling_path = os.path.join(parent_dir, sibling)
                            if os.path.isdir(sibling_path):
                                test_path_sib = os.path.join(sibling_path, db_file)
                                if os.path.exists(test_path_sib):
                                    found_dir = sibling_path
                                    break
                    if found_dir:
                        break
                    
                    # Move one level up
                    next_parent = os.path.dirname(curr)
                    if next_parent == curr:
                        break
                    curr = next_parent
                if found_dir:
                    project_dir = found_dir
                    break
            
        if not project_dir or not isinstance(project_dir, (str, bytes)):
            return None
            
        if not hasattr(self, "_mempalace_client") or self._mempalace_client is None or getattr(self, "_mempalace_project_dir", None) != project_dir:
            from core.mempalace_client import MemePalaceClient
            self._mempalace_client = MemePalaceClient(project_dir=project_dir)
            self._mempalace_project_dir = project_dir
            
        return self._mempalace_client

    def _get_wing_name(self) -> str:
        """Deduce clean active wing/game identifier."""
        game_name = "Zelda_TP"
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
        elif hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            game_name = self.mw.current_game_rules.get_display_name()
        
        clean_name = "".join([c if c.isalnum() else "_" for c in game_name]).strip("_")
        
        # Sibling fallback: If there is a local SQLite database, check if clean_name exists there.
        # If not, and there is exactly one other wing in the database, use that one as fallback!
        try:
            client = self._get_mempalace_client()
            if client and hasattr(client, "get_wings"):
                wings = client.get_wings()
                wing_names = [w["name"] for w in wings]
                if wing_names and clean_name not in wing_names:
                    # Look for fuzzy match or prefix match
                    for w_name in wing_names:
                        if clean_name.lower().startswith(w_name.lower()) or w_name.lower().startswith(clean_name.lower()):
                            return w_name
                    # If only one wing exists in DB, use it
                    if len(wing_names) == 1:
                        return wing_names[0]
        except Exception as e:
            import utils.logging_utils
            utils.logging_utils.log_error(f"Error resolving wing name fallback: {e}")
            
        return clean_name or "Zelda_TP"

    def _get_block_label(self, block_idx: int) -> str:
        """Get friendly display label for a project file block index."""
        if block_idx is None or block_idx == -1:
            return "Block"
            
        import os
        store = self.mw.data_store
        name_key = str(block_idx)
        
        # 1. Try project block name or source file stem
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
           self.mw.project_manager.project and block_idx < len(self.mw.project_manager.project.blocks):
            block = self.mw.project_manager.project.blocks[block_idx]
            if block.name and not block.name.startswith("Block_"):
                return block.name
            if block.source_file:
                return os.path.splitext(os.path.basename(block.source_file))[0]

        # 2. Try list widget item name or block_names description
        if store.block_names and name_key in store.block_names:
            b_desc = store.block_names[name_key]
            base = os.path.splitext(os.path.basename(b_desc))[0]
            if "(" in base:
                base = base.partition("(")[0].strip()
            return base

        # 3. Fallback: if json_path is loaded in datastore, use its stem
        if getattr(store, "json_path", None):
            return os.path.splitext(os.path.basename(store.json_path))[0]
            
        return f"Block_{block_idx}"

    def _fetch_story_context(self, block_idx: int, s_idx: int, text: str) -> Optional[str]:
        """Query the local SQLite database for visual scene description, character status and timeline info."""
        client = self._get_mempalace_client()
        if not client:
            return None
            
        wing_name = self._get_wing_name()
        block_label = self._get_block_label(block_idx)
        bmg_id = f"{block_label}_Str_{s_idx}"
        
        # 1. Try local in-memory cache first for instant response
        cached_ctx = client.get_cached_context(bmg_id, text)
        if cached_ctx:
            room_name = cached_ctx.get("room")
            speaker = cached_ctx.get("speaker")
            timestamp = cached_ctx.get("timestamp") or "Unknown time"
            visual_ctx = client.get_room_visual_context(wing_name, room_name)
            
            context_parts = []
            clean_room = room_name.replace("_", " ")
            context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")
            
            if speaker:
                context_parts.append(f"Speaker in this line: {speaker}")
                
            if visual_ctx:
                context_parts.append(f"Visual Action Context:\n{visual_ctx}")
            else:
                context_parts.append("Timeline context mapped successfully (No detailed visual context generated).")
                
            # Retrieve relations
            try:
                relations = client.get_relations(wing_name)
                relevant_relations = []
                if speaker:
                    speaker_low = speaker.lower()
                    for r in relations:
                        if r.get("source", "").lower() == speaker_low or r.get("target", "").lower() == speaker_low:
                            relevant_relations.append(r)
                            
                if not relevant_relations and relations:
                    room_low = room_name.lower()
                    for r in relations:
                        valid_from = r.get("valid_from", "")
                        if valid_from and valid_from.lower() in room_low:
                            relevant_relations.append(r)
                            
                if relevant_relations:
                    context_parts.append("\nCharacter Status & Story Relations:")
                    for r in relevant_relations[:5]:
                        context_parts.append(f"• {r.get('source')} -[{r.get('relation')}]-> {r.get('target')}")
            except Exception as rel_err:
                log_debug(f"Could not load relations for visual context: {rel_err}")
                
            return "\n".join(context_parts)

        # 2. Search database fallback
        results = client.search_context(wing_name, bmg_id, limit=1)
        
        if not results:
            # Fallback: search by actual text (first 40 characters)
            query_text = text.strip()[:40]
            if len(query_text) > 8:
                results = client.search_context(wing_name, query_text, limit=1)
                
        if results:
            best_match = results[0]
            room_name = best_match.get("room")
            if room_name:
                # Retrieve visual scene context if generated by AI
                visual_ctx = client.get_room_visual_context(wing_name, room_name)
                
                # Check metadata for timestamp & speakers
                meta = best_match.get("metadata") or {}
                timestamp = meta.get("timestamp") or "Unknown time"
                speaker_map = meta.get("speaker_map") or {}
                
                # Deduce speaker for this row if available
                speaker = speaker_map.get(bmg_id) or speaker_map.get(f"[{bmg_id}]")
                
                context_parts = []
                # Clean room name for display
                clean_room = room_name.replace("_", " ")
                context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")
                
                if speaker:
                    context_parts.append(f"Speaker in this line: {speaker}")
                    
                if visual_ctx:
                    context_parts.append(f"Visual Action Context:\n{visual_ctx}")
                else:
                    context_parts.append("Timeline context mapped successfully (No detailed visual context generated).")
                
                # 3. Retrieve character relations from temporal Knowledge Graph
                try:
                    relations = client.get_relations(wing_name)
                    relevant_relations = []
                    if speaker:
                        speaker_low = speaker.lower()
                        for r in relations:
                            if r.get("source", "").lower() == speaker_low or r.get("target", "").lower() == speaker_low:
                                relevant_relations.append(r)
                                
                    if not relevant_relations and relations:
                        room_low = room_name.lower()
                        for r in relations:
                            valid_from = r.get("valid_from", "")
                            if valid_from and valid_from.lower() in room_low:
                                relevant_relations.append(r)
                                
                    if relevant_relations:
                        rel_lines = ["\nCHARACTER & STORY RELATIONS (Ukrainian Grammar Priority):"]
                        rel_lines.append("Use these social relations to determine the correct informal ('ти') or formal/respectful ('ви') pronoun and verb endings in Ukrainian:")
                        for r in relevant_relations:
                            rel_lines.append(f"• {r['source']} -[{r['relation']}]-> {r['target']}")
                        context_parts.append("\n".join(rel_lines))
                except Exception as rel_err:
                    import utils.logging_utils
                    utils.logging_utils.log_error(f"Error gathering relations for prompt: {rel_err}")
                     
                return "\n".join(context_parts)
                
        return None
