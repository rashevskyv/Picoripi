"""Game-string to dialogue-node mapping package."""

from core.mempalace.mapping.models import (
    DialogueCandidate,
    DialogueMappingCancelled,
    DialogueMappingInput,
    DialogueMappingRecord,
    DialogueMappingState,
    DialogueMappingUpsertResult,
    DialogueMatchSummary,
    GameString,
)
from core.mempalace.mapping.match import (
    canonicalize_dialogue_text,
    match_game_strings,
)
from core.mempalace.mapping.persist import (
    get_dialogue_mapping_state,
    get_dialogue_mappings,
    upsert_dialogue_mapping,
)

__all__ = [
    "DialogueCandidate",
    "DialogueMappingCancelled",
    "DialogueMappingInput",
    "DialogueMappingRecord",
    "DialogueMappingState",
    "DialogueMappingUpsertResult",
    "DialogueMatchSummary",
    "GameString",
    "canonicalize_dialogue_text",
    "get_dialogue_mapping_state",
    "get_dialogue_mappings",
    "match_game_strings",
    "upsert_dialogue_mapping",
]
