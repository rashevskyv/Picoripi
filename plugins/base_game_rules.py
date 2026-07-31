from typing import List, Tuple, Dict, Optional, Any, Set
from PyQt6.QtGui import QTextCharFormat
import json
import re

class BaseGameRules:
    """
    Base class for game-specific rules.
    Supports the 'Kruptar' format: strings delimited by {END} + empty line.
    """
    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self._alias_lookup_signature = None
        self._alias_lookup_cache = None

    def _get_alias_lookup_tables(self, mappings: Dict[str, str]):
        """Build alias lookup tables once for the current mapping contents."""
        signature = (id(mappings), tuple(mappings.items()))
        if signature == self._alias_lookup_signature and self._alias_lookup_cache is not None:
            return self._alias_lookup_cache

        tag_pattern = re.compile(r'(?:\{[^{}]*\}|\[[^\[\]]*\])')
        reverse: Dict[str, str] = {}
        tag_aliases: Dict[str, str] = {}
        non_tag_to_alias = []
        non_alias_to_tag = []
        for alias, original_tag in mappings.items():
            if not original_tag:
                continue
            if tag_pattern.fullmatch(original_tag):
                reverse.setdefault(original_tag, alias)
            else:
                non_tag_to_alias.append((alias, original_tag))
            if alias:
                if tag_pattern.fullmatch(alias):
                    tag_aliases[alias] = original_tag
                else:
                    non_alias_to_tag.append((alias, original_tag))

        non_tag_to_alias.sort(key=lambda item: len(item[1]), reverse=True)
        non_alias_to_tag.sort(key=lambda item: len(item[0]), reverse=True)
        self._alias_lookup_signature = signature
        self._alias_lookup_cache = (
            reverse,
            tag_aliases,
            non_tag_to_alias,
            non_alias_to_tag,
        )
        return self._alias_lookup_cache

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """Load data from json obj."""
        if isinstance(json_data, list):
            # If it's an empty list, return it as a single empty block
            if not json_data:
                return [[]], {}
            # If it's already a list of lists, return as is
            if all(isinstance(sub, list) for sub in json_data):
                return json_data, {}
            # Otherwise, assume it's a single block containing these items
            return [json_data], {}
        
        if isinstance(json_data, dict):
            # Try to handle common dict-based formats (e.g. { "strings": [...] })
            if "strings" in json_data and isinstance(json_data["strings"], list):
                return self.load_data_from_json_obj(json_data["strings"])
            # Fallback for generic dict: wrap in list? No, probably return as is if it's a block
            # But the UI expects List[List[str]].
            return [], {}

        if isinstance(json_data, str):
            # Kruptar format check: if it contains {END}, split by it
            if '{END}' in json_data:
                raw_strings = re.split(r'\{END\}', json_data)
                processed_strings = []
                for s in raw_strings:
                    cleaned = s.strip('\r\n')
                    # If it's not empty, or it's the last one and contains content
                    if cleaned:
                        processed_strings.append(cleaned)
                    elif s == raw_strings[-1] and s.strip():
                         processed_strings.append(s.strip())
                return [processed_strings], {}
            
            # Fallback: treat as a single block with lines
            lines = json_data.splitlines()
            return [lines], {}
        return [], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        # If we are dealing with a single block (typical for .txt files)
        """Save data to json obj."""
        if len(data) == 1 and isinstance(data[0], list):
            # If we suspect Kruptar format (or just want to be safe if we loaded it that way)
            # For now, let's assume if we have {END} in the original or if it's multi-line strings
            # we might want to use {END}. But to be safe and consistent with user request:
            # "один блок - одна строка. {END} + порожня строка - симантичний символ"
            return "\n\n".join([str(line) + "\n{END}" for line in data[0]])
        return data
    
    def get_enter_char(self) -> str:
        """Get the enter char."""
        return '\n'
        
    def get_shift_enter_char(self) -> str:
        """Get the shift enter char."""
        return '\n'

    def get_ctrl_enter_char(self) -> str:
        """Get the ctrl enter char."""
        return '\n'

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        return self.replace_aliases_with_tags(text)

    def get_display_name(self) -> str:
        """Get the display name."""
        if self.mw and hasattr(self.mw, 'display_name'):
            return self.mw.display_name
        return "Base Game (No Plugin)"

    def should_auto_match_story_context(self, block_idx: int, string_idx: int) -> bool:
        """Whether this physical string may participate in automatic dialogue matching."""
        return True

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Game metadata that should accompany this string in AI workflows.

        The engine recognises these keys and assigns their VALUES no meaning --
        it never compares them against anything game-specific. Every value, and
        what it implies, belongs to the plugin:

        ``window_type`` (str)
            Inserted as ``Window Type: <value>``.
        ``content_role`` (str)
            Inserted as ``Content Role: <value>``. Free-form.
        ``role_instruction`` (str)
            Inserted verbatim as the instruction for that role. This is how a
            plugin teaches the model what its own roles mean without the engine
            having to know.
        ``has_speaker`` (bool)
            ``False`` marks the line as not spoken dialogue, so no speaker is
            looked up for it. Omit it when the line is ordinary dialogue.
        ``glossary_section`` (str)
            Section a new term from this line goes into.
        ``force_glossary`` (bool)
            Marks the line as one that must produce a glossary entry.

        Default: no metadata.
        """
        return {}

    def get_capabilities(self) -> Set[str]:
        """Optional abilities this plugin declares, for the build wizard.

        Lets the engine offer only the steps a plugin can actually perform,
        instead of presenting every stage and failing halfway. Recognised names
        are documented in docs/PLUGIN_AUTHORING_GUIDE.md. Default: none.
        """
        return set()

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Glossary material read straight out of the game's own data.

        Some games name their own terms: an item window already pairs a name
        with an icon and an explanation, a location plate already holds a place
        name. Where that is true, the terms need no AI pass to be discovered --
        the plugin hands them over and the build seeds them directly.

        Returns a list of dicts with:
        ``term`` (required), ``description``, ``section``, ``icon``,
        ``source_ref`` (free-form provenance, e.g. block/string coordinates).
        Default: nothing to seed.
        """
        return []

    def get_external_lore(self, term: str) -> Optional[str]:
        """Background knowledge about a term from a source outside the game.

        For games with a community reference (a wiki, a published guide) a
        plugin may look the term up and return prose the describe pass can use.
        Whether such a source exists, and whether it is trustworthy, is entirely
        the plugin's business. Default: no external source.
        """
        return None

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return {}

    def get_color_marker_definitions(self) -> Dict[str, str]:
        """Returns descriptions for manual color markers."""
        return {}

    def get_spellcheck_ignore_pattern(self) -> str:
        """Returns a regex pattern of sequences to ignore during spellcheck (e.g. tags, control codes)."""
        # Default: ignore standard curly and square bracket tags
        patterns = [r'\{[^}]*\}', r'\[[^\]]*\]']
        
        # Add control codes from plugin if defined
        # We check both class attribute and module-level constant
        codes = []
        if hasattr(self, 'CONTROL_CODES'):
            codes = self.CONTROL_CODES
        else:
            # Try to get from the module where the subclass is defined
            import sys
            module = sys.modules.get(self.__class__.__module__)
            if module and hasattr(module, 'CONTROL_CODES'):
                codes = module.CONTROL_CODES
        
        if codes:
            # Escape each code to handle special regex characters like backslash or dots
            escaped_codes = [re.escape(c) for c in codes]
            patterns.extend(escaped_codes)
            
        return '|'.join(patterns)

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        return set()

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix data string."""
        return data_string, False

    def process_pasted_segment(self,
                                segment_to_insert: str,
                                original_text_for_tags: str,
                                editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        return segment_to_insert, "OK", ""
        
    def get_base_game_rules_class(self):
        """Get the base game rules class."""
        return BaseGameRules

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        return {}

    def get_dynamic_name_tags(self) -> Dict[str, str]:
        """Return a mapping of {tag_string: replacement_name} for dynamic in-game names.

        These tags are substituted *before* stripping tags during script-matching distillation,
        so that a name tag in the game text matches the written-out name used in
        an external script (e.g. a horse's name tag matching 'Epona').
        The dict key must be the exact tag string as it appears in editor text.
        """
        return {}
    
    def get_tag_checker_handler(self) -> Optional[Any]:
        """Get the tag checker handler."""
        return None
        
    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        problem_definitions = self.get_problem_definitions()
        return problem_definitions.get(problem_id, {}).get("name", problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        """Get the plugin actions."""
        return []

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """Get the text representation for editor."""
        return self.replace_tags_with_aliases(data_string_subline)

    def replace_tags_with_aliases(self, text: str) -> str:
        """Replace complete tag tokens with aliases.

        Alias values are tags, not arbitrary substrings.  Exact token matching
        prevents a mapping for ``{escape:0:0037}`` from corrupting the longer
        ``{escape:0:003700}`` tag.
        """
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        mappings = self.mw.default_tag_mappings
        reverse, _, non_tag_mappings, _ = self._get_alias_lookup_tables(mappings)
        result = re.sub(
            r'\{[^{}]*\}|\[[^\[\]]*\]',
            lambda match: reverse.get(match.group(0), match.group(0)),
            str(text),
        )
        for alias, original_tag in non_tag_mappings:
            result = result.replace(original_tag, alias)
        return result

    def replace_aliases_with_tags(self, text: str) -> str:
        """Replace complete alias tokens with their stored tags."""
        if not self.mw or not hasattr(self.mw, 'default_tag_mappings') or not self.mw.default_tag_mappings:
            return text
        mappings = self.mw.default_tag_mappings
        _, tag_aliases, _, non_tag_mappings = self._get_alias_lookup_tables(mappings)
        result = re.sub(
            r'\{[^{}]*\}|\[[^\[\]]*\]',
            lambda match: tag_aliases.get(match.group(0), match.group(0)),
            str(text),
        )
        for alias, original_tag in non_tag_mappings:
            result = result.replace(alias, original_tag)
        return result

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        aliased = self.replace_tags_with_aliases(str(data_string))
        return aliased.replace('\n', newline_symbol)

    def prepare_preview_glyph_text(self, text: str) -> Tuple[str, Optional[List[Optional[str]]]]:
        """Prepare raw string text for the visual (BFN) preview renderer.

        Returns (clean_text, per_char_colors). clean_text has all control tags
        removed; per_char_colors is either None (single default color) or a list
        aligned with clean_text where each entry is a "#rrggbb" string or None.
        Plugins override this to substitute dynamic names and map in-game color
        tags to real text colors.
        """
        import re
        cleaned = str(text)
        pattern = self.get_spellcheck_ignore_pattern()
        if pattern:
            try:
                cleaned = re.sub(pattern, "", cleaned)
            except Exception:
                pass
        cleaned = re.sub(r'\{[^}]*\}', "", cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', "", cleaned)
        return cleaned, None

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Per-string layout defaults derived from game data (e.g. the message's
        window type): {"warn_width": int, "max_width": int, "font_file": str,
        "lines_per_page": int}. Any key may be omitted.

        Resolution priority in the app: explicit per-string metadata override >
        this hook > global plugin settings. Default: no game-derived layout.
        """
        return None

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Per-line game-script flow context for the AI translation prompt.

        Plugins that can reconstruct the game's dialogue graphs from its data
        return a short English annotation: which conversation the line belongs
        to, its position, branch conditions and follow-up game actions.
        Default: no flow data.
        """
        return None

    def get_ai_flow_overview(self, block_idx: int, string_indices) -> Optional[str]:
        """Conversation outlines covering the given string indices, used as a
        chunk-level context section in AI translation prompts. Default: None."""
        return None

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Game-truth scene evidence for one line, for the Story Timeline window.

        Plugins that can mine the game's own data return a dict with any of:
        ``resource`` (the file this line came from), ``msg_group`` (its resource
        group), ``flow_ids``, ``candidate_actors`` (characters that own this
        text, may be ambiguous), ``flow_summary`` (per-line conversation
        context), ``location_candidates`` (places that use this resource).
        Default: no data.
        """
        return {}

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        return []

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        return set()

    def get_tag_tooltip(self, tag: str) -> str:
        """Return an optional human-readable explanation for an editor tag."""
        return ""

    def get_context_menu_actions(self, editor_widget, selected_text: Optional[str]) -> List[Dict[str, Any]]:
        """Get the context menu actions."""
        return []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        return None

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
        return 2

    def get_custom_context_tags(self) -> Dict[str, List[Dict[str, str]]]:
        """Get the custom context tags."""
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            return self.mw.context_menu_tags
        return {"single_tags": [], "wrap_tags": []}

    def save_custom_context_tags(self, tags_data: dict) -> None:
        """Save custom context tags."""
        if self.mw and hasattr(self.mw, 'context_menu_tags'):
            self.mw.context_menu_tags = tags_data
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()

    def get_font_for_block(self, block_idx: int) -> Optional[Dict[str, str]]:
        """Returns a dict with 'original_font_name' and 'font_name' if block has specific font overrides."""
        return None

    def get_default_script_name(self) -> Optional[str]:
        """
        Return the default script file name for this game.
        Override in subclasses if needed (e.g. 'zelda_mc_script.md').
        """
        return None

    def parse_walkthrough_transcript(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse game-specific walkthrough transcript text file into structured rooms and dialogue cues.
        Plugins should override this to handle custom separators, chapters, acts, speakers, etc.
        """
        import os
        import re
        from utils.logging_utils import log_warning
        
        transcript_list = []
        if not file_path or not os.path.exists(file_path):
            return transcript_list
            
        try:
            if file_path.lower().endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        transcript_list = data
                    elif isinstance(data, dict) and "lines" in data:
                        transcript_list = data["lines"]
            elif file_path.lower().endswith(".md"):
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(file_path)
                transcript_list = parsed.get("dialogues", [])
            else:
                # Highly advanced text parser for structured and GameFAQ scripts
                # Supports standardized [Chapter: ...], {Action: ...}, classical SPEAKER: dialogue, 
                # as well as classic bracketed descriptions and uppercase gutter speakers.
                with open(file_path, "r", encoding="cp1252", errors="replace") as f:
                    lines = f.readlines()
                
                current_chapter = "Foreword"
                last_speaker = "Dialogue/Narrator"
                last_brackets = ""
                open_bracket_action = None

                for idx, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        if open_bracket_action:
                            last_brackets = " ".join(open_bracket_action).strip()
                            open_bracket_action = None
                        continue

                    if open_bracket_action is not None:
                        if line.endswith("]"):
                            open_bracket_action.append(line[:-1].strip())
                            last_brackets = " ".join(open_bracket_action).strip()
                            open_bracket_action = None
                        else:
                            open_bracket_action.append(line)
                        continue
                    
                    # 1. Detect Wave separators (e.g. ~~~~~~~~~~~~~~~~~~~~~~~~) to split micro-scenes
                    if line.startswith("~") or (len(line) > 5 and all(c == '~' for c in line)):
                        last_brackets = ""
                        continue
                    
                    # 2. Detect Standard Chapter / Location tags (e.g. [Chapter: Prologue])
                    chapter_location_match = re.match(r'^\[(Chapter|Location):\s*(.*)\]$', line)
                    if chapter_location_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', chapter_location_match.group(2)).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = "" # Reset micro-scene boundary on new chapter
                        continue
                    
                    # 3. Detect Standard Action / Context tags (e.g. {Action: Zelda sighs})
                    action_match = re.match(r'^\{(Action|Context):\s*(.*)\}$', line)
                    if action_match:
                        last_brackets = action_match.group(2).strip()
                        continue

                    # 4. Fallback: Detect classic GameFAQ Chapter / Act changes
                    chapter_match = re.search(r'(Chapter\s+[IVXLCDM\d]+|ACT\s+[A-Z]+|Act\s+[A-Za-z]+)', line)
                    if chapter_match:
                        clean_ch = re.sub(r'[^a-zA-Z0-9_\s]', '', line).strip()
                        clean_ch = "_".join(clean_ch.split())
                        if len(clean_ch) > 3:
                            current_chapter = clean_ch
                        last_brackets = ""
                        continue

                    # 5. Fallback: Detect classic action descriptions in brackets [...]
                    if line.startswith("[") and line.endswith("]"):
                        last_brackets = line[1:-1].strip()
                        continue
                    if line.startswith("["):
                        open_bracket_action = [line[1:].strip()]
                        continue

                    # 6. Detect Standard Inline Speaker dialogue (e.g. "ZELDA: I must find Link.")
                    speaker_dialogue_match = re.match(r'^([A-Z][A-Z\s]+):\s*(.*)$', line)
                    if speaker_dialogue_match:
                        last_speaker = speaker_dialogue_match.group(1).strip()
                        text = speaker_dialogue_match.group(2).strip()
                        context_note = f"Action: {last_brackets}" if last_brackets else ""
                        transcript_list.append({
                            "text": text,
                            "speaker": last_speaker,
                            "timestamp": context_note or f"Scene_{idx}",
                            "room": current_chapter
                        })
                        continue

                    # 7. Fallback: Detect Speaker (Uppercase words on a separate line, e.g. "MIDNA")
                    if line.isupper() and len(line) >= 2 and not line.startswith("ACT") and not line.startswith("CHAPTER") and not line.startswith("VERSION"):
                        last_speaker = line
                        continue

                    # 8. Classic Dialogue lines (fallback for flat text)
                    text = line
                    context_note = f"Action: {last_brackets}" if last_brackets else ""
                    
                    transcript_list.append({
                        "text": text,
                        "speaker": last_speaker,
                        "timestamp": context_note or f"Scene_{idx}",
                        "room": current_chapter
                    })
        except Exception as e:
            log_warning(f"BaseGameRules: Failed to parse transcript: {e}")
            
        return transcript_list
