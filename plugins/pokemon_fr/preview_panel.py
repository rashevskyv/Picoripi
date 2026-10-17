"""The message-box preview of a Generation III project: the game's own font, read from the base ROM in a worker.

The widget and its worker are shared (plugins/common/text_window_panel.py). This module only says how a
Generation III project loads its font, charmap and window from its facts file.
"""
from __future__ import annotations

import json
from pathlib import Path

from plugins.common import text_window_panel as panel
from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import read_glyph_set, read_glyph_set_4bpp
from plugins.common.text_window_panel import SCALE  # noqa: F401 (tests read the scale here)
from plugins.pokemon_fr import rom_project, rom_text
from core.i18n import tr

FontContext = tw.FontContext


def load_context(rom_dir: Path) -> FontContext:
    """Read the font of the unpacked game. Blocking file reads: call it from the worker only."""
    meta = json.loads((rom_dir / rom_project.META_FILE.name).read_text(encoding="utf-8"))
    facts = json.loads((rom_text.FACTS_DIR / meta["facts"]).read_text(encoding="utf-8"))
    font = facts.get("font")
    if not font:
        raise ValueError(tr("The font of this game is not in its facts yet."))
    reader = read_glyph_set_4bpp if font.get("kind") == "gen3_4bpp" else read_glyph_set
    glyphs = reader(rom_dir / rom_project.BASE_ROM.name, font)
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts.get("charmap", rom_text.CHARMAP_FILE))
    return FontContext(glyphs, charmap, tw.Window.from_facts(font["window"]))


class MessageWindowPreview(panel.MessageWindowPreview):
    """The message box in the game's font, for the editor's preview column (GameRules.get_custom_preview_widget)."""

    rom_dir_name = rom_project.ROM_DIR
    context_loader = staticmethod(load_context)
