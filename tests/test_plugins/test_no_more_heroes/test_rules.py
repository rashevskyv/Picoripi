"""No More Heroes plugin: text blocks exported by the workspace script (load, save, other keys kept, Ukrainian),
tags, the HOME Menu table; the game's LZ, text codec and text box rebuild of the workspace script when it is on
this machine; the real fonts and text when the workspace is unpacked here."""
import importlib
import json
import sys
from pathlib import Path

import pytest

from core import font_formats
from core.formats import SaveContext
from plugins.no_more_heroes.rules import TAG_RE
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "no_more_heroes"
WS = Path(r"E:\Emulators\RomHacking\No More Heroes")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
real = pytest.mark.skipif(not (WS / "source" / "text" / "main.dol.nmt").exists(), reason="No More Heroes not unpacked here")

SAMPLE = {"file": "Title/TITLE.rsl", "blocks": [
    {"name": "MOVIE", "gdlg": ["/9/0"], "lines": [2, 3], "strings": ["I know a lot of gamers out there ", "Rank %02d"]},
    {"name": "SYS_SWEET", "gdlg": ["/15/1/0", "/15/6/0"], "lines": [1], "strings": ["Perfect for beginners."]}]}


def nmh():
    if not (SCRIPTS / "zt" / "nmh.py").is_file():
        pytest.skip("workspace scripts not on this machine")
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("zt.nmh")


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".nmt", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_saving_changes_only_the_strings():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["I know a lot of gamers out there ", "Rank %02d"], ["Perfect for beginners."]]
    assert names == {"0": "MOVIE", "1": "SYS_SWEET"}
    raw = json.dumps(SAMPLE).encode("utf-8")
    rules.prepare_save_context(SaveContext(relative_path="text/Title/TITLE.rsl.nmt", existing_versions=lambda: iter([raw])))
    blocks[1][0] = "Для новачків. Ґанок, їжак, є."
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["blocks"][1]["strings"] == ["Для новачків. Ґанок, їжак, є."]
    assert saved["blocks"][1]["gdlg"] == ["/15/1/0", "/15/6/0"] and saved["blocks"][0] == SAMPLE["blocks"][0]
    assert SAMPLE["blocks"][1]["strings"] == ["Perfect for beginners."]          # the loaded object is untouched


def test_tags():
    assert TAG_RE.fullmatch("<$8256>") and TAG_RE.fullmatch("%02d") and not TAG_RE.fullmatch("<w>")


def test_the_home_menu_table_shows_the_english_cells():
    text = "\r\n".join("\t".join(f'"{lang}{n}"' for lang in ("jp", "en", "de")) for n in range(2))
    blocks, _names = load_rules(PLUGIN).load_data_from_json_obj(b"\xfe\xff" + text.encode("utf-16-be"))
    assert blocks == [["en0", "en1"]]


def test_the_game_lz_round_trip():
    zt = nmh()
    data = b"RMHG" + bytes(40) + b"abcabcabcabc" * 50 + bytes(range(256)) * 3 + b"\x91" * 9
    packed = zt.lz_encode(data)
    assert zt.is_packed(packed) and zt.lz_decode(packed) == data and len(packed) < len(data)


def test_text_codec_and_box_rebuild():
    zt = nmh()
    raw = zt.encode_text("Привіт, Ґанок! <$8256> ’")
    assert zt.decode_text(raw) == "Привіт, Ґанок! ７ ’" and raw.startswith(b"\x84\x50")
    assert zt.codes_of(b"A\x84\x92") == [0x41, 0x8492]
    # a GDLG without dialogs: header, string offset table at 0x34, strings XOR 0x8D at 0x80
    import struct
    head = bytearray(0x80)
    head[:8] = b"GDLG\x01\x00\x00\x01"
    struct.pack_into("<HHIIII", head, 8, 0, 3, 0x40, 0x30, 0x80, 0x34)
    struct.pack_into("<III", head, 0x34, 0, 4, 8)
    blob = bytes(head) + bytes(b ^ 0x8D for b in b"BOX\0YES\0NO\0") + b"\x8d" * 5
    assert zt.gdlg_strings(blob) == [b"BOX", b"YES", b"NO"]
    new = zt.gdlg_with(blob, [b"BOX", "ТАК".encode("cp932"), b"NO"])
    assert zt.gdlg_strings(new) == [b"BOX", "ТАК".encode("cp932"), b"NO"] and len(new) % 0x10 == 0
    assert zt.gdlg_with(blob, zt.gdlg_strings(blob)) == blob


@real
def test_every_font_opens_and_packs_back_unchanged():
    sources = load_rules(PLUGIN).get_font_sources()
    grids = [s for s in sources if s["format"] == "texture_grid"]
    assert len(grids) >= 10
    for src in grids:
        data = (WS / "source" / src["path"]).read_bytes()
        backend = font_formats._backends()["texture_grid"]
        meta, sheets = backend.extract(data, src["params"])
        assert len(src["params"]["chars"]) == len(set(src["params"]["chars"]))
        assert "Ї" in src["params"]["chars"] and "ї" in src["params"]["chars"]          # the Ukrainian cells
        assert backend.pack(meta, sheets, data, src["params"]) == data, src["path"]


@real
def test_the_real_text_loads():
    rules = load_rules(PLUGIN)
    doc = json.loads((WS / "source" / "text" / "Title" / "TITLE.rsl.nmt").read_text(encoding="utf-8"))
    blocks, names = rules.load_data_from_json_obj(doc)
    assert any("Perfect for beginners." in b for b in blocks) and "MOVIE" in names.values()
    dol = json.loads((WS / "source" / "text" / "main.dol.nmt").read_text(encoding="utf-8"))
    assert any("Rising Star Games Ltd." in b["strings"] for b in dol["blocks"])
