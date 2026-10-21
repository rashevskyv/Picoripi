"""The game's own picture: the 3DS SMDH icon and the GameCube banner decoded from synthetic bytes, and the new project's icon.png."""
import struct

from PyQt6.QtGui import QImage

from core.project_library import game_icon
from core.project_library.scan import ICON_FILE_NAME
from ui.project_manager import tasks
from ui.project_manager.tasks import UnpackJob


def _smdh(color565: int, corner565: int) -> bytes:
    """An SMDH block whose large icon is one colour, except the top-left pixel (Morton index 0 of tile 0)."""
    data = bytearray(game_icon.SMDH_LARGE_ICON_AT + 48 * 48 * 2)
    data[:4] = game_icon.SMDH_MAGIC
    for index in range(48 * 48):
        struct.pack_into("<H", data, game_icon.SMDH_LARGE_ICON_AT + index * 2, color565)
    struct.pack_into("<H", data, game_icon.SMDH_LARGE_ICON_AT, corner565)
    return bytes(data)


def _banner(value: int, last: int) -> bytes:
    """A BNR1 banner whose picture is one RGB5A3 value, except the bottom-right pixel."""
    data = bytearray(0x1960)
    data[:4] = b"BNR1"
    for index in range(96 * 32):
        struct.pack_into(">H", data, game_icon.BANNER_PICTURE_AT + index * 2, value)
    struct.pack_into(">H", data, game_icon.BANNER_PICTURE_AT + (96 * 32 - 1) * 2, last)
    return bytes(data)


def test_the_smdh_icon_is_48_pixels_with_its_tile_order(qtbot):
    image = game_icon.smdh_icon(_smdh(0x001F, 0xF800))   # blue, red corner
    assert (image.width(), image.height()) == (48, 48)
    assert image.pixel(0, 0) == 0xFFFF0000
    assert image.pixel(47, 47) == 0xFF0000FF


def test_the_banner_is_96_by_32_with_its_tile_order(qtbot):
    image = game_icon.banner_picture(_banner(0xFC00, 0x83E0))   # opaque red, green last pixel
    assert (image.width(), image.height()) == (96, 32)
    assert image.pixel(0, 0) == 0xFFFF0000
    assert image.pixel(95, 31) == 0xFF00FF00


def test_other_bytes_and_files_give_no_picture(qtbot, tmp_path):
    assert game_icon.smdh_icon(b"nope") is None
    assert game_icon.banner_picture(b"BNR1") is None
    plain = tmp_path / "notes.txt"
    plain.write_text("text", encoding="utf-8")
    assert game_icon.icon_png(str(plain)) is None
    assert game_icon.icon_png(str(tmp_path)) is None


def test_a_new_project_keeps_the_game_picture_and_never_replaces_one(qtbot, tmp_path, monkeypatch):
    png = bytes(game_icon._png(game_icon.smdh_icon(_smdh(0x07E0, 0x07E0))))
    monkeypatch.setattr(tasks.game_icon, "icon_png", lambda path: png if path == "game.3ds" else None)
    project = tmp_path / "Aria"
    project.mkdir()
    job = UnpackJob("fake", {"base": "game.3ds"}, str(project), lambda name: None)

    job._store_game_icon()

    assert not QImage(str(project / ICON_FILE_NAME)).isNull()
    (project / ICON_FILE_NAME).write_bytes(b"mine")
    job._store_game_icon()
    assert (project / ICON_FILE_NAME).read_bytes() == b"mine"
