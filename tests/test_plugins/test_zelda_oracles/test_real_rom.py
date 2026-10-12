"""The USA Oracle ROMs on this machine (skipped where they are missing): identity, text spans and the font.

No ROM bytes are stored in the repository. The test reads the ROM from the user's collection and
checks that rewriting every string with its own bytes leaves the ROM unchanged.
"""
from pathlib import Path

import pytest

from plugins.zelda_oracles import font, text
from plugins.zelda_oracles.rom import AGES_US, SEASONS_US, identify

ROMS = {
    "ages": Path(r"D:\Emulators\roms\roms\gbc\Legend of Zelda,The-Oracle of Ages.gbc"),
    "seasons": Path(r"D:\Emulators\roms\roms\gbc\Legend of Zelda,The-Oracle of Seasons.gbc"),
}


def _load(key):
    path = ROMS[key]
    if not path.is_file():
        pytest.skip(f"the USA {key} ROM is not on this machine")
    return path.read_bytes()


@pytest.mark.parametrize("key,layout", [("ages", AGES_US), ("seasons", SEASONS_US)])
def test_usa_rom_is_identified(key, layout):
    assert identify(_load(key)) is layout


@pytest.mark.parametrize("key", ["ages", "seasons"])
def test_every_string_decodes_and_rewrites_unchanged(key):
    raw = _load(key)
    layout = identify(raw)
    tables = text.TextTables(raw, layout)
    named = [span for span in tables.spans if not span.is_dictionary]
    assert len(named) > 1500
    assert sum(1 for span in tables.spans if span.terminated) > 0.9 * len(tables.spans)
    rom = bytearray(raw)
    for span in named:
        if span.terminated and tables.is_isolated(span):
            text.replace_text(rom, span, tables.raw(span))
    assert bytes(rom) == raw
    for span in tables.spans:
        tables.expand(span)


def test_font_glyph_cells_are_read_in_place():
    raw = _load("ages")
    cells = font.font_to_grid(font.font_slice(raw, AGES_US))
    assert len(cells) == font.IMAGE_HEIGHT
    assert font.grid_to_font(cells) == font.font_slice(raw, AGES_US)
