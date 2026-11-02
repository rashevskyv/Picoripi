"""Resolve glossary details for a displayed speaker name."""
from __future__ import annotations

from html import escape
from typing import Iterable, Optional

from core.glossary.manager import GlossaryManager
from core.glossary.models import GlossaryEntry


def resolve_speaker_entry(
    manager: Optional[GlossaryManager], names: Iterable[str]
) -> Optional[GlossaryEntry]:
    """Resolve the first matching speaker by original, alias, or translation."""
    if manager is None:
        return None
    names = tuple(str(name or "").strip() for name in names if str(name or "").strip())
    for name in names:
        entry = manager.get_entry(name)
        if entry:
            return entry
    folded = {name.casefold() for name in names}
    for entry in manager.get_entries():
        translations = [entry.translation, *(variant.translation for variant in entry.translation_variants)]
        if any(
            part.strip().casefold() in folded
            for value in translations if value
            for part in value.split(";")
        ):
            return entry
    return None


def speaker_description_html(entry: GlossaryEntry) -> str:
    """Render a safe tooltip fragment from the glossary description."""
    from core.glossary_manager import render_notes
    description = render_notes(entry.notes, translation=entry.translation, original=entry.original)
    description = escape(description).replace("\n", "<br>")
    user_notes = escape(entry.user_notes or "").replace("\n", "<br>")
    body = "<br>".join(part for part in (description, user_notes) if part)
    return f"<b>{escape(entry.original)}</b><br>{body}" if body else ""
