"""The Wind Waker plugin: Wind Waker HD (Wii U) MSBT files, and the older Kruptar text dumps.

A Wind Waker HD project points at the files ``1_unpack.bat`` takes out of ``permanent_2d_UsEnglish.pack``
(``Message/*.msbt``, ``Font/*.bffnt``): every MSBT is one block, every message one string, its tags
readable (``tags.py``). Saving writes the whole MSBT with only the edited messages re-encoded; an
unedited file is written back byte for byte. Speakers, box types and conversations come from the
messages' own attributes (``messages.py``). A project of Kruptar ``.txt`` dumps opens as before.
"""
import math
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as uu
from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning

from . import messages
from .config import PROBLEM_DEFINITIONS
from .tag_logic import process_segment_tags_aggressively_zww
from .tag_manager import TagManager
from .tags import TAG_RE, describe, from_editor, to_editor

ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, "ZWW", without=("BROKEN_ICON_HYPHEN",))

_DIALOGUE_FILES = ("message", "message2", "message3", "message4")
_LABEL_MAX_CHARS = 40


def _plain(text: str) -> str:
    return TAG_RE.sub("", text)


class GameRules(BaseGameRules):
    """Zelda: The Wind Waker (HD on Wii U; Kruptar text dumps)."""

    problem_prefix = "ZWW"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    short_problem_names = {"EMPTY_ODD_SUBLINE_DISPLAY": "EmptyOddD"}

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None        # the file loaded or about to be saved
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}
        self._chains: Dict[int, Dict[int, str]] = {}

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: The Wind Waker"

    def get_file_formats(self) -> list:
        """MSBT files are binary; the Kruptar ``.txt`` dumps keep the default text formats."""
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[to_editor(tokens) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == to_editor(original):
                rebuilt.append(original)
            else:
                rebuilt.append(from_editor(str(text)))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            self._msbt = None
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"zelda_ww: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()
        self._chains.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        """``(file name, parsed MSBT)`` of a block; cached until the next project load."""
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = getattr(self.mw, "project_manager", None)
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            block = pm.project.blocks[project_idx]
            if str(block.source_file).lower().endswith(".msbt"):
                path = Path(pm.get_absolute_path(block.source_file))
                found = (path.name, Msbt(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_ww: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """File, label, attributes and English text of one message, or None outside an MSBT."""
        name, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        return {"file": name, "label": msbt.labels.get(index, ""), "text": to_editor(msbt.messages[index]),
                "attributes": messages.attributes(msbt.section(b"ATR1"), index),
                "dialogue": Path(name).stem in _DIALOGUE_FILES}

    # -- AI and story context ------------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        attributes = found["attributes"]
        if not found["dialogue"] or not attributes:
            return {"content_role": f"Interface text ({found['file']}, {found['label']})", "has_speaker": False}
        context: Dict[str, Any] = {"window_type": attributes["balloon"]}
        role = messages.NOT_SPEAKERS.get(attributes["character"])
        if role:
            context["content_role"] = role[0]
            context["has_speaker"] = False
            if role[1]:
                context["glossary_section"] = role[1]
        return context

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found or not found["attributes"]:
            return None
        return messages.speaker_name(found["attributes"]["character"])

    def is_placeholder_speaker(self, name: str) -> bool:
        return False  # speaker_name() gives English names (curated where the MSBP label is a working title)

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        result: Dict[str, Any] = {"resource": found["file"], "label": found["label"]}
        attributes = found["attributes"]
        if attributes:
            result["msg_group"] = attributes["balloon"]
            speaker = messages.speaker_name(attributes["character"])
            if speaker:
                result["candidate_actors"] = [speaker]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        where = f"Message {found['label']} in {found['file']}"
        attributes = found["attributes"]
        if attributes and attributes["next"]:
            where += f", continues with message {attributes['next']:05d}"
        return where

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Messages chained by NextNo are one conversation; the group is the chain's first message."""
        name, msbt = self._member(block_idx)
        if msbt is None or Path(name).stem not in _DIALOGUE_FILES:
            return None
        if block_idx not in self._chains:
            self._chains[block_idx] = conversation_roots(msbt)
        try:
            root = self._chains[block_idx].get(int(string_idx))
        except (TypeError, ValueError):
            return None
        return f"wwhd:{root}" if root else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Item names (inventory), dungeon and place names, figurine names: the game names them itself."""
        entries: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        def add(term: str, section: str, description: str, ref: str) -> None:
            term = " ".join(_plain(term).replace("", "").replace("", "").split())
            if term and term not in seen and len(term) <= _LABEL_MAX_CHARS:
                seen.add(term)
                entries.append({"term": term, "section": section, "description": description, "source_ref": ref})

        blocks = getattr(getattr(getattr(self.mw, "project_manager", None), "project", None), "blocks", None) or []
        for block_idx in range(len(blocks)):
            name, msbt = self._member(block_idx)
            if msbt is None:
                continue
            stem, atr1 = Path(name).stem, msbt.section(b"ATR1")
            for index, tokens in enumerate(msbt.messages):
                text, label = to_editor(tokens), msbt.labels.get(index, "")
                ref = f"{name} {label}"
                if stem == "PlaceName_00":
                    add(text, "Places", "Place name shown when Link arrives", ref)
                elif stem == "DungeonMap_00" and label.startswith("T_DungeonName"):
                    add(text, "Places", "Dungeon name on the dungeon map", ref)
                elif stem in _DIALOGUE_FILES:
                    character = (messages.attributes(atr1, index) or {}).get("character")
                    if character == "ItemName":
                        add(text, "Items", "Item name in the inventory", ref)
                    elif character == "Figurine":
                        add(text.split("\n", 1)[0], "Characters", "Nintendo Gallery figurine", ref)
        return entries

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed", "external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        """Return a Zelda Wiki search or reference URL for ``term``."""
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Dialogue: the box width of the message's BalloonType and 4 lines a page.

        Interface labels (one line, no box) may grow to 1.3x / 1.6x their English width.
        """
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        attributes = found["attributes"]
        if found["dialogue"] and attributes:
            width = messages.box_width(attributes["balloon"])
            return {"warn_width": width, "max_width": width, "lines_per_page": messages.LINES_PER_PAGE}
        text = found["text"]
        font_map = getattr(self.mw, "font_map", None) if self.mw else None
        if "\n" in text or not font_map or len(_plain(text)) > _LABEL_MAX_CHARS:
            return None
        width = self.calculate_string_width_override(text, font_map) or 0
        if width <= 0:
            return None
        return {"warn_width": math.ceil(width * 1.3), "max_width": math.ceil(width * 1.6)}

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def get_dynamic_name_tags(self) -> dict:
        return {"[Name]": "Link"}

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zww(
            segment_to_insert=cleaned_segment,
            original_text_for_tags=original_text_for_tags,
            editor_player_tag_const=editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        return uu.calculate_string_width(text, font_map, default_char_width, icon_sequences=icon_sequences)

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
        return 1


def conversation_roots(msbt: Msbt) -> Dict[int, str]:
    """``{message index: label of the first message of its NextNo chain}``, for chains of two or more."""
    atr1 = msbt.section(b"ATR1")
    by_label = {label: index for index, label in msbt.labels.items()}
    following: Dict[int, int] = {}
    for index in range(len(msbt.messages)):
        attributes = messages.attributes(atr1, index)
        target = by_label.get(f"{attributes['next']:05d}") if attributes and attributes["next"] else None
        if target is not None and target != index:
            following[index] = target
    has_parent = set(following.values())
    roots: Dict[int, str] = {}
    for start in following:
        if start in has_parent:
            continue
        index, seen = start, set()
        while index is not None and index not in seen:
            seen.add(index)
            roots.setdefault(index, msbt.labels.get(start, str(start)))
            index = following.get(index)
    return roots
