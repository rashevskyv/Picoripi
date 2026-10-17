"""Pokémon Red / Blue / Yellow (Game Boy, USA) through the pret decomps pokered and pokeyellow.

The project's files are the decomp's own asm files (``1_unpack.bat`` copies the ones with game text into
``source/``); ``asm_text`` turns each into editable strings and writes edits back into the asm, keeping every
line it did not change. ``2_build.bat`` assembles the decomp with ``translation/`` laid over it.

Letters: ``constants/charmap.asm`` in ``source/`` maps the Ukrainian letters to free cells of
``gfx/font/font.png`` and the look-alikes to their Latin tiles, so text is typed as it is read.

Context: ``picoripi/context.json`` (written by ``1_unpack.bat``) names for each text label its map, the
person whose script shows it (the map object's sprite) and the script line.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from utils.utils import clean_spaces

from . import asm_text, rom_project, rom_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .problem_analyzer import ProblemAnalyzer
from .tag_manager import TagManager
from .tag_manager import SERIES_TAG_MAP

CHAR_WIDTH = 8
LINE_CHARS = 18
# Game codes and how many characters they print (names: the longest the game allows).
CODE_CHARS = {"<PLAYER>": 7, "<RIVAL>": 7, "<PKMN>": 2, "<TM>": 2, "<PC>": 2, "<TRAINER>": 7, "<ROCKET>": 6,
              "<USER>": 10, "<TARGET>": 10, "<……>": 2, "#": 4}
_CODE = re.compile(r"<[^<>]+>|\{[^{}]*\}|#|@")
NAME_FILES = {"data/pokemon/names.asm": "Pokémon", "data/moves/names.asm": "Moves",
              "data/items/names.asm": "Items", "data/trainers/names.asm": "Trainer classes",
              "data/types/names.asm": "Types"}


def _macro_line(raw: str) -> Tuple[str, str]:
    """A rendered asm line as the codec reads it: its macro word and its arguments."""
    word, _, args = raw.strip().partition(" ")
    return word, args.strip()


def text_width(text: str) -> int:
    """Pixels of the longest line: 8 per character, codes as the characters they print."""
    widest = 0
    for line in text.split("\n"):
        chars = 0
        for part in _CODE.split(line):
            chars += len(part)
        chars += sum(CODE_CHARS.get(code, 1 if code.startswith("<") else 0) for code in _CODE.findall(line))
        widest = max(widest, chars)
    return widest * CHAR_WIDTH


# The disk reads of this plugin. They run in a worker (plugins/common/block_loader.py), never on the UI thread.

def _asm_units(rel: str, path: Path) -> Tuple[str, List[asm_text.Unit]]:
    return rel, asm_text.parse(path.read_text("utf-8"))[1]


def _read_context(path: str) -> Dict[str, Any]:
    """The context of the unpacked project (``picoripi/context.json``); {} when there is none."""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _budgets_near(source: Path) -> Optional[Tuple[Dict[str, int], rom_text.Names]]:
    """The budgets of the rom/meta.json a few folders above a block's text file (None when there is none)."""
    for folder in list(source.parents)[:4]:
        candidate = folder / rom_project.ROM_DIR / "meta.json"
        if candidate.is_file():
            return rom_project.read_budgets(str(candidate))
    return None


