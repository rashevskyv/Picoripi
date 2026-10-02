"""Compatibility shim: implementation lives in handlers.translation.facade.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
from PyQt6.QtCore import QTimer, QPoint
from PyQt6.QtWidgets import QDialog, QMessageBox

from core.translation.providers import GeminiProvider
from core.translation.session_manager import TranslationSessionManager
from handlers.translation.glossary_handler import GlossaryHandler
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation.translation_ui_handler import TranslationUIHandler
from handlers.translation.ai_lifecycle_manager import AILifecycleManager
from handlers.translation.text_formatter import TextFormatter
from handlers.translation.ai_variations_handler import AIVariationsHandler
from handlers.translation.progress_manager import TranslationProgressManager
from handlers.translation.batch_translator import AIBatchTranslator
from components.prompt_editor_dialog import PromptEditorDialog
from utils.logging_utils import log_debug
from utils.utils import is_control_modifier_pressed
from core.tag_utils import iter_all_strings
from core.i18n import tr

from handlers.translation.facade import TranslationHandler


# Names tests patch on this module and that __init__/mixins use as globals.


__all__ = [
    "TranslationHandler",
    "GlossaryHandler",
    "AIPromptComposer",
    "TranslationUIHandler",
    "AILifecycleManager",
    "TranslationSessionManager",
    "TextFormatter",
    "AIVariationsHandler",
    "TranslationProgressManager",
    "AIBatchTranslator",
    "QTimer",
    "QPoint",
    "QDialog",
    "QMessageBox",
    "GeminiProvider",
    "PromptEditorDialog",
    "is_control_modifier_pressed",
    "log_debug",
    "iter_all_strings",
    "tr",
]
