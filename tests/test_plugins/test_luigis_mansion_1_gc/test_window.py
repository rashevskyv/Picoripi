"""The Luigi's Mansion message window: script speakers, the composed frame and the preview style."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from plugins.luigis_mansion_1_gc import window
from plugins.luigis_mansion_1_gc.rules import GameRules
from utils.width import calculate_string_width

SCRIPT = ("<WINDOW>(0)<COLOR>(3)\r\n<SPEAK>(0)\r\nコメント\r\n<COLOR>(1)<SPEAK>(1)<SPEAK>(0)\r\n"
          "<WINDOW>(2)<SPEAK>(4)\r\n")
DMMAN = "files/Game/game_usa.szp/kawano/dmman"


def _textures(root: Path) -> None:
    (root / DMMAN / "pressed").mkdir(parents=True)
    for name in ("m_window4.bti", "m_window5.bti", "pressed/luigi_icon.bti"):
        (root / DMMAN / name).write_bytes(name.encode())


def _read(path: Path) -> Image.Image:
    """Fake .bti decoder: the window is full grey ink 238; the icon is solid red."""
    if path.name.endswith("_icon.bti"):
        return Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    return Image.new("RGBA", window.WINDOW_SIZE, (238, 238, 238, 238))


def test_speakers_follow_the_last_window_and_colour_and_keep_the_first_speak():
    assert window.speakers(SCRIPT) == {0: (0, 3), 1: (0, 1), 4: (2, 1)}


def test_the_frame_is_tinted_and_fades_to_the_bottom(tmp_path):
    _textures(tmp_path)

    canvas = window.frame_image(0, 3, [tmp_path], _read)

    x, y = window.DEFAULT_PLACE
    assert canvas.size == window.SCREEN and canvas.getpixel((0, 0))[3] == 0
    top, bottom = canvas.getpixel((x + 200, y)), canvas.getpixel((x + 200, y + 119))
    assert top[:3] == (108 * 238 // 255, 225 * 238 // 255, 95 * 238 // 255) and abs(top[3] - 238) <= 2
    assert abs(bottom[3] - 238 * 32 / 255) <= 2
    assert canvas.getpixel((x + 18, y + 24)) == (255, 0, 0, 255)      # luigi_icon is COLOR(3)


def test_the_call_window_has_its_own_place_and_no_frame_without_textures(tmp_path):
    assert window.geometry(2)["box"] == [19, 353, 480, 120]
    assert window.frame_image(0, 1, [tmp_path], _read) is None


def test_the_text_box_starts_at_the_first_glyph_top_and_wraps_at_the_scissor():
    text = window.geometry(0)["text"]

    assert text[0] == 28 + 56 and abs(text[1] - (21 + 45 - 22 * 27 / 32)) < 1e-9
    assert int(text[2] * window.CELL / window.FONT_Y) == 502


def test_the_rules_read_the_event_script_next_to_the_table(tmp_path):
    archive = tmp_path / "files/Event/event08.szp"
    (archive / "message").mkdir(parents=True)
    (archive / "text").mkdir()
    (archive / "message/message8.csv").write_bytes(b"a\r\nb\r\n")
    (archive / "text/event08.txt").write_bytes(SCRIPT.encode("cp932"))
    _textures(tmp_path)
    project = SimpleNamespace(blocks=[SimpleNamespace(source_file="files/Event/event08.szp/message/message8.csv")],
                              metadata={"source_path": str(tmp_path)})
    pm = SimpleNamespace(project=project, get_absolute_path=lambda rel: str(tmp_path / rel))
    rules = GameRules(SimpleNamespace(project_manager=pm, block_to_project_file_map={}))

    style = rules.get_preview_window_style(0, 4)
    unknown = rules.get_preview_window_style(0, 9)

    assert "message_window_preview" in rules.get_capabilities()
    assert (style["window"], style["colour"], style["geometry"]["box"][:2]) == (2, 1, [19, 353])
    assert (unknown["window"], unknown["colour"], style["lines_per_page"]) == (0, 0, 2)


def test_ukrainian_letters_are_previewed_and_measured_in_their_font_cells():
    rules = GameRules(SimpleNamespace(project_manager=None, block_to_project_file_map={}))
    font_map = {"ы": {"width": 9}, "ё": {"width": 13}, "а": {"width": 12}}

    assert rules.prepare_preview_glyph_text("Ґанок і ї")[0] == "Ёанок ы ъ"
    assert rules.calculate_string_width_override("іа", font_map) == calculate_string_width("ыа", font_map) == 21
    assert rules.calculate_string_width_override("аа", font_map) is None    # nothing to map: the core measures it
