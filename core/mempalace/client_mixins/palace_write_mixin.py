"""Wing/room/drawer/relation write helpers."""
import json
import sqlite3
import urllib.request
from typing import Any, Dict, Optional

from utils.logging_utils import log_debug, log_error, log_info, log_warning


class PalaceWriteMixin:
    """Wing/room/drawer/relation write helpers."""
    def has_room(self, wing_name: str, room_name: str) -> bool:
        """Check if visual scene context drawer already exists for a room in local database."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ? AND r.name = ? AND d.name = 'visual_scene_context'
                """, (wing_name, room_name))
                row = cursor.fetchone()
                return bool(row)
            except Exception as e:
                log_error(f"Local DB error in has_room: {e}")
        return False

    def add_wing(self, name: str, description: str = "", conn: Optional[sqlite3.Connection] = None) -> bool:
        """Create a new top-level container (Wing) for the project."""
        log_info(f"Adding Wing: {name}")
        
        # 1. Try external server first
        if self.is_server_available():
            try:
                url = f"{self.server_url}/wings"
                data = json.dumps({"name": name, "description": description}).encode('utf-8')
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in (200, 201):
                        log_info(f"Successfully added Wing '{name}' to external MemPalace server.")
            except Exception as e:
                log_warning(f"Failed to write to external MemPalace server: {e}. Falling back to local database.")

        # 2. Write to local SQLite database as fallback or local-first storage
        local_conn = conn if conn is not None else self._get_connection()
        if local_conn:
            try:
                cursor = local_conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO wings (name, description) VALUES (?, ?)",
                    (name, description)
                )
                if conn is None:
                    local_conn.commit()
                return True
            except Exception as e:
                log_error(f"Local DB error in add_wing: {e}")
        return False

    def add_room(self, wing_name: str, room_name: str, description: str = "", conn: Optional[sqlite3.Connection] = None) -> bool:
        """Add a specific room (location/scene category) to a wing."""
        log_info(f"Adding Room: {room_name} to Wing: {wing_name}")
        
        # 1. Try external server first
        if self.is_server_available():
            try:
                url = f"{self.server_url}/wings/{wing_name}/rooms"
                data = json.dumps({"name": room_name, "description": description}).encode('utf-8')
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in (200, 201):
                        log_info(f"Successfully added Room '{room_name}' to external MemPalace.")
            except Exception as e:
                log_warning(f"Failed to write Room to external MemPalace: {e}")

        # 2. Write to local SQLite
        local_conn = conn if conn is not None else self._get_connection()
        if local_conn:
            try:
                cursor = local_conn.cursor()
                # Find wing ID
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                row = cursor.fetchone()
                if not row:
                    # Create wing implicitly
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = row[0]
                
                cursor.execute(
                    "INSERT OR IGNORE INTO rooms (wing_id, name, description) VALUES (?, ?, ?)",
                    (wing_id, room_name, description)
                )
                if conn is None:
                    local_conn.commit()
                return True
            except Exception as e:
                log_error(f"Local DB error in add_room: {e}")
        return False

    def add_drawer(self, wing_name: str, room_name: str, drawer_name: str, content: str, metadata: Dict[str, Any] = None, conn: Optional[sqlite3.Connection] = None) -> bool:
        """Add a verbatim transcription or scene description (Drawer) to a room."""
        meta_str = json.dumps(metadata or {})
        log_debug(f"Adding Drawer '{drawer_name}' to '{wing_name}/{room_name}'")

        # 1. Try external server
        if self.is_server_available():
            try:
                url = f"{self.server_url}/wings/{wing_name}/rooms/{room_name}/drawers"
                payload = {
                    "name": drawer_name,
                    "content": content,
                    "metadata": metadata or {}
                }
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in (200, 201):
                        log_debug(f"Successfully sent Drawer '{drawer_name}' to external MemPalace.")
            except Exception as e:
                log_warning(f"Failed to write Drawer to external MemPalace: {e}")

        # 2. Write to local database
        local_conn = conn if conn is not None else self._get_connection()
        if local_conn:
            try:
                cursor = local_conn.cursor()
                # Get wing ID and room ID
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = w_row[0]

                cursor.execute("SELECT id FROM rooms WHERE wing_id = ? AND name = ?", (wing_id, room_name))
                r_row = cursor.fetchone()
                if not r_row:
                    cursor.execute("INSERT INTO rooms (wing_id, name) VALUES (?, ?)", (wing_id, room_name))
                    room_id = cursor.lastrowid
                else:
                    room_id = r_row[0]

                cursor.execute(
                    "INSERT INTO drawers (room_id, name, content, metadata) VALUES (?, ?, ?, ?)",
                    (room_id, drawer_name, content, meta_str)
                )
                if conn is None:
                    local_conn.commit()
                self._cache_loaded = False  # Reset cache to reload new data on next access
                return True
            except Exception as e:
                log_error(f"Local DB error in add_drawer: {e}")
        return False

    def add_relation(self, wing_name: str, source: str, relation: str, target: str, valid_from: str = "", conn: Optional[sqlite3.Connection] = None) -> bool:
        """Add relationship rule between characters or entities to temporal knowledge graph."""
        log_info(f"Adding relation: {source} -[{relation}]-> {target}")

        if self.is_server_available():
            try:
                url = f"{self.server_url}/wings/{wing_name}/graph"
                payload = {
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "valid_from": valid_from
                }
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in (200, 201):
                        log_info("Successfully added relation to external knowledge graph.")
            except Exception as e:
                log_warning(f"Failed to add relation to external MemPalace Graph: {e}")

        local_conn = conn if conn is not None else self._get_connection()
        if local_conn:
            try:
                cursor = local_conn.cursor()
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = w_row[0]

                cursor.execute(
                    "INSERT OR IGNORE INTO knowledge_graph (wing_id, source_entity, target_entity, relation, valid_from) VALUES (?, ?, ?, ?, ?)",
                    (wing_id, source, target, relation, valid_from)
                )
                if conn is None:
                    local_conn.commit()
                return True
            except Exception as e:
                log_error(f"Local DB error in add_relation: {e}")
        return False
