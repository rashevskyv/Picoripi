"""Professor Layton DS plugin: packs, scripts, databases and the rows of the editor; the game's files when present."""
import struct
from pathlib import Path

import pytest

from core.containers import layton_ds as pack_codec
from core.containers import level5, lz10
from plugins.layton_ds import formats
from plugins.layton_ds.formats import Document, EncodeError, FormatError
from plugins.testing import check_loads, check_round_trip, check_validator

LAYTON = Path(r"E:\Emulators\RomHacking\Professor Layton")


# -- builders ------------------------------------------------------------------------------------------------

def gds(commands, talk=False):
    """A ``.gds`` script from ``[(opcode bytes, [(type, value)])]`` (type 1 int, 3 text, 6 jump)."""
    body = bytearray()
    for index, (opcode, operands) in enumerate(commands):
        if not (talk and index == 0):
            body += struct.pack("<H", 0) + opcode
        for kind, value in operands:
            body += struct.pack("<H", kind)
            if kind in (1, 6, 7):
                body += struct.pack("<i", value)
            elif kind == 3:
                body += struct.pack("<H", len(value)) + value
    body += struct.pack("<H", 0xC)
    return struct.pack("<I", len(body)) + bytes(body)


def lscr(commands, strings):
    """``LSCR``: commands ``[(opcode, [operand])]``, an operand is ``("i", n)`` or ``("s", text)``."""
    bank = bytearray()
    where = {}
    for text in strings:
        where[text] = len(bank)
        bank += text.encode("cp932") + b"\0"
    table, ops = bytearray(), bytearray()
    first = 0
    for opcode, operands in commands:
        table += struct.pack("<HHI", opcode, len(operands), first)
        first += len(operands)
        for kind, value in operands:
            ops += (b"\0" + struct.pack("<i", value)) if kind == "i" else (b"\x02" + struct.pack("<I", where[value]))
    cmd_at = 0x10
    ops_at = cmd_at + len(table)
    bank_at = ops_at + len(ops)
    return b"LSCR" + struct.pack("<HHII", len(commands), cmd_at, ops_at, bank_at) + bytes(table) + bytes(ops) + bytes(bank)


