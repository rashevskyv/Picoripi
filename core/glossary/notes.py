"""Glossary note rendering and serialization helpers."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence, Tuple

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
    if not notes:
        return ""
    replacement = (translation or "").strip() or (original or "").strip()
    if not replacement:
        return notes
    if TERM_PLACEHOLDER in notes:
        notes = notes.replace(TERM_PLACEHOLDER, replacement)
    if "{TERM}" in notes:
        notes = notes.replace("{TERM}", replacement)
    return notes


def ensure_term_placeholder(
    notes: str,
    original: str = "",
    known_names: Sequence[str] = (),
) -> str:
    """Normalize notes so the subject term uses the {{TERM}} placeholder.

    If notes already contain {{TERM}} or {TERM}, normalizes {TERM} to {{TERM}}.
    Otherwise, if the description starts with the original term, a known translation,
    or a leading punctuation dash, substitutes the leading reference with {{TERM}}.
    """
    if not notes or not notes.strip():
        return notes or ""

    if TERM_PLACEHOLDER in notes:
        return notes
    if "{TERM}" in notes:
        return notes.replace("{TERM}", TERM_PLACEHOLDER)

    stripped = notes.strip()
    if stripped.startswith(("—", "–", "-", ":")):
        remainder = stripped.lstrip("—–-: ").strip()
        return f"{TERM_PLACEHOLDER} — {remainder}"

    candidates: List[str] = []
    for cand in [original, *known_names]:
        clean = (cand or "").strip()
        if clean and clean not in candidates:
            candidates.append(clean)

    candidates.sort(key=len, reverse=True)

    for cand in candidates:
        pattern = re.compile(
            r'^(?i:' + re.escape(cand) + r')(?:\s*(?:—|–|-|:)\s*|\s+(?:is|are|was|were)\s+|\s*,\s*|\s+)',
            flags=re.UNICODE,
        )
        match = pattern.match(stripped)
        if match:
            matched_text = match.group(0)
            remainder = stripped[match.end():].strip()
            verb_match = re.search(r'\b(is|are|was|were)\b', matched_text, flags=re.IGNORECASE)
            if verb_match:
                return f"{TERM_PLACEHOLDER} {verb_match.group(1)} {remainder}"
            return f"{TERM_PLACEHOLDER} — {remainder}"

    lead_match = re.match(r'^([^\n—–:]{1,35})\s*(?:—|–|-|:)\s*(.+)$', stripped, flags=re.DOTALL)
    if lead_match:
        lead = lead_match.group(1).strip()
        remainder = lead_match.group(2).strip()
        lower_lead = lead.lower()
        if lower_lead not in {"note", "notes", "warning", "tip", "примітка", "увага", "важливо", "див", "see"}:
            if len(lead.split()) <= 4:
                return f"{TERM_PLACEHOLDER} — {remainder}"

    return notes

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
    if getattr(entry, "user_notes", ""):
        out["user_notes"] = entry.user_notes
    if getattr(entry, "updated_at", ""):
        out["updated_at"] = entry.updated_at
    if entry.aliases:
        out["aliases"] = list(entry.aliases)
    return out
