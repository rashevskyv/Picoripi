"""Hyrule Warriors: Definitive Edition plugin: the 12-language XL text tables of the Switch romfs."""
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import ktbin
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import PLACEHOLDER_RE, TAG_RE, describe
from .textfile import (SUBTITLE_SPEAKER_ROW, FormatError, TextFile, decode_cell, english_tables,
                       subtitle_speaker_rows, table_role)

# msgdata.bin, English section, table 6: unit and character names; row = character id of VoiceInf.
NAMES_TABLE = 6
# Character ids whose VoiceInf lines were checked against the names table (0-17 heroes, 100+ officers).
# 18-99 do not match the table (DLC heroes reuse those ids) and are returned as placeholders.
_UNVERIFIED_SPEAKER_IDS = range(18, 100)
_VOICE_FILES = ("VoiceMes.bin", "VoiceMesChange.bin")

_ROLE_INSTRUCTIONS = {
    "Place names (forms)": "One grammatical form of a place name. The game inserts it into sentences "
                           "through %Ns{form:N}; N is this column.",
    "Names (forms)": "One grammatical form of a unit or character name. The game inserts it into "
                     "sentences through %Ns{form:N}; N is this column.",
    "Subtitles": "A cutscene or narration subtitle, shown under the video.",
    "Voice lines": "A short voiced battle line spoken by a hero during combat.",
    "Voice lines (variants)": "A short voiced battle line spoken by a hero during combat.",
    "Messages": "A battle report or mission message shown during a battle.",
}


