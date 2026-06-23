"""Markup recipe: a reusable, serializable description of *how a particular
walkthrough is shaped* (where speakers, locations, chapters, actions and noise
live, and in what form).

A recipe is intentionally just data: ordered regex rules + a few flags. The
engine (markup_engine.py) applies it deterministically. Recipes are portable —
once tuned for a given walkthrough source style (e.g. "GameFAQs classic") they
can be reused across games of the same source.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


class LineKind:
    """Classification of a single raw line. String constants (not Enum) so they
    serialize trivially and read clearly in the UI/highlighting layer."""
    BLANK = "blank"
    IGNORE = "ignore"            # noise: TOC dot-leaders, separators, legal, ascii art
    CHAPTER = "chapter"
    LOCATION = "location"
    ACTION = "action"
    SPEAKER = "speaker"          # inline "NAME: text"
    GUTTER_SPEAKER = "gutter"    # lone UPPERCASE name line; dialogue follows below
    DIALOGUE_CONT = "dialogue"   # continuation of the open speaker's line
    NARRATION = "narration"      # prose that is not in-game text → dropped from output


# Default rule set tuned for typical GameFAQs / structured walkthroughs.
# All patterns are full-line regexes (matched against the stripped line) and may
# use named groups that the engine reads: title / name / text / speaker.
_DEFAULT_CHAPTER_PATTERNS = [
    r"^\[Chapter:\s*(?P<title>.*?)\]\s*$",
    r"^#{1,2}\s+(?P<title>(?:Chapter|Act|Prologue|Epilogue)\b.*)$",
    r"^(?P<title>(?:ACT|Act)\s+[A-Za-z0-9]+.*)$",
    r"^(?P<title>Chapter\s+[IVXLCDM\d]+.*)$",
]

_DEFAULT_LOCATION_PATTERNS = [
    r"^\[Location:\s*(?P<name>.*?)\]\s*$",
    r"^#{3}\s*Location:\s*(?P<name>.*)$",
]

_DEFAULT_ACTION_PATTERNS = [
    r"^\{(?:Action|Context):\s*(?P<text>.*)\}\s*$",
    r"^\[(?P<text>[^\]]+)\]\s*$",            # bracketed stage direction
]

_DEFAULT_SPEAKER_PATTERNS = [
    # NAME: text  — name is uppercase, 2..30 chars, allows space . ' # -
    r"^(?P<speaker>[A-Z][A-Z0-9 .'#\-]{1,29}):\s*(?P<text>.*)$",
]

_DEFAULT_IGNORE_PATTERNS = [
    r"^[~=_*#\-]{4,}$",          # separator runs: ~~~~, ====, ----, ####
    r".*\.{4,}.*",               # TOC dot-leaders:  Foreword..........3
    r"^\s*[ivxlcdm]+\.{2,}.*$",  # lowercase roman TOC entries
]


@dataclass
class MarkupRecipe:
    """A portable description of one walkthrough's structure."""
    name: str = "GameFAQs classic"
    chapter_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_CHAPTER_PATTERNS))
    location_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_LOCATION_PATTERNS))
    action_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_ACTION_PATTERNS))
    speaker_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_SPEAKER_PATTERNS))
    ignore_patterns: List[str] = field(default_factory=lambda: list(_DEFAULT_IGNORE_PATTERNS))

    # Behaviour flags
    gutter_speakers: bool = True      # treat a lone UPPERCASE line as a speaker (Format B)
    continuation: bool = True         # unmatched line after dialogue continues that dialogue
    drop_narration: bool = True       # prose that is not dialogue is excluded from output
    min_speaker_len: int = 2
    max_speaker_len: int = 30
    # Noise heuristic: drop lines whose non-alphanumeric ratio exceeds this
    # (catches ascii art that no explicit pattern covers). 0 disables.
    max_symbol_ratio: float = 0.6

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-ready)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarkupRecipe":
        """Build a recipe from a dict, ignoring unknown keys for forward compat."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in (data or {}).items() if k in known}
        return cls(**clean)


def default_recipe() -> MarkupRecipe:
    """Return a fresh default recipe tuned for GameFAQs-style scripts."""
    return MarkupRecipe()
