"""Serialize / restore StoryVirtualProjection for durable sessions."""

from __future__ import annotations

from core.mempalace.timeline.models import (
    StoryVirtualFolder,
    StoryVirtualMapping,
    StoryVirtualProjection,
    StoryVirtualSpeaker,
)


def story_virtual_projection_to_dict(projection: StoryVirtualProjection) -> dict:
    """Serialize a virtual Story projection for durable project sessions."""
    def mapping_to_dict(mapping: StoryVirtualMapping) -> dict:
        return {
            "game_block_id": mapping.game_block_id,
            "game_string_id": mapping.game_string_id,
            "string_index": mapping.string_index,
        }

    def folder_to_dict(folder: StoryVirtualFolder) -> dict:
        return {
            "id": folder.id,
            "node_type": folder.node_type,
            "title": folder.title,
            "children": [folder_to_dict(child) for child in folder.children],
            "mappings": [mapping_to_dict(mapping) for mapping in folder.mappings],
        }

    return {
        "document_id": projection.document_id,
        "roots": [folder_to_dict(folder) for folder in projection.roots],
        "speakers": [
            {
                "name": speaker.name,
                "mappings": [mapping_to_dict(mapping) for mapping in speaker.mappings],
            }
            for speaker in projection.speakers
        ],
    }

def story_virtual_projection_from_dict(value: dict) -> StoryVirtualProjection | None:
    """Restore a virtual Story projection from a session-safe dictionary."""
    if not isinstance(value, dict):
        return None

    def mapping_from_dict(mapping: dict) -> StoryVirtualMapping:
        return StoryVirtualMapping(
            game_block_id=str(mapping.get("game_block_id", "")),
            game_string_id=str(mapping.get("game_string_id", "")),
            string_index=int(mapping.get("string_index", -1)),
        )

    def folder_from_dict(folder: dict) -> StoryVirtualFolder:
        return StoryVirtualFolder(
            id=int(folder["id"]),
            node_type=str(folder.get("node_type", "chapter")),
            title=str(folder.get("title", "")),
            children=tuple(folder_from_dict(child) for child in folder.get("children", [])),
            mappings=tuple(mapping_from_dict(mapping) for mapping in folder.get("mappings", [])),
        )

    try:
        return StoryVirtualProjection(
            document_id=value.get("document_id"),
            roots=tuple(folder_from_dict(folder) for folder in value.get("roots", [])),
            speakers=tuple(
                StoryVirtualSpeaker(
                    name=str(speaker.get("name", "")),
                    mappings=tuple(
                        mapping_from_dict(mapping)
                        for mapping in speaker.get("mappings", [])
                    ),
                )
                for speaker in value.get("speakers", [])
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None
