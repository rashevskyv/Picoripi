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
        self.mapped_results = []  # Pairs of BMG strings mapped to transcript timeline

    def cancel(self):
        self.is_cancelled = True
        self.log.emit("Cancellation requested...")

    def run(self):
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
            if not text:
                return ""
            # Replace known dynamic name tags (e.g. {escape:0:0000} -> "Link") before stripping tags
            for tag, name in _dynamic_name_tags.items():
                text = text.replace(tag, name)
            # Remove XML/custom tags like {Color:Red}, [PLAYER], {escape:...}
            text_no_tags = re.sub(r'\{[^}]+\}', '', text)
            text_no_tags = re.sub(r'\[[^]]+\]', '', text_no_tags)
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

class MemePalaceScriptAnalyzerWorker(QThread):
    # Signals for UI communication
    progress = pyqtSignal(int, int, str)  # current, total, status
    log = pyqtSignal(str)                 # log message
    finished = pyqtSignal(bool, str)      # success, message

    def __init__(self, 
                 client: MemePalaceClient, 
                 file_path: str, 
                 ai_provider: BaseTranslationProvider, 
                 wing_name: str = "Zelda_TP",
                 glossary_manager: Optional[Any] = None,
                 target_lang: str = "Ukrainian",
                 plugin_name: Optional[str] = None,
                 mw=None):
        super().__init__()
        self.client = client
        self.file_path = file_path
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.glossary_manager = glossary_manager
        self.target_lang = target_lang
        self.plugin_name = plugin_name
        self.mw = mw or (getattr(glossary_manager, 'mw', None) if glossary_manager else None)
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        self.log.emit("Script pre-analysis cancellation requested...")

    def _load_plugin_prompts(self) -> dict:
        """Load prompts.json for active plugin if available."""
        from pathlib import Path
        prompts_data = {}
        if self.plugin_name:
            prompts_path = Path("plugins") / self.plugin_name / "translation_prompts" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("plugins") / "common" / "defaults" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("translation_prompts") / "prompts.json"
            
            if prompts_path.exists():
                try:
                    prompts_data = json.loads(prompts_path.read_text("utf-8"))
                    self.log.emit(f"MemePalace Worker: Loaded per-plugin prompts config from {prompts_path}")
                except Exception as e_load:
                    log_error(f"Failed to load prompts.json for plugin {self.plugin_name}: {e_load}")
        return prompts_data

    def _get_mining_prompts(self, script_segment: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve Mining prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        p_sys = m_section.get("mining_system_prompt")
        p_usr = m_section.get("mining_user_prompt")

        if p_sys and p_usr:
            return p_sys.format(target_lang=self.target_lang), p_usr.format(script_segment=script_segment, target_lang=self.target_lang)

        # Fallback built-in prompts
        if self.target_lang == "Ukrainian":
            system_prompt = (
                "Ви — професійний сценарист відеоігор та директор з локалізації. Ваше завдання — проаналізувати список персонажів "
                "та вступний текст ігрового скрипту, вилучити всіх ключових персонажів, їхні профілі, важливі предмети, "
                "локації чи термінологію, а також соціальні зв'язки. Ви повинні писати всі детальні описи, атрибути, "
                "описи стосунків та типи звертання виключно українською мовою."
            )
            user_prompt = f"""
Проаналізуйте наступний вступний фрагмент ігрового скрипту.
Вилучіть:
1. Усіх згаданих персонажів з їхнім детальним описом та роллю в сюжеті.
2. Атрибути персонажів для забезпечення послідовності перекладу українською мовою:
   - "gender": 'male', 'female' або 'unknown'.
   - "age_group": 'child', 'adult', 'elder' або 'unknown'.
   - "relationship_summary": детальний опис того, ким є цей персонаж для інших, виключно українською мовою (наприклад, 'наставник Лінка, чоловік Улі').
   - "address_type": граматичний статус звертання виключно українською мовою (наприклад, 'звертається до Лінка неформально (на "ти"), до мера звертається шанобливо/формально (на "ви")').
   - "description": детальний опис характеру та сюжетної ролі виключно українською мовою.
3. Ключові ігрові/сюжетні предмети, локації або спеціальну термінологію ("objects_and_terms") з чітким описом того, що це таке, виключно українською мовою.
4. Соціальні зв'язки між персонажами, які визначають стиль їхнього спілкування в українському перекладі:
   - "addresses_informally" (використовують "ти"): для близьких друзів, рівних за статусом, родини, дітей чи наставників, що звертаються до учнів.
   - "addresses_respectfully" (шанобливе "ти" або шанобливе "ви").
   - "addresses_formally" (використовують "ви"): для королівських осіб, високопосадовців, незнайомців або при формальній ієрархії.

ВСТУПНИЙ СЕГМЕНТ СКРИПТУ:
{script_segment}

У відповідь поверніть ВИКЛЮЧНО валідний об'єкт JSON. Не додавайте блоки markdown чи будь-які інші пояснення.
Структура JSON:
{{
  "characters": [
    {{
      "name": "RUSL",
      "gender": "male",
      "age_group": "adult",
      "relationship_summary": "наставник Лінка, чоловік Улі, батько Коліна",
      "address_type": "звертається до Лінка неформально ('ти'), до мера звертається шанобливо/формально ('ви')",
      "description": "Хоробрий мечник із селища Ордон, який є наставником Лінка та просить його доставити щит до замку Хайрул."
    }}
  ],
  "objects_and_terms": [
    {{
      "name": "Ordon Shield",
      "description": "Дерев'яний щит з шкіряними елементами, виготовлений Руслем для того, щоб Лінк доставив його до замку Хайрул."
    }}
  ],
  "relations": [
    {{"source": "RUSL", "relation": "addresses_informally", "target": "LINK", "reason": "mentor speaking to student"}},
    {{"source": "LINK", "relation": "addresses_respectfully", "target": "RUSL", "reason": "student speaking to mentor"}}
  ]
}}
"""
        else:
            system_prompt = (
                f"You are an expert game narrative architect and localization director. Your task is to analyze a game script's "
                f"character list and introduction text, and extract all key characters, their character profiles, "
                f"important gameplay/story objects, locations, or terminology, and social relations. "
                f"You must write all detailed descriptions, attributes, relationship summaries, and address types strictly in {self.target_lang}."
            )
            user_prompt = f"""
Analyze the following introduction segment of a game script.
Extract:
1. All characters mentioned with their detailed description and specific story role.
2. Character attributes for target language translation consistency (specifically for {self.target_lang} translation):
   - "gender": 'male', 'female', or 'unknown'.
   - "age_group": 'child', 'adult', 'elder', or 'unknown'.
   - "relationship_summary": detailed explanation of who this character is to others strictly in {self.target_lang} (e.g., 'mentor of Link').
   - "address_type": grammar address status strictly in {self.target_lang} (e.g., 'speaks to Link informally').
   - "description": detailed context and personality description strictly in {self.target_lang}.
3. Key gameplay/story objects, items, locations, or special terminology ("objects_and_terms") found in the script with a clear description of what they are, written strictly in {self.target_lang}.
4. Social relations between characters that dictate how they should speak to each other in {self.target_lang} translation:
   - "addresses_informally" (meaning they use "ти"): for close friends, equals, family, children, mentors speaking to students.
   - "addresses_respectfully" (meaning they use respect forms).
   - "addresses_formally" (meaning they use formal "ви").
   
INTRO TEXT SEGMENT:
{script_segment}

Respond ONLY with a valid JSON object. Do not include markdown blocks or any other explanation.
JSON structure:
{{
  "characters": [
    {{
      "name": "RUSL",
      "gender": "male",
      "age_group": "adult",
      "relationship_summary": "mentor of Link, husband of Uli",
      "address_type": "addresses Link informally, addresses mayor respectfully",
      "description": "Brave swordsman from Ordon..."
    }}
  ],
  "objects_and_terms": [
    {{
      "name": "Ordon Shield",
      "description": "Wooden shield crafted by Rusl..."
    }}
  ],
  "relations": [
    {{"source": "RUSL", "relation": "addresses_informally", "target": "LINK", "reason": "mentor speaking to student"}}
  ]
}}
"""
        return system_prompt, user_prompt

    def _get_synthesis_prompts(self, term_name: str, existing_notes: str, details: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve Synthesis prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        s_sys = m_section.get("synthesis_system_prompt")
        s_usr = m_section.get("synthesis_user_prompt")

        if s_sys and s_usr:
            return s_sys.format(target_lang=self.target_lang), s_usr.format(
                term_name=term_name,
                existing_notes=existing_notes,
                details=details,
                target_lang=self.target_lang
            )

        if self.target_lang == "Ukrainian":
            synth_system_prompt = (
                "Ви — професійний лексикограф та перекладач відеоігор. Ваше завдання — об'єднати існуючі нотатки/опис "
                "терміна у глосарії з новими деталями, знайденими в ігровому скрипті. Ви повинні синтезувати їх "
                "у один зв'язний, високоякісний, структурований та детальний опис (notes), написаний виключно українською мовою."
            )
            synth_user_prompt = f"""
Синтезуйте наступну інформацію для терміна/персонажа '{term_name}':

Існуючий опис у глосарії (нотатки):
{existing_notes}

Нові сюжетні деталі зі скрипту:
{details}

Створіть єдиний, красиво структурований та детальний опис, написаний виключно українською мовою. Уникайте повторень.
Збережіть увесь попередній контекст, обов'язково переклавши його українською мовою (якщо він був англійською), та гармонійно інтегруйте нову інформацію (стать, вік, стосунки, стилі звертання та роль у грі).
Не повертайте нічого, крім фінального синтезованого тексту українською мовою. Не загортайте в блоки markdown або JSON. Поверніть лише чистий текст опису.
"""
        else:
            synth_system_prompt = (
                f"You are an expert game translation lexicographer. Your task is to combine the existing glossary entry notes "
                f"with new narrative insights extracted from the game script. You must synthesize them into one coherent, premium, well-structured, "
                f"highly detailed description (notes) written strictly in {self.target_lang}."
            )
            synth_user_prompt = f"""
Synthesize the following information for the term/character '{term_name}':

Existing Glossary Description (Notes):
{existing_notes}

New Script Insights:
{details}

Produce a unified, beautifully structured, and highly detailed description written strictly in {self.target_lang}. Avoid redundancy. 
Keep any pre-existing context while seamlessly translating it and integrating the new information (like gender, age, relationships, address styles, and gameplay role). 
Do not output anything else but the synthesized {self.target_lang} text. Do not wrap in markdown blocks or JSON. Just print the final synthesized notes paragraph or text body.
"""
        return synth_system_prompt, synth_user_prompt

    def _get_new_term_prompts(self, term_name: str, details: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve New Term prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        nt_sys = m_section.get("new_term_system_prompt")
        nt_usr = m_section.get("new_term_user_prompt")

        if nt_sys and nt_usr:
            return nt_sys.format(target_lang=self.target_lang), nt_usr.format(
                term_name=term_name,
                details=details,
                target_lang=self.target_lang
            )

        if self.target_lang == "Ukrainian":
            new_term_system_prompt = (
                "Ви — професійний перекладач ретро-ігор з англійської на українську мову. Ваше завдання — "
                "запропонувати природний переклад або транслітерацію назви терміна українською мовою, "
                "а також згенерувати детальний структурований опис (нотатки) виключно українською мовою на основі наданих сюжетних деталей."
            )
            new_term_user_prompt = f"""
Створити новий запис у глосарії для терміна: '{term_name}'

Сюжетні деталі зі скрипту:
{details}

У відповідь поверніть ВИКЛЮЧНО валідний об'єкт JSON. Не додавайте блоки markdown чи будь-які інші пояснення.
Структура JSON:
{{
  "translation": "Природний переклад або транслітерація українською мовою (наприклад, 'Русль' або 'Ордонський щит')",
  "notes": "Високоякісний структурований опис, написаний виключно українською мовою, який містить стать, вікову групу, стосунки, форми звертання та сюжетний контекст."
}}
"""
        else:
            new_term_system_prompt = (
                f"You are an expert retro game translator from English to {self.target_lang}. "
                f"Your task is to provide a natural translated or transliterated name for the term in {self.target_lang}, "
                f"and generate a premium structured description (notes) written strictly in {self.target_lang} based on script insights."
            )
            new_term_user_prompt = f"""
Create a new glossary record for term: '{term_name}'

Script Insights:
{details}

Respond ONLY with a valid JSON object. Do not include markdown blocks or any other explanation.
JSON structure:
{{
  "translation": "Natural translation or transliteration in {self.target_lang} (e.g. 'Rusl')",
  "notes": "Premium structured description written strictly in {self.target_lang} including gender, age group, relationships, address forms, and narrative context."
}}
"""
        return new_term_system_prompt, new_term_user_prompt

    def run(self):
        try:
            self.log.emit("Starting AI Script Pre-Analyzer...")
            self.progress.emit(10, 100, "Reading script introduction...")

            # 1. Read first 2000 lines of the script (where cast/intro resides)
            import os
            if not os.path.exists(self.file_path):
                self.finished.emit(False, f"Script file not found: {self.file_path}")
                return

            if self.file_path.lower().endswith(".md"):
                self.log.emit("Markdown script detected. Processing locally without AI queries...")
                self.progress.emit(25, 100, "Parsing Markdown script structures...")
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(self.file_path)
                
                characters = parsed.get("characters", [])
                terms = parsed.get("terms", [])
                
                # Format objects_and_terms as expected by the database step
                objects_and_terms = []
                for t in terms:
                    objects_and_terms.append({
                        "name": t.get("original", t.get("name")),
                        "description": t.get("description", "")
                    })

                self.progress.emit(50, 100, "Processing character profiles and writing to Glossary...")
                if self.glossary_manager:
                    # process characters
                    for char in characters:
                        term_name = char["name"]
                        if self.target_lang == "Ukrainian":
                            notes = f"Стать: {char['gender']}. Вік: {char['age_group']}. Зв'язки: {char['relationship_summary']}. Звертання: {char['address_type']}. Опис: {char['description']}"
                        else:
                            notes = f"Gender: {char['gender']}. Age: {char['age_group']}. Relations: {char['relationship_summary']}. Address Style: {char['address_type']}. Description: {char['description']}"
                        
                        existing = self.glossary_manager.get_entry(term_name)
                        if existing:
                            self.glossary_manager.update_entry(
                                original=existing.original,
                                translation=char.get("translation", existing.translation),
                                notes=notes
                            )
                        else:
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=char.get("translation", term_name),
                                notes=notes,
                                section="Characters"
                            )

                    # process terms
                    for t in terms:
                        term_name = t["original"]
                        notes = t.get("description", "")
                        existing = self.glossary_manager.get_entry(term_name)
                        if existing:
                            self.glossary_manager.update_entry(
                                original=existing.original,
                                translation=t.get("translation", existing.translation),
                                notes=notes
                            )
                        else:
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=t.get("translation", term_name),
                                notes=notes,
                                section="Terms"
                            )
                    
                    try:
                        self.glossary_manager.save_to_disk()
                        self.log.emit("Successfully saved updated glossary database (.md table) to disk.")
                    except Exception as disk_err:
                        log_error(f"Failed to save glossary to disk: {disk_err}")
                        self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

                # Build relations from characters profiles
                relations = []
                for char in characters:
                    source_name = char.get("translation", char.get("name")).upper()
                    if char.get("relationship_summary"):
                        relations.append({
                            "source": source_name,
                            "relation": char.get("relationship_summary"),
                            "target": "Global_Cast"
                        })
                    if char.get("address_type"):
                        relations.append({
                            "source": source_name,
                            "relation": char.get("address_type"),
                            "target": "Style"
                        })

                self.progress.emit(90, 100, "Writing character profiles to SQLite Memory Palace...")
                # Write to local SQLite Palace
                self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}")
                cast_content = "CHARACTER CAST PROFILES:\n"
                for char in characters:
                    name = char.get("name", "Unknown").upper()
                    desc = char.get("description", "")
                    cast_content += f"- {name}: {desc}\n"
                    
                self.client.add_room(self.wing_name, "Global_Cast_Profiles", "Global character details and profiles.")
                self.client.add_drawer(
                    self.wing_name,
                    "Global_Cast_Profiles",
                    "character_cast_profiles",
                    cast_content,
                    {"characters": characters}
                )

                for rel in relations:
                    self.client.add_relation(
                        self.wing_name,
                        rel["source"],
                        rel["relation"],
                        rel["target"],
                        valid_from="Global_Cast"
                    )
                    self.log.emit(f"Saved Relation: {rel['source']} -[{rel['relation']}]-> {rel['target']}")

                self.progress.emit(100, 100, "Script pre-analysis and glossary synthesis completed!")
                self.finished.emit(True, f"Successfully parsed Markdown script locally! Found {len(characters)} characters. Glossary has been synchronized.")
                return

            # Read with cp1252 to handle special symbols in GameFAQ scripts
            with open(self.file_path, "r", encoding="cp1252", errors="replace") as f:
                intro_lines = []
                for _ in range(2000):
                    line = f.readline()
                    if not line:
                        break
                    intro_lines.append(line)

            script_segment = "".join(intro_lines)
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            self.progress.emit(25, 100, "Sending script segment to AI for terminology & character mining...")
            self.log.emit(f"Extracted {len(intro_lines)} lines for AI Persona Miner. Querying LLM...")

            # Load prompts.json configuration (per-plugin)
            prompts_data = self._load_plugin_prompts()

            # 2. Formulate Prompt for Character and Term mining
            system_prompt, user_prompt = self._get_mining_prompts(script_segment, prompts_data)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            log_ai_traffic(self.mw, "mempalace_terminology_mining", messages)
            try:
                response = self.ai_provider.translate(messages, session=None)
                log_ai_traffic(self.mw, "mempalace_terminology_mining", messages, response_text=response.text)
            except Exception as e_mining:
                log_ai_traffic(self.mw, "mempalace_terminology_mining", messages, error=str(e_mining))
                raise e_mining
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            self.progress.emit(50, 100, "Processing AI response and writing to SQLite...")
            
            # 3. Parse JSON response using robust parser
            data = robust_json_loads(response.text)
            characters = data.get("characters", [])
            objects_and_terms = data.get("objects_and_terms", [])
            relations = data.get("relations", [])

            self.log.emit(f"AI found {len(characters)} character profiles, {len(objects_and_terms)} objects/terms, and {len(relations)} relations.")

            # 4. Process and enrich Picoripi Glossary
            if self.glossary_manager:
                self.log.emit(f"Active Glossary Manager detected. Populating and synthesizing glossary entries in {self.target_lang}...")
                
                # Combine characters and objects for glossary processing
                items_to_process = []
                for char in characters:
                    items_to_process.append({
                        "name": char.get("name", "").strip(),
                        "type": "character",
                        "gender": char.get("gender", "unknown"),
                        "age_group": char.get("age_group", "unknown"),
                        "relationship_summary": char.get("relationship_summary", ""),
                        "address_type": char.get("address_type", ""),
                        "description": char.get("description", "")
                    })
                for obj in objects_and_terms:
                    items_to_process.append({
                        "name": obj.get("name", "").strip(),
                        "type": "object",
                        "description": obj.get("description", "")
                    })

                total_items = len(items_to_process)
                for item_idx, item in enumerate(items_to_process):
                    if self.is_cancelled:
                        break
                    
                    term_name = item["name"]
                    if not term_name:
                        continue
                    
                    # Update progress slightly during glossary loop (from 50% to 85%)
                    sub_pct = 50 + int((item_idx / total_items) * 35)
                    self.progress.emit(sub_pct, 100, f"Synthesizing Glossary Entry {item_idx + 1}/{total_items}: {term_name}...")

                    # Search in glossary manager (case-insensitive)
                    existing_entry = self.glossary_manager.get_entry(term_name)
                    
                    if existing_entry:
                        # Term exists! Synthesize notes with existing ones, preserving translation!
                        self.log.emit(f"Term '{term_name}' exists in glossary. Synthesizing notes via AI strictly in {self.target_lang} (preserving translation)...")
                        
                        existing_notes = existing_entry.notes or ""
                        
                        if item["type"] == "character":
                            details = f"""
- Тип сутності: Персонаж
- Стать: {item['gender']}
- Вікова категорія: {item['age_group']}
- Стосунки/Родинні зв'язки: {item['relationship_summary']}
- Форми звертання (на "ти" / на "ви"): {item['address_type']}
- Новий сюжетний контекст: {item['description']}
"""
                        else:
                            details = f"""
- Тип сутності: Предмет/Локація/Термін
- Новий сюжетний контекст: {item['description']}
"""
                        
                        synth_system_prompt, synth_user_prompt = self._get_synthesis_prompts(
                            term_name, existing_notes, details, prompts_data
                        )

                        synth_messages = [
                            {"role": "system", "content": synth_system_prompt},
                            {"role": "user", "content": synth_user_prompt}
                        ]
                        
                        try:
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages)
                            synth_response = self.ai_provider.translate(synth_messages, session=None)
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages, response_text=synth_response.text)
                            synthesized_notes = synth_response.text.strip()
                            
                            # Safely update the entry in the glossary
                            self.glossary_manager.update_entry(
                                original=existing_entry.original,
                                translation=existing_entry.translation,
                                notes=synthesized_notes
                            )
                            self.log.emit(f"SUCCESS: Synthesized entry for '{term_name}' (notes updated in {self.target_lang}, translation '{existing_entry.translation}' kept).")
                        except Exception as e_synth:
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages, error=str(e_synth))
                            log_error(f"Failed to synthesize notes for existing term {term_name}: {e_synth}")
                            self.log.emit(f"WARNING: Notes synthesis failed for '{term_name}': {str(e_synth)}")
                    
                    else:
                        # New term! Translate term and construct initial notes in self.target_lang
                        self.log.emit(f"Term '{term_name}' is new. Translating name and creating structured notes in {self.target_lang} via AI...")
                        
                        if item["type"] == "character":
                            details = f"""
- Тип сутності: Персонаж
- Стать: {item['gender']}
- Вікова категорія: {item['age_group']}
- Стосунки/Родинні зв'язки: {item['relationship_summary']}
- Форми звертання (на "ти" / на "ви"): {item['address_type']}
- Опис: {item['description']}
"""
                        else:
                            details = f"""
- Тип сутності: Предмет/Локація/Термін
- Опис: {item['description']}
"""

                        new_term_system_prompt, new_term_user_prompt = self._get_new_term_prompts(
                            term_name, details, prompts_data
                        )

                        new_term_messages = [
                            {"role": "system", "content": new_term_system_prompt},
                            {"role": "user", "content": new_term_user_prompt}
                        ]
                        
                        try:
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages)
                            new_term_response = self.ai_provider.translate(new_term_messages, session=None)
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages, response_text=new_term_response.text)
                            term_data = robust_json_loads(new_term_response.text)
                            translated_name = term_data.get("translation", term_name).strip()
                            synthesized_notes = term_data.get("notes", "").strip()
                            
                            # Add new entry to the glossary
                            section = "Characters" if item["type"] == "character" else "Terms"
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=translated_name,
                                notes=synthesized_notes,
                                section=section
                            )
                            self.log.emit(f"SUCCESS: Created new entry '{term_name}' -> '{translated_name}' in section '{section}' with description in {self.target_lang}.")
                        except Exception as e_new:
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages, error=str(e_new))
                            log_error(f"Failed to translate and save new term {term_name}: {e_new}")
                            self.log.emit(f"WARNING: Creation failed for new term '{term_name}': {str(e_new)}")

                # Write all glossary updates to disk
                try:
                    self.glossary_manager.save_to_disk()
                    self.log.emit("Successfully saved updated glossary database (.md table) to disk.")
                except Exception as disk_err:
                    log_error(f"Failed to save glossary to disk: {disk_err}")
                    self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

            self.progress.emit(90, 100, "Writing character profiles to SQLite Memory Palace...")

            # 5. Write to local SQLite Palace (for viewer consistency)
            self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}")
            
            # Save character cast profiles to a dedicated drawer in a special room
            cast_content = "CHARACTER CAST PROFILES:\n"
            for char in characters:
                name = char.get("name", "Unknown").upper()
                desc = char.get("description", "")
                cast_content += f"- {name}: {desc}\n"
                
            self.client.add_room(self.wing_name, "Global_Cast_Profiles", "Global character details and profiles.")
            self.client.add_drawer(
                self.wing_name,
                "Global_Cast_Profiles",
                "character_cast_profiles",
                cast_content,
                {"characters": characters}
            )

            # Write relations to temporal knowledge graph
            for rel in relations:
                source = rel.get("source", "Unknown").upper()
                relation = rel.get("relation", "addresses_informally")
                target = rel.get("target", "Unknown").upper()
                reason = rel.get("reason", "")
                
                self.client.add_relation(
                    self.wing_name,
                    source,
                    relation,
                    target,
                    valid_from="Global_Cast"
                )
                self.log.emit(f"Saved Relation: {source} -[{relation}]-> {target} ({reason})")

            self.progress.emit(100, 100, "Script pre-analysis and glossary synthesis completed!")
            self.finished.emit(True, f"Successfully parsed script! Found {len(characters)} characters and {len(relations)} relations. Glossary has been synchronized and saved to disk.")

        except Exception as e:
            log_error(f"Error in MemePalaceScriptAnalyzerWorker: {e}", exc_info=True)
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")

