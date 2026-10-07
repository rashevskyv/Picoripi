"""Zelda: A Link to the Past (SNES) through its PC port snesrev/zelda3: the port's ``dialogue.txt``.

``1_unpack.bat`` runs the port's own extractor (``assets/restool.py``): ``source/dialogue.txt`` holds the
397 messages as ``N: text`` lines, control codes as named tags (``[Name]``, ``[Waitkey]``, ``[Color 02]``).
The editor shows a line break before ``[2]``, ``[3]`` and ``[Scroll]`` (the codes that start the next
line); a break typed without one gets the code of its position. Letters the font lacks are saved as the
glyph of ``translation_map.json`` (the project's, else this plugin's). ``2_build.bat`` compiles the
translation into the port's ``zelda3_assets.dat``.

Context comes from the port's C code (``port_context.py`` -> ``context.json``): the sprite that shows a
message (speaker), the function and source line (scene, link), so lines of one NPC are translated together.
"""
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from plugins.base_game_rules import BaseGameRules
from plugins.common.z64_rules import Zelda64Rules
from utils.utils import clean_spaces

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_LINE_RE = re.compile(r"^(\d+): (.*)$")
_BREAK_BEFORE = re.compile(r"(?<=.)(?=\[(?:2|3|Scroll)\])")
_LINE_TAG = re.compile(r"\[(?:1|2|3|Scroll)\]")
_NEXT_LINE = {"[1]": "[2]", "[2]": "[3]", "[3]": "[Scroll]", "[Scroll]": "[Scroll]"}
# Cyrillic letters drawn with the Latin glyph they look like: they load back as that Latin letter.
LOOKALIKES = frozenset("АВСЕНІКМОРТХаеіорсух’")
MAX_LINE_WIDTH = 176     # widest retail line (174 px with a 6-letter name) in font pixels
LINES_PER_WINDOW = 3


def parse_dialogue(text: str) -> List[str]:
    """Message texts of a port ``dialogue.txt``, in order (line ``N`` is message ``N - 1``)."""
    messages = []
    for number, line in enumerate(text.splitlines(), 1):
        match = _LINE_RE.match(line)
        if not match or int(match.group(1)) != number:
            raise ValueError(f"dialogue.txt line {number}: expected '{number}: text', got {line[:40]!r}")
        messages.append(match.group(2))
    return messages


def render_dialogue(messages: List[str]) -> str:
    return "".join(f"{number}: {text}\n" for number, text in enumerate(messages, 1))


def to_editor(message: str) -> str:
    """A line break before each code that starts a new line."""
    return _BREAK_BEFORE.sub("\n", message)


def from_editor(text: str) -> str:
    """Line breaks back to codes: dropped before a line code, else the code after the last one ([2], [3], [Scroll])."""
    out, last = [], "[1]"
    for index, part in enumerate(text.split("\n")):
        if index and not _LINE_TAG.match(part):
            last = _NEXT_LINE[last]
            out.append(last)
        last = (_LINE_TAG.findall(part) or [last])[-1]
        out.append(part)
    return "".join(out)


def swap_letters(text: str, mapping: Dict[str, str]) -> str:
    """Characters outside ``[tags]`` replaced by ``mapping``."""
    if not mapping:
        return text
    parts = re.split(r"(\[[^\]]*\])", text)
    return "".join(part if part.startswith("[") else "".join(mapping.get(ch, ch) for ch in part) for part in parts)


class GameRules(BaseGameRules):
    """Zelda: A Link to the Past (SNES), PC port snesrev/zelda3."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True
    game_name = "Zelda: A Link to the Past (PC port)"
    data_dir = os.path.dirname(os.path.abspath(__file__))

    # translation_map.json (the project's, else the plugin's) and context.json, read as the N64 Zelda plugins do.
    translation_map = Zelda64Rules.translation_map
    _context = Zelda64Rules._context

    def get_display_name(self) -> str:
        return self.game_name

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".txt",), "text", "zelda3 dialogue.txt")]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"} if self._context().get("messages") else set()

    # -- loading and saving ---------------------------------------------------------------

    def _reverse_map(self) -> Dict[str, str]:
        """Glyph -> letter for the letters that take a glyph of their own (look-alikes stay Latin)."""
        return {glyph: letter for letter, glyph in self.translation_map().items() if letter not in LOOKALIKES}

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        reverse = self._reverse_map()
        messages = [to_editor(swap_letters(text, reverse)) for text in parse_dialogue(json_obj)]
        return [messages], {"0": "Dialogue"}

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        mapping = self.translation_map()
        return render_dialogue([swap_letters(from_editor(str(text)), mapping) for text in (data[0] if data else [])])

    # -- context from the port's code ------------------------------------------------------

    def _message(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if block_idx != 0:
            return {}
        return self._context().get("messages", {}).get(str(int(string_idx)), {})

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The one sprite whose code shows the message; None when several or none do."""
        speakers = self._message(block_idx, string_idx).get("speakers") or []
        return speakers[0] if len(speakers) == 1 else None

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        role = self._message(block_idx, string_idx).get("role")
        if role == "ItemGet":
            return {"content_role": "ItemGet", "has_speaker": False, "glossary_section": "Items",
                    "role_instruction": 'ITEM MESSAGES: "content_role": "ItemGet" is the box shown when Link '
                                        "receives an item; the item name must match the glossary."}
        if role in ("Menu", "Narration"):
            return {"content_role": role, "has_speaker": False}
        return {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The source line that shows the message, its functions and the sprites they belong to."""
        entry = self._message(block_idx, string_idx)
        result: Dict[str, Any] = {}
        if entry.get("refs"):
            result["resource"] = entry["refs"][0]
            result["flow_ids"] = list(entry.get("functions", []))
        if entry.get("speakers"):
            result["candidate_actors"] = list(entry["speakers"])
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        entry = self._message(block_idx, string_idx)
        if not entry.get("refs"):
            return None
        shown = ", ".join(f"{f} ({r})" for f, r in zip(entry.get("functions", []), entry["refs"]))
        return f"Shown by {shown} in the zelda3 PC port source."

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Messages one function shows are one conversation."""
        functions = self._message(block_idx, string_idx).get("functions") or []
        return functions[0] if len(functions) == 1 else None

    # -- width and editing ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"max_width": MAX_LINE_WIDTH, "warn_width": MAX_LINE_WIDTH, "lines_per_page": LINES_PER_WINDOW}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return width_utils.calculate_string_width(text, font_map or {}, default_char_width=default_char_width)

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool,
                        editor_font_map: Optional[Dict] = None, editor_line_width_threshold: Optional[int] = None,
                        full_data_string_text_for_logical_check: Optional[str] = None,
                        is_target_for_debug: bool = False, logical_hard_limit: Optional[int] = None) -> Set[str]:
        threshold = editor_line_width_threshold or MAX_LINE_WIDTH
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
        return LINES_PER_WINDOW
