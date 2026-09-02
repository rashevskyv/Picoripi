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
from handlers.translation.facade import handler as _handler
from handlers.translation.facade import glossary_proxy_mixin as _glossary_proxy_mixin
from handlers.translation.facade import session_mixin as _session_mixin
from handlers.translation.facade import translate_mixin as _translate_mixin
from handlers.translation.facade import apply_mixin as _apply_mixin


class _ShimName:
    """Late-bound name that always reads from this shim module."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _resolve(self):
        import sys
        return getattr(sys.modules[__name__], object.__getattribute__(self, "_name"))

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __repr__(self):
        return repr(self._resolve())


# Names tests patch on this module and that __init__/mixins use as globals.
_handler.GlossaryHandler = _ShimName("GlossaryHandler")
_handler.AIPromptComposer = _ShimName("AIPromptComposer")
_handler.TranslationUIHandler = _ShimName("TranslationUIHandler")
_handler.AILifecycleManager = _ShimName("AILifecycleManager")
_handler.TranslationSessionManager = _ShimName("TranslationSessionManager")
_handler.QTimer = _ShimName("QTimer")
_handler.TextFormatter = _ShimName("TextFormatter")
_handler.AIVariationsHandler = _ShimName("AIVariationsHandler")
_handler.TranslationProgressManager = _ShimName("TranslationProgressManager")
_handler.AIBatchTranslator = _ShimName("AIBatchTranslator")

_glossary_proxy_mixin.QMessageBox = _ShimName("QMessageBox")
_glossary_proxy_mixin.tr = _ShimName("tr")

_session_mixin.GeminiProvider = _ShimName("GeminiProvider")
_session_mixin.PromptEditorDialog = _ShimName("PromptEditorDialog")
_session_mixin.is_control_modifier_pressed = _ShimName("is_control_modifier_pressed")
_session_mixin.QMessageBox = _ShimName("QMessageBox")
_session_mixin.QDialog = _ShimName("QDialog")
_session_mixin.tr = _ShimName("tr")
_session_mixin.log_debug = _ShimName("log_debug")

_translate_mixin.QMessageBox = _ShimName("QMessageBox")
_translate_mixin.QPoint = _ShimName("QPoint")
_translate_mixin.tr = _ShimName("tr")
_translate_mixin.log_debug = _ShimName("log_debug")
_translate_mixin.iter_all_strings = _ShimName("iter_all_strings")

_apply_mixin.log_debug = _ShimName("log_debug")

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
