"""Versioned, additive schema migrations for the local MemPalace database."""

import sqlite3


LATEST_SCHEMA_VERSION = 8


def migrate_mempalace_schema(conn: sqlite3.Connection) -> None:
    """Apply additive MemPalace migrations without modifying legacy tables."""
    savepoint = "mempalace_schema_migration"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mempalace_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        applied = {
            row[0]
            for row in conn.execute("SELECT version FROM mempalace_schema_migrations")
        }
        if 1 not in applied:
            _migrate_story_timeline_v1(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (1,),
            )
        if 2 not in applied:
            _migrate_story_conflicts_v2(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (2,),
            )
        if 3 not in applied:
            _migrate_dialogue_mappings_v3(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (3,),
            )
        if 4 not in applied:
            _migrate_dialogue_relations_v4(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (4,),
            )
        if 5 not in applied:
            _migrate_reference_items_v5(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (5,),
            )
        if 6 not in applied:
            _migrate_semantic_timeline_v6(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (6,),
            )
        if 7 not in applied:
            _migrate_character_profiles_v7(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (7,),
            )
        if 8 not in applied:
            _migrate_timeline_interactions_v8(conn)
            conn.execute(
                "INSERT INTO mempalace_schema_migrations (version) VALUES (?)",
                (8,),
            )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def _migrate_story_timeline_v1(conn: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE story_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL UNIQUE,
            source_hash TEXT NOT NULL,
            markup_format TEXT NOT NULL,
            markup_version INTEGER NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE story_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stable_id TEXT NOT NULL,
            document_id INTEGER NOT NULL,
            parent_id INTEGER,
            node_type TEXT NOT NULL CHECK (
                node_type IN (
                    'act', 'chapter', 'scene', 'action', 'context',
                    'speaker', 'dialogue', 'narrator'
                )
            ),
            order_index INTEGER NOT NULL CHECK (order_index >= 0),
            title TEXT,
            text TEXT,
            start_line INTEGER,
            end_line INTEGER,
            start_column INTEGER,
            end_column INTEGER,
            origin TEXT NOT NULL DEFAULT 'markup_studio',
            approved INTEGER NOT NULL DEFAULT 1 CHECK (approved IN (0, 1)),
            source_payload TEXT,
            source_version INTEGER NOT NULL DEFAULT 1,
            UNIQUE(document_id, stable_id),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(parent_id) REFERENCES story_nodes(id) ON DELETE CASCADE,
            CHECK (end_line IS NULL OR start_line IS NULL OR end_line >= start_line),
            CHECK (end_column IS NULL OR start_column IS NULL OR end_column >= start_column)
        )
        """,
        """
        CREATE INDEX story_nodes_parent_order_idx
            ON story_nodes(document_id, parent_id, order_index)
        """,
        """
        CREATE INDEX story_nodes_type_idx
            ON story_nodes(document_id, node_type)
        """,
        """
        CREATE INDEX story_documents_hash_idx
            ON story_documents(source_hash)
        """,
    )
    for statement in statements:
        conn.execute(statement)


def _migrate_story_conflicts_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE story_sync_conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            source_path TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            conflict_type TEXT NOT NULL,
            source_stable_id TEXT NOT NULL,
            manual_stable_id TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'resolved')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX story_sync_conflicts_source_status_idx
            ON story_sync_conflicts(source_path, status, created_at)
        """
    )