class GameRules(BaseGameRules):
    """Pokémon Red / Blue / Yellow, pret decomps."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True
    problem_analyzer_class = ProblemAnalyzer
    game_name = "Pokémon Red / Blue / Yellow (Game Boy)"

    def get_series_tag_map(self):
        """The control tags of this game, with a kind each, for the series reuse (plugins/common/series_tags.py)."""
        return SERIES_TAG_MAP

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._template: Optional[str] = None
        # Read off the UI thread (plugins/common/block_loader.py): a block's asm units, its ROM budgets, the context.
        self._files = ReadThrough("pokemon_gen1 asm", lambda block_idx: rescan_block(self.mw, block_idx))
        self._budgets = ReadThrough("pokemon_gen1 budgets", lambda block_idx: rescan_block(self.mw, block_idx))
        self._contexts = ReadThrough("pokemon_gen1 context")

    def get_display_name(self) -> str:
        return self.game_name

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message box in the game's own font (plugins/pokemon_gen1/preview_panel.py)."""
        from .preview_panel import MessageWindowPreview
        return MessageWindowPreview(main_window)

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".asm",), "bytes", "pret decomp asm")]   # bytes: the line ends stay as they are

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if isinstance(json_obj, (bytes, bytearray)):
            json_obj = bytes(json_obj).decode("utf-8")
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        self._template = json_obj
        return [asm_text.texts(json_obj)], {}

    def prepare_save_context(self, context: Any) -> None:
        """The asm is rebuilt around its code: take the newest version that exists (translation, else source)."""
        if not str(getattr(context, "relative_path", "")).lower().endswith(".asm"):
            return
        for raw in context.existing_versions():
            self._template = raw.decode("utf-8")
            return

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        if self._template is None:
            raise ValueError("No asm file to write the text into")
        texts = data[0] if data else []
        return asm_text.apply(self._template, [str(text) for text in texts]).encode("utf-8")

    def reset_runtime_state(self) -> None:
        self._template = None
        self._files.clear()
        self._contexts.clear()
        self._budgets.clear()

    # -- where a string comes from -----------------------------------------------------------

    def _project(self):
        return getattr(getattr(self, "mw", None), "project_manager", None)

    def _file(self, block_idx: int) -> Tuple[str, List[asm_text.Unit]]:
        """``(path in the decomp, units)`` of a block's source file, from memory; ``("", [])`` until it is read."""
        source = source_of(self.mw, block_idx)
        if source is None or not source[0].endswith(".asm"):
            return "", []
        rel, path = source
        return self._files.get(block_idx, lambda: _asm_units(rel, path)) or ("", [])

    def _unit(self, block_idx: int, string_idx: int) -> Tuple[str, Optional[asm_text.Unit]]:
        rel, units = self._file(block_idx)
        try:
            return rel, units[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return rel, None

    def _context(self) -> Dict[str, Any]:
        pm = self._project()
        project_dir = getattr(pm, "project_dir", None) or ""
        path = os.path.join(project_dir, "context.json") if project_dir else ""
        if not path:
            return {}
        return self._contexts.get(path, lambda: _read_context(path)) or {}

    def _label_context(self, block_idx: int, string_idx: int) -> Tuple[str, Optional[asm_text.Unit], Dict]:
        rel, unit = self._unit(block_idx, string_idx)
        entry = self._context().get("labels", {}).get(unit.label, {}) if unit is not None and unit.label else {}
        return rel, unit, entry

    # -- byte budgets ----------------------------------------------------------------------------

    def _budget_data(self, block_idx: int) -> Optional[Tuple[Dict[str, int], rom_text.Names]]:
        """The budgets and names of the block's ROM project, from memory: the meta.json search and read run off the UI thread."""
        source = source_of(self.mw, block_idx)
        if source is None:
            return None
        path = source[1]
        return self._budgets.get(block_idx, lambda: _budgets_near(path))

    def exceeds_byte_budget(self, block_idx: int, string_idx: int, text: str) -> bool:
        """True when a field the ROM keeps in place cannot hold this text.

        The budget key is the unit's label and its index among the units of that label (``label#k``). A movable
        body has no budget: it moves to free space when it grows.
        """
        _rel, units = self._file(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return False
        if not 0 <= index < len(units) or not units[index].label:
            return False
        unit = units[index]
        data = self._budget_data(block_idx)
        if data is None:
            return False
        budgets, names = data
        ordinal = sum(1 for earlier in units[:index] if earlier.label == unit.label)
        size = budgets.get(f"{unit.label}#{ordinal}")
        if size is None:
            return False
        try:
            if unit.single:      # a name field or a list entry: its own keyword and the text as one literal
                lines = [(unit.lines[0].keyword, '"' + asm_text.escape(text) + '"')]
            else:
                lines = [_macro_line(raw) for raw in asm_text.render(asm_text.from_editor(text, unit), unit)
                         if raw.strip()]
            return rom_text.encoded_length(lines, names) > size
        except (rom_text.CodecError, ValueError, IndexError):
            return False

    # -- context hooks -----------------------------------------------------------------------------

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The sprite of the map person whose script shows this text."""
        return self._label_context(block_idx, string_idx)[2].get("speaker")

    def is_placeholder_speaker(self, name: str) -> bool:
        return False

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel, unit, entry = self._label_context(block_idx, string_idx)
        if entry.get("role") == "Sign":
            return {"content_role": "Sign", "has_speaker": False}
        if rel in NAME_FILES:
            return {"content_role": "Name", "has_speaker": False, "glossary_section": NAME_FILES[rel],
                    "role_instruction": "NAMES: a name in the game's capitals; it must fit the same length."}
        if unit is not None and unit.single:
            return {"content_role": "Menu", "has_speaker": False}
        return {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The asm line of the text, its label, the map and the script that shows it."""
        rel, unit, entry = self._label_context(block_idx, string_idx)
        if unit is None:
            return {}
        result: Dict[str, Any] = {"resource": f"{rel}:{unit.start + 1}"}
        if unit.label:
            result["flow_ids"] = [unit.label]
        if entry.get("map"):
            result["location_candidates"] = [entry["map"]]
            result["msg_group"] = entry["map"]
        if entry.get("speaker"):
            result["candidate_actors"] = [entry["speaker"]]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        rel, unit, entry = self._label_context(block_idx, string_idx)
        if unit is None or not unit.label:
            return None
        where = f" on map {entry['map']}, shown by {entry['script']}" if entry.get("script") else ""
        return f"Text {unit.label} ({rel}){where} in the pret decomp."

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Texts of one map file are one scene."""
        rel, unit = self._unit(block_idx, string_idx)
        return rel if unit is not None and rel.startswith("text/") else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, move, item, trainer class and type names from the decomp's name tables."""
        pm = self._project()
        source = getattr(getattr(pm, "project", None), "metadata", {}) or {}
        root = source.get("source_path") if isinstance(source, dict) else None
        entries = []
        for rel, section in NAME_FILES.items():
            path = Path(root or "", rel)
            if not root or not path.is_file():
                continue
            for unit in asm_text.parse(path.read_text("utf-8"))[1]:
                term = asm_text.to_editor(unit).replace("@", "").strip()
                if term and "\n" not in term:
                    entries.append({"term": term, "section": section, "source_ref": f"{rel}:{unit.start + 1}"})
        return entries

    # -- width and editing ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        width = LINE_CHARS * CHAR_WIDTH
        return {"max_width": width, "warn_width": width, "lines_per_page": 2}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return text_width(text)

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool,
                        editor_font_map: Optional[Dict] = None, editor_line_width_threshold: Optional[int] = None,
                        full_data_string_text_for_logical_check: Optional[str] = None,
                        is_target_for_debug: bool = False, logical_hard_limit: Optional[int] = None) -> Set[str]:
        threshold = editor_line_width_threshold or LINE_CHARS * CHAR_WIDTH
        full_text = text if full_data_string_text_for_logical_check is None else full_data_string_text_for_logical_check
        return super().analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map or {}, threshold, full_text,
            is_target_for_debug, logical_hard_limit=logical_hard_limit,
        )

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return 2

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """The short aliases of config.json, in place of the raw tags they stand for."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(path, encoding="utf-8") as handle:
            return dict(json.load(handle).get("default_tag_mappings") or {})

    # ----- Project Manager: ROM mode (a game ROM unpacks to asm text; the build writes a patched ROM) -----

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": rom_project.ROM_ROLE, "label": "Game ROM (Game Boy)"}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return rom_project.identify(path)

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "gb", "label": "Game Boy"}]

    def get_source_subfolder(self) -> Optional[str]:
        return rom_project.SOURCE_DIR

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        rom = sources.get(rom_project.ROM_ROLE)
        if not rom:
            return None
        return rom_project.unpack(rom, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "rom", "label": "Patched ROM", "platforms": ["gb"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
        if target_id != "rom":
            raise ValueError(f"Unknown build target: {target_id}")
        return rom_project.build(source_dir, translation_dir, output_dir, progress, is_cancelled)
