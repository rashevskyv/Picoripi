"""Alignment data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkedDialogue:
    node_id: int
    order: int
    text: str
    speaker: str
    start_line: int | None


@dataclass(frozen=True)
class GameMessage:
    message_id: int
    block_id: str
    block_name: str
    string_index: int
    stable_id: str
    text: str


@dataclass(frozen=True)
class Proposal:
    node_id: int
    node_order: int
    score: float
    game_coverage: float
    phrase_locality: float
    retrieval_score: float
    script_ranges: tuple[tuple[int, int], ...]
