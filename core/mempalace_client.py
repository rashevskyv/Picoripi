import os
import json
import sqlite3
import urllib.request
import urllib.error
import re
from core.tag_utils import ANY_TAG_PATTERN as tag_pattern
import threading
from typing import Dict, List, Any, Optional
from utils.logging_utils import log_info, log_warning, log_error, log_debug

class MemePalaceClient:
    """Meme palace client implementation."""
    def __init__(self, project_dir: Optional[str] = None, server_url: str = "http://127.0.0.1:8000"):
        """Initialize a new instance."""
        self.server_url = server_url.rstrip('/')
        self.project_dir = project_dir
        self.db_path = None
        self._cache_loaded = False
        self._bmg_to_context = {}
        self._text_to_context = {}
        self._db_mtime = 0
        self._local = threading.local()
        
        if self.project_dir:
            # We store the local database inside the project directory
            self.db_path = os.path.join(self.project_dir, "mempalace_local.db")
            self._init_local_db()
            self.preload_cache()

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get or create the cached thread-local SQLite connection."""
        if not self.db_path:
            return None
        if not hasattr(self._local, "conn") or self._local.conn is None:
            try:
                self._local.conn = sqlite3.connect(self.db_path)
                cursor = self._local.conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON;")
            except Exception as e:
                log_error(f"MemePalaceClient: Failed to open thread-local SQLite connection: {e}", exc_info=True)
                return None
        return self._local.conn

    def preload_cache(self, force: bool = False):
        """Preload all drawers from local DB and build high-performance in-memory indexes."""
        if not force and self._cache_loaded:
            return
        if not self.db_path or not os.path.exists(self.db_path):
            return
        
        try:
            self._db_mtime = os.path.getmtime(self.db_path)
            self._bmg_to_context = {}
            self._text_to_context = {}
            
            conn = self._get_connection()
            if not conn:
                return
            cursor = conn.cursor()
            
            # Verify if table drawers exists first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drawers'")
            if not cursor.fetchone():
                return
                
            cursor.execute("""
                SELECT d.name, d.content, d.metadata, r.name 
                FROM drawers d
                JOIN rooms r ON d.room_id = r.id
            """)
            rows = cursor.fetchall()
            
            for name, content, metadata_str, room_name in rows:
                try:
                    meta = json.loads(metadata_str) if metadata_str else {}
                except Exception:
                    meta = {}
                
                speaker_map = meta.get("speaker_map") or {}
                timestamp = meta.get("timestamp") or "Unknown time"
                
                # 1. Map explicitly from speaker_map
                for bmg_id, speaker in speaker_map.items():
                    ctx_info = {
                        "room": room_name,
                        "speaker": speaker,
                        "timestamp": timestamp,
                        "metadata": meta,
                        "content": content
                    }
                    self._bmg_to_context[bmg_id] = ctx_info
                    self._bmg_to_context[f"[{bmg_id}]"] = ctx_info
                
                # 2. Extract dialogue lines and map to texts
                if content:
                    for line in content.splitlines():
                        line_id = None
                        line_text = None
                        
                        # Format A: "ID: BMG_Str_12 | Text: In the kingdom..."
                        if "ID:" in line and "| Text:" in line:
                            parts = line.split("| Text:", 1)
                            line_id = parts[0].replace("ID:", "").strip()
                            line_text = parts[1].strip()
                        # Format B: "[BMG_Str_12]: In the kingdom..."
                        elif ":" in line:
                            parts = line.split(":", 1)
                            line_id = parts[0].strip()
                            if line_id.startswith("[") and line_id.endswith("]"):
                                line_id = line_id[1:-1].strip()
                            line_text = parts[1].strip()
                            
                        if line_id and line_text:
                            clean_text = line_text.lower().strip()
                            speaker = speaker_map.get(line_id) or speaker_map.get(f"[{line_id}]")
                            
                            ctx_info = {
                                "room": room_name,
                                "speaker": speaker,
                                "timestamp": timestamp,
                                "metadata": meta,
                                "content": content
                            }
                            if line_id not in self._bmg_to_context:
                                self._bmg_to_context[line_id] = ctx_info
                                self._bmg_to_context[f"[{line_id}]"] = ctx_info
                                
                            if clean_text and len(clean_text) > 2:
                                if clean_text not in self._text_to_context:
                                    self._text_to_context[clean_text] = ctx_info
            
            self._cache_loaded = True
            log_info(f"MemePalace cache preloaded successfully: {len(self._bmg_to_context)} BMG IDs, {len(self._text_to_context)} text patterns mapped.")
        except Exception as e:
            log_error(f"Error preloading MemePalace cache: {e}", exc_info=True)

    def get_cached_context(self, bmg_id: str, text: str) -> Optional[Dict[str, Any]]:
        """MemePalace high-performance memory cache lookup by BMG ID or text string."""
        if self.db_path and os.path.exists(self.db_path):
            try:
                current_mtime = os.path.getmtime(self.db_path)
                if current_mtime != self._db_mtime:
                    log_info(f"MemePalace database modified ({self._db_mtime} -> {current_mtime}). Invalidate and reload cache.")
                    self.preload_cache(force=True)
            except Exception as e:
                log_error(f"Error checking DB mtime in get_cached_context: {e}")

        if not self._cache_loaded:
            self.preload_cache()
            
        # 1. Direct match by BMG ID
        if bmg_id in self._bmg_to_context:
            return self._bmg_to_context[bmg_id]
            
        # 2. Match by bracketed BMG ID
        bracketed = f"[{bmg_id}]"
        if bracketed in self._bmg_to_context:
            return self._bmg_to_context[bracketed]
            
        # 3. Fallback: match by clean text
        if text:
            clean_text = text.lower().strip()
            if clean_text in self._text_to_context:
                return self._text_to_context[clean_text]
                
        return None

    def _init_local_db(self):
        """Initialize the local SQLite database for local fallback mode."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Create Wings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT
                )
            """)
            
            # Create Rooms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wing_id INTEGER,
                    name TEXT,
                    description TEXT,
                    UNIQUE(wing_id, name),
                    FOREIGN KEY(wing_id) REFERENCES wings(id) ON DELETE CASCADE
                )
            """)
            
            # Create Drawers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drawers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    name TEXT,
                    content TEXT,
                    metadata TEXT,
                    FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            """)
            
            # Create Knowledge Graph table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wing_id INTEGER,
                    source_entity TEXT,
                    target_entity TEXT,
                    relation TEXT,
                    valid_from TEXT,
                    FOREIGN KEY(wing_id) REFERENCES wings(id) ON DELETE CASCADE
                )
            """)

            # Create Script Chapters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS script_chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wing_id INTEGER,
                    num TEXT,
                    title TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    ai_summary TEXT,
                    content TEXT,
                    FOREIGN KEY(wing_id) REFERENCES wings(id) ON DELETE CASCADE
                )
            """)

            # Create Script Mappings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS script_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wing_id INTEGER,
                    chapter_id INTEGER,
                    bmg_id TEXT,
                    script_line INTEGER,
                    bmg_text TEXT,
                    FOREIGN KEY(wing_id) REFERENCES wings(id) ON DELETE CASCADE,
                    FOREIGN KEY(chapter_id) REFERENCES script_chapters(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
            log_info(f"Initialized local MemePalace database at: {self.db_path}")
        except Exception as e:
            log_error(f"Failed to initialize local SQLite database: {e}", exc_info=True)

    def is_server_available(self) -> bool:
        """Check if the external MemPalace server is up and responding."""
        import time
        if hasattr(self, "_server_available_cached") and hasattr(self, "_server_last_checked"):
            if time.time() - self._server_last_checked < 30.0:
                return self._server_available_cached

        try:
            # We make a simple GET request to check availability
            url = f"{self.server_url}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                avail = response.status == 200
                self._server_available_cached = avail
                self._server_last_checked = time.time()
                return avail
        except Exception:
            self._server_available_cached = False
            self._server_last_checked = time.time()
            return False

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

    def get_chapter_for_line(self, wing_name: str, line_num: int) -> Optional[Dict[str, Any]]:
        """Find the script chapter containing the given script line number."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sc.id, sc.num, sc.title, sc.start_line, sc.end_line, sc.ai_summary, sc.content
                    FROM script_chapters sc
                    JOIN wings w ON sc.wing_id = w.id
                    WHERE w.name = ? AND ? BETWEEN sc.start_line AND sc.end_line
                """, (wing_name, line_num))
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "num": row[1],
                        "title": row[2],
                        "start_line": row[3],
                        "end_line": row[4],
                        "ai_summary": row[5] or "",
                        "content": row[6] or ""
                    }
            except Exception as e:
                log_error(f"Local DB error in get_chapter_for_line: {e}")
        return None

    def get_script_mapping(self, wing_name: str, bmg_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve script mapping directly from script_mappings table."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sm.script_line, sm.bmg_text, sc.id, sc.num, sc.title
                    FROM script_mappings sm
                    JOIN wings w ON sm.wing_id = w.id
                    LEFT JOIN script_chapters sc ON sm.chapter_id = sc.id
                    WHERE w.name = ? AND sm.bmg_id = ?
                """, (wing_name, bmg_id))
                row = cursor.fetchone()
                
                # Try with clean ID if original is bracketed
                if not row and bmg_id.startswith("[") and bmg_id.endswith("]"):
                    clean_id = bmg_id[1:-1]
                    cursor.execute("""
                        SELECT sm.script_line, sm.bmg_text, sc.id, sc.num, sc.title
                        FROM script_mappings sm
                        JOIN wings w ON sm.wing_id = w.id
                        LEFT JOIN script_chapters sc ON sm.chapter_id = sc.id
                        WHERE w.name = ? AND sm.bmg_id = ?
                    """, (wing_name, clean_id))
                    row = cursor.fetchone()
                    
                if row:
                    return {
                        "script_line": row[0],
                        "bmg_text": row[1],
                        "chapter_id": row[2],
                        "chapter_num": row[3],
                        "chapter_title": row[4]
                    }
            except Exception as e:
                log_error(f"Local DB error in get_script_mapping: {e}")
        return None

    def get_chapter_mappings(self, wing_name: str, chapter_id: int) -> List[Dict[str, Any]]:
        """Retrieve all BMG mappings for a specific chapter."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT bmg_id, script_line, bmg_text 
                    FROM script_mappings 
                    WHERE chapter_id = ?
                    ORDER BY script_line
                """, (chapter_id,))
                rows = cursor.fetchall()
                for row in rows:
                    results.append({
                        "bmg_id": row[0],
                        "script_line": row[1],
                        "bmg_text": row[2]
                    })
            except Exception as e:
                log_error(f"Local DB error in get_chapter_mappings: {e}")
        return results

    def get_all_chapter_mappings(self, wing_name: str) -> Dict[int, List[Dict[str, Any]]]:
        """Retrieve all BMG mappings for all chapters in a wing, grouped by chapter_id."""
        results = {}
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sm.chapter_id, sm.bmg_id, sm.script_line, sm.bmg_text 
                    FROM script_mappings sm
                    JOIN wings w ON sm.wing_id = w.id
                    WHERE w.name = ?
                    ORDER BY sm.script_line
                """, (wing_name,))
                rows = cursor.fetchall()
                for row in rows:
                    ch_id = row[0]
                    if ch_id is not None:
                        results.setdefault(ch_id, []).append({
                            "bmg_id": row[1],
                            "script_line": row[2],
                            "bmg_text": row[3]
                        })
            except Exception as e:
                log_error(f"Local DB error in get_all_chapter_mappings: {e}")
        return results


    def get_all_chapters(self, wing_name: str) -> List[Dict[str, Any]]:
        """Retrieve all chapters and their mapping counts for a wing."""
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Check if wings table has entries first
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    return results
                wing_id = w_row[0]

                cursor.execute("""
                    SELECT sc.id, sc.num, sc.title, sc.start_line, sc.end_line, sc.ai_summary,
                           (SELECT COUNT(*) FROM script_mappings sm WHERE sm.chapter_id = sc.id) as mapped_count
                    FROM script_chapters sc
                    WHERE sc.wing_id = ?
                    ORDER BY sc.start_line
                """, (wing_id,))
                rows = cursor.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "num": row[1],
                        "title": row[2],
                        "start_line": row[3],
                        "end_line": row[4],
                        "ai_summary": row[5] or "",
                        "mapped_count": row[6]
                    })
            except Exception as e:
                log_error(f"Local DB error in get_all_chapters: {e}")
        return results

    def save_chapter_summary(self, chapter_id: int, summary: str):
        """Update AI summary of a chapter."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE script_chapters SET ai_summary = ? WHERE id = ?", (summary, chapter_id))
                conn.commit()
            except Exception as e:
                log_error(f"Local DB error in save_chapter_summary: {e}")

    def save_chapters_to_db(self, wing_name: str, chapters: List[Dict[str, Any]]):
        """Save segmented chapters into local SQLite DB, clearing older chapters for the wing."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Get wing ID
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = w_row[0]
                    
                # Clear old chapters and mappings (cascade delete or manual delete)
                cursor.execute("DELETE FROM script_chapters WHERE wing_id = ?", (wing_id,))
                cursor.execute("DELETE FROM script_mappings WHERE wing_id = ?", (wing_id,))
                
                for ch in chapters:
                    cursor.execute("""
                        INSERT INTO script_chapters (wing_id, num, title, start_line, end_line, ai_summary, content)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        wing_id,
                        ch.get("num", ""),
                        ch.get("title", ""),
                        ch.get("start_line", 0),
                        ch.get("end_line", 0),
                        ch.get("ai_summary", ""),
                        ch.get("content", "")
                    ))
                conn.commit()
                log_info(f"Successfully saved {len(chapters)} chapters for wing '{wing_name}' to local DB.")
            except Exception as e:
                log_error(f"Local DB error in save_chapters_to_db: {e}", exc_info=True)

    def save_mappings_to_db(self, wing_name: str, mappings: List[Dict[str, Any]]):
        """Save BMG to script mappings into SQLite DB, clearing older mappings first."""
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Get wing ID
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = w_row[0]
                    
                cursor.execute("DELETE FROM script_mappings WHERE wing_id = ?", (wing_id,))
                
                # Retrieve active chapter lookup map: (start, end) -> chapter_id
                cursor.execute("SELECT id, start_line, end_line FROM script_chapters WHERE wing_id = ?", (wing_id,))
                ch_rows = cursor.fetchall()
                
                for m in mappings:
                    line = m.get("script_line")
                    chapter_id = None
                    for ch_id, s_line, e_line in ch_rows:
                        if s_line <= line <= e_line:
                            chapter_id = ch_id
                            break
                            
                    cursor.execute("""
                        INSERT INTO script_mappings (wing_id, chapter_id, bmg_id, script_line, bmg_text)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        wing_id,
                        chapter_id,
                        m.get("bmg_id", ""),
                        line,
                        m.get("bmg_text", "")
                    ))
                conn.commit()
                log_info(f"Successfully saved {len(mappings)} BMG mappings for wing '{wing_name}' to local DB.")
            except Exception as e:
                log_error(f"Local DB error in save_mappings_to_db: {e}", exc_info=True)

    def get_all_character_lines(self, wing_name: str) -> Dict[str, List[str]]:
        """Retrieve and group all dialogue dialogue lines spoken by each character from mapped drawers."""
        results: Dict[str, List[str]] = {}
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Fetch all dialogue drawers for this wing
                cursor.execute("""
                    SELECT d.content, d.metadata 
                    FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ? AND d.name IN ('dialogues', 'dialogue_lines')
                """, (wing_name,))
                rows = cursor.fetchall()
                
                # Fallback if specific wing has no drawers, fetch all dialogue drawers
                if not rows:
                    cursor.execute("""
                        SELECT d.content, d.metadata 
                        FROM drawers d
                        WHERE d.name IN ('dialogues', 'dialogue_lines')
                    """)
                    rows = cursor.fetchall()
                    
                # Tag cleaning pattern
                
                for content, metadata_str in rows:
                    if not content:
                        continue
                        
                    try:
                        meta = json.loads(metadata_str) if metadata_str else {}
                    except Exception:
                        meta = {}
                        
                    speaker_map = meta.get("speaker_map") or {}
                    
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                            
                        line_id = None
                        line_text = None
                        
                        # Format: ID: BMG_Str_12 | Text: Hello...
                        if "ID:" in line and "| Text:" in line:
                            parts = line.split("| Text:", 1)
                            line_id = parts[0].replace("ID:", "").strip()
                            line_text = parts[1].strip()
                        # Format: [BMG_Str_12]: Hello...
                        elif ":" in line:
                            parts = line.split(":", 1)
                            line_id = parts[0].strip()
                            if line_id.startswith("[") and line_id.endswith("]"):
                                line_id = line_id[1:-1].strip()
                            line_text = parts[1].strip()
                            
                        if line_id and line_text:
                            speaker = speaker_map.get(line_id) or speaker_map.get(f"[{line_id}]")
                            if speaker:
                                clean_speaker = str(speaker).strip()
                                if clean_speaker and clean_speaker.lower() not in ("unknown", "none"):
                                    # Strip tags for clean linguistic analysis
                                    clean_text = tag_pattern.sub('', line_text).strip()
                                    # Clean spaces
                                    clean_text = re.sub(r'\s+', ' ', clean_text)
                                    if clean_text:
                                        results.setdefault(clean_speaker, []).append(clean_text)
                                        
                log_info(f"Retrieved dialogue lines for {len(results)} speakers from local database.")
            except Exception as e:
                log_error(f"Local DB error in get_all_character_lines: {e}", exc_info=True)
                
        return results

