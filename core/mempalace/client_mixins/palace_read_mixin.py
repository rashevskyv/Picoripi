"""Search, list, and clear helpers for wings/rooms/drawers."""
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from utils.logging_utils import log_debug, log_error, log_info, log_warning


class PalaceReadMixin:
    """Search, list, and clear helpers for wings/rooms/drawers."""
    def search_context(self, wing_name: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search the MemPalace database for visual/story context related to the query string."""
        log_debug(f"Searching context in MemPalace for query: '{query}'")
        
        # 1. Try external server
        if self.is_server_available():
            try:
                # Search using external server API
                # Typically, this would be a POST or GET request with a search query
                url = f"{self.server_url}/wings/{wing_name}/search?q={urllib.parse.quote(query)}&limit={limit}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status == 200:
                        results = json.loads(response.read().decode('utf-8'))
                        return results
            except Exception as e:
                log_warning(f"Failed to search external MemPalace: {e}. Searching local fallback DB.")

        # 2. Local Fallback Database Search
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Fetch all drawers in this wing
                cursor.execute("""
                    SELECT d.name, d.content, d.metadata, r.name 
                    FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ?
                """, (wing_name,))
                drawers = cursor.fetchall()
                
                # Sibling fallback: if no drawers found for this specific wing, grab all drawers
                # to handle differences in game/wing name configurations across builders
                if not drawers:
                    cursor.execute("""
                        SELECT d.name, d.content, d.metadata, r.name 
                        FROM drawers d
                        JOIN rooms r ON d.room_id = r.id
                    """)
                    drawers = cursor.fetchall()
                    
                # Basic TF-IDF / Substring similarity matching for demonstration/local-first use.
                # We calculate simple keyword overlap score as robust fallback.
                query_words = set(query.lower().split())
                scored_results = []
                
                for name, content, metadata_str, room_name in drawers:
                    content_lower = content.lower()
                    name_lower = name.lower()
                    
                    # Score matches
                    score = 0
                    for word in query_words:
                        if word in content_lower:
                            score += content_lower.count(word)
                        if word in name_lower:
                            score += 5 # strong match if query word in scene/drawer name

                    if score > 0 or not query_words:
                        try:
                            meta = json.loads(metadata_str)
                        except Exception:
                            meta = {}
                        scored_results.append({
                            "score": score,
                            "name": name,
                            "content": content,
                            "room": room_name,
                            "metadata": meta
                        })

                # Sort by score descending
                scored_results.sort(key=lambda x: x["score"], reverse=True)
                return scored_results[:limit]
            except Exception as e:
                log_error(f"Local search database error: {e}")
        
        return []

    def get_room_visual_context(self, wing_name: str, room_name: str) -> Optional[str]:
        """Retrieve visual_scene_context Drawer content for a given room in SQLite database."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.content FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ? AND r.name = ? AND d.name = 'visual_scene_context'
                """, (wing_name, room_name))
                row = cursor.fetchone()
                
                # Fallback: if no context found with exact wing name, search by room only
                # to tolerate name changes of active plugin
                if not row:
                    cursor.execute("""
                        SELECT d.content FROM drawers d
                        JOIN rooms r ON d.room_id = r.id
                        WHERE r.name = ? AND d.name = 'visual_scene_context'
                    """, (room_name,))
                    row = cursor.fetchone()
                    
                if row:
                    return row[0]
            except Exception as e:
                log_error(f"Local DB error in get_room_visual_context: {e}")
        return None

    def get_relations(self, wing_name: str) -> List[Dict[str, Any]]:
        """Retrieve all character relations for a given wing from SQLite database."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT kg.source_entity, kg.relation, kg.target_entity, kg.valid_from 
                    FROM knowledge_graph kg
                    JOIN wings w ON kg.wing_id = w.id
                    WHERE w.name = ?
                """, (wing_name,))
                rows = cursor.fetchall()
                
                # Sibling fallback: if no relations found for this specific wing, grab all relations
                # to handle differences in game/wing name configurations across builders
                if not rows:
                    cursor.execute("""
                        SELECT kg.source_entity, kg.relation, kg.target_entity, kg.valid_from 
                        FROM knowledge_graph kg
                    """)
                    rows = cursor.fetchall()
                    
                for row in rows:
                    results.append({
                        "source": row[0],
                        "relation": row[1],
                        "target": row[2],
                        "valid_from": row[3]
                    })
            except Exception as e:
                log_error(f"Local DB error in get_relations: {e}")
        return results

    def clear_wing(self, wing_name: str) -> bool:
        """Clear all database entries (rooms, drawers, knowledge graph relations) for the given wing."""
        log_info(f"Clearing database for Wing: {wing_name}")
        
        # 1. Try external server first
        if self.is_server_available():
            try:
                url = f"{self.server_url}/wings/{wing_name}"
                req = urllib.request.Request(url, method="DELETE")
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in (200, 204):
                        log_info(f"Successfully deleted Wing '{wing_name}' from external MemPalace server.")
            except Exception as e:
                log_warning(f"Failed to clear wing on external MemPalace server: {e}")

        # 2. Local SQLite clear
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Find wing ID
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                row = cursor.fetchone()
                if row:
                    wing_id = row[0]
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    cursor.execute("DELETE FROM wings WHERE id = ?", (wing_id,))
                    cursor.execute("DELETE FROM knowledge_graph WHERE wing_id = ?", (wing_id,))
                    
                    # Deletes explicitly to make sure everything cascade-deletes even if foreign_key is disabled:
                    cursor.execute("""
                        DELETE FROM drawers WHERE room_id IN (
                            SELECT id FROM rooms WHERE wing_id = ?
                        )
                    """, (wing_id,))
                    cursor.execute("DELETE FROM rooms WHERE wing_id = ?", (wing_id,))
                    
                conn.commit()
                return True
            except Exception as e:
                log_error(f"Local DB error in clear_wing: {e}")
        return False

    def clear_all_local_data(self) -> bool:
        """Completely clear all data from all tables in the local SQLite database."""
        log_info("Completely clearing all local SQLite database tables.")
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM drawers")
                cursor.execute("DELETE FROM rooms")
                cursor.execute("DELETE FROM knowledge_graph")
                cursor.execute("DELETE FROM story_sync_conflicts")
                cursor.execute("DELETE FROM story_dialogue_mappings")
                cursor.execute("DELETE FROM story_documents")
                cursor.execute("DELETE FROM wings")
                conn.commit()
                log_info(f"Completely cleared all local database tables at: {self.db_path}")
                return True
            except Exception as e:
                log_error(f"Local DB error in clear_all_local_data: {e}")
        return False

    def get_wings(self) -> List[Dict[str, Any]]:
        """Retrieve all Wings (game projects) from the local SQLite database."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description FROM wings")
                rows = cursor.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2] or ""
                    })
            except Exception as e:
                log_error(f"Local DB error in get_wings: {e}")
        return results

    def get_rooms(self, wing_name: str) -> List[Dict[str, Any]]:
        """Retrieve all Rooms (scenes/timeline locations) for the given wing."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Check for table rooms and wings
                cursor.execute("""
                    SELECT r.id, r.name, r.description FROM rooms r
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ?
                """, (wing_name,))
                rows = cursor.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2] or ""
                    })
            except Exception as e:
                # Sibling fallback: if no rooms found under this exact wing name,
                # fetch all rooms (similar to search context fallback)
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, name, description FROM rooms")
                    rows = cursor.fetchall()
                    for row in rows:
                        results.append({
                            "id": row[0],
                            "name": row[1],
                            "description": row[2] or ""
                        })
                except Exception as ex:
                    log_error(f"Local DB fallback error in get_rooms: {ex}")
        return results

    def get_room_drawers(self, wing_name: str, room_name: str) -> List[Dict[str, Any]]:
        """Retrieve all Drawers (contents/transcripts) for the given room and wing."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.id, d.name, d.content, d.metadata FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ? AND r.name = ?
                """, (wing_name, room_name))
                rows = cursor.fetchall()
                
                # Fallback: if no drawers found under exact wing/room match, search by room only
                if not rows:
                    cursor.execute("""
                        SELECT d.id, d.name, d.content, d.metadata FROM drawers d
                        JOIN rooms r ON d.room_id = r.id
                        WHERE r.name = ?
                    """, (room_name,))
                    rows = cursor.fetchall()
                    
                for row in rows:
                    try:
                        meta = json.loads(row[3]) if row[3] else {}
                    except Exception:
                        meta = {}
                    results.append({
                        "id": row[0],
                        "name": row[1],
                        "content": row[2] or "",
                        "metadata": meta
                    })
            except Exception as e:
                log_error(f"Local DB error in get_room_drawers: {e}")
        return results
