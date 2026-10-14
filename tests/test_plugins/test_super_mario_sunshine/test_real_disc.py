"""The owner's Super Mario Sunshine disc (read only), when PICORIPI_ROMHACKING points at the workspace.

The disc on disk is a damaged download: its file table runs past the end of the file, and the bytes from 0x4F800000
on are an HTML page. The tests read only the intact part and check the facts measured on 2026-10-14.
"""
import romhacking_root
from core.containers import ContainerManager
from core.containers import yaz0
from core.containers.gcm import GameCubeImage
from core.containers.image_files import ImageError
from plugins.zelda_bmg import bmg_tool
from plugins.super_mario_sunshine import dol_patch
from plugins.super_mario_sunshine.rules import GameRules

DISC = ("_new", "Super Mario Sunshine (2002)(Nintendo)(US).iso")
# Message files whose INF1 is 8 bytes per entry; the BMG save path does not reproduce their INF1 (see build.py).
INF1_NOT_REPRODUCED = {
    "files/data/scene/pinnaBeach0.szs/map/dolpic1.bmg",
    "files/data/scene/pinnaBeach1.szs/map/dolpic1.bmg",
    "files/data/scene/pinnaBeach2.szs/map/dolpic1.bmg",
    "files/data/scene/pinnaBeach3.szs/map/dolpic1.bmg",
}


@romhacking_root.needs(DISC)
def test_real_disc_is_gmse01_rev0():
    assert GameRules().identify_source(str(romhacking_root.path(*DISC))) == {"role": "base", "platform": "gc"}


@romhacking_root.needs(DISC)
def test_real_main_dol_holds_the_four_retail_words_and_takes_the_patch():
    with open(romhacking_root.path(*DISC), "rb") as stream:
        image = GameCubeImage(stream)
        dol = image.read(next(e for e in image.entries() if e.path == "sys/main.dol"))
    patched = dol_patch.apply(dol)
    assert len(patched) == len(dol)
    assert dol_patch.revert(patched) == dol


@romhacking_root.needs(DISC)
def test_intact_bmg_messages_round_trip_except_the_known_shift_jis_files():
    differing, count = set(), 0
    with open(romhacking_root.path(*DISC), "rb") as stream:
        image = GameCubeImage(stream)
        for entry in image.entries():
            if not entry.path.endswith((".szs", ".arc")):
                continue
            try:
                data = image.read(entry)
            except ImageError:
                continue   # the damaged part of the download
            raw = yaz0.decompress(data) if data[:4] == b"Yaz0" else data
            container = ContainerManager.open(raw)
            if container is None:
                continue   # not an archive Picoripi reads (not RARC)
            for name in container.list_files():
                if not name.lower().endswith(".bmg"):
                    continue
                body = container.read_file(name)
                count += 1
                tool = bmg_tool.BMGFile()
                tool.load(body)
                if tool.save() != body:
                    differing.add(f"{entry.path}/{name}")
    assert count == 171
    assert differing == INF1_NOT_REPRODUCED
