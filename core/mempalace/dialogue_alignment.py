"""Headless marked-script to game-message alignment engine.

Identity-preserving barrel: implementation lives in `core.mempalace.alignment`.
Existing `from core.mempalace.dialogue_alignment import ...` imports keep working.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    raise SystemExit(main())
