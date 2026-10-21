"""Portrait colours from a sprite sheet: frame matching, majority vote, screen colours, colour file. Synthetic data only."""
import importlib.util
import json
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.lunar_sssc import portrait_colours as pc

REPO = Path(__file__).resolve().parents[3]


def _frame(shift=0):
    """A 64x64 index array: a border of 0 and five bands of indices 1..5."""
    indices = np.zeros((64, 64), np.uint8)
    indices[4:60, 4:60] = (np.arange(56)[None, :] + shift) // 13 % 5 + 1
    return indices


def _sheet_colour(value):
    """Sheet colour of an index: 5-bit channels times 8, as the sprite sheet stores them."""
    return (8 * value * 5, 8 * (31 - value * 4), 8 * value * 3)


def _sheet_with(frame, x, y, height=120, width=150):
    sheet = np.zeros((height, width, 4), np.uint8)
    cell = sheet[y:y + 64, x:x + 64]
    for value in range(1, 6):
        cell[frame == value, :3] = _sheet_colour(value)
    cell[frame > 0, 3] = 255
    return sheet


def _member(frames, ids=(0x6A, 0x6B, 0x6C, 0x6D, 0x6E)):
    """A TIZ member: 32-byte header with the ID bytes, then raw deflate of the five frames."""
    header = bytearray(32)
    header[0:4] = b"FACE"
    header[0x10:0x10 + len(ids)] = bytes(ids)
    body = b"".join(bytes(f.ravel()) for f in frames)
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    return bytes(header) + packer.compress(body) + packer.flush()


def test_best_cell_finds_the_cell_of_the_frame():
    frame = _frame()
    sheet = _sheet_with(frame, 10, 20)
    cell = pc.SheetIndex(sheet).best_cell(frame)
    assert cell is not None
    assert (cell.x, cell.y) == (10, 20)
    assert cell.consistency == 1.0
    assert cell.mask == 1.0


def test_best_cell_refuses_a_cell_whose_colours_do_not_follow_the_indices():
    frame = _frame()
    sheet = _sheet_with(frame, 10, 20)
    rng = np.random.default_rng(0)
    cell = sheet[20:84, 10:74]
    for y in range(64):
        for x in range(64):
            if frame[y, x]:
                cell[y, x, :3] = rng.integers(0, 256, 3)
    assert pc.SheetIndex(sheet).best_cell(frame) is None


def test_vote_keeps_the_colour_when_the_ripper_altered_a_few_pixels():
    frame = _frame(0)
    sheet = _sheet_with(frame, 10, 20)
    sheet[20 + 30, 10 + 30, :3] = (255, 0, 255)      # one edited pixel
    files = {"FACE_T.TIZ": _member([frame] * 5)}
    matches = pc.match_file(files, pc.SheetIndex(sheet))
    assert set(matches["FACE_T.TIZ"]) == {0, 1, 2, 3, 4}
    colours = pc.vote(files, sheet, matches)["FACE_T.TIZ"]
    assert colours[1] == pc.screen_rgb(_sheet_colour(1))
    assert colours[5] == pc.screen_rgb(_sheet_colour(5))


def test_screen_rgb_widens_5_bit_channels_like_the_console():
    assert pc.screen_rgb((201, 201, 201)) == (206, 206, 206)      # 25 -> (25 << 3) | (25 >> 2)
    assert pc.screen_rgb((153, 128, 96)) == (156, 132, 99)
    assert pc.screen_rgb((0, 8, 248)) == (0, 8, 255)


def test_frames_of_inflates_the_five_frames():
    frames = [_frame(n) for n in range(5)]
    decoded = pc.frames_of(_member(frames))
    assert len(decoded) == 5
    for got, want in zip(decoded, frames):
        assert np.array_equal(got, want)


def test_colour_file_round_trips_and_is_written_atomically(tmp_path):
    path = tmp_path / pc.COLOURS_FILE
    assert pc.read_colours(path) == {}
    colours = {"FACE_001.TIZ": {1: (0, 0, 0), 2: (206, 206, 206)}}
    pc.write_colours(path, colours)
    assert pc.read_colours(path) == colours
    assert json.loads(path.read_text(encoding="utf-8")) == {"FACE_001.TIZ": {"1": "#000000", "2": "#cecece"}}
    assert [p.name for p in tmp_path.iterdir()] == [pc.COLOURS_FILE]


def test_face_picture_uses_the_colour_table_and_falls_back_to_the_palette():
    frames = [_frame(n) for n in range(5)]
    member = _member(frames)
    files = {"FACE_T.TIZ": member}
    index = dp.index_faces(files)
    palette = [(v, v, v) for v in range(256)]
    colours = {"FACE_T.TIZ": {1: (10, 20, 30)}}
    picture = dp.face_picture(files, index, 0x6A, palette, colours)
    assert picture.getpixel((4, 4)) == (10, 20, 30, 255)     # index 1 from the table
    assert picture.getpixel((4 + 13, 4)) == (2, 2, 2, 255)   # index 2 from the palette
    assert picture.getpixel((0, 0)) == (0, 0, 0, 0)          # index 0 stays transparent


def test_script_writes_the_colour_table_to_the_given_file(tmp_path):
    source = tmp_path / "LUNADATA"
    source.mkdir()
    frames = [_frame(n) for n in range(5)]
    (source / "FACE_T.TIZ").write_bytes(_member(frames))
    sheet_path = tmp_path / "sheet.png"
    Image.fromarray(np.concatenate([_sheet_with(frames[0], 10, 20), _sheet_with(frames[1], 80, 20)], axis=1)).save(sheet_path)
    output = tmp_path / "out" / "face_palettes.json"
    spec = importlib.util.spec_from_file_location("lunar_portrait_colours", REPO / "scripts" / "lunar_portrait_colours.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.main([str(source), str(sheet_path), str(output)]) == 0
    written = pc.read_colours(output)
    assert written["FACE_T.TIZ"][1] == pc.screen_rgb(_sheet_colour(1))


def test_the_shipped_table_has_the_expected_shape():
    table = dp.load_colour_table(REPO / "plugins" / "lunar_sssc" / "face_palettes.json")
    assert table
    for name, colours in table.items():
        assert name.startswith("FACE_") and name.endswith(".TIZ")
        assert all(0 < value < 256 for value in colours)
        assert all(len(rgb) == 3 and all(0 <= c <= 255 for c in rgb) for rgb in colours.values())


def test_the_plugin_table_is_the_default_and_a_project_table_overrides_it(monkeypatch):
    frames = [_frame(0)] * 5
    files = {"FACE_T.TIZ": _member(frames)}
    index = dp.index_faces(files)
    palette = [(v, v, v) for v in range(256)]
    monkeypatch.setattr(dp, "FACE_COLOURS", {"FACE_T.TIZ": {1: (9, 9, 9), 2: (8, 8, 8)}})
    default = dp.face_picture(files, index, 0x6A, palette)
    assert default.getpixel((4, 4)) == (9, 9, 9, 255)
    assert default.getpixel((4 + 13, 4)) == (8, 8, 8, 255)
    override = dp.face_picture(files, index, 0x6A, palette, {"FACE_T.TIZ": {1: (1, 2, 3)}})
    assert override.getpixel((4, 4)) == (1, 2, 3, 255)        # the project's colour wins
    assert override.getpixel((4 + 13, 4)) == (8, 8, 8, 255)   # the plugin's colour stays for the other index
    assert override.getpixel((4 + 26, 4))[:3] == (3, 3, 3)    # neither table: the palette
