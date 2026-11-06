"""The plugin's fonts: per game font one sheet of whole Latin glyphs and one file of Ukrainian letters (ua_*.bin, the
port's glyph data), 8x8 and 8x16 fonts apart (the cells name their tiles, so a tall glyph is its top tile over its
bottom tile)."""
import json
from collections import defaultdict
from pathlib import Path

from core import font_formats

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "super_metroid" / "font_sources.json"
FULL = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ’"     # every Ukrainian capital and the apostrophe


def _fonts():
    return json.loads(PLUGIN.read_text(encoding="utf-8"))


def _font(label):
    return next(d for d in _fonts() if d["label"] == label)


def _cells(descriptor):
    return dict(zip(descriptor["params"]["chars"], descriptor["params"]["tiles"]))


def test_every_font_is_a_list_of_cells_of_one_height():
    fonts = _fonts()
    labels = [d["label"] for d in fonts]
    assert len(labels) == len(set(labels)) == 17
    assert not [a for a in labels for b in labels if a != b and b.startswith(a)]     # a label is never another's prefix
    for d in fonts:
        params = d["params"]
        assert d["format"] == "texture_grid" and len(params["chars"]) == len(params["tiles"]), d["label"]
        tall = params["cell"] == [8, 16]
        assert all(isinstance(t, list) and len(t) == 2 for t in params["tiles"]) if tall else \
            all(isinstance(t, int) for t in params["tiles"]), d["label"]


def test_a_ukrainian_cell_shares_no_tile_with_any_other_cell_of_its_file():
    users = defaultdict(list)
    for d in _fonts():
        for ch, tile in zip(d["params"]["chars"], d["params"]["tiles"]):
            for t in tile if isinstance(tile, list) else [tile]:
                users[(d["path"], t)].append((d["label"], ch))
    for d in _fonts():
        if "Ukrainian" not in d["label"]:
            continue
        for ch, tile in _cells(d).items():
            for t in tile if isinstance(tile, list) else [tile]:
                assert users[(d["path"], t)] == [(d["label"], ch)], (d["label"], ch, users[(d["path"], t)])


def test_every_ukrainian_sheet_is_a_file_of_its_own_with_every_letter_and_the_apostrophe():
    ua = [d for d in _fonts() if "Ukrainian" in d["label"]]
    assert sorted(d["path"] for d in ua) == sorted(f"gfx/ua_{n}.bin" for n in (
        "bg3", "menu", "menu_big", "pause", "story", "prologue", "credits", "credits_big"))
    for d in ua:
        tall = d["params"]["cell"] == [8, 16]
        assert "".join(d["params"]["chars"]) == FULL, d["label"]
        assert d["params"]["tiles"] == ([[2 * k, 2 * k + 1] for k in range(34)] if tall else list(range(34)))
        assert d["params"]["texture_params"]["height"] == (40 if tall else 24)       # 80 or 48 tiles, rows of 16


def test_the_big_menu_letters_are_whole_glyphs_the_way_the_game_draws_them():
    big = _cells(_font("File select, game over and options: big letters (8x16)"))
    assert big["G"] == [0x0C, 0x30]       # the game's G: the top of the C over its own bottom
    assert big["9"] == [0x08, 0x19]       # the top of the 8 (tile 9 is empty)
    assert big["O"] == [0x00, 0x10] and big["P"] == [0x0D, 0x38]
    ua = _cells(_font("File select, game over and options: Ukrainian big letters (8x16)"))
    assert ua["Б"] == [2, 3] and ua["Я"] == [64, 65] and ua["О"] == [36, 37]


def test_an_edited_ukrainian_cell_changes_only_its_own_tiles():
    small = _font("File select, game over and options: Ukrainian small letters (8x8)")
    params = small["params"]
    data = bytes((i * 7 + 3) % 256 for i in range(params["texture_params"]["height"] * 128 // 2))
    meta, (sheet,) = font_formats.extract("texture_grid", data, params)
    cell = params["chars"].index("О")
    x, y = cell % 16 * 8, cell // 16 * 8
    sheet = sheet.copy()
    sheet.putpixel((x, y), (255, 255, 255, 255) if sheet.getpixel((x, y))[3] == 0 else (0, 0, 0, 0))
    out = font_formats.pack("texture_grid", meta, [sheet], data, params)
    tile = params["tiles"][cell]
    changed = {i // 32 for i in range(len(data)) if out[i] != data[i]}
    assert changed == {tile}
