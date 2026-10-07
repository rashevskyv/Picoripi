"""A Link Between Worlds plugin: the MSBT text of the 3DS game (EU English), its fonts and text images.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it). The game keeps its
files in Yaz0 SARC archives; the unpack writes each archive as a folder of its members, at the path a
LayeredFS mod replaces one member with (``2_build.bat`` repacks the archive around it):

- ``romfs/EU_English/<Archive>.szs/EU_English/<File>.msbt`` -- every message, one block per file. A file
  that several archives hold with the same bytes (``Field.msbt`` is in 7) is there once; the build writes
  its translation into each of them. Saving encodes again only the edited messages: an unedited file is
  written back byte for byte. Tags are named by the game's own message project (``tags.py``).
- ``romfs/EU/RegionBoot.szs/EU/Font/*.bffnt`` -- the fonts (``font_sources.json``).
- ``romfs/EU_English/Layout/*.bflim`` and ``romfs/Archive/Lyt_Menu.arc/timg/TitleLogo*.bflim`` -- the
  images with text (``texture_sources.json``).

Layout texts (``Gm_*``, ``Mn_*``, ``Cm_*``, ``Ed_*`` files) take the width and line count of their text box
from the message project's styles (``<file>_<label>``); dialogue lines keep to the widest English line.
A Tri Force Heroes plugin can subclass ``GameRules`` with its own ``msbp.json`` and JSON lists.
"""
import math
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import tags
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

LAYOUT_PREFIXES = ("Gm_", "Mn_", "Cm_", "Ed_")
FONT_FILE = "MessageFont.json"
DIALOGUE_WIDTH = 344    # widest retail English dialogue line in MessageFont advances (credits left out)
LAYOUT_SLACK = 1.1      # a layout text may run this much past its box before it is an error
PLAYER_NAME = "Link"
# Message files whose entries are names: (glossary section, description).
NAME_FILES = {"ItemName": ("Items", "Item name"), "NPCName": ("Characters", "Character name"),
              "LocationName": ("Places", "Place name"), "ExtraName": ("Characters", "Character name")}
ROLES = {"ItemName": "Item name (inserted into sentences, lower case)", "ItemNameUpper": "Item name (capitalised)",
         "NPCName": "Character name", "LocationName": "Place name", "LocationNameUpper": "Place name (capitalised)",
         "ExtraName": "Character name", "StaffCredit": "Staff credits", "System": "System message",
         "Action": "Action button label", "EventItemGet": "Item get message", "Collect": "Item description"}
_STYLES = {style["name"]: style for style in tags.PROJECT.get("styles", [])}
_LABEL_MAX_CHARS = 40


class GameRules(BaseGameRules):
    """The Legend of Zelda: A Link Between Worlds (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None        # the file loaded or about to be saved
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}

    def get_display_name(self) -> str:
        return "Zelda: A Link Between Worlds"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[tags.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == tags.to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(tags.from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        self._msbt = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"zelda_albw: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        """``(path relative to the source folder, parsed MSBT)`` of a block; cached until the next load."""
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".msbt"):
                found = (Path(source).as_posix(), Msbt(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_albw: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """File, archive, label and English text of one message, or None outside an MSBT."""
        rel_path, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        parts = Path(rel_path).parts
        archive = next((Path(part).stem for part in parts if part.lower().endswith(".szs")), "")
        stem = Path(rel_path).stem
        return {"path": rel_path, "file": Path(rel_path).name, "stem": stem, "archive": archive,
                "label": msbt.labels.get(index, ""), "text": tags.to_editor(msbt.messages[index], msbt.little),
                "layout": stem.startswith(LAYOUT_PREFIXES)}

    # -- AI and story context ------------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        if found["layout"]:
            return {"content_role": f"Interface text ({found['stem']}, {found['label']})", "has_speaker": False}
        role = ROLES.get(found["stem"])
        if role:
            context = {"content_role": role, "has_speaker": False}
            if found["stem"] in NAME_FILES:
                context["glossary_section"] = NAME_FILES[found["stem"]][0]
            return context
        return {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"resource": found["path"], "label": found["label"]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        return f"Message {found['label']} in {found['file']} ({found['archive']})"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Item, character and place names the game lists itself (ItemName, NPCName, LocationName...)."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        blocks = getattr(getattr(getattr(self.mw, "project_manager", None), "project", None), "blocks", None) or []
        for block_idx in range(len(blocks)):
            rel_path, msbt = self._member(block_idx)
            if msbt is None or Path(rel_path).stem not in NAME_FILES:
                continue
            section, description = NAME_FILES[Path(rel_path).stem]
            for index, tokens in enumerate(msbt.messages):
                term = " ".join(tags.TAG_RE.sub("", tags.to_editor(tokens, msbt.little)).split())
                if term and term not in seen and len(term) <= _LABEL_MAX_CHARS:
                    seen.add(term)
                    entries.append({"term": term, "section": section, "description": description,
                                    "source_ref": f"{Path(rel_path).name} {msbt.labels.get(index, '')}"})
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed", "external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Layout texts: their text box (message project style); dialogue: the widest English line, 3 lines a page."""
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        if found["layout"]:
            style = _STYLES.get(f"{found['stem']}_{found['label']}")
            if not style:
                return {"font_file": FONT_FILE}
            return {"warn_width": style["region_width"], "max_width": math.ceil(style["region_width"] * LAYOUT_SLACK),
                    "lines_per_page": max(1, style["lines"]), "font_file": FONT_FILE}
        return {"warn_width": DIALOGUE_WIDTH, "max_width": DIALOGUE_WIDTH, "lines_per_page": DEFAULT_LINES_PER_PAGE,
                "font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        """Widest line in font advances: ``{PlayerName}`` as "Link", a number as its digits, other tags nothing."""
        widest = 0
        for line in str(text).split("\n"):
            total = 0
            for match_or_char in _drawn(line):
                entry = (font_map or {}).get(match_or_char)
                total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
            widest = max(widest, total)
        return widest

    def get_tag_tooltip(self, tag: str) -> str:
        return tags.describe(str(tag))

    def get_dynamic_name_tags(self) -> dict:
        return {"{PlayerName}": PLAYER_NAME}

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _drawn(line: str) -> str:
    """The characters a line draws: the player's name and numbers in place of their tags, no other tags."""
    out, position = [], 0
    for match in tags.TAG_RE.finditer(line):
        out.append(line[position:match.start()])
        name, *args = match.group(0)[1:-1].split(":")
        if name == "PlayerName":
            out.append(PLAYER_NAME)
        elif name == "IntNumberN" and args and args[0].isdigit():
            out.append("0" * int(args[0]))
        position = match.end()
    out.append(line[position:])
    return "".join(out)
