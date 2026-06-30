from __future__ import annotations
import os
import re
from typing import Dict, List, Optional, Tuple
from utils.logging_utils import log_debug

class StoryContextManager:
    """Manages SQLite MemePalace database context, room visual context and active wings."""

    def __init__(self, mw: object):
        self.mw = mw
        self._mempalace_client = None
        self._mempalace_project_dir = None

    def get_mempalace_client(self) -> Optional[object]:
        """Dynamically get or initialize MemePalaceClient for current project directory."""
        project_dir = None
        if hasattr(self.mw, "project_manager") and self.mw.project_manager:
            proj_dir = getattr(self.mw.project_manager, "project_dir", None)
            if proj_dir and isinstance(proj_dir, (str, bytes)):
                project_dir = proj_dir

        if not project_dir:
            if hasattr(self.mw, "data_store") and self.mw.data_store:
                project_file = getattr(self.mw.data_store, "project_file", None)
                json_path = getattr(self.mw.data_store, "json_path", None)
                if project_file and isinstance(project_file, (str, bytes)):
                    project_dir = os.path.dirname(project_file)
                elif json_path and isinstance(json_path, (str, bytes)):
                    project_dir = os.path.dirname(json_path)
            if not project_dir or not isinstance(project_dir, (str, bytes)):
                project_dir = os.getcwd()

        # Verify if the db exists or search in parent/adjacent directories up to 4 levels
        db_file = "mempalace_local.db"
        resolved_db = os.path.join(project_dir, db_file) if project_dir else ""

        if not project_dir or not os.path.exists(resolved_db):
            candidates = [os.getcwd()]
            if hasattr(self.mw, "data_store") and self.mw.data_store:
                json_path = getattr(self.mw.data_store, "json_path", None)
                if json_path and isinstance(json_path, (str, bytes)):
                    candidates.append(os.path.dirname(json_path))

            found_dir = None
            for cand in candidates:
                if not cand: continue
                curr = os.path.abspath(cand)
                # Check up to 4 levels of parent directories
                for _ in range(5):
                    # Check current directory
                    test_path = os.path.join(curr, db_file)
                    if os.path.exists(test_path):
                        found_dir = curr
                        break
                    # Also check immediately adjacent sibling folders
                    parent_dir = os.path.dirname(curr)
                    if parent_dir and parent_dir != curr and os.path.isdir(parent_dir):
                        try:
                            siblings = os.listdir(parent_dir)
                        except OSError:
                            siblings = []
                        for sibling in siblings:
                            sibling_path = os.path.join(parent_dir, sibling)
                            if os.path.isdir(sibling_path):
                                test_path_sib = os.path.join(sibling_path, db_file)
                                if os.path.exists(test_path_sib):
                                    found_dir = sibling_path
                                    break
                    if found_dir:
                        break

                    # Move one level up
                    next_parent = os.path.dirname(curr)
                    if next_parent == curr:
                        break
                    curr = next_parent
                if found_dir:
                    project_dir = found_dir
                    break

        if not project_dir or not isinstance(project_dir, (str, bytes)):
            return None

        if self._mempalace_client is None or self._mempalace_project_dir != project_dir:
            from core.mempalace_client import MemePalaceClient
            self._mempalace_client = MemePalaceClient(project_dir=project_dir)
            self._mempalace_project_dir = project_dir

        return self._mempalace_client

    def get_wing_name(self) -> str:
        """Deduce clean active wing/game identifier."""
        game_name = "Zelda_TP"
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
        elif hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            game_name = self.mw.current_game_rules.get_display_name()

        clean_name = "".join([c if c.isalnum() else "_" for c in game_name]).strip("_")

        try:
            client = self.get_mempalace_client()
            if client and hasattr(client, "get_wings"):
                wings = client.get_wings()
                wing_names = [w["name"] for w in wings]
                if wing_names and clean_name not in wing_names:
                    # Look for fuzzy match or prefix match
                    for w_name in wing_names:
                        if clean_name.lower().startswith(w_name.lower()) or w_name.lower().startswith(clean_name.lower()):
                            return w_name
                    # If only one wing exists in DB, use it
                    if len(wing_names) == 1:
                        return wing_names[0]
        except Exception as e:
            import utils.logging_utils
            utils.logging_utils.log_error(f"Error resolving wing name fallback: {e}")

        return clean_name or "Zelda_TP"

    def get_block_label(self, block_idx: int) -> str:
        """Get friendly display label for a project file block index."""
        if block_idx is None or block_idx == -1:
            return "Block"

        store = self.mw.data_store
        name_key = str(block_idx)

        # 1. Try project block name or source file stem
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
           self.mw.project_manager.project and block_idx < len(self.mw.project_manager.project.blocks):
            block = self.mw.project_manager.project.blocks[block_idx]
            if block.name and not block.name.startswith("Block_"):
                return block.name
            if block.source_file:
                return os.path.splitext(os.path.basename(block.source_file))[0]

        # 2. Try list widget item name or block_names description
        if store.block_names and name_key in store.block_names:
            b_desc = store.block_names[name_key]
            base = os.path.splitext(os.path.basename(b_desc))[0]
            if "(" in base:
                base = base.partition("(")[0].strip()
            return base

        # 3. Fallback: if json_path is loaded in datastore, use its stem
        if getattr(store, "json_path", None):
            return os.path.splitext(os.path.basename(store.json_path))[0]

        return f"Block_{block_idx}"

    def fetch_story_context(
        self,
        block_idx: int,
        s_idx: int,
        text: str,
        script_speaker_finder: object,
        data_processor: object,
    ) -> Optional[str]:
        """Query the local SQLite database for visual scene description, character status and timeline info."""
        client = self.get_mempalace_client()

        from utils.utils import remove_all_tags
        clean_t = remove_all_tags(text).strip()
        is_single_word = len(clean_t.split()) <= 1

        script_res = None
        if not is_single_word and script_speaker_finder:
            block_label = self.get_block_label(block_idx)
            script_res = script_speaker_finder.find_speaker_in_script(
                block_idx, s_idx, text, self.get_wing_name(), block_label
            )
            if not isinstance(script_res, (tuple, list)) or len(script_res) != 2:
                script_res = None

        script_lines_str = script_res[1] if script_res else None

        # Helper to try and resolve speaker via script fallback if missing
        def get_script_speaker_fallback() -> Optional[Tuple[str, str, str]]:
            if script_res:
                raw_spk, lines_str = script_res
                return raw_spk, script_speaker_finder.translate_speaker(raw_spk, None), lines_str
            return None

        # 1. Try local in-memory cache first for instant response
        if client:
            wing_name = self.get_wing_name()
            block_label = self.get_block_label(block_idx)
            bmg_id = f"{block_label}_Str_{s_idx}"

            cached_ctx = client.get_cached_context(bmg_id, text)
            if cached_ctx:
                room_name = cached_ctx.get("room")
                speaker = "NONE" if is_single_word else cached_ctx.get("speaker")
                timestamp = cached_ctx.get("timestamp") or "Unknown time"
                visual_ctx = client.get_room_visual_context(wing_name, room_name)

                context_parts = []
                clean_room = room_name.replace("_", " ")
                context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")

                # If speaker missing in cache, try script fallback
                if not speaker and not is_single_word:
                    fallback = get_script_speaker_fallback()
                    if fallback:
                        raw_spk, trans_spk, _ = fallback
                        if re.match(r'^[\d,\s]+$', raw_spk):
                            speaker = f"{raw_spk} [Disk Script]"
                        else:
                            speaker = f"{trans_spk} ({raw_spk}) [Disk Script]"

                if speaker:
                    context_parts.append(f"Speaker in this line: {speaker}")
                if script_lines_str:
                    context_parts.append(f"Script Line: {script_lines_str}")

                if visual_ctx:
                    context_parts.append(f"Visual Action Context:\n{visual_ctx}")
                else:
                    context_parts.append("Timeline context mapped successfully (No detailed visual context generated).")

                # Retrieve relations
                try:
                    relations = client.get_relations(wing_name)
                    relevant_relations = []
                    if speaker:
                        speaker_low = speaker.lower()
                        for r in relations:
                            if r.get("source", "").lower() in speaker_low or r.get("target", "").lower() in speaker_low:
                                relevant_relations.append(r)

                    if not relevant_relations and relations:
                        room_low = room_name.lower()
                        for r in relations:
                            valid_from = r.get("valid_from", "")
                            if valid_from and valid_from.lower() in room_low:
                                relevant_relations.append(r)

                    if relevant_relations:
                        context_parts.append("\nCharacter Status & Story Relations:")
                        for r in relevant_relations[:5]:
                            context_parts.append(f"• {r.get('source')} -[{r.get('relation')}]-> {r.get('target')}")
                except Exception as rel_err:
                    log_debug(f"Could not load relations for visual context: {rel_err}")

                return "\n".join(context_parts)

            # 2. Search database fallback
            results = client.search_context(wing_name, bmg_id, limit=1)

            if not results:
                query_text = text.strip()[:40]
                if len(query_text) > 8:
                    results = client.search_context(wing_name, query_text, limit=1)

            if results:
                best_match = results[0]
                room_name = best_match.get("room")
                if room_name:
                    visual_ctx = client.get_room_visual_context(wing_name, room_name)

                    meta = best_match.get("metadata") or {}
                    timestamp = meta.get("timestamp") or "Unknown time"
                    speaker_map = meta.get("speaker_map") or {}

                    speaker = None
                    content = best_match.get("content") or ""
                    matched_id_in_content = None

                    if content:
                        def clean_for_compare(t: str) -> str:
                            if not t:
                                return ""
                            t = re.sub(r'\{[^}]+\}', '', t)
                            t = re.sub(r'\[[^]]+\]', '', t)
                            return re.sub(r'[^a-zA-Z0-9]', '', t).lower().strip()

                        clean_query = clean_for_compare(text)
                        for line in content.splitlines():
                            line_id = None
                            line_text = None
                            if "ID:" in line and "| Text:" in line:
                                parts = line.split("| Text:", 1)
                                line_id = parts[0].replace("ID:", "").strip()
                                line_text = parts[1].strip()
                            elif ":" in line:
                                parts = line.split(":", 1)
                                line_id = parts[0].strip()
                                if line_id.startswith("[") and line_id.endswith("]"):
                                    line_id = line_id[1:-1].strip()
                                line_text = parts[1].strip()

                            if line_id and line_text:
                                if clean_for_compare(line_text) == clean_query:
                                    matched_id_in_content = line_id
                                    break

                    target_bmg_id = matched_id_in_content or bmg_id
                    speaker = "NONE" if is_single_word else (speaker_map.get(target_bmg_id) or speaker_map.get(f"[{target_bmg_id}]"))

                    if not speaker and not is_single_word:
                        fallback = get_script_speaker_fallback()
                        if fallback:
                            raw_spk, trans_spk, _ = fallback
                            if re.match(r'^[\d,\s]+$', raw_spk):
                                speaker = f"{raw_spk} [Disk Script]"
                            else:
                                speaker = f"{trans_spk} ({raw_spk}) [Disk Script]"

                    context_parts = []
                    clean_room = room_name.replace("_", " ")
                    context_parts.append(f"Story Location/Scene: {clean_room} (Timeline: {timestamp})")

                    if speaker:
                        context_parts.append(f"Speaker in this line: {speaker}")
                    if script_lines_str:
                        context_parts.append(f"Script Line: {script_lines_str}")

                    if visual_ctx:
                        context_parts.append(f"Visual Action Context:\n{visual_ctx}")
                    else:
                        context_parts.append("Timeline context mapped successfully (No detailed visual context generated).")

                    try:
                        relations = client.get_relations(wing_name)
                        relevant_relations = []
                        if speaker:
                            speaker_low = speaker.lower()
                            for r in relations:
                                if r.get("source", "").lower() in speaker_low or r.get("target", "").lower() in speaker_low:
                                    relevant_relations.append(r)

                        if not relevant_relations and relations:
                            room_low = room_name.lower()
                            for r in relations:
                                valid_from = r.get("valid_from", "")
                                if valid_from and valid_from.lower() in room_low:
                                    relevant_relations.append(r)

                        if relevant_relations:
                            rel_lines = ["\nCHARACTER & STORY RELATIONS (Ukrainian Grammar Priority):"]
                            rel_lines.append("Use these social relations to determine the correct informal ('ти') or formal/respectful ('ви') pronoun and verb endings in Ukrainian:")
                            for r in relevant_relations:
                                rel_lines.append(f"• {r['source']} -[{r['relation']}]-> {r['target']}")
                            context_parts.append("\n".join(rel_lines))
                    except Exception as rel_err:
                        import utils.logging_utils
                        utils.logging_utils.log_error(f"Error gathering relations for prompt: {rel_err}")

                    return "\n".join(context_parts)

        # 3. Absolute Fallback: SQLite completely failed, try Script Fallback to at least extract Speaker
        fallback = get_script_speaker_fallback() if not is_single_word else None
        if fallback:
            raw_spk, trans_spk, lines_str = fallback
            context_parts = [
                "Story Location/Scene: Mapped from Disk Script",
                f"Speaker in this line: {trans_spk} ({raw_spk}) [Disk Script]",
                f"Script Line: {lines_str}",
                "Timeline: Mapped from script sequence"
            ]
            return "\n".join(context_parts)

        return None
