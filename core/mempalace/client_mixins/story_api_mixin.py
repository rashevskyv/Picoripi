"""Story timeline, dialogue mapping, and character profile API."""
from typing import Optional

from core.mempalace.character_profiles import (
    get_character_profile,
    get_character_profiles,
    replace_character_profiles,
)
from core.mempalace.dialogue_alignment import lock_relation_choice
from core.mempalace.dialogue_mapping import (
    DialogueMappingInput,
    DialogueMatchSummary,
    DialogueMappingRecord,
    DialogueMappingState,
    DialogueMappingUpsertResult,
    get_dialogue_mapping_state,
    get_dialogue_mappings,
    GameString,
    match_game_strings,
    upsert_dialogue_mapping,
)
from core.mempalace.semantic_timeline import (
    get_story_event_for_game_string,
    get_story_events,
    replace_story_event_contexts,
)
from core.mempalace.story_timeline import (
    ReferenceItemRecord,
    StoryNodeRecord,
    StorySyncConflictRecord,
    StoryTimelineConflictError,
    StoryTimelinePosition,
    StoryTimelineSyncResult,
    StoryVirtualProjection,
    StoryStringContext,
    get_reference_item_context,
    get_reference_items,
    get_story_ancestors,
    get_story_descendants,
    get_story_document_id,
    get_story_document_source_path,
    get_story_mappings_for_node,
    get_story_navigation_target,
    get_story_neighbors,
    get_story_node,
    get_story_speakers_for_game_string,
    get_story_string_contexts,
    get_story_sync_conflicts,
    get_story_timeline,
    get_story_timeline_position,
    get_story_virtual_projection,
    record_story_sync_conflict,
    resolve_story_sync_conflict,
    sync_hierarchy_project,
)