class MemePalaceChapterMapperWorker(QThread):
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: MemePalaceClient, composer, wing_name: str):
        super().__init__()
        self.client = client
        self.composer = composer
        self.wing_name = wing_name
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        import os
        try:
            self.log.emit("Starting Chapter Mapping Process...")
            script_path = self.composer._find_script_path()
            if not script_path or not os.path.exists(script_path):
                self.finished.emit(False, "Script file not found.")
                return

            self.log.emit(f"Parsing script file: {script_path}")
            if script_path.lower().endswith(".md"):
                self.log.emit("Markdown script detected. Segmenting using local markdown parser...")
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(script_path)
                chapters = parsed.get("chapters", [])
            else:
                from core.script_segmenter import segment_script_file
                chapters = segment_script_file(script_path)
                
            if not chapters:
                self.finished.emit(False, "No chapters found in the script.")
                return

            self.log.emit(f"Found {len(chapters)} chapters. Saving chapters to local DB...")
            self.client.save_chapters_to_db(self.wing_name, chapters)

            # Gather BMG strings from project workspace
            mw = self.composer.mw
            store = getattr(mw, "data_store", None)
            if not store or not store.data:
                self.finished.emit(False, "No project blocks loaded.")
                return

            total_blocks = len(store.data)
            mappings = []
            
            # Map BMG strings
            for b_idx in range(total_blocks):
                if self.is_cancelled:
                    self.finished.emit(False, "Process cancelled.")
                    return
                    
                block_label = self.composer._get_block_label(b_idx)
                block_strings = store.data[b_idx]
                total_strings = len(block_strings)
                
                self.progress.emit(b_idx, total_blocks, f"Mapping block {block_label} ({b_idx+1}/{total_blocks})...")
                self.log.emit(f"Mapping block '{block_label}'...")

                for s_idx, text in enumerate(block_strings):
                    if not text or not str(text).strip():
                        continue
                        
                    res = self.composer._find_speaker_in_script(b_idx, s_idx, text)
                    if res and isinstance(res, (tuple, list)) and len(res) == 2:
                        _, lines_str = res
                        if lines_str and lines_str != "NONE":
                            try:
                                first_line = int(lines_str.split(",")[0].strip())
                                mappings.append({
                                    "bmg_id": f"{block_label}_Str_{s_idx}",
                                    "script_line": first_line,
                                    "bmg_text": text
                                })
                            except Exception:
                                pass

            self.log.emit(f"Saving {len(mappings)} mappings to database...")
            self.client.save_mappings_to_db(self.wing_name, mappings)
            
            self.progress.emit(100, 100, "Mapping complete!")
            self.finished.emit(True, f"Mapped {len(chapters)} chapters and {len(mappings)} dialogue lines successfully.")
            
        except Exception as e:
            log_error(f"Error in MemePalaceChapterMapperWorker: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {e}")

