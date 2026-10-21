"""Pokemon generation III plugin: FireRed / LeafGreen, Ruby / Sapphire and Emerald.

Two ways in: the JSON dumps of the ROM text (``load_data_from_json_obj`` with a dict, one block per bank) and the
source files of a pret decompilation (``.inc``, ``.s``, ``.c``, ``.h``: ``pret_text``; a project block is one
source file, saved in place so ``2_build.bat`` only copies the translated files over the decompilation).
"""
import json
import os
import re
from pathlib import Path
from typing import Callable, Dict, Any, Tuple, Set, Optional, List
from collections import OrderedDict
from plugins.base_game_rules import BaseGameRules
from core.i18n import tr
from plugins.common import name_seeds, pokemon_recomp
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from plugins.common.series_tags import TagMap, body_kind
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
    PROBLEM_BYTE_BUDGET,
    DEFAULT_TAG_MAPPINGS_POKEMON_FR,
    P_NEWLINE_MARKER,
    L_NEWLINE_MARKER,
    P_VISUAL_EDITOR_MARKER,
    L_VISUAL_EDITOR_MARKER
)
from . import pret_context, pret_text, rom_project
from .rom_text import CodecError
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
    PROBLEM_BYTE_BUDGET = PROBLEM_BYTE_BUDGET

def _config_aliases() -> Dict[str, str]:
    """The ``default_tag_mappings`` of this plugin's config.json: alias -> raw tag."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, encoding="utf-8") as handle:
        return dict(json.load(handle).get("default_tag_mappings") or {})


def _pret_file(rel: str, path: Any) -> Tuple[list, Dict[str, list], Dict[str, list]]:
    """``(units, scripts of each label, speakers of each script)`` of a pret source file and the files beside it.
    Reads the disk: called from a worker (plugins/common/block_loader.py)."""
    with open(path, encoding="utf-8", errors="surrogateescape") as stream:
        text = stream.read()
    units = pret_text.parse_file(text, rel)
    scripts: Dict[str, list] = {}
    if pret_text.is_asm(rel):
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
    return units, scripts, people


def _budgets_in(text_dir: str) -> Optional[Tuple[Dict[str, int], Any]]:
    """The budgets of a ROM text folder: its meta.json, else an old project's source. Reads the disk: called from a worker."""
    if not rom_project.is_rom_project(text_dir):
        return None
    ready = rom_project.meta_budgets(text_dir)
    return ready if ready is not None else rom_project.old_project_budgets(text_dir)


SERIES_TAG_MAP = TagMap(name="fr", pattern=pret_text.TAG_RE, kind_of=body_kind)

# pret name tables of the Ruby / Emerald / FireRed line: file stem (English files only) -> (section, description)
_FR_NAME_TABLES = {"species_names": ("Pokémon", "Pokémon name"), "move_names": ("Moves", "Move name"),
                   "abilities": ("Abilities", "Ability name"), "ability_names": ("Abilities", "Ability name"),
                   "items": ("Items", "Item name"), "type_names": ("Types", "Type name"),
                   "trainer_class_names": ("Characters", "Trainer class")}
_OTHER_LANGUAGE = re.compile(r"_(de|fr|es|it|ge|sp|ja|ko|zh)$")
_C_NAME = re.compile(r'_\("((?:[^"\\]|\\.)*)"\)')
_ITEM_NAME = re.compile(r'\.name\s*=\s*_\("((?:[^"\\]|\\.)*)"\)')
_DOT_STRING = re.compile(r'\.string\s+"((?:[^"\\]|\\.)*)"')


def _fr_name_texts(stem: str, text: str) -> List[str]:
    """The rows of one name table: ``_("NAME")`` in C, ``.name = _(...)`` in items.h, ``.string "NAME$"`` in an .inc."""
    if stem == "items":
        return _ITEM_NAME.findall(text)
    texts = _C_NAME.findall(text)
    texts += [s[:-1] if s.endswith("$") else s for s in _DOT_STRING.findall(text)]
    return texts


