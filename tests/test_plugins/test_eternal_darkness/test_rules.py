"""Eternal Darkness plugin: packs of string tables with byte-pair messages (load, save, layout after a longer
text), control codes, main.dol strings, the font format and the TPL members of a pack; the real files when the
workspace is unpacked here."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats
from core.font_formats import eternal_darkness as ed_font
from core.font_formats.sources import join_pair, split_pair
from core.formats import SaveContext
from plugins.eternal_darkness import edtext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "eternal_darkness"
GAME = Path(r"E:\Emulators\RomHacking\Eternal Darkness - Sanity’s Requiem\source\game")
real = pytest.mark.skipif(not (GAME / "EBootPak.bin").exists(), reason="Eternal Darkness not unpacked here")
TPL_STUB = b"\x00\x20\xaf\x30" + bytes(28) + b"T" * 32      # stands in for texture data


def message(text: bytes, font: int = 7) -> bytes:
    head = struct.pack(">fIHHIHHI", 1.0, 0xFFFFFFFF, 320, 200, 0, 3, font, 0) + b"c\0"
    plain = head + text + b"\0\0"
    return plain[16:20] + edtext.bpe_encode(plain)


def table(*texts: bytes) -> bytes:
    """A string table with its messages stored after the header."""
    blobs = [message(t) if t else b"" for t in texts]
    out = bytearray(struct.pack(">II", len(blobs), 0xFB90))
    at = 8 + 8 * len(blobs)
    body = b""
    for blob in blobs:
        out += struct.pack(">II", at + len(body), len(blob)) if blob else bytes(8)
        body += blob
    return bytes(out) + body


def pack(*entries: bytes) -> bytes:
    """A pack with each entry on 0x20 bytes (entry sizes are real, as in the game's top packs)."""
    head = bytearray(struct.pack(">II", len(entries), 0x6B5) + bytes(8 * len(entries)))
    out = bytearray(head + bytes(-len(head) % 0x20))
    for i, entry in enumerate(entries):
        struct.pack_into(">II", out, 8 + 8 * i, len(out), 8 if entry[4:8] == b"\0\0\xfb\x90" else len(entry))
        out += entry + bytes(-len(entry) % 0x20)
    return bytes(out)


SAMPLE = pack(table(b"Start \\ayGame\\aw", b"", b"~p cannot use \\i21 that now."), TPL_STUB,
              table(b"Yes", b"No"), TPL_STUB)


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".cmp", ".bin", ".dol"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_byte_pairs_decode_back_and_stay_shallow():
    text = (b"The \\ayDispel Magick spell\\aw cannot be cast at the current location. " * 6)
    blob = edtext.bpe_encode(text)
    assert len(blob) < len(text)
    assert edtext.bpe_decode(blob) == (text, len(blob))
    every = edtext.bpe_encode(bytes(range(256)))            # no free byte: a table with no pairs
    assert edtext.bpe_decode(every) == (bytes(range(256)), 3 + 2 + 256)


def test_control_codes_become_tags_and_ukrainian_goes_to_cp1251():
    raw = b"\\ayItem\\aw: ~p has \\i21 \\s0.6x\\n\n\\\\"
    shown = edtext.to_editor(raw)
    assert shown == "{ay}Item{aw}: {~p} has {i21} {s0.6}x{n}\n{\\}"
    assert edtext.from_editor(shown) == raw
    missing = set()
    assert edtext.from_editor("Їжак ґ ★", missing) == "Їжак ґ ?".encode("cp1251") and missing == {"★"}


def test_a_longer_text_moves_the_data_after_it_and_keeps_the_textures():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["Start {ay}Game{aw}", "{~p} cannot use {i21} that now."], ["Yes", "No"]]
    assert names == {"0": "Table 0", "1": "Table 2"}
    rules.prepare_save_context(SaveContext(relative_path="EBootPak.bin", existing_versions=lambda: iter([SAMPLE])))
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[0][1] = "{~p} не може зараз використати {i21} це. " * 3
    blocks[1][0] = "Так"
    saved = rules.save_data_to_json_obj(blocks, names)
    again, _names = rules.load_data_from_json_obj(saved)
    assert again == blocks
    members = edtext.pack_members(saved, TPL_STUB[:4], ".tpl")
    assert [name for name, _span in members] == ["1.tpl", "3.tpl"]
    for _name, (start, end) in members:
        assert start % 0x20 == 0 and saved[start:start + len(TPL_STUB)] == TPL_STUB
    sizes = [struct.unpack_from(">I", saved, 12 + 8 * i)[0] for i in range(4)]
    assert sizes == [8, len(TPL_STUB), 8, len(TPL_STUB)]


