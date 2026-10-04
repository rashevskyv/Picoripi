"""Hyrule Warriors: Age of Calamity plugin: the LinkData text tables of the Switch romfs, one bundle per file."""
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from .aoctext import FormatError, TextBundle
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import PLACEHOLDER_RE, TAG_RE, describe, to_editor

# Battle dialogue and radio tables: u32 string, f32 seconds on screen, u8 speaker, u8, u16 per row.
_DIALOGUE_LABELS = ("radio_allies", "radio_warnings", "radio_link")
_SPEAKER_AT, _SECONDS_AT = 8, 4
# Speaker id -> row of the names table (text/*_names.bin). Only ids whose lines were read and match the
# character: 2-13 are the same row; the fairies (14-17), 1, 20, 21 and the soldier/NPC ids are not tied.
_SPEAKER_NAME_ROW = {**{i: i for i in range(2, 14)}, 18: 15, 19: 16, 22: 21, 40: 40}
_SUBTITLE_ROWS_PER_SCENE = 35  # subtitles: rows come in blocks of 35 per cutscene (from the empty rows)
# Cutscene k is titled by row k + 1 of the memories table (text/*_memories.bin; matched by reading
# scenes 0-4, 9, 13 and 14 against their titles).
_NAME_FORM_RE = re.compile(r"\[es:[0-9_]+\]([^\[]*)")

_ROLES = {
    "subtitles": ("Cutscene subtitle", "A subtitle line of a story cutscene."),
    "battle": ("Battle dialogue", "A line a character says over the radio during a battle, shown with a portrait."),
    "radio_allies": ("Battle dialogue", "A radio line during a battle, shown with a portrait."),
    "radio_warnings": ("Battle dialogue", "A radio line during a battle, shown with a portrait."),
    "radio_link": ("Battle dialogue", "A radio line during a battle, shown with a portrait."),
    "names": ("Name forms", "The forms of one name: [cs]form[cm]form[ce]; each form starts with its grammar "
                            "code [es:N_N_N]. Translate the words, keep the tags and codes."),
    "unit_names": ("Name forms", "The forms of one name: [cs]form[cm]form[ce]; each form starts with its "
                                 "grammar code [es:N_N_N]. Translate the words, keep the tags and codes."),
    "places": ("Place name", "A place name; it starts with its grammar code [es:N_N_N]."),
    "stages": ("Battle name", "The name or description of a battle (stage) on the map."),
    "quests": ("Quest", "A side quest name, description or reward text."),
    "tips": ("Tutorial", "A tip or tutorial page."),
    "tutorials": ("Tutorial", "A tip or tutorial page."),
    "staff_credits": ("Staff credits", "A line of the staff credits."),
}
_GLOSSARY = {
    "names": "Characters", "unit_names": "Characters", "places": "Places", "regions": "Places",
    "stables": "Places", "weapons": "Items", "key_items": "Items", "materials": "Items", "meals": "Items",
    "armor_body": "Items", "armor_legs": "Items", "armor_head": "Items", "sheikah_runes": "Items",
}


def _label(rel: str) -> str:
    """``text/07257_radio_allies.bin`` -> ``radio_allies``; ``battle/battle_007.bin`` -> ``battle``."""
    name = Path(rel).stem
    return "battle" if rel.replace("\\", "/").startswith("battle/") else name.split("_", 1)[-1]


def plain_name(text: str) -> str:
    """The first form of a name cell: ``[cs][es:1_1_1]Link[cm]...`` -> ``Link``."""
    text = to_editor(text)
    m = _NAME_FORM_RE.search(text)
    return (m.group(1) if m else TAG_RE.sub("", text)).strip()


