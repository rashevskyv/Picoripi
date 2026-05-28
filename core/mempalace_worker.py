import json
import re
import difflib
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional, Tuple
from core.mempalace_client import MemePalaceClient
from core.translation.providers import BaseTranslationProvider, ProviderResponse
from utils.logging_utils import log_info, log_error, log_debug


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
        
        def clean_for_match(text: str) -> str:
            if not text:
                return ""
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
        self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}")
        
        total = len(mapped_scenes)
        for idx, scene in enumerate(mapped_scenes):
            if self.is_cancelled:
                break
            if idx % 10 == 0 or idx == total - 1:
                pct = int((idx / total) * 100)
                self.progress.emit(pct, 100, f"Saving mapped scenes to database: {idx + 1}/{total}...")
                
            room_name = scene["room_name"]
            self.client.add_room(self.wing_name, room_name, f"Chronological Scene at timeline: {scene['timestamp']}")
            
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
                }
            )

    def _save_single_scene_locally(self, scene: Dict[str, Any]):
        """Helper to save a single scene directly without AI queries."""
        room_name = scene["room_name"]
        self.client.add_room(self.wing_name, room_name, f"Timeline context: {scene['timestamp']}")
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
            }
        )

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

            try:
                response: ProviderResponse = self.ai_provider.translate(messages, session=None)
                
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
                
                # Write to MemPalace Wing/Room/Drawers
                # Write verbatim dialogues
                self.client.add_drawer(
                    self.wing_name, 
                    room_name, 
                    "dialogues", 
                    dialogue_block, 
                    {"bmg_start_idx": scene["bmg_start_idx"], "timestamp": scene["timestamp"], "speaker_map": speaker_map}
                )
                
                # Write visual scene context drawer
                self.client.add_drawer(
                    self.wing_name, 
                    room_name, 
                    "visual_scene_context", 
                    visual_context, 
                    {"timestamp": scene["timestamp"]}
                )
                
                # Write relations to temporal knowledge graph
                for rel in relations:
                    self.client.add_relation(
                        self.wing_name, 
                        rel.get("source", "Unknown"), 
                        rel.get("relation", "relates"), 
                        rel.get("target", "Unknown"), 
                        valid_from=scene["timestamp"]
                    )
                    
            except Exception as e:
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
                 plugin_name: Optional[str] = None):
        super().__init__()
        self.client = client
        self.file_path = file_path
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.glossary_manager = glossary_manager
        self.target_lang = target_lang
        self.plugin_name = plugin_name
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

            response = self.ai_provider.translate(messages, session=None)
            
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
                            synth_response = self.ai_provider.translate(synth_messages, session=None)
                            synthesized_notes = synth_response.text.strip()
                            
                            # Safely update the entry in the glossary
                            self.glossary_manager.update_entry(
                                original=existing_entry.original,
                                translation=existing_entry.translation,
                                notes=synthesized_notes
                            )
                            self.log.emit(f"SUCCESS: Synthesized entry for '{term_name}' (notes updated in {self.target_lang}, translation '{existing_entry.translation}' kept).")
                        except Exception as e_synth:
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
                            new_term_response = self.ai_provider.translate(new_term_messages, session=None)
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
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")
