"""Pass 3 driver: propose translation variants from a term's description.

The AI call is injected as ``propose(term, description) -> raw variants``. The
driver normalizes the raw output into typed variants, dedups them, caps them to
at most three, and reports whether the result is ambiguous -- more than one
distinct variant -- which is one of the yellow "unconfirmed" signals (roadmap
sections 5 and 7). The model is asked to return one variant when there is no
real ambiguity, so a multi-variant result is meaningful, not decorative.

The active translation is always exactly one (the first variant); the rest live
as candidates until the user confirms a choice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional

from core.glossary_manager import TranslationVariant


DEFAULT_MAX_VARIANTS = 3


@dataclass
class TranslateResult:
    """Outcome of proposing translations for one term."""

    variants: List[TranslationVariant] = field(default_factory=list)
    active: str = ""
    multiple: bool = False


def _coerce(item: Any) -> TranslationVariant:
    """Accept a dict, a TranslationVariant, or a bare string."""
    if isinstance(item, TranslationVariant):
        return item
    if isinstance(item, dict):
        return TranslationVariant(
            translation=str(item.get("translation", "") or ""),
            rationale=str(item.get("rationale", "") or ""),
        )
    return TranslationVariant(translation=str(item or ""))


def propose_translations(
    term: str,
    description: str,
    propose: Callable[[str, str], Iterable[Any]],
    *,
    max_variants: int = DEFAULT_MAX_VARIANTS,
    normalize: Optional[Callable[[str], str]] = None,
) -> TranslateResult:
    """Ask the AI for translation variants and normalize the result.

    Variants are deduped (by ``normalize`` if given, else casefold), capped to
    ``max_variants``, and blanks dropped. The first surviving variant is active.
    """
    raw = propose(term, description) or []
    key_of = normalize if normalize is not None else (lambda s: s.casefold())

    variants: List[TranslationVariant] = []
    seen = set()
    for item in raw:
        variant = _coerce(item)
        translation = variant.translation.strip()
        if not translation:
            continue
        key = key_of(translation)
        if key in seen:
            continue
        seen.add(key)
        variants.append(
            TranslationVariant(translation=translation, rationale=variant.rationale.strip())
        )
        if len(variants) >= max_variants:
            break

    active = variants[0].translation if variants else ""
    return TranslateResult(variants=variants, active=active, multiple=len(variants) > 1)
