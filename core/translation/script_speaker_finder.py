from __future__ import annotations
import os
import re
from typing import Optional, Tuple
from utils.logging_utils import log_debug

class ScriptSpeakerFinder:
    """Finds characters and speakers in game scripts on disk using line caching and distilled text matches."""

    def __init__(self, mw: object, story_context_manager: object):
        self.mw = mw
        self.story_context_manager = story_context_manager

        # Invalidation cache variables
        self._script_lines_cache = None
        self._global_distilled_text_cache = None
        self._char_to_line_map_cache = None
        self._cached_script_path = None
        self._cached_mtime = None
        self._cached_size = None
        self._cached_plugin_name = None
        self._distill_cache_version = None

    def find_script_path(self) -> Optional[str]:
        """Find the absolute path to the game script file on disk."""
        plugin_script_name = None
        if hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            try:
                plugin_script_name = self.mw.current_game_rules.get_default_script_name()
            except Exception:
                pass

        search_dirs = []

        # Candidate near DB path
        client = self.story_context_manager.get_mempalace_client()
        db_path = client.db_path if client else None
        if db_path:
            db_dir = os.path.dirname(db_path)
            search_dirs.append(db_dir)
            search_dirs.append(os.path.dirname(db_dir))

        # Candidate near project directory
        project_dir = getattr(self.story_context_manager, "_mempalace_project_dir", None)
        if not project_dir and hasattr(self.mw, "project_manager") and self.mw.project_manager and self.mw.project_manager.project:
            project_dir = self.mw.project_manager.project.project_dir

        if project_dir:
            search_dirs.append(project_dir)
            search_dirs.append(os.path.dirname(project_dir))

        # Check in current working directory
        search_dirs.append(os.getcwd())

        # Clean search directories (remove duplicates and verify existence)
        unique_dirs = []
        for d in search_dirs:
            if d and os.path.exists(d):
                abs_d = os.path.abspath(d)
                if abs_d not in unique_dirs:
                    unique_dirs.append(abs_d)

        # 3. Check for specific plugin script name
        if plugin_script_name:
            for d in unique_dirs:
                p = os.path.join(d, plugin_script_name)
                if os.path.exists(p):
                    return p

        # 4. Fallback search: look for hardcoded TP script
        candidates = [
            r"e:\Emulators\RomHacking\ZELDA\TP_UA\zelda_tp_script.txt",
        ]
        for d in unique_dirs:
            candidates.append(os.path.join(d, "zelda_tp_script.txt"))

        for path in candidates:
            if path and os.path.exists(path):
                return path

        # 5. Generic search for any *script*.md or *script*.txt in the search directories
        for d in unique_dirs:
            try:
                for f in os.listdir(d):
                    if "script" in f.lower() and f.lower().endswith(".md"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            return p
                for f in os.listdir(d):
                    if "script" in f.lower() and f.lower().endswith(".txt"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            return p
            except Exception:
                pass

        return None

    def translate_speaker(self, speaker: str, glossary_manager: Optional[object]) -> str:
        """Translate the character name using glossary if possible."""
        if not speaker:
            return ""
        if not glossary_manager:
            return speaker

        for entry in glossary_manager.get_entries():
            if entry.original.strip().lower() == speaker.strip().lower():
                trans = entry.translation.split(";")[0].strip()
                if trans:
                    return trans
        return speaker

    def find_speaker_in_script(
        self,
        block_idx: int,
        s_idx: int,
        text: str,
        default_wing_name: str,
        block_label: str,
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Find speaker in the script file using direct DB mapping or middle third distilled matching."""
        script_path = self.find_script_path()
        if not script_path or not os.path.exists(script_path):
            log_debug("Script Fallback: script file not found.")
            return None

        # Calculate file status and plugin configuration
        try:
            stat = os.stat(script_path)
            mtime = stat.st_mtime
            size = stat.st_size
        except Exception as e:
            log_debug(f"Failed to stat script file {script_path}: {e}")
            mtime = 0.0
            size = 0

        plugin_name = "Unknown"
        if self.mw and getattr(self.mw, 'current_game_rules', None):
            try:
                plugin_name = self.mw.current_game_rules.get_display_name()
            except Exception:
                pass

        # Invalidate cache if file properties or active plugin changed
        if (self._cached_script_path != script_path or
            self._cached_mtime != mtime or
            self._cached_size != size or
            self._cached_plugin_name != plugin_name):
            self._script_lines_cache = None
            self._global_distilled_text_cache = None
            self._char_to_line_map_cache = None
            self._cached_script_path = None
            self._cached_mtime = None
            self._cached_size = None
            self._cached_plugin_name = None

        # 1. High-priority Direct DB Script Mapping Check
        client = self.story_context_manager.get_mempalace_client()
        db_mapping = None
        if client:
            bmg_id = f"{block_label}_Str_{s_idx}"
            db_mapping = client.get_script_mapping(default_wing_name, bmg_id)

        # Retrieve dynamic name tag substitutions from the active plugin
        _dynamic_name_tags: dict = {}
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            try:
                _dynamic_name_tags = self.mw.current_game_rules.get_dynamic_name_tags()
            except Exception:
                pass

        def line_strip_is_speaker(s: str) -> bool:
            s_clean = re.sub(r'\(.*?\)', '', s).strip()
            return s_clean.isupper() and len(s_clean) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s_clean) is not None

        # If direct mapping found, we can load the script and find the speaker directly from that line index
        if db_mapping and db_mapping.get("script_line"):
            line_num = db_mapping["script_line"]
            try:
                if self._script_lines_cache is not None:
                    lines = self._script_lines_cache
                else:
                    try:
                        with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                            lines = f.readlines()
                    except Exception:
                        with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()
                    self._script_lines_cache = lines
                    self._cached_script_path = script_path
                    self._cached_mtime = mtime
                    self._cached_size = size
                    self._cached_plugin_name = plugin_name

                # Scan backwards from line_num - 2 (0-indexed offset of line_num - 1)
                speaker = None
                in_brackets_back = False
                for idx in range(line_num - 2, -1, -1):
                    s = lines[idx].strip()
                    if not s:
                        continue
                    if s.endswith("]") and not s.startswith("["):
                        in_brackets_back = True
                        continue
                    if in_brackets_back:
                        if s.startswith("["):
                            in_brackets_back = False
                        continue
                    if s.startswith("[") and s.endswith("]"):
                        continue
                    if line_strip_is_speaker(s):
                        speaker = re.sub(r'\(.*?\)', '', s).strip()
                        break
                speaker_str = speaker if speaker else "NONE"
                return speaker_str, str(line_num)
            except Exception as e:
                log_debug(f"Direct mapping speaker extraction failed: {e}")

        def distill(t: str) -> str:
            if not t:
                return ""
            for tag, name in _dynamic_name_tags.items():
                t = t.replace(tag, name)
            from core.tag_utils import strip_tags
            t = strip_tags(t)
            t = re.sub(r'\([^)]+\)', '', t)
            return "".join(c for c in t if c.isalnum()).lower()

        _DISTILL_CACHE_VERSION = 2

        # Try to retrieve from cache
        if (self._script_lines_cache is not None and
            self._global_distilled_text_cache is not None and
            self._char_to_line_map_cache is not None and
            self._cached_script_path == script_path and
            self._cached_mtime == mtime and
            self._cached_size == size and
            self._cached_plugin_name == plugin_name and
            self._distill_cache_version == _DISTILL_CACHE_VERSION):
            lines = self._script_lines_cache
            global_distilled_text = self._global_distilled_text_cache
            char_to_line_map = self._char_to_line_map_cache
        else:
            if self._script_lines_cache is not None:
                lines = self._script_lines_cache
            else:
                try:
                    with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                        lines = f.readlines()
                except Exception as e:
                    log_debug(f"Script Fallback: failed to load with cp1252, trying utf-8: {e}")
                    try:
                        with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()
                    except Exception as e2:
                        log_debug(f"Script Fallback: failed to load script file: {e2}")
                        return None
                self._script_lines_cache = lines

            global_distilled = []
            char_to_line_map = []
            in_brackets = False
            for idx, line in enumerate(lines):
                line_strip = line.strip()
                if not line_strip:
                    continue
                starts_bracket = line_strip.startswith("[")
                ends_bracket = line_strip.endswith("]")
                if starts_bracket or in_brackets:
                    if ends_bracket or "]" in line_strip:
                        in_brackets = False
                    else:
                        in_brackets = True
                    continue
                if line_strip_is_speaker(line_strip):
                    continue

                distilled_line = distill(line)
                if distilled_line:
                    for _ in range(len(distilled_line)):
                        char_to_line_map.append(idx + 1)
                    global_distilled.append(distilled_line)

            self._global_distilled_text_cache = "".join(global_distilled)
            self._char_to_line_map_cache = char_to_line_map
            self._cached_script_path = script_path
            self._cached_mtime = mtime
            self._cached_size = size
            self._cached_plugin_name = plugin_name
            self._distill_cache_version = _DISTILL_CACHE_VERSION
            global_distilled_text = self._global_distilled_text_cache
            log_debug(f"Successfully cached and mapped script file {script_path} ({len(lines)} lines, {len(global_distilled_text)} distilled characters).")

        # Count words in original text
        words_count = len(re.findall(r'\w+', text))

        distilled_query = distill(text)
        if not distilled_query:
            return "NONE", None

        # Check if the query is too short
        if len(distilled_query) < 3:
            return "NONE", None

        start_offset = 0
        if words_count < 4:
            search_query = distilled_query
        else:
            n = len(distilled_query)
            if n < 3:
                search_query = distilled_query
            else:
                third = n // 3
                start = third
                end = n - third
                search_query = distilled_query[start:end]
                start_offset = start

        if not search_query:
            return "NONE", None

        def get_script_remainder(e_pos: int) -> str:
            remainder_chars = []
            prev_line = char_to_line_map[e_pos - 1] if e_pos > 0 else 1
            for i in range(e_pos, len(global_distilled_text)):
                curr_line = char_to_line_map[i]
                if curr_line != prev_line:
                    break
                remainder_chars.append(global_distilled_text[i])
            return "".join(remainder_chars)

        def get_prev_script_text(l_num: int) -> str:
            for idx in range(l_num - 2, -1, -1):
                line_str = lines[idx].strip()
                if not line_str or (line_str.startswith("[") and line_str.endswith("]")) or line_strip_is_speaker(line_str):
                    continue
                return line_str
            return ""

        # Get preceding and subsequent BMG strings for context check
        preceding_strings = []
        subsequent_strings = []
        if (hasattr(self.mw, 'data_store') and self.mw.data_store and
            block_idx is not None and 0 <= block_idx < len(self.mw.data_store.data)):
            block_strings = self.mw.data_store.data[block_idx]
            for prev_idx in range(max(0, s_idx - 5), s_idx):
                preceding_strings.append(block_strings[prev_idx])
            for next_idx in range(s_idx + 1, len(block_strings)):
                subsequent_strings.append(block_strings[next_idx])

        dist_prev_bmg = ""
        if preceding_strings:
            for s in reversed(preceding_strings):
                d_s = distill(s)
                if d_s:
                    dist_prev_bmg = d_s
                    break

        dist_next_bmg = ""
        if subsequent_strings:
            for s in subsequent_strings:
                d_s = distill(s)
                if d_s:
                    dist_next_bmg = d_s
                    break

        # Search the query in the global distilled text
        start_pos = 0
        while True:
            pos = global_distilled_text.find(search_query, start_pos)
            if pos == -1:
                break
            actual_pos = max(0, pos - start_offset)
            end_pos = actual_pos + len(distilled_query)

            needs_validation = False
            if end_pos < len(char_to_line_map):
                if char_to_line_map[end_pos] == char_to_line_map[end_pos - 1]:
                    needs_validation = True

            if needs_validation:
                remainder = get_script_remainder(end_pos)
                if remainder:
                    temp_remainder = remainder
                    match_valid = True
                    for next_text in subsequent_strings:
                        dist_next = distill(next_text)
                        if not dist_next:
                            continue
                        if temp_remainder.startswith(dist_next):
                            temp_remainder = temp_remainder[len(dist_next):]
                            if not temp_remainder:
                                break
                        elif dist_next.startswith(temp_remainder):
                            temp_remainder = ""
                            break
                        else:
                            match_valid = False
                            break

                    if not match_valid or (temp_remainder and len(temp_remainder) > 0):
                        start_pos = pos + 1
                        continue

            if actual_pos < len(char_to_line_map) and (end_pos - 1) < len(char_to_line_map):
                line_num = char_to_line_map[actual_pos]
                L_start = char_to_line_map[actual_pos]
                L_end = char_to_line_map[end_pos - 1]

                # Word count diff
                script_matched_text = " ".join(lines[l - 1].strip() for l in range(L_start, L_end + 1))
                words_script = len(re.findall(r'\w+', script_matched_text))
                words_bmg = len(re.findall(r'\w+', text))
                word_diff = abs(words_script - words_bmg)

                # Context Match
                has_prev_match = False
                if dist_prev_bmg:
                    prev_script_text = get_prev_script_text(line_num)
                    dist_prev_script = distill(prev_script_text)
                    if dist_prev_script:
                        if dist_prev_bmg in dist_prev_script or dist_prev_script in dist_prev_bmg:
                            has_prev_match = True

                # Speaker resolution by scanning backwards from line_num - 1
                speaker = None
                in_brackets_back = False
                for idx in range(line_num - 2, -1, -1):
                    s = lines[idx].strip()
                    if not s:
                        continue
                    if s.endswith("]") and not s.startswith("["):
                        in_brackets_back = True
                        continue
                    if in_brackets_back:
                        if s.startswith("["):
                            in_brackets_back = False
                        continue
                    if s.startswith("[") and s.endswith("]"):
                        continue
                    if line_strip_is_speaker(s):
                        speaker = re.sub(r'\(.*?\)', '', s).strip()
                        break

                speaker_str = speaker if speaker else "NONE"
                return speaker_str, str(line_num)

            start_pos = pos + 1

        return "NONE", None
