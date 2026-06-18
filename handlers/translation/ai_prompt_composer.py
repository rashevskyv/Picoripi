from __future__ import annotations

import json
import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from core.translation.session_manager import TranslationSessionState
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug

# Import new services
from core.translation.placeholder_manager import AIPlaceholderManager
from core.translation.glossary_formatter import GlossaryPromptFormatter
from core.translation.story_context_manager import StoryContextManager
from core.translation.script_speaker_finder import ScriptSpeakerFinder


class AIPromptComposer(BaseTranslationHandler):
    """Compose prompts for AI translation/variation tasks and manage placeholders."""

    def __init__(self, *args, **kwargs):
        """Initialize a new instance."""
        super().__init__(*args, **kwargs)

        # Instantiate services
        self.placeholder_manager = AIPlaceholderManager()
        self.glossary_formatter = GlossaryPromptFormatter()
        self.story_context = StoryContextManager(self.mw)
        self.script_speaker_finder = ScriptSpeakerFinder(self.mw, self.story_context)

    # ------------------------------------------------------------------
    # Properties for backwards compatibility with test cache assertions
    # ------------------------------------------------------------------
    @property
    def _script_lines_cache(self):
        return self.script_speaker_finder._script_lines_cache
    @_script_lines_cache.setter
    def _script_lines_cache(self, val):
        self.script_speaker_finder._script_lines_cache = val

    @property
    def _global_distilled_text_cache(self):
        return self.script_speaker_finder._global_distilled_text_cache
    @_global_distilled_text_cache.setter
    def _global_distilled_text_cache(self, val):
        self.script_speaker_finder._global_distilled_text_cache = val

    @property
    def _char_to_line_map_cache(self):
        return self.script_speaker_finder._char_to_line_map_cache
    @_char_to_line_map_cache.setter
    def _char_to_line_map_cache(self, val):
        self.script_speaker_finder._char_to_line_map_cache = val

    @property
    def _cached_script_path(self):
        return self.script_speaker_finder._cached_script_path
    @_cached_script_path.setter
    def _cached_script_path(self, val):
        self.script_speaker_finder._cached_script_path = val

    @property
    def _cached_mtime(self):
        return self.script_speaker_finder._cached_mtime
    @_cached_mtime.setter
    def _cached_mtime(self, val):
        self.script_speaker_finder._cached_mtime = val

    @property
    def _cached_size(self):
        return self.script_speaker_finder._cached_size
    @_cached_size.setter
    def _cached_size(self, val):
        self.script_speaker_finder._cached_size = val

    @property
    def _cached_plugin_name(self):
        return self.script_speaker_finder._cached_plugin_name
    @_cached_plugin_name.setter
    def _cached_plugin_name(self, val):
        self.script_speaker_finder._cached_plugin_name = val

    @property
    def _distill_cache_version(self):
        return self.script_speaker_finder._distill_cache_version
    @_distill_cache_version.setter
    def _distill_cache_version(self, val):
        self.script_speaker_finder._distill_cache_version = val

    # Helper methods mapped to services
    def _find_script_path(self) -> Optional[str]:
        return self.script_speaker_finder.find_script_path()

    def _translate_speaker(self, speaker: str) -> str:
        glossary_manager = self.main_handler._glossary_manager
        return self.script_speaker_finder.translate_speaker(speaker, glossary_manager)

    def _find_speaker_in_script(self, block_idx: int, s_idx: int, text: str) -> Optional[Tuple[str, Optional[str]]]:
        block_label = self.story_context.get_block_label(block_idx)
        default_wing_name = self.story_context.get_wing_name()
        return self.script_speaker_finder.find_speaker_in_script(
            block_idx, s_idx, text, default_wing_name, block_label
        )

    def _get_mempalace_client(self) -> Optional[object]:
        return self.story_context.get_mempalace_client()

    def _get_wing_name(self) -> str:
        return self.story_context.get_wing_name()

    def _get_block_label(self, block_idx: int) -> str:
        return self.story_context.get_block_label(block_idx)

    def _fetch_story_context(self, block_idx: int, s_idx: int, text: str) -> Optional[str]:
        return self.story_context.fetch_story_context(
            block_idx, s_idx, text, self.script_speaker_finder, self.data_processor
        )

    def _append_speaker_glossary_entries(
        self,
        relevant_entries: List[GlossaryEntry],
        speaker_candidates: Iterable[str]
    ) -> None:
        glossary_manager = self.main_handler._glossary_manager
        self.glossary_formatter.append_speaker_glossary_entries(
            relevant_entries, speaker_candidates, glossary_manager
        )

    def _glossary_entries_to_text(self, entries: Sequence[GlossaryEntry]) -> str:
        return self.glossary_formatter.glossary_entries_to_text(entries)

    def _prepare_glossary_for_prompt(
        self,
        system_prompt: str,
        session_state: Optional[TranslationSessionState],
        is_batch_translation: bool = False,
    ) -> str:
        return (system_prompt or "").strip()

    # ------------------------------------------------------------------
    # Public API used by translation handler
    # ------------------------------------------------------------------
    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        """Prepare text for translation."""
        return self.placeholder_manager.prepare_text_for_translation(source_text, glossary_entries)

    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
    ) -> str:
        """Restore placeholders."""
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
        glossary_manager = self.main_handler._glossary_manager
        return self.placeholder_manager.restore_placeholders(
            translated_text,
            placeholder_map,
            key=key,
            default_tag_mappings=default_tag_mappings,
            glossary_manager=glossary_manager,
        )

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
        """Compose batch request."""
        placeholder_map: Dict = {}
        glossary_manager = self.main_handler._glossary_manager
        client = self._get_mempalace_client()
        wing_name = self._get_wing_name()
        block_label = self._get_block_label(block_idx)

        # 1. Resolve speakers and clean newlines for all items in chunk
        items_with_context = []
        speaker_candidates = set()
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
            raw_spk = None

            from utils.utils import remove_all_tags
            clean_item_text = remove_all_tags(current_text).strip()
            is_single_word = len(clean_item_text.split()) <= 1

            if is_single_word:
                speaker = "NONE"
            else:
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

                script_res = self._find_speaker_in_script(real_b_idx, real_s_idx, current_text)
                if script_res and isinstance(script_res, (tuple, list)) and len(script_res) == 2:
                    raw_spk = script_res[0]

                if not speaker:
                    speaker = self._translate_speaker(raw_spk) if raw_spk else None

                if not speaker:
                    speaker = "Unknown"

            if raw_spk:
                for part in raw_spk.split(','):
                    speaker_candidates.add(part.strip())
            if speaker and speaker not in ("Unknown", "NONE"):
                for part in speaker.split(','):
                    speaker_candidates.add(part.strip())

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
            relevant_glossary_entries = list(glossary_manager.get_relevant_terms(lookahead_text))
            self._append_speaker_glossary_entries(relevant_glossary_entries, speaker_candidates)
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
                'GLOSSARY IS MANDATORY: Every term found in the "glossary" field MUST be translated exactly as specified there. Do NOT use synonyms, alternatives, or your own translation for glossary terms. You may only inflect the word endings to match Ukrainian grammar. Glossary overrides everything.',
                'Carefully read the "Notes" column of the glossary for details about character gender, age, personality, speech style, and the form of address (ти/ви). Apply this information to the entire translation.',
                'Use "scene_context" (if present) and "speaker" to determine the correct tone, formality, and speech mannerisms.',
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
                'GLOSSARY IS MANDATORY: Every term in the "glossary" MUST be translated exactly as specified. No synonyms or alternatives allowed.',
                'Use "scene_context" (if present) and "speaker" to determine tone, gender agreement, and form of address.',
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
        selected_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Compose variation request."""
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
            selected_text=selected_text,
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
        selected_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Compose messages."""
        glossary_text = ""
        glossary_manager = self.main_handler._glossary_manager

        # Resolve speaker for this string to include in glossary lookup
        speaker_candidates = set()
        from utils.utils import remove_all_tags
        clean_src_text = remove_all_tags(source_text).strip()
        is_single_word = len(clean_src_text.split()) <= 1

        speaker = None
        raw_spk = None

        if is_single_word:
            speaker = "NONE"
        elif block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            client = self._get_mempalace_client()
            block_label = self._get_block_label(block_idx)
            if client:
                bmg_id = f"{block_label}_Str_{string_idx}"
                cached_ctx = client.get_cached_context(bmg_id, source_text)
                if cached_ctx:
                    speaker = cached_ctx.get("speaker")

            script_res = self._find_speaker_in_script(block_idx, string_idx, source_text)
            if script_res and isinstance(script_res, (tuple, list)) and len(script_res) == 2:
                raw_spk = script_res[0]

            if not speaker:
                speaker = self._translate_speaker(raw_spk) if raw_spk else None

            if not speaker:
                speaker = "Unknown"

        if raw_spk:
            for part in raw_spk.split(','):
                speaker_candidates.add(part.strip())
        if speaker and speaker not in ("Unknown", "NONE"):
            for part in speaker.split(','):
                speaker_candidates.add(part.strip())

        if glossary_manager and source_text:
            text_for_glossary = f"{source_text} {selected_text}" if selected_text else source_text
            relevant_glossary_entries = list(glossary_manager.get_relevant_terms(text_for_glossary))
            self._append_speaker_glossary_entries(relevant_glossary_entries, speaker_candidates)
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
            if selected_text:
                instructions = [
                    'Generate 10 different Ukrainian translation alternatives specifically for the selected text segment, keeping the context of the full string in mind.',
                    f'Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.',
                    'Follow the glossary and preserve all tags exactly as they appear.',
                    'Follow the tone of the original text and the surrounding translation.',
                    'Return the response as a raw JSON array of strings, for example: ["option 1", "option 2", ...].',
                    'Do NOT wrap the array in an object. Return only valid JSON without any markdown or extra commentary.',
                ]
            else:
                instructions = [
                    'Generate 10 different Ukrainian translation alternatives for the provided text.',
                    f'Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.',
                    'Follow the glossary and preserve all tags exactly as they appear.',
                    'Follow the tone of the original text.',
                    'Return the response as a raw JSON array of strings, for example: ["option 1", "option 2", ...].',
                    'Do NOT wrap the array in an object (e.g. do not use {"variations": [...]}). Return only valid JSON without any markdown or extra commentary.',
                ]
        elif request_type == 'glossary_notes_variation':
            instructions = [
                'Generate 5 alternative Ukrainian glossary descriptions for the provided term.',
                'Each description should be 1-2 sentences and stay under 60 words.',
                'Preserve any tags/placeholders exactly as provided.',
                'Keep the description informative and suitable for a glossary entry.',
                'Return the response as a raw JSON array of strings, for example: ["option 1", "option 2", ...].',
                'Do NOT wrap the array in an object. Return only valid JSON without any markdown or extra commentary.',
            ]
        else:
            instructions = [
                'Translate the text into Ukrainian without altering the meaning.',
                f'Keep exactly {expected_lines} lines (including empty ones) and preserve their order.',
                'GLOSSARY IS MANDATORY: Every term found in the glossary MUST be translated exactly as specified in the "Translation" column. Do NOT use synonyms, alternatives, or your own translation for glossary terms. You may only inflect word endings to match Ukrainian grammar.',
                'Read the "Notes" column in the glossary carefully for character gender, age, personality, speech style, and form of address (ти/ви). Apply this to the full translation.',
                'All tags must be preserved exactly as they appear.',
                'Do not add explanations or meta text; return only the translation.',
            ]

        user_sections: List[str] = ['\n'.join(context_lines), '\n'.join(instructions)]
        if glossary_text:
            user_sections.append(f"GLOSSARY (use with absolute priority):\n{glossary_text}")

        if request_type == 'variation_list' and current_translation:
            if selected_text:
                user_sections.append('Full original text (for context):')
                user_sections.append(source_text)
                user_sections.append('Full current translation (for context):')
                user_sections.append(str(current_translation))
                user_sections.append('Selected segment to vary/translate (Input text):')
                user_sections.append(selected_text)
            else:
                user_sections.append('Current translation:')
                user_sections.append(str(current_translation))
                user_sections.append('Input text:')
                user_sections.append(source_text)
        else:
            if request_type == 'glossary_notes_variation' and current_translation is not None:
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
        """Compose glossary occurrence update request."""
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
        """Compose glossary occurrence batch request."""
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
        """Compose glossary request."""
        return system_prompt.strip(), user_content