def gsd1(strings, refs):
    """``GSD1`` with one string reference (type 0x18) per entry of ``refs`` (index into ``strings``)."""
    entries = struct.pack("<HHH", 0x04B0, 0, 2) + b"".join(struct.pack("<HHH", 0x04B1, 2 + 3 * i, 3) for i in range(1))
    ops_at = 0x10 + len(entries) + 2
    ops = bytearray()
    for index in refs:
        ops += b"\x01" + struct.pack("<i", 7)
    table_at = (ops_at + len(ops) + 3 + 5 * len(refs)) & ~3
    where, blob = [], bytearray(b"\0")
    for text in strings:
        where.append(table_at + len(blob))
        blob += text.encode("cp932") + b"\0"
    ops = bytearray()
    for index in refs:
        ops += b"\x18" + struct.pack("<I", where[index])
    ops_len = len(ops)
    head = b"GSD1" + struct.pack("<6H", 2, 4, ops_len // 5, 1, 2, 0)
    body = head + entries + b"\0\0" + bytes(ops)
    return body + bytes(table_at - len(body)) + bytes(blob)


# -- the rows ----------------------------------------------------------------------------------------------

def test_plugin_loads_and_validates():
    rules = check_loads("layton_ds")
    assert rules.get_display_name() == "Professor Layton (DS)"
    formats_ = {e for f in rules.get_file_formats() for e in f.extensions}
    assert {".pcm", ".plz", ".cpck", ".gds", ".cb"} <= formats_
    check_validator("layton_ds")


def test_lpck_pack_of_texts_round_trips_and_edits_grow_the_file():
    members = [pack_codec.Member(f"t{i}.txt", f"Line {i}\nsecond line".encode(), 16) for i in range(3)]
    plain = pack_codec.Pack(pack_codec.LPCK, members, b"", 16).build()
    raw = b"\x02\x00\x00\x00" + lz10.compress(plain)               # a Curious Village file: type prefix + LZ10
    check_round_trip("layton_ds", raw)
    doc = Document(raw)
    assert doc.texts() == ["Line 0\nsecond line", "Line 1\nsecond line", "Line 2\nsecond line"]
    assert doc.build(doc.texts()) == raw
    out = doc.build(["Hello", "Line 1\nsecond line", "A much longer third line of text"])
    again = Document(out)
    assert again.texts() == ["Hello", "Line 1\nsecond line", "A much longer third line of text"]
    assert out[:4] == b"\x02\x00\x00\x00"
    assert pack_codec.decompress(out)[0][:4] == b"\x10\x00\x00\x00"


def test_pack_kinds_rebuild_byte_for_byte():
    for kind, align in ((pack_codec.LPCK, 16), (pack_codec.LPCK, 4), (pack_codec.PCK2, 4), (pack_codec.LPC2, 4)):
        members = [pack_codec.Member("a.txt", b"x" * n, 16 if kind != pack_codec.LPC2 else 0) for n in (1, 4, 15, 16, 17)]
        plain = pack_codec.Pack(kind, members, b"", align).build()
        parsed = pack_codec.Pack.parse(plain)
        assert [m.data for m in parsed.members] == [m.data for m in members]
        assert parsed.build() == plain


def test_bios_streams_rle_huffman_and_prefix():
    plain = bytes(range(32)) * 4 + b"\x00" * 50
    rle = b"\x30" + len(plain).to_bytes(3, "little")
    data = bytearray(plain)
    out = bytearray()
    i = 0
    while i < len(data):
        run = 1
        while i + run < len(data) and data[i + run] == data[i] and run < 130:
            run += 1
        if run >= 3:
            out += bytes([0x80 | run - 3, data[i]])
            i += run
        else:
            j = i
            while j < len(data) and j - i < 128 and not (j + 2 < len(data) and data[j] == data[j + 1] == data[j + 2]):
                j += 1
            j = max(j, i + 1)
            out += bytes([j - i - 1]) + data[i:j]
            i = j
    assert pack_codec.bios_decompress(rle + bytes(out)) == plain
    stored = b"\x00" + len(plain).to_bytes(3, "little") + plain
    assert pack_codec.decompress(stored)[0] == plain
    assert pack_codec.recompress(stored, plain + b"!").startswith(b"\x00")           # stored stays stored
    with pytest.raises(ValueError):
        pack_codec.bios_decompress(b"\x77\x01\x00\x00")


def test_gds_texts_are_found_and_a_longer_text_moves_the_jumps():
    commands = [(b"J\0", [(1, 3)]),
                (b"m\0", [(3, b"layton_e_face.spr\0"), (3, b"Hello there, Luke!\0")]),
                (b"c\0", [(6, 0)]),
                (b"\0", [])]
    script = bytearray(gds(commands))
    # the jump (a position after the 4-byte length) goes to the last command
    position, jump_at, here = 4, 0, []
    while position < len(script) - 2:
        kind = struct.unpack_from("<H", script, position)[0]
        if kind == 0:
            here.append(position)
            position += 4
        elif kind in (1, 6):
            if kind == 6:
                jump_at = position + 2
            position += 6
        else:
            position += 4 + struct.unpack_from("<H", script, position + 2)[0]
    struct.pack_into("<i", script, jump_at, here[-1] - 4)
    doc = Document(bytes(script))
    assert [r.text for r in doc.rows] == ["Hello there, Luke!"]       # the sprite name is not text
    longer = doc.build(["Hello there, Luke! Please come and look at this."])
    assert Document(longer).texts() == ["Hello there, Luke! Please come and look at this."]
    assert struct.unpack_from("<I", longer, 0)[0] + 4 == len(longer)
    moved = struct.unpack_from("<i", longer, jump_at + len(longer) - len(script))[0]
    assert moved == here[-1] - 4 + len(longer) - len(script)         # the jump follows the growth
    assert doc.build(doc.texts()) == bytes(script)


def test_talk_script_nazo_record_and_database():
    talk = gds([(b"", [(1, 1), (3, b"b1 normal\0"), (3, b"NONE\0"), (1, 2), (3, b"What's that, Professor?\0")])], talk=True)
    doc = Document(talk)
    assert doc.texts() == ["What's that, Professor?"]
    assert Document(doc.build(["Look here, Luke."])).texts() == ["Look here, Luke."]
    # a Pandora's Box puzzle record: title (48 bytes), six string offsets at 0x40, the string bank at 112
    texts = [b"Complete the map.", b"Correct!", b"Wrong.", b"Hint one", b"Hint two", b"Hint three"]
    bank, offsets = b"", []
    for text in texts:
        offsets.append(len(bank))
        bank += text + b"\0"
    head = struct.pack("<HH", 1, 112) + b"Dr Schrader's Map".ljust(48, b"\0") + bytes(12) + struct.pack("<6I", *offsets)
    record = head + bytes(112 - len(head)) + bank
    codec = formats.NazoCodec(record, "n1.dat")
    assert [r.text for r in codec.rows][:2] == ["Dr Schrader's Map", "Complete the map."]
    assert codec.build(codec.texts()) == record
    new = codec.build(["Dr Schrader's Map", "Complete the map by sliding the pieces.", "Correct!", "Wrong.", "H1", "H2", "H3"])
    assert formats.NazoCodec(new, "n1.dat").rows[1].text == "Complete the map by sliding the pieces."
    with pytest.raises(EncodeError):
        codec.build(["T" * 60] + codec.texts()[1:])
    # a database file: 3 entries of 60 bytes with a 48-byte text at 4
    entries = b"".join(struct.pack("<I", i) + f"Event {i}".encode().ljust(48, b"\0") + bytes(8) for i in range(3))
    dlz = struct.pack("<HHI", 3, 8, 60) + entries
    doc = Document(lz10.compress(dlz))
    assert doc.texts() == ["Event 0", "Event 1", "Event 2"]
    assert Document(doc.build(["Event 0", "Gebeurtenis 1", "Event 2"])).texts()[1] == "Gebeurtenis 1"
    with pytest.raises(EncodeError):
        doc.build(["Event 0", "x" * 60, "Event 2"])


def test_lscr_dialogue_lines_have_a_speaker_and_a_longer_text_is_appended():
    script = lscr([(0x1770, [("i", 18)]),
                   (0x1771, [("i", 10), ("s", "レイトン"), ("s", "<V0000><T>Professor, I hope this letter finds you well.</V>")]),
                   (0x1771, [("i", 20), ("s", "OPルーク"), ("s", "<V0010><T>From...my future self?</V>")])],
                  ["レイトン", "<V0000><T>Professor, I hope this letter finds you well.</V>", "OPルーク", "<V0010><T>From...my future self?</V>"])
    doc = Document(script)
    assert [(r.speaker, r.kind) for r in doc.rows] == [("レイトン", "dialogue"), ("OPルーク", "dialogue")]
    assert doc.build(doc.texts()) == script
    out = doc.build(["<V0000><T>Professor, a much longer line of English text to write here.</V>", doc.rows[1].text])
    assert Document(out).texts()[0].startswith("<V0000><T>Professor, a much longer")
    assert Document(out).texts()[1] == doc.rows[1].text
    with pytest.raises(EncodeError):
        doc.build(["Ґанок і їжак", doc.rows[1].text])        # letters outside cp932 are refused, not mangled


def test_gsd1_strings_stay_in_place_when_shorter_and_move_to_the_end_when_longer():
    script = gsd1(["レイトン", "<T>That's a strange place for a\nwooden box.", "<T>Hmm."], [0, 1, 2])
    doc = Document(script)
    assert [(r.speaker, r.text) for r in doc.rows] == [("レイトン", "<T>That's a strange place for a\nwooden box."),
                                                      ("レイトン", "<T>Hmm.")]
    assert doc.build(doc.texts()) == script
    shorter = doc.build([doc.rows[0].text, "<T>Hm."])
    assert len(shorter) == len(script) and Document(shorter).texts()[1] == "<T>Hm."
    longer = doc.build(["<T>This is a considerably longer sentence than before.", doc.rows[1].text])
    assert len(longer) > len(script)
    assert Document(longer).texts()[0] == "<T>This is a considerably longer sentence than before."
    compressed = level5.compress(script)
    assert Document(compressed).texts() == doc.texts()
    assert level5.decompress(Document(compressed).build(doc.texts())) == script


def test_a_file_that_is_not_a_text_file_is_refused():
    with pytest.raises(FormatError):
        Document(bytes(range(256)) * 3)


# -- the game's own files ----------------------------------------------------------------------------------

WORKSPACES = [("Curious Village", "DS"), ("Pandora's Box", "DS"), ("Lost Future", "DS"), ("Spectre's Call", None)]


@pytest.mark.parametrize("game,platform", WORKSPACES)
def test_real_text_files_round_trip_and_edit(game, platform):
    root = LAYTON / game / (platform or "") / "source"
    if not root.is_dir():
        pytest.skip(f"{root} is missing")
    suffixes = (".pcm", ".plz", ".cpck", ".gds", ".cbin", ".cb", ".dlz")
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)[:400]
    checked = 0
    for path in files:
        raw = path.read_bytes()
        try:
            doc = Document(raw, path.name)
        except FormatError:
            continue
        if not doc.rows:
            continue
        assert doc.build(doc.texts()) == raw, path
        try:
            changed = doc.build([text + " X" for text in doc.texts()])
        except EncodeError:               # a fixed-width field of a database file: refused, not cut
            checked += 1
            continue
        assert Document(changed, path.name).texts() == [text + " X" for text in doc.texts()], path
        checked += 1
    assert checked > 0