class MemePalaceChapterAIAnalyzerWorker(QThread):
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: MemePalaceClient, ai_provider, chapter_id: int, num: str, title: str, content: str, start_line: int = 1, target_lang: str = "Ukrainian", mw=None):
        super().__init__()
        self.client = client
        self.ai_provider = ai_provider
        self.chapter_id = chapter_id
        self.num = num
        self.title = title
        self.content = content
        self.start_line = start_line
        self.target_lang = target_lang
        self.mw = mw
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            self.log.emit(f"Analyzing Chapter {self.num}: {self.title} via AI...")
            self.progress.emit(0, 100, "Preparing prompt...")
            
            if not self.ai_provider:
                self.finished.emit(False, "No AI Provider configured.")
                return

            # Number the lines of the content sequentially starting from start_line
            lines = self.content.splitlines()
            numbered_lines = []
            for i, line in enumerate(lines):
                actual_line_num = self.start_line + i
                numbered_lines.append(f"{actual_line_num}: {line}")
            
            content_snippet = "\n".join(numbered_lines)
            if len(content_snippet) > 35000:
                content_snippet = content_snippet[:35000] + "\n\n[TRUNCATED FOR LENGTH...]"

            system_prompt = (
                "You are an expert game narrative architect. Your task is to analyze a game script chapter "
                "and divide it into logical, sequential story events (micro-scenes or narrative events) with precise line ranges. "
                "Format your entire response as a single valid JSON array of objects. Each object must have fields: "
                "'start_line', 'end_line', 'event_name', and 'summary_ukrainian'. Ensure that there are no line gaps between events, "
                "and they cover the entire chapter sequentially."
            )
            
            user_prompt = f"""
Analyze the following game script chapter where each line is prefixed with its actual script file line number.
Divide this chapter into sequential, logical narrative events (scenes or plot points).
For each event, determine the start line and end line numbers and write a brief, 1-2 sentence summary of what is happening in Ukrainian.

CHAPTER: Chapter {self.num} - {self.title}

SCRIPT TEXT:
{content_snippet}

Your output must be a valid JSON array of objects. Do not wrap the JSON in markdown formatting (do not use ```json). Return ONLY the raw JSON string.
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            self.progress.emit(30, 100, "Sending request to AI...")
            self.log.emit("Sending request to AI provider. This might take 10-20 seconds...")
            
            log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages)
            try:
                response: ProviderResponse = self.ai_provider.translate(messages, session=None)
                log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages, response_text=response.text)
            except Exception as e_ch:
                log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages, error=str(e_ch))
                raise e_ch
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled.")
                return

            summary = response.text.strip()
            if not summary:
                self.finished.emit(False, "Received empty summary from AI.")
                return

            # Clean json formatting tags if any
            cleaned_json = summary
            if cleaned_json.startswith("```"):
                lines_json = cleaned_json.splitlines()
                if lines_json[0].startswith("```"):
                    lines_json = lines_json[1:]
                if lines_json and lines_json[-1].startswith("```"):
                    lines_json = lines_json[:-1]
                cleaned_json = "\n".join(lines_json).strip()

            self.progress.emit(80, 100, "Saving summary to database...")
            self.client.save_chapter_summary(self.chapter_id, cleaned_json)

            self.progress.emit(100, 100, "Analysis complete!")
            self.finished.emit(True, f"Chapter {self.num} successfully analyzed and saved.")

        except Exception as e:
            log_error(f"Error in MemePalaceChapterAIAnalyzerWorker: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {e}")


class MemePalaceCharacterProfilerWorker(QThread):
    # Signals for UI communication
    progress = pyqtSignal(int, int, str)  # current, total, status
    log = pyqtSignal(str)                 # log message
    finished = pyqtSignal(bool, str)      # success, message

    def __init__(self, 
                 client: MemePalaceClient, 
                 ai_provider: BaseTranslationProvider, 
                 wing_name: str = "Zelda_TP",
                 glossary_manager: Optional[Any] = None,
                 target_lang: str = "Ukrainian",
                 plugin_name: Optional[str] = None,
                 composer: Optional[Any] = None,
                 mw=None):
        super().__init__()
        self.client = client
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.glossary_manager = glossary_manager
        self.target_lang = target_lang
        self.plugin_name = plugin_name
        self.composer = composer
        self.mw = mw or (getattr(composer, 'mw', None) if composer else None) or (getattr(glossary_manager, 'mw', None) if glossary_manager else None)
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        self.log.emit("Character speech profiling cancellation requested...")

    def _fetch_zelda_wiki_description(self, char_name: str) -> str:
        """Search and fetch character description from Zelda Fandom Wiki."""
        import urllib.request
        import urllib.parse
        import json
        import re
        from utils.logging_utils import log_warning, log_info

        # Search specifically within Twilight Princess context
        query = f"{char_name} Twilight Princess"
        try:
            # 1. Search page on Zelda Wiki
            search_url = f"https://zelda.fandom.com/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
            req = urllib.request.Request(
                search_url, 
                headers={"User-Agent": "Picoripi Localization Tool/1.0 (Contact: admin@picoripi.org)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                search_results = data.get("query", {}).get("search", [])
                if not search_results:
                    return ""
                
                # Find the most relevant title
                title = search_results[0].get("title")
                if not title:
                    return ""
                    
            # 2. Fetch page introduction (extract) with redirects resolved
            extract_url = f"https://zelda.fandom.com/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles={urllib.parse.quote(title)}&redirects=1&format=json"
            req_extract = urllib.request.Request(
                extract_url,
                headers={"User-Agent": "Picoripi Localization Tool/1.0 (Contact: admin@picoripi.org)"}
            )
            with urllib.request.urlopen(req_extract, timeout=5) as response:
                data_extract = json.loads(response.read().decode('utf-8'))
                pages = data_extract.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    extract = page_data.get("extract", "")
                    if extract and extract.strip():
                        log_info(f"Successfully retrieved Zelda Wiki extract for '{char_name}' (Title: {title})")
                        return self._translate_wiki_to_target_lang(title, extract.strip())

            # 3. Fallback: Fetch raw Wikitext content from revisions if extract was empty (common with complex templates/infoboxes)
            log_info(f"Zelda Wiki extract was empty for '{char_name}'. Fetching raw Wikitext revisions content fallback...")
            revisions_url = f"https://zelda.fandom.com/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&titles={urllib.parse.quote(title)}&redirects=1&format=json"
            req_rev = urllib.request.Request(
                revisions_url,
                headers={"User-Agent": "Picoripi Localization Tool/1.0 (Contact: admin@picoripi.org)"}
            )
            with urllib.request.urlopen(req_rev, timeout=5) as response:
                data_rev = json.loads(response.read().decode('utf-8'))
                pages_rev = data_rev.get("query", {}).get("pages", {})
                for page_id, page_data in pages_rev.items():
                    revisions = page_data.get("revisions", [])
                    if revisions:
                        slots = revisions[0].get("slots", {})
                        raw_text = ""
                        if "main" in slots:
                            raw_text = slots["main"].get("*", "") or slots["main"].get("content", "")
                        if not raw_text:
                            raw_text = revisions[0].get("*", "") or revisions[0].get("content", "")
                        
                        if raw_text:
                            # Basic cleanup of wikitext to make it digestible
                            clean_text = raw_text
                            for _ in range(5):
                                clean_text = re.sub(r'\{\{[^{}]*\}\}', '', clean_text)
                            clean_text = re.sub(r'\[\[(?:File|Category|Image):[^\]]+\]\]', '', clean_text, flags=re.IGNORECASE)
                            clean_text = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', clean_text)
                            clean_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', clean_text)
                            clean_text = re.sub(r'<!--.*?-->', '', clean_text, flags=re.DOTALL)
                            clean_text = clean_text.strip()
                            if len(clean_text) > 1500:
                                clean_text = clean_text[:1500] + "..."
                                
                            log_info(f"Successfully retrieved raw Wikitext for '{char_name}' (Title: {title})")
                            return self._translate_wiki_to_target_lang(title, clean_text)
        except Exception as e:
            log_warning(f"Zelda Wiki lookup failed for '{char_name}': {e}")
        return ""

    def _translate_wiki_to_target_lang(self, title: str, text: str) -> str:
        """Translate Zelda Wiki description to the target language immediately using AI."""
        if not text or not text.strip():
            return ""
        
        # If target language is already English, no translation needed
        if self.target_lang == "English":
            return f"Page: {title}\n{text}"
            
        from utils.logging_utils import log_info, log_error
        
        if self.target_lang == "Ukrainian":
            system_prompt = (
                "Ви — професійний перекладач відеоігор та редактор локалізації. Ваше завдання — зробити точний, "
                "літературний переклад вступного опису персонажа з англійської Вікіпедії на українську мову. "
                "Переклад має бути максимально природним та художнім."
            )
            user_prompt = f"""
