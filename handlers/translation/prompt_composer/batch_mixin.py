from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from core.story_context_overrides import get_story_context_override
from core.translation.session_manager import TranslationSessionState
from core.translation.story_context_bundle import glossary_names_from_story_bundle
from utils.logging_utils import log_debug
from utils.utils import resolve_target_language_prompt


class BatchMixin:
    """Batch translation prompt composition."""

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
        story_context_catalog = {}
        story_context_refs = {}
        for item in source_items:
            if isinstance(item, dict):
                item_id = item.get('id', 0)
                current_text = item.get('text', '')
            else:
                item_id = 0
                current_text = str(item)

            # Convert to editor representation to unify page/line breaks (e.g. \\n to \n)
            if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
                converted = self.mw.current_game_rules.get_text_representation_for_editor(current_text)
                if isinstance(converted, str):
                    current_text = converted

            # Apply force-aliases
            from utils.force_alias import prepare_text_for_ai
            tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
            current_text_for_ai, force_maps = prepare_text_for_ai(current_text, tag_mappings)
            current_text_for_ai = self._replace_runtime_names_for_ai(current_text_for_ai)
            if force_maps:
                placeholder_map[item_id] = force_maps

            # Keep the exact editor-visible line structure and whitespace. The
            # response validator enforces a one-to-one line layout.
            current_text_clean = current_text_for_ai.replace('\r\n', '\n').replace('\r', '\n')

            # Resolve real data-store coordinates for this item
            real_b_idx = block_idx
            real_s_idx = item_id
            if temp_id_map and item_id in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[item_id]
            elif temp_id_map and str(item_id) in temp_id_map:
                real_b_idx, real_s_idx = temp_id_map[str(item_id)]

            translation_context = {}
            rules = getattr(self.mw, 'current_game_rules', None)
            if rules is not None and hasattr(rules, 'get_translation_context_for_string'):
                try:
                    candidate = rules.get_translation_context_for_string(real_b_idx, real_s_idx)
                    if isinstance(candidate, dict):
                        translation_context = candidate
                except Exception as e:
                    log_debug(f"AIPromptComposer: translation context failed for ({real_b_idx},{real_s_idx}): {e}")

            manual = get_story_context_override(self.mw, real_b_idx, real_s_idx)
            structured_story_context = (
                {}
                if manual.get("structure_id") == "story:none"
                else self._get_structured_story_context(real_b_idx, real_s_idx)
            )

            speaker, item_spk_candidates = self._resolve_prompt_speaker(
                real_b_idx, real_s_idx, current_text, translation_context
            )
            if not speaker:
                speaker = "Unknown"

            speaker_candidates.update(item_spk_candidates)
            speaker_candidates.update(
                glossary_names_from_story_bundle(structured_story_context)
            )

            item_for_ai = {
                'id': item_id,
                'text': current_text_clean,
                'speaker': speaker,
                'layout': self._layout_contract_for_string(
                    current_text_clean, real_b_idx, real_s_idx
                ),
            }
            item_for_ai.update(translation_context)
            structure_path = [
                str(part) for part in manual.get('structure_path') or () if str(part)
            ]
            if manual.get('structure_id') == 'story:none':
                item_for_ai['story_structure'] = 'None (manually unassigned)'
            elif structure_path:
                item_for_ai['story_structure'] = ' > '.join(structure_path)
            manual_item = str(manual.get('item') or '').strip()
            if manual_item:
                item_for_ai['reference_item'] = (
                    'None (manually unassigned)'
                    if manual_item.casefold() == 'none' else manual_item
                )
            translator_note = str(manual.get('translator_note') or '').strip()
            if translator_note:
                item_for_ai['translator_note'] = translator_note
            if structured_story_context:
                context_key = json.dumps(
                    structured_story_context, ensure_ascii=False, sort_keys=True
                )
                context_ref = story_context_refs.get(context_key)
                if context_ref is None:
                    context_ref = f"story_context_{len(story_context_catalog) + 1}"
                    story_context_refs[context_key] = context_ref
                    story_context_catalog[context_ref] = structured_story_context
                item_for_ai['story_context_ref'] = context_ref
            if isinstance(item, dict) and item.get('scene_context'):
                item_for_ai['scene_context'] = item['scene_context']

            # Who the line is spoken TO (plugin-provided). Needed for languages
            # that mark politeness or gender in address; the speaker alone is
            # not enough to choose between them.
            if rules is not None and hasattr(rules, 'get_addressee_for_string'):
                try:
                    addressee = rules.get_addressee_for_string(
                        real_b_idx, real_s_idx, speaker=speaker
                    )
                    if isinstance(addressee, str) and addressee:
                        item_for_ai['addressee'] = self._translate_speaker(addressee)
                except Exception as e:
                    log_debug(f"AIPromptComposer: addressee failed for ({real_b_idx},{real_s_idx}): {e}")

            # Game-script flow context (plugin-provided): conversation position,
            # branch conditions and follow-up game actions for this exact line
            if rules is not None and hasattr(rules, 'get_ai_flow_context_for_string'):
                try:
                    flow_ctx = rules.get_ai_flow_context_for_string(real_b_idx, real_s_idx)
                    if isinstance(flow_ctx, str) and flow_ctx:
                        item_for_ai['flow_context'] = flow_ctx
                except Exception as e:
                    log_debug(f"AIPromptComposer: flow context failed for ({real_b_idx},{real_s_idx}): {e}")

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
        if story_context_catalog:
            lookahead_text += " " + json.dumps(
                story_context_catalog, ensure_ascii=False
            )

        relevant_glossary_entries = []
        if glossary_manager:
            relevant_glossary_entries = list(glossary_manager.get_relevant_terms(lookahead_text))
            self._append_speaker_glossary_entries(relevant_glossary_entries, speaker_candidates)
        glossary_text = self._glossary_entries_to_text(relevant_glossary_entries)

        # 3b. Game-script dialogue flow outlines for the whole chunk: the actual
        # in-game conversation graphs (order, player choices, conditions) that
        # contain the lines being translated (plugin-provided)
        dialogue_flow = ""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules is not None and hasattr(rules, 'get_ai_flow_overview'):
            try:
                indices_by_block = {}
                for item in source_items:
                    iid = item.get('id', 0) if isinstance(item, dict) else 0
                    rb, rs = block_idx, iid
                    if temp_id_map and iid in temp_id_map:
                        rb, rs = temp_id_map[iid]
                    elif temp_id_map and str(iid) in temp_id_map:
                        rb, rs = temp_id_map[str(iid)]
                    indices_by_block.setdefault(rb, []).append(rs)
                overviews = []
                for rb, indices in indices_by_block.items():
                    ov = rules.get_ai_flow_overview(rb, indices)
                    if isinstance(ov, str) and ov:
                        overviews.append(ov)
                dialogue_flow = "\n\n".join(overviews)
            except Exception as e:
                log_debug(f"AIPromptComposer: flow overview failed: {e}")

        # 4. Build JSON payload
        tag_alias_legend = self._relevant_tag_aliases(
            getattr(self.mw, 'default_tag_mappings', {}),
            *(str(it.get('text', '')) for it in items_with_context),
        )

        json_payload_for_ai = {
            'strings_to_translate': items_with_context
        }
        if story_context_catalog:
            json_payload_for_ai['story_context_catalog'] = story_context_catalog
        if scene_context:
            json_payload_for_ai['scene_context'] = scene_context
        if dialogue_flow:
            json_payload_for_ai['dialogue_flow'] = dialogue_flow
        if glossary_text:
            json_payload_for_ai['glossary'] = glossary_text
        if tag_alias_legend:
            json_payload_for_ai['tag_alias_legend'] = tag_alias_legend

        target_lang = self._get_target_lang()
        if not is_retry:
            instructions = [
                f'Translate the "text" field for each object in the "strings_to_translate" array into {target_lang}.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object in the returned array must have the original "id" (integer) and a "translation" (string) field.',
                'The number of objects in the "translated_strings" array must exactly match the number of objects provided in the input.',
                'LAYOUT PRIORITY: First try to preserve line_count, blank_line_indices, trailing-newline state, and window_count from each item\'s "layout" field. Translate each source line into the corresponding output line and prefer concise wording that stays within max_line_width_px. Never remove, merge, or reorder source lines. You may add the minimum necessary extra lines, and therefore an extra dialogue window, only when the translation cannot remain readable or fit the width otherwise.',
                f'GLOSSARY IS MANDATORY: Every term found in the "glossary" field MUST be translated exactly as specified there. Do NOT use synonyms, alternatives, or your own translation for glossary terms. You may only inflect the word endings to match {target_lang} grammar. Glossary overrides everything.',
                'Carefully read the "Notes" column of the glossary for details about character gender, age, personality, speech style, and the form of address (e.g. formal/informal). Apply this information to the entire translation.',
                'Resolve each item\'s "story_context_ref" in "story_context_catalog". Use its event, location, participants, event-local interactions, character profiles, and known relationships. Apply only populated facts; do not invent missing context.',
                'Use per-item "window_type", "content_role", "story_structure", and "reference_item", plus "scene_context" (if present), "speaker" and "addressee", to determine whether text is dialogue, a caption, a name, an item, or another UI role and translate it accordingly.',
                'Follow the rules from the system prompt regarding tags.',
                'Do not add any explanations or text outside the JSON object.',
            ]
        else:
            instructions = [
                'Your previous response was invalid. Please correct it.',
                f'Error: {retry_reason}',
                'Follow these instructions carefully:',
                f'Translate the "text" field for each object in the "strings_to_translate" array into {target_lang}.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object must have the original "id" and a "translation" field.',
                'The number of objects must match the input.',
                'LAYOUT PRIORITY: Try to match every item\'s "layout", including window_count, and translate source lines one-to-one. Never remove, merge, or reorder source lines. Prefer concise wording within max_line_width_px; add only the minimum necessary extra lines or dialogue windows when preserving the original count is not viable.',
                'GLOSSARY IS MANDATORY: Every term in the "glossary" MUST be translated exactly as specified. No synonyms or alternatives allowed.',
                'Resolve each item\'s "story_context_ref" in "story_context_catalog" and use it for event facts, location, participants, interactions, character voices, relationships, gender agreement, and forms of address. Do not invent missing facts.',
                'Use per-item "window_type", "content_role", "story_structure", and "reference_item", plus "scene_context" (if present), "speaker" and "addressee", to determine the text role and tone.',
                'Follow the rules from the system prompt regarding tags.',
                'Do not add any explanations or text outside the JSON object.',
            ]

        has_flow_items = any('flow_context' in it for it in items_with_context)
        if dialogue_flow or has_flow_items:
            instructions.append(
                'DIALOGUE FLOW: The "dialogue_flow" field (and per-item "flow_context") describes the real '
                'in-game conversation graphs extracted from the game data: the order lines are spoken in, '
                'player choices, the conditions under which a line appears (e.g. wolf form, not enough rupees) '
                'and game actions that follow it. Use this to keep replies coherent with their questions, '
                'match choice answers to the choice prompt, and pick the correct tone and referents.'
            )

        # Role instructions come from the plugin verbatim: the engine inserts the
        # text without knowing what the role means. Deduplicated in first-seen
        # order so a role shared by many items is stated once.
        seen_roles = set()
        for item in items_with_context:
            role = item.get('content_role')
            instruction = item.get('role_instruction')
            if not instruction or role in seen_roles:
                continue
            seen_roles.add(role)
            instructions.append(str(instruction))

        if any(it.get('addressee') for it in items_with_context):
            instructions.append(
                'ADDRESSEE: The "addressee" field names who the line is spoken TO. '
                'Use it to choose the form of address the target language requires '
                '(politeness level, formal vs familiar "you", gendered forms) and to '
                'keep that choice consistent for the same pair of characters.'
            )

        if tag_alias_legend:
            instructions.append('TAG ALIAS LEGEND: Use the "tag_alias_legend" field in the JSON payload to understand the meaning of tag aliases (e.g. colors, speed). Place these tag aliases correctly around the corresponding translated words.')
        instructions.append('ANCHORED TAGS: Any tags not present in the "tag_alias_legend" are anchored system tags (e.g. {0}, {1}, [PLAYER]). Do NOT translate, modify, or delete them. Keep them exactly in their correct relative positions in the translation.')

        # Add a note about text unity to the system prompt
        system_prompt_addition = (
            "IMPORTANT: All text chunks you receive in a single request are part of a larger, "
            "cohesive block of text. Ensure your translations are consistent in style, tone, "
            "and terminology across all chunks. Context priority: preserve source meaning and tags; "
            "obey glossary translations; use event/location/participant facts; apply relationship and "
            "address rules; then preserve each current speaker's voice profile. Context describes the "
            "source scene and must never be copied into the translation as extra text. OUTPUT SHAPE IS "
            "IMMUTABLE: preserve every source line boundary and blank line; never reflow text."
        )

        final_system_prompt = f"{system_prompt}\n\n{system_prompt_addition}"
        final_system_prompt = resolve_target_language_prompt(final_system_prompt, target_lang)
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
        user_content = self._replace_runtime_names_for_ai(user_content)

        log_debug(
            f'Composed batch request for AI. System prompt size: {len(combined_system)}, '
            f'User content size: {len(user_content)}'
        )
        return combined_system, user_content, placeholder_map
