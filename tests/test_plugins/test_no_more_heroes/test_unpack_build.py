"""No More Heroes unpack and build on a synthetic disc: one game file with a text box (RMHG tree, GDLG), read through a
fake reader, then an edited line packed back. The Wii writer's file placement is checked on a fake partition."""
import struct
from pathlib import Path
from types import SimpleNamespace

from plugins.no_more_heroes import build, gx, rmhg, unpack, wii_write
from plugins.no_more_heroes.rules import GameRules

GAME_FILE = "Title/TITLE.RSL"


def _gdlg(strings: list, lines: list) -> bytes:
    """A GDLG box: one dialog, one page, the given lines (indices into ``strings``)."""
    head = bytearray(0x100)
    head[:4] = b"GDLG"
    struct.pack_into("<HHIIII", head, 8, 1, len(strings), 0x40, 0x30, 0x100, 0x34)
    struct.pack_into("<I", head, 0x30, 0)                      # the dialog starts at the section
    struct.pack_into("<I", head, 0x44, 1)                      # one page
    struct.pack_into("<I", head, 0x60, 0x40)                   # the page starts at 0x40 + 0x40
    struct.pack_into("<H", head, 0x82, len(lines))
    for i, idx in enumerate(lines):
        struct.pack_into("<I", head, 0xA0 + 4 * i, 0x40 + 4 * i)
        struct.pack_into("<I", head, 0x80 + 0x40 + 4 * i, idx)
    pool, offsets = bytearray(), []
    for s in strings:
        offsets.append(len(pool))
        pool += s.encode("ascii") + b"\0"
    struct.pack_into(f"<{len(offsets)}I", head, 0x34, *offsets)
    return bytes(head) + bytes(b ^ rmhg.KEY for b in pool)


def _game_file(blob: bytes) -> bytes:
    """An RMHG file whose one chunk is ``blob``."""
    root = [b"RMHG" + struct.pack("<II", 1, 0x20) + bytes(0x20 - 12), [[bytes(0x20), blob]]]
    return rmhg.rmhg_save(root, b"")


class FakeReader:
    """What ``images.open_image`` gives: the entries of a disc and their bytes."""

    def __init__(self, files: dict) -> None:
        self.files = dict(files)
        self.files.setdefault("sys/main.dol", bytes(0x100))

    def entries(self) -> list:
        return [SimpleNamespace(path=p) for p in self.files]

    def read(self, entry) -> bytes:
        return self.files[entry.path]


def _disc() -> FakeReader:
    box = _gdlg(["BOX", "YES", "NO"], [1, 2])
    return FakeReader({f"files/{GAME_FILE}": _game_file(box)})


def test_unpack_writes_the_english_lines_and_the_index(tmp_path, monkeypatch):
    monkeypatch.setattr(unpack, "_unpack_loose", lambda disc, source, made: 0)
    done = unpack.unpack_disc(unpack.DiscFiles(_disc()), tmp_path, lambda *_: None, lambda: False)
    assert done is not None and done["fonts"] == 0
    doc = (tmp_path / "source" / "text" / "Title" / "TITLE.RSL.nmt").read_text(encoding="utf-8")
    assert '"YES"' in doc and '"NO"' in doc and '"BOX"' not in doc.split('"strings"')[1]
    assert (tmp_path / "nmh_index.json").is_file()


def test_unpack_stops_when_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(unpack, "_unpack_loose", lambda disc, source, made: 0)
    assert unpack.unpack_disc(unpack.DiscFiles(_disc()), tmp_path, lambda *_: None, lambda: True) is None


def test_an_edited_line_is_packed_back_into_the_game_file(tmp_path, monkeypatch):
    monkeypatch.setattr(unpack, "_unpack_loose", lambda disc, source, made: 0)
    disc = unpack.DiscFiles(_disc())
    unpack.unpack_disc(disc, tmp_path, lambda *_: None, lambda: False)
    source = tmp_path / "source"
    translation = tmp_path / "translation"
    doc = (source / "text" / "Title" / "TITLE.RSL.nmt").read_text(encoding="utf-8")
    edited = doc.replace('"NO"', '"BYE"')
    (translation / "text" / "Title").mkdir(parents=True)
    (translation / "text" / "Title" / "TITLE.RSL.nmt").write_text(edited, encoding="utf-8")
    index = __import__("json").loads((tmp_path / "nmh_index.json").read_text(encoding="utf-8"))
    changes, warnings = build.pack(translation, source, index, disc, lambda *_: None, lambda: False)
    assert warnings == [] and list(changes) == [f"files/{GAME_FILE}"]
    _packed, tree, _rest = rmhg.load_game_file(changes[f"files/{GAME_FILE}"])
    assert rmhg.gdlg_strings(rmhg.get(tree, "/0")) == [b"BOX", b"YES", b"BYE"]


