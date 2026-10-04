"""Vagrant Story (PlayStation, USA) plugin: events, rooms, menus, items, help pages."""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import codec, formats, russian
from . import doc as docs
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN_DIR = Path(__file__).resolve().parent
FONT_FILE = "FONT/VSFONT.FNT"
INDEX_FILE = "vs_index.json"
CELL = 12                      # a balloon is chars_per_line * 12 pixels of text wide
ITALIC = 0xBD                  # the italic glyphs follow the 189 regular ones
DEFAULT_WIDTHS = [6] * (2 * ITALIC)
_TITLES = {"Duke", "Lord", "Sir"}

_ROLES = {
    docs.DIALOG: ("Spoken dialogue", "A line said in a speech balloon of a cutscene or a room event. Keep it "
                                     "natural speech; the balloon has a fixed width and number of lines."),
    docs.ITEM_NAME: ("Item name", "Name of a weapon part, armour, gem, key or consumable. At most 23 bytes."),
    docs.ITEM_HELP: ("Item description", "One or two short lines describing an item in the menu."),
    docs.MONSTER: ("Monster name", "Name of a creature in the bestiary (Monster Book)."),
    docs.MONSTER_HELP: ("Monster description", "Bestiary entry describing a creature."),
    docs.ROOM_NAME: ("Room name", "Name of a room shown on the map and when entering it."),
    docs.HELP: ("Help page text", "Text of the in-game manual (Quick Manual)."),
    docs.MENU: ("Menu text", "Menu label, option help or system message."),
    docs.NAME: ("Name in game data", "A name stored in the game's program or zone data (spell, art, ability, "
                                     "enemy, equipment). It is edited in place: never longer than the English."),
    docs.HUD: ("HUD word", "A short capitalised label drawn with the HUD sheet's letters (body part, timing result, "
                           "menu header). ASCII only and never longer than the English; keep a leading # or $."),
}