class StoryApiMixin:
    """Story timeline, dialogue mapping, and character profile API."""
    def sync_story_timeline(self, project) -> StoryTimelineSyncResult:
        """Synchronize a validated Markup Studio project into the local story tree."""
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Local MemPalace database is unavailable.")
        try:
            result = sync_hierarchy_project(conn, project)
        except StoryTimelineConflictError as exc:
            exc.conflict_id = record_story_sync_conflict(conn, project, exc)
            conn.commit()
            raise
        conn.commit()
        return result

    def get_reference_items(self, document_id: int) -> tuple[ReferenceItemRecord, ...]:
        """Return imported non-dialogue item catalogue entries in source order."""
        conn = self._get_connection()
        return get_reference_items(conn, document_id) if conn else ()

    def get_story_sync_conflicts(
        self,
        source_path: str,
        *,
        status: str = "open",
    ) -> tuple[StorySyncConflictRecord, ...]:
        conn = self._get_connection()
        return get_story_sync_conflicts(conn, source_path, status=status) if conn else ()

    def upsert_dialogue_mapping(
        self,
        item: DialogueMappingInput,
        *,
        allow_locked_override: bool = False,
    ) -> DialogueMappingUpsertResult:
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Local MemPalace database is unavailable.")
        result = upsert_dialogue_mapping(
            conn,
            item,
            allow_locked_override=allow_locked_override,
        )
        conn.commit()
        return result

    def get_dialogue_mappings(
        self,
        document_id: int,
        *,
        review_status: str | None = None,
    ) -> tuple[DialogueMappingRecord, ...]:
        conn = self._get_connection()
        return (
            get_dialogue_mappings(conn, document_id, review_status=review_status)
            if conn else ()
        )

    def get_dialogue_mapping_state(self, document_id: int) -> DialogueMappingState:
        """Read saved context-search progress for reopening the Builder."""
        conn = self._get_connection()
        if conn is None:
            return DialogueMappingState(0, 0, 0, 0, 0)
        return get_dialogue_mapping_state(conn, document_id)

    def match_game_strings(
        self,
        document_id: int,
        game_strings: list[GameString],
        *,
        progress_callback=None,
        cancel_check=None,
    ) -> DialogueMatchSummary:
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Local MemPalace database is unavailable.")
        result = match_game_strings(
            conn,
            document_id,
            game_strings,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        conn.commit()
        return result

    def lock_dialogue_relation_choice(
        self,
        document_id: int,
        game_block_id: str,
        string_index: int,
        dialogue_node_id: int | None,
    ) -> int:
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Local MemPalace database is unavailable.")
        return lock_relation_choice(
            conn,
            document_id,
            game_block_id,
            string_index,
            dialogue_node_id,
        )

    def resolve_story_sync_conflict(self, conflict_id: int) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        resolved = resolve_story_sync_conflict(conn, conflict_id)
        conn.commit()
        return resolved

    def get_story_node(self, document_id: int, stable_id: str) -> Optional[StoryNodeRecord]:
        conn = self._get_connection()
        return get_story_node(conn, document_id, stable_id) if conn else None

    def get_story_document_id(self, source_path: str) -> Optional[int]:
        conn = self._get_connection()
        return get_story_document_id(conn, source_path) if conn else None

    def get_story_timeline(self, document_id: int) -> tuple[StoryNodeRecord, ...]:
        conn = self._get_connection()
        return get_story_timeline(conn, document_id) if conn else ()

    def replace_story_event_contexts(self, document_id, contexts, source_hash) -> int:
        conn = self._get_connection()
        return replace_story_event_contexts(conn, document_id, contexts, source_hash) if conn else 0

    def get_story_event_for_game_string(
        self, game_block_id: str, string_index: int, document_id: int | None = None
    ):
        conn = self._get_connection()
        return get_story_event_for_game_string(
            conn, game_block_id, string_index, document_id
        ) if conn else None

    def get_story_events(self, document_id: int):
        conn = self._get_connection()
        return get_story_events(conn, document_id) if conn else ()

    def replace_character_profiles(self, document_id, profiles, source_hash) -> int:
        conn = self._get_connection()
        return replace_character_profiles(conn, document_id, profiles, source_hash) if conn else 0

    def get_character_profile(
        self, speaker_name: str, document_id: int | None = None
    ):
        conn = self._get_connection()
        return get_character_profile(conn, speaker_name, document_id) if conn else None

    def get_character_profiles(self, document_id: int):
        conn = self._get_connection()
        return get_character_profiles(conn, document_id) if conn else ()

    def get_character_profiles_for_game_string(
        self, game_block_id: str, string_index: int, document_id: int | None = None
    ):
        names = self.get_story_speakers_for_game_string(
            game_block_id, string_index, document_id
        )
        if not names:
            target = self.get_story_navigation_target(
                game_block_id, string_index, document_id
            )
            if target is not None:
                names = tuple(
                    (node.title or node.text or "").strip()
                    for node in self.get_story_ancestors(
                        target.document_id, target.stable_id
                    )
                    if node.node_type == "speaker"
                    and (node.title or node.text or "").strip()
                )
        return tuple(
            profile for name in names
            if (profile := self.get_character_profile(name, document_id)) is not None
        )

    def get_story_virtual_projection(
        self,
        document_id: int | None = None,
    ) -> StoryVirtualProjection:
        """Return folders derived from the current normalized story and saved links."""
        conn = self._get_connection()
        if conn is None:
            return StoryVirtualProjection(None, (), ())
        return get_story_virtual_projection(conn, document_id)

    def get_story_speakers_for_game_string(
        self,
        game_block_id: str,
        string_index: int,
        document_id: int | None = None,
    ) -> tuple[str, ...]:
        """Return authoritative Markup Studio speakers for one game string."""
        conn = self._get_connection()
        if conn is None:
            return ()
        return get_story_speakers_for_game_string(
            conn,
            game_block_id,
            string_index,
            document_id,
        )

    def get_story_navigation_target(
        self,
        game_block_id: str,
        string_index: int,
        document_id: int | None = None,
    ) -> Optional[StoryNodeRecord]:
        """Return the marked-script node currently linked to a game string."""
        conn = self._get_connection()
        if conn is None:
            return None
        return get_story_navigation_target(
            conn, game_block_id, string_index, document_id
        )

    def get_story_string_contexts(
        self,
        game_block_id: str,
        string_index: int,
        document_id: int | None = None,
    ) -> tuple[StoryStringContext, ...]:
        conn = self._get_connection()
        return (
            get_story_string_contexts(
                conn, game_block_id, string_index, document_id
            ) if conn else ()
        )

    def get_story_mappings_for_node(
        self, document_id: int, stable_id: str
    ):
        conn = self._get_connection()
        return get_story_mappings_for_node(conn, document_id, stable_id) if conn else ()

    def get_reference_item_context(self, document_id: int, item_name: str):
        conn = self._get_connection()
        return get_reference_item_context(conn, document_id, item_name) if conn else None

    def get_story_document_source_path(self, document_id: int | None = None) -> str:
        conn = self._get_connection()
        return get_story_document_source_path(conn, document_id) if conn else ""

    def get_story_ancestors(self, document_id: int, stable_id: str) -> tuple[StoryNodeRecord, ...]:
        conn = self._get_connection()
        return get_story_ancestors(conn, document_id, stable_id) if conn else ()

    def get_story_descendants(self, document_id: int, stable_id: str) -> tuple[StoryNodeRecord, ...]:
        conn = self._get_connection()
        return get_story_descendants(conn, document_id, stable_id) if conn else ()

    def get_story_neighbors(
        self,
        document_id: int,
        stable_id: str,
    ) -> tuple[Optional[StoryNodeRecord], Optional[StoryNodeRecord]]:
        conn = self._get_connection()
        return get_story_neighbors(conn, document_id, stable_id) if conn else (None, None)

    def get_story_timeline_position(
        self,
        document_id: int,
        stable_id: str,
    ) -> Optional[StoryTimelinePosition]:
        conn = self._get_connection()
        return get_story_timeline_position(conn, document_id, stable_id) if conn else None
