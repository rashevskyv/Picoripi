"""Prompt for a batch of strings: payload, context rows, run memory."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from core.story_context_overrides import get_story_context_override
from core.translation.layout_contract import resolve_lines_per_window
from core.translation.run_memory import RunMemory
from core.translation.session_manager import TranslationSessionState
from core.translation.story_context_bundle import glossary_names_from_story_bundle
from handlers.translation.prompt_composer.glossary_mixin import SERIES_GLOSSARY_LEAD
from utils.logging_utils import log_debug
from utils.utils import resolve_target_language_prompt

from .instructions import append_engine_rules, batch_rules


# Layout values that are normally the same for every item of a chunk.
_SHARED_LAYOUT_KEYS = ('lines_per_window', 'warning_line_width_px', 'max_line_width_px')
# Reference languages sent per item unless the translation config says otherwise: None is every one.
DEFAULT_MAX_REFERENCE_LANGUAGES: Optional[int] = None


def _hoist_layout_defaults(items: List[Dict]) -> Dict:
    """Move what the items' layouts share into one dict and drop what says nothing.

    Every item used to repeat eight layout keys (~70 tokens), most of them equal
    across the chunk or at their trivial value. An item keeps ``line_count`` plus
    only what differs: non-empty ``blank_line_indices``, a true
    ``ends_with_newline``, a ``window_count`` above 1, and any shared key whose
    value is not the chunk's most common one.
    """
    defaults: Dict = {}
    for key in _SHARED_LAYOUT_KEYS:
        values = [item['layout'][key] for item in items if key in (item.get('layout') or {})]
        if values:
            defaults[key] = Counter(values).most_common(1)[0][0]
    for item in items:
        layout = item.get('layout') or {}
        slim = {'line_count': layout.get('line_count')}
        if layout.get('blank_line_indices'):
            slim['blank_line_indices'] = layout['blank_line_indices']
        if layout.get('ends_with_newline'):
            slim['ends_with_newline'] = True
        if isinstance(layout.get('window_count'), int) and layout['window_count'] > 1:
            slim['window_count'] = layout['window_count']
        for key in _SHARED_LAYOUT_KEYS:
            if key in layout and layout[key] != defaults.get(key):
                slim[key] = layout[key]
        item['layout'] = slim
    return defaults


def _dump_payload(payload: Dict) -> str:
    """The payload as JSON: sections indented, one string item per line.

    Fully indented, each item spread a handful of fields over a dozen lines, and
    the indentation alone was about a tenth of the request. One item per line is
    the same JSON and easier to scan in the prompt editor.
    """
    sections = []
    for key, value in payload.items():
        if key == 'strings_to_translate' and isinstance(value, list):
            rows = ",\n".join("    " + json.dumps(item, ensure_ascii=False) for item in value)
            body = "[\n" + rows + "\n  ]"
        else:
            # Newlines inside string values are escaped, so this only re-indents structure.
            body = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        sections.append(f"  {json.dumps(key)}: {body}")
    return "{\n" + ",\n".join(sections) + "\n}"


class BatchMixin:
    """Batch translation prompt composition."""

    def _max_reference_languages(self) -> Optional[int]:
        """How many reference languages go into each item (translation config; default every one, 0 none)."""
        config = getattr(self.mw, 'translation_config', None)
        value = config.get('max_reference_languages') if isinstance(config, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return DEFAULT_MAX_REFERENCE_LANGUAGES

    @staticmethod
    def _real_pair(item: Any, block_idx: Optional[int], temp_id_map: Optional[Dict]) -> Tuple[Any, Any]:
        """(block, string) of ``item`` in the data store.

        Selections, chapters and project-wide runs number their items 0..n and
        keep the real coordinates in ``temp_id_map``; a plain block run uses the
        string index as the id.
        """
        item_id = item.get('id', 0) if isinstance(item, dict) else 0
        if temp_id_map:
            for key in (item_id, str(item_id)):
                if key in temp_id_map:
                    real_block, real_string = temp_id_map[key]
                    return real_block, real_string
        return block_idx, item_id

    def _surrounding_rows(self, real_pairs: List[Tuple[Any, Any]], k: int = 3) -> str:
        """The ``k`` rows before and after the chunk, with their current translations.

        Grouped by real block: a chunk that spans two blocks gets the neighbours
        of each. The rows come from where the strings actually are, not from the
        chunk's own 0..n numbering.
        """
        data = getattr(getattr(self.mw, 'data_store', None), 'data', None)
        if not isinstance(data, list):
            return ""
        spans: Dict[int, List[int]] = {}
        for block, string in real_pairs:
            if not (isinstance(block, int) and isinstance(string, int)):
                continue
            if not (0 <= block < len(data)) or not isinstance(data[block], list):
                continue
            span = spans.setdefault(block, [string, string])
            span[0], span[1] = min(span[0], string), max(span[1], string)

        lines: List[str] = []
        for block, (first, last) in spans.items():
            rows = data[block]
            label = f" (block {self._get_block_label(block)})" if len(spans) > 1 else ""
            for title, indices in (
                ("BEFORE", range(max(0, first - k), min(first, len(rows)))),
                ("AFTER", range(last + 1, min(len(rows), last + k + 1))),
            ):
                if not indices:
                    continue
                lines.append(f"--- Dialogue {title} this chunk{label} ---")
                for i in indices:
                    original = str(rows[i]).replace('\n', ' ')
                    try:
                        translation, _ = self.data_processor.get_current_string_text(block, i)
                    except Exception as e:
                        log_debug(f"AIPromptComposer: no current text for ({block},{i}): {e}")
                        translation = ""
                    translation = translation.replace('\n', ' ') if isinstance(translation, str) else ""
                    if translation and translation != original:
                        lines.append(f'- [Row #{i}] (Original): "{original}" | (Translation): "{translation}"')
                    else:
                        lines.append(f'- [Row #{i}] (Original): "{original}"')
        return "\n".join(lines)

    def _item_text_for_ai(self, item: Any) -> Tuple[Any, str, str, Any]:
        """(id, editor text, text as the model sees it, forced-alias maps) for one item."""
        if isinstance(item, dict):
            item_id = item.get('id', 0)
            text = item.get('text', '')
        else:
            item_id = 0
            text = str(item)

        # Convert to editor representation to unify page/line breaks (e.g. \\n to \n)
        rules = self.mw.current_game_rules
        if rules and hasattr(rules, 'get_text_representation_for_editor'):
            converted = rules.get_text_representation_for_editor(text)
            if isinstance(converted, str):
                text = converted

        # Apply force-aliases
        from utils.force_alias import force_alias_wrapping, prepare_text_for_ai
        text_for_ai, force_maps = prepare_text_for_ai(
            text, getattr(self.mw, 'default_tag_mappings', {}), force_alias_wrapping(self.mw))
        return item_id, text, self._replace_runtime_names_for_ai(text_for_ai), force_maps

    def _plugin_translation_context(self, real_b_idx: Any, real_s_idx: Any) -> Dict:
        """What the plugin says about the string (window type, content role, ...); ``{}`` when it says nothing."""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules is not None and hasattr(rules, 'get_translation_context_for_string'):
            try:
                candidate = rules.get_translation_context_for_string(real_b_idx, real_s_idx)
                if isinstance(candidate, dict):
                    return candidate
            except Exception as e:
                log_debug(f"AIPromptComposer: translation context failed for ({real_b_idx},{real_s_idx}): {e}")
        return {}

    def _plugin_addressee(self, real_b_idx: Any, real_s_idx: Any, speaker: Optional[str]) -> str:
        """Who the line is spoken TO, as the plugin reports it; ``""`` when unknown."""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules is not None and hasattr(rules, 'get_addressee_for_string'):
            try:
                addressee = rules.get_addressee_for_string(real_b_idx, real_s_idx, speaker=speaker)
                if isinstance(addressee, str) and addressee:
                    return addressee
            except Exception as e:
                log_debug(f"AIPromptComposer: addressee failed for ({real_b_idx},{real_s_idx}): {e}")
        return ""

    def duplicate_context_key(self, item: Dict, block_idx: Optional[int], temp_id_map: Optional[Dict]) -> Tuple:
        """Everything except the text that decides how a string is translated.

        Two strings with the same text may share one translation only when this
        is equal too: who says it and to whom (gender, politeness), what the
        plugin and the user say about the row, and the window it must fit.
        """
        _, current_text, _, _ = self._item_text_for_ai(item)
        real_b_idx, real_s_idx = self._real_pair(item, block_idx, temp_id_map)
        translation_context = self._plugin_translation_context(real_b_idx, real_s_idx)
        speaker, _ = self._resolve_prompt_speaker(real_b_idx, real_s_idx, current_text, translation_context)
        manual = get_story_context_override(self.mw, real_b_idx, real_s_idx)
        return (
            str(speaker or ""),
            self._plugin_addressee(real_b_idx, real_s_idx, speaker),
            str(resolve_lines_per_window(self.mw, real_b_idx, real_s_idx)),
            json.dumps(translation_context, ensure_ascii=False, sort_keys=True, default=str),
            json.dumps(manual, ensure_ascii=False, sort_keys=True, default=str),
        )

    def _run_memory_rows(self, source_items: List[Any]) -> List[Dict[str, str]]:
        """Earlier translations of this run whose source matches one of ``source_items``, as the model sees text."""
        memory = getattr(self.main_handler, 'run_memory', None)
        if not isinstance(memory, RunMemory):
            return []
        own_texts = [item.get('text', '') if isinstance(item, dict) else str(item) for item in source_items]
        return [
            {
                'text': self._item_text_for_ai({'id': 0, 'text': row['text']})[2],
                'translation': self._item_text_for_ai({'id': 0, 'text': row['translation']})[2],
            }
            for row in memory.similar(own_texts)
        ]

    def build_placeholder_map(self, source_items: List[Dict]) -> Dict:
        """The forced-alias maps of ``source_items``, keyed by item id.

        Needed up front to restore tags in the replies. Cheap on purpose: no
        speaker, story or plugin lookups -- those happen per chunk in the worker.
        """
        placeholder_map: Dict = {}
        for item in source_items:
            item_id, _, _, force_maps = self._item_text_for_ai(item)
            if force_maps:
                placeholder_map[item_id] = force_maps
        return placeholder_map

    def compose_batch_request(
        self,
        system_prompt: str,
        source_items: List[Dict],
        all_source_items: List[Dict],
        *,
        block_idx: Optional[int],
        mode_description: str,
        session_state: Optional[TranslationSessionState] = None,
        temp_id_map: Optional[Dict] = None,
        **kwargs: Any,
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
            item_id, current_text, current_text_for_ai, force_maps = self._item_text_for_ai(item)
            if force_maps:
                placeholder_map[item_id] = force_maps

            # Keep the exact editor-visible line structure and whitespace. The
            # response validator enforces a one-to-one line layout.
            current_text_clean = current_text_for_ai.replace('\r\n', '\n').replace('\r', '\n')

            # Resolve real data-store coordinates for this item
            real_b_idx, real_s_idx = self._real_pair(item, block_idx, temp_id_map)

            rules = getattr(self.mw, 'current_game_rules', None)
            translation_context = self._plugin_translation_context(real_b_idx, real_s_idx)

            manual = get_story_context_override(self.mw, real_b_idx, real_s_idx)
            structured_story_context = (
                {}
                if manual.get("structure_id") == "story:none"
                else self._get_structured_story_context(real_b_idx, real_s_idx, compact=True)
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

            item_for_ai = {'id': item_id, 'text': current_text_clean}
            if speaker != "Unknown":
                item_for_ai['speaker'] = speaker
            item_for_ai['layout'] = self._layout_contract_for_string(
                current_text_clean, real_b_idx, real_s_idx
            )
            # Reference translations for context
            ref_langs = getattr(self.mw.data_store, 'reference_languages_data', {})
            ref_translations: Dict[str, str] = {}
            if isinstance(ref_langs, dict) and ref_langs and real_b_idx is not None and real_s_idx is not None:
                for lang_name, lang_dict in ref_langs.items():
                    if isinstance(lang_dict, dict):
                        t = lang_dict.get((real_b_idx, real_s_idx), "")
                        if isinstance(t, str) and t.strip():
                            ref_translations[str(lang_name)] = t.strip()
            elif real_b_idx is not None and real_s_idx is not None:
                raw_ref = getattr(self.mw.data_store, 'reference_data', {})
                if isinstance(raw_ref, dict):
                    single_ref = raw_ref.get((real_b_idx, real_s_idx), "")
                    if isinstance(single_ref, str) and single_ref.strip():
                        from core.reference_manager import ReferenceManager
                        game_rules = getattr(self.mw, 'current_game_rules', None)
                        ref_label = ReferenceManager.get_reference_language_label(game_rules)
                        ref_translations[ref_label] = single_ref.strip()

            ref_limit = self._max_reference_languages()
            if ref_translations and ref_limit != 0:
                from core.reference_manager import least_trusted_last
                item_for_ai['reference_translations'] = dict(least_trusted_last(ref_translations.items())[:ref_limit])

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
            addressee = self._plugin_addressee(real_b_idx, real_s_idx, speaker)
            if addressee:
                item_for_ai['addressee'] = self._translate_speaker(addressee)

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

        # Rows just before and after the chunk, by their real position in the data.
        surrounding_rows = ""
        if block_idx is not None and block_idx != -1:
            surrounding_rows = self._surrounding_rows(
                [self._real_pair(item, block_idx, temp_id_map) for item in source_items]
            )

        # 2. Extract scene context for the entire chunk if available
        room_name = None
        for item in source_items:
            item_text = item.get('text', '') if isinstance(item, dict) else str(item)
            real_b_idx, real_s_idx = self._real_pair(item, block_idx, temp_id_map)
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
            except Exception as exc:
                log_debug(f"batch_mixin.BatchMixin.compose_batch_request: ignored {exc!r}")

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

            if surrounding_rows:
                context_parts.append("\n" + surrounding_rows)
            scene_context = "\n".join(context_parts)

        if not scene_context:
            scene_context = surrounding_rows

        # 3. Glossary rows for this chunk: terms in its own text, plus the entries
        # of the speakers and story participants (added below by name). Terms of
        # later chunks, and every word of the story catalog, used to be matched
        # too -- rows the model could not use for these lines.
        # Matched on the text the model gets: a force alias turns a tag into a word ({escape:0:0000} -> "Link"),
        # and that word needs its glossary row, or the model spells the name after a reference language.
        from utils.force_alias import prepare_text_for_ai
        tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) or {}
        chunk_text = " ".join(
            prepare_text_for_ai(item.get('text', '') if isinstance(item, dict) else str(item), tag_mappings)[0]
            for item in source_items
        )

        relevant_glossary_entries = []
        if glossary_manager:
            relevant_glossary_entries = list(glossary_manager.get_relevant_terms(chunk_text))
            self._append_speaker_glossary_entries(relevant_glossary_entries, speaker_candidates)
        glossary_text = self._glossary_entries_to_text(relevant_glossary_entries)
        series_glossary_text = self._series_glossary_text(chunk_text)

        # 3b. Game-script dialogue flow outlines for the whole chunk: the actual
        # in-game conversation graphs (order, player choices, conditions) that
        # contain the lines being translated (plugin-provided)
        dialogue_flow = ""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules is not None and hasattr(rules, 'get_ai_flow_overview'):
            try:
                indices_by_block = {}
                for item in source_items:
                    rb, rs = self._real_pair(item, block_idx, temp_id_map)
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

        layout_defaults = _hoist_layout_defaults(items_with_context)
        json_payload_for_ai = {}
        if layout_defaults:
            json_payload_for_ai['layout_defaults'] = layout_defaults
        json_payload_for_ai['strings_to_translate'] = items_with_context
        memory_rows = self._run_memory_rows(source_items)
        if memory_rows:
            json_payload_for_ai['already_translated_in_this_run'] = memory_rows
        if story_context_catalog:
            json_payload_for_ai['story_context_catalog'] = story_context_catalog
        if scene_context:
            json_payload_for_ai['scene_context'] = scene_context
        if dialogue_flow:
            json_payload_for_ai['dialogue_flow'] = dialogue_flow
        if glossary_text:
            json_payload_for_ai['glossary'] = glossary_text
        if series_glossary_text:
            json_payload_for_ai['series_glossary'] = f"{SERIES_GLOSSARY_LEAD.capitalize()}.\n{series_glossary_text}"
        if tag_alias_legend:
            json_payload_for_ai['tag_alias_legend'] = tag_alias_legend

        # The rules for this kind of request are fixed text appended to the system
        # prompt (see instructions.py): identical for every chunk, so cacheable.
        target_lang = self._get_target_lang()
        final_system_prompt = resolve_target_language_prompt(
            append_engine_rules(system_prompt, batch_rules(system_prompt)), target_lang
        )
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
            'JSON DATA TO PROCESS:\n' + _dump_payload(json_payload_for_ai),
        ]
        user_content = '\n\n'.join(user_sections)
        user_content = self._replace_runtime_names_for_ai(user_content)

        log_debug(
            f'Composed batch request for AI. System prompt size: {len(combined_system)}, '
            f'User content size: {len(user_content)}'
        )
        return combined_system, user_content, placeholder_map