class GameRules(BaseGameRules):
    """Vagrant Story (PlayStation, USA, SLUS-01040).

    The project's source folder is the ``source`` folder the workspace's unpack step fills with the
    disc's text files under their disc paths (``EVENT/*.EVT``, ``MAP/*.MPD``, ``MAP/*.ZND``,
    ``MENU/*``, ``SMALL/*``, ``BATTLE/*.PRG``, ``TITLE/TITLE.PRG``, ``SLUS_010.40``) and the font
    ``FONT/VSFONT.FNT``. Saving writes the same files into the translation folder; the build step
    puts them back on the disc.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._known: Dict[str, List[Tuple[int, int, int]]] = {}
        self._save_source: Optional[bytes] = None
        self._save_name = ""
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, docs.Doc, int]]] = {}
        self._parsed: Dict[str, docs.Doc] = {}
        self._widest: Dict[Tuple[int, int], int] = {}
        self._widths: Optional[List[int]] = None
        self._italic = False
        self._index: Optional[Dict[str, Any]] = None
        self._map_path: Optional[str] = None
        self._map_mtime = 0.0
        self.translation_map: Dict[str, str] = {}
        self.char_codes: Dict[str, int] = {}
        self.reverse_codes: Dict[int, str] = {}
        self.reader = codec.Reader()

    def get_display_name(self) -> str:
        return "Vagrant Story"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        extensions = (".evt", ".mpd", ".znd", ".bin", ".prg", ".hf0", ".arm", ".40")
        return [FileFormat(extensions, "bytes", "Vagrant Story data"), *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the plugin's: Ukrainian letter -> font cell."""
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None) if self.mw else None
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(_PLUGIN_DIR / "translation_map.json")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        if path == self._map_path and mtime == self._map_mtime:
            return
        self._map_path, self._map_mtime = path, mtime
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_warning(f"vagrant_story: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if len(k) == 1 and len(v) == 1 and v in codec.CODES}
        self.char_codes = {k: codec.CODES[v] for k, v in self.translation_map.items()}
        self.reverse_codes = {}
        lookalike = {}
        for letter, code in self.char_codes.items():     # a letter on a cell of its own reads back as itself
            if not letter.isalpha():
                continue
            if codec.CHARS.get(code, "").isascii():
                lookalike.setdefault(codec.CHARS[code], letter)
            else:
                self.reverse_codes.setdefault(code, letter)
        self.reader = codec.Reader(self.reverse_codes, lookalike)

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            parsed = docs.parse(data, known=self._known)
        except (formats.FormatError, ValueError, IndexError, KeyError) as error:
            log_debug(f"vagrant_story: not a Vagrant Story text file ({error})")
            return [[]], {}
        docs.remember(data, parsed, self._known)
        self.load_translation_map()
        texts = parsed.texts(self.reader)
        return (texts or [[]]), parsed.names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_name = str(getattr(context, "relative_path", "") or "")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        missing: Set[str] = set()
        parsed = docs.parse(source, known=self._known)
        name = self._save_name.replace("\\", "/") or "file"
        out = docs.build(source, parsed, data or [], self.char_codes, missing, stem=name, reader=self.reader)
        if missing:
            log_warning(f"vagrant_story: characters the font has no glyph for were written as '?': "
                        f"{''.join(sorted(missing))}")
        return out

    def export_runtime_state(self) -> Any:
        return {"known": {key: [list(region) for region in regions] for key, regions in self._known.items()}}

    def restore_runtime_state(self, state: Any) -> None:
        if isinstance(state, dict) and isinstance(state.get("known"), dict):
            self._known = {str(key): [tuple(int(v) for v in region) for region in regions]
                           for key, regions in state["known"].items()}

    def reset_runtime_state(self) -> None:
        self._known.clear()
        self._located.clear()
        self._parsed.clear()
        self._widest.clear()
        self._widths = None
        self._index = None
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _source_root(self) -> Optional[Path]:
        pm, project = self._project()
        for block in getattr(project, "blocks", []) or []:
            rel = str(block.source_file).replace("\\", "/")
            try:
                absolute = Path(pm.get_absolute_path(block.source_file))
            except (AttributeError, TypeError, ValueError):
                return None
            parts = len(Path(rel).parts)
            return absolute.parents[parts - 1] if parts else absolute
        return None

    def _locate(self, block_idx: int) -> Optional[Tuple[str, docs.Doc, int]]:
        """``(relative path, parsed source file, group inside the file)``, cached."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm, project = self._project()
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = project.blocks[project_idx]
            rel = str(block.source_file).replace("\\", "/")
            if rel not in self._parsed:
                data = Path(pm.get_absolute_path(block.source_file)).read_bytes()
                self._parsed[rel] = docs.parse(data, rel, known=self._known)
            found = (rel, self._parsed[rel], sub)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"vagrant_story: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _line(self, block_idx: int, string_idx: int) -> Optional[Tuple[str, docs.Doc, int, docs.Line]]:
        located = self._locate(block_idx)
        if not located:
            return None
        rel, parsed, sub = located
        try:
            return rel, parsed, sub, parsed.groups[sub].lines[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None

    def _scene_index(self) -> Dict[str, Any]:
        """``vs_index.json`` the unpack step writes: room file -> area and room name."""
        if self._index is None:
            self._index = {}
            root = self._source_root()
            if root is not None and (root / INDEX_FILE).is_file():
                try:
                    self._index = json.loads((root / INDEX_FILE).read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    log_warning(f"vagrant_story: cannot read {INDEX_FILE}: {error}")
        return self._index

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._line(block_idx, string_idx)
        if not found:
            return None
        rel, _parsed, _sub, line = found
        attributes: Dict[str, Any] = {"file": rel, "kind": line.kind, "where": line.where}
        if line.box is not None:
            attributes.update(chars_per_line=line.box.chars_per_line, box_lines=line.box.line_count)
        if line.room:
            attributes["bytes_available"] = line.room - 1
        return attributes

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if not found:
            return {}
        role, instruction = _ROLES.get(found[3].kind, ("", ""))
        return {"content_role": role, "role_instruction": instruction} if role else {}

    def _place(self, rel: str) -> str:
        entry = self._scene_index().get("rooms", {}).get(rel) or {}
        return " -- ".join(part for part in (entry.get("area"), entry.get("room")) if part)

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._line(block_idx, string_idx)
        if not found:
            return {}
        rel, parsed, sub, line = found
        context: Dict[str, Any] = {"resource": rel, "label": parsed.groups[sub].name, "where": line.where}
        place = self._place(rel)
        if place:
            context["location_candidates"] = [place]
        return context

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        return f"{found[0]}#{found[2]}" if found else None

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._line(block_idx, string_idx)
        if not found:
            return None
        rel, parsed, sub, line = found
        role = _ROLES.get(line.kind, ("Text", ""))[0]
        place = self._place(rel)
        label = f"{Path(rel).stem} ({place})" if place else Path(rel).stem
        if line.kind == docs.DIALOG and parsed.kind == "event":
            label = f"cutscene {label}"
        return f"{role} -- {label}"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Names the game data lists: items, monsters, rooms and areas, spells and arts, and the
        characters of ``characters.json`` that the dialogue really names."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        def add(term: str, section: str, description: str, ref: str) -> None:
            term = codec.TAG_RE.sub("", term).strip()
            if term and term not in seen and term.lower() not in ("untitled", "nothing", "unknown", "dummy"):
                seen.add(term)
                entries.append({"term": term, "section": section, "description": description, "source_ref": ref})

        dialog = []
        for rel, parsed in self._iter_project_docs():
            for group in parsed.groups:
                for line in group.lines:
                    text = codec.decode(line.raw)
                    if line.kind == docs.DIALOG:
                        dialog.append(text)
                    elif line.kind == docs.ITEM_NAME:
                        add(text, "Items", "Item, weapon part or armour", rel)
                    elif line.kind == docs.MONSTER:
                        add(text, "Monsters", "Creature of the Monster Book", rel)
                    elif line.kind == docs.ROOM_NAME:
                        add(text, "Places", "Room name", rel)
                    elif line.kind == docs.NAME and rel.startswith("SLUS"):
                        add(text.split("{")[0], "Spells and arts", "Spell, Break Art, Battle Ability or effect", rel)
        joined = "\n".join(dialog)
        try:
            people = json.loads((_PLUGIN_DIR / "characters.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            people = {}
        words = set(re.findall(r"[^\W\d_]+", joined))
        for name, note in people.items():       # offered when the dialogue uses one of its names
            if not name.startswith("_") and any(part in words for part in name.split() if part not in _TITLES):
                add(name, "Characters", str(note), "dialogue")
        return entries

    def _iter_project_docs(self):
        pm, project = self._project()
        for block in getattr(project, "blocks", []) or []:
            rel = str(block.source_file).replace("\\", "/")
            try:
                if rel not in self._parsed:
                    data = Path(pm.get_absolute_path(block.source_file)).read_bytes()
                    self._parsed[rel] = docs.parse(data, rel, known=self._known)
                yield rel, self._parsed[rel]
            except (OSError, ValueError, AttributeError, TypeError) as error:
                log_debug(f"vagrant_story: cannot read {rel} for the glossary seed: {error}")

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- reference: the Russian fan translation ----------------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (Reborn 1.5f)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        """(block, line) -> Russian text, from the Russian disc's files under ``patch_path`` (the same
        disc paths as the project's source; the workspace's unpack step puts them in ``reference/RU``)."""
        result: Dict[Tuple[int, int], str] = {}
        root = Path(patch_path)
        pm, project = self._project()
        block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
        blocks = sorted(block_map) if block_map else range(len(getattr(project, "blocks", []) or []))
        cache: Dict[str, Optional[bytes]] = {}
        for block_idx in blocks:
            located = self._locate(block_idx)
            if not located:
                continue
            rel, parsed, sub = located
            if rel not in cache:
                path = root / rel
                cache[rel] = path.read_bytes() if path.is_file() else None
            ru = cache[rel]
            if ru is None:
                continue
            for index, raw in enumerate(_reference_strings(ru, parsed, sub)):
                if raw:
                    result[(block_idx, index)] = russian.decode(raw)
        return result

    # -- editor ----------------------------------------------------------------

    def _font_widths(self) -> List[int]:
        """Advances of the 378 glyphs, from the project's font file (the translation copy first)."""
        if self._widths is None:
            self._widths = list(DEFAULT_WIDTHS)
            pm, _project = self._project()
            root = self._source_root()
            candidates = []
            try:
                candidates.append(Path(pm.get_absolute_path(FONT_FILE, is_translation=True)))
            except (AttributeError, TypeError, ValueError):
                pass
            if root is not None:
                candidates.append(root / FONT_FILE)
            for path in candidates:
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                if data[:4] == b"VSFN":
                    from core.font_formats.vagrant import HEADER, TEXTURE, WIDTHS
                    self._widths = list(data[HEADER + TEXTURE:HEADER + TEXTURE + WIDTHS])
                    break
        return self._widths

    def _width(self, text: str, italic: bool) -> int:
        widths = self._font_widths()
        raw = codec.encode(text, self.char_codes)
        if italic:
            raw = bytes((0xFB, 5)) + raw
        return max(codec.line_widths(raw, widths) or [0])

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Width limit of one string. A dialog line: its balloon (``chars_per_line`` x 12 pixels of
        the italic font, ``line_count`` lines). Anything else: the widest English line of its group,
        in the regular font.
        """
        found = self._line(block_idx, string_idx)
        if not found:
            return None
        _rel, parsed, sub, line = found
        self.load_translation_map()
        self._italic = line.kind == docs.DIALOG
        if line.box is not None:
            width = line.box.chars_per_line * CELL
            return {"warn_width": width, "max_width": width, "lines_per_page": max(1, line.box.line_count)}
        key = (block_idx, sub)
        if key not in self._widest:
            texts = [codec.decode(other.raw) for other in parsed.groups[sub].lines]
            self._widest[key] = max((self._width(part, self._italic) for text in texts for part in text.split("\n")),
                                    default=0)
        widest = self._widest[key]
        return {"warn_width": widest, "max_width": widest} if widest > 0 else None

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        # The last get_string_layout said which font the line is drawn with: dialog balloons use the
        # italic set. ponytail: per-call state; pass the font with the text if the host ever allows it.
        self.load_translation_map()
        return self._width(text, self._italic)

    def get_spellcheck_ignore_pattern(self) -> str:
        return codec.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        tips = {"{page}": "New page", "{wait}": "Continuation arrow: waits for a button", "{Lv}": "The glyph 'Lv.'",
                "{center}": "Centre the lines", "{italic}": "Italic font", "{regular}": "Regular font"}
        if tag in tips:
            return tips[tag]
        if tag.startswith("{>") or tag.startswith("{<"):
            return "Move the pen right/left by that many pixels"
        if tag.startswith("{down"):
            return "Move the text down by that many pixels"
        if tag.startswith("{color"):
            return "Text colour"
        if tag.startswith(("{num", "{hex", "{str")):
            return "A value the game prints here"
        if tag.startswith(("{speed", "{sfx")):
            return "Text speed / sound while printing"
        return "Raw byte of the game text" if tag.startswith("{x") else ""

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _reference_strings(ru: bytes, parsed: docs.Doc, sub: int) -> List[Optional[bytes]]:
    """The Russian strings of one group, line by line (None where the file differs)."""
    group = parsed.groups[sub]
    table = None
    if group.table is not None:
        if group.script is not None:
            start = 0
            if parsed.kind != "event":
                sections = formats.mpd_header(ru)
                start = sections[2][0] if sections and sections[2][1] else -1
            if 0 <= start and start + 4 <= len(ru):
                # the dialog table where the header says; a few Russian tables run past their region
                text = int.from_bytes(ru[start + 2:start + 4], "little")
                table = formats.read_table(ru, start + text, len(ru), min_letters=0)
        elif parsed.kind == "help":
            table = formats.help_table(ru)
        else:
            table = formats.read_table(ru, group.table.start, len(ru), count_in_front=group.table.refs != group.table.base,
                                       min_letters=0)
        if table is None or table.count != group.table.count:
            return [None] * len(group.lines)
        return [table.string_at(ru, line.place)[:-1] for line in group.lines]
    out: List[Optional[bytes]] = []
    for line in group.lines:                 # in place: the Russian string sits where the English one is
        if line.kind == docs.HUD:            # the Russian HUD words are Latin letters redrawn as Cyrillic
            out.append(None)
            continue
        end = codec.string_end(ru, line.place)
        out.append(ru[line.place:end - 1] if end - line.place <= line.room else None)
    return out
