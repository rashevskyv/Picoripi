"""Marked-script to game-message alignment package."""

from core.mempalace.alignment.models import GameMessage, MarkedDialogue, Proposal
from core.mempalace.alignment.normalize import (
    classify_alignment_exclusions,
    infer_tag_equivalents,
    is_stage_direction,
    normalize_tokens,
)
from core.mempalace.alignment.persist import (
    load_dialogues,
    load_messages,
    lock_relation_choice,
    main,
    save_relations,
)
from core.mempalace.alignment.simulate import simulate

__all__ = [
    "GameMessage",
    "MarkedDialogue",
    "Proposal",
    "classify_alignment_exclusions",
    "infer_tag_equivalents",
    "is_stage_direction",
    "load_dialogues",
    "load_messages",
    "lock_relation_choice",
    "main",
    "normalize_tokens",
    "save_relations",
    "simulate",
]
