from __future__ import annotations
import re
from typing import Dict, Optional, Tuple

class AIPlaceholderManager:
    """Manages text preparation for AI translation and placeholder restoration."""

    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: list,
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        """Prepare text for translation. Retained for backwards compatibility."""
        return source_text or '', {}

    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
        default_tag_mappings: Optional[Dict[str, str]] = None,
        glossary_manager: Optional[object] = None,
    ) -> str:
        """Restore placeholders, Force-aliases, and normal tag aliases in translated text."""
        if not translated_text:
            return ''

        # 1. Restore Force-aliases if they exist
        if placeholder_map and key in placeholder_map:
            from utils.force_alias import restore_force_aliases_in_translation
            force_maps = placeholder_map[key]
            glossary_translations = {}
            if glossary_manager:
                for mapping in force_maps:
                    word = mapping.word
                    entry = glossary_manager.get_entry(word)
                    if entry and entry.translation:
                        glossary_translations[word.lower()] = entry.translation
            translated_text = restore_force_aliases_in_translation(translated_text, force_maps, glossary_translations)

        # 2. Restore normal tag aliases from default_tag_mappings
        if default_tag_mappings:
            sorted_mappings = sorted(default_tag_mappings.items(), key=lambda item: len(item[0]), reverse=True)
            for alias, original_tag in sorted_mappings:
                if alias and original_tag:
                    pattern = re.compile(re.escape(alias), re.IGNORECASE)
                    translated_text = pattern.sub(original_tag, translated_text)

        return translated_text
