import json
import re
import difflib
import sqlite3
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional, Tuple
from core.mempalace_client import MemePalaceClient
from core.translation.providers import BaseTranslationProvider, ProviderResponse
from utils.logging_utils import log_info, log_error, log_debug, log_ai_traffic


def robust_json_loads(text: str) -> dict:
    """Parse JSON from AI response text, stripping markdown code fences if present."""
    cleaned = (text or "").strip()
    # Strip ```json ... ``` or ``` ... ``` blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```[a-zA-Z]*\n?', '', cleaned)
        cleaned = re.sub(r'```$', '', cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: try to find first { ... } block
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


class MemePalaceWorker(QThread):
    """Meme palace worker implementation."""
    # Signals for UI communication
    progress = pyqtSignal(int, int, str)  # current_step, total_steps, status_text
    log = pyqtSignal(str)                 # log message to display in UI
    finished = pyqtSignal(bool, str)      # is_success, message

    def __init__(self, 
                 client: MemePalaceClient, 
                 bmg_strings: List[str], 
                 bmg_ids: List[str],
                 transcript_data: List[Dict[str, Any]], 
                 ai_provider: Optional[BaseTranslationProvider] = None,
                 wing_name: str = "Zelda_TP",
                 mapping_only: bool = False,
                 bmg_translation_states: Optional[List[bool]] = None,
                 target_lang: str = "Ukrainian",
                 glossary_manager: Optional[Any] = None,
                 glossary_entries: Optional[List[Any]] = None):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.bmg_strings = bmg_strings
        self.bmg_ids = bmg_ids
        self.transcript_data = transcript_data  # List of dicts with {"text": str, "speaker": str, "timestamp": str}
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.mapping_only = mapping_only
        self.bmg_translation_states = bmg_translation_states
        self.target_lang = target_lang
        self.glossary_manager = glossary_manager
        self.glossary_entries = glossary_entries or []
        self.is_cancelled = False
        self.mapped_results = []  # Pairs of BMG strings mapped to timeline

    def cancel(self):
        """Cancel."""
        self.is_cancelled = True
        self.log.emit("Cancellation requested...")

    def run(self):
        """Run."""
        try:
            self.log.emit("Starting MemePalace Context Weaver...")
            
            # --- PHASE 1: WEAVE / FUZZY MAPPING ---
            self.progress.emit(0, 100, "Mapping BMG strings to timeline...")
            self.mapped_results = self._weave_strings()
            
            if self.is_cancelled:
                self.finished.emit(False, "Process was cancelled by user.")
                return

            self.log.emit(f"Weaving completed. Mapped {len(self.mapped_results)} chunks/scenes to timeline.")
            
            if self.mapping_only:
                self.log.emit("Timeline Mapping Only is active. Saving mapped scenes directly to local database...")
                self._save_mapped_data_to_local_palace(self.mapped_results)
                self.progress.emit(100, 100, "Mapping completed successfully!")
                self.finished.emit(True, f"Successfully mapped BMG strings. Found {len(self.mapped_results)} chronological scenes.")
                return

            # --- PHASE 2: GENERATE MEMORY PALACE ---
            if not self.ai_provider:
                self.log.emit("No AI Provider configured. Skipping LLM scene annotation phase.")
                self._save_mapped_data_to_local_palace(self.mapped_results)
                self.progress.emit(100, 100, "Local Memory Palace saved!")
                self.finished.emit(True, "MemePalace built locally (mapping-only, no LLM descriptions).")
                return

            self._generate_palace_via_llm(self.mapped_results)
            
            if self.is_cancelled:
                self.finished.emit(False, "Process was cancelled by user during LLM phase.")
                return

            self.progress.emit(100, 100, "MemePalace generation completed!")
            self.finished.emit(True, "MemePalace built successfully with full AI annotations!")

        except Exception as e:
            log_error(f"Error in MemePalaceWorker: {e}", exc_info=True)
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")

    def _weave_strings(self) -> List[Dict[str, Any]]:
        """Map chronological transcript timeline to unordered BMG strings 
        by using the transcript sequence as the primary source of truth,
        deeply cleaning strings and matching them to BMG indices.
        """
        import re
        
        # Retrieve dynamic name tags from rules if available
        _dynamic_name_tags = {}
        mw = getattr(self.glossary_manager, 'mw', None) if self.glossary_manager else None
        if mw and hasattr(mw, 'current_game_rules') and mw.current_game_rules:
            try:
                _dynamic_name_tags = mw.current_game_rules.get_dynamic_name_tags()
            except Exception:
                pass

        def clean_for_match(text: str) -> str:
            """Clean for match."""
            if not text:
                return ""
            # Replace known dynamic name tags (e.g. {escape:0:0000} -> "Link") before stripping tags
            for tag, name in _dynamic_name_tags.items():
                text = text.replace(tag, name)
            # Remove XML/custom tags like {Color:Red}, [PLAYER], {escape:...}
            from core.tag_utils import strip_tags
            text_no_tags = strip_tags(text)
            # Remove punctuation, spaces, quotes, apostrophes, and convert to lower
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text_no_tags).lower()
            return cleaned

        # 1. Build a hash map of normalized BMG strings to their actual indices and IDs
        bmg_hash = {} # cleaned_text -> list of (bmg_idx, bmg_id)
        for bmg_idx, bmg_text in enumerate(self.bmg_strings):
            cleaned = clean_for_match(bmg_text)
            if len(cleaned) > 4: # Skip empty or extremely short system codes
                if cleaned not in bmg_hash:
                    bmg_hash[cleaned] = []
                bmg_hash[cleaned].append((bmg_idx, self.bmg_ids[bmg_idx]))

        self.log.emit(f"Indexed {len(bmg_hash)} distinct BMG lines for matching...")

        # 2. Iterate through chronological transcript entries (the script)
        # We map transcript index to BMG index
        t_to_bmg = {} # t_idx -> (bmg_idx, bmg_id)
        bmg_mapped_set = set() # Keep track of which BMG indices have been mapped to avoid double mapping

        self.log.emit("Phase 1: Direct chronological mapping via BMG hash table...")
        
        for t_idx, item in enumerate(self.transcript_data):
            t_text = item.get("text", "")
            cleaned_t = clean_for_match(t_text)
            
            if len(cleaned_t) > 6 and cleaned_t in bmg_hash:
                candidates = bmg_hash[cleaned_t]
                # Find the first candidate that hasn't been mapped yet
                best_candidate = None
                for b_idx, b_id in candidates:
                    if b_idx not in bmg_mapped_set:
                        best_candidate = (b_idx, b_id)
                        break
                
                # If all candidates are mapped, reuse the first one
                if not best_candidate and candidates:
                    best_candidate = candidates[0]
                    
                if best_candidate:
                    t_to_bmg[t_idx] = best_candidate
                    bmg_mapped_set.add(best_candidate[0])

        self.log.emit(f"Successfully mapped {len(t_to_bmg)} lines chronologically in Phase 1.")

        self.log.emit("Phase 2: Resolving remaining gaps via local fuzzy search...")
        
        # Phase 2: Local Fuzzy matching for unmapped transcript lines
        total_transcript = len(self.transcript_data)
        for t_idx in range(total_transcript):
            if t_idx in t_to_bmg:
                continue
                
            t_text = self.transcript_data[t_idx].get("text", "")
            cleaned_t = clean_for_match(t_text)
            if len(cleaned_t) <= 5: # Skip very short dialogues/remarks
                continue
                
            # Restrain search bounds to local surrounding matches to maintain strict timeline sequence
            prev_matches = [t_to_bmg[i][0] for i in range(t_idx - 1, -1, -1) if i in t_to_bmg]
            next_matches = [t_to_bmg[i][0] for i in range(t_idx + 1, total_transcript) if i in t_to_bmg]
            
            b_start = prev_matches[0] if prev_matches else 0
            b_end = next_matches[0] if next_matches else len(self.bmg_strings) - 1
            
            # Prevent huge search windows
            if b_end - b_start > 100:
                b_end = min(b_start + 100, len(self.bmg_strings) - 1)
                
            best_score = 0.0
            best_b_idx = -1
            best_b_id = None
            
            for b_idx in range(b_start, b_end + 1):
                if b_idx in bmg_mapped_set:
                    continue
                bmg_text = self.bmg_strings[b_idx]
                cleaned_b = clean_for_match(bmg_text)
                
                score = difflib.SequenceMatcher(None, cleaned_t, cleaned_b).ratio()
                
                # Intelligent Keyword Overlap Fallback:
                # If one string is much longer than another (e.g. BMG contains multiple combined sentences),
                # SequenceMatcher ratio drops significantly. We compute word overlap ratio for robust matching.
                if score < 0.65 and len(cleaned_t) > 12 and len(cleaned_b) > 12:
                    words_t = set(re.findall(r'[a-zA-Z]+', t_text.lower()))
                    words_b = set(re.findall(r'[a-zA-Z]+', bmg_text.lower()))
                    
                    # Filter short words (like 'is', 'a', 'to') to prevent noise
                    words_t = {w for w in words_t if len(w) > 2}
                    words_b = {w for w in words_b if len(w) > 2}
                    
                    if words_t:
                        intersection = words_t.intersection(words_b)
                        overlap = len(intersection) / len(words_t)
                        if overlap > 0.82: # Over 82% of transcript words are present in BMG message
                            score = max(score, overlap * 0.9)
                
                if score > best_score:
                    best_score = score
                    best_b_idx = b_idx
                    best_b_id = self.bmg_ids[b_idx]
                    
            if best_score > 0.65 and best_b_idx != -1:
                t_to_bmg[t_idx] = (best_b_idx, best_b_id)
                bmg_mapped_set.add(best_b_idx)

        self.log.emit(f"Total mapped transcript lines after Phase 2: {len(t_to_bmg)}.")

        # 3. Group chronologically mapped entries into scenes (Rooms) based on Script sequence
        # We group by active transcript Room/Chapter
        rooms_data = {} # room_name -> list of {"bmg_text", "bmg_id", "bmg_idx", "t_item"}
        
        for t_idx in sorted(t_to_bmg.keys()):
            b_idx, b_id = t_to_bmg[t_idx]
            t_item = self.transcript_data[t_idx]
            room_name = t_item.get("room", "Generic_Scene")
            
            if room_name not in rooms_data:
                rooms_data[room_name] = []
                
            rooms_data[room_name].append({
                "bmg_text": self.bmg_strings[b_idx],
                "bmg_id": b_id,
                "bmg_idx": b_idx,
                "t_item": t_item
            })

        # 4. Form chronological chunks based on natural micro-scenes inside each Room
        mapped_scenes = []
        window_size = 8
        
        for room_name, items in rooms_data.items():
            if self.is_cancelled:
                return []
                
            # Group items inside this Room by their scene block
            # A scene block is either a contiguous list of items with the same "Action:" timestamp,
            # or contiguous items that don't have "Action:" (we will group them by window_size=8)
            grouped_chunks = []
            current_action_ts = None
            current_action_chunk = []
            generic_chunk = []
            
            for x in items:
                ts = x["t_item"].get("timestamp", "")
                
                if ts.startswith("Action:"):
                    # If we had a running generic chunk, flush it first
                    if generic_chunk:
                        # Split generic chunk into chunks of window_size=8
                        for start_g in range(0, len(generic_chunk), window_size):
                            grouped_chunks.append(generic_chunk[start_g:start_g + window_size])
                        generic_chunk = []
                        
                    # If this is a different action, flush the previous action chunk
                    if current_action_ts and ts != current_action_ts:
                        if current_action_chunk:
                            grouped_chunks.append(current_action_chunk)
                        current_action_chunk = []
                        
                    current_action_ts = ts
                    current_action_chunk.append(x)
                else:
                    # If we had a running action chunk, flush it
                    if current_action_chunk:
                        grouped_chunks.append(current_action_chunk)
                        current_action_chunk = []
                        current_action_ts = None
                        
                    generic_chunk.append(x)
                    
            # Flush remaining chunks
            if current_action_chunk:
                grouped_chunks.append(current_action_chunk)
            if generic_chunk:
                for start_g in range(0, len(generic_chunk), window_size):
                    grouped_chunks.append(generic_chunk[start_g:start_g + window_size])
                    
            # Transform grouped_chunks into mapped_scenes format
            for chunk in grouped_chunks:
                if not chunk:
                    continue
                bmg_texts = [x["bmg_text"] for x in chunk]
                bmg_ids = [x["bmg_id"] for x in chunk]
                bmg_indices = [x["bmg_idx"] for x in chunk]
                t_items = [x["t_item"] for x in chunk]
                
                # Determine timestamp from the first item
                timestamp = "Generic"
                for item in t_items:
                    if item.get("timestamp"):
                        timestamp = item.get("timestamp")
                        break
                        
                # Build speaker map from chunk mappings
                speaker_map = {}
                for x in chunk:
                    bmg_id = x["bmg_id"]
                    t_item = x["t_item"]
                    if t_item and t_item.get("speaker"):
                        speaker_map[bmg_id] = t_item.get("speaker")
                        
                mapped_scenes.append({
                    "bmg_start_idx": bmg_indices[0],
                    "bmg_texts": bmg_texts,
                    "bmg_ids": bmg_ids,
                    "transcript_window": t_items,
                    "timestamp": timestamp,
                    "room_name": room_name,
                    "speaker_map": speaker_map
                })

        # Sort mapped scenes so they follow the chronological start index
        mapped_scenes.sort(key=lambda x: x["bmg_start_idx"])
        return mapped_scenes

    def _save_mapped_data_to_local_palace(self, mapped_scenes: List[Dict[str, Any]]):
        """Quickly save mapped scenes directly to MemePalace client without AI additions."""
        import sqlite3
        conn = None
        if self.client.db_path:
            try:
                conn = sqlite3.connect(self.client.db_path)
                conn.execute("BEGIN TRANSACTION")
            except Exception as e:
                log_error(f"Failed to start transaction in _save_mapped_data_to_local_palace: {e}")
                conn = None

        try:
            self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}", conn=conn)
            
            total = len(mapped_scenes)
            for idx, scene in enumerate(mapped_scenes):
                if self.is_cancelled:
                    break
                if idx % 10 == 0 or idx == total - 1:
                    pct = int((idx / total) * 100)
                    self.progress.emit(pct, 100, f"Saving mapped scenes to database: {idx + 1}/{total}...")
                    
                room_name = scene["room_name"]
                self.client.add_room(self.wing_name, room_name, f"Chronological Scene at timeline: {scene['timestamp']}", conn=conn)
                
                # Store dialogues verbatim in a Drawer
                content = "DIALOGUES:\n"
                for bmg_text, bmg_id in zip(scene["bmg_texts"], scene["bmg_ids"]):
                    content += f"[{bmg_id}]: {bmg_text}\n"
                    
                self.client.add_drawer(
                    self.wing_name, 
                    room_name, 
                    "dialogue_lines", 
                    content, 
                    {
                        "bmg_start_idx": scene["bmg_start_idx"], 
                        "timestamp": scene["timestamp"],
                        "speaker_map": scene.get("speaker_map", {})
                    },
                    conn=conn
                )
            if conn:
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def _save_single_scene_locally(self, scene: Dict[str, Any], conn: Optional[sqlite3.Connection] = None):
        """Helper to save a single scene directly without AI queries."""
        local_conn = conn
        is_local_trans = False
        if local_conn is None and self.client.db_path:
            try:
                local_conn = sqlite3.connect(self.client.db_path)
                local_conn.execute("BEGIN TRANSACTION")
                is_local_trans = True
            except Exception as e:
                log_error(f"Failed to start transaction in _save_single_scene_locally: {e}")
                local_conn = None

        try:
            room_name = scene["room_name"]
            self.client.add_room(self.wing_name, room_name, f"Timeline context: {scene['timestamp']}", conn=local_conn)
            dialogue_block = ""
            for bmg_text, bmg_id in zip(scene["bmg_texts"], scene["bmg_ids"]):
                dialogue_block += f"[{bmg_id}]: {bmg_text}\n"
            self.client.add_drawer(
                self.wing_name, 
                room_name, 
                "dialogues", 
                dialogue_block, 
                {
                    "bmg_start_idx": scene["bmg_start_idx"], 
                    "timestamp": scene["timestamp"],
                    "speaker_map": scene.get("speaker_map", {})
                },
                conn=local_conn
            )
            if is_local_trans and local_conn:
                local_conn.commit()
        except Exception as e:
            if is_local_trans and local_conn:
                local_conn.rollback()
            raise e
        finally:
            if is_local_trans and local_conn:
                local_conn.close()

    def _generate_palace_via_llm(self, mapped_scenes: List[Dict[str, Any]]):
        """Query AI Provider to generate deep visual context and relation updates."""
        self.client.add_wing(self.wing_name, f"AI-Assisted Memory Palace for {self.wing_name}")
        
        total_scenes = len(mapped_scenes)
        self.log.emit(f"Starting AI generation for {total_scenes} scenes...")
        
        for idx, scene in enumerate(mapped_scenes):
            if self.is_cancelled:
                return

            room_name = scene["room_name"]

            # 1. Check if this scene has already been AI-annotated in database (Incremental building!)
            if self.client.has_room(self.wing_name, room_name):
                self.log.emit(f"[Scene {idx+1}] Already AI annotated in local database from a previous run. Skipping to save tokens.")
                continue

            # 2. Check if all dialogues in this mapped scene are already translated
            scene_start = scene["bmg_start_idx"]
            scene_len = len(scene["bmg_texts"])
            all_translated = True
            
            if self.bmg_translation_states:
                for offset in range(scene_len):
                    global_idx = scene_start + offset
                    if global_idx < len(self.bmg_translation_states):
                        if not self.bmg_translation_states[global_idx]:
                            all_translated = False
                            break
                    else:
                        all_translated = False
            else:
                all_translated = False

            if all_translated:
                self.log.emit(f"[Scene {idx+1}] All lines already translated. Saving locally and skipping AI annotation to save tokens.")
                self._save_single_scene_locally(scene)
                continue

            # Update progress (Phase 2 is 50% to 100%)
            pct = 50 + int((idx / total_scenes) * 50)
            self.progress.emit(pct, 100, f"AI Annotating Scene {idx + 1}/{total_scenes}...")
            
            room_name = scene["room_name"]
            self.client.add_room(self.wing_name, room_name, f"Timeline context: {scene['timestamp']}")
            
            # 1. Format dialogues for prompt
            dialogue_block = ""
            for bmg_text, bmg_id in zip(scene["bmg_texts"], scene["bmg_ids"]):
                dialogue_block += f"ID: {bmg_id} | Text: {bmg_text}\n"
                
            transcript_block = ""
            for t_item in scene["transcript_window"]:
                transcript_block += f"- [{t_item.get('timestamp')} - {t_item.get('speaker', 'Unknown')}]: {t_item.get('text')}\n"

            # 2. Formulate Prompt
            # Extract only the glossary entries relevant to this specific scene to prevent prompt bloating
            relevant_entries = []
            if self.glossary_manager:
                combined_scene_text = "\n".join(scene["bmg_texts"]) + "\n" + "\n".join([t.get('text', '') for t in scene["transcript_window"]])
                relevant_entries = self.glossary_manager.get_relevant_terms(combined_scene_text)
            elif self.glossary_entries:
                combined_scene_text = ("\n".join(scene["bmg_texts"]) + "\n" + "\n".join([t.get('text', '') for t in scene["transcript_window"]])).lower()
                for entry in self.glossary_entries:
                    if entry.original.lower() in combined_scene_text:
                        relevant_entries.append(entry)

            glossary_text = ""
            if relevant_entries:
                glossary_text = "GLOSSARY FOR TERMINOLOGY & CHARACTER NAMES CONSISTENCY IN THIS SCENE:\n"
                for entry in relevant_entries:
                    glossary_text += f"- '{entry.original}' -> '{entry.translation}'"
                    if entry.notes:
                        glossary_text += f" (Note: {entry.notes})"
                    glossary_text += "\n"

            system_prompt = (
                "You are an expert game translation director. Your task is to analyze chronological "
                "game script scenes and synthesize rich visual/story context for AI localization translators."
            )
            
            user_prompt = f"""
Analyze this game dialogue scene and generate a context record in JSON format.

{glossary_text}

DIALOUGE LINES FROM FILE (Unordered but grouped):
{dialogue_block}

CHRONOLOGICAL WALKTHROUGH/TRANSCRIPT MATCH (If any):
{transcript_block}

Respond ONLY with a JSON object containing:
1. "visual_context": A vivid description of what is happening on screen, the environment, mood, and character postures/expressions. You must write this description strictly in the target translation language: {self.target_lang} (e.g. Ukrainian).
2. "relations": An array of objects showing character relationships found or updated in this scene: {{"source": "character_name", "relation": "feeling/status", "target": "other_character"}}. Write all character names ("source" and "target") and the "relation" descriptions strictly in {self.target_lang}. Character names must correspond to their translation/glossary entries if present (e.g., if GLOSSARY maps 'Link' to 'Лінк', use 'Лінк').
3. "speaker_map": A dictionary mapping dialogue Line_IDs (exactly as provided in the 'DIALOUGE LINES FROM FILE' section, e.g., "zelda_tp_script_Str_12") to actual speaker names (e.g. "RUSL", "MIDNA", "LINK"). You must analyze every single dialogue line from the input and identify its speaker based on the chronological transcript and context. Map every Line_ID key to its corresponding character name, written strictly in {self.target_lang}. Character names must align exactly with the GLOSSARY provided above if present.

JSON format example (assuming target language is Ukrainian):
{{
  "visual_context": "Лінк знаходиться в селищі Ордон. Сонце світить. Колін сором'язливо пропонує Лінку вудку...",
  "relations": [
    {{"source": "Колін", "relation": "захоплюється", "target": "Лінк"}}
  ],
  "speaker_map": {{
    "zelda_tp_script_Str_12": "Колін",
    "zelda_tp_script_Str_13": "Руслан"
  }}
}}
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            mw = getattr(self.glossary_manager, 'mw', None) if self.glossary_manager else None

            try:
                log_ai_traffic(mw, "mempalace_scene_annotation", messages)
                response: ProviderResponse = self.ai_provider.translate(messages, session=None)
                log_ai_traffic(mw, "mempalace_scene_annotation", messages, response_text=response.text)
                
                # Parse JSON safely
                cleaned_text = response.text.strip()
                # strip markdown blocks if model wrapped JSON
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text.split("```")[1]
                    if cleaned_text.startswith("json"):
                        cleaned_text = cleaned_text[4:]
                
                data = json.loads(cleaned_text.strip())
                visual_context = data.get("visual_context", "No context generated.")
                relations = data.get("relations", [])
                speaker_map = data.get("speaker_map", {})
                
                # Log success to worker log console
                self.log.emit(f"[Scene {idx+1}] AI annotated successfully. Speakers: {list(speaker_map.values())}")
                
                # Write to MemPalace Wing/Room/Drawers inside transaction
                import sqlite3
                conn = None
                if self.client.db_path:
                    try:
                        conn = sqlite3.connect(self.client.db_path)
                        conn.execute("BEGIN TRANSACTION")
                    except Exception as e_tx:
                        log_error(f"Failed to start transaction for AI scene writing: {e_tx}")
                        conn = None

                try:
                    # Write verbatim dialogues
                    self.client.add_drawer(
                        self.wing_name, 
                        room_name, 
                        "dialogues", 
                        dialogue_block, 
                        {"bmg_start_idx": scene["bmg_start_idx"], "timestamp": scene["timestamp"], "speaker_map": speaker_map},
                        conn=conn
                    )
                    
                    # Write visual scene context drawer
                    self.client.add_drawer(
                        self.wing_name, 
                        room_name, 
                        "visual_scene_context", 
                        visual_context, 
                        {"timestamp": scene["timestamp"]},
                        conn=conn
                    )
                    
                    # Write relations to temporal knowledge graph
                    for rel in relations:
                        self.client.add_relation(
                            self.wing_name, 
                            rel.get("source", "Unknown"), 
                            rel.get("relation", "relates"), 
                            rel.get("target", "Unknown"), 
                            valid_from=scene["timestamp"],
                            conn=conn
                        )
                    if conn:
                        conn.commit()
                except Exception as e_db:
                    if conn:
                        conn.rollback()
                    log_error(f"Error saving AI results to DB: {e_db}")
                    raise e_db
                finally:
                    if conn:
                        conn.close()
                    
            except Exception as e:
                log_ai_traffic(mw, "mempalace_scene_annotation", messages, error=str(e))
                log_error(f"Error querying AI in worker for scene {idx}: {e}")
                self.log.emit(f"[Scene {idx+1}] AI Annotation failed: {str(e)}. Saving local fallback only.")
                
                # Write fallback data
                self.client.add_drawer(
                    self.wing_name, 
                    room_name, 
                    "dialogues", 
                    dialogue_block, 
                    {"bmg_start_idx": scene["bmg_start_idx"], "timestamp": scene["timestamp"]}
                )
