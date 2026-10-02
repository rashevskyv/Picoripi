import json
from typing import Any, Dict, List
from core.translation.providers import BaseTranslationProvider, ProviderResponse, TranslationProviderError
from core.translation.ai_error_handler import handle_ai_error
from core.translation.chunk_result import verify_chunk_ids
from core.translation.transport import ErrorKind
from core.glossary_build.parallel import MAX_CONSECUTIVE_FAILURES, run_pool
from core.translation.layout_contract import (
    editor_text_for_layout,
    resolve_lines_per_window,
    validate_translation_layout,
)
from utils.logging_utils import log_debug


def _is_cancel(exc: Exception) -> bool:
    """Whether ``exc`` is the provider reporting that the user cancelled the request."""
    return getattr(exc, 'kind', None) is ErrorKind.CANCELLED


class AIWorkerRunMixin:
    """Main AIWorker.run() implementation."""

    def run(self):
        """Run."""
        from components.ai_status_dialog import AIStatusDialog
        log_debug(f"AIWorker: Thread started for task type '{self.task_details.get('type')}'.")
        
        try:
            task_type = self.task_details.get('type')
            messages: List[Dict[str, str]] = []
            settings_override = {}
            if self.task_details.get('web_search_enabled'):
                settings_override['web_search_enabled'] = True
            extra_override = self.task_details.get('settings_override')
            if isinstance(extra_override, dict):
                settings_override.update(extra_override)

            if task_type == 'chat_message_stream':
                state = self.task_details.get('session_state')
                user_message = {"role": "user", "content": self.task_details.get('session_user_message')}
                messages, session_payload = state.prepare_request(user_message)

                self._last_messages = messages
                self._log_ai_traffic(messages)

                full_response_text = ""
                for chunk in self.provider.translate_stream(messages, session=session_payload, settings_override=settings_override):
                    if self.is_cancelled:
                        self.translation_cancelled.emit()
                        return
                    self.chunk_received.emit(self.task_details, chunk)
                    full_response_text += chunk
                
                self._log_ai_traffic(messages, response_text=full_response_text)
                final_response = ProviderResponse(text=full_response_text)
                self.success.emit(final_response, self.task_details)
                return
            
            elif task_type == 'chat_message':
                state = self.task_details.get('session_state')
                user_message = {"role": "user", "content": self.task_details.get('session_user_message')}
                messages, session_payload = state.prepare_request(user_message)
                
                self._last_messages = messages
                self._log_ai_traffic(messages)
                response = self.provider.translate(messages, session=session_payload, settings_override=settings_override)
                self._log_ai_traffic(messages, response_text=response.text)
                self.success.emit(response, self.task_details)
                return

            if task_type == 'build_glossary':
                system_prompt = self.task_details.get('system_prompt', '')
                user_template = self.task_details.get('user_prompt_template', '{text_chunk}')
                block_data = self.task_details.get('block_data', [])
                target_indices = self.task_details.get('target_indices', [])
                string_contexts = self.task_details.get('string_contexts', {}) or {}
                raw_chunk_size = self.task_details.get('chunk_size', 8000)
                dialog_steps = self.task_details.get('dialog_steps', [])

                # Normalize chunk_size
                try:
                    chunk_size = int(raw_chunk_size)
                    if chunk_size <= 0:
                        chunk_size = 8000
                except (ValueError, TypeError):
                    chunk_size = 8000
                chunk_size = max(1000, min(32000, chunk_size))

                # 1. Background text aggregation
                target_strings = []
                for string_idx in target_indices:
                    if string_idx >= len(block_data):
                        continue
                    text = str(block_data[string_idx])
                    context = string_contexts.get(string_idx) or string_contexts.get(str(string_idx))
                    if isinstance(context, dict) and context:
                        metadata = []
                        if context.get('window_type'):
                            metadata.append(f"Window Type: {context['window_type']}")
                        if context.get('content_role'):
                            metadata.append(f"Content Role: {context['content_role']}")
                        if context.get('role_instruction'):
                            metadata.append(f"Role Instruction: {context['role_instruction']}")
                        if context.get('glossary_section'):
                            metadata.append(f"Glossary Section: {context['glossary_section']}")
                        if context.get('force_glossary'):
                            metadata.append("Required Glossary Entry: yes")
                        target_strings.append(
                            "=== GAME STRING ===\n" + "\n".join(metadata) + f"\nText:\n{text}\n=== END GAME STRING ==="
                        )
                    else:
                        target_strings.append(text)
                full_text = "\n".join(target_strings)

                # 2. Background tag masking first to prevent tag leakage on chunk boundaries
                from core.tag_utils import mask_all_tags_including_visual_markers
                masked_text = mask_all_tags_including_visual_markers(full_text)

                # 3. Background chunking. When semantic records are present, keep
                # their metadata and text together whenever one record fits.
                if string_contexts:
                    masked_records = [mask_all_tags_including_visual_markers(record) for record in target_strings]
                    chunks = []
                    current_chunk = ""
                    for record in masked_records:
                        separator = "\n" if current_chunk else ""
                        if current_chunk and len(current_chunk) + len(separator) + len(record) > chunk_size:
                            chunks.append(current_chunk)
                            current_chunk = ""
                            separator = ""
                        if len(record) > chunk_size:
                            if current_chunk:
                                chunks.append(current_chunk)
                                current_chunk = ""
                            chunks.extend(record[i:i+chunk_size] for i in range(0, len(record), chunk_size))
                        else:
                            current_chunk += separator + record
                    if current_chunk:
                        chunks.append(current_chunk)
                else:
                    chunks = [masked_text[i:i+chunk_size] for i in range(0, len(masked_text), chunk_size)]
                
                total_chunks = len(chunks)
                log_debug(f"AIWorker: Splitting text into {total_chunks} chunks of size ~{chunk_size} in background.")

                aggregated_terms: List[Dict[str, Any]] = []

                self.total_chunks_calculated.emit(total_chunks, 0)
                if dialog_steps:
                    self.step_updated.emit(0, dialog_steps[0], AIStatusDialog.STATUS_IN_PROGRESS)

                if not chunks:
                    aggregated_payload = ProviderResponse(text="[]", raw_payload=[])
                    if dialog_steps:
                        self.step_updated.emit(1, dialog_steps[1], AIStatusDialog.STATUS_DONE)
                        self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_DONE)
                        self.step_updated.emit(3, dialog_steps[3], AIStatusDialog.STATUS_DONE)
                    self.success.emit(aggregated_payload, self.task_details)
                    return

                for idx, chunk in enumerate(chunks):
                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary build cancelled before processing chunk.")
                        self.translation_cancelled.emit()
                        return

                    self.progress_updated.emit(idx + 1)
                    step_text = f"Processing chunk {idx + 1}/{total_chunks}"
                    self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)

                    user_prompt = user_template.format(text_chunk=chunk)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]

                    response = None
                    try:
                        self._last_messages = messages
                        self._log_ai_traffic(messages)
                        response = self.provider.translate(messages, session=None, settings_override={"think": 1})
                        self._log_ai_traffic(messages, response_text=response.text)
                        # ParseError when the chunk's reply is not a term list: a
                        # dropped chunk must stop the build, not shrink it quietly.
                        aggregated_terms.extend(json.loads(self._clean_json_response(response.text, "array")))
                    except (TranslationProviderError, json.JSONDecodeError) as exc:
                        self._log_ai_traffic(messages, error=exc)
                        if _is_cancel(exc):
                            self.translation_cancelled.emit()
                        elif not self.is_cancelled:
                            resp_t = response.text if response is not None else ""
                            err_msg, updated_details = handle_ai_error(exc, self.task_details, resp_t, f"Glossary chunk {idx + 1}")
                            self.error.emit(err_msg, updated_details)
                        return

                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary build cancelled after chunk response.")
                        self.translation_cancelled.emit()
                        return

                aggregated_payload = ProviderResponse(
                    text=json.dumps(aggregated_terms, ensure_ascii=False),
                    raw_payload=aggregated_terms
                )
                if dialog_steps:
                    self.step_updated.emit(1, dialog_steps[1], AIStatusDialog.STATUS_DONE)
                    self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_DONE)
                    self.step_updated.emit(3, dialog_steps[3], AIStatusDialog.STATUS_DONE)
                self.success.emit(aggregated_payload, self.task_details)
                return

            if task_type == 'translate_block_chunked':
                source_items = self.task_details['source_items']
                block_idx = self.task_details.get('block_idx')
                
                client = self.prompt_composer._get_mempalace_client()
                wing_name = self.prompt_composer._get_wing_name()
                block_label = self.prompt_composer._get_block_label(block_idx)
                
                # Classify items into scene-based and scene-less
                scene_items_by_room = {}
                scene_less_items = []
                rooms_order = []
                
                for item in source_items:
                    if isinstance(item, dict):
                        item_id = item.get('id', 0)
                        item_text = item.get('text', '')
                    else:
                        item_id = 0
                        item_text = str(item)
                    
                    room = None
                    if client:
                        bmg_id = f"{block_label}_Str_{item_id}"
                        cached_ctx = client.get_cached_context(bmg_id, item_text)
                        if cached_ctx:
                            room = cached_ctx.get("room")
                            
                    if room:
                        if room not in scene_items_by_room:
                            scene_items_by_room[room] = []
                            rooms_order.append(room)
                        scene_items_by_room[room].append(item)
                    else:
                        scene_less_items.append(item)
                
                # Build chunks: first scenes in chronological order, then scene-less ones at the end
                chunks = []
                
                for room in rooms_order:
                    room_items = scene_items_by_room[room]
                    # Split room items into sub-chunks of max 12 items
                    for k in range(0, len(room_items), 12):
                        chunks.append(room_items[k:k+12])
                        
                for k in range(0, len(scene_less_items), 12):
                    chunks.append(scene_less_items[k:k+12])

                # Save calculated chunks directly inside task_details for reliable sequential parsing in callbacks
                self.task_details['calculated_chunks'] = chunks

                chunks_to_skip = self.task_details.get('chunks_to_skip', set())
                self.total_chunks_calculated.emit(len(chunks), len(chunks_to_skip))
                session_state = self.task_details.get('session_state')
                provider_override = self.task_details.get('provider_settings_override', {})
                provider_override.setdefault('think', 1)
                # A chunk reply is one JSON object; ask for JSON mode where it exists.
                provider_override.setdefault('json', True)
                workers = int(self.task_details.get('workers', 1) or 1)
                if workers > 1 and isinstance(self.provider, BaseTranslationProvider):
                    workers = self.provider.clamp_workers(workers)
                attempt = self.task_details.get('attempt', 1)

                def _build_chunk_request(i: int):
                    chunk = chunks[i]
                    composer_args_for_chunk = self.task_details['composer_args'].copy()
                    composer_args_for_chunk['source_items'] = chunk
                    composer_args_for_chunk['all_source_items'] = source_items
                    system, user, _ = self.prompt_composer.compose_batch_request(**composer_args_for_chunk)

                    custom_header = self.task_details.get('custom_user_header')
                    if custom_header:
                        label = (self.task_details.get('custom_user_label') or 'JSON DATA TO PROCESS:').strip()
                        _, sep_marker, json_section = user.partition('JSON DATA TO PROCESS:')
                        if sep_marker:
                            rebuilt = custom_header.rstrip()
                            if rebuilt:
                                rebuilt += '\n\n' + label
                            else:
                                rebuilt = label
                            if not json_section.startswith('\n'):
                                rebuilt += '\n'
                            rebuilt += json_section
                            user = rebuilt
                    return system, user

                def _validate_chunk_result(i: int, chunk: list, cleaned_text: str):
                    parsed_response = json.loads(cleaned_text)
                    translated_items = parsed_response.get('translated_strings', [])

                    if len(translated_items) != len(chunk):
                        raise ValueError(f"Line count mismatch in chunk {i+1}. Expected {len(chunk)}, got {len(translated_items)}.")
                    verify_chunk_ids(translated_items, chunk)

                    rules = getattr(self.mw, 'current_game_rules', None) if self.mw else None
                    for result_item, source_item in zip(translated_items, chunk):
                        if not isinstance(result_item, dict):
                            raise ValueError("A translated item is not a JSON object")
                        translated_value = next(
                            (
                                str(result_item[key])
                                for key in ("translation", "text", "translated_text")
                                if key in result_item and result_item[key] is not None
                            ),
                            "",
                        )
                        source_value = (
                            source_item.get('text', '')
                            if isinstance(source_item, dict) else str(source_item)
                        )
                        source_id = (
                            source_item.get('id')
                            if isinstance(source_item, dict) else None
                        )
                        real_block_idx = self.task_details.get('block_idx')
                        real_string_idx = source_id
                        temp_id_map = self.task_details.get('temp_id_map') or {}
                        if source_id in temp_id_map:
                            real_block_idx, real_string_idx = temp_id_map[source_id]
                        elif str(source_id) in temp_id_map:
                            real_block_idx, real_string_idx = temp_id_map[str(source_id)]
                        validate_translation_layout(
                            editor_text_for_layout(source_value, rules),
                            translated_value,
                            resolve_lines_per_window(
                                self.mw,
                                real_block_idx,
                                real_string_idx,
                            ),
                            allow_line_expansion=True,
                        )
                    return parsed_response

                def _maybe_run_editor_review(chunk_i: int, chunk_items: list, cleaned_draft: str) -> str:
                    if not self.task_details.get('enable_editor_review', False):
                        return cleaned_draft
                    editor_prompt = self.task_details.get('editor_system_prompt')
                    if not editor_prompt or self.is_cancelled:
                        return cleaned_draft
                    try:
                        drafts = json.loads(cleaned_draft).get('translated_strings', [])
                        # Source and draft side by side, nothing else: the editor
                        # polishes wording, it does not need the layout or context blobs.
                        editor_input = {
                            "task": "Review, polish, and ensure terminology consistency for the draft translation.",
                            "strings": [
                                {
                                    "id": source.get('id') if isinstance(source, dict) else index,
                                    "text": source.get('text', '') if isinstance(source, dict) else str(source),
                                    "translation": draft.get('translation', '') if isinstance(draft, dict) else str(draft),
                                }
                                for index, (source, draft) in enumerate(zip(chunk_items, drafts))
                            ],
                            "output": 'Return {"translated_strings": [{"id": ..., "translation": "..."}]} with one '
                                      'object per input string, in the same order.',
                        }
                        review_messages = [
                            {"role": "system", "content": editor_prompt},
                            {"role": "user", "content": json.dumps(editor_input, ensure_ascii=False, indent=2)}
                        ]
                        review_resp = self.provider.translate(review_messages, session=None, settings_override=provider_override)
                        if self.is_cancelled or not review_resp or not review_resp.text:
                            return cleaned_draft
                        polished_cleaned = self._clean_json_response(review_resp.text)
                        _validate_chunk_result(chunk_i, chunk_items, polished_cleaned)
                        return polished_cleaned
                    except Exception as e:
                        log_debug(f"AIWorker: Editor review for chunk {chunk_i} skipped/failed, keeping draft: {e}")
                        return cleaned_draft

                # Parallel path when workers > 1 and stateless
                if workers > 1 and not session_state:
                    indices = [idx for idx in range(len(chunks)) if idx not in chunks_to_skip]
                    chunk_errors: Dict[int, Exception] = {}
                    fatal_errors: List[Exception] = []

                    def _worker_call(idx: int) -> str:
                        try:
                            return _translate_chunk(idx)
                        except Exception as exc:
                            chunk_errors[idx] = exc
                            # A wrong key, model or URL fails every chunk the same
                            # way: stop handing out the rest.
                            if getattr(exc, 'kind', None) in (ErrorKind.AUTH, ErrorKind.BAD_REQUEST):
                                fatal_errors.append(exc)
                            raise

                    def _translate_chunk(idx: int) -> str:
                        chunk = chunks[idx]
                        system, user = _build_chunk_request(idx)
                        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                        self._add_retry_reminder(messages)
                        self._last_messages = messages
                        self._log_ai_traffic(messages, chunk=idx)
                        try:
                            response = self.provider.translate(messages, session=None, settings_override=provider_override)
                        except Exception as exc:
                            self._log_ai_traffic(messages, error=exc, chunk=idx)
                            raise
                        self._log_ai_traffic(messages, response_text=response.text, chunk=idx)
                        cleaned = self._clean_json_response(response.text)
                        _validate_chunk_result(idx, chunk, cleaned)
                        return _maybe_run_editor_review(idx, chunk, cleaned)

                    completed_count = len(chunks_to_skip)

                    def _chunk_done(idx: int, cleaned_text: str) -> None:
                        # Runs on this worker's thread, as each chunk finishes.
                        nonlocal completed_count
                        if self.is_cancelled:
                            return
                        completed_count += 1
                        self.progress_updated.emit(completed_count)
                        self.step_updated.emit(1, f"Translating chunk {completed_count}/{len(chunks)} (Attempt {attempt})", AIStatusDialog.STATUS_IN_PROGRESS)
                        self.chunk_translated.emit(idx, cleaned_text, self.task_details.copy())

                    # A rolling window instead of submitting everything up front:
                    # after a stop or a cancel no further request is sent, and the
                    # chunks that did finish are already applied.
                    outcome = run_pool(
                        indices,
                        _worker_call,
                        workers=min(workers, max(1, len(indices))),
                        on_result=_chunk_done,
                        is_cancelled=lambda: self.is_cancelled or bool(fatal_errors),
                        max_consecutive_failures=MAX_CONSECUTIVE_FAILURES,
                    )
                    if self.is_cancelled:
                        self.translation_cancelled.emit()
                        return
                    if chunk_errors:
                        failed = sorted(chunk_errors)
                        first_error = (fatal_errors or [outcome.stop_error or chunk_errors[failed[0]]])[0]
                        self._log_ai_traffic([{"role": "user", "content": f"Chunks {failed}"}], error=first_error)
                        resp_t = getattr(first_error, 'raw_text', '') or ''
                        err_msg, updated_details = handle_ai_error(first_error, self.task_details, resp_t, f"chunks {failed}")
                        updated_details['failed_chunks'] = failed
                        numbers = ", ".join(str(i + 1) for i in failed)
                        stopped = "; the run was stopped" if (fatal_errors or outcome.stop_error) else ""
                        self.error.emit(
                            f"{len(failed)} of {len(chunks)} chunks failed (chunk {numbers}){stopped}; "
                            f"the finished chunks are kept. {err_msg}",
                            updated_details,
                        )
                    return

                # Sequential path when workers == 1 or session_state is present
                for i, chunk in enumerate(chunks):
                    if i in chunks_to_skip:
                        log_debug(f"AIWorker: Skipping already translated chunk {i + 1}/{len(chunks)}.")
                        continue

                    if self.is_cancelled:
                        log_debug("AIWorker: Translation cancelled by user before processing chunk.")
                        self.translation_cancelled.emit()
                        return

                    system, user = _build_chunk_request(i)

                    session_payload = None
                    if session_state:
                        user_message = {"role": "user", "content": user}
                        messages, session_payload = session_state.prepare_request(user_message)
                    else:
                        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

                    # Determine line and chapter details for UI progress dialog
                    detail_parts = []
                    if chunk:
                        first_item = chunk[0]
                        item_id = first_item.get('id', 0) if isinstance(first_item, dict) else 0
                            
                        bmg_id = f"{block_label}_Str_{item_id}"
                        script_line = None
                        chapter_num = None
                        chapter_title = None
                        
                        if client:
                            try:
                                mapping = client.get_script_mapping(wing_name, bmg_id)
                                if mapping:
                                    script_line = mapping.get("script_line")
                                    chapter_num = mapping.get("chapter_num")
                                    chapter_title = mapping.get("chapter_title")
                            except Exception as e:
                                log_debug(f"AIWorker: Failed to get script mapping: {e}")
                                
                        if chapter_title or chapter_num is not None:
                            ch_str = f"Chapter {chapter_num}" if chapter_num is not None else "Chapter"
                            if chapter_title:
                                ch_str += f": {chapter_title}"
                            detail_parts.append(ch_str)
                            
                        file_line_str = f"File: {block_label}.bmg | Line: {item_id}"
                        if script_line is not None:
                            file_line_str += f" (Script Line: {script_line})"
                        detail_parts.append(file_line_str)
                        
                    detail_text = " | ".join(detail_parts) if detail_parts else f"File: {block_label}.bmg"
                    self.detail_updated.emit(detail_text)

                    self.progress_updated.emit(i + 1)
                    self.step_updated.emit(1, f"Translating chunk {i + 1}/{len(chunks)} (Attempt {attempt})", AIStatusDialog.STATUS_IN_PROGRESS)

                    try:
                        self._add_retry_reminder(messages)
                        self._last_messages = messages
                        self._log_ai_traffic(messages, chunk=i)
                        response = self.provider.translate(messages, session=session_payload, settings_override=provider_override)

                        if self.is_cancelled:
                            log_debug("AIWorker: Translation cancelled during network request. Discarding response.")
                            break

                        self._log_ai_traffic(messages, response_text=response.text, chunk=i)
                        cleaned_text = self._clean_json_response(response.text)
                        _validate_chunk_result(i, chunk, cleaned_text)
                        cleaned_text = _maybe_run_editor_review(i, chunk, cleaned_text)

                        if session_state and not session_state.bootstrapped:
                            log_debug(f"AIWorker: First chunk (index {i}) of block translation successful. Marking session as bootstrapped.")
                            session_state.bootstrapped = True

                        task_details_for_chunk = self.task_details.copy()
                        if session_state:
                            task_details_for_chunk['session_state'] = session_state
                            task_details_for_chunk['session_user_message'] = user
                        self.chunk_translated.emit(i, cleaned_text, task_details_for_chunk)

                    except (TranslationProviderError, json.JSONDecodeError, ValueError) as e:
                        self._log_ai_traffic(messages, error=e, chunk=i)
                        if _is_cancel(e):
                            self.translation_cancelled.emit()
                            return
                        resp_t = response.text if 'response' in locals() else ""
                        err_msg, updated_details = handle_ai_error(e, self.task_details, resp_t, f"chunk {i}")
                        self.error.emit(err_msg, updated_details)
                        return

                    if self.is_cancelled:
                        self.translation_cancelled.emit()
                        return

                return

            if task_type == 'glossary_occurrence_batch_update':
                composer = self.task_details.get('composer_args', {})
                system_prompt = composer.get('system_prompt', '')
                term = composer.get('term', '')
                old_translation = composer.get('old_translation', '')
                new_translation = composer.get('new_translation', '')
                batch_items = composer.get('batch_items', [])

                # Split batch_items into chunks of max 12 items
                chunks = [batch_items[k:k+12] for k in range(0, len(batch_items), 12)]
                total_chunks = len(chunks)

                self.total_chunks_calculated.emit(total_chunks, 0)
                aggregated_occurrences = []

                provider_settings_override = self.task_details.get('provider_settings_override', {})
                provider_settings_override.update(settings_override)
                provider_settings_override.setdefault('think', 1)

                for i, chunk in enumerate(chunks):
                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary occurrence batch update cancelled before processing chunk.")
                        self.translation_cancelled.emit()
                        return

                    self.progress_updated.emit(i)
                    attempt = self.task_details.get('attempt', 1)
                    step_text = f"Updating chunk {i + 1}/{total_chunks} (Attempt {attempt})"
                    self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)

                    # Compose the prompt for this specific chunk
                    system, user = self.prompt_composer.compose_glossary_occurrence_batch_request(
                        system_prompt=system_prompt,
                        term=term,
                        old_translation=old_translation,
                        new_translation=new_translation,
                        batch_items=chunk,
                        session_state=self.task_details.get('session_state')
                    )

                    custom_header = self.task_details.get('custom_user_header')
                    if custom_header:
                        label = (self.task_details.get('custom_user_label') or 'JSON DATA TO UPDATE:').strip()
                        _, sep_marker, json_section = user.partition('JSON DATA TO UPDATE:')
                        if sep_marker:
                            rebuilt = custom_header.rstrip()
                            if rebuilt:
                                rebuilt += '\n\n' + label
                            else:
                                rebuilt = label
                            if not json_section.startswith('\n'):
                                rebuilt += '\n'
                            rebuilt += json_section
                            user = rebuilt

                    session_payload = None
                    session_state = self.task_details.get('session_state')
                    if session_state:
                        user_message = {"role": "user", "content": user}
                        messages, session_payload = session_state.prepare_request(user_message)
                    else:
                        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

                    self._add_retry_reminder(messages)

                    self._last_messages = messages
                    self._log_ai_traffic(messages)
                    response = self.provider.translate(messages, session=session_payload, settings_override=provider_settings_override)

                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary occurrence batch update cancelled during network request.")
                        self.translation_cancelled.emit()
                        return

                    self._log_ai_traffic(messages, response_text=response.text)
                    cleaned_text = self._clean_json_response(response.text)
                    payload = json.loads(cleaned_text)

                    updates = None
                    if isinstance(payload, dict):
                        updates = payload.get("occurrences") or payload.get("translations") or payload.get("updated_translations")

                    if not isinstance(updates, list):
                        raise ValueError(f"AI response missing 'occurrences' array in chunk {i + 1}.")

                    aggregated_occurrences.extend(updates)

                # Done with all chunks! Emit success.
                self.progress_updated.emit(total_chunks)
                aggregated_payload = ProviderResponse(
                    text=json.dumps({"occurrences": aggregated_occurrences}, ensure_ascii=False),
                    raw_payload={"occurrences": aggregated_occurrences}
                )
                self.success.emit(aggregated_payload, self.task_details)
                return

            dialog_steps = self.task_details['dialog_steps']
            self.step_updated.emit(0, dialog_steps[0], AIStatusDialog.STATUS_IN_PROGRESS)
            log_debug("AIWorker: Starting non-chunked task type='%s', block=%s, string=%s" % (task_type, self.task_details.get('block_idx'), self.task_details.get('string_idx')))
            
            precomposed = self.task_details.get('precomposed_prompt')
            session_info = self.task_details.get('session') if isinstance(self.task_details.get('session'), dict) else None
            session_payload = None

            if precomposed and not session_info:
                messages = precomposed
            elif task_type == 'translate_preview':
                system, user, _ = self.prompt_composer.compose_batch_request(**self.task_details['composer_args'])
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type in ['translate_single', 'generate_variation', 'glossary_notes_variation']:
                system, user = self.prompt_composer.compose_variation_request(**self.task_details['composer_args'])
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type == 'fill_glossary':
                system, user = self.prompt_composer.compose_glossary_request(**self.task_details['composer_args'])
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            elif task_type == 'glossary_occurrence_update':
                system, user = self.prompt_composer.compose_glossary_occurrence_update_request(**self.task_details['composer_args'])
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            elif task_type == 'glossary_occurrence_batch_update':
                composer = self.task_details.get('composer_args', {})
                system = composer.get('system_prompt', '')
                user = composer.get('user_prompt', '')
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            else:
                messages = [{"role": "system", "content": self.task_details.get('composer_args', {}).get('system_prompt', '')}]

            step_text = f"Sending to AI... (Attempt {self.task_details.get('attempt', 1)}/{self.task_details.get('max_retries', 1)})"
            self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)
            
            self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_IN_PROGRESS)
            
            provider_settings_override = self.task_details.get('provider_settings_override', {})
            provider_settings_override.update(settings_override)
            if task_type in ['translate_single', 'translate_preview']:
                # These replies are one JSON object; ask for JSON mode where it exists.
                provider_settings_override.setdefault('json', True)
            if task_type in ['translate_single', 'generate_variation', 'glossary_notes_variation']:
                provider_settings_override.setdefault('think', 2)
            elif task_type == 'fill_glossary':
                provider_settings_override.setdefault('think', 4)
            elif task_type == 'translate_preview':
                provider_settings_override.setdefault('think', 1)

            attempt = self.task_details.get('attempt', 1)
            self._add_retry_reminder(messages)

            self._last_messages = messages
            self._log_ai_traffic(messages)
            response = self.provider.translate(messages, session=session_payload, settings_override=provider_settings_override)

            if self.is_cancelled:
                log_debug("AIWorker: Operation cancelled after network request. Discarding response.")
                self.translation_cancelled.emit()
                return
            
            self._log_ai_traffic(messages, response_text=response.text)
            log_debug("AIWorker: Request successful, emitting success signal for task_type='%s'" % task_type)
            self.success.emit(response, self.task_details)


        except (TranslationProviderError, ValueError, Exception) as e:
            if _is_cancel(e):
                self.translation_cancelled.emit()
            elif not self.is_cancelled:
                self._log_ai_traffic(getattr(self, '_last_messages', None) or [], error=e)
                resp_t = response.text if 'response' in locals() and response is not None else None
                err_msg, updated_details = handle_ai_error(e, self.task_details, resp_t, "worker thread exception")
                self.error.emit(err_msg, updated_details)
        finally:
            self._report_traffic_summary()
            log_debug("AIWorker: Task finished, emitting 'finished' signal.")
            self.finished.emit()