def _migrate_dialogue_mappings_v3(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE story_dialogue_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            game_block_id TEXT NOT NULL,
            game_block_name TEXT NOT NULL,
            string_index INTEGER NOT NULL CHECK (string_index >= 0),
            game_string_id TEXT NOT NULL,
            dialogue_node_id INTEGER,
            source_text_snapshot TEXT NOT NULL,
            match_method TEXT NOT NULL CHECK (
                match_method IN ('unmatched', 'exact_id', 'exact_text', 'fuzzy', 'manual')
            ),
            confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
            review_status TEXT NOT NULL CHECK (
                review_status IN ('unmatched', 'matched', 'needs_review', 'approved', 'rejected')
            ),
            reviewed_by TEXT,
            reviewed_at TEXT,
            conflict_reason TEXT,
            locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, game_block_id, string_index),
            UNIQUE(document_id, game_string_id),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(dialogue_node_id) REFERENCES story_nodes(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX story_dialogue_mappings_node_idx
            ON story_dialogue_mappings(document_id, dialogue_node_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX story_dialogue_mappings_review_idx
            ON story_dialogue_mappings(document_id, review_status, locked)
        """
    )


def _migrate_dialogue_relations_v4(conn: sqlite3.Connection) -> None:
    """Store many-to-many links between reusable game strings and marked contexts."""
    conn.execute(
        """
        CREATE TABLE story_dialogue_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            game_block_id TEXT NOT NULL,
            game_block_name TEXT NOT NULL,
            string_index INTEGER NOT NULL CHECK (string_index >= 0),
            game_string_id TEXT NOT NULL,
            dialogue_node_id INTEGER NOT NULL,
            source_text_snapshot TEXT NOT NULL,
            relation_method TEXT NOT NULL CHECK (
                relation_method IN ('exact_or_contained', 'fuzzy_window', 'manual')
            ),
            score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
            game_coverage REAL NOT NULL CHECK (
                game_coverage >= 0.0 AND game_coverage <= 1.0
            ),
            primary_link INTEGER NOT NULL DEFAULT 0 CHECK (primary_link IN (0, 1)),
            relation_status TEXT NOT NULL CHECK (
                relation_status IN ('supported', 'needs_review', 'approved', 'rejected')
            ),
            locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, game_block_id, string_index, dialogue_node_id),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(dialogue_node_id) REFERENCES story_nodes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX story_dialogue_relations_game_idx
            ON story_dialogue_relations(document_id, game_block_id, string_index)
        """
    )
    conn.execute(
        """
        CREATE INDEX story_dialogue_relations_node_idx
            ON story_dialogue_relations(document_id, dialogue_node_id)
        """
    )


def _migrate_reference_items_v5(conn: sqlite3.Connection) -> None:
    """Store non-dialogue item catalogue entries imported from Markup Studio."""
    conn.execute(
        """
        CREATE TABLE story_reference_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stable_id TEXT NOT NULL,
            document_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL CHECK (order_index >= 0),
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            start_line INTEGER,
            end_line INTEGER,
            origin TEXT NOT NULL DEFAULT 'markup_studio',
            source_payload TEXT,
            source_version INTEGER NOT NULL DEFAULT 1,
            UNIQUE(document_id, stable_id),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE,
            CHECK (end_line IS NULL OR start_line IS NULL OR end_line >= start_line)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX story_reference_items_document_order_idx
            ON story_reference_items(document_id, order_index)
        """
    )


def _migrate_semantic_timeline_v6(conn: sqlite3.Connection) -> None:
    """Store AI story events directly against normalized dialogue nodes."""
    conn.execute(
        """
        CREATE TABLE story_timeline_contexts (
            document_id INTEGER NOT NULL,
            dialogue_node_id INTEGER NOT NULL,
            event_order INTEGER NOT NULL CHECK (event_order >= 0),
            event_title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            participants_json TEXT NOT NULL DEFAULT '[]',
            previous_event TEXT NOT NULL DEFAULT '',
            next_event TEXT NOT NULL DEFAULT '',
            source_hash TEXT NOT NULL,
            analysis_version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(document_id, dialogue_node_id),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(dialogue_node_id) REFERENCES story_nodes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX story_timeline_contexts_order_idx
            ON story_timeline_contexts(document_id, event_order, dialogue_node_id)
        """
    )


def _migrate_character_profiles_v7(conn: sqlite3.Connection) -> None:
    """Store translation-oriented profiles for normalized story speakers."""
    conn.execute(
        """
        CREATE TABLE story_character_profiles (
            document_id INTEGER NOT NULL,
            speaker_key TEXT NOT NULL,
            speaker_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            personality TEXT NOT NULL DEFAULT '',
            speech_style TEXT NOT NULL DEFAULT '',
            vocabulary TEXT NOT NULL DEFAULT '',
            relationships TEXT NOT NULL DEFAULT '',
            address_and_grammar TEXT NOT NULL DEFAULT '',
            translation_advice TEXT NOT NULL DEFAULT '',
            evidence_notes TEXT NOT NULL DEFAULT '',
            dialogue_count INTEGER NOT NULL DEFAULT 0 CHECK (dialogue_count >= 0),
            source_hash TEXT NOT NULL,
            analysis_version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(document_id, speaker_key),
            FOREIGN KEY(document_id) REFERENCES story_documents(id) ON DELETE CASCADE
        )
        """
    )


def _migrate_timeline_interactions_v8(conn: sqlite3.Connection) -> None:
    """Add event-local character dynamics to semantic timeline contexts."""
    conn.execute(
        "ALTER TABLE story_timeline_contexts "
        "ADD COLUMN interactions_json TEXT NOT NULL DEFAULT '[]'"
    )
    # Existing summaries predate event-local interactions. They are derived AI
    # data, so invalidate them instead of presenting incomplete context as fresh.
    conn.execute("DELETE FROM story_timeline_contexts")
