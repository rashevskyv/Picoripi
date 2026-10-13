"""Twin Snakes unpack: the disc roles, the text layout of one or two discs, and the real discs when present.

The synthetic discs are GameCube images built here (a file tree, a file system table, the header fields the
reader reads); the script and font samples come from ``samples``.
"""
import struct
import zlib

import pytest

import romhacking_root
from core.containers.image_files import ImageError
from plugins.mgs_ts import subtitles, unpack
from plugins.mgs_ts.rules import GameRules
from plugins.mgs_ts.stage_dat import StageDatContainer

from .samples import container, demo_container, font_file, gcx_file

GAME = b"GGSEA4"
ISO_DIR = ("Metal Gear", "Twin Snakes", "ISO")
TEXT = ("Metal Gear", "Twin Snakes", "source", "text")


def disc_file(number):
    return (*ISO_DIR, f"Metal Gear Solid - The Twin Snakes (USA) (Disc {number}).nkit.iso")


def _align(value, step):
    return (value + step - 1) // step * step


def gc_disc(tree, disc=0, game=GAME):
    """A GameCube image of the nested dict ``tree`` (name -> bytes, or name -> dict for a folder)."""
    entries, names, files = [None], bytearray(b"\0"), []

    def walk(node):
        for name, value in node.items():
            word = len(names)
            names.extend(name.encode() + b"\0")
            if isinstance(value, dict):
                index = len(entries)
                entries.append(None)
                walk(value)
                entries[index] = (0x01000000 | word, 0, len(entries))
            else:
                files.append((len(entries), word, value))
                entries.append(None)

    walk(tree)
    entries[0] = (0x01000000, 0, len(entries))
    fst_at, fst_size = 0x2600, 12 * len(entries) + len(names)
    body_at = _align(fst_at + fst_size, 0x100)
    body = bytearray()
    for index, word, value in files:
        entries[index] = (word, body_at + len(body), len(value))
        body += value
    image = bytearray(body_at + len(body))
    image[0:6] = game
    image[6] = disc
    struct.pack_into(">I", image, 0x1C, 0xC2339F3D)
    struct.pack_into(">III", image, 0x420, 0x2480, fst_at, fst_size)
    image[fst_at:fst_at + fst_size] = b"".join(struct.pack(">III", *entry) for entry in entries) + bytes(names)
    image[body_at:] = body
    return bytes(image)


def stage(files):
    """One stage: ``files`` = [(file word, bytes)] in one zlib folder at its sector."""
    blob, table = bytearray(), []
    for k, (word, data) in enumerate(files):
        table.append((word, len(blob)))
        blob += data + (bytes(-len(data) % 0x20) if k + 1 < len(files) else b"")
    packed = zlib.compress(bytes(blob), 6)
    ents = [(0x7F000002, len(blob)), (0x7E000000 | len(packed), 0)] + table + [(0x7F000000, len(blob))]
    head = struct.pack(">I", len(ents)) + b"".join(struct.pack(">II", *e) for e in ents)
    return head + bytes(-len(head) % 0x800) + packed


