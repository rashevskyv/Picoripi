# handlers/base_handler.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.context import ProjectContext
    from core.data_state_processor import DataStateProcessor
    from ui.ui_updater import UIUpdater
    from core.state_manager import StateManager
    from core.data_store import AppDataStore

class BaseHandler:
    """Handler for base operations."""
    def __init__(self, context: ProjectContext, data_processor: DataStateProcessor, ui_updater: UIUpdater):
        """Initialize a new instance."""
        self.ctx: ProjectContext = context
        self.data_processor: DataStateProcessor = data_processor
        self.ui_updater: UIUpdater = ui_updater

    @property
    def mw(self) -> ProjectContext:
        """Temporary property for backward compatibility during refactoring."""
        return self.ctx

    @property
    def state(self) -> StateManager:
        """State."""
        return self.ctx.state

    @property
    def data_store(self) -> AppDataStore:
        """Data store."""
        return self.ctx.data_store
