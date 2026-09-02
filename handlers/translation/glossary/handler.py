from pathlib import Path
from typing import Optional, Tuple

from handlers.translation.base_translation_handler import BaseTranslationHandler
from handlers.translation.glossary_prompt_manager import GlossaryPromptManager
from handlers.translation.glossary_occurrence_updater import GlossaryOccurrenceUpdater
from handlers.translation.glossary.dialog_mixin import DialogMixin
from handlers.translation.glossary.edit_mixin import EditMixin
from handlers.translation.glossary.crud_mixin import CrudMixin
from handlers.translation.glossary.classify_mixin import ClassifyMixin
from handlers.translation.glossary.speaker_mixin import SpeakerMixin
from core.glossary_manager import GlossaryManager
from components.glossary_dialog import GlossaryDialog
from PyQt6.QtGui import QAction


class GlossaryHandler(
    DialogMixin,
    EditMixin,
    CrudMixin,
    ClassifyMixin,
    SpeakerMixin,
    BaseTranslationHandler,
):
    """Handler for glossary operations."""

    def __init__(self, main_handler):
        """Initialize a new instance."""
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self.dialog: Optional[GlossaryDialog] = None
        # Snapshot of (original, translation) pairs taken when the dialog opens,
        # so closing it only rebuilds the virtual folders if a name actually changed.
        self._glossary_signature_on_open: Optional[tuple] = None

        # Delegates
        self._prompt_manager = GlossaryPromptManager(self.mw, main_handler, self.glossary_manager)
        self._occurrence_updater = GlossaryOccurrenceUpdater(self)



    # ── Public prompt manager proxy (used by TranslationHandler) ─────────

    @property
    def _current_prompts_path(self) -> Optional[Path]:
        """Internal helper to current prompts path."""
        return self._prompt_manager.current_prompts_path

    @property
    def translation_update_dialog(self):
        """Translation update dialog."""
        return self._occurrence_updater.translation_update_dialog

    @translation_update_dialog.setter
    def translation_update_dialog(self, value):
        """Translation update dialog."""
        self._occurrence_updater.translation_update_dialog = value

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        """Load prompts."""
        return self._prompt_manager.load_prompts()

    def bind_glossary_for_write(self):
        """Bind the glossary to the project file, creating it when absent."""
        return self._prompt_manager.bind_glossary_for_write()

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        """Save prompt section."""
        return self._prompt_manager.save_prompt_section(section, field, value)

    def _get_glossary_prompt_template(self) -> Tuple[str, Optional[Path]]:
        """Internal helper to get the glossary prompt template."""
        return self._prompt_manager.get_glossary_prompt_template()

    def _update_glossary_highlighting(self) -> None:
        """Internal helper to update the glossary highlighting."""
        self._prompt_manager._update_glossary_highlighting()

    def _ensure_glossary_loaded(self, *, glossary_text, plugin_name, glossary_path) -> None:
        """Internal helper to ensure glossary loaded."""
        self._prompt_manager._ensure_glossary_loaded(
            glossary_text=glossary_text, plugin_name=plugin_name, glossary_path=glossary_path
        )

    # ── Occurrence updater proxy (used by TranslationHandler success handlers) ──

    def request_glossary_occurrence_update(self, **kwargs):
        """Request glossary occurrence update."""
        return self._occurrence_updater.request_glossary_occurrence_update(**kwargs)

    def request_glossary_occurrence_batch_update(self, **kwargs):
        """Request glossary occurrence batch update."""
        return self._occurrence_updater.request_glossary_occurrence_batch_update(**kwargs)

    def request_glossary_notes_variation(self, **kwargs):
        """Request glossary notes variation."""
        return self._occurrence_updater.request_glossary_notes_variation(**kwargs)

    def _handle_occurrence_ai_result(self, **kwargs):
        """Internal helper to handle occurrence ai result."""
        return self._occurrence_updater.handle_occurrence_ai_result(**kwargs)

    def _handle_occurrence_batch_success(self, **kwargs):
        """Internal helper to handle occurrence batch success."""
        return self._occurrence_updater.handle_occurrence_batch_success(**kwargs)

    def _handle_occurrence_ai_error(self, message, from_batch):
        """Internal helper to handle occurrence ai error."""
        return self._occurrence_updater._handle_occurrence_ai_error(message, from_batch)

    def _handle_glossary_occurrence_update_success(self, response, context):
        """Internal helper to handle glossary occurrence update success."""
        return self._occurrence_updater.handle_glossary_occurrence_update_success(response, context)

    def _handle_glossary_occurrence_batch_success(self, response, context):
        """Internal helper to handle glossary occurrence batch success."""
        return self._occurrence_updater.handle_glossary_occurrence_batch_success(response, context)

    def initialize_glossary_highlighting(self) -> None:
        """Initialize glossary highlighting."""
        self._prompt_manager.initialize_highlighting()