class GameRules(BaseGameRules):
    """Zelda: Hyrule Warriors Age of Calamity (Switch).

    A project points at the workspace ``source`` folder made by ``1_unpack.bat``: ``text/*.bin`` and
    ``battle/*.bin`` are AOCT bundles cut out of ``data/LinkData2.bin`` (12 or 13 languages each). The
    English table is shown as one block; saving writes the bundle with the English (and EN2) table
    replaced, and ``2_build.bat`` packs the changed bundles back into LinkData2/LinkInfo2.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[TextBundle] = None
        self._located: Dict[int, Optional[Tuple[str, TextBundle]]] = {}
        self._names: Optional[List[str]] = None
        self._scene_titles: Optional[List[str]] = None
        self._widest: Dict[int, int] = {}

    def get_display_name(self) -> str:
        return "Zelda: Hyrule Warriors Age of Calamity"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Age of Calamity text bundles"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        try:
            bundle = TextBundle(bytes(json_obj))
        except (FormatError, ValueError, UnicodeDecodeError) as error:
            log_debug(f"zelda_aoc: not a text bundle ({error})")
            self._file = None
            return [[]], {}
        self._file = bundle
        return [bundle.texts()], {"0": "Battle dialogue" if bundle.is_battle_dialogue else "Text"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        return self._file.build((data or [[]])[0])

    def prepare_save_context(self, context) -> None:
        """The bundle is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._file = TextBundle(raw)
                return
            except (FormatError, ValueError) as error:
                log_debug(f"zelda_aoc: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()
        self._names = None
        self._scene_titles = None
        self._widest.clear()

    # -- where a block comes from ---------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _locate(self, block_idx: int) -> Optional[Tuple[str, TextBundle]]:
        """``(relative path, parsed source bundle)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm, project = self._project()
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = project.blocks[block_map.get(block_idx, block_idx)]
            path = Path(pm.get_absolute_path(block.source_file))
            found = (str(block.source_file).replace("\\", "/"), TextBundle(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_aoc: no text bundle behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _cell(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        rel, bundle = located
        try:
            row, column = bundle.cells[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None
        return rel, bundle, row, column

    @staticmethod
    def _is_dialogue(rel: str, bundle: TextBundle) -> bool:
        return (bundle.is_battle_dialogue or _label(rel) in _DIALOGUE_LABELS) and bundle.table.row_size == 12

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Row and column of the string; speaker id and seconds of a dialogue line; subtitle scene."""
        found = self._cell(block_idx, string_idx)
        if not found:
            return None
        rel, bundle, row, column = found
        attributes: Dict[str, Any] = {"file": rel, "row": row, "column": column, "languages": len(bundle.slots)}
        if len(bundle.table.columns) > 1:
            attributes["field"] = bundle.table.columns.index(column)
        if self._is_dialogue(rel, bundle):
            attributes.update(speaker_id=bundle.table.value(row, _SPEAKER_AT, "B"),
                              seconds=round(bundle.table.value(row, _SECONDS_AT, "f"), 2))
        if _label(rel) == "subtitles":
            attributes["scene"] = row // _SUBTITLE_ROWS_PER_SCENE
        return attributes

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._cell(block_idx, string_idx)
        if not found:
            return {}
        rel, bundle, _row, column = found
        label = _label(rel)
        role, instruction = _ROLES.get(label, ("Text", ""))
        if not instruction and len(bundle.table.columns) == 2:
            role, instruction = (("Name", "The name of an item or entry.") if column == bundle.table.columns[0]
                                 else ("Description", "The description shown under an item or entry."))
        context: Dict[str, Any] = {"content_role": role}
        if instruction:
            context["role_instruction"] = instruction
        if label in _GLOSSARY and column == bundle.table.columns[0]:
            context["glossary_section"] = _GLOSSARY[label]
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._cell(block_idx, string_idx)
        if not found:
            return {}
        rel, _bundle, row, _column = found
        context = {"resource": rel, "label": _label(rel)}
        if context["label"] == "subtitles":
            scene = context["scene"] = row // _SUBTITLE_ROWS_PER_SCENE
            titles = self._table_column("_memories.bin", "_scene_titles")
            if scene + 1 < len(titles) and titles[scene + 1]:
                context["scene_title"] = titles[scene + 1]
        return context

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        if not context:
            return None
        scene = f", cutscene {context['scene']}" if "scene" in context else ""
        title = f" \"{context['scene_title']}\"" if "scene_title" in context else ""
        return f"File {context['resource']}{scene}{title}"

    def _table_column(self, suffix: str, cache: str) -> List[str]:
        """English first column of the project's ``text/*<suffix>`` table, by row (cached in ``cache``)."""
        if getattr(self, cache) is not None:
            return getattr(self, cache)
        values: List[str] = []
        try:
            pm, project = self._project()
            for block in project.blocks:
                rel = str(block.source_file).replace("\\", "/")
                if rel.startswith("text/") and rel.endswith(suffix):
                    bundle = TextBundle(Path(pm.get_absolute_path(block.source_file)).read_bytes())
                    column = bundle.table.columns[0]
                    values = [plain_name(bundle.table.text(r, column)) for r in range(bundle.table.rows)]
                    break
        except (AttributeError, OSError, IndexError, TypeError, ValueError) as error:
            log_debug(f"zelda_aoc: no {suffix} table: {error}")
        setattr(self, cache, values)
        return values

    def _names_table(self) -> List[str]:
        """English first forms of the names table (``text/*_names.bin``), by row."""
        return self._table_column("_names.bin", "_names")

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Battle dialogue and radio lines: the speaker id of the row, named from the names table."""
        found = self._cell(block_idx, string_idx)
        if not found or not self._is_dialogue(found[0], found[1]):
            return None
        _rel, bundle, row, _column = found
        speaker = bundle.table.value(row, _SPEAKER_AT, "B")
        if not speaker:
            return None
        names = self._names_table()
        name_row = _SPEAKER_NAME_ROW.get(speaker)
        if name_row is not None and name_row < len(names) and names[name_row]:
            return names[name_row]
        return f"chara_{speaker:03d}"

    def is_placeholder_speaker(self, name: str) -> bool:
        """Speaker ids that are not tied to a name yet."""
        return str(name).startswith("chara_")

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Names, places and items from the game's own tables (English, first form)."""
        entries, seen = [], set()
        try:
            pm, project = self._project()
            blocks = list(project.blocks)
        except (AttributeError, TypeError):
            return []
        for block in blocks:
            rel = str(block.source_file).replace("\\", "/")
            section = _GLOSSARY.get(_label(rel))
            if not section or not rel.startswith("text/"):
                continue
            try:
                bundle = TextBundle(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            except (OSError, FormatError, ValueError) as error:
                log_debug(f"zelda_aoc: no glossary terms from {rel}: {error}")
                continue
            column = bundle.table.columns[0]
            for row in range(bundle.table.rows):
                term = plain_name(bundle.table.text(row, column))
                if not term or term in seen or term in ("0", "???") or "%" in term or len(term) > 48:
                    continue
                seen.add(term)
                entries.append({"term": term, "section": section,
                                "description": f"Age of Calamity {_label(rel).replace('_', ' ')} table",
                                "source_ref": f"{rel} row {row}"})
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Width limit of a table: its widest English line (the text is wrapped by hand)."""
        located = self._locate(block_idx)
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if not located or not font_map:
            return None
        if block_idx not in self._widest:
            lines = (line for text in located[1].texts() for line in text.split("\n"))
            self._widest[block_idx] = max((self._width(line, font_map) for line in lines), default=0)
        widest = self._widest[block_idx]
        if widest <= 0:
            return None
        return {"warn_width": widest, "max_width": round(widest * 1.05)}

    @staticmethod
    def _width(text: str, font_map: dict, default_char_width: int = 20) -> int:
        text = PLACEHOLDER_RE.sub("", TAG_RE.sub("", text))
        total = 0
        for ch in text:
            entry = font_map.get(ch)
            total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
        return total

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 20) -> Optional[int]:
        return self._width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(str(tag))

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
