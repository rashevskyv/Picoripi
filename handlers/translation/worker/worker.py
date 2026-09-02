from PyQt6.QtCore import QObject, pyqtSignal
from typing import Any, Dict, Optional
from core.translation.providers import BaseTranslationProvider, ProviderResponse
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation.worker.json_mixin import AIWorkerJsonMixin
from handlers.translation.worker.run_mixin import AIWorkerRunMixin
from handlers.translation.worker.control_mixin import AIWorkerControlMixin


class AIWorker(
    AIWorkerJsonMixin,
    AIWorkerRunMixin,
    AIWorkerControlMixin,
    QObject,
):
    """A i worker implementation."""
    success = pyqtSignal(ProviderResponse, dict)
    error = pyqtSignal(str, dict)
    finished = pyqtSignal()
    step_updated = pyqtSignal(int, str, int)
    
    chunk_translated = pyqtSignal(int, str, dict)
    total_chunks_calculated = pyqtSignal(int, int)
    translation_cancelled = pyqtSignal()
    progress_updated = pyqtSignal(int)
    chunk_received = pyqtSignal(dict, str)
    detail_updated = pyqtSignal(str)

    def __init__(self, provider: BaseTranslationProvider, prompt_composer: Optional[AIPromptComposer], task_details: Dict[str, Any], mw: Any = None):
        """Initialize a new instance."""
        super().__init__()
        self.provider = provider
        self.prompt_composer = prompt_composer
        self.task_details = task_details
        self._mw = mw
        self.is_cancelled = False
        self._last_messages = None

    @property
    def mw(self) -> Optional[Any]:
        """Mw."""
        if self._mw is not None:
            return self._mw
        if self.prompt_composer and hasattr(self.prompt_composer, 'mw'):
            return self.prompt_composer.mw
        return None

