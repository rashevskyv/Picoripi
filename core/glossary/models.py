"""Glossary status constants, placeholders, and dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# Lifecycle status of a glossary entry (roadmap section 3). An empty string is a
# legacy entry with no explicit status, treated as already usable.
STATUS_SEEDED = "seeded"            # term only
STATUS_FRAGMENTS = "fragments"      # description fragments accumulated
STATUS_SYNTHESIZED = "synthesized"  # fragments folded into one description
STATUS_TRANSLATED = "translated"    # one or more translation variants proposed
STATUS_CONFIRMED = "confirmed"      # user picked the active translation

# Descriptions are written before a translation is chosen, so a note must not
# bake in one particular rendering of the term: the build prompts write this
# placeholder wherever the term itself is named, and it is substituted with
# whichever variant the user settles on.
#
# The substitution is literal. Ukrainian and other Slavic targets decline nouns,
# so the prompts ask for phrasing that keeps the placeholder in the nominative;
# declining an arbitrary noun phrase by rule is not something this layer can do
# honestly. A note that needs the term in an oblique case should be rewritten
# (the AI Variations button) rather than patched by string surgery.
TERM_PLACEHOLDER = "{{TERM}}"

# Statuses whose entries still await a confirmed human decision; the UI
# highlights these as unconfirmed (roadmap section 7).
UNCONFIRMED_STATUSES = frozenset(
    {STATUS_SEEDED, STATUS_FRAGMENTS, STATUS_SYNTHESIZED, STATUS_TRANSLATED}
)


@dataclass(frozen=True)
class DescriptionFragment:
    """One description fragment for a term, tagged with its source row."""

    text: str
    block_idx: int = -1
    string_idx: int = -1


@dataclass(frozen=True)
class TranslationVariant:
    """A candidate translation with the rationale the AI gave for it."""

    translation: str
    rationale: str = ""


@dataclass(frozen=True)
class GlossaryEntry:
    """Single glossary record."""

    original: str
    translation: str
    notes: str = ""
    section: Optional[str] = None
    profiled: bool = False
    status: str = ""
    icon: str = ""
    fragments: Tuple[DescriptionFragment, ...] = ()
    translation_variants: Tuple[TranslationVariant, ...] = ()
    # The term itself is a stand-in, not a name: an actor id like "CLERK_B" or
    # a voice code the game data produced. It groups the character's lines
    # correctly and means nothing to a reader, so it is shown as provisional
    # until a real name is decided for it.
    provisional: bool = False
    # What the AI read out of the description as this character's likely real
    # name, with how sure it was. A suggestion for a person to accept or reject
    # -- never applied on its own, because a wrong name here would be stamped
    # onto every line the character speaks.
    suggested_name: str = ""
    suggested_name_evidence: str = ""

    def is_valid(self) -> bool:
        """Whether the entry should load and appear.

        A legacy entry needs both a term and a translation. A seeded entry has a
        term and a lifecycle status but no translation yet (roadmap section 6),
        so a status alone also makes it valid.
        """
        return bool(self.original) and (bool(self.translation) or bool(self.status))

    @property
    def is_unconfirmed(self) -> bool:
        """True while the entry still awaits a confirmed human decision."""
        return self.status in UNCONFIRMED_STATUSES

@dataclass(frozen=True)
class GlossaryMatch:
    """Result of matching a glossary entry inside text."""

    entry: GlossaryEntry
    start: int
    end: int


OCC_MENTION = "mention"
OCC_SPOKEN = "spoken"


@dataclass(frozen=True)
class GlossaryOccurrence:
    """Specific occurrence of a glossary entry in project data.

    ``mention`` — the term is spelled in the line (someone names or addresses
    them). ``spoken`` — this is a line the character themselves says, even if
    the label never appears in the text.
    """

    entry: GlossaryEntry
    block_idx: int
    string_idx: int
    line_idx: int
    start: int
    end: int
    line_text: str
    kind: str = OCC_MENTION
