import os
import json
import sqlite3
import urllib.request
import urllib.error
import threading
from typing import Dict, Any, Optional

from core.mempalace.schema import migrate_mempalace_schema
from core.mempalace.client_mixins.chapter_mixin import ChapterMixin
from core.mempalace.client_mixins.palace_read_mixin import PalaceReadMixin
from core.mempalace.client_mixins.palace_write_mixin import PalaceWriteMixin
from core.mempalace.client_mixins.story_api_mixin import StoryApiMixin
from utils.logging_utils import log_info, log_error


class MemePalaceClient(
    StoryApiMixin,
    PalaceWriteMixin,
    PalaceReadMixin,
    ChapterMixin,
):
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

            # Additive, versioned tables for the normalized story timeline.
            migrate_mempalace_schema(conn)
            
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
