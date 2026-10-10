"""Pokemon generation III plugin: FireRed / LeafGreen, Ruby / Sapphire and Emerald.

Two ways in: the JSON dumps of the ROM text (``load_data_from_json_obj`` with a dict, one block per bank) and the
source files of a pret decompilation (``.inc``, ``.s``, ``.c``, ``.h``: ``pret_text``; a project block is one
source file, saved in place so ``2_build.bat`` only copies the translated files over the decompilation).
"""
import os
from typing import Dict, Any, Tuple, Set, Optional, List
from collections import OrderedDict
from plugins.base_game_rules import BaseGameRules
from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    PROBLEM_TAG_WARNING,
    PROBLEM_BAD_SPACING,
    PROBLEM_MISSING_ICON_SPACING,
    DEFAULT_TAG_MAPPINGS_POKEMON_FR,
    P_NEWLINE_MARKER,
    L_NEWLINE_MARKER,
    P_VISUAL_EDITOR_MARKER,
    L_VISUAL_EDITOR_MARKER
)
from . import pret_context, pret_text
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display

class ProblemIDs:
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_SUBLINE = PROBLEM_EMPTY_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING

class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""
    problem_prefix = "PKFR"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    problem_analyzer_class = ProblemAnalyzer
    text_fixer_class = TextFixer
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING

    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self.original_keys = []
        # The game's own block names, in load order. The editor may show a one-block file under the file's
        # name; the file must still be written under the block's name.
        self.original_block_names = []
        self._save_block_names = None
        # pret decompilation source files: the text of the file loaded last and the one a save writes over
        self._pret_loaded: Optional[str] = None
        self._pret_source: Optional[str] = None
        self._pret_cache: Dict[str, Tuple[int, list, Dict[str, list], Dict[str, list]]] = {}

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat(pret_text.SUFFIXES, "text", "pret decompilation source"), *DEFAULT_FORMATS]

    # The keys of every loaded block, in load order. The game files are dicts of
    # key -> string; the editor only sees the strings, so the keys are kept here
    # and travel with the host as the plugin's runtime state.

    def export_runtime_state(self) -> Any:
        return list(self.original_keys)

    def restore_runtime_state(self, state: Any) -> None:
        if state is not None:
            # The loaded block names are never narrowed: one per block after a load, more after a re-parse. A
            # state longer than them is a session of an older build, which held a split file's keys twice; the
            # keys just loaded are the right ones.
            names = self.original_block_names
            if self.original_keys and names and len(state) > len(names):
                log_debug("[PokemonFR Plugin] Session keys do not match the loaded blocks; keeping the loaded keys.")
                return
            self.original_keys = list(state)
            # Parses after the snapshot (translation files, a revert) appended names the keys no longer have.
            self.original_block_names = self.original_block_names[:len(self.original_keys)]

    def reset_runtime_state(self) -> None:
        self.original_keys = []
        self.original_block_names = []
        self._pret_loaded = None
        self._pret_source = None

    def prepare_save_context(self, context: Any) -> None:
        """Narrow the keys to the blocks that go into the file being saved."""
        if str(getattr(context, "relative_path", "")).lower().endswith(pret_text.SUFFIXES):
            # A source file of a decompilation: every save is built from the file as the game's source has it
            # (the last version offered), so an unchanged message keeps its lines byte for byte.
            versions = list(context.existing_versions())
            self._pret_source = versions[-1].decode("utf-8", "surrogateescape") if versions else self._pret_loaded
            return
        all_keys = context.runtime_state
        if all_keys is None:
            return
        if all(0 <= index < len(all_keys) for index in context.block_indices):
            self.original_keys = [all_keys[index] for index in context.block_indices]
            names = self.original_block_names
            self._save_block_names = (
                [names[index] for index in context.block_indices]
                if len(names) == len(all_keys) else None
            )
        else:
            log_debug("[PokemonFR Plugin] Key snapshot is incomplete; keys were not narrowed for this file.")

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """Load data from json obj."""
        if isinstance(json_data, (bytes, bytearray)):
            json_data = bytes(json_data).decode("utf-8", "surrogateescape")
        if isinstance(json_data, str):
            self._pret_loaded = json_data
            return [pret_text.load(json_data, self._is_asm(json_data))], {"0": "Text"}
        if not isinstance(json_data, dict):
            return [], {}
        
        # We no longer clear self.original_keys here so it can accumulate across multiple blocks.
        # It is cleared explicitly by ProjectActionHandler and AppActionHandler before loading starts.
        app_data = []
        block_names = {}
        
        sorted_blocks = sorted(json_data.items())

        for i, (block_name, string_obj) in enumerate(sorted_blocks):
            if isinstance(string_obj, dict):
                string_list = list(string_obj.values())
                key_list = list(string_obj.keys())
                
                app_data.append(string_list)
                self.original_keys.append(key_list)
                self.original_block_names.append(block_name)
                block_names[str(i)] = block_name
            else:
                log_debug(f"[PokemonFR Plugin] Skipping block '{block_name}' because its value is not a dictionary.")
        
        return app_data, block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Save data to json obj."""
        source = self._pret_source if self._pret_source is not None else self._pret_loaded
        if source is not None and not self.original_keys:
            texts = [str(text) for text in (data[0] if data else [])]
            return pret_text.write(source, self._is_asm(source), texts)
        if not self.original_keys or len(self.original_keys) != len(data):
            raise ValueError("Original keys for Pokemon data are missing or mismatched. Cannot save.")
            
        output_json = OrderedDict()
        own_names, self._save_block_names = self._save_block_names, None
        for i, block_data in enumerate(data):
            block_name = own_names[i] if own_names and i < len(own_names) else block_names.get(str(i))
            if not block_name or i >= len(self.original_keys):
                log_debug(f"[PokemonFR Plugin] Skipping block index {i} during save due to missing name or keys.")
                continue 
            
            keys_for_block = self.original_keys[i]
            if len(keys_for_block) != len(block_data):
                log_debug(f"[PokemonFR Plugin] Mismatch in string count for '{block_name}': expected {len(keys_for_block)}, got {len(block_data)}. Data will be padded/truncated.")

            string_obj = OrderedDict()
            for j, key in enumerate(keys_for_block):
                if j < len(block_data):
                    string_obj[key] = block_data[j]
                else:
                    string_obj[key] = "" # Pad with empty string if missing
            
            output_json[block_name] = string_obj
            
        return output_json
        
    @staticmethod
    def _is_asm(text: str) -> bool:
        """An assembly file holds ``.string`` lines; a C file holds ``_("...")`` calls."""
        return ".string" in text

    # -- context from the decompilation ---------------------------------------------------

    def _block_file(self, block_idx: int) -> Optional[Tuple[str, str]]:
        """``(relative path, absolute path)`` of the source file of a block."""
        try:
            pm = getattr(self.mw, "project_manager", None)
            project = getattr(pm, "project", None) if pm else None
            if project is None:
                return None
            block_map = getattr(self.mw, "block_to_project_file_map", {}) or {}
            index = block_map.get(block_idx, block_idx)
            if not isinstance(index, int) or not 0 <= index < len(project.blocks):
                return None
            rel = project.blocks[index].source_file
            path = pm.get_absolute_path(rel)
            return (rel.replace("\\", "/"), path) if path and os.path.isfile(path) else None
        except Exception as error:  # noqa: BLE001 - context is optional
            log_debug(f"[PokemonFR Plugin] no file for block {block_idx}: {error}")
            return None

    def _pret_unit(self, block_idx: int, string_idx: int):
        """``(relative path, unit or None, scripts of the text, speakers of the text)``."""
        found = self._block_file(block_idx)
        if not found or not found[0].lower().endswith(pret_text.SUFFIXES):
            return "", None, [], []
        rel, path = found
        stamp = os.stat(path).st_mtime_ns
        cached = self._pret_cache.get(path)
        if cached is None or cached[0] != stamp:
            with open(path, encoding="utf-8", errors="surrogateescape") as stream:
                text = stream.read()
            asm = pret_text.is_asm(rel)
            units = pret_text.parse(text, asm)
            scripts = {}
            if asm:
                labels = [unit.label for unit in units if unit.label]
                sibling = os.path.join(os.path.dirname(path), "scripts.inc")
                if not os.path.isfile(sibling):
                    sibling += ".ctx"      # kept by the unpack when the map's scripts hold no text themselves
                if os.path.basename(path) != "scripts.inc" and os.path.isfile(sibling):
                    with open(sibling, encoding="utf-8", errors="surrogateescape") as stream:
                        scripts = pret_text.references(stream.read(), labels)
                else:
                    scripts = pret_text.references(text, labels)
            people: Dict[str, list] = {}
            map_json = os.path.join(os.path.dirname(path), "map.json")
            if scripts and os.path.isfile(map_json):
                with open(map_json, encoding="utf-8", errors="replace") as stream:
                    people = pret_context.speakers_of_scripts(stream.read())
            cached = (stamp, units, scripts, people)
            self._pret_cache[path] = cached
        units = cached[1]
        if not 0 <= int(string_idx) < len(units):
            return rel, None, [], []
        unit = units[int(string_idx)]
        scripts = cached[2].get(unit.label, [])
        speakers: List[str] = []
        for script in scripts:
            for who in cached[3].get(script, []):
                if who not in speakers:
                    speakers.append(who)
        return rel, unit, scripts, speakers

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The one person or sign whose map script shows the text."""
        speakers = self._pret_unit(block_idx, string_idx)[3]
        return speakers[0] if len(speakers) == 1 else None

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The file and line of the text, the scripts that show it and their people."""
        rel, unit, scripts, speakers = self._pret_unit(block_idx, string_idx)
        if unit is None:
            return {}
        result: Dict[str, Any] = {"resource": f"{rel}:{unit.first_line + 1}"}
        parts = rel.split("/")
        if "maps" in parts and parts.index("maps") + 1 < len(parts) - 1:
            result["locations"] = [parts[parts.index("maps") + 1]]
        if scripts:
            result["flow_ids"] = list(scripts)
        if speakers:
            result["candidate_actors"] = list(speakers)
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        rel, unit, scripts, _speakers = self._pret_unit(block_idx, string_idx)
        if unit is None:
            return None
        shown = f", shown by {', '.join(scripts)}" if scripts else ""
        return f"Text {unit.label or '(no label)'} in {rel}{shown}."

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Texts one map script shows are one conversation."""
        rel, unit, scripts, _speakers = self._pret_unit(block_idx, string_idx)
        return f"{rel}:{scripts[0]}" if unit is not None and len(scripts) == 1 else None

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed_string = aliased.replace('\\p', P_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\l', L_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\n', newline_symbol)
        
        show_dots = False
        if self.mw and hasattr(self.mw, "show_multiple_spaces_as_dots"):
            val = self.mw.show_multiple_spaces_as_dots
            if isinstance(val, bool):
                show_dots = val
        
        return convert_spaces_to_dots_for_display(processed_string, show_dots)

    def get_enter_char(self) -> str:
        """Get the enter char."""
        return '\n'

    def get_shift_enter_char(self) -> str:
        """Get the shift enter char."""
        return f"{P_VISUAL_EDITOR_MARKER}\n"

    def get_ctrl_enter_char(self) -> str:
        """Get the ctrl enter char."""
        return f"{L_VISUAL_EDITOR_MARKER}\n"

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """Get the text representation for editor."""
        processed = str(data_string_subline).replace('\\p', f"{P_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\l', f"{L_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\n', '\n')
        return super().get_text_representation_for_editor(processed)

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        converted = super().convert_editor_text_to_data(text)
        actual_text = converted.replace(f"{P_VISUAL_EDITOR_MARKER}\n", '\\p')
        actual_text = actual_text.replace(f"{L_VISUAL_EDITOR_MARKER}\n", '\\l')
        actual_text = actual_text.replace('\n', '\\n')
        return actual_text

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Pokémon FireRed/LeafGreen"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        return DEFAULT_TAG_MAPPINGS_POKEMON_FR

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
        problems_per_subline = self.problem_analyzer.analyze_data_string(
            full_data_string_text_for_logical_check,
            editor_font_map,
            editor_line_width_threshold,
            logical_hard_limit
        )
        
        if qtextblock_number_in_editor < len(problems_per_subline):
            return problems_per_subline[qtextblock_number_in_editor]
        
        return set()

    def process_pasted_segment(self, segment_to_insert: str, *args, **kwargs) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return cleaned_segment, "OK", ""