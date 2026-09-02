from __future__ import annotations

from handlers.translation.base_translation_handler import BaseTranslationHandler
from core.translation.placeholder_manager import AIPlaceholderManager
from core.translation.glossary_formatter import GlossaryPromptFormatter
from core.translation.story_context_manager import StoryContextManager
from core.translation.script_speaker_finder import ScriptSpeakerFinder
from handlers.translation.prompt_composer.script_mixin import ScriptMixin
from handlers.translation.prompt_composer.story_mixin import StoryMixin
from handlers.translation.prompt_composer.glossary_mixin import GlossaryMixin
from handlers.translation.prompt_composer.batch_mixin import BatchMixin
from handlers.translation.prompt_composer.messages_mixin import MessagesMixin


class AIPromptComposer(
    ScriptMixin,
    StoryMixin,
    GlossaryMixin,
    BatchMixin,
    MessagesMixin,
    BaseTranslationHandler,
):
    """Compose prompts for AI translation/variation tasks and manage placeholders."""

    def __init__(self, *args, **kwargs):
        """Initialize a new instance."""
        super().__init__(*args, **kwargs)

        # Instantiate services
        self.placeholder_manager = AIPlaceholderManager()
        self.glossary_formatter = GlossaryPromptFormatter()
        self.story_context = StoryContextManager(self.mw)
        self.script_speaker_finder = ScriptSpeakerFinder(self.mw, self.story_context)

    def _get_target_lang(self) -> str:
        """Helper to get and sanitize the target language."""
        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')
        if not isinstance(target_lang, str) or not target_lang.strip():
            return 'Ukrainian'
        return target_lang

    def _replace_runtime_names_for_ai(self, text: str) -> str:
        """Apply a game plugin's explicit runtime-name substitutions."""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules and hasattr(rules, 'replace_runtime_names_for_ai'):
            replaced = rules.replace_runtime_names_for_ai(text)
            if isinstance(replaced, str):
                return replaced
        return str(text or "")

    # ------------------------------------------------------------------
    # Properties for backwards compatibility with test cache assertions
    # ------------------------------------------------------------------
    @property
    def _script_lines_cache(self):
        return self.script_speaker_finder._script_lines_cache
    @_script_lines_cache.setter
    def _script_lines_cache(self, val):
        self.script_speaker_finder._script_lines_cache = val

    @property
    def _global_distilled_text_cache(self):
        return self.script_speaker_finder._global_distilled_text_cache
    @_global_distilled_text_cache.setter
    def _global_distilled_text_cache(self, val):
        self.script_speaker_finder._global_distilled_text_cache = val

    @property
    def _char_to_line_map_cache(self):
        return self.script_speaker_finder._char_to_line_map_cache
    @_char_to_line_map_cache.setter
    def _char_to_line_map_cache(self, val):
        self.script_speaker_finder._char_to_line_map_cache = val

    @property
    def _cached_script_path(self):
        return self.script_speaker_finder._cached_script_path
    @_cached_script_path.setter
    def _cached_script_path(self, val):
        self.script_speaker_finder._cached_script_path = val

    @property
    def _cached_mtime(self):
        return self.script_speaker_finder._cached_mtime
    @_cached_mtime.setter
    def _cached_mtime(self, val):
        self.script_speaker_finder._cached_mtime = val

    @property
    def _cached_size(self):
        return self.script_speaker_finder._cached_size
    @_cached_size.setter
    def _cached_size(self, val):
        self.script_speaker_finder._cached_size = val

    @property
    def _cached_plugin_name(self):
        return self.script_speaker_finder._cached_plugin_name
    @_cached_plugin_name.setter
    def _cached_plugin_name(self, val):
        self.script_speaker_finder._cached_plugin_name = val

    @property
    def _distill_cache_version(self):
        return self.script_speaker_finder._distill_cache_version
    @_distill_cache_version.setter
    def _distill_cache_version(self, val):
        self.script_speaker_finder._distill_cache_version = val
