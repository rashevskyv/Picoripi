"""Chapter and script mapping helpers."""
import json
import re
from typing import Any, Dict, List, Optional

from core.tag_utils import ANY_TAG_PATTERN as tag_pattern
from utils.logging_utils import log_error, log_info


class ChapterMixin:
    """Chapter and script mapping helpers."""
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

    def get_all_script_mappings(self, wing_name: str) -> List[Dict[str, Any]]:
        """Every BMG->script_line mapping for a wing, regardless of chapter.

        Unlike ``get_all_chapter_mappings`` (which drops rows whose
        ``chapter_id`` is NULL), this returns the complete ``script_mappings``
        table for the wing — the same source ``get_script_mapping`` reads per
        row. The speaker pool needs the full set so chapterless rows resolve to
        the same speaker the editor field shows, in a single query.
        """
        results = []
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sm.bmg_id, sm.script_line
                    FROM script_mappings sm
                    JOIN wings w ON sm.wing_id = w.id
                    WHERE w.name = ?
                    ORDER BY sm.script_line
                """, (wing_name,))
                for row in cursor.fetchall():
                    results.append({"bmg_id": row[0], "script_line": row[1]})
            except Exception as e:
                log_error(f"Local DB error in get_all_script_mappings: {e}")
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