class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""
    problem_prefix = "PKFR"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    problem_analyzer_class = ProblemAnalyzer
    text_fixer_class = TextFixer
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING

    def get_series_tag_map(self):
        """The control tags of this game, with a kind each, for the series reuse (plugins/common/series_tags.py)."""
        return SERIES_TAG_MAP

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
        # Read off the UI thread (plugins/common/block_loader.py): a block's pret source and the fixed name fields of its
        # ROM project (None outside a ROM project).
        self._pret = ReadThrough("pokemon_fr pret", lambda block_idx: rescan_block(self.mw, block_idx))
        self._budgets = ReadThrough("pokemon_fr budgets", lambda block_idx: rescan_block(self.mw, block_idx))

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        # newline="": the decompilation's line endings come back as they are (a plain text write would make CRLF)
        return [FileFormat(pret_text.SUFFIXES, "text", "pret decompilation source", newline=""), *DEFAULT_FORMATS]

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
        self._pret.clear()
        self._budgets.clear()

    def prepare_save_context(self, context: Any) -> None:
        """Narrow the keys to the blocks that go into the file being saved."""
        name = str(getattr(context, "relative_path", "")).lower()
        if name.endswith(pret_text.ASM_SUFFIXES + pret_text.C_SUFFIXES) or (
                name.endswith(pret_text.JSON_SUFFIXES) and self._is_pret_json_file(context)):
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

    def _is_pret_json_file(self, context: Any) -> bool:
        """A ``.json`` file is a decompilation's JSON only when its text has the pret roots (other JSON keys)."""
        versions = list(context.existing_versions())
        text = versions[-1].decode("utf-8", "surrogateescape") if versions else self._pret_loaded
        return isinstance(text, str) and pret_text.is_pret_json(text)

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """Load data from json obj."""
        if isinstance(json_data, (bytes, bytearray)):
            json_data = bytes(json_data).decode("utf-8", "surrogateescape")
        if isinstance(json_data, str):
            # ``.json`` is a text format of this plugin (the decompilation's region map and item tables), so a
            # JSON dump of the ROM text arrives here as text: it is parsed back into a dict.
            if pret_text.is_pret_json(json_data):
                units = pret_text.load_json(json_data)
            elif json_data.lstrip().startswith("{"):
                try:
                    json_data = json.loads(json_data)
                except ValueError:
                    return [], {}
                units = None
            else:
                units = pret_text.load(json_data, self._is_asm(json_data))
            if units is not None:
                if not units:
                    return [], {}      # no decompilation text: what a text file gave this plugin before
                self._pret_loaded = json_data
                return [units], {"0": "Text"}
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
            if pret_text.is_pret_json(source):
                return pret_text.write_json(source, texts)
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

        # the ROM text dumps are JSON files, a text format of this plugin: the file's text
        return json.dumps(output_json, ensure_ascii=False, indent=4)

    @staticmethod
    def _is_asm(text: str) -> bool:
        """An assembly file holds ``.string`` or ``.braille`` lines; a C file holds ``_("...")`` calls."""
        return pret_text.is_asm_text(text)

    # -- context from the decompilation ---------------------------------------------------

    def _block_file(self, block_idx: int) -> Optional[Tuple[str, Any]]:
        """``(relative path, absolute path)`` of the source file of a block, from the open project."""
        return source_of(self.mw, block_idx)

    def _pret_unit(self, block_idx: int, string_idx: int):
        """``(relative path, unit or None, scripts of the text, speakers of the text)``, from memory (read off the UI thread)."""
        found = self._block_file(block_idx)
        if not found or not found[0].lower().endswith(pret_text.SUFFIXES):
            return "", None, [], []
        rel, path = found
        parsed = self._pret.get(block_idx, lambda: _pret_file(rel, path))
        if parsed is None:
            return rel, None, [], []
        units, scripts_of_label, people = parsed
        if not 0 <= int(string_idx) < len(units):
            return rel, None, [], []
        unit = units[int(string_idx)]
        scripts = scripts_of_label.get(unit.label, [])
        speakers: List[str] = []
        for script in scripts:
            for who in people.get(script, []):
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

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, moves, items, abilities, types and trainer classes from the decomp's name tables (English files)."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        try:
            blocks = list(pm.project.blocks)
        except (AttributeError, TypeError):
            return []
        collector = name_seeds.TermCollector()
        for block in blocks:
            rel = str(block.source_file).replace("\\", "/")
            stem = Path(rel).stem
            if _OTHER_LANGUAGE.search(stem):
                continue
            stem = stem[:-3] if stem.endswith("_en") else stem
            if stem not in _FR_NAME_TABLES:
                continue
            section, _description = _FR_NAME_TABLES[stem]
            try:
                text = Path(pm.get_absolute_path(block.source_file)).read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                log_debug(f"pokemon_fr: no glossary terms from {rel}: {error}")
                continue
            collector.add_table(rel, _fr_name_texts(stem, text), section, f"{stem} table")
        return collector.entries

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

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
        return "Pokémon FireRed / LeafGreen, Ruby / Sapphire, Emerald"

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message box in the game's own font (plugins/pokemon_fr/preview_panel.py)."""
        from plugins.pokemon_fr.preview_panel import MessageWindowPreview
        return MessageWindowPreview(main_window)

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings: the short aliases of config.json, in place of the raw tags they stand for."""
        aliases = _config_aliases()
        aliased = set(aliases.values())
        mappings = {alias: tag for alias, tag in DEFAULT_TAG_MAPPINGS_POKEMON_FR.items() if tag not in aliased}
        mappings.update(aliases)
        return mappings

    # ----- Project Manager: ROM mode (a game ROM unpacks to text; the build writes a patched ROM) -----

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": rom_project.ROM_ROLE, "label": "Game ROM (Game Boy Advance)"}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return rom_project.identify(path)

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "gba", "label": "Game Boy Advance"}]

    def get_source_subfolder(self) -> Optional[str]:
        return rom_project.SOURCE_DIR

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        rom = sources.get(rom_project.ROM_ROLE)
        if not rom:
            return None
        return rom_project.unpack(rom, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "rom", "label": "Patched ROM", "platforms": ["gba"], "kind": "patch"},
                {"id": pokemon_recomp.TARGET_ID, "label": tr("Recomp package (EmeraldRecomp, FireRedLeafGreenRecomp)"),
                 "platforms": ["gba"], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
        if target_id == "rom":
            return rom_project.build(source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == pokemon_recomp.TARGET_ID:
            return pokemon_recomp.build_packages(
                source_dir, translation_dir, output_dir,
                lambda s, t, o: rom_project.build(s, t, o, progress, is_cancelled), progress, is_cancelled)
        raise ValueError(f"Unknown build target: {target_id}")

    def _budgets_of(self, block_idx: int) -> Optional[Tuple[Dict[str, int], Any]]:
        """The budgets of a block's text folder, from memory. Read off the UI thread once per block (an old project's
        budgets are read there too); until then the check answers False for it."""
        found = self._block_file(block_idx)
        if not found:
            return None
        text_dir = os.path.dirname(found[1])
        return self._budgets.get(block_idx, lambda: _budgets_in(text_dir))

    def exceeds_byte_budget(self, block_idx: int, string_idx: int, text: str) -> bool:
        """True when a fixed name field of the ROM (a C-built table entry) cannot hold this text.

        Messages are not fixed fields: they move to free space when they grow, so they never exceed a budget.
        """
        block = self._block_file(block_idx)
        if not block:
            return False
        budgets = self._budgets_of(block_idx)
        if budgets is None:
            return False
        sizes, charmap = budgets
        _rel, unit, _scripts, _speakers = self._pret_unit(block_idx, string_idx)
        size = sizes.get(unit.label) if unit is not None else None
        if size is None:
            return False
        try:
            return len(charmap.encode(text)) > size
        except CodecError:
            return False

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