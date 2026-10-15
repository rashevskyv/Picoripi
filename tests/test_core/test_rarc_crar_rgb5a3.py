"""Two small format additions for Super Mario Galaxy: the Switch's little-endian RARC (``CRAR``) and Wii font sheets
in RGB5A3 (the button-icon and number fonts)."""
import random

from core.containers import yaz0
from core.containers.rarc_container import RarcContainer
from core.font_formats import bcfnt
from rarc_fixture import build_rarc


def test_a_crar_reads_and_repacks_like_a_rarc():
    files = {"message.bmg": b"M" * 40, "messageid.tbl": b"T" * 7}
    for little in (False, True):
        data = build_rarc(files, little=little)
        assert RarcContainer.can_handle(data) and RarcContainer.can_handle(yaz0.compress(data))
        archive = RarcContainer(data)
        assert sorted(archive.list_files()) == sorted(files)
        assert archive.read_file("messageid.tbl") == b"T" * 7
        archive.write_file("message.bmg", b"N" * 100)
        again = RarcContainer(archive.pack())
        assert again.read_file("message.bmg") == b"N" * 100 and again.read_file("messageid.tbl") == b"T" * 7
        assert archive.pack()[:4] == (b"CRAR" if little else b"RARC")


def test_an_rgb5a3_sheet_decodes_and_encodes_back_to_its_bytes():
    rng = random.Random(9)
    # opaque texels (top bit set, RGB555) and translucent ones (3-bit alpha 1-6, RGB444): the forms the codec writes
    words = [0x8000 | rng.getrandbits(15) if index % 2 else rng.randint(1, 6) << 12 | rng.getrandbits(12)
             for index in range(16 * 8)]
    raw = b"".join(word.to_bytes(2, "big") for word in words)
    image = bcfnt.gx_decode(raw, bcfnt.RVL_RGB5A3, 16, 8)
    assert image.size == (16, 8) and image.mode == "RGBA"
    assert bcfnt.gx_encode(image, bcfnt.RVL_RGB5A3) == raw