Перекладіть наступний опис персонажа '{title}' з гри The Legend of Zelda на українську мову:

{text}

Поверніть ЛИШЕ готовий переклад українською мовою. Не додавайте жодних вступних чи пояснювальних фраз.
"""
        else:
            system_prompt = (
                f"You are an expert game translation editor. Translate the provided Zelda character description "
                f"from English into {self.target_lang}. Keep it highly professional and natural."
            )
            user_prompt = f"""
Translate the following character description for '{title}' into {self.target_lang}:

{text}

Return ONLY the translated text. Do not add any introduction or meta comments.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            response = self.ai_provider.translate(messages, session=None)
            translated = response.text.strip()
            log_info(f"Successfully translated Zelda Wiki context for '{title}' to {self.target_lang}")
            return f"Page: {title}\n{translated}"
        except Exception as e:
            log_error(f"Failed to translate Zelda Wiki description for '{title}': {e}")
            return f"Page: {title} (Original English Context)\n{text}"

    def _load_plugin_prompts(self) -> dict:
        """Load prompts.json for active plugin if available."""
        from pathlib import Path
        prompts_data = {}
        if self.plugin_name:
            prompts_path = Path("plugins") / self.plugin_name / "translation_prompts" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("plugins") / "common" / "defaults" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("translation_prompts") / "prompts.json"
            
            if prompts_path.exists():
                try:
                    prompts_data = json.loads(prompts_path.read_text("utf-8"))
                except Exception as e_load:
                    log_error(f"Failed to load prompts.json for plugin {self.plugin_name}: {e_load}")
        return prompts_data

    def _get_synthesis_prompts(self, term_name: str, existing_notes: str, details: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve Synthesis prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        s_sys = m_section.get("synthesis_system_prompt")
        s_usr = m_section.get("synthesis_user_prompt")

        if s_sys and s_usr:
            return s_sys.format(target_lang=self.target_lang), s_usr.format(
                term_name=term_name,
                existing_notes=existing_notes,
                details=details,
                target_lang=self.target_lang
            )

        if self.target_lang == "Ukrainian":
            synth_system_prompt = (
                "Ви — професійний лексикограф та перекладач відеоігор. Ваше завдання — об'єднати існуючі нотатки/опис "
                "персонажа у глосарії з новим детальним аналізом його стилю мовлення та характеру від ШІ. Ви повинні синтезувати їх "
                "у один зв'язний, високоякісний, структурований та детальний опис (notes), написаний виключно українською мовою."
            )
            synth_user_prompt = f"""
Синтезуйте наступну інформацію для персонажа '{term_name}':

Існуючий опис у глосарії (нотатки):
{existing_notes}

Нові деталі аналізу мовлення та характеру від ШІ:
{details}

Створіть єдиний, красиво структурований та детальний опис, написаний виключно українською мовою. Уникайте повторень.
Збережіть увесь попередній контекст, обов'язково переклавши його українською мовою (якщо він був англійською), та гармонійно інтегруйте нову інформацію про характер, манеру мовлення, форми звертання та особливості перекладу.
Не повертайте нічого, крім фінального синтезованого тексту українською мовою. Не загортайте в блоки markdown або JSON. Поверніть лише чистий текст опису.
"""
        else:
            synth_system_prompt = (
                f"You are an expert game translation lexicographer. Your task is to combine the existing glossary entry notes "
                f"with new speech analysis insights. You must synthesize them into one coherent, premium, well-structured, "
                f"highly detailed description (notes) written strictly in {self.target_lang}."
            )
            synth_user_prompt = f"""
Synthesize the following information for the character '{term_name}':

Existing Glossary Description (Notes):
{existing_notes}

New AI Speech Analysis Insights:
{details}

Produce a unified, beautifully structured, and highly detailed description written strictly in {self.target_lang}. Avoid redundancy. 
Keep any pre-existing context while seamlessly translating it and integrating the new character and speech features.
Do not output anything else but the synthesized {self.target_lang} text. Do not wrap in markdown blocks or JSON. Just print the final synthesized notes.
"""
        return synth_system_prompt, synth_user_prompt

    def run(self):
        try:
            self.log.emit("Starting AI Character Speech Profiler...")
            self.progress.emit(5, 100, "Retrieving dialogue lines from database...")

            # 1. Fetch character dialogue lines from local MemPalace DB
            char_dialogues = self.client.get_all_character_lines(self.wing_name)
            
            # Workspace scan fallback if DB is empty but we have composer
            if not char_dialogues and self.composer:
                self.log.emit("No dialogue drawers found in SQLite. Scanning active project workspace strings via composer...")
                mw = getattr(self.composer, "mw", None)
                store = getattr(mw, "data_store", None) if mw else None
                if store and store.data:
                    char_dialogues = {}
                    total_blocks = len(store.data)
                    tag_pattern = re.compile(r'\{[^}]+\}|\[[^]]+\]')
                    
                    for b_idx in range(total_blocks):
                        if self.is_cancelled:
                            break
                        block_strings = store.data[b_idx]
                        block_label = self.composer._get_block_label(b_idx)
                        
                        self.progress.emit(
                            5 + int((b_idx / total_blocks) * 15),
                            100,
                            f"Workspace scan: Mapping block {block_label} ({b_idx+1}/{total_blocks})..."
                        )
                        self.log.emit(f"Scanning workspace block '{block_label}' for character dialogues...")
                        
                        for s_idx, text in enumerate(block_strings):
                            if not text or not str(text).strip():
                                continue
                                
                            res = self.composer._find_speaker_in_script(b_idx, s_idx, text)
                            if res and isinstance(res, (tuple, list)) and len(res) == 2:
                                speaker, lines_str = res
                                if speaker and speaker != "NONE":
                                    clean_speaker = str(speaker).strip()
                                    if clean_speaker and clean_speaker.lower() not in ("unknown", "none"):
                                        clean_text = tag_pattern.sub('', text).strip()
                                        clean_text = re.sub(r'\s+', ' ', clean_text)
                                        if clean_text:
                                            char_dialogues.setdefault(clean_speaker, []).append(clean_text)
            
            # Filter out minor characters with fewer than 3 lines to speed up profiling and save API costs
            original_char_count = len(char_dialogues)
            char_dialogues = {speaker: d_lines for speaker, d_lines in char_dialogues.items() if len(d_lines) >= 3}
            filtered_count = original_char_count - len(char_dialogues)
            if filtered_count > 0:
                self.log.emit(f"Filtered out {filtered_count} minor characters with fewer than 3 dialogue lines to speed up profiling.")

            if not char_dialogues:
                self.finished.emit(False, "No character dialogues found in database or active project workspace. Please map script chapters first.")
                return

            self.log.emit(f"Found dialogues for {len(char_dialogues)} characters.")
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            # Prepare prompts configuration
            prompts_data = self._load_plugin_prompts()
            
            # System prompt for profiling (optimized for target language)
            if self.target_lang == "Ukrainian":
                system_prompt = (
                    "Ви — видатний директор з локалізації відеоігор, психолог персонажів та професійний лінгвіст. "
                    "Ваше завдання — проаналізувати всі репліки, які вимовляє конкретний персонаж гри, та скласти надзвичайно "
                    "детальний, художній та розлогий мовленнєвий портрет (speech profile) українською мовою для забезпечення абсолютної "
                    "художньої послідовності та автентичності при перекладі."
                )
            else:
                system_prompt = (
                    "You are an expert game localization director, character psychologist, and linguist. "
                    "Your task is to analyze all dialogues spoken by a specific character to compile a comprehensive, "
                    "high-quality, and deeply detailed speech profile to ensure consistency in localized translations."
                )

            total_characters = len(char_dialogues)
            processed_count = 0
            stats_updated = 0
            stats_added = 0
            stats_failed = 0
            stats_empty = 0
            consecutive_failures = 0

            for char_name, lines in char_dialogues.items():
                if self.is_cancelled:
                    break

                # Skip already profiled characters to support incremental resumption
                if self.glossary_manager:
                    existing_entry = self.glossary_manager.get_entry(char_name)
                    if existing_entry:
                        has_marker = bool(existing_entry.profiled)
                        has_profile = False
                        if existing_entry.notes:
                            has_profile = ("📌" in existing_entry.notes and 
                                           "🗣️" in existing_entry.notes and 
                                           "💡" in existing_entry.notes)
                        
                        note_lines = [line.strip() for line in existing_entry.notes.splitlines() if line.strip()] if existing_entry.notes else []
                        line_count = len(note_lines)
                        
                        skip = False
                        
                        # 1. Якщо одночасно є і маркер і профайл
                        if has_marker and has_profile:
                            if line_count < 3:
                                # Опис неповний (<3 рядків) -> знімаємо profiled, запускаємо наново!
                                skip = False
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=False
                                    )
                                    self.glossary_manager.save_to_disk()
                                    self.log.emit(f"Character '{char_name}' is marked as Profiled but has <3 lines. Clearing profiled and re-profiling...")
                                except Exception as e_unmark:
                                    log_error(f"Failed to clear profiled for {char_name}: {e_unmark}")
                            else:
                                # Все гаразд -> скіпаємо
                                skip = True
                            
                        # 2. Якщо є профайл і немає маркера, або якщо є маркер і немає профайла
                        elif (has_profile and not has_marker) or (has_marker and not has_profile):
                            if line_count < 3:
                                # Знімаємо profiled, якщо раптом стояла (у випадку has_marker and not has_profile)
                                if has_marker:
                                    try:
                                        self.glossary_manager.update_entry(
                                            original=existing_entry.original,
                                            translation=existing_entry.translation,
                                            notes=existing_entry.notes,
                                            profiled=False
                                        )
                                        self.glossary_manager.save_to_disk()
                                    except Exception:
                                        pass
                                skip = False  # запускаємо
                            else:
                                # якщо більше або дорівнює трьох строк, помічаємо як Profiled і скіпаємо
                                skip = True
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=True
                                    )
                                    self.glossary_manager.save_to_disk()
                                except Exception as e_mark:
                                    log_error(f"Failed to auto-mark profiled for {char_name}: {e_mark}")
                                    
                        # 3. Якщо є профайл і >= 3 строк
                        elif has_profile and line_count >= 3:
                            skip = True
                            if not has_marker:
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=True
                                    )
                                    self.glossary_manager.save_to_disk()
                                except Exception:
                                    pass
                                    
                        if skip:
                            self.log.emit(f"Character '{char_name}' already has a completed speech profile. Skipping (incremental resume).")
                            stats_updated += 1
                            processed_count += 1
                            continue

                self.progress.emit(
                    20 + int((processed_count / total_characters) * 75),
                    100,
                    f"Profiling character speech {processed_count + 1}/{total_characters}: {char_name}..."
                )

                self.log.emit(f"Processing character '{char_name}' with {len(lines)} total lines...")

                # 1. Fetch Wiki context from Zelda Wiki to secure factual grounding
                self.log.emit(f"AI Speech Profiler: Searching Zelda Wiki context for '{char_name}'...")
                wiki_context = self._fetch_zelda_wiki_description(char_name)
                if wiki_context:
                    self.log.emit(f"AI Speech Profiler: Found Zelda Wiki description for '{char_name}'.")
                else:
                    self.log.emit(f"AI Speech Profiler: No Zelda Wiki description found for '{char_name}' (using script dialogue only).")

                # 2. Filter out non-informative short dialogue lines (< 3 words) and enrich with timeline chapter context
                clean_lines = []
                tag_pattern = re.compile(r'\{[^}]+\}|\[[^]]+\]')
                for line in lines:
                    # Clean tags before counting words
                    text_no_tags = tag_pattern.sub('', line).strip()
                    words = [w for w in text_no_tags.split() if w.strip()]
                    if len(words) < 3: # Skip short/non-informative lines like "No", "Huh", "Yes"
                        continue
                    
                    # Try to fetch timeline room context (chapter name)
                    ctx = None
                    if self.client:
                        try:
                            ctx = self.client.get_cached_context("", line)
                        except Exception:
                            ctx = None
                            
                    if ctx:
                        room = ctx.get("room", "Unknown Chapter")
                        if self.target_lang == "Ukrainian":
                            clean_lines.append(f'[У главі "{room}"]: "{line}"')
                        else:
                            clean_lines.append(f'[In Chapter "{room}"]: "{line}"')
                    else:
                        clean_lines.append(f'"{line}"')

                # 3. Sample up to 80 representative lines to fit context window and prevent token bloat
                sampled_lines = clean_lines
                if len(clean_lines) > 80:
                    self.log.emit(f"Character '{char_name}' has many informative lines ({len(clean_lines)}). Sampling 80 representative dialogues...")
                    step = len(clean_lines) / 80
                    sampled_lines = [clean_lines[int(i * step)] for i in range(80)]

                # Format dialogues block
                dialogue_text_block = "\n".join(f'- {line}' for line in sampled_lines)

                # Formulate user prompt
                if self.target_lang == "Ukrainian":
                    wiki_section = ""
                    if wiki_context:
                        wiki_section = f"\n--- Wiki Context (Джерело істини з Zelda Wiki) ---\n{wiki_context}\n"
                        
                    user_prompt = f"""
Проаналізуйте наступну інформацію для персонажа '{char_name}':
{wiki_section}
--- Характерні діалоги персонажа у грі ---
{dialogue_text_block}
---

Створіть високоякісний, структурований та НАДЗВИЧАЙНО КОНЦЕНТРОВАНИЙ мовленнєвий портрет українською мовою.
УНИКАЙТЕ БУДЬ-ЯКОЇ ВОДИ та очевидних банальностей! Кожен розділ має бути ультра-коротким (максимум 2-3 інформативні речення, до 40-50 слів), але містити саму суть і конкретні поради.

ВАЖЛИВО: Якщо цей "персонаж" насправді є службовим тегом розповіді/системи (наприклад, "NARRATIVE", "SYSTEM") або якщо про нього немає реального лору та індивідуального стилю мовлення для аналізу, обов'язково поверніть "speech_profile": "" (порожній рядок) в JSON, щоб ми могли пропустити його профілювання. Не генеруйте порожній шаблон із самих лише заголовків без реального змісту! Кожен заповнений розділ обов'язково повинен містити реальний детальний художній опис з інформативними реченнями.

Обов'язково структуруйте опис (поле "speech_profile" у JSON) на такі чіткі розділи з відповідними емодзі-заголовками:

📌 **Хто цей персонаж (Загальний опис та роль)**:
[Коротко (до 2 речень): хто він згідно з лором Вікіпедії, його роль у сюжеті. Базуйтеся САМЕ на наданому Wiki Context (якщо є) і не галюцинуйте!]

🎭 **Характер та психологічний портрет**:
[Коротко (до 2 речень): ключові риси характеру, емоційний стан, манера поведінки]

🗣️ **Особливості мовлення та лексика**:
[Коротко (до 2 речень): стиль спілкування, характерні вигуки, слова-паразити чи унікальні слова. Тон і темп.]

👥 **Відносини з іншими персонажами та соціальний статус**:
[Коротко (до 2 речень): ставлення до Лінка та інших героїв, соціальне становище]

📝 **Форми звертання та граматичні рекомендації**:
[Коротко (до 2 речень): як він звертається до інших (неформально на 'ти' чи формально на 'ви'), граматичні особливості при перекладі]

💡 **Рекомендації для перекладача (Як його перекладати)**:
[Коротко (до 2 речень): конкретні практичні поради перекладачу: які емоційні відтінки чи унікальні українські вирази підібрати]

Поверніть відповідь ВИКЛЮЧНО у форматі JSON. Не обгортайте JSON у блоки markdown (не пишіть ```json) і не додавайте жодного іншого супровідного тексту.
Структура JSON має бути такою:
{{
  "name_translation": "Природний переклад або транслітерація імені персонажа українською мовою (наприклад, 'Тріл')",
  "speech_profile": "[Сюди запишіть весь згенерований стислий структурований портрет українською мовою з усіма вищенаведеними розділами та заголовками]"
}}
"""
                else:
                    wiki_section = ""
                    if wiki_context:
                        wiki_section = f"\n--- Wiki Context (Source of Truth) ---\n{wiki_context}\n"
                        
                    user_prompt = f"""
Analyze the following information for the character '{char_name}':
{wiki_section}
--- Representative Dialogues ---
{dialogue_text_block}
---

Create a premium, structured, and EXTREMELY CONCISE speech profile written strictly in {self.target_lang}.
AVOID ANY WATER or redundancy! Each section must be ultra-short (maximum 2-3 sentences, up to 40-50 words), focusing only on crucial facts and translation advice.

IMPORTANT: If this "character" is actually a narrative/system tag (like "NARRATIVE", "SYSTEM") or has no real lore and distinct speech pattern to analyze, you MUST return "speech_profile": "" (empty string) in JSON so we can skip profiling them. Do not generate an empty template of headings without real content! Each filled section must contain a substantial description with informative sentences.

Structure the description (the "speech_profile" field in JSON) into these exact sections with emoji headings:

📌 **Who is this character (General description & role)**:
[Briefly (up to 2 sentences): who they are based on the Wiki Context, their role in the game.]

🎭 **Personality and psychological portrait**:
[Briefly (up to 2 sentences): core traits, emotional state, temperament.]

🗣️ **Speech features and vocabulary**:
[Briefly (up to 2 sentences): speech style, register, tone, and tempo.]

👥 **Relationships with other characters and social status**:
[Briefly (up to 2 sentences): how they relate to Link and others, social standing.]

📝 **Forms of address and grammatical recommendations**:
[Briefly (up to 2 sentences): formal vs informal address, specific grammar tips for {self.target_lang} translation.]

💡 **Recommendations for the translator (How to translate)**:
[Briefly (up to 2 sentences): practical tips, specific vocabulary choices or emotional nuances to capture.]

Respond ONLY with a valid JSON object. Do not wrap in markdown json blocks or add any conversational text.
JSON Structure:
{{
  "name_translation": "Natural translation or transliteration of the character's name to {self.target_lang} (e.g. 'Trill')",
  "speech_profile": "[Put the entire synthesized concise structured profile here with all headings listed above]"
}}
"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

                try:
                    # Query AI
                    log_ai_traffic(self.mw, "mempalace_speech_profiling", messages)
                    response = self.ai_provider.translate(messages, session=None)
                    log_ai_traffic(self.mw, "mempalace_speech_profiling", messages, response_text=response.text)
                    consecutive_failures = 0
                    
                    if self.is_cancelled:
                        break

                    # Parse JSON
                    data = robust_json_loads(response.text)
                    name_translation = data.get("name_translation", char_name).strip()
                    speech_profile = data.get("speech_profile", "").strip()

                    if not speech_profile:
                        self.log.emit(f"WARNING: AI returned empty speech profile for '{char_name}'. Skipping.")
                        stats_empty += 1
                        processed_count += 1
                        continue

                    self.log.emit(f"AI Speech Profiler: Successfully generated profile for '{char_name}' (Translated as '{name_translation}').")

                    # 2. Update Glossary Entry
                    if self.glossary_manager:
                        # Look up existing entry by original or translated name
                        existing_entry = self.glossary_manager.get_entry(char_name) or self.glossary_manager.get_entry(name_translation)
                        
                        if existing_entry:
                            # Synthesize existing notes with new speech profile
                            self.log.emit(f"Entry '{existing_entry.original}' exists. Synthesizing notes with AI Speech Profile...")
                            existing_notes = existing_entry.notes or ""
                            
                            synth_sys, synth_usr = self._get_synthesis_prompts(
                                existing_entry.original, existing_notes, speech_profile, prompts_data
                            )
                            synth_messages = [
                                {"role": "system", "content": synth_sys},
                                {"role": "user", "content": synth_usr}
                            ]
                            
                            try:
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages)
                                synth_response = self.ai_provider.translate(synth_messages, session=None)
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages, response_text=synth_response.text)
                                final_notes = synth_response.text.strip()
                                
                                self.glossary_manager.update_entry(
                                    original=existing_entry.original,
                                    translation=existing_entry.translation,
                                    notes=final_notes,
                                    profiled=True
                                )
                                stats_updated += 1
                                self.log.emit(f"SUCCESS: Synthesized speech profile for existing character '{existing_entry.original}'.")
                            except Exception as e_synth:
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages, error=str(e_synth))
                                log_error(f"Failed to synthesize speech notes for {char_name}: {e_synth}")
                                # Fallback: append profile to notes directly
                                fallback_notes = f"{existing_notes}\n\nСтиль мовлення: {speech_profile}"
                                self.glossary_manager.update_entry(
                                    original=existing_entry.original,
                                    translation=existing_entry.translation,
                                    notes=fallback_notes,
                                    profiled=True
                                )
                                stats_updated += 1
                                self.log.emit(f"FALLBACK: Appended speech profile directly for existing character '{existing_entry.original}'.")
                        else:
                            # Add new glossary entry in Characters section
                            self.glossary_manager.add_entry(
                                original=char_name,
                                translation=name_translation,
                                notes=speech_profile,
                                section="Characters",
                                profiled=True
                            )
                            stats_added += 1
                            self.log.emit(f"SUCCESS: Created new Characters entry '{char_name}' -> '{name_translation}' with AI speech profile.")
                        
                        try:
                            self.glossary_manager.save_to_disk()
                        except Exception as e_save:
                            log_error(f"Failed to auto-save glossary for {char_name}: {e_save}")

                except Exception as e_proc:
                    log_error(f"Failed to process speech profile for {char_name}: {e_proc}")
                    self.log.emit(f"WARNING: Speech profiling failed for '{char_name}': {str(e_proc)}")
                    stats_failed += 1
                    
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        self.log.emit("Too many consecutive AI errors. Stopping character speech profiling to prevent flooding.")
                        self.finished.emit(False, f"Profiling stopped due to multiple consecutive AI errors (last error: {e_proc}).")
                        return

                processed_count += 1

            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            # Save all glossary updates to disk
            if self.glossary_manager:
                try:
                    self.progress.emit(95, 100, "Saving glossary database to disk...")
                    self.glossary_manager.save_to_disk()
                    self.log.emit("Successfully saved updated glossary (.md table) to disk.")
                except Exception as disk_err:
                    log_error(f"Failed to save glossary to disk: {disk_err}")
                    self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

            self.progress.emit(100, 100, "Speech profiling and glossary updates completed!")
            
            # Format high-quality descriptive success message with statistics
            stat_msg = (
                f"Successfully completed character speech profiling!\n\n"
                f"📊 Execution Statistics:\n"
                f"• Total characters processed: {processed_count}\n"
                f"• Successfully updated in Glossary: {stats_updated}\n"
                f"• Newly added to Glossary: {stats_added}\n"
                f"• Failed/skipped due to API errors: {stats_failed}\n"
                f"• Empty AI profiles received: {stats_empty}\n\n"
                f"You can find the generated profiles directly in the Picoripi Glossary editor (Characters tab) "
                f"or as tooltip previews when hovering over these character names in the main translation window."
            )
            self.finished.emit(True, stat_msg)

        except Exception as e:
            log_error(f"Error in MemePalaceCharacterProfilerWorker: {e}", exc_info=True)
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")


