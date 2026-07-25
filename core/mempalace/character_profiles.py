"""Translation-oriented AI profiles for normalized story speakers."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Iterable


def speaker_key(name: str) -> str:
    return " ".join(str(name or "").casefold().split())


@dataclass(frozen=True)
class StoryCharacterProfile:
    document_id: int
    speaker_name: str
    role: str
    personality: str
    speech_style: str
    vocabulary: str
    relationships: str
    address_and_grammar: str
    translation_advice: str
    evidence_notes: str
    dialogue_count: int
    source_hash: str

    def to_prompt_text(self) -> str:
        parts = [f"Character Voice Profile — {self.speaker_name}:"]
        labels = (
            ("Role", self.role),
            ("Personality", self.personality),
            ("Speech style", self.speech_style),
            ("Vocabulary and verbal habits", self.vocabulary),
            ("Relationships and social position", self.relationships),
            ("Address and grammar", self.address_and_grammar),
            ("Translation direction", self.translation_advice),
            ("Evidence limits", self.evidence_notes),
        )
        parts.extend(f"{label}: {value}" for label, value in labels if value)
        return "\n".join(parts)


def replace_character_profiles(
    conn: sqlite3.Connection,
    document_id: int,
    profiles: Iterable[dict],
    source_hash: str,
) -> int:
    rows = list(profiles)
    with conn:
        conn.execute(
            "DELETE FROM story_character_profiles WHERE document_id = ?",
            (document_id,),
        )
        conn.executemany(
            """
            INSERT INTO story_character_profiles (
                document_id, speaker_key, speaker_name, role, personality,
                speech_style, vocabulary, relationships, address_and_grammar,
                translation_advice, evidence_notes, dialogue_count, source_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document_id,
                    speaker_key(row["speaker_name"]),
                    str(row["speaker_name"]),
                    str(row.get("role") or ""),
                    str(row.get("personality") or ""),
                    str(row.get("speech_style") or ""),
                    str(row.get("vocabulary") or ""),
                    str(row.get("relationships") or ""),
                    str(row.get("address_and_grammar") or ""),
                    str(row.get("translation_advice") or ""),
                    str(row.get("evidence_notes") or ""),
                    int(row.get("dialogue_count") or 0),
                    source_hash,
                )
                for row in rows
            ],
        )
    return len(rows)


def get_character_profile(
    conn: sqlite3.Connection,
    speaker_name: str,
    document_id: int | None = None,
) -> StoryCharacterProfile | None:
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return None
    row = conn.execute(
        """
        SELECT document_id, speaker_name, role, personality, speech_style,
               vocabulary, relationships, address_and_grammar,
               translation_advice, evidence_notes, dialogue_count, source_hash
        FROM story_character_profiles
        WHERE document_id = ? AND speaker_key = ?
        """,
        (document_id, speaker_key(speaker_name)),
    ).fetchone()
    return StoryCharacterProfile(*row) if row else None


def get_character_profiles(
    conn: sqlite3.Connection, document_id: int
) -> tuple[StoryCharacterProfile, ...]:
    rows = conn.execute(
        """
        SELECT document_id, speaker_name, role, personality, speech_style,
               vocabulary, relationships, address_and_grammar,
               translation_advice, evidence_notes, dialogue_count, source_hash
        FROM story_character_profiles
        WHERE document_id = ? ORDER BY speaker_name COLLATE NOCASE
        """,
        (document_id,),
    ).fetchall()
    return tuple(StoryCharacterProfile(*row) for row in rows)
