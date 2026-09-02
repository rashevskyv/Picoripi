from PyQt6.QtCore import pyqtSignal, QThread


class ProviderTestWorker(QThread):
    """Provider test worker implementation."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, provider_key: str, provider_settings: dict):
        """Initialize a new instance."""
        super().__init__()
        self.provider_key = provider_key
        self.provider_settings = provider_settings
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation."""
        self._is_cancelled = True

    def run(self):
        """Run."""
        try:
            from core.translation.providers import create_translation_provider
            provider = create_translation_provider(self.provider_key, self.provider_settings)
            messages = [
                {"role": "user", "content": "Say the word \"Test\" and nothing else."}
            ]
            if self._is_cancelled:
                return
            response = provider.translate(messages)
            if self._is_cancelled:
                return
            if response and response.text:
                self.finished_signal.emit(True, response.text.strip())
            else:
                self.finished_signal.emit(False, "Received empty response from provider.")
        except Exception as e:
            if self._is_cancelled:
                return
            self.finished_signal.emit(False, str(e))
