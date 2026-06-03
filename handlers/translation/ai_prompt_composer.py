from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from core.translation.session_manager import TranslationSessionState
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug


class AIPromptComposer(BaseTranslationHandler):
    """Compose prompts for AI translation/variation tasks and manage placeholders."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._script_lines_cache = None
        self._global_distilled_text_cache = None
        self._char_to_line_map_cache = None
        self._cached_script_path = None

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
        if not translated_text:
            return ''
            
        # 1. Restore Force-aliases if they exist
        if placeholder_map and key in placeholder_map:
            from utils.force_alias import restore_force_aliases_in_translation
            force_maps = placeholder_map[key]
            glossary_translations = {}
            glossary_manager = self.main_handler._glossary_manager
            if glossary_manager:
                for mapping in force_maps:
                    word = mapping.word
                    entry = glossary_manager.get_entry(word)
                    if entry and entry.translation:
                        glossary_translations[word.lower()] = entry.translation
            translated_text = restore_force_aliases_in_translation(translated_text, force_maps, glossary_translations)

        # 2. Restore normal tag aliases from default_tag_mappings
        tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
        if tag_mappings:
            sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[0]), reverse=True)
            for alias, original_tag in sorted_mappings:
                if alias and original_tag:
                    pattern = re.compile(re.escape(alias), re.IGNORECASE)
                    translated_text = pattern.sub(original_tag, translated_text)

        return translated_text

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
        temp_id_map: Optional[Dict] = None,
    ) -> Tuple[str, str, Dict]:
        placeholder_map: Dict = {}
        glossary_manager = self.main_handler._glossary_manager
        client = self._get_mempalace_client()
        wing_name = self._get_wing_name()
        block_label = self._get_block_label(block_idx)

        # 1. Resolve speakers and clean newlines for all items in chunk
        items_with_context = []
        for item in source_items:
            if isinstance(item, dict):
                item_id = item.get('id', 0)
                current_text = item.get('text', '')
            else:
                item_id = 0
                current_text = str(item)
            
            # Apply force-aliases
            from utils.force_alias import prepare_text_for_ai
            tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
            current_text_for_ai, force_maps = prepare_text_for_ai(current_text, tag_mappings)
            if force_maps:
                placeholder_map[item_id] = force_maps
            
            # Remove line breaks inside sentences for AI translation
            current_text_clean = current_text_for_ai.replace('\n', ' ')
            current_text_clean = re.sub(r' +', ' ', current_text_clean).strip()

            # Resolve speaker
            speaker = None
            real_b_idx = block_idx
            real_s_idx = item_id
            if temp_id_map and item_id in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[item_id]
            elif temp_id_map and str(item_id) in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[str(item_id)]
            real_block_label = self._get_block_label(real_b_idx)

            if client:
                bmg_id = f"{real_block_label}_Str_{real_s_idx}"
                cached_ctx = client.get_cached_context(bmg_id, current_text)
                if cached_ctx:
                    speaker = cached_ctx.get("speaker")
                    
            if not speaker:
                script_res = self._find_speaker_in_script(real_b_idx, real_s_idx, current_text)
                if script_res and isinstance(script_res, (tuple, list)) and len(script_res) == 2:
                    raw_spk = script_res[0]
                    speaker = self._translate_speaker(raw_spk) if raw_spk else None
            
            if not speaker:
                speaker = "Unknown"

            item_for_ai = {
                'id': item_id,
                'text': current_text_clean,
                'speaker': speaker
            }
            if isinstance(item, dict) and item.get('scene_context'):
                item_for_ai['scene_context'] = item['scene_context']
            items_with_context.append(item_for_ai)

        # 2. Extract scene context for the entire chunk if available
        room_name = None
        for item in source_items:
            if isinstance(item, dict):
                item_id = item.get('id', 0)
                item_text = item.get('text', '')
            else:
                item_id = 0
                item_text = str(item)
            
            real_b_idx = block_idx
            real_s_idx = item_id
            if temp_id_map and item_id in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[item_id]
            elif temp_id_map and str(item_id) in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[str(item_id)]
            real_block_label = self._get_block_label(real_b_idx)
            
            bmg_id = f"{real_block_label}_Str_{real_s_idx}"
            cached_ctx = client.get_cached_context(bmg_id, item_text) if client else None
            if cached_ctx and cached_ctx.get("room"):
                room_name = cached_ctx.get("room")
                break

        scene_context = ""
        # Try to get scene context directly from items first
        for item in source_items:
            if isinstance(item, dict) and item.get('scene_context'):
                scene_context = item['scene_context']
                break

        if not scene_context and room_name and client:
            visual_ctx = client.get_room_visual_context(wing_name, room_name)
            relations = []
            try:
                relations = client.get_relations(wing_name)
            except Exception:
                pass
                
            context_parts = []
            clean_room = room_name.replace("_", " ")
            context_parts.append(f"Story Location/Scene: {clean_room}")
            
            if visual_ctx:
                context_parts.append(f"Visual Action Context:\n{visual_ctx}")
                
            relevant_relations = []
            if relations:
                chunk_speakers = set()
                for item in items_with_context:
                    spk = item.get('speaker')
                    if spk and spk != "Unknown":
                        chunk_speakers.add(spk.lower())
                
                for r in relations:
                    if r.get("source", "").lower() in chunk_speakers or r.get("target", "").lower() in chunk_speakers:
                        relevant_relations.append(r)
                        
            if relevant_relations:
                rel_lines = ["\nCharacter Relations & Status (Use for formal/informal tone):"]
                for r in relevant_relations[:5]:
                    rel_lines.append(f"• {r.get('source')} -[{r.get('relation')}]-> {r.get('target')}")
                context_parts.append("\n".join(rel_lines))
                
            # Collect surrounding dialogue context for the batch chunk (Surrounding Translated Context)
            surrounding_context_lines = []
            if block_idx is not None and block_idx != -1 and source_items:
                try:
                    ds = getattr(self.mw, 'data_store', None)
                    if ds and hasattr(ds, 'data') and ds.data:
                        item_ids = []
                        for item in source_items:
                            if isinstance(item, dict):
                                item_ids.append(item.get('id', 0))
                            else:
                                item_ids.append(0)
                        if item_ids:
                            if block_idx == -2 and temp_id_map:
                                first_temp_id = item_ids[0]
                                last_temp_id = item_ids[-1]
                                real_block_idx, first_s_idx = None, None
                                if first_temp_id in temp_id_map:
                                    real_block_idx, first_s_idx = temp_id_map[first_temp_id]
                                elif str(first_temp_id) in temp_id_map:
                                    real_block_idx, first_s_idx = temp_id_map[str(first_temp_id)]
                                
                                _, last_s_idx = None, None
                                if last_temp_id in temp_id_map:
                                    _, last_s_idx = temp_id_map[last_temp_id]
                                elif str(last_temp_id) in temp_id_map:
                                    _, last_s_idx = temp_id_map[str(last_temp_id)]
                            else:
                                real_block_idx = block_idx
                                first_s_idx = min(item_ids)
                                last_s_idx = max(item_ids)

                            if real_block_idx is not None and 0 <= real_block_idx < len(ds.data):
                                block_data = ds.data[real_block_idx]
                                if isinstance(block_data, list):
                                    N = len(block_data)
                                    K = 3
                                    before_indices = list(range(max(0, first_s_idx - K), first_s_idx))
                                    after_indices = list(range(last_s_idx + 1, min(N, last_s_idx + K + 1)))
                                    
                                    if before_indices:
                                        surrounding_context_lines.append("--- Dialogue BEFORE this chunk ---")
                                        for i in before_indices:
                                            orig_text = str(block_data[i]).replace('\n', ' ')
                                            curr_trans, _ = self.data_processor.get_current_string_text(real_block_idx, i)
                                            curr_trans_clean = curr_trans.replace('\n', ' ') if curr_trans else ""
                                            if curr_trans_clean and curr_trans_clean != orig_text:
                                                surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\" | (Translation): \"{curr_trans_clean}\"")
                                            else:
                                                surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\"")
                                                
                                    if after_indices:
                                        surrounding_context_lines.append("--- Dialogue AFTER this chunk ---")
                                        for i in after_indices:
                                            orig_text = str(block_data[i]).replace('\n', ' ')
                                            curr_trans, _ = self.data_processor.get_current_string_text(real_block_idx, i)
                                            curr_trans_clean = curr_trans.replace('\n', ' ') if curr_trans else ""
                                            if curr_trans_clean and curr_trans_clean != orig_text:
                                                surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\" | (Translation): \"{curr_trans_clean}\"")
                                            else:
                                                surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\"")
                except Exception as e:
                    log_debug(f"AIPromptComposer: Error fetching batch surrounding context: {e}")

            if surrounding_context_lines:
                context_parts.append("\n" + "\n".join(surrounding_context_lines))
            scene_context = "\n".join(context_parts)

        # Fallback surrounding context if no MemePalace scene context is built but dialogue boundaries exist
        if not scene_context and block_idx is not None and block_idx != -1 and source_items:
            try:
                ds = getattr(self.mw, 'data_store', None)
                if ds and hasattr(ds, 'data') and ds.data:
                    item_ids = [item.get('id', 0) if isinstance(item, dict) else 0 for item in source_items]
                    if item_ids:
                        if block_idx == -2 and temp_id_map:
                            first_temp_id = item_ids[0]
                            last_temp_id = item_ids[-1]
                            real_block_idx, first_s_idx = None, None
                            if first_temp_id in temp_id_map:
                                real_block_idx, first_s_idx = temp_id_map[first_temp_id]
                            elif str(first_temp_id) in temp_id_map:
                                real_block_idx, first_s_idx = temp_id_map[str(first_temp_id)]
                            
                            _, last_s_idx = None, None
                            if last_temp_id in temp_id_map:
                                _, last_s_idx = temp_id_map[last_temp_id]
                            elif str(last_temp_id) in temp_id_map:
                                _, last_s_idx = temp_id_map[str(last_temp_id)]
                        else:
                            real_block_idx = block_idx
                            first_s_idx = min(item_ids)
                            last_s_idx = max(item_ids)

                        if real_block_idx is not None and 0 <= real_block_idx < len(ds.data):
                            block_data = ds.data[real_block_idx]
                            if isinstance(block_data, list):
                                N = len(block_data)
                                K = 3
                                before_indices = list(range(max(0, first_s_idx - K), first_s_idx))
                                after_indices = list(range(last_s_idx + 1, min(N, last_s_idx + K + 1)))
                                surrounding_context_lines = []
                                
                                if before_indices:
                                    surrounding_context_lines.append("--- Dialogue BEFORE this chunk ---")
                                    for i in before_indices:
                                        orig_text = str(block_data[i]).replace('\n', ' ')
                                        curr_trans, _ = self.data_processor.get_current_string_text(real_block_idx, i)
                                        curr_trans_clean = curr_trans.replace('\n', ' ') if curr_trans else ""
                                        if curr_trans_clean and curr_trans_clean != orig_text:
                                            surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\" | (Translation): \"{curr_trans_clean}\"")
                                        else:
                                            surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\"")
                                            
                                if after_indices:
                                    surrounding_context_lines.append("--- Dialogue AFTER this chunk ---")
                                    for i in after_indices:
                                        orig_text = str(block_data[i]).replace('\n', ' ')
                                        curr_trans, _ = self.data_processor.get_current_string_text(real_block_idx, i)
                                        curr_trans_clean = curr_trans.replace('\n', ' ') if curr_trans else ""
                                        if curr_trans_clean and curr_trans_clean != orig_text:
                                            surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\" | (Translation): \"{curr_trans_clean}\"")
                                        else:
                                            surrounding_context_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\"")
                                if surrounding_context_lines:
                                    scene_context = "\n".join(surrounding_context_lines)
            except Exception as e:
                log_debug(f"AIPromptComposer: Error fetching batch surrounding context fallback: {e}")

        # 3. Find relevant glossary terms for the entire chunk and next chunks (Lookahead)
        combined_chunk_text = " ".join(
            (item.get('text', '') if isinstance(item, dict) else str(item))
            for item in source_items
        )

        lookahead_text = combined_chunk_text
        try:
            if source_items and all_source_items:
                first_item_id = source_items[0].get('id', 0)
                start_idx = 0
                for idx, item in enumerate(all_source_items):
                    if isinstance(item, dict) and item.get('id') == first_item_id:
                        start_idx = idx
                        break
                
                lookahead_items = all_source_items[start_idx:start_idx + 60]
                lookahead_text = " ".join(
                    (item.get('text', '') if isinstance(item, dict) else str(item))
                    for item in lookahead_items
                )
        except Exception as e:
            log_debug(f"AIPromptComposer: Error calculating lookahead glossary text: {e}")

        relevant_glossary_entries = []
        if glossary_manager:
            relevant_glossary_entries = glossary_manager.get_relevant_terms(lookahead_text)
        glossary_text = self._glossary_entries_to_text(relevant_glossary_entries)

        # 4. Build JSON payload
        json_payload_for_ai = {
            'strings_to_translate': items_with_context
        }
        if scene_context:
            json_payload_for_ai['scene_context'] = scene_context
        if glossary_text:
            json_payload_for_ai['glossary'] = glossary_text

        if not is_retry:
            instructions = [
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object in the returned array must have the original "id" (integer) and a "translation" (string) field.',
                'The number of objects in the "translated_strings" array must exactly match the number of objects provided in the input.',
                'Use "scene_context" (if present), "speaker", and "glossary" (if present) to maintain consistency and tone.',
                'Follow the rules from the system prompt regarding tags.',
                'Do not add any explanations or text outside the JSON object.',
            ]
        else:
            instructions = [
                'Your previous response was invalid. Please correct it.',
                f'Error: {retry_reason}',
                'Follow these instructions carefully:',
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object must have the original "id" and a "translation" field.',
                'The number of objects must match the input.',
                'Use "scene_context" (if present), "speaker", and "glossary" (if present) to maintain consistency and tone.',
                'Follow the rules from the system prompt regarding tags.',
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
        # Fetch relevant glossary terms for this single string or variation
        glossary_text = ""
        glossary_manager = self.main_handler._glossary_manager
        if glossary_manager and source_text:
            relevant_glossary_entries = glossary_manager.get_relevant_terms(source_text)
            if relevant_glossary_entries:
                glossary_text = self._glossary_entries_to_text(relevant_glossary_entries)

        combined_system = system_prompt

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

        # Fetch surrounding dialogue context (Surrounding Translated Context)
        if block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            try:
                ds = getattr(self.mw, 'data_store', None)
                if ds and hasattr(ds, 'data') and ds.data and 0 <= block_idx < len(ds.data):
                    block_data = ds.data[block_idx]
                    if isinstance(block_data, list):
                        N = len(block_data)
                        K = 3
                        start_i = max(0, string_idx - K)
                        end_i = min(N - 1, string_idx + K)
                        dialogue_lines = []
                        for i in range(start_i, end_i + 1):
                            if i == string_idx:
                                dialogue_lines.append(f"- [Row #{i}] (Target - Translate this now): \"{source_text.replace(chr(10), ' ')}\"")
                            else:
                                orig_text = str(block_data[i]).replace('\n', ' ')
                                curr_trans, _ = self.data_processor.get_current_string_text(block_idx, i)
                                curr_trans_clean = curr_trans.replace('\n', ' ') if curr_trans else ""
                                if curr_trans_clean and curr_trans_clean != orig_text:
                                    dialogue_lines.append(
                                        f"- [Row #{i}] (Original): \"{orig_text}\"\n"
                                        f"            (Current Translation): \"{curr_trans_clean}\""
                                    )
                                else:
                                    dialogue_lines.append(f"- [Row #{i}] (Original): \"{orig_text}\"")
                        if dialogue_lines:
                            context_lines.append("Surrounding Dialogue Context:\n" + "\n".join(dialogue_lines))
            except Exception as e:
                log_debug(f"AIPromptComposer: Error fetching surrounding dialogue context: {e}")

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
        if glossary_text:
            user_sections.append(f"GLOSSARY (use with absolute priority):\n{glossary_text}")

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
        """Prepare the system prompt. Now returns the system prompt as-is for glossary unification."""
        return (system_prompt or "").strip()

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
        
        script_res = self._find_speaker_in_script(block_idx, s_idx, text)
        if not isinstance(script_res, (tuple, list)) or len(script_res) != 2:
            script_res = None
            
        script_lines_str = script_res[1] if script_res else None

        # Helper to try and resolve speaker via script fallback if missing
        def get_script_speaker_fallback() -> Optional[Tuple[str, str, str]]:
            if script_res:
                raw_spk, lines_str = script_res
                return raw_spk, self._translate_speaker(raw_spk), lines_str
            return None

        # 1. Try local in-memory cache first for instant response
        if client:
            wing_name = self._get_wing_name()
            block_label = self._get_block_label(block_idx)
            bmg_id = f"{block_label}_Str_{s_idx}"
            
            cached_ctx = client.get_cached_context(bmg_id, text)
            if cached_ctx:
                room_name = cached_ctx.get("room")
                speaker = cached_ctx.get("speaker")
                timestamp = cached_ctx.get("timestamp") or "Unknown time"
                visual_ctx = client.get_room_visual_context(wing_name, room_name)
                
                context_parts = []
                clean_room = room_name.replace("_", " ")
                context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")
                
                # If speaker missing in cache, try script fallback
                if not speaker:
                    fallback = get_script_speaker_fallback()
                    if fallback:
                        raw_spk, trans_spk, _ = fallback
                        if re.match(r'^[\d,\s]+$', raw_spk):
                            speaker = f"{raw_spk} [Disk Script]"
                        else:
                            speaker = f"{trans_spk} ({raw_spk}) [Disk Script]"
                
                if speaker:
                    context_parts.append(f"Speaker in this line: {speaker}")
                if script_lines_str:
                    context_parts.append(f"Script Line: {script_lines_str}")
                    
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
                            if r.get("source", "").lower() in speaker_low or r.get("target", "").lower() in speaker_low:
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
                    speaker = None
                    content = best_match.get("content") or ""
                    matched_id_in_content = None
                    
                    if content:
                        # Helper function for tagless text cleaning
                        def clean_for_compare(t: str) -> str:
                            if not t:
                                return ""
                            t = re.sub(r'\{[^}]+\}', '', t)
                            t = re.sub(r'\[[^]]+\]', '', t)
                            return re.sub(r'[^a-zA-Z0-9]', '', t).lower().strip()
                            
                        clean_query = clean_for_compare(text)
                        for line in content.splitlines():
                            line_id = None
                            line_text = None
                            if "ID:" in line and "| Text:" in line:
                                parts = line.split("| Text:", 1)
                                line_id = parts[0].replace("ID:", "").strip()
                                line_text = parts[1].strip()
                            elif ":" in line:
                                parts = line.split(":", 1)
                                line_id = parts[0].strip()
                                if line_id.startswith("[") and line_id.endswith("]"):
                                    line_id = line_id[1:-1].strip()
                                line_text = parts[1].strip()
                                
                            if line_id and line_text:
                                if clean_for_compare(line_text) == clean_query:
                                    matched_id_in_content = line_id
                                    break
                                    
                    target_bmg_id = matched_id_in_content or bmg_id
                    speaker = speaker_map.get(target_bmg_id) or speaker_map.get(f"[{target_bmg_id}]")
                    
                    # If speaker is missing in SQLite metadata, try disk script fallback
                    if not speaker:
                        fallback = get_script_speaker_fallback()
                        if fallback:
                            raw_spk, trans_spk, _ = fallback
                            if re.match(r'^[\d,\s]+$', raw_spk):
                                speaker = f"{raw_spk} [Disk Script]"
                            else:
                                speaker = f"{trans_spk} ({raw_spk}) [Disk Script]"
                    
                    context_parts = []
                    # Clean room name for display
                    clean_room = room_name.replace("_", " ")
                    context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")
                    
                    if speaker:
                        context_parts.append(f"Speaker in this line: {speaker}")
                    if script_lines_str:
                        context_parts.append(f"Script Line: {script_lines_str}")
                        
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
                                if r.get("source", "").lower() in speaker_low or r.get("target", "").lower() in speaker_low:
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

        # 3. Absolute Fallback: SQLite completely failed, try Script Fallback to at least extract Speaker
        fallback = get_script_speaker_fallback()
        if fallback:
            raw_spk, trans_spk, lines_str = fallback
            context_parts = [
                "Story Location/Scene: Mapped from Disk Script",
                f"Speaker in this line: {trans_spk} ({raw_spk}) [Disk Script]",
                f"Script Line: {lines_str}",
                "Timeline: Mapped from script sequence"
            ]
            return "\n".join(context_parts)
            
        return None

    def _find_script_path(self) -> Optional[str]:
        """Find the absolute path to the game script file on disk."""
        import os
        from pathlib import Path
        
        # 1. Ask active rules if they define a default script file name
        plugin_script_name = None
        if hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            try:
                plugin_script_name = self.mw.current_game_rules.get_default_script_name()
            except Exception:
                pass

        # 2. Gather directories to search in
        search_dirs = []
        
        # Candidate near DB path
        client = self._get_mempalace_client()
        db_path = client.db_path if client else None
        if db_path:
            db_dir = os.path.dirname(db_path)
            search_dirs.append(db_dir)
            search_dirs.append(os.path.dirname(db_dir))
            
        # Candidate near project directory
        project_dir = getattr(self, "_mempalace_project_dir", None)
        if not project_dir and hasattr(self.mw, "project_manager") and self.mw.project_manager and self.mw.project_manager.project:
            project_dir = self.mw.project_manager.project.project_dir
            
        if project_dir:
            search_dirs.append(project_dir)
            search_dirs.append(os.path.dirname(project_dir))

        # Check in current working directory
        search_dirs.append(os.getcwd())

        # Clean search directories (remove duplicates and verify existence)
        unique_dirs = []
        for d in search_dirs:
            if d and os.path.exists(d):
                abs_d = os.path.abspath(d)
                if abs_d not in unique_dirs:
                    unique_dirs.append(abs_d)

        # 3. Check for specific plugin script name
        if plugin_script_name:
            for d in unique_dirs:
                p = os.path.join(d, plugin_script_name)
                if os.path.exists(p):
                    return p

        # 4. Fallback search: look for hardcoded TP script
        candidates = [
            r"e:\Emulators\RomHacking\ZELDA\TP_UA\zelda_tp_script.txt",
        ]
        for d in unique_dirs:
            candidates.append(os.path.join(d, "zelda_tp_script.txt"))

        for path in candidates:
            if path and os.path.exists(path):
                return path

        # 5. Generic search for any *script*.md or *script*.txt in the search directories
        for d in unique_dirs:
            try:
                for f in os.listdir(d):
                    # prioritize markdown over plain text
                    if "script" in f.lower() and f.lower().endswith(".md"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            return p
                for f in os.listdir(d):
                    if "script" in f.lower() and f.lower().endswith(".txt"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            return p
            except Exception:
                pass
                
        return None

    def _translate_speaker(self, speaker: str) -> str:
        """Translate the character name using glossary if possible."""
        if not speaker:
            return ""
        glossary_manager = getattr(self.main_handler, '_glossary_manager', None)
        if not glossary_manager:
            return speaker
            
        for entry in glossary_manager.get_entries():
            if entry.original.strip().lower() == speaker.strip().lower():
                trans = entry.translation.split(";")[0].strip()
                if trans:
                    return trans
        return speaker

    def _find_speaker_in_script(self, block_idx: int, s_idx: int, text: str) -> Optional[str]:
        """Find speaker in the script file using direct DB mapping or middle third distilled matching."""
        import os
        import re
        
        script_path = self._find_script_path()
        if not script_path or not os.path.exists(script_path):
            log_debug("Script Fallback: script file not found.")
            return None

        # 1. High-priority Direct DB Script Mapping Check
        client = self._get_mempalace_client()
        db_mapping = None
        if client:
            wing_name = self._get_wing_name()
            block_label = self._get_block_label(block_idx)
            bmg_id = f"{block_label}_Str_{s_idx}"
            db_mapping = client.get_script_mapping(wing_name, bmg_id)

        # Retrieve dynamic name tag substitutions from the active plugin (e.g. {escape:0:0022} -> "Epona")
        _dynamic_name_tags: dict = {}
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            try:
                _dynamic_name_tags = self.mw.current_game_rules.get_dynamic_name_tags()
            except Exception:
                pass

        def line_strip_is_speaker(s: str) -> bool:
            return s.isupper() and len(s) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s) is not None

        # If direct mapping found, we can load the script and find the speaker directly from that line index
        if db_mapping and db_mapping.get("script_line"):
            line_num = db_mapping["script_line"]
            # Fast check: load only lines up to line_num if not cached, or load all
            try:
                if hasattr(self, "_script_lines_cache") and self._script_lines_cache:
                    lines = self._script_lines_cache
                else:
                    try:
                        with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                            lines = f.readlines()
                    except Exception:
                        with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()
                    self._script_lines_cache = lines
                
                # Scan backwards from line_num - 2 (0-indexed offset of line_num - 1)
                speaker = None
                for idx in range(line_num - 2, -1, -1):
                    s = lines[idx].strip()
                    if not s:
                        continue
                    if s.startswith("[") and s.endswith("]"):
                        continue
                    if line_strip_is_speaker(s):
                        speaker = s
                        break
                speaker_str = speaker if speaker else "NONE"
                return speaker_str, str(line_num)
            except Exception as e:
                log_debug(f"Direct mapping speaker extraction failed: {e}")

            
        # Retrieve dynamic name tag substitutions from the active plugin (e.g. {escape:0:0022} -> "Epona")
        _dynamic_name_tags: dict = {}
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            try:
                _dynamic_name_tags = self.mw.current_game_rules.get_dynamic_name_tags()
            except Exception:
                pass

        def distill(t: str) -> str:
            if not t:
                return ""
            # First replace known dynamic name tags (e.g. {escape:0:0022} -> "Epona")
            for tag, name in _dynamic_name_tags.items():
                t = t.replace(tag, name)
            t = re.sub(r'\{[^}]+\}', '', t)      # {escape:…} and other curly tags
            t = re.sub(r'\[[^]]+\]', '', t)       # [action notes]
            t = re.sub(r'\([^)]+\)', '', t)       # (button hints) e.g. (Up on D Pad)
            return "".join(c for c in t if c.isalnum()).lower()

        # Cache version – bump whenever distill() logic changes so stale caches are rebuilt
        _DISTILL_CACHE_VERSION = 2

        # Try to retrieve from In-Memory Script Cache to ensure instant response
        if (hasattr(self, "_script_lines_cache") and self._script_lines_cache and 
            hasattr(self, "_global_distilled_text_cache") and self._global_distilled_text_cache and 
            hasattr(self, "_char_to_line_map_cache") and self._char_to_line_map_cache and 
            getattr(self, "_cached_script_path", None) == script_path and
            getattr(self, "_distill_cache_version", None) == _DISTILL_CACHE_VERSION):
            lines = self._script_lines_cache
            global_distilled_text = self._global_distilled_text_cache
            char_to_line_map = self._char_to_line_map_cache
        else:
            try:
                with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                    lines = f.readlines()
            except Exception as e:
                log_debug(f"Script Fallback: failed to load with cp1252, trying utf-8: {e}")
                try:
                    with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception as e2:
                    log_debug(f"Script Fallback: failed to load script file: {e2}")
                    return None
            # Populate cache and global mapping
            self._script_lines_cache = lines
            
            global_distilled = []
            char_to_line_map = []
            def line_strip_is_speaker(s: str) -> bool:
                return s.isupper() and len(s) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s) is not None

            for idx, line in enumerate(lines):
                line_strip = line.strip()
                # Skip action bracket lines or uppercase speaker lines in mapping to avoid false positive speaker triggers
                if line_strip.startswith("[") and line_strip.endswith("]"):
                    continue
                if line_strip_is_speaker(line_strip):
                    continue
                    
                distilled_line = distill(line)
                if distilled_line:
                    for _ in range(len(distilled_line)):
                        char_to_line_map.append(idx + 1) # 1-based line number
                    global_distilled.append(distilled_line)
                    
            self._global_distilled_text_cache = "".join(global_distilled)
            self._char_to_line_map_cache = char_to_line_map
            self._cached_script_path = script_path
            self._distill_cache_version = _DISTILL_CACHE_VERSION
            global_distilled_text = self._global_distilled_text_cache
            log_debug(f"Successfully cached and mapped script file {script_path} ({len(lines)} lines, {len(global_distilled_text)} distilled characters).")

        # Count words in original text
        words_count = len(re.findall(r'\w+', text))
        
        # Distill current text
        distilled_query = distill(text)
        if not distilled_query:
            return "NONE", None
            
        start_offset = 0
        if words_count < 4:
            search_query = distilled_query
        else:
            n = len(distilled_query)
            if n < 3:
                search_query = distilled_query
            else:
                third = n // 3
                start = third
                end = n - third
                search_query = distilled_query[start:end]
                start_offset = start
                
        if not search_query:
            return "NONE", None

        def line_strip_is_speaker(s: str) -> bool:
            return s.isupper() and len(s) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s) is not None

        def is_line_boundary(line_str: str) -> bool:
            s = line_str.strip()
            if not s:
                return True
            if s.startswith("[") and s.endswith("]"):
                return True
            if line_strip_is_speaker(s):
                return True
            return False

        def get_script_remainder(e_pos: int) -> str:
            remainder_chars = []
            prev_line = char_to_line_map[e_pos - 1] if e_pos > 0 else 1
            for i in range(e_pos, len(global_distilled_text)):
                curr_line = char_to_line_map[i]
                if curr_line != prev_line:
                    break  # Stop at line boundary!
                remainder_chars.append(global_distilled_text[i])
            return "".join(remainder_chars)

        def get_prev_script_text(l_num: int) -> str:
            for idx in range(l_num - 2, -1, -1):
                line_str = lines[idx].strip()
                if not line_str or (line_str.startswith("[") and line_str.endswith("]")) or line_strip_is_speaker(line_str):
                    continue
                return line_str
            return ""

        def get_next_script_text(l_num: int) -> str:
            for idx in range(l_num, len(lines)):
                line_str = lines[idx].strip()
                if not line_str or (line_str.startswith("[") and line_str.endswith("]")) or line_strip_is_speaker(line_str):
                    continue
                return line_str
            return ""

        # Get preceding and subsequent BMG strings for context check
        preceding_strings = []
        subsequent_strings = []
        if (hasattr(self.mw, 'data_store') and self.mw.data_store and 
            block_idx is not None and 0 <= block_idx < len(self.mw.data_store.data)):
            block_strings = self.mw.data_store.data[block_idx]
            # Preceding BMG strings
            for prev_idx in range(max(0, s_idx - 5), s_idx):
                preceding_strings.append(block_strings[prev_idx])
            # Subsequent BMG strings
            for next_idx in range(s_idx + 1, len(block_strings)):
                subsequent_strings.append(block_strings[next_idx])

        dist_prev_bmg = ""
        if preceding_strings:
            for s in reversed(preceding_strings):
                d_s = distill(s)
                if d_s:
                    dist_prev_bmg = d_s
                    break

        dist_next_bmg = ""
        if subsequent_strings:
            for s in subsequent_strings:
                d_s = distill(s)
                if d_s:
                    dist_next_bmg = d_s
                    break
            
        # Search the query in the global distilled text
        candidates = []
        start_pos = 0
        while True:
            pos = global_distilled_text.find(search_query, start_pos)
            if pos == -1:
                break
            # Translate position back to original line number of the START of the query
            actual_pos = max(0, pos - start_offset)
            end_pos = actual_pos + len(distilled_query)
            
            # Check if validation is needed: only if the match does NOT end at a line boundary
            needs_validation = False
            if end_pos < len(char_to_line_map):
                if char_to_line_map[end_pos] == char_to_line_map[end_pos - 1]:
                    needs_validation = True
            
            if needs_validation:
                remainder = get_script_remainder(end_pos)
                if remainder:
                    temp_remainder = remainder
                    match_valid = True
                    for next_text in subsequent_strings:
                        dist_next = distill(next_text)
                        if not dist_next:
                            continue
                        if temp_remainder.startswith(dist_next):
                            temp_remainder = temp_remainder[len(dist_next):]
                            if not temp_remainder:
                                break
                        elif dist_next.startswith(temp_remainder):
                            temp_remainder = ""
                            break
                        else:
                            match_valid = False
                            break
                    
                    if not match_valid or (temp_remainder and len(temp_remainder) > 0):
                        start_pos = pos + 1
                        continue
            
            if actual_pos < len(char_to_line_map) and (end_pos - 1) < len(char_to_line_map):
                line_num = char_to_line_map[actual_pos]
                L_start = char_to_line_map[actual_pos]
                L_end = char_to_line_map[end_pos - 1]
                
                # 1. Word count diff
                script_matched_text = " ".join(lines[l - 1].strip() for l in range(L_start, L_end + 1))
                words_script = len(re.findall(r'\w+', script_matched_text))
                words_bmg = len(re.findall(r'\w+', text))
                word_diff = abs(words_script - words_bmg)
                
                # 2. Context Match
                has_prev_match = False
                if dist_prev_bmg:
                    prev_script_text = get_prev_script_text(line_num)
                    dist_prev_script = distill(prev_script_text)
                    if dist_prev_script:
                        if dist_prev_bmg in dist_prev_script or dist_prev_script in dist_prev_bmg:
                            has_prev_match = True
                            
                has_next_match = False
                if dist_next_bmg:
                    next_script_text = get_next_script_text(line_num)
                    dist_next_script = distill(next_script_text)
                    if dist_next_script:
                        if dist_next_bmg in dist_next_script or dist_next_script in dist_next_bmg:
                            has_next_match = True
                            
                context_level = 0
                if has_prev_match and has_next_match:
                    context_level = 2
                elif has_prev_match or has_next_match:
                    context_level = 1
                    
                candidates.append({
                    "line_num": line_num,
                    "context_level": context_level,
                    "word_diff": word_diff
                })
            start_pos = pos + 1
            
        if not candidates:
            return "NONE", None
            
        # FILTERING HIERARCHY
        # 1. Keep max context level
        max_level = max(c["context_level"] for c in candidates)
        filtered = [c for c in candidates if c["context_level"] == max_level]
        
        # 2. Keep min word count diff
        min_diff = min(c["word_diff"] for c in filtered)
        final_candidates = [c for c in filtered if c["word_diff"] == min_diff]
        
        matched_lines = []
        for c in final_candidates:
            if c["line_num"] not in matched_lines:
                matched_lines.append(c["line_num"])
                
        speakers = []
        for line_num in matched_lines:
            speaker = None
            for idx in range(line_num - 2, -1, -1):
                s = lines[idx].strip()
                if not s:
                    continue
                if s.startswith("[") and s.endswith("]"):
                    continue
                if line_strip_is_speaker(s):
                    speaker = s
                    break
            if speaker and speaker not in speakers:
                speakers.append(speaker)
                
        if matched_lines:
            matched_lines_str = ", ".join(str(line_num) for line_num in matched_lines)
            speaker_str = ", ".join(speakers) if speakers else "NONE"
            return speaker_str, matched_lines_str
            
        return None
