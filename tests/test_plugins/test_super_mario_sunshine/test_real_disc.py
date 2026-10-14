"""The owner's Super Mario Sunshine disc (read only), when ``PICORIPI_SMS_DISC`` names it (a plain ISO or a WIA or RVZ).

The tests read the disc through ``core.containers.wia.open_disc``, so an RVZ is read as its disc. They check the
facts measured on the real disc: the header, the retail executable, the message files and the system font.
"""
import hashlib
import os
from pathlib import Path

import pytest

from core.bfn_core import BfnCore
from core.containers import ContainerManager
from core.containers import yaz0
from core.containers.gcm import GameCubeImage
from core.containers.image_files import ImageError
from core.containers.rarc_container import RarcContainer
from core.containers.wia import open_disc
from core.project_library import images
from plugins.zelda_bmg import bmg_tool
from plugins.super_mario_sunshine import dol_patch
from plugins.super_mario_sunshine.dol_text import DolText
from plugins.super_mario_sunshine.rules import GameRules
from tools.bfn_editor.bfn_engine import read_bfn_model, write_bfn_model

DISC_ENV = "PICORIPI_SMS_DISC"
RETAIL_DOL_SHA256 = "13934c863d649b1ddca1ca4d7748f49d28a571685cbee5fb1542545c32869955"


def _disc_path():
    value = os.environ.get(DISC_ENV, "").strip()
    return Path(value) if value and Path(value).is_file() else None


pytestmark = pytest.mark.skipif(_disc_path() is None, reason=f"{DISC_ENV} does not name a Super Mario Sunshine image")


@pytest.fixture
def disc_path():
    return _disc_path()


def test_real_disc_is_gmse01_rev0(disc_path):
    assert images.identify(disc_path) == {"kind": "gc", "game_id": "GMSE01", "encrypted": False, "revision": 0}
    assert GameRules().identify_source(str(disc_path)) == {"role": "base", "platform": "gc"}


def test_real_main_dol_is_the_retail_executable_and_takes_the_patch(disc_path):
    with open_disc(disc_path) as stream:
        image = GameCubeImage(stream)
        dol = image.read(next(e for e in image.entries() if e.path == "sys/main.dol"))
    assert hashlib.sha256(dol).hexdigest() == RETAIL_DOL_SHA256
    assert DolText.can_handle(dol)
    DolText(dol)                       # every string room matches its digest
    patched = dol_patch.apply(dol)
    assert len(patched) == len(dol)
    assert dol_patch.revert(patched) == dol


def _archive_member(disc_path, archive, member):
    with open_disc(disc_path) as stream:
        image = GameCubeImage(stream)
        data = image.read(next(e for e in image.entries() if e.path == archive))
    return RarcContainer(yaz0.decompress(data) if data[:4] == b"Yaz0" else data).read_file(member)


@pytest.mark.parametrize("archive,member", [("files/data/nintendo.szs", "font/standard_fontex.bfn"),
                                            ("files/data/subtitle.szs", "font/demo_font.bfn")])
def test_the_editable_fonts_pack_back_byte_for_byte(disc_path, archive, member):
    font = _archive_member(disc_path, archive, member)
    assert write_bfn_model(*read_bfn_model(font)) == font


def test_no_english_message_uses_a_code_of_the_ukrainian_map(disc_path):
    codes = {ord(value) for value in GameRules().translation_map.values()}
    used = set()
    with open_disc(disc_path) as stream:
        image = GameCubeImage(stream)
        for entry in image.entries():
            if not entry.path.endswith(".szs"):
                continue
            data = image.read(entry)
            raw = yaz0.decompress(data) if data[:4] == b"Yaz0" else data
            if raw[:4] != b"RARC":
                continue
            container = RarcContainer(raw)
            for name in container.list_files():
                if name.lower().endswith(".bmg"):
                    tool = bmg_tool.BMGFile()
                    tool.load(container.read_file(name))
                    if tool.encoding == "cp1252":     # the four dolpic1.bmg are Shift-JIS Japanese
                        used |= {b for m in tool.messages for p in m.parts if isinstance(p, str) for b in p.encode("cp1252")}
    assert used and not used & codes


def test_intact_bmg_messages_round_trip_byte_for_byte(disc_path):
    differing, count = set(), 0
    with open_disc(disc_path) as stream:
        image = GameCubeImage(stream)
        for entry in image.entries():
            if not entry.path.endswith((".szs", ".arc")):
                continue
            try:
                data = image.read(entry)
            except ImageError:
                continue   # a damaged entry of a broken download
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
    # The count may only grow with a more complete image, and no message file may stop round-tripping.
    assert count >= 171
    assert differing == set()


def test_the_system_font_is_single_byte_with_a_lookup_from_0x20_to_0xff(disc_path):
    with open_disc(disc_path) as stream:
        image = GameCubeImage(stream)
        archive = image.read(next(e for e in image.entries() if e.path == "files/data/nintendo.szs"))
    font = BfnCore()
    font.load(RarcContainer(yaz0.decompress(archive)).read_file("font/standard_fontex.bfn"))
    assert font.inf1[0]["encoding"] == 0
    mapping = font.map1[0]
    assert (mapping["mapping_type"], mapping["first_char"], mapping["last_char"]) == (2, 32, 255)
    assert mapping["mapping_entry_count"] == 224
