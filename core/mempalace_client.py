import os
import json
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
from utils.logging_utils import log_info, log_warning, log_error, log_debug

class MemePalaceClient:
    def __init__(self, project_dir: Optional[str] = None, server_url: str = "http://127.0.0.1:8000"):
        self.server_url = server_url.rstrip('/')
        self.project_dir = project_dir
        self.db_path = None
        self._cache_loaded = False
        self._bmg_to_context = {}
        self._text_to_context = {}
        self._db_mtime = 0
        
        if self.project_dir:
            # We store the local database inside the project directory
            self.db_path = os.path.join(self.project_dir, "mempalace_local.db")
            self._init_local_db()
            self.preload_cache()

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
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify if table drawers exists first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drawers'")
            if not cursor.fetchone():
                conn.close()
                return
                
            cursor.execute("""
                SELECT d.name, d.content, d.metadata, r.name 
                FROM drawers d
                JOIN rooms r ON d.room_id = r.id
            """)
            rows = cursor.fetchall()
            conn.close()
            
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
                        if ":" in line:
                            parts = line.split(":", 1)
                            line_id = parts[0].strip()
                            line_text = parts[1].strip()
                            clean_text = line_text.lower().strip()
                            
                            speaker = speaker_map.get(line_id) or speaker_map.get(f"[{line_id}]")
                            
                            ctx_info = {
                                "room": room_name,
                                "speaker": speaker,
                                "timestamp": timestamp,
                                "metadata": meta,
                                "content": content
                            }
                            if line_id and line_id not in self._bmg_to_context:
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
        if not self.db_path:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
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
            
            conn.commit()
            conn.close()
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
        if self.db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM drawers d
                    JOIN rooms r ON d.room_id = r.id
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ? AND r.name = ? AND d.name = 'visual_scene_context'
                """, (wing_name, room_name))
                row = cursor.fetchone()
                conn.close()
                return bool(row)
            except Exception as e:
                log_error(f"Local DB error in has_room: {e}")
        return False

    def add_wing(self, name: str, description: str = "") -> bool:
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
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO wings (name, description) VALUES (?, ?)",
                    (name, description)
                )
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                log_error(f"Local DB error in add_wing: {e}")
        return False

    def add_room(self, wing_name: str, room_name: str, description: str = "") -> bool:
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
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
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
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                log_error(f"Local DB error in add_room: {e}")
        return False

    def add_drawer(self, wing_name: str, room_name: str, drawer_name: str, content: str, metadata: Dict[str, Any] = None) -> bool:
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
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
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
                conn.commit()
                conn.close()
                self._cache_loaded = False  # Reset cache to reload new data on next access
                return True
            except Exception as e:
                log_error(f"Local DB error in add_drawer: {e}")
        return False

    def add_relation(self, wing_name: str, source: str, relation: str, target: str, valid_from: str = "") -> bool:
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

        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM wings WHERE name = ?", (wing_name,))
                w_row = cursor.fetchone()
                if not w_row:
                    cursor.execute("INSERT INTO wings (name) VALUES (?)", (wing_name,))
                    wing_id = cursor.lastrowid
                else:
                    wing_id = w_row[0]

                cursor.execute(
                    "INSERT INTO knowledge_graph (wing_id, source_entity, target_entity, relation, valid_from) VALUES (?, ?, ?, ?, ?)",
                    (wing_id, source, target, relation, valid_from)
                )
                conn.commit()
                conn.close()
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
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
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
                    
                conn.close()

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
        if self.db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
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
                    
                conn.close()
                if row:
                    return row[0]
            except Exception as e:
                log_error(f"Local DB error in get_room_visual_context: {e}")
        return None

    def get_relations(self, wing_name: str) -> List[Dict[str, Any]]:
        """Retrieve all character relations for a given wing from SQLite database."""
        results = []
        if self.db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
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
                    
                conn.close()
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
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
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
                conn.close()
                return True
            except Exception as e:
                log_error(f"Local DB error in clear_wing: {e}")
        return False

    def clear_all_local_data(self) -> bool:
        """Completely clear all data from all tables in the local SQLite database."""
        log_info("Completely clearing all local SQLite database tables.")
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM drawers")
                cursor.execute("DELETE FROM rooms")
                cursor.execute("DELETE FROM knowledge_graph")
                cursor.execute("DELETE FROM wings")
                conn.commit()
                conn.close()
                log_info(f"Completely cleared all local database tables at: {self.db_path}")
                return True
            except Exception as e:
                log_error(f"Local DB error in clear_all_local_data: {e}")
        return False

    def get_wings(self) -> List[Dict[str, Any]]:
        """Retrieve all Wings (game projects) from the local SQLite database."""
        results = []
        if self.db_path and os.path.exists(self.db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description FROM wings")
                rows = cursor.fetchall()
                conn.close()
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
        if self.db_path and os.path.exists(self.db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                # Check for table rooms and wings
                cursor.execute("""
                    SELECT r.id, r.name, r.description FROM rooms r
                    JOIN wings w ON r.wing_id = w.id
                    WHERE w.name = ?
                """, (wing_name,))
                rows = cursor.fetchall()
                conn.close()
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
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, name, description FROM rooms")
                    rows = cursor.fetchall()
                    conn.close()
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
        if self.db_path and os.path.exists(self.db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
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
                    
                conn.close()
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
