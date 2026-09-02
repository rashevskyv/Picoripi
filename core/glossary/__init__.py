"""Glossary package: models, helpers, and GlossaryManager."""
from core.glossary.models import (
    STATUS_SEEDED,
    STATUS_FRAGMENTS,
    STATUS_SYNTHESIZED,
    STATUS_TRANSLATED,
    STATUS_CONFIRMED,
    TERM_PLACEHOLDER,
    UNCONFIRMED_STATUSES,
    OCC_MENTION,
    OCC_SPOKEN,
    DescriptionFragment,
    TranslationVariant,
    GlossaryEntry,
    GlossaryMatch,
    GlossaryOccurrence,
)
from core.glossary.notes import (
    render_notes,
    possible_duplicate_pairs,
    _fragments_from_raw,
    _variants_from_raw,
    _entry_to_dict,
)
from core.glossary.replace import preserve_case, replace_preserve_case
from core.glossary.manager import GlossaryManager

__all__ = [
    "STATUS_SEEDED",
    "STATUS_FRAGMENTS",
    "STATUS_SYNTHESIZED",
    "STATUS_TRANSLATED",
    "STATUS_CONFIRMED",
    "TERM_PLACEHOLDER",
    "UNCONFIRMED_STATUSES",
    "OCC_MENTION",
    "OCC_SPOKEN",
    "DescriptionFragment",
    "TranslationVariant",
    "GlossaryEntry",
    "GlossaryMatch",
    "GlossaryOccurrence",
    "render_notes",
    "possible_duplicate_pairs",
    "_fragments_from_raw",
    "_variants_from_raw",
    "_entry_to_dict",
    "preserve_case",
    "replace_preserve_case",
    "GlossaryManager",
]
