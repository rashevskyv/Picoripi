"""Glossary note rendering and serialization helpers."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from core.glossary.models import (
    TERM_PLACEHOLDER,
    DescriptionFragment,
    GlossaryEntry,
    TranslationVariant,
)


def render_notes(notes: str, *, translation: str = "", original: str = "") -> str:
    """Substitute the term placeholder with the chosen translation.

    Falls back to the source term, and finally leaves the placeholder visible,
    so a note never silently loses the subject of its own sentence.
    """
    if not notes or TERM_PLACEHOLDER not in notes:
        return notes or ""
    replacement = (translation or "").strip() or (original or "").strip()
    return notes.replace(TERM_PLACEHOLDER, replacement) if replacement else notes

def possible_duplicate_pairs(entries) -> List[Tuple[str, str]]:
    """Conservative fuzzy duplicate proposals; never merges anything itself."""
    candidates = []
    for index, left in enumerate(entries):
        left_key = "".join(ch for ch in left.original.casefold() if ch.isalnum())
        if len(left_key) < 4:
            continue
        for right in entries[index + 1:]:
            if left.section and right.section and left.section != right.section:
                continue
            right_key = "".join(ch for ch in right.original.casefold() if ch.isalnum())
            if left_key == right_key or len(right_key) < 4:
                continue
            if left_key[:2] != right_key[:2] or abs(len(left_key) - len(right_key)) > 3:
                continue
            # ponytail: lexical similarity only; replace with semantic matching
            # if real projects show that differently spelled aliases are missed.
            if SequenceMatcher(None, left_key, right_key).ratio() >= 0.88:
                candidates.append((left.original, right.original))
    return candidates

def _fragments_from_raw(raw) -> Tuple[DescriptionFragment, ...]:
    """Parse serialized description fragments back into typed objects."""
    if not isinstance(raw, list):
        return ()
    out: List[DescriptionFragment] = []
    for item in raw:
        if isinstance(item, dict):
            def _coord(key: str) -> int:
                try:
                    return int(item.get(key, -1))
                except (TypeError, ValueError):
                    return -1
            out.append(
                DescriptionFragment(
                    text=str(item.get("text", "") or ""),
                    block_idx=_coord("block_idx"),
                    string_idx=_coord("string_idx"),
                )
            )
        elif isinstance(item, str):
            out.append(DescriptionFragment(text=item))
    return tuple(out)

def _variants_from_raw(raw) -> Tuple[TranslationVariant, ...]:
    """Parse serialized translation variants back into typed objects."""
    if not isinstance(raw, list):
        return ()
    out: List[TranslationVariant] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(
                TranslationVariant(
                    translation=str(item.get("translation", "") or ""),
                    rationale=str(item.get("rationale", "") or ""),
                )
            )
        elif isinstance(item, str):
            out.append(TranslationVariant(translation=item))
    return tuple(out)

def _entry_to_dict(entry: GlossaryEntry) -> Dict[str, Any]:
    """Serialize an entry, emitting new lifecycle fields only when set.

    Keeping default-valued fields out of the JSON preserves the existing file
    shape for legacy glossaries and avoids churning every entry on save.
    """
    out: Dict[str, Any] = {
        "original": entry.original,
        "translation": entry.translation,
        "notes": entry.notes,
        "section": entry.section,
        "profiled": entry.profiled,
    }
    if entry.status:
        out["status"] = entry.status
    if entry.icon:
        out["icon"] = entry.icon
    if entry.provisional:
        out["provisional"] = True
    if entry.suggested_name:
        out["suggested_name"] = entry.suggested_name
    if entry.suggested_name_evidence:
        out["suggested_name_evidence"] = entry.suggested_name_evidence
    if entry.fragments:
        out["fragments"] = [
            {"text": f.text, "block_idx": f.block_idx, "string_idx": f.string_idx}
            for f in entry.fragments
        ]
    if entry.translation_variants:
        out["translation_variants"] = [
            {"translation": v.translation, "rationale": v.rationale}
            for v in entry.translation_variants
        ]
    return out
