from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from core.story_context_overrides import get_story_context_override
from core.translation.session_manager import TranslationSessionState
from core.translation.story_context_bundle import glossary_names_from_story_bundle
from utils.logging_utils import log_debug
from utils.utils import resolve_target_language_prompt

from .instructions import append_engine_rules, single_rules


class MessagesMixin:
    """Single-string, variation, and glossary prompt composition."""

    def _resolve_prompt_speaker(
        self,
        block_idx: Optional[int],
        string_idx: Optional[int],
        text: str,
        translation_context: Dict,
    ) -> Tuple[Optional[str], set]:
        """Resolve speaker for single/batch translation prompts via resolve_speaker_for_string.

        Returns (resolved_speaker, speaker_candidates).
        """
        from utils.utils import remove_all_tags
        from core.speaker_resolution import (
            resolve_speaker_for_string,
            resolve_speaker_identity,
        )

        clean_text = remove_all_tags(text).strip()
        is_single_word = len(clean_text.split()) <= 1

        manual = (
            get_story_context_override(self.mw, block_idx, string_idx)
            if block_idx is not None and string_idx is not None else {}
        )
        manual_speaker = str(manual.get("speaker") or "").strip()

        raw_identity: Optional[str] = None
        speaker: Optional[str] = None

        if manual_speaker:
            if manual_speaker.casefold() == "none":
                speaker = "NONE"
            else:
                raw_identity = resolve_speaker_identity(self.mw, manual_speaker)
                if raw_identity is None:
                    speaker = "NONE"
                else:
                    speaker = self._translate_speaker(raw_identity)
        elif translation_context.get('has_speaker') is False:
            speaker = "NONE"
        elif is_single_word:
            speaker = "NONE"
        elif block_idx is not None and string_idx is not None:
            res = resolve_speaker_for_string(self.mw, block_idx, string_idx, composer=self)
            if res and res.name:
                raw_identity = res.name
                speaker = self._translate_speaker(raw_identity)

        speaker_candidates = set()
        if raw_identity and raw_identity not in ("Unknown", "NONE"):
            for part in raw_identity.split(','):
                if part.strip():
                    speaker_candidates.add(part.strip())

        if speaker and speaker not in ("Unknown", "NONE"):
            for part in speaker.split(','):
                if part.strip():
                    speaker_candidates.add(part.strip())

        return speaker, speaker_candidates

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
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            converted = self.mw.current_game_rules.get_text_representation_for_editor(source_text)
            if isinstance(converted, str):
                source_text = converted
            if selected_text:
                converted_sel = self.mw.current_game_rules.get_text_representation_for_editor(selected_text)
                if isinstance(converted_sel, str):
                    selected_text = converted_sel

        source_text = self._replace_runtime_names_for_ai(source_text)
        if selected_text:
            selected_text = self._replace_runtime_names_for_ai(selected_text)

        target_lang = self._get_target_lang()
        glossary_text = ""
        glossary_manager = self.main_handler._glossary_manager

        manual = (
            get_story_context_override(self.mw, block_idx, string_idx)
            if block_idx is not None and string_idx is not None else {}
        )
        structured_story_context = (
            {}
            if manual.get("structure_id") == "story:none"
            or block_idx is None or string_idx is None
            else self._get_structured_story_context(block_idx, string_idx)
        )

        translation_context = {}
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules is not None and block_idx is not None and string_idx is not None and hasattr(rules, 'get_translation_context_for_string'):
            try:
                candidate = rules.get_translation_context_for_string(block_idx, string_idx)
                if isinstance(candidate, dict):
                    translation_context = candidate
            except Exception as e:
                log_debug(f"AIPromptComposer: single-string translation context failed: {e}")

        speaker, item_spk_candidates = self._resolve_prompt_speaker(
            block_idx, string_idx, source_text, translation_context
        )

        speaker_candidates = set(item_spk_candidates)
        speaker_candidates.update(
            glossary_names_from_story_bundle(structured_story_context)
        )

        if glossary_manager and source_text:
            text_for_glossary = f"{source_text} {selected_text}" if selected_text else source_text
            if structured_story_context:
                text_for_glossary += " " + json.dumps(
                    structured_story_context, ensure_ascii=False
                )
            relevant_glossary_entries = list(glossary_manager.get_relevant_terms(text_for_glossary))
            self._append_speaker_glossary_entries(relevant_glossary_entries, speaker_candidates)
            if relevant_glossary_entries:
                glossary_text = self._glossary_entries_to_text(relevant_glossary_entries)

        tag_alias_legend = self._relevant_tag_aliases(
            getattr(self.mw, 'default_tag_mappings', {}),
            source_text, current_translation,
        )

        tag_alias_legend_text = ""
        if tag_alias_legend:
            tag_alias_legend_text = "TAG ALIAS LEGEND:\n" + "\n".join(f"- {alias} -> {orig}" for alias, orig in tag_alias_legend.items())

        # The rules for this kind of request are fixed text appended to the system
        # prompt (see instructions.py), so the system prompt does not vary per string.
        combined_system = resolve_target_language_prompt(
            append_engine_rules(system_prompt, single_rules(request_type, has_selection=bool(selected_text))),
            target_lang,
        )

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else 'Unknown game'
        context_lines.append(f'Game: {game_name}')
        if block_idx is not None and block_idx != -1:
            block_label = self._get_block_label(block_idx)
            context_lines.append(f'Block: {block_label} (#{block_idx})')
        if string_idx is not None and string_idx != -1:
            context_lines.append(f'Row: #{string_idx}')
        if speaker and speaker not in ("Unknown", "NONE"):
            context_lines.append(f'Speaker: {speaker}')
        if mode_description:
            context_lines.append(f'Mode: {mode_description}')
        if translation_context.get('window_type'):
            context_lines.append(f"Window Type: {translation_context['window_type']}")
        if translation_context.get('content_role'):
            context_lines.append(f"Content Role: {translation_context['content_role']}")
        if translation_context.get('role_instruction'):
            # Inserted verbatim; the engine assigns it no meaning.
            context_lines.append(f"Role Instruction: {translation_context['role_instruction']}")
        structure_path = [
            str(part) for part in manual.get('structure_path') or () if str(part)
        ]
        if manual.get('structure_id') == 'story:none':
            context_lines.append('Story Structure: None (manually unassigned)')
        elif structure_path:
            context_lines.append('Story Structure: ' + ' > '.join(structure_path))
        manual_item = str(manual.get('item') or '').strip()
        if manual_item:
            context_lines.append(
                'Reference Item: ' + (
                    'None (manually unassigned)'
                    if manual_item.casefold() == 'none' else manual_item
                )
            )
        translator_note = str(manual.get('translator_note') or '').strip()
        if translator_note:
            context_lines.append(f'Translator Note: {translator_note}')
        if structured_story_context:
            context_lines.append(
                "MEMORY PALACE CONTEXT (structured authoritative facts):\n"
                + json.dumps(structured_story_context, indent=2, ensure_ascii=False)
            )
        layout_source = selected_text if selected_text is not None else source_text
        context_lines.append(
            "SOURCE LAYOUT TARGET (preserve when viable; minimal expansion allowed):\n"
            + json.dumps(
                self._layout_contract_for_string(
                    layout_source, block_idx, string_idx
                ),
                ensure_ascii=False,
            )
        )

        # Fetch story context from MemePalace if available
        if block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            story_context = self._fetch_story_context(block_idx, string_idx, source_text)
            if story_context:
                context_lines.append(f"Story Context:\n{story_context}")

        # Reference translations from unpacked ROM / patch
        ref_texts: List[str] = []
        ref_langs = getattr(self.mw.data_store, 'reference_languages_data', {})
        if block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            if isinstance(ref_langs, dict) and ref_langs:
                for lang_name, lang_dict in ref_langs.items():
                    if isinstance(lang_dict, dict):
                        t = lang_dict.get((block_idx, string_idx), "")
                        if isinstance(t, str) and t.strip():
                            ref_texts.append(f"- {lang_name}: {t.strip()}")
            else:
                raw_ref = getattr(self.mw.data_store, 'reference_data', {})
                if isinstance(raw_ref, dict):
                    single_ref = raw_ref.get((block_idx, string_idx), "")
                    if isinstance(single_ref, str) and single_ref.strip():
                        from core.reference_manager import ReferenceManager
                        game_rules = getattr(self.mw, 'current_game_rules', None)
                        ref_label = ReferenceManager.get_reference_language_label(game_rules)
                        ref_texts.append(f"- {ref_label}: {single_ref.strip()}")
            if ref_texts:
                context_lines.append(
                    "REFERENCE TRANSLATIONS (contextual reference only; the original text remains the source):\n"
                    + "\n".join(ref_texts)
                )

        # Objective conversation structure from the game BMG itself. This is
        # complementary to MemePalace: it supplies real order, branches,
        # conditions and game actions, but does not override the per-line speaker.
        dialogue_flow_context = ""
        if block_idx is not None and block_idx != -1 and string_idx is not None and string_idx != -1:
            rules = getattr(self.mw, 'current_game_rules', None)
            if rules is not None:
                flow_parts = []
                try:
                    if hasattr(rules, 'get_ai_flow_context_for_string'):
                        line_flow = rules.get_ai_flow_context_for_string(block_idx, string_idx)
                        if isinstance(line_flow, str) and line_flow:
                            flow_parts.append(f"Current line: {line_flow}")
                    if hasattr(rules, 'get_ai_flow_overview'):
                        overview = rules.get_ai_flow_overview(block_idx, [string_idx])
                        if isinstance(overview, str) and overview:
                            flow_parts.append(overview)
                except Exception as e:
                    log_debug(f"AIPromptComposer: single-string flow context failed: {e}")
                if flow_parts:
                    dialogue_flow_context = "\n\n".join(flow_parts)
                    context_lines.append(f"Dialogue Flow (from game data):\n{dialogue_flow_context}")

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

        user_sections: List[str] = ['\n'.join(context_lines)]
        if glossary_text:
            user_sections.append(f"GLOSSARY (use with absolute priority):\n{glossary_text}")
        if tag_alias_legend_text:
            user_sections.append(tag_alias_legend_text)

        if request_type == 'variation_list' and current_translation:
            if selected_text:
                user_sections.append('Full original text (for context):')
                user_sections.append(source_text)
                user_sections.append('Full current translation (for context):')
                user_sections.append(str(current_translation))
                user_sections.append('Selected segment to vary/translate (Input text, original source):')
                user_sections.append(selected_text)
            else:
                user_sections.append('Current translation:')
                user_sections.append(str(current_translation))
                user_sections.append('Input text (Original source):')
                user_sections.append(source_text)
        else:
            if request_type == 'glossary_notes_variation' and current_translation is not None:
                user_sections.append('Current description:')
                user_sections.append(str(current_translation or '(empty)'))

            user_sections.append('Input text (Original source):')
            user_sections.append(source_text)

        user_content = '\n\n'.join([section for section in user_sections if section])
        user_content = self._replace_runtime_names_for_ai(user_content)
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
        target_lang = self._get_target_lang()
        system_prompt_resolved = resolve_target_language_prompt(system_prompt, target_lang)
        combined_system = self._prepare_glossary_for_prompt(system_prompt_resolved, session_state)
        instructions = [
            f"Update the existing {target_lang} translation to reflect the new glossary term translation.",
            "Preserve all tags, placeholders, punctuation, whitespace, and line breaks exactly as in the input.",
            f"Keep the total number of lines at {expected_lines}; do not add or remove lines.",
            "Use the new glossary translation naturally (adjust case/grammar if required by context).",
            f"Return JSON only: {{\"translation\": \"...\"}} with the updated {target_lang} text.",
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
        user_content = self._replace_runtime_names_for_ai(user_content)
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
        target_lang = self._get_target_lang()
        system_prompt_resolved = resolve_target_language_prompt(system_prompt, target_lang)
        combined_system = self._prepare_glossary_for_prompt(system_prompt_resolved, session_state)
        instructions = [
            f"For each object in the JSON payload, update the {target_lang} translation to use the new glossary translation.",
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
        user_content = self._replace_runtime_names_for_ai(user_content)
        log_debug(
            "Composed glossary batch update: "
            f"System prompt size={len(combined_system)}, User content size={len(user_content)}"
        )
        return combined_system, user_content

    def compose_glossary_request(self, system_prompt: str, user_content: str, **_: Dict) -> Tuple[str, str]:
        """Compose glossary request."""
        return system_prompt.strip(), self._replace_runtime_names_for_ai(user_content)