def stage_dat(stages):
    """stage.dat of ``stages`` = [(name, stage bytes)], each stage at its own sector."""
    head = bytearray(struct.pack(">IHHHHI", 0x401D1141, 1, 1, len(stages), 0xCCCC, 0x1234))
    body, sector = bytearray(), 1
    for name, data in stages:
        head += name.encode().ljust(8, b"\0") + struct.pack(">I", sector + len(body) // 0x800)
        body += data + bytes(-len(data) % 0x800)
    return bytes(head) + bytes(0x800 - len(head)) + bytes(body)


def disc_tree(demo, codec=b"codec"):
    """The files one disc needs: codec, module, subtitles, banner, and a stage.dat with a script and a font."""
    first = stage([(0x06180720, gcx_file()), (0x11383C45, font_file())])
    return {
        "shared": {"codec.dat": codec, "mgso.rel": b"module", "vox.dat": container([]), "movie.dat": container([])},
        "demo.dat": demo,
        "opening.bnr": b"banner",
        "stage.dat": stage_dat([("n_title", first)]),
    }


def _write(path, data):
    path.write_bytes(data)
    return str(path)


def _layout(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _unpack(tmp_path, discs):
    target = tmp_path / "text"
    target.mkdir()
    assert unpack.extract(discs, str(target), lambda p, t: None, lambda: False) == str(target)
    return target


# ---------------------------------------------------------------- roles and identity

def test_roles_are_disc1_and_disc2_and_the_header_names_the_disc(tmp_path):
    rules = GameRules(None)
    assert [r["id"] for r in rules.get_source_roles()] == ["disc1", "disc2"]
    first = _write(tmp_path / "anything.iso", gc_disc({"demo.dat": b"x"}, disc=0))
    second = _write(tmp_path / "other name.bin", gc_disc({"demo.dat": b"x"}, disc=1))
    assert rules.identify_source(first) == {"role": "disc1", "platform": "gc"}
    assert rules.identify_source(second) == {"role": "disc2", "platform": "gc"}
    europe = _write(tmp_path / "eu.iso", gc_disc({"demo.dat": b"x"}, game=b"GGSPA4"))
    assert rules.identify_source(europe) is None
    text = _write(tmp_path / "disc1.iso", b"not an image" * 100)
    assert rules.identify_source(text) is None


# ---------------------------------------------------------------- the layout

def test_two_discs_write_the_common_files_once_and_each_disc_its_own_subtitles(tmp_path):
    first = _write(tmp_path / "d1.iso", gc_disc(disc_tree(demo_container()), disc=0))
    second = _write(tmp_path / "d2.iso", gc_disc(disc_tree(demo_container()), disc=1))
    target = _unpack(tmp_path, {"disc1": first, "disc2": second})
    layout = _layout(target)
    assert {"common/codec.dat", "common/mgso.rel", "common/vox.subs", "common/movie.subs"} <= set(layout)
    assert "disc2/codec.dat" not in layout
    assert {"disc1/demo.subs", "disc2/demo.subs", "disc1/opening.bnr", "disc2/opening.bnr"} <= set(layout)
    # the second disc has the same script and font: each is written once, under the first disc's name
    assert [p for p in layout if p.startswith("stage/")] == ["stage/n_title.gcx"]
    assert [p for p in layout if p.startswith("font/")] == ["font/n_title_383c45.fnt"]
    assert "texture/n_title.stage" in layout
    assert (target / "common" / "codec.dat").read_bytes() == b"codec"


def test_a_common_file_that_differs_on_disc2_goes_to_disc2(tmp_path):
    first = _write(tmp_path / "d1.iso", gc_disc(disc_tree(demo_container(), codec=b"codec one"), disc=0))
    second = _write(tmp_path / "d2.iso", gc_disc(disc_tree(demo_container(), codec=b"codec two"), disc=1))
    target = _unpack(tmp_path, {"disc1": first, "disc2": second})
    assert (target / "common" / "codec.dat").read_bytes() == b"codec one"
    assert (target / "disc2" / "codec.dat").read_bytes() == b"codec two"


def test_one_disc_gives_what_that_disc_has(tmp_path):
    only = _write(tmp_path / "d2.iso", gc_disc(disc_tree(demo_container(), codec=b"codec two"), disc=1))
    target = _unpack(tmp_path, {"disc2": only})
    layout = _layout(target)
    assert {"common/codec.dat", "disc2/demo.subs", "disc2/opening.bnr"} <= set(layout)
    assert not any(p.startswith("disc1/") for p in layout)
    assert "disc2/codec.dat" not in layout
    assert (target / "common" / "codec.dat").read_bytes() == b"codec two"


def test_a_texture_stage_is_a_one_stage_file_that_reads_back(tmp_path):
    first = _write(tmp_path / "d1.iso", gc_disc(disc_tree(demo_container()), disc=0))
    target = _unpack(tmp_path, {"disc1": first})
    texture = StageDatContainer((target / "texture" / "n_title.stage").read_bytes())
    assert sorted(texture.list_files()) == ["n_title/06180720.bin", "n_title/11383c45.bin"]


def test_the_image_must_be_the_disc_its_role_names(tmp_path):
    disc_two = _write(tmp_path / "d2.iso", gc_disc(disc_tree(demo_container()), disc=1))
    with pytest.raises(ImageError, match="not Disc 1"):
        _unpack(tmp_path, {"disc1": disc_two})


def test_cancel_returns_none(tmp_path):
    first = _write(tmp_path / "d1.iso", gc_disc(disc_tree(demo_container()), disc=0))
    target = tmp_path / "text"
    target.mkdir()
    assert unpack.extract({"disc1": first}, str(target), lambda p, t: None, lambda: True) is None


def test_no_disc_gives_none_from_the_hook(tmp_path):
    assert GameRules(None).unpack_sources({}, str(tmp_path), lambda p, t: None, lambda: False) is None


# ---------------------------------------------------------------- the pieces

def test_subtitle_records_keep_their_bytes():
    raw = demo_container()
    records = subtitles.read(unpack._subs(raw, "demo"))
    assert [r.raw for r in records] == [r.raw for r in subtitles.scan(raw)]
    assert subtitles.kind_of(unpack._subs(raw, "demo")) == "cutscene"


def test_script_and_font_detection():
    assert unpack._gcx_has_text(gcx_file())
    assert unpack._is_font(font_file())
    assert not unpack._is_font(b"not a font at all, just letters" * 4)
    assert not unpack._gcx_has_text(b"\0" * 64)


# ---------------------------------------------------------------- the real discs

@romhacking_root.needs(disc_file(1), disc_file(2), TEXT)
def test_both_real_discs_unpack_to_the_workspace_text(tmp_path):
    target = tmp_path / "text"
    target.mkdir()
    discs = {f"disc{n}": str(romhacking_root.path(*disc_file(n))) for n in (1, 2)}
    assert unpack.extract(discs, str(target), lambda p, t: None, lambda: False) == str(target)

    def tree(folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}

    assert tree(target) == tree(romhacking_root.path(*TEXT))