class GameRules(BaseGameRules):
    """Zelda: Hyrule Warriors Definitive Edition (Switch).

    A project points at a folder with the game's text files (``data/common/msgdata.bin``,
    ``data/battle/scenario/snstr*.bin``, the subtitle files...). Each file holds 12 languages; the
    English one is shown, one block per XL table. Saving writes the whole file back with the English
    (and English-EU) section replaced -- into a LayeredFS ``romfs`` when the translation folder is
    ``atmosphere/contents/<title id>/romfs``.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[TextFile] = None
        self._located: Dict[int, Optional[Tuple[str, TextFile, int]]] = {}
        self._parsed: Dict[str, TextFile] = {}   # absolute path -> the file, parsed once per load
        self._english: Dict[str, List[ktbin.XlTable]] = {}   # absolute path -> its English tables only
        self._speakers: Dict[str, List[Optional[str]]] = {}
        self._block_speakers: Dict[int, List[Optional[str]]] = {}
        self._widest: Dict[int, int] = {}

    def get_display_name(self) -> str:
        return "Zelda: Hyrule Warriors Definitive Edition"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Hyrule Warriors text tables"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        try:
            text_file = TextFile(bytes(json_obj))
        except (FormatError, ValueError) as error:
            log_debug(f"zelda_hwde: not a text file ({error})")
            self._file = None
            return [[]], {}
        self._file = text_file
        return (text_file.texts() or [[]]), text_file.names()

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        missing: set = set()
        out = self._file.build(data or [], missing)
        if missing:
            log_warning(f"zelda_hwde: characters outside the game's code page were written as '?': {''.join(missing)}")
        return out

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._file = TextFile(raw, verify=True)
                return
            except (FormatError, ValueError) as error:
                log_warning(f"zelda_hwde: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()
        self._parsed.clear()
        self._english.clear()
        self._speakers.clear()
        self._block_speakers.clear()
        self._widest.clear()

    # -- where a block comes from ---------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _text_file(self, path: Path) -> TextFile:
        """The parsed file at ``path``: one parse per load, shared by all its blocks."""
        key = str(path)
        if key not in self._parsed:
            self._parsed[key] = TextFile(path.read_bytes())
        return self._parsed[key]

    def _english_tables(self, path: Path) -> List[ktbin.XlTable]:
        """The English tables of the file at ``path`` (a twelfth of a full parse), cached per load."""
        key = str(path)
        if key not in self._english:
            self._english[key] = (self._parsed[key].tables if key in self._parsed
                                  else english_tables(path.read_bytes()))
        return self._english[key]

    def _source(self, block_idx: int) -> Tuple[str, Path, int]:
        """``(relative path, absolute path, block index inside the file)`` of a data block."""
        pm, project = self._project()
        block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
        project_idx = block_map.get(block_idx, block_idx)
        sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
        block = project.blocks[project_idx]
        return str(block.source_file).replace("\\", "/"), Path(pm.get_absolute_path(block.source_file)), sub

    def _locate(self, block_idx: int) -> Optional[Tuple[str, TextFile, int]]:
        """``(relative path, parsed source file, block index inside the file)``; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            rel, path, sub = self._source(block_idx)
            found = (rel, self._text_file(path), sub)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_hwde: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _cell(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        rel, text_file, sub = located
        try:
            table, row, column = text_file.cell(sub, int(string_idx))
        except (IndexError, TypeError, ValueError):
            return None
        return rel, text_file, sub, table, row, column

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Table, row and column of the string; the subtitle scene and timing; the voice row."""
        found = self._cell(block_idx, string_idx)
        if not found:
            return None
        rel, text_file, sub, table, row, column = found
        values = table.rows[row]
        attributes: Dict[str, Any] = {
            "file": rel, "table": text_file.blocks[sub].table, "row": row, "column": column,
            "role": table_role(table),
        }
        if len(table.string_columns) > 1:
            attributes["form"] = table.string_columns.index(column)
        if attributes["role"] == "Subtitles":
            attributes.update(scene=values[0], line=values[1], start=values[2], end=values[3],
                              speaker_label=values[4] == SUBTITLE_SPEAKER_ROW)
        elif table.types[:3] == [3, 3, 3]:
            attributes["flags"] = values[:3]
        return attributes

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._cell(block_idx, string_idx)
        if not found:
            return {}
        _rel, _file, _sub, table, row, column = found
        role = table_role(table)
        if role == "Subtitles" and table.rows[row][4] == SUBTITLE_SPEAKER_ROW:
            return {"content_role": "Speaker name", "glossary_section": "Characters",
                    "role_instruction": "The name of the character shown with a cutscene subtitle."}
        context: Dict[str, Any] = {"content_role": role}
        if role in _ROLE_INSTRUCTIONS:
            instruction = _ROLE_INSTRUCTIONS[role]
            if len(table.string_columns) > 1:
                instruction += f" This is form {table.string_columns.index(column)}."
            context["role_instruction"] = instruction
        if role in ("Place names (forms)", "Names (forms)"):
            context["glossary_section"] = "Places" if role.startswith("Place") else "Characters"
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._cell(block_idx, string_idx)
        if not found:
            return {}
        rel, text_file, sub, _table, _row, _column = found
        return {"resource": rel, "label": text_file.blocks[sub].name}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        if not context:
            return None
        return f"File {context['resource']}, table {context['label']}"

    def _speaker_names(self, voice_rel: str) -> List[Optional[str]]:
        """Speaker per VoiceMes row: VoiceInf.bin.gz (character id) -> msgdata names table."""
        folder = str(Path(voice_rel).parent)
        if folder in self._speakers:
            return self._speakers[folder]
        names: List[Optional[str]] = []
        try:
            pm, _project = self._project()
            base = Path(pm.get_absolute_path(voice_rel)).parent
            info = ktbin.parse_xl((base / "VoiceInf.bin.gz").read_bytes())
            table = self._english_tables(base / "msgdata.bin")[NAMES_TABLE]
            for row in info.rows:
                chara = row[0]
                if chara in _UNVERIFIED_SPEAKER_IDS:
                    names.append(f"chara_{chara:03d}")
                elif chara < 0 or chara >= len(table.rows):
                    names.append(None)
                else:
                    names.append(table.rows[chara][0].split(b"\0", 1)[0].decode("cp1252"))
        except (AttributeError, OSError, IndexError, TypeError, ValueError) as error:
            log_debug(f"zelda_hwde: no speaker data next to {voice_rel}: {error}")
        self._speakers[folder] = names
        return names

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Subtitles: the name row with the same timing. Voice lines: VoiceInf -> names table."""
        if block_idx not in self._block_speakers:
            self._block_speakers[block_idx] = self._speakers_of_block(block_idx)
        speakers = self._block_speakers[block_idx]
        return speakers[string_idx] if 0 <= string_idx < len(speakers) else None

    def _speakers_of_block(self, block_idx: int) -> List[Optional[str]]:
        """The speaker of every string of a block (empty when the table names nobody).

        Only subtitle tables and the voice files name speakers; a file with neither is told apart by
        its English tables alone, so opening a project does not parse every language of every file.
        """
        try:
            rel, path, _sub = self._source(block_idx)
            if (Path(rel).name not in _VOICE_FILES
                    and not any(table_role(t) == "Subtitles" for t in self._english_tables(path))):
                return []
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_hwde: no text file behind block {block_idx}: {error}")
            return []
        located = self._locate(block_idx)
        if not located:
            return []
        rel, text_file, sub = located
        block = text_file.blocks[sub]
        table = text_file.tables[block.table]
        by_timing = subtitle_speaker_rows(table)
        if by_timing:
            return [decode_cell(table.rows[by_timing[row]][5], False) or None if row in by_timing else None
                    for row, _column in block.cells]
        if Path(rel).name not in _VOICE_FILES:
            return []
        names = self._speaker_names(rel)
        return [names[row] if row < len(names) else None for row, _column in block.cells]

    def is_placeholder_speaker(self, name: str) -> bool:
        """Raw character ids, and the "???" the game shows before a character is revealed."""
        return str(name).startswith("chara_") or str(name) == "???"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Character and unit names from msgdata.bin's names table (form 0, English)."""
        try:
            pm, project = self._project()
            for block in project.blocks:
                if str(block.source_file).replace("\\", "/").endswith("common/msgdata.bin"):
                    table = self._english_tables(Path(pm.get_absolute_path(block.source_file)))[NAMES_TABLE]
                    break
            else:
                return []
        except (AttributeError, OSError, IndexError, TypeError, ValueError) as error:
            log_debug(f"zelda_hwde: no names table for the glossary seed: {error}")
            return []
        seen, entries = set(), []
        for row_idx, row in enumerate(table.rows):
            term = row[0].split(b"\0", 1)[0].decode("cp1252").strip()
            if not term or term in seen or "\x1b" in term:
                continue
            seen.add(term)
            entries.append({
                "term": term, "section": "Characters",
                "description": "Unit or character name (Hyrule Warriors DE names table)",
                "source_ref": f"msgdata.bin table {NAMES_TABLE} row {row_idx}",
            })
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed"}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Width limit of a table: its widest English line (the game wraps by hand, never by width)."""
        found = self._cell(block_idx, string_idx)
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if not found or not font_map:
            return None
        if block_idx not in self._widest:
            _rel, text_file, sub, _table, _row, _column = found
            lines = (line for text in text_file.texts()[sub] for line in text.split("\n"))
            self._widest[block_idx] = max((self._width(line, font_map) for line in lines), default=0)
        widest = self._widest[block_idx]
        if widest <= 0:
            return None
        return {"warn_width": widest, "max_width": round(widest * 1.05)}

    @staticmethod
    def _width(text: str, font_map: dict, default_char_width: int = 26) -> int:
        text = PLACEHOLDER_RE.sub("", TAG_RE.sub("", text))
        total = 0
        for ch in text:
            entry = font_map.get(ch)
            total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
        return total

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 26) -> Optional[int]:
        return self._width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

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
