r"""Paper Mario (N64) plugin: the message table of the US 1.0 ROM as text, one block per message.

The source is ``source\text\paper_mario_64_messages.txt`` (``1_unpack.bat``): one line per message,
``MSG_<name><TAB><text>``, in the order of the port's ``messages.yml``. The text is ``msg_codec``'s
editor form. ``2_build.bat`` writes the changed messages into the PC port's mod archive; the ROM itself
is never changed.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, PLUGIN_PREFIX)


class GameRules(BaseGameRules):
    """Paper Mario (N64): message text."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_manager_class = TagManager
    tag_style = "square"

    def get_display_name(self) -> str:
        return "Paper Mario (N64)"

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".txt",), "text", "Paper Mario messages")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        """One block per message: ``[text]``, named by the message id."""
        blocks: List[List[str]] = []
        names: Dict[str, str] = {}
        for line in str(json_obj or "").split("\n"):
            if not line.strip():
                continue
            name, _sep, text = line.partition("\t")
            if not _sep:
                name, text = f"MSG_{len(blocks):04d}", line
            names[str(len(blocks))] = name
            blocks.append([text])
        return blocks, names

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        names = block_names or {}
        lines = []
        for index, block in enumerate(blocks):
            name = names.get(str(index)) or f"MSG_{index:04d}"
            lines.append(f"{name}\t{block[0] if block else ''}")
        return "\n".join(lines) + "\n"
