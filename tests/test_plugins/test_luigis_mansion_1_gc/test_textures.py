"""Textures window: the plugin names the English text textures of the unpacked game; an edited one reaches the build."""
import struct
from types import SimpleNamespace

from PIL import Image

from core.texture_formats import pixels
from core.texture_formats import sources as texture_sources
from plugins.luigis_mansion_1_gc import build
from plugins.luigis_mansion_1_gc.rules import GameRules


def _bti(colour) -> bytes:
    """An 8x4 RGB5A3 BTI."""
    image = Image.new("RGBA", (8, 4), colour)
    head = struct.pack(">BBHHBBBBHI", 5, 0, image.width, image.height, 0, 0, 0, 0, 0, 0) + bytes(8)
    head += bytes([1, 0, 0, 0]) + struct.pack(">I", 0x20)
    return head + pixels.codec("gx:RGB5A3").encode(image)


def _write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_the_english_text_textures_are_listed_and_an_edited_one_is_built(tmp_path):
    source, translation = tmp_path / "unpacked", tmp_path / "translation"
    english = ["files/Kawano/ENGLISH/res_save.szp/timg/e_save_message_1_1a.bti",
               "files/Game/game_usa.szp/kawano/roomname/e_living.bti",
               "files/Game/game_usa.szp/kawano/base/timg/gbf_title.bti",
               "files/Ending/English/end_msE.bti"]
    others = ["files/Kawano/res_save.szp/timg/tx_datatitle_1a.bti",        # the Japanese copy
              "files/Game/game.szp/kawano/roomname/e_living.bti",           # the Japanese game archive
              "files/Kawano/ENGLISH/res_save.szp/timg/cursorb1.bti"]       # a picture with no text
    for rel in english + others:
        _write(source, rel, _bti((40, 40, 40, 255)))

    metadata = {"source_path": str(source), "translation_path": str(translation), "is_directory_mode": True}
    # As in the app: the rules see the open project, so the list keeps only the entries its folder has.
    main_window = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(metadata=metadata)))
    descriptors = GameRules(main_window).get_texture_sources()
    assert all(isinstance(d["path"], list) or d["path"] == "sys/main.dol" for d in descriptors)
    found = texture_sources.resolve(descriptors, metadata)
    assert sorted(s.key for s in found) == sorted(rel for rel in english)

    room = next(s for s in found if s.key.endswith("e_living.bti"))
    assert room.write(Image.new("RGBA", (8, 4), (255, 255, 255, 255)))
    assert list(build.changed_files(source, translation)) == ["files/Game/game_usa.szp/kawano/roomname/e_living.bti"]
