"""The message-box preview of a Game Boy Pokemon project (Generations I and II): the game's font and box from the ROM.

The box is the game's two-row text box: 18 cells of text on rows 14 and 16, scrolled with ``cont``. The panel
and its worker are shared (plugins/common/text_window_panel.py). Generation II reuses this class with its own
facts folder (plugins/pokemon_gsc/preview_panel.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from plugins.common import gb_text_font
from plugins.common import text_window_panel as panel
from plugins.common import text_window_preview as tw
from plugins.pokemon_gen1 import rom_project

# The placeholders a line may carry: the alias of config.json and the raw tag it stands for, both drawn as the
# name the game prints, padded to the cells the game gives it (rules.CODE_CHARS).
_NAMES = {"Player": ("PLAYER", 7), "Rival": ("RIVAL", 7), "POKe": ("POKé", 4), "TM": ("TM", 2), "PC": ("PC", 2),
          "Trainer": ("TRAINER", 7), "Rocket": ("ROCKET", 6), "Target": ("TARGET", 10), "User": ("USER", 10)}
_RAW = {"Player": "<PLAYER>", "Rival": "<RIVAL>", "POKe": "#", "TM": "<TM>", "PC": "<PC>", "Trainer": "<TRAINER>",
        "Rocket": "<ROCKET>", "Target": "<TARGET>", "User": "<USER>"}
PLACEHOLDERS: Dict[str, str] = {}
for _alias, (_word, _cells) in _NAMES.items():
    PLACEHOLDERS["{%s}" % _alias] = _word.ljust(_cells)
    PLACEHOLDERS[_RAW[_alias]] = _word.ljust(_cells)


def make_loader(facts_dir: Path):
    """A loader for the projects of one facts folder: the font, the charmap and the box of the unpacked ROM."""
    def load(rom_dir: Path) -> tw.FontContext:
        return gb_text_font.load_gb_context(rom_dir, facts_dir, rom_project.BASE_ROM.name, rom_project.META_FILE.name)
    return load


class MessageWindowPreview(panel.MessageWindowPreview):
    """The Game Boy message box in the game's font, for the editor's preview column."""

    rom_dir_name = rom_project.ROM_DIR
    context_loader = staticmethod(make_loader(rom_project.FACTS_DIR))

    def paginate(self, ctx: tw.FontContext, text: str) -> List[List[tw.Line]]:
        byte_of = ctx.charmap.byte_of
        return tw.parse_gb_pages(text, byte_of.get, byte_of.get("?", 0), PLACEHOLDERS)