def test_messages_kept_together_after_all_tables_move_as_one_run():
    """Room texts: every table header first, then all messages back to back (sizes of tables are 8)."""
    first, second = table(b"Alex questions the presence"), table(b"The Dresser is locked!")
    heads = [first[:16], second[:16]]
    bodies = [first[16:], second[16:]]
    out = bytearray(struct.pack(">II", 2, 0x6B5) + bytes(16))
    at = [len(out), len(out) + 16]
    data_at = len(out) + 32
    struct.pack_into(">IIII", out, 8, at[0], 8, at[1], 8)
    run = bodies[0] + bodies[1]
    h0 = bytearray(heads[0])
    struct.pack_into(">I", h0, 8, data_at - at[0])
    h1 = bytearray(heads[1])
    struct.pack_into(">I", h1, 8, data_at + len(bodies[0]) - at[1])
    data = bytes(out + h0 + h1 + run)
    tf = edtext.parse(data)
    assert [m.text for b in tf.blocks() for m in b] == [b"Alex questions the presence", b"The Dresser is locked!"]
    new = edtext.build(tf, {(at[0], 0): b"Alex " * 40})
    assert [m.text for b in edtext.parse(new).blocks() for m in b] == [b"Alex " * 40, b"The Dresser is locked!"]


def test_the_font_grid_turns_column_major_and_upside_down_into_rows():
    image = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(image)
    params = {"grid": [4, 4]}
    for code in range(16):                       # cell of code c: column c // 4, row c % 4, counted from the bottom
        x, y = (code // 4) * 16, 48 - (code % 4) * 16
        draw.rectangle((x, y, x + 15, y + 15), fill=(code, 0, 0, 255))
    model = ed_font._to_model(image, params)
    assert [model.getpixel(((c % 4) * 16 + 8, (c // 4) * 16 + 8))[0] for c in range(16)] == list(range(16))
    assert ed_font._from_model(model, params).tobytes() == image.tobytes()


@real
def test_every_text_file_of_the_game_opens_and_saves_unchanged():
    files = [GAME / "EBootPak.bin", GAME / "EBookPak.bin", GAME / "EMemcardText.bin", *sorted(GAME.glob("RmTxt*.cmp")),
             *sorted(GAME.glob("Chars/cin*/cin*.bin"))]
    count = 0
    for path in files:
        data = path.read_bytes()
        tf = edtext.parse(data)
        count += sum(len(b) for b in tf.blocks())
        assert edtext.build(tf, {}) == data
    dol = (GAME / "sys" / "main.dol").read_bytes()
    strings = edtext.dol_strings(dol)
    assert edtext.build_dol(dol, [t for _o, _s, t in strings]) == dol
    assert count + len(strings) >= 4200


@real
def test_the_text_font_opens_with_its_widths_and_packs_back_the_same():
    data = join_pair((GAME / "EFonts.tpl").read_bytes(), (GAME / "EBootPak.bin").read_bytes())
    params = {"image": 0, "width_table": 0}
    metadata, sheets = font_formats.extract("eternal_darkness", data, params)
    widths = metadata["WID1"][0]["packets"]
    assert widths[ord("A")]["width"] == 18 and widths[ord("i")]["width"] == 7
    assert font_formats.pack("eternal_darkness", metadata, sheets, data, params) == data
    widths[ord("o")]["width"] = 20
    tpl, pack_bytes = split_pair(font_formats.pack("eternal_darkness", metadata, sheets, data, params))
    assert tpl == (GAME / "EFonts.tpl").read_bytes() and pack_bytes != (GAME / "EBootPak.bin").read_bytes()


@real
def test_textures_of_the_packs_are_members():
    data = (GAME / "EBootPak.bin").read_bytes()
    assert [name for name, _span in edtext.pack_members(data, TPL_STUB[:4], ".tpl")] == ["5.tpl"]
    sources = json.loads((Path(__file__).resolve().parents[3] / "plugins" / PLUGIN / "texture_sources.json")
                         .read_text(encoding="utf-8"))
    assert any(s.get("member") == "*.tpl" and s["path"] == "EBootPak.bin" for s in sources)
