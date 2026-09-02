from typing import Dict, List, Optional
from utils.logging_utils import log_debug


class AIWorkerControlMixin:
    """Cancel and AI traffic logging."""

    def _log_ai_traffic(self, messages: List[Dict[str, str]], response_text: Optional[str] = None, error: Optional[str] = None):
        """Internal helper to log ai traffic."""
        from utils.logging_utils import log_ai_traffic
        task_type = self.task_details.get('type', 'unknown')
        mw = self.mw
        log_ai_traffic(mw, task_type, messages, response_text, error)

    def cancel(self):
        """Cancel."""
        log_debug("AIWorker: Cancellation requested.")
        self.is_cancelled = True
        cancel_stream = getattr(self.provider, "cancel_active_stream", None)
        if callable(cancel_stream):
            cancel_stream()
