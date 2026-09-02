from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.glossary_manager import GlossaryEntry
from core.translation.session_manager import TranslationSessionState


class GlossaryMixin:
    """Glossary formatting, placeholders, and tag-alias helpers."""

    def _append_speaker_glossary_entries(
        self,
        relevant_entries: List[GlossaryEntry],
        speaker_candidates: Iterable[str]
    ) -> None:
        glossary_manager = self.main_handler._glossary_manager
        self.glossary_formatter.append_speaker_glossary_entries(
            relevant_entries, speaker_candidates, glossary_manager
        )

    def _glossary_entries_to_text(self, entries: Sequence[GlossaryEntry]) -> str:
        return self.glossary_formatter.glossary_entries_to_text(entries)

    def _prepare_glossary_for_prompt(
        self,
        system_prompt: str,
        session_state: Optional[TranslationSessionState],
        is_batch_translation: bool = False,
    ) -> str:
        return (system_prompt or "").strip()

    # ------------------------------------------------------------------
    # Public API used by translation handler
    # ------------------------------------------------------------------
    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        """Prepare text for translation."""
        return self.placeholder_manager.prepare_text_for_translation(source_text, glossary_entries)

    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
    ) -> str:
        """Restore placeholders."""
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
        glossary_manager = self.main_handler._glossary_manager
        return self.placeholder_manager.restore_placeholders(
            translated_text,
            placeholder_map,
            key=key,
            default_tag_mappings=default_tag_mappings,
            glossary_manager=glossary_manager,
        )

    # ------------------------------------------------------------------
    # Prompt composition helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _relevant_tag_aliases(mappings, *texts) -> dict:
        """Only the tag aliases that actually occur in what is being sent.

        The full mapping is ~500 entries. Sending all of it with every request
        buries the handful of tags the line really uses under a wall the model
        has to read past, and costs the tokens to do it. An alias the text does
        not contain explains nothing.
        """
        haystack = "\n".join(str(t or "") for t in texts)
        legend = {}
        for alias, orig in (mappings or {}).items():
            lowered = alias.lower()
            if lowered.startswith('{f:') or lowered.startswith('[f:'):
                continue
            # Match the alias as shown, and the raw form in case one leaks
            # through unconverted.
            if alias in haystack or (orig and orig in haystack):
                legend[alias] = orig
        return legend
