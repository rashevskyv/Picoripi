"""TranslationHandler composition."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QTimer, QThread

from handlers.base_handler import BaseHandler
from core.translation.session_manager import TranslationSessionManager
from handlers.translation.glossary_handler import GlossaryHandler
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation.translation_ui_handler import TranslationUIHandler
from handlers.translation.ai_lifecycle_manager import AILifecycleManager
from handlers.translation.ai_worker import AIWorker
from handlers.translation.text_formatter import TextFormatter
from handlers.translation.ai_variations_handler import AIVariationsHandler
from handlers.translation.progress_manager import TranslationProgressManager
from handlers.translation.batch_translator import AIBatchTranslator
from utils.logging_utils import log_debug
from handlers.translation.facade.glossary_proxy_mixin import GlossaryProxyMixin
from handlers.translation.facade.session_mixin import SessionMixin
from handlers.translation.facade.translate_mixin import TranslateMixin
from handlers.translation.facade.apply_mixin import ApplyMixin


class TranslationHandler(
    GlossaryProxyMixin,
    SessionMixin,
    TranslateMixin,
    ApplyMixin,
    BaseHandler,
):
    """Handler for translation operations."""
    _MAX_LOG_EXCERPT: int = 160

    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self._session_manager = TranslationSessionManager()
        self._session_mode: str = 'auto'
        self._provider_supports_sessions: bool = False
        self._active_provider_key: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[AIWorker] = None
        self.is_ai_running = False
        self.translation_progress: Dict[int, Dict[str, Union[set, int]]] = {}
        self.pre_translation_state: Dict[int, List[str]] = {}
        self.current_session_translations: Dict[int, List[Tuple[int, str]]] = {}
        self.current_session_previous_translations: Dict[int, List[Tuple[int, str]]] = {}

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)
        self.ai_lifecycle_manager = AILifecycleManager(self)
        self.text_formatter = TextFormatter(self.mw)
        self.variations_handler = AIVariationsHandler(self)
        self.progress_manager = TranslationProgressManager(self)
        self.batch_translator = AIBatchTranslator(self)

        # Register AI success/error handlers
        self.ai_lifecycle_manager.register_handler('translate_preview', self.batch_translator.handle_preview_translation_success)
        self.ai_lifecycle_manager.register_handler('translate_single', self.batch_translator.handle_single_translation_success)
        self.ai_lifecycle_manager.register_handler('generate_variation', self.variations_handler._handle_variation_success)
        self.ai_lifecycle_manager.register_handler('fill_glossary', self.glossary_handler._handle_ai_fill_success)
        self.ai_lifecycle_manager.register_handler('glossary_occurrence_update', self.glossary_handler._handle_glossary_occurrence_update_success)
        self.ai_lifecycle_manager.register_handler('glossary_occurrence_batch_update', self.glossary_handler._handle_glossary_occurrence_batch_success)
        self.ai_lifecycle_manager.register_handler('glossary_notes_variation', self.glossary_handler._handle_glossary_notes_variation_success)
        self.ai_lifecycle_manager.register_handler('classify_suggest_types', self.glossary_handler._handle_classify_suggest_success, self.glossary_handler._handle_classify_error)
        self.ai_lifecycle_manager.register_handler('classify_apply', self.glossary_handler._handle_classify_apply_success, self.glossary_handler._handle_classify_error)
        
        # Block translation has a chunk handler
        self.ai_lifecycle_manager.register_handler('translate_block_chunked', 
                                                    self.batch_translator.handle_block_translation_success,
                                                    chunk_cb=self.batch_translator.handle_chunk_translated)

        self._glossary_manager = self.glossary_handler.glossary_manager
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.__init__: start_new_session initialized to {self.start_new_session}")

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
