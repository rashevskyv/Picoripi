"""Dialogue mapping data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueMappingInput:
    document_id: int
    game_block_id: str
    game_block_name: str
    string_index: int
    game_string_id: str
    source_text_snapshot: str
    dialogue_node_id: int | None
    match_method: str
    confidence: float
    review_status: str
    reviewed_by: str | None = None
    conflict_reason: str | None = None
    locked: bool = False


@dataclass(frozen=True)
class DialogueMappingRecord:
    id: int
    document_id: int
    game_block_id: str
    game_block_name: str
    string_index: int
    game_string_id: str
    dialogue_node_id: int | None
    source_text_snapshot: str
    match_method: str
    confidence: float
    review_status: str
    reviewed_by: str | None
    reviewed_at: str | None
    conflict_reason: str | None
    locked: bool


@dataclass(frozen=True)
class DialogueMappingUpsertResult:
    mapping: DialogueMappingRecord
    preserved_locked_mapping: bool


@dataclass(frozen=True)
class DialogueMappingState:
    """Persisted UI-facing state of one document's context search."""

    total: int
    automatic: int
    reviewed: int
    needs_review: int
    context_links: int

    @property
    def has_results(self) -> bool:
        return self.total > 0 or self.context_links > 0

    @property
    def is_complete(self) -> bool:
        return self.has_results and self.needs_review == 0


@dataclass(frozen=True)
class GameString:
    block_id: str
    block_name: str
    string_index: int
    stable_id: str
    text: str


@dataclass(frozen=True)
class DialogueCandidate:
    node_id: int
    stable_id: str
    text: str
    identifiers: tuple[str, ...]
    canonical_text: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class DialogueMatchSummary:
    total: int
    exact_id: int
    exact_text: int
    auto_fuzzy: int
    needs_review: int
    unmatched: int
    preserved_locked: int
    marked_dialogues: int = 0
    located_dialogues: int = 0
    inferred_tag_equivalents: tuple[tuple[str, str], ...] = ()


class DialogueMappingCancelled(RuntimeError):
    pass
