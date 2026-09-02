"""Story timeline dataclasses and exceptions."""

from __future__ import annotations

from dataclasses import dataclass


class StoryTimelineConflictError(RuntimeError):
    """Raised when source synchronization would remove a manual DB decision."""

    def __init__(
        self,
        source_stable_id: str,
        manual_stable_id: str,
        *,
        conflict_id: int | None = None,
    ) -> None:
        self.source_stable_id = source_stable_id
        self.manual_stable_id = manual_stable_id
        self.conflict_id = conflict_id
        super().__init__(str(self))

    def __str__(self) -> str:
        prefix = f"Conflict record #{self.conflict_id}: " if self.conflict_id else ""
        return (
            f"{prefix}cannot remove {self.source_stable_id!r}; manual node "
            f"{self.manual_stable_id!r} depends on it."
        )

@dataclass(frozen=True)
class StoryNode:
    stable_id: str
    parent_stable_id: str | None
    node_type: str
    order_index: int
    title: str | None
    text: str | None
    start_line: int
    end_line: int
    start_column: int | None
    end_column: int | None
    origin: str
    source_payload: str
    source_version: int

@dataclass(frozen=True)
class StoryTimelineSyncResult:
    document_id: int
    inserted_or_updated: int
    removed: int
    reference_items: int = 0
    reference_items_removed: int = 0

@dataclass(frozen=True)
class ReferenceItem:
    stable_id: str
    order_index: int
    name: str
    description: str
    start_line: int
    end_line: int
    origin: str
    source_payload: str
    source_version: int

@dataclass(frozen=True)
class ReferenceItemRecord:
    id: int
    stable_id: str
    document_id: int
    order_index: int
    name: str
    description: str
    start_line: int | None
    end_line: int | None

@dataclass(frozen=True)
class StoryNodeRecord:
    id: int
    stable_id: str
    document_id: int
    parent_id: int | None
    node_type: str
    order_index: int
    title: str | None
    text: str | None
    start_line: int | None
    end_line: int | None

@dataclass(frozen=True)
class StoryTimelinePosition:
    index: int
    total: int
    progress: float
    path: tuple[StoryNodeRecord, ...]

@dataclass(frozen=True)
class StoryVirtualMapping:
    """One physical game string exposed through a derived story folder."""

    game_block_id: str
    game_string_id: str
    string_index: int

@dataclass(frozen=True)
class StoryVirtualFolder:
    """A selectable Act, Chapter, or Scene in the main project tree."""

    id: int
    node_type: str
    title: str
    children: tuple["StoryVirtualFolder", ...]
    mappings: tuple[StoryVirtualMapping, ...]

@dataclass(frozen=True)
class StoryVirtualSpeaker:
    """A selectable speaker folder derived from marked script ancestry."""

    name: str
    mappings: tuple[StoryVirtualMapping, ...]

@dataclass(frozen=True)
class StoryVirtualProjection:
    """Read-only projection of saved story context for the translation UI."""

    document_id: int | None
    roots: tuple[StoryVirtualFolder, ...]
    speakers: tuple[StoryVirtualSpeaker, ...]

@dataclass(frozen=True)
class StoryStringContext:
    """Saved virtual destinations for one physical game string."""

    structure_id: int | None
    structure_path: tuple[str, ...]
    speaker_name: str | None

@dataclass(frozen=True)
class StorySyncConflictRecord:
    id: int
    document_id: int | None
    source_path: str
    source_hash: str
    conflict_type: str
    source_stable_id: str
    manual_stable_id: str
    details: str
    status: str
    created_at: str
    resolved_at: str | None