def test_changed_files_lists_only_new_or_different_files(tmp_path):
    (tmp_path / "src" / "text").mkdir(parents=True)
    (tmp_path / "tr" / "text").mkdir(parents=True)
    (tmp_path / "src" / "text" / "a.nmt").write_bytes(b"1")
    (tmp_path / "tr" / "text" / "a.nmt").write_bytes(b"2")
    (tmp_path / "tr" / "text" / "b.nmt").write_bytes(b"3")
    (tmp_path / "tr" / "text" / "Thumbs.db").write_bytes(b"x")
    assert build.changed_files(tmp_path / "tr", tmp_path / "src") == ["text/a.nmt", "text/b.nmt"]


def test_grid_font_round_trip_keeps_the_glyphs():
    glyph = (3, 2, bytes([255, 0, 128, 0, 255, 0]))
    blob = gx.grid_write([glyph, None], (4, 3), 2)
    cells = gx.grid_read(blob, (4, 3), 2, 2)
    # I4 keeps 16 gray levels: 128 is stored as 136, 255 and 0 are exact
    assert cells[0][2][:3] == bytes([255, 0, 136]) and cells[0][2][4:7] == bytes([0, 255, 0])
    assert cells[1][2] == bytes(12)


def test_gct_picture_becomes_a_tpl_and_back():
    header = b"GCT0" + struct.pack(">IHH", gx.I4, 8, 8) + bytes(4) + struct.pack(">I", 0x40)
    gct = header + bytes(0x40 - len(header)) + bytes(range(0x20))          # 8 x 8 I4 is 32 bytes
    tpl = gx.gct_to_tpl(gct)
    assert tpl is not None and gx.tpl_image(tpl)["format"] == gx.I4
    assert gx.tpl_to_gct(tpl, gct) == gct


def test_a_grown_file_moves_to_the_first_free_gap():
    class Part:
        def __init__(self):
            self.writes = []

        def write(self, at, blob):
            self.writes.append((at, bytes(blob)))

    part = Part()
    table = {"files/a.bin": (0x100, 0x8000, 0x100), "files/b.bin": (0x110, 0x8100, 0x100)}
    used = {"files/a.bin": (0x8000, 0x8100), "files/b.bin": (0x8100, 0x8200)}
    wii_write._write_file(part, table, used, 0x4000, 0x100000, "files/a.bin", bytes(0x200))
    assert part.writes[0] == (0x10000, bytes(0x200))
    assert part.writes[-1] == (0x104, struct.pack(">II", 0x10000 >> 2, 0x200))


def test_a_shorter_file_keeps_its_place_and_its_tail_is_zeroed():
    class Part:
        def __init__(self):
            self.writes = []

        def write(self, at, blob):
            self.writes.append((at, bytes(blob)))

    part = Part()
    table = {"files/a.bin": (0x100, 0x8000, 0x100)}
    used = {"files/a.bin": (0x8000, 0x8100)}
    wii_write._write_file(part, table, used, 0x4000, 0x100000, "files/a.bin", b"ab")
    assert part.writes[0] == (0x8000, b"ab")
    assert part.writes[1] == (0x8002, bytes(0xFE))


def test_the_plugin_declares_the_wizard_hooks():
    rules = GameRules(None)
    assert rules.unpack_key_consoles() == ["wii"]
    assert rules.get_source_subfolder() == "source"
    assert [t["id"] for t in rules.get_build_targets()] == [build.TARGET_ISO]
    assert rules.identify_source(str(Path("missing.rvz"))) is None


def _source_of(tmp_path: Path, image: Path) -> tuple:
    """An unpacked folder (with its source mark) that points at ``image``; returns (source, translation, output)."""
    from plugins.common.disc_source import write_source_mark
    root = tmp_path / "unpacked"
    (root / "source").mkdir(parents=True)
    write_source_mark(root, image)
    (tmp_path / "translation").mkdir()
    (tmp_path / "out").mkdir()
    return root / "source", tmp_path / "translation", tmp_path / "out"


def test_a_rvz_source_is_refused_before_anything_is_written(tmp_path):
    image = tmp_path / "game.rvz"
    image.write_bytes(b"RVZ\x01" + bytes(64))
    source, translation, out = _source_of(tmp_path, image)
    try:
        build.build_iso(str(source), str(translation), str(out), lambda *_: None, lambda: False)
    except ValueError as error:
        assert "plain ISO" in str(error)
    else:
        raise AssertionError("an RVZ source must be refused")
    assert list(out.iterdir()) == []


def test_a_build_without_the_wii_key_file_says_so(tmp_path, monkeypatch):
    from core.project_library import console_keys
    image = tmp_path / "game.iso"
    image.write_bytes(bytes(64))
    source, translation, out = _source_of(tmp_path, image)
    monkeypatch.setattr(console_keys, "path_for", lambda console: None)
    try:
        build.build_iso(str(source), str(translation), str(out), lambda *_: None, lambda: False)
    except ValueError as error:
        assert "Wii key file" in str(error)
    else:
        raise AssertionError("a build without the key file must be refused")
