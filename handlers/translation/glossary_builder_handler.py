# --- START OF FILE handlers/translation/glossary_builder_handler.py ---
# D:/git/dev/zeldamc/jsonreader/handlers/translation/glossary_builder_handler.py
import json
from typing import Dict, List, Optional
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QThread
from utils.logging_utils import log_debug
from core.translation.providers import get_provider_for_config, ProviderResponse
from utils.utils import ALL_TAGS_PATTERN
from components.ai_status_dialog import AIStatusDialog
from handlers.translation.ai_worker import AIWorker

class GlossaryBuilderHandler:
    def __init__(self, main_window):
        self.mw = main_window
        self.prompt_data = self._load_prompts()
        self._thread: Optional[QThread] = None
        self._worker: Optional[AIWorker] = None
        self._status_dialog: Optional[AIStatusDialog] = None
        self._glossary_manager = None

    def _load_prompts(self):
        try:
            with open('translation_prompts/glossary_builder_prompts.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_debug(f"Error loading glossary builder prompts: {e}")
            QMessageBox.critical(self.mw, "Error", "Could not load glossary builder prompts file.")
            return None

    def _split_text_into_chunks(self, text, chunk_size):
        # Simple chunking for now. Can be improved to respect sentence boundaries.
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    def _mask_tags_for_ai(self, text: str) -> str:
        return ALL_TAGS_PATTERN.sub(' ', text or '')

    def _clean_json_response(self, text: str) -> str:
        stripped_text = (text or '').strip()
        if stripped_text.startswith("```") and stripped_text.endswith("```"):
            lines = stripped_text.splitlines()
            if len(lines) > 1:
                content_lines = lines[1:-1]
                joined_content = "\n".join(content_lines).strip()
                if joined_content.startswith("json"):
                    joined_content = joined_content[4:].strip()
                return joined_content
            else:
                return ""
        return stripped_text

    def _resolve_translation_credentials(self, provider_name: str) -> dict:
        translation_config = getattr(self.mw, 'translation_config', {}) or {}
        providers_cfg = {}
        if isinstance(translation_config, dict):
            providers_cfg = translation_config.get('providers', {}) or {}

        provider_key_map = {
            'OpenAI': ['openai_chat', 'perplexity'],
            'Gemini': ['gemini'],
            'Ollama': ['ollama_chat']
        }

        base_url = ''
        for key in provider_key_map.get(provider_name, []):
            cfg = providers_cfg.get(key, {}) or {}

            if not base_url and cfg.get('base_url'):
                base_url = cfg.get('base_url')

            api_key = cfg.get('api_key')
            api_key_env = cfg.get('api_key_env')
            if api_key or api_key_env:
                credentials = {
                    'api_key': api_key or '',
                    'api_key_env': api_key_env or ''
                }
                if base_url:
                    credentials['base_url'] = base_url
                return credentials

        if provider_name == 'Ollama' and base_url:
            return {'base_url': base_url}

        return {}

    def build_glossary_for_block(self, block_id, category_name: Optional[str] = None):
        if not self.prompt_data:
            return

        # 1. Get all text from the block
        target_strings = []
        if self.mw.data_store.data and block_id < len(self.mw.data_store.data):
            block_data = self.mw.data_store.data[block_id]
            
            # Determine target indices
            target_indices = range(len(block_data))
            if category_name and hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                pm = self.mw.project_manager
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_id, block_id)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.get_all_categories_flat() if c.name == category_name), None)
                    if category:
                        target_indices = category.line_indices
                        log_debug(f"Building glossary only for category '{category_name}' ({len(target_indices)} lines)")
            
            target_strings = [str(block_data[i]) for i in target_indices if i < len(block_data)]
        
        full_text = "\n".join(target_strings)
        
        if not full_text.strip():
            QMessageBox.information(self.mw, "Info", "The selected block/category is empty. Nothing to process.")
            return

        # 2. Get AI settings
        glossary_ai_config = dict(getattr(self.mw, 'glossary_ai', {}) or {})
        chunk_size = glossary_ai_config.get('chunk_size', 8000)

        if glossary_ai_config.get('use_translation_api_key'):
            provider_name = glossary_ai_config.get('provider', '')
            resolved_credentials = self._resolve_translation_credentials(provider_name)

            if provider_name not in ('Ollama',) and not (resolved_credentials.get('api_key') or resolved_credentials.get('api_key_env')):
                QMessageBox.warning(
                    self.mw,
                    "AI Error",
                    "No API key is configured for the selected glossary provider in AI Translation settings."
                )
                return

            glossary_ai_config.update(resolved_credentials)

        # 3. Get provider
        try:
            provider = get_provider_for_config(glossary_ai_config)
        except Exception as e:
            log_debug(f"Failed to initialize AI provider: {e}")
            QMessageBox.critical(self.mw, "AI Error", f"Failed to initialize AI provider: {e}")
            return

        # 4. Split text into chunks
        raw_chunks = self._split_text_into_chunks(full_text, chunk_size)
        chunks = [self._mask_tags_for_ai(chunk) for chunk in raw_chunks]
        total_chunks = len(chunks)
        log_debug(f"Splitting text into {total_chunks} chunks of size ~{chunk_size}.")

        if not chunks:
            QMessageBox.information(self.mw, "Finished", "Nothing to send to the AI after preprocessing.")
            return

        self._start_async_glossary_task(block_id, provider, glossary_ai_config, chunks)

    def _start_async_glossary_task(self, block_id: int, provider, glossary_ai_config: dict, chunks: list[str]) -> None:
        status_bar = getattr(self.mw, 'statusBar', None)

        block_names = getattr(self.mw, 'block_names', {}) or {}
        block_label = block_names.get(str(block_id)) or f"Block {block_id + 1}"
        model_display = glossary_ai_config.get('model') or glossary_ai_config.get('provider') or 'Unknown model'

        self._cleanup_worker()

        self._status_dialog = AIStatusDialog(self.mw)
        self._status_dialog.start(f"AI Glossary Build ({block_label})", is_chunked=True, model_name=str(model_display))
        QApplication.processEvents()

        prompt_composer = None
        translation_handler = getattr(self.mw, 'translation_handler', None)
        if translation_handler:
            prompt_composer = translation_handler.prompt_composer
            self._glossary_manager = translation_handler.glossary_handler.glossary_manager
        else:
            self._glossary_manager = getattr(self.mw, 'glossary_manager', None)

        task_details = {
            'type': 'build_glossary',
            'system_prompt': self.prompt_data['system_prompt'],
            'user_prompt_template': self.prompt_data['user_prompt_template'],
            'chunks': chunks,
            'dialog_steps': self._status_dialog.steps,
            'block_id': block_id
        }

        self._worker = AIWorker(provider, prompt_composer, task_details)
        self._thread = QThread(self.mw)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        self._worker.translation_cancelled.connect(lambda: self._on_glossary_cancelled(status_bar))
        self._worker.step_updated.connect(self._status_dialog.update_step)
        self._worker.total_chunks_calculated.connect(self._status_dialog.setup_progress_bar)
        self._worker.progress_updated.connect(self._status_dialog.update_progress)
        self._worker.success.connect(lambda response, details: self._on_glossary_success(response, details, status_bar))
        self._worker.error.connect(lambda message, details: self._on_glossary_error(message, status_bar))
        self._worker.finished.connect(self._status_dialog.finish)
        self._worker.finished.connect(lambda: setattr(self, '_worker', None))

        if status_bar:
            total_chunks = len(chunks)
            self._worker.progress_updated.connect(
                lambda completed, total=total_chunks: status_bar.showMessage(
                    f"Processing chunk {min(completed, total)}/{total}...", 0
                )
            )

        self._status_dialog.cancelled.connect(self._worker.cancel)

        self._thread.start()
        QApplication.processEvents()

    def _on_glossary_success(self, response: ProviderResponse, task_details: dict, status_bar) -> None:
        aggregated_terms: List[Dict] = []
        if isinstance(response.raw_payload, list):
            aggregated_terms = response.raw_payload
        else:
            try:
                aggregated_terms = json.loads(response.text or '[]')
            except Exception:
                aggregated_terms = []

        manager = self._glossary_manager
        if not manager:
            QMessageBox.warning(self.mw, "AI Error", "Glossary manager is not available.")
            self._cleanup_worker()
            return

        if not aggregated_terms:
            QMessageBox.information(self.mw, "Finished", "The AI did not find any new terms to add to the glossary.")
            if status_bar:
                status_bar.showMessage("Glossary generation complete.", 5000)
            self._cleanup_worker()
            return

        existing_terms = {manager.normalize_term(entry.original) for entry in manager.get_entries()}
        seen_in_batch = set()
        added_total = 0
        added_new = 0
        added_existing = 0
        skipped_duplicates = 0

        for item in aggregated_terms:
            if not isinstance(item, dict):
                continue
            term = str(item.get('term') or '').strip()
            translation = str(item.get('translation') or '').strip()
            notes = str(item.get('notes') or item.get('description') or '').strip()
            if not term or not translation:
                continue

            normalized = manager.normalize_term(term)
            if normalized in seen_in_batch:
                skipped_duplicates += 1
                continue

            seen_in_batch.add(normalized)
            entry = manager.add_entry(term, translation, notes)
            if not entry:
                continue

            added_total += 1
            if normalized in existing_terms:
                added_existing += 1
            else:
                added_new += 1
                existing_terms.add(normalized)

        manager.save_to_disk()

        translation_handler = getattr(self.mw, 'translation_handler', None)
        if translation_handler:
            translation_handler._cached_glossary = manager.get_raw_text()
            translation_handler.glossary_handler._update_glossary_highlighting()
            translation_handler.reset_translation_session()

        summary_parts = [
            f"Додано {added_total} термінів",
            f"нових: {added_new}",
            f"оновлено: {added_existing}",
        ]
        if skipped_duplicates:
            summary_parts.append(f"пропущено дублікатів: {skipped_duplicates}")
        summary_text = ", ".join(summary_parts)

        log_debug(
            f"Glossary build stats: added={added_total} (new={added_new}, existing={added_existing}), "
            f"skipped duplicates={skipped_duplicates}"
        )

        QMessageBox.information(self.mw, "Success", summary_text)
        if status_bar:
            status_bar.showMessage(summary_text, 5000)
        self._cleanup_worker()

    def _on_glossary_error(self, message: str, status_bar) -> None:
        QMessageBox.warning(self.mw, "AI Error", message)
        if status_bar:
            status_bar.showMessage("Glossary generation failed.", 5000)
        self._cleanup_worker()

    def _on_glossary_cancelled(self, status_bar) -> None:
        QMessageBox.information(self.mw, "Cancelled", "Glossary generation was cancelled.")
        if status_bar:
            status_bar.showMessage("Glossary generation cancelled.", 5000)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        if self._worker:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self._worker = None
        
        if self._status_dialog:
            try:
                self._status_dialog.finish()
            except Exception:
                pass
        self._status_dialog = None

        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2000)
            self._thread = None
        self._glossary_manager = None
