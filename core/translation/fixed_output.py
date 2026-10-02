"""Strings whose translation is fixed by the glossary and never go to the model.

Recurring interface words -- "OK", "Yes", "Back" -- are the same string dozens
of times. A glossary entry in a *fixed-output section* (``UI`` unless the
translation config names others) says what such a string is in the target
language; a game string that is, as a whole, exactly that term takes the
translation as it stands.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from core.glossary.models import UNCONFIRMED_STATUSES, GlossaryEntry

DEFAULT_SECTIONS = ("UI",)


def fixed_output_sections(translation_config: Any) -> tuple:
    """The glossary sections whose entries are fixed outputs (translation config ``fixed_output_sections``)."""
    configured = translation_config.get("fixed_output_sections") if isinstance(translation_config, dict) else None
    if isinstance(configured, (list, tuple)):
        return tuple(str(section) for section in configured if str(section).strip())
    return DEFAULT_SECTIONS


def fixed_translation(text: Any, glossary_manager: Any, sections: Iterable[str] = DEFAULT_SECTIONS) -> Optional[str]:
    """The translation of ``text`` when the whole string is a term of a fixed-output section, else None.

    The text must equal the term (or one of its aliases) character for
    character: "OK" is fixed, "ok" and "OK!" are translated in context. An
    entry whose translation is still an unconfirmed suggestion fixes nothing.
    """
    if not isinstance(text, str) or not text.strip() or glossary_manager is None:
        return None
    wanted = {str(section).strip().casefold() for section in sections}
    entry = glossary_manager.get_entry(text)
    if not isinstance(entry, GlossaryEntry):
        return None
    if (entry.section or "").strip().casefold() not in wanted or entry.status in UNCONFIRMED_STATUSES:
        return None
    if text != entry.original and text not in entry.aliases:
        return None
    translation = (entry.translation or "").strip()
    return translation or None
