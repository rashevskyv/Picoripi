# handlers/base_handler.py
from typing import Any

class BaseHandler:
    def __init__(self, context: Any, data_processor: Any, ui_updater: Any):
        self.ctx: Any = context
        self.data_processor: Any = data_processor
        self.ui_updater: Any = ui_updater

    @property
    def mw(self) -> Any:
        """Temporary property for backward compatibility during refactoring."""
        return self.ctx

    @property
    def state(self) -> Any:
        return self.ctx.state

    @property
    def data_store(self) -> Any:
        return self.ctx.data_store
