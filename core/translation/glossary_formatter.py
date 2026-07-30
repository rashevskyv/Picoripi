from __future__ import annotations
import re
from typing import List, Sequence, Iterable, Optional
from core.glossary_manager import GlossaryEntry, render_notes

class GlossaryPromptFormatter:
    """Formats glossary entries and appends speaker terms for prompt context."""

    def glossary_entries_to_text(self, entries: Sequence[GlossaryEntry]) -> str:
        """Format glossary entries into a markdown table."""
        if not entries:
            return ""
        lines = ["| Original | Translation | Notes |", "|---|---|---|"]
        for entry in entries:
            # Notes are stored with a term placeholder; the translator must see
            # the settled translation, not the token.
            notes = render_notes(
                entry.notes, translation=entry.translation, original=entry.original
            )
            lines.append(f"| {entry.original} | {entry.translation} | {notes} |")
        return "\n".join(lines)

    def append_speaker_glossary_entries(
        self,
        relevant_entries: List[GlossaryEntry],
        speaker_candidates: Iterable[str],
        glossary_manager: Optional[object],
    ) -> None:
        """Find speaker names in the glossary and append them to relevant_entries."""
        if not glossary_manager:
            return

        expanded_candidates = set()
        for cand in speaker_candidates:
            if cand:
                for part in cand.split(','):
                    expanded_candidates.add(part.strip())

        for c_raw in expanded_candidates:
            if not c_raw or c_raw.upper() in ("UNKNOWN", "NONE"):
                continue

            clean_cand = re.sub(r'#\s*\d+', '', c_raw).strip()
            candidates_to_try = [c_raw, clean_cand] if clean_cand != c_raw else [c_raw]

            for c in candidates_to_try:
                entry = glossary_manager.get_entry(c)
                if entry:
                    if entry not in relevant_entries:
                        relevant_entries.append(entry)
                else:
                    c_low = c.strip().lower()
                    for entry in glossary_manager.get_entries():
                        if (entry.original.strip().lower() == c_low or
                            entry.translation.strip().lower() == c_low):
                            if entry not in relevant_entries:
                                relevant_entries.append(entry)
