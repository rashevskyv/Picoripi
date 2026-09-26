"""Shared memory ledger for established narrative decisions, character voices, and lore.

Used by the Translator and Editor/Arbiter during chronological story translation
and passed downstream to semantic blocks (shops, menus, UI) to maintain consistency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NarrativeLedger:
    """Stores dynamic canon decisions established during translation."""
    established_terms: Dict[str, Dict[str, str]] = field(default_factory=dict)
    speaker_voices: Dict[str, str] = field(default_factory=dict)
    recent_events: List[str] = field(default_factory=list)
    max_recent_events: int = 5

    def record_term(self, term: str, target: str, category: str = "", notes: str = "") -> None:
        """Record an established term translation."""
        clean_term = (term or "").strip()
        clean_target = (target or "").strip()
        if not clean_term or not clean_target:
            return
        self.established_terms[clean_term] = {
            "target": clean_target,
            "category": (category or "").strip(),
            "notes": (notes or "").strip(),
        }

    def record_speaker_voice(self, speaker: str, voice_or_address: str) -> None:
        """Record established tone, formality or pronoun rules for a speaker."""
        clean_spk = (speaker or "").strip()
        clean_voice = (voice_or_address or "").strip()
        if clean_spk and clean_voice:
            self.speaker_voices[clean_spk] = clean_voice

    def record_story_event(self, event_summary: str) -> None:
        """Add a story event summary, keeping the rolling history bounded."""
        clean_event = (event_summary or "").strip()
        if not clean_event:
            return
        if clean_event not in self.recent_events:
            self.recent_events.append(clean_event)
            if len(self.recent_events) > self.max_recent_events:
                self.recent_events.pop(0)

    def format_for_prompt(self) -> str:
        """Format the ledger into a concise prompt block for Translator and Editor."""
        if not self.established_terms and not self.speaker_voices and not self.recent_events:
            return ""

        parts = ["=== ESTABLISHED NARRATIVE CONTEXT & CANON DECISIONS ==="]

        if self.established_terms:
            parts.append("Established Game Terms (Must be followed consistently):")
            for term, data in list(self.established_terms.items())[:30]:
                target = data.get("target", "")
                cat = data.get("category", "")
                cat_suffix = f" [{cat}]" if cat else ""
                parts.append(f"• {term} -> {target}{cat_suffix}")

        if self.speaker_voices:
            parts.append("\nCharacter Voices & Formality (Preserve tone):")
            for spk, voice in self.speaker_voices.items():
                parts.append(f"• {spk}: {voice}")

        if self.recent_events:
            parts.append("\nRecent Story Context (What just happened):")
            for evt in self.recent_events:
                parts.append(f"- {evt}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ledger for session or project metadata storage."""
        return {
            "established_terms": dict(self.established_terms),
            "speaker_voices": dict(self.speaker_voices),
            "recent_events": list(self.recent_events),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> NarrativeLedger:
        """Deserialize ledger from dictionary."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            established_terms=dict(data.get("established_terms") or {}),
            speaker_voices=dict(data.get("speaker_voices") or {}),
            recent_events=list(data.get("recent_events") or []),
        )

    def clear(self) -> None:
        """Reset ledger state."""
        self.established_terms.clear()
        self.speaker_voices.clear()
        self.recent_events.clear()
